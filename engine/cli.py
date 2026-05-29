import argparse
import sys
import os
import logging
import json
import csv
import io
import math
from datetime import datetime, timezone

logger = logging.getLogger("Astrosis")


def _parse_state(arg: str) -> list:
    parts = [p.strip() for p in arg.split(",")]
    if len(parts) != 6:
        raise ValueError(f"State must have 6 components, got {len(parts)}")
    return [float(p) for p in parts]


def _load_csv(path: str) -> tuple:
    rows = []
    ids = []
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"Empty CSV: {path}")
        ncols = len(header)
        has_ids = ncols == 7
        if has_ids:
            for row in reader:
                ids.append(row[0])
                rows.append([float(x) for x in row[1:7]])
        else:
            for row in reader:
                ids.append(str(len(rows)))
                rows.append([float(x) for x in row[:6]])
    return ids, rows


def _tle_to_state(norad_id: int, start_dt=None) -> list:
    if start_dt is None:
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    from .io.data import tle_ingestor
    sats = tle_ingestor.get_satellites(satellite_id=str(norad_id), force_refresh=False)
    if not sats:
        raise ValueError(f"Satellite {norad_id} not found in TLE cache")
    from sgp4.api import Satrec, jday
    tle = sats[0]
    satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])
    jd, jdfrac = jday(
        start_dt.year, start_dt.month, start_dt.day,
        start_dt.hour, start_dt.minute,
        start_dt.second + start_dt.microsecond / 1e6,
    )
    err, r_teme, v_teme = satrec.sgp4(jd, jdfrac)
    if err != 0:
        raise ValueError(f"SGP4 propagation error (code {err})")
    import numpy as np
    from .geo.frames import teme_to_eci
    r_eci, v_eci = teme_to_eci(np.array(r_teme), np.array(v_teme), start_dt)
    return list(r_eci) + list(v_eci)


def _propagate(args):
    from .core.accelerator import propagate_steps, backend_info
    info = backend_info()
    logger.info("Backend: %s", info["description"])

    dt = args.dt or 60.0
    if args.steps:
        steps = args.steps
        total = steps * dt
        logger.info("Propagating %d steps (dt=%.1fs, %.2fh)", steps, dt, total / 3600)
    elif args.hours:
        total = args.hours * 3600
        steps = max(1, int(total / dt))
        total = steps * dt
        logger.info("Propagating ~%.2fh in %d steps (dt=%.1fs)", total / 3600, steps, dt)
    else:
        steps = 1440
        total = steps * dt
        logger.info("Propagating %d steps (dt=%.1fs, %.2fh) [default]", steps, dt, total / 3600)

    state = _parse_state(args.state) if "," in args.state else _tle_to_state(int(args.state))
    logger.info("Initial: [%.4f, %.4f, %.4f, %.6f, %.6f, %.6f]", *state)

    result = propagate_steps(
        state, total, dt,
        area=args.area, mass=args.mass, cd=args.cd, cr=args.cr,
        with_drag=args.drag, mjd0=args.mjd0 or 0.0,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump({
                "initial": state,
                "final": result,
                "steps": steps,
                "dt_seconds": dt,
                "total_seconds": total,
                "backend": info,
            }, f, indent=2)
        logger.info("Wrote %s", args.output)
    else:
        print(f"Propagated state after {steps} steps (dt={dt:.1f}s, {total/3600:.2f}h):")
        print(f"  Position: [{result[0]:.6f}, {result[1]:.6f}, {result[2]:.6f}] km")
        print(f"  Velocity: [{result[3]:.6f}, {result[4]:.6f}, {result[5]:.6f}] km/s")
        print(f"  Backend: {info['description']}")


def _batch(args):
    from .core.accelerator import propagate_batch, backend_info
    info = backend_info()
    logger.info("Backend: %s", info["description"])

    ids, states = _load_csv(args.file)
    n = len(states)
    logger.info("Loaded %d states from %s", n, args.file)

    dt = args.dt or 60.0
    if args.steps:
        steps = args.steps
    elif args.hours:
        steps = max(1, int(args.hours * 3600 / dt))
    else:
        steps = 1440
    total = steps * dt
    logger.info("Propagating %d steps (dt=%.1fs, %.2fh)", steps, dt, total / 3600)

    results = propagate_batch(
        states, dt, steps,
        area=args.area, mass=args.mass, cd=args.cd, cr=args.cr,
        with_drag=args.drag, mjd0=args.mjd0 or 0.0,
    )

    if args.output:
        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "x", "y", "z", "vx", "vy", "vz"])
            for iid, row in zip(ids, results):
                w.writerow([iid] + row)
        logger.info("Wrote %d results to %s", len(results), args.output)
    else:
        print(f"{'id':<10} {'x (km)':<14} {'y (km)':<14} {'z (km)':<14} "
              f"{'vx (km/s)':<14} {'vy (km/s)':<14} {'vz (km/s)':<14}")
        print("-" * 94)
        for iid, row in zip(ids, results):
            print(f"{iid:<10} {row[0]:<14.6f} {row[1]:<14.6f} {row[2]:<14.6f} "
                  f"{row[3]:<14.6f} {row[4]:<14.6f} {row[5]:<14.6f}")


def _conjunction(args):
    from .core.accelerator import detect_conjunctions, backend_info
    info = backend_info()
    logger.info("Backend: %s", info["description"])

    sat_ids, sat_states = _load_csv(args.primary)
    deb_ids, deb_states = _load_csv(args.secondary)
    logger.info("Loaded %d primary / %d secondary states", len(sat_states), len(deb_states))

    warnings = detect_conjunctions(
        sat_states, deb_states,
        lookahead=args.lookahead, step_s=args.step, mjd0=args.mjd0 or 0.0,
    )

    if args.output:
        results = []
        for w in warnings:
            results.append({
                "sat_id": w.sat_id,
                "debris_id": w.debris_id,
                "miss_distance_km": w.current_distance,
                "tca_seconds": w.time_to_closest_approach,
                "severity": w.severity.value,
                "relative_velocity_km_s": w.relative_velocity,
                "pc": w.pc,
            })
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        logger.info("Wrote %d warnings to %s", len(warnings), args.output)
    else:
        print(f"{'Sat':<8} {'Debris':<8} {'Miss (km)':<12} {'TCA (s)':<12} "
              f"{'Severity':<10} {'Rel vel (km/s)':<16} {'Pc':<14}")
        print("-" * 86)
        sev_colors = {
            "CRITICAL": "\033[91m",
            "WARNING": "\033[93m",
            "ADVISORY": "\033[94m",
            "NONE": "\033[90m",
        }
        reset = "\033[0m"
        for w in warnings:
            sv = w.severity.value
            sv_str = f"{sev_colors.get(sv, '')}{sv}{reset}"
            rv = w.relative_velocity
            rv_mag = math.sqrt(rv[0]**2 + rv[1]**2 + rv[2]**2)
            pc_str = f"{w.pc:.4e}" if hasattr(w, "pc") and w.pc > 0 else "N/A"
            print(f"{w.sat_id:<8} {w.debris_id:<8} {w.current_distance:<12.4f} "
                  f"{w.time_to_closest_approach:<12.1f} {sv_str:<10} "
                  f"{rv_mag:<16.4f} {pc_str:<14}")
    logger.info("Found %d conjunction warnings (%d critical, %d warning, %d advisory)",
                len([w for w in warnings if w.severity.value != "NONE"]),
                sum(1 for w in warnings if w.severity.value == "CRITICAL"),
                sum(1 for w in warnings if w.severity.value == "WARNING"),
                sum(1 for w in warnings if w.severity.value == "ADVISORY"))


def _ephemeris(args):
    from .core.ephemeris import sun_position_eci, moon_position_eci
    mjd = args.mjd
    sx, sy, sz = sun_position_eci(mjd)
    mx, my, mz = moon_position_eci(mjd)
    r_sun = math.sqrt(sx * sx + sy * sy + sz * sz)
    r_moon = math.sqrt(mx * mx + my * my + mz * mz)
    print(f"Ephemeris at MJD {mjd}:")
    print(f"  Sun:   [{sx:.3f}, {sy:.3f}, {sz:.3f}] km  (r={r_sun:.3f} km)")
    print(f"  Moon:  [{mx:.3f}, {my:.3f}, {mz:.3f}] km  (r={r_moon:.3f} km)")


def _backend(args):
    from .core.accelerator import backend_info
    info = backend_info()
    print(f"Active backend:    {info['active']}")
    print(f"Description:       {info['description']}")
    print(f"CUDA available:    {info['cuda']}")
    print(f"C++ available:     {info['cpp']}")
    print(f"NumPy batch:       {info.get('numpy_batch', False)}")
    print(f"Python fallback:   {info.get('python', True)}")


def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Astrosis — Orbital Mechanics Calculator"
    )
    parser.add_argument("--version", action="version", version="Astrosis 0.1.0")
    parser.add_argument("--mock-gpu", action="store_true",
                        help="Force CPU backend (skip CUDA even if GPU available)")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # fetch
    p = sub.add_parser("fetch", help="Fetch and cache TLE data")
    p.add_argument("--id", type=str, help="NORAD ID")
    p.add_argument("--force", action="store_true")

    # passes
    p = sub.add_parser("passes", help="Predict satellite passes")
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--alt", type=float, default=0.0)
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--output", type=str)
    p.add_argument("--area", type=float, default=10.0)
    p.add_argument("--mass", type=float, default=1000.0)
    p.add_argument("--cd", type=float, default=2.2)

    # backend
    p = sub.add_parser("backend", help="Show backend hardware info")

    # propagate
    p = sub.add_parser("propagate", help="Propagate a state or NORAD ID")
    p.add_argument("state", help="Comma-separated 'x,y,z,vx,vy,vz' or NORAD ID (digits only)")
    p.add_argument("--dt", type=float, default=60.0)
    p.add_argument("--steps", type=int, help="Number of steps")
    p.add_argument("--hours", type=float, help="Total hours (overrides --steps)")
    p.add_argument("--drag", action="store_true")
    p.add_argument("--area", type=float, default=10.0)
    p.add_argument("--mass", type=float, default=1000.0)
    p.add_argument("--cd", type=float, default=2.2)
    p.add_argument("--cr", type=float, default=1.5)
    p.add_argument("--mjd0", type=float, default=0.0)
    p.add_argument("--output", type=str)

    # batch
    p = sub.add_parser("batch", help="Batch propagate from CSV")
    p.add_argument("file", help="CSV with id,x,y,z,vx,vy,vz or x,y,z,vx,vy,vz")
    p.add_argument("--dt", type=float, default=60.0)
    p.add_argument("--steps", type=int)
    p.add_argument("--hours", type=float)
    p.add_argument("--drag", action="store_true")
    p.add_argument("--area", type=float, default=10.0)
    p.add_argument("--mass", type=float, default=1000.0)
    p.add_argument("--cd", type=float, default=2.2)
    p.add_argument("--cr", type=float, default=1.5)
    p.add_argument("--mjd0", type=float, default=0.0)
    p.add_argument("--output", type=str)

    # conjunction
    p = sub.add_parser("conjunction", help="Screen primary vs secondary states for conjunctions")
    p.add_argument("--primary", required=True, help="CSV: id,x,y,z,vx,vy,vz")
    p.add_argument("--secondary", required=True, help="CSV: id,x,y,z,vx,vy,vz")
    p.add_argument("--lookahead", type=float, default=86400.0)
    p.add_argument("--step", type=float, default=60.0)
    p.add_argument("--mjd0", type=float, default=0.0)
    p.add_argument("--output", type=str)

    # ephemeris
    p = sub.add_parser("ephemeris", help="Sun/moon positions at an MJD")
    p.add_argument("--mjd", type=float, required=True)

    args = parser.parse_args()

    if args.mock_gpu:
        os.environ["ASTROSIS_MOCK_GPU"] = "1"
        logger.info("Mock GPU enabled — forcing CPU backend")

    if args.command == "fetch":
        from .io.data import tle_ingestor
        sats = tle_ingestor.get_satellites(
            satellite_id=args.id, force_refresh=args.force
        )
        logger.info("Processed %d TLE entries.", len(sats))

    elif args.command == "passes":
        from .geo.analysis import report_passes
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Passes for %d from %sZ, %.1fh", args.id, start_dt.isoformat(), args.hours)
        result = report_passes(
            norad_id=args.id, lat=args.lat, lon=args.lon, alt=args.alt,
            start_dt=start_dt, hours=args.hours,
            sat_area=args.area, sat_mass=args.mass, sat_cd=args.cd,
        )
        if "error" in result:
            logger.error(result["error"])
            sys.exit(1)
        logger.info("Found %d passes.", len(result.get("passes", [])))
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            logger.info("Wrote %s", args.output)
        else:
            print(json.dumps(result, indent=2))

    elif args.command == "backend":
        _backend(args)

    elif args.command == "propagate":
        _propagate(args)

    elif args.command == "batch":
        _batch(args)

    elif args.command == "conjunction":
        _conjunction(args)

    elif args.command == "ephemeris":
        _ephemeris(args)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
