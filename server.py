"""
Astrosis REST API Server
========================
FastAPI server wrapping the Astrosis orbital mechanics engine.
"""

import math
import json
import sys
import os
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any

import numpy as np
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sgp4.api import Satrec, jday

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.constants import MU, RE
from engine.core.accelerator import backend_info, propagate_batch, propagate_batch_full_history
from engine.io.data import tle_ingestor
from engine.geo.frames import eci_to_ecef, topocentric_aer, julian_date, equation_of_equinoxes, teme_to_eci

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("astrosis-server")

app = FastAPI(title="Astrosis API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Ephemeris cache (in-process dict + TTL) ──

_EPHEMERIS_CACHE: dict[str, Any] = {}
_CACHE_TTL_S = 60.0  # seconds before cache is considered stale


def _cache_get(key: str) -> Optional[Any]:
    entry = _EPHEMERIS_CACHE.get(key)
    if entry is None:
        return None
    if time.monotonic() - entry["ts"] > _CACHE_TTL_S:
        del _EPHEMERIS_CACHE[key]
        return None
    return entry["data"]


def _cache_set(key: str, data: Any) -> None:
    _EPHEMERIS_CACHE[key] = {"ts": time.monotonic(), "data": data}


def _backend_fields() -> dict:
    """Return backend info fields for inclusion in API responses."""
    info = backend_info() if callable(backend_info) else {}
    return {
        "backend": info.get("active", "python"),
        "backend_description": info.get("description", "Python / NumPy"),
        "cuda_available": bool(info.get("cuda", False)),
        "cuda_device": info.get("cuda_device"),
    }


# ── Load synthetic constellation from config file ──

_CONSTELLATION_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "config", "constellation.json"
)


def _load_constellation() -> list:
    """Load or generate the demo constellation."""
    try:
        with open(_CONSTELLATION_PATH) as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {"count": 500, "altitude_base_km": RE, "altitude_offset_min": 400,
               "altitude_offset_step": 50, "velocity_base_kms": 7.5, "velocity_step_kms": 0.1}

    sats = []
    base_r = cfg.get("altitude_base_km", RE)
    off_min = cfg.get("altitude_offset_min", 400)
    off_step = cfg.get("altitude_offset_step", 50)
    v_base = cfg.get("velocity_base_kms", 7.5)
    v_step = cfg.get("velocity_step_kms", 0.1)
    count = cfg.get("count", 500)

    for i in range(count):
        r = base_r + off_min + (i % 10) * off_step
        v = v_base + (i % 5) * v_step
        sats.append([r, 0, 0, 0, v * 0.5, v * 0.866])
    return sats


INITIAL_SATS = _load_constellation()


def _enrich(state: list) -> dict:
    x, y, z, vx, vy, vz = state
    r = math.sqrt(x * x + y * y + z * z)
    v = math.sqrt(vx * vx + vy * vy + vz * vz)
    hx = y * vz - z * vy
    hy = z * vx - x * vz
    hz = x * vy - y * vx
    h = math.sqrt(hx * hx + hy * hy + hz * hz) or 1e-9
    incl = math.degrees(math.acos(max(-1.0, min(1.0, hz / h))))
    denom = 2.0 / r - v * v / MU
    a = 1.0 / denom if denom > 0 else float("nan")
    period_min = (2 * math.pi * math.sqrt(a ** 3 / MU)) / 60.0 if not math.isnan(a) and a > 0 else None
    return {
        "pos": [x, y, z],
        "vel": [vx, vy, vz],
        "altitude_km": max(0.0, r - RE),
        "speed_kms": v,
        "inclination_deg": incl,
        "period_min": period_min,
        "sma_km": a if not math.isnan(a) else None,
    }


# ── Julian Date / TEME→ECI helpers ──
# Both julian_date() and equation_of_equinoxes() are imported from engine.geo.frames,
# which also provides teme_to_eci() with the correct velocity transport term.


def _load_tle_state(norad: int) -> tuple:
    sats = tle_ingestor.get_satellites(satellite_id=str(norad), force_refresh=False)
    if not sats:
        raise HTTPException(404, f"Satellite {norad} not found in Celestrak catalog")
    tle = sats[0]
    satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])
    now = datetime.now(timezone.utc)
    jd, jf = jday(now.year, now.month, now.day, now.hour, now.minute, now.second + now.microsecond / 1e6)
    err, rt, vt = satrec.sgp4(jd, jf)
    if err != 0:
        raise HTTPException(500, f"SGP4 propagation error (code {err})")
    re, ve = teme_to_eci(np.array(rt), np.array(vt), now)
    return re.tolist() + ve.tolist(), tle, now


# ── API Endpoints ────────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    info = backend_info() if callable(backend_info) else {}
    return {
        **_backend_fields(),
        "engine_version": "0.1.0",
        "ok": True,
    }


@app.get("/api/public/tle")
async def proxy_tle(group: str = "active"):
    FALLBACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "active.txt")
    sources = []

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
            resp = await client.get(url)
            if resp.status_code == 200:
                sources.append(("celestrak", resp.text))
    except Exception:
        pass

    space_track_user = os.environ.get("SPACETRACK_USER")
    space_track_pass = os.environ.get("SPACETRACK_PASS")
    if space_track_user and space_track_pass:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                login = await client.post("https://www.space-track.org/ajaxauth/login", data={
                    "identity": space_track_user, "password": space_track_pass,
                })
                if login.status_code == 200:
                    url = f"https://www.space-track.org/basicspaceradar/query/class/tle_latest/ORDINAL/NORAD_CAT_ID/EPOCH/now/format/tle"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        sources.append(("spacetrack", resp.text))
        except Exception:
            pass

    if os.path.exists(FALLBACK_PATH):
        with open(FALLBACK_PATH) as f:
            sources.append(("bundled", f.read()))

    if not sources:
        return PlainTextResponse("# No TLE sources available\n", status_code=503)

    source_name, text = sources[0]
    return PlainTextResponse(text)


@app.get("/api/constellation")
async def constellation(n: int = 500):
    cache_key = f"constellation:{n}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    states = propagate_batch(INITIAL_SATS[: min(n, len(INITIAL_SATS))], dt_seconds=60, steps=1)
    result = {
        **_backend_fields(),
        "epoch": datetime.now(timezone.utc).isoformat(),
        "count": len(states),
        "source": "live",
        "satellites": [{"id": i, **_enrich(s)} for i, s in enumerate(states)],
    }
    _cache_set(cache_key, result)
    return result


@app.get("/api/catalog/{norad}")
async def catalog_entry(norad: int):
    sats = tle_ingestor.get_satellites(satellite_id=str(norad), force_refresh=False)
    if not sats:
        raise HTTPException(404, f"Satellite {norad} not found")
    tle = sats[0]
    l1, l2 = tle["line1"], tle["line2"]

    incl_deg = float(l2[8:16])
    raan_deg = float(l2[17:25])
    ecc = float("0." + l2[26:33])
    argp_deg = float(l2[34:42])
    ma_deg = float(l2[43:51])
    mm = float(l2[52:63])

    period_min = 1440.0 / mm
    n_rad_s = mm * 2.0 * math.pi / 86400.0
    sma = (MU / (n_rad_s * n_rad_s)) ** (1.0 / 3.0)

    return {
        **_backend_fields(),
        "norad": norad,
        "name": tle["satellite_name"],
        "tle": [l1, l2],
        "elements": {
            "epoch": tle["epoch"].isoformat() if tle.get("epoch") else "",
            "sma_km": round(sma, 3),
            "ecc": ecc,
            "incl_deg": incl_deg,
            "raan_deg": raan_deg,
            "argp_deg": argp_deg,
            "mean_anom_deg": ma_deg,
            "period_min": round(period_min, 2),
            "apogee_km": round(sma * (1 + ecc) - RE, 1),
            "perigee_km": round(sma * (1 - ecc) - RE, 1),
        },
    }


class PropagateReq(BaseModel):
    norad: Optional[int] = None
    state: Optional[List[float]] = None
    hours: float = 6
    dt_seconds: float = 60


@app.post("/api/propagate")
async def propagate(req: PropagateReq):
    if req.norad is not None:
        state, tle, epoch = _load_tle_state(req.norad)
    elif req.state and len(req.state) == 6:
        state = list(req.state)
        epoch = datetime.now(timezone.utc)
    else:
        raise HTTPException(400, "Provide 'norad' or 'state' (6-element [x,y,z,vx,vy,vz])")

    steps = int(req.hours * 3600 / req.dt_seconds)
    if steps < 1:
        steps = 1
    steps = min(steps, 10000)

    history = propagate_batch_full_history([state], dt_seconds=req.dt_seconds, steps=steps)

    ephemeris = []
    for k in range(1, steps + 1):
        t = epoch + timedelta(seconds=k * req.dt_seconds)
        s = history[k, 0]
        ephemeris.append({
            "t": t.isoformat(),
            "pos": s[:3].tolist(),
            "vel": s[3:6].tolist(),
        })

    return {
        **_backend_fields(),
        "norad": req.norad,
        "ephemeris": ephemeris,
        "dt_seconds": req.dt_seconds,
        "hours": req.hours,
    }


class PassesReq(BaseModel):
    norad: int
    lat_deg: float
    lon_deg: float
    alt_m: float = 0
    hours: float = 24


@app.post("/api/passes")
async def predict_passes(req: PassesReq):
    state, tle, epoch = _load_tle_state(req.norad)
    lat_r = math.radians(req.lat_deg)
    lon_r = math.radians(req.lon_deg)
    alt_km = req.alt_m / 1000.0

    dt_step = 30.0
    steps = int(req.hours * 3600 / dt_step)

    history = propagate_batch_full_history(
        [state], dt_seconds=dt_step, steps=steps
    )

    passes_out = []
    cur_pass = None
    t = epoch

    for step in range(1, steps + 1):
        t += timedelta(seconds=dt_step)
        s = history[step, 0]

        r_eci = s[:3]
        r_ecef = eci_to_ecef(r_eci, t)
        az, el, _ = topocentric_aer(r_ecef, lat_r, lon_r, alt_km)
        el_deg = float(np.degrees(el))
        az_deg = float(np.degrees(az))

        if el_deg >= 10.0:
            if cur_pass is None:
                cur_pass = {"start": t.isoformat(), "max_el": el_deg, "az_s": az_deg}
            else:
                cur_pass["max_el"] = max(cur_pass["max_el"], el_deg)
            cur_pass["end"] = t.isoformat()
            cur_pass["az_e"] = az_deg
        else:
            if cur_pass is not None:
                s = datetime.fromisoformat(cur_pass["start"])
                e = datetime.fromisoformat(cur_pass["end"])
                passes_out.append({
                    "aos": cur_pass["start"],
                    "los": cur_pass["end"],
                    "max_el_deg": cur_pass["max_el"],
                    "az_aos_deg": cur_pass["az_s"],
                    "az_los_deg": cur_pass["az_e"],
                    "duration_s": (e - s).total_seconds(),
                })
                cur_pass = None

    if cur_pass is not None:
        s = datetime.fromisoformat(cur_pass["start"])
        e = datetime.fromisoformat(cur_pass["end"])
        passes_out.append({
            "aos": cur_pass["start"],
            "los": cur_pass["end"],
            "max_el_deg": cur_pass["max_el"],
            "az_aos_deg": cur_pass["az_s"],
            "az_los_deg": cur_pass["az_e"],
            "duration_s": (e - s).total_seconds(),
        })

    return {**_backend_fields(), "passes": passes_out, "norad": req.norad}


class ConjReq(BaseModel):
    norads: List[int]
    hours: float = 24
    threshold_km: float = 5.0


@app.post("/api/conjunctions")
async def conjunctions(req: ConjReq):
    from engine.core.accelerator import propagate_batch
    from engine.core.conjunction import ConjunctionDetector
    
    # Load states for all requested satellites
    sat_states = []
    sat_ids = []
    for norad in req.norads:
        try:
            state, tle, epoch = _load_tle_state(norad)
            sat_states.append(state)
            sat_ids.append(norad)
        except HTTPException:
            # Skip satellites not found in catalog
            continue
    
    if len(sat_states) < 2:
        return []
    
    # Detect conjunctions
    detector = ConjunctionDetector()
    warnings = detector.detect(
        sat_states=sat_states,
        debris_states=sat_states,  # Self-conjunction detection among the set
        lookahead_s=req.hours * 3600,
        step_s=60.0,
        mjd0=0.0,
    )
    
    # Format response to match frontend ConjunctionPair interface
    results = []
    for w in warnings:
        # Skip self-conjunctions (same satellite)
        if sat_ids[w.sat_id] == sat_ids[w.debris_id]:
            continue

        results.append({
            "a": sat_ids[w.sat_id],
            "b": sat_ids[w.debris_id],
            "tca": (datetime.now(timezone.utc) + timedelta(seconds=w.time_to_closest_approach)).isoformat(),
            "miss_km": w.current_distance,
            "rel_vel_kms": math.sqrt(sum(v*v for v in w.relative_velocity)),
            "pc": w.pc if w.pc_result.computed else None,
        })

    return {**_backend_fields(), "results": results}


class HohmannReq(BaseModel):
    r1_km: float
    r2_km: float
    isp_s: Optional[float] = None
    dry_mass_kg: Optional[float] = None
    prop_mass_kg: Optional[float] = None


@app.post("/api/maneuver/hohmann")
async def hohmann(req: HohmannReq):
    a_t = (req.r1_km + req.r2_km) / 2
    v1 = math.sqrt(MU / req.r1_km)
    v2 = math.sqrt(MU / req.r2_km)
    v_p = math.sqrt(MU * (2 / req.r1_km - 1 / a_t))
    v_a = math.sqrt(MU * (2 / req.r2_km - 1 / a_t))
    dv1 = abs(v_p - v1)
    dv2 = abs(v2 - v_a)
    dv_total = dv1 + dv2
    transfer_time = math.pi * math.sqrt(a_t ** 3 / MU)

    result = {
        **_backend_fields(),
        "r1_km": req.r1_km,
        "r2_km": req.r2_km,
        "dv1_kms": round(dv1, 6),
        "dv2_kms": round(dv2, 6),
        "dv_total_kms": round(dv_total, 6),
        "transfer_time_s": round(transfer_time, 1),
    }

    if req.isp_s is not None and req.dry_mass_kg is not None and req.prop_mass_kg is not None:
        m0 = req.dry_mass_kg + req.prop_mass_kg
        ve = req.isp_s * 9.80665
        mass_ratio = math.exp(dv_total * 1000 / ve)
        m_final = m0 / mass_ratio
        fuel_used = m0 - m_final
        result.update({
            "isp_s": req.isp_s,
            "mass_ratio": round(mass_ratio, 4),
            "fuel_used_kg": round(fuel_used, 2),
            "fuel_remaining_kg": round(max(0, req.prop_mass_kg - fuel_used), 2),
        })

    return result


if __name__ == "__main__":
    import signal
    import uvicorn

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    def _shutdown(sig, frame):
        server.should_exit = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    server.run()
