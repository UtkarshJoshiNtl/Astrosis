// Drop-in extension for frontend/main.py on branch alpha. The user pastes this
// over the existing 30-line file; it keeps the original /api/constellation
// behaviour but adds CORS + the endpoints the workbench needs.

export const FASTAPI_PATCH = `# frontend/main.py — Astrosis workbench server (drop-in extension)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from fastapi.responses import PlainTextResponse
import math, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine import backend_info
from engine.core.accelerator import propagate_batch
from engine.simulation import SimulationContext

FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
MU = 398600.4418
RE = 6371.0

app = FastAPI(title="Astrosis", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Reuse SimulationContext across requests for TLE caching / backend handle.
_sim = SimulationContext()

# Seed catalog identical to the original demo, kept so /api/constellation
# keeps working out of the box.
INITIAL_SATS = []
for i in range(500):
    r = RE + 400 + (i % 10) * 50
    v = 7.5 + (i % 5) * 0.1
    INITIAL_SATS.append([r, 0, 0, 0, v * 0.5, v * 0.866])


def _enrich(state):
    x, y, z, vx, vy, vz = state[:6]
    r = math.sqrt(x*x + y*y + z*z)
    v = math.sqrt(vx*vx + vy*vy + vz*vz)
    hx, hy, hz = y*vz - z*vy, z*vx - x*vz, x*vy - y*vx
    h = math.sqrt(hx*hx + hy*hy + hz*hz) or 1e-9
    incl = math.degrees(math.acos(max(-1.0, min(1.0, hz / h))))
    a = 1.0 / (2.0 / r - v*v / MU) if (2.0 / r - v*v / MU) > 0 else float("nan")
    period_min = (2 * math.pi * math.sqrt(a**3 / MU)) / 60.0 if a == a and a > 0 else None
    return {
        "pos": [x, y, z],
        "vel": [vx, vy, vz],
        "altitude_km": max(0.0, r - RE),
        "speed_kms": v,
        "inclination_deg": incl,
        "period_min": period_min,
    }


@app.get("/")
async def read_index():
    p = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(p):
        with open(p) as f:
            return HTMLResponse(f.read())
    return {"ok": True}


@app.get("/api/health")
async def health():
    info = backend_info() if callable(backend_info) else {}
    return {
        "backend": info.get("name", "Python"),
        "backend_kind": info.get("kind", "python"),
        "engine_version": info.get("version", "0.1"),
        "cuda_available": bool(info.get("cuda_available")),
        "cuda_device": info.get("cuda_device"),
        "ok": True,
    }


@app.get("/api/public/tle")
async def proxy_tle(group: str = "active"):
    import httpx, os
    FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "active.txt")
    sources = []

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            url = f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle"
            resp = await client.get(url)
            if resp.status_code == 200:
                sources.append(resp.text)
    except Exception:
        pass

    st_user = os.environ.get("SPACETRACK_USER")
    st_pass = os.environ.get("SPACETRACK_PASS")
    if st_user and st_pass:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                login = await client.post("https://www.space-track.org/ajaxauth/login",
                    data={"identity": st_user, "password": st_pass})
                if login.status_code == 200:
                    resp = await client.get("https://www.space-track.org/basicspaceradar/query/class/tle_latest/ORDINAL/NORAD_CAT_ID/EPOCH/now/format/tle")
                    if resp.status_code == 200:
                        sources.append(resp.text)
        except Exception:
            pass

    if os.path.exists(FALLBACK):
        with open(FALLBACK) as f:
            sources.append(f.read())

    if not sources:
        return PlainTextResponse("# No TLE sources available\n", status_code=503)
    return PlainTextResponse(sources[0])


@app.get("/api/constellation")
async def constellation(n: int = 500):
    states = propagate_batch(INITIAL_SATS[:n], dt_seconds=60, steps=1)
    return {
        "epoch": datetime.now(timezone.utc).isoformat(),
        "count": len(states),
        "source": "live",
        "backend": backend_info().get("name") if callable(backend_info) else "Python",
        "satellites": [{"id": i, **_enrich(s)} for i, s in enumerate(states)],
    }


@app.get("/api/catalog/{norad}")
async def catalog_entry(norad: int):
    try:
        sat = _sim.load_tle(str(norad))
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    el = getattr(sat, "elements", lambda: {})()
    return {"norad": norad, "name": getattr(sat, "name", str(norad)),
            "tle": [getattr(sat, "line1", ""), getattr(sat, "line2", "")],
            "elements": el}


class PropagateReq(BaseModel):
    norad: Optional[int] = None
    state: Optional[List[float]] = None
    hours: float = 6
    dt_seconds: float = 60


@app.post("/api/propagate")
async def propagate(req: PropagateReq):
    if req.norad is not None:
        sat = _sim.load_tle(str(req.norad))
        traj = _sim.propagate(sat, hours=req.hours, dt_seconds=req.dt_seconds)
    else:
        if not req.state or len(req.state) != 6:
            raise HTTPException(400, "state must be 6-vector")
        steps = int(req.hours * 3600 / req.dt_seconds)
        traj = propagate_batch([req.state], dt_seconds=req.dt_seconds, steps=steps)
    out = []
    base = datetime.now(timezone.utc).timestamp()
    for k, s in enumerate(traj[:10000]):
        out.append({"t": datetime.utcfromtimestamp(base + k * req.dt_seconds).isoformat() + "Z",
                    "pos": list(s[:3]), "vel": list(s[3:6])})
    return {"norad": req.norad, "ephemeris": out,
            "dt_seconds": req.dt_seconds, "hours": req.hours}


class PassesReq(BaseModel):
    norad: int
    lat_deg: float
    lon_deg: float
    alt_m: float = 0
    hours: float = 24


@app.post("/api/passes")
async def predict_passes(req: PassesReq):
    from engine.geo.analysis import predict_passes as _pp
    sat = _sim.load_tle(str(req.norad))
    return _pp(sat, req.lat_deg, req.lon_deg, req.alt_m, hours=req.hours)


class ConjReq(BaseModel):
    norads: List[int]
    hours: float = 24
    threshold_km: float = 5.0


@app.post("/api/conjunctions")
async def conjunctions(req: ConjReq):
    sats = [_sim.load_tle(str(n)) for n in req.norads]
    return _sim.conjunction_assessment(sats, hours=req.hours, threshold_km=req.threshold_km)


class HohmannReq(BaseModel):
    r1_km: float
    r2_km: float
    isp_s: Optional[float] = None
    dry_mass_kg: Optional[float] = None
    prop_mass_kg: Optional[float] = None


@app.post("/api/maneuver/hohmann")
async def hohmann(req: HohmannReq):
    return _sim.plan_hohmann_transfer(
        r1_km=req.r1_km, r2_km=req.r2_km,
        isp_s=req.isp_s, dry_mass_kg=req.dry_mass_kg,
        prop_mass_kg=req.prop_mass_kg)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
`;