import argparse
import sys
import os
import logging
import json
import csv
import math
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

try:
    _VERSION = version("astrosis")
except PackageNotFoundError:
    _VERSION = "0.1.0"

console = Console()

logger = logging.getLogger("Astrosis")


def _parse_state(arg: str) -> list:
    parts = [p.strip() for p in arg.split(",")]
    if len(parts) != 6:
        console.print(
            Panel(
                f"[red]Invalid state format: '{arg}'[/red]\n"
                f"Expected 6 comma-separated values: [bold]x,y,z,vx,vy,vz[/bold]\n"
                f"Example: [bold]7000,0,0,0,7.5,0[/bold]",
                title="Error",
            )
        )
        sys.exit(1)
    try:
        return [float(p) for p in parts]
    except ValueError as e:
        console.print(Panel(f"[red]Invalid number in state: {e}[/red]", title="Error"))
        sys.exit(1)


def _load_csv(path: str) -> tuple:
    ids = []
    rows = []
    try:
        with open(path) as f:
            reader = csv.reader(f)
            first = next(reader, None)
            if first is None:
                raise ValueError(f"Empty CSV: {path}")
            ncols = len(first)
            if ncols == 7:
                for row in reader:
                    ids.append(row[0])
                    rows.append([float(x) for x in row[1:7]])
            else:
                try:
                    rows.append([float(x) for x in first[:6]])
                except ValueError:
                    pass
                for row in reader:
                    rows.append([float(x) for x in row[:6]])
                ids = [str(i) for i in range(len(rows))]
    except FileNotFoundError:
        console.print(Panel(f"[red]File not found: {path}[/red]", title="Error"))
        sys.exit(1)
    except (csv.Error, ValueError) as e:
        console.print(
            Panel(
                f"[red]Could not parse CSV at {path}[/red]\n"
                "[bold]Expected columns: id,x,y,z,vx,vy,vz[/bold]"
                " or [bold]x,y,z,vx,vy,vz[/bold]\n"
                f"[dim]{e}[/dim]",
                title="CSV Error",
            )
        )
        sys.exit(1)
    return ids, rows


def _tle_to_state(norad_id: int, start_dt=None) -> list:
    if start_dt is None:
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
    from .io.data import tle_ingestor

    sats = tle_ingestor.get_satellites(satellite_id=str(norad_id), force_refresh=False)
    if not sats:
        console.print(
            Panel(
                f"[red]Satellite {norad_id} not found in TLE cache.[/red]\n"
                f"Try [bold]astrosis fetch --id {norad_id}[/bold] first.",
                title="Error",
            )
        )
        sys.exit(1)
    from sgp4.api import Satrec, jday

    tle = sats[0]
    satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])
    jd, jdfrac = jday(
        start_dt.year,
        start_dt.month,
        start_dt.day,
        start_dt.hour,
        start_dt.minute,
        start_dt.second + start_dt.microsecond / 1e6,
    )
    err, r_teme, v_teme = satrec.sgp4(jd, jdfrac)
    if err != 0:
        console.print(
            Panel(
                f"[red]SGP4 propagation error (code {err})"
                f" for NORAD ID {norad_id}[/red]",
                title="Error",
            )
        )
        sys.exit(1)
    import numpy as np
    from .geo.frames import teme_to_eci

    r_eci, v_eci = teme_to_eci(np.array(r_teme), np.array(v_teme), start_dt)
    return list(r_eci) + list(v_eci)


def _fetch(args):
    from .io.data import tle_ingestor

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Fetching TLE data...", total=None)
        sats = tle_ingestor.get_satellites(
            satellite_id=args.id, force_refresh=args.force
        )
    if not sats:
        console.print(
            Panel(
                "[red]No TLE data found.[/red]\n"
                "Check your network connection or the NORAD ID.",
                title="Error",
            )
        )
        sys.exit(1)
    if args.id:
        console.print(
            f"[green]✓[/green] Found {len(sats)} TLE entry"
            f" for NORAD ID [bold]{args.id}[/bold]"
        )
    else:
        console.print(f"[green]✓[/green] Fetched and cached {len(sats)} TLE entries")


def _passes(args):
    from .geo.cities import resolve_location
    from .geo.analysis import report_passes

    if args.city and args.lon is not None:
        console.print(
            Panel(
                "[red]--lon cannot be used with --city.[/red] "
                "Use --city alone or --lat/--lon together.",
                title="Error",
            )
        )
        sys.exit(1)

    if args.city:
        try:
            lat, lon, city_name = resolve_location(args.city.lower())
        except ValueError as e:
            console.print(Panel(f"[red]{e}[/red]", title="City Not Found"))
            sys.exit(1)
        display_name = city_name.title()
    elif args.lat is not None and args.lon is not None:
        lat = args.lat
        lon = args.lon
        display_name = f"{lat}°, {lon}°"
    elif args.lat is not None:
        console.print(
            Panel(
                "[red]--lon is required when --lat is provided.[/red]",
                title="Error",
            )
        )
        sys.exit(1)
    else:
        console.print(
            Panel(
                "[yellow]Specify a location with"
                " --city <name> or --lat/--lon.[/yellow]\n"
                "Examples:\n"
                "  astrosis passes --city Mumbai --id 25544\n"
                "  astrosis passes --lat 19.076 --lon 72.8777 --id 25544",
                title="Usage",
            )
        )
        sys.exit(1)

    start_dt = datetime.now(timezone.utc).replace(tzinfo=None)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Propagating {args.id} over {display_name}...", total=None)
        result = report_passes(
            norad_id=args.id,
            lat=lat,
            lon=lon,
            alt=args.alt,
            start_dt=start_dt,
            hours=args.hours,
            sat_area=args.area,
            sat_mass=args.mass,
            sat_cd=args.cd,
        )

    if "error" in result:
        console.print(Panel(f"[red]{result['error']}[/red]", title="Error"))
        sys.exit(1)

    passes_data = result.get("passes", [])
    sat_name = result.get("satellite", f"SAT {args.id}")
    console.print(
        f"[bold]Found {len(passes_data)} passes for {sat_name} over "
        f"{display_name} in the next {args.hours}h[/bold]"
    )

    if not passes_data:
        return

    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Time (UTC)", style="cyan")
    table.add_column("Max Elevation", justify="right")
    table.add_column("Azimuth", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Visible", justify="center")

    for p in passes_data:
        points = p.get("points", [])
        az_at_max = ""
        if points:
            best_pt = max(points, key=lambda pt: pt["el_deg"])
            az_at_max = f"{best_pt['az_deg']:.1f}°"

        duration_str = ""
        if "start_time" in p and "end_time" in p:
            t_start = datetime.fromisoformat(p["start_time"])
            t_end = datetime.fromisoformat(p["end_time"])
            secs = int((t_end - t_start).total_seconds())
            duration_str = f"{secs // 60}m {secs % 60}s"

        visible = p.get("visible", False)
        visible_text = "[green]Yes[/green]" if visible else "[dim]No[/dim]"

        t_start = datetime.fromisoformat(p["start_time"])
        time_str = t_start.strftime("%H:%M:%S")

        table.add_row(
            time_str,
            f"{p['max_elevation']:.1f}°",
            az_at_max,
            duration_str,
            visible_text,
        )

    console.print(table)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2)
        console.print(f"[dim]Wrote {args.output}[/dim]")


def _backend(args):
    from .core.accelerator import backend_info

    info = backend_info()

    cuda_status = "[green]✓[/green]" if info["cuda"] else "[red]✗[/red]"
    cpp_status = "[green]✓[/green]" if info["cpp"] else "[red]✗[/red]"
    numpy_status = (
        "[green]✓[/green]" if info.get("numpy_batch", False) else "[dim]✗[/dim]"
    )
    python_status = "[green]✓[/green]"

    active = info["active"]
    active_color = {"cuda": "green", "cpp": "yellow", "python": "blue"}.get(
        active, "white"
    )

    lines = [
        f"[{active_color}]Active backend:"
        f" [bold]{active.upper()}[/bold][/{active_color}]",
        f"  {cuda_status} CUDA",
        f"  {cpp_status} C++ / OpenMP",
        f"  {numpy_status} NumPy batch",
        f"  {python_status} Python fallback",
        "",
        f"[dim]{info['description']}[/dim]",
    ]

    if info["cuda"]:
        try:
            import physics_engine as _pe

            gpu = getattr(_pe, "cuda_device_name", lambda: "NVIDIA GPU")()
            lines.append(f"\n[bold]GPU:[/bold] {gpu}")
        except Exception:
            pass

    console.print(Panel("\n".join(lines), title="Backend Status", border_style="bold"))


def _info(args):
    from .io.data import tle_ingestor
    from sgp4.api import Satrec, jday
    from .geo.frames import teme_to_eci, eci_to_ecef, ecef_to_geodetic
    from .constants import MU, RE
    import numpy as np

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Fetching TLE for {args.id}...", total=None)
        sats = tle_ingestor.get_satellites(
            satellite_id=str(args.id), force_refresh=False
        )

    if not sats:
        console.print(
            Panel(
                f"[red]Satellite {args.id} not found.[/red]\n"
                f"Try [bold]astrosis fetch --id {args.id}[/bold] first.",
                title="Error",
            )
        )
        sys.exit(1)

    tle = sats[0]
    satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])

    inclination = math.degrees(satrec.inclo)
    raan = math.degrees(satrec.nodeo)
    eccentricity = satrec.ecco
    arg_perigee = math.degrees(satrec.argpo)
    mean_anomaly = math.degrees(satrec.mo)
    mean_motion_rpm = satrec.no

    period_sec = 2.0 * math.pi / mean_motion_rpm * 60.0
    period_min = period_sec / 60.0

    no_rad_s = mean_motion_rpm / 60.0
    a = (MU / (no_rad_s * no_rad_s)) ** (1.0 / 3.0)

    perigee_alt = a * (1.0 - eccentricity) - RE
    apogee_alt = a * (1.0 + eccentricity) - RE

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    jd, jdfrac = jday(
        now.year,
        now.month,
        now.day,
        now.hour,
        now.minute,
        now.second + now.microsecond / 1e6,
    )
    err, r_teme, v_teme = satrec.sgp4(jd, jdfrac)

    if err != 0:
        console.print(
            Panel(
                f"[red]SGP4 propagation error (code {err})"
                f" for NORAD ID {args.id}[/red]",
                title="Error",
            )
        )
        sys.exit(1)

    r_eci, v_eci = teme_to_eci(np.array(r_teme), np.array(v_teme), now)
    altitude = float(np.linalg.norm(r_eci)) - RE

    r_ecef = eci_to_ecef(r_eci, now)
    lat_rad, lon_rad, _ = ecef_to_geodetic(r_ecef)
    lat_deg = float(np.degrees(lat_rad))
    lon_deg = float(np.degrees(lon_rad))

    epoch_str = (
        tle["epoch"].strftime("%Y-%m-%d %H:%M:%S UTC")
        if tle.get("epoch")
        else "Unknown"
    )

    identity = (
        f"[bold]Name:[/bold] {tle.get('satellite_name', 'Unknown')}\n"
        f"[bold]NORAD ID:[/bold] {args.id}\n"
        f"[bold]TLE Epoch:[/bold] {epoch_str}"
    )
    console.print(Panel(identity, title="Satellite Identity", border_style="green"))

    orb_table = Table(box=box.SIMPLE, header_style="bold cyan")
    orb_table.add_column("Parameter", style="cyan")
    orb_table.add_column("Value", justify="right")
    orb_table.add_row("Inclination", f"{inclination:.4f}°")
    orb_table.add_row("RAAN", f"{raan:.4f}°")
    orb_table.add_row("Eccentricity", f"{eccentricity:.6f}")
    orb_table.add_row("Arg. of Perigee", f"{arg_perigee:.4f}°")
    orb_table.add_row("Mean Anomaly", f"{mean_anomaly:.4f}°")
    orb_table.add_row("Period", f"{period_min:.2f} min ({period_sec:.0f} s)")
    orb_table.add_row("Semi-major Axis", f"{a:.3f} km")
    orb_table.add_row("Perigee Alt.", f"{perigee_alt:.1f} km")
    orb_table.add_row("Apogee Alt.", f"{apogee_alt:.1f} km")
    console.print(Panel(orb_table, title="Orbital Elements", border_style="blue"))

    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    lon_dir = "E" if lon_deg >= 0 else "W"
    state_text = (
        f"[bold]Position:[/bold]"
        f" [{r_eci[0]:.3f}, {r_eci[1]:.3f}, {r_eci[2]:.3f}] km\n"
        f"[bold]Velocity:[/bold] [{v_eci[0]:.6f}, {v_eci[1]:.6f}, {v_eci[2]:.6f}] km/s\n"
        f"[bold]Altitude:[/bold]"
        f" {altitude:.1f} km\n"
        f"[bold]Ground Track:[/bold] {abs(lat_deg):.4f}°{'N' if lat_deg >= 0 else 'S'}, "
        f"{abs(lon_deg):.4f}°{lon_dir}\n"
        f"[dim]As of {now_str} UTC[/dim]"
    )
    console.print(Panel(state_text, title="Current State (ECI)", border_style="yellow"))


def _propagate(args):
    from .core.accelerator import propagate_steps, backend_info
    from .constants import RE

    info = backend_info()

    dt = args.dt or 60.0
    if args.steps:
        steps = args.steps
        total = steps * dt
    elif args.hours:
        total = args.hours * 3600.0
        steps = max(1, int(total / dt))
        total = steps * dt
    else:
        steps = 1440
        total = steps * dt

    state = (
        _parse_state(args.state)
        if "," in args.state
        else _tle_to_state(int(args.state))
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Propagating {steps} steps...", total=None)
        result = propagate_steps(
            state,
            total,
            dt,
            area=args.area,
            mass=args.mass,
            cd=args.cd,
            cr=args.cr,
            with_drag=args.drag,
            mjd0=args.mjd0 or 0.0,
        )

    r = result[:3]
    altitude = math.sqrt(r[0] * r[0] + r[1] * r[1] + r[2] * r[2]) - RE

    if args.output:
        with open(args.output, "w") as f:
            json.dump(
                {
                    "initial": state,
                    "final": result,
                    "steps": steps,
                    "dt_seconds": dt,
                    "total_seconds": total,
                    "backend": info,
                },
                f,
                indent=2,
            )
        console.print(f"[dim]Wrote {args.output}[/dim]")
    else:
        table = Table(box=box.ROUNDED, header_style="bold cyan")
        table.add_column("Quantity", style="cyan")
        table.add_column("Value", justify="right")
        table.add_column("Unit", style="dim")
        table.add_row("Position X", f"{result[0]:.6f}", "km")
        table.add_row("Position Y", f"{result[1]:.6f}", "km")
        table.add_row("Position Z", f"{result[2]:.6f}", "km")
        table.add_row("Velocity X", f"{result[3]:.6f}", "km/s")
        table.add_row("Velocity Y", f"{result[4]:.6f}", "km/s")
        table.add_row("Velocity Z", f"{result[5]:.6f}", "km/s")
        table.add_row("Altitude", f"{altitude:.3f}", "km")
        console.print(
            f"[bold]Propagated after {steps} steps"
            f" (dt={dt:.1f}s, {total / 3600:.2f}h)[/bold]"
        )
        console.print(table)
        console.print(f"[dim]Backend: {info['description']}[/dim]")


def _batch(args):
    from .core.accelerator import propagate_batch, backend_info

    info = backend_info()
    ids, states = _load_csv(args.file)
    n = len(states)

    dt = args.dt or 60.0
    if args.steps:
        steps = args.steps
    elif args.hours:
        steps = max(1, int(args.hours * 3600.0 / dt))
    else:
        steps = 1440
    total = steps * dt

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"Propagating {n} satellites...", total=None)
        results = propagate_batch(
            states,
            dt,
            steps,
            area=args.area,
            mass=args.mass,
            cd=args.cd,
            cr=args.cr,
            with_drag=args.drag,
            mjd0=args.mjd0 or 0.0,
        )

    if args.output:
        with open(args.output, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "x", "y", "z", "vx", "vy", "vz"])
            for iid, row in zip(ids, results):
                w.writerow([iid] + row)
        console.print(f"[dim]Wrote {len(results)} results to {args.output}[/dim]")
    else:
        table = Table(box=box.ROUNDED, header_style="bold cyan")
        table.add_column("id", style="cyan")
        table.add_column("x (km)", justify="right")
        table.add_column("y (km)", justify="right")
        table.add_column("z (km)", justify="right")
        table.add_column("vx (km/s)", justify="right")
        table.add_column("vy (km/s)", justify="right")
        table.add_column("vz (km/s)", justify="right")
        for iid, row in zip(ids, results):
            table.add_row(str(iid), *(f"{v:.6f}" for v in row))
        console.print(
            f"[bold]Batch propagated {n} states ({steps} steps, dt={dt:.1f}s, "
            f"{total / 3600:.2f}h)[/bold]"
        )
        console.print(table)
        console.print(f"[dim]Backend: {info['description']}[/dim]")


def _conjunction(args):
    from .core.accelerator import detect_conjunctions

    sat_ids, sat_states = _load_csv(args.primary)
    deb_ids, deb_states = _load_csv(args.secondary)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(
            f"Screening {len(sat_states)}×{len(deb_states)} pairs...", total=None
        )
        warnings = detect_conjunctions(
            sat_states,
            deb_states,
            lookahead=args.lookahead,
            step_s=args.step,
            mjd0=args.mjd0 or 0.0,
        )

    if args.output:
        results = []
        for w in warnings:
            results.append(
                {
                    "sat_id": w.sat_id,
                    "debris_id": w.debris_id,
                    "miss_distance_km": w.current_distance,
                    "tca_seconds": w.time_to_closest_approach,
                    "severity": w.severity.value,
                    "relative_velocity_km_s": w.relative_velocity,
                    "pc": w.pc,
                }
            )
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        console.print(f"[dim]Wrote {len(results)} warnings to {args.output}[/dim]")

    if not warnings:
        console.print("[green]✓[/green] No conjunctions detected.")
        return

    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Sat", style="cyan")
    table.add_column("Debris", style="cyan")
    table.add_column("Miss (km)", justify="right")
    table.add_column("TCA (s)", justify="right")
    table.add_column("Severity")
    table.add_column("Rel vel (km/s)", justify="right")
    table.add_column("Pc", justify="right")

    sev_styles = {
        "CRITICAL": "on red bold white",
        "WARNING": "on yellow bold black",
        "ADVISORY": "on blue bold white",
    }

    for w in warnings:
        sv = w.severity.value
        rv = w.relative_velocity
        rv_mag = math.sqrt(rv[0] * rv[0] + rv[1] * rv[1] + rv[2] * rv[2])
        pc_str = f"{w.pc:.4e}" if w.pc > 0 else "N/A"
        table.add_row(
            str(w.sat_id),
            str(w.debris_id),
            f"{w.current_distance:.4f}",
            f"{w.time_to_closest_approach:.1f}",
            sv,
            f"{rv_mag:.4f}",
            pc_str,
            style=sev_styles.get(sv, ""),
        )

    console.print(table)

    counts = {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0}
    for w in warnings:
        sv = w.severity.value
        if sv in counts:
            counts[sv] += 1
    total = sum(counts.values())
    summary_lines = [
        f"Found {total} conjunction warning{'s' if total != 1 else ''}",
        f"[red]CRITICAL:[/red] {counts['CRITICAL']}",
        f"[yellow]WARNING:[/yellow] {counts['WARNING']}",
        f"[blue]ADVISORY:[/blue] {counts['ADVISORY']}",
    ]
    console.print(Panel("\n".join(summary_lines), title="Summary"))


def _ephemeris(args):
    from .core.ephemeris import sun_position_eci, moon_position_eci

    mjd = args.mjd
    sx, sy, sz = sun_position_eci(mjd)
    mx, my, mz = moon_position_eci(mjd)
    r_sun = math.sqrt(sx * sx + sy * sy + sz * sz)
    r_moon = math.sqrt(mx * mx + my * my + mz * mz)

    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("Body", style="cyan")
    table.add_column("Position (km)", justify="right")
    table.add_column("Distance (km)", justify="right")
    table.add_row("Sun", f"[{sx:.3f}, {sy:.3f}, {sz:.3f}]", f"{r_sun:.3f}")
    table.add_row("Moon", f"[{mx:.3f}, {my:.3f}, {mz:.3f}]", f"{r_moon:.3f}")
    console.print(f"[bold]Ephemeris at MJD {mjd}[/bold]")
    console.print(table)


_DISPATCH = {
    "fetch": _fetch,
    "passes": _passes,
    "backend": _backend,
    "info": _info,
    "propagate": _propagate,
    "batch": _batch,
    "conjunction": _conjunction,
    "ephemeris": _ephemeris,
}


def main():
    if len(sys.argv) == 1 or (
        len(sys.argv) == 2 and sys.argv[1] == "--mock-gpu"
    ):
        if "--mock-gpu" in sys.argv:
            os.environ["ASTROSIS_MOCK_GPU"] = "1"
        from engine.tui import AstrosisApp

        AstrosisApp().run()
        return

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(
        description="Astrosis — Orbital Mechanics Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"Astrosis {_VERSION}",
    )
    parser.add_argument(
        "--mock-gpu",
        action="store_true",
        help="Force CPU backend (skip CUDA even if GPU available)",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # fetch
    p = sub.add_parser("fetch", help="Fetch and cache TLE data")
    p.add_argument("--id", type=str, help="NORAD ID")
    p.add_argument("--force", action="store_true")

    # passes
    p = sub.add_parser("passes", help="Predict satellite passes")
    p.add_argument("--id", type=int, required=True)
    loc = p.add_mutually_exclusive_group()
    loc.add_argument("--city", type=str, help="City name (e.g. Mumbai, New York)")
    loc.add_argument("--lat", type=float, help="Latitude (used with --lon)")
    p.add_argument("--lon", type=float, help="Longitude (used with --lat)")
    p.add_argument("--alt", type=float, default=0.0)
    p.add_argument("--hours", type=float, default=24.0)
    p.add_argument("--output", type=str)
    p.add_argument("--area", type=float, default=10.0)
    p.add_argument("--mass", type=float, default=1000.0)
    p.add_argument("--cd", type=float, default=2.2)

    # backend
    sub.add_parser("backend", help="Show backend hardware info")

    # info
    p = sub.add_parser("info", help="Show satellite info from TLE")
    p.add_argument("--id", type=int, required=True)

    # propagate
    p = sub.add_parser("propagate", help="Propagate a state or NORAD ID")
    p.add_argument(
        "state",
        help="Comma-separated 'x,y,z,vx,vy,vz' or NORAD ID (digits only)",
    )
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
    p = sub.add_parser(
        "conjunction", help="Screen primary vs secondary states for conjunctions"
    )
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

    cmd = args.command
    if cmd in _DISPATCH:
        _DISPATCH[cmd](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
