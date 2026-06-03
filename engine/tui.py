"""
engine/tui.py — Astrosis Terminal UI (Textual)
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Button,
    Input,
    DataTable,
    ListView,
    ListItem,
    Static,
)
from textual import work
from textual.binding import Binding

from engine.core.accelerator import backend_info, propagate_steps, detect_conjunctions
from engine.geo.cities import resolve_location
from engine.constants import RE

# ── Safe helpers (no sys.exit) ──────────────────────────────────────────────────


def _parse_state(arg: str) -> list | None:
    parts = [p.strip() for p in arg.split(",")]
    if len(parts) != 6:
        return None
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def _load_csv_safe(path: str) -> tuple | str:
    ids = []
    rows = []
    try:
        with open(path) as f:
            reader = csv.reader(f)
            first = next(reader, None)
            if first is None:
                return f"Empty CSV: {path}"
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
        return f"File not found: {path}"
    except (csv.Error, ValueError) as e:
        return f"Could not parse CSV at {path}: {e}"
    return ids, rows


def _tle_to_state_safe(norad_id: int) -> list | str:
    try:
        from engine.io.data import tle_ingestor

        sats = tle_ingestor.get_satellites(
            satellite_id=str(norad_id), force_refresh=False
        )
        if not sats:
            return f"Satellite {norad_id} not found in TLE cache."
        from sgp4.api import Satrec, jday
        import numpy as np
        from engine.geo.frames import teme_to_eci

        tle = sats[0]
        satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])
        start_dt = datetime.now(timezone.utc).replace(tzinfo=None)
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
            return f"SGP4 error (code {err}) for NORAD ID {norad_id}"
        r_eci, v_eci = teme_to_eci(np.array(r_teme), np.array(v_teme), start_dt)
        return list(r_eci) + list(v_eci)
    except Exception as e:
        return f"Error resolving NORAD ID {norad_id}: {e}"


def _get_backend_display() -> str:
    info = backend_info()
    if info.get("cuda"):
        try:
            import physics_engine as _pe

            gpu = getattr(_pe, "cuda_device_name", lambda: "NVIDIA GPU")()
            return f"CUDA · {gpu}"
        except Exception:
            return "CUDA"
    elif info.get("cpp"):
        return "C++ / OpenMP"
    return "Python"


def _altitude(state: list) -> float:
    r = math.sqrt(state[0] ** 2 + state[1] ** 2 + state[2] ** 2)
    return r - RE


def _speed(state: list) -> float:
    return math.sqrt(state[3] ** 2 + state[4] ** 2 + state[5] ** 2)


def _format_time(dt: datetime) -> str:
    return dt.strftime("%m-%d %H:%M:%S")


# ── App ─────────────────────────────────────────────────────────────────────────


class AstrosisApp(App[None]):
    CSS_PATH = "tui.css"

    BINDINGS = [
        Binding("tab", "switch_mode", "Switch"),
        Binding("e", "export", "Export"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_tab = "passes"
        self._passes_data: list = []
        self._conjunction_data: list = []
        self._conjunction_ids: tuple[list, list] = ([], [])
        self._last_results: dict | None = None
        self._propagate_initial: list | None = None
        self._propagate_final: list | None = None
        self._propagate_steps = 0
        self._propagate_dt = 0.0
        self._export_params: dict = {}

    # ── Compose ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(id="app-header")
        with Horizontal():
            with Vertical(id="input-panel"):
                yield Input(
                    id="norad-id", placeholder="NORAD ID", classes="passes-input"
                )
                yield Input(
                    id="city", placeholder="CITY (e.g. Mumbai)", classes="passes-input"
                )
                yield Input(
                    id="hours", placeholder="HOURS", value="24", classes="passes-input"
                )
                yield Input(id="prop-id", placeholder="NORAD ID", classes="prop-input")
                yield Input(
                    id="prop-state",
                    placeholder="State (x,y,z,vx,vy,vz)",
                    classes="prop-input",
                )
                yield Input(
                    id="prop-dt", placeholder="dt (s)", value="60", classes="prop-input"
                )
                yield Input(
                    id="prop-steps",
                    placeholder="steps",
                    value="1440",
                    classes="prop-input",
                )
                yield Input(
                    id="primary-csv",
                    placeholder="Primary CSV path",
                    classes="conj-input",
                )
                yield Input(
                    id="secondary-csv",
                    placeholder="Secondary CSV path",
                    classes="conj-input",
                )
                yield Input(
                    id="lookahead",
                    placeholder="Lookahead (s)",
                    value="86400",
                    classes="conj-input",
                )
                yield Button("Run", id="run-btn", variant="success")
                yield Static("MODE", id="mode-label")
                yield ListView(
                    ListItem(Static("passes")),
                    ListItem(Static("propagate")),
                    ListItem(Static("conjunction")),
                    id="mode-selector",
                )
            with Vertical(id="results-panel"):
                yield DataTable(id="results-table")
                yield Static(id="propagate-result", classes="hidden")
                yield Static(id="detail-strip")
        yield Footer()

    # ── Mount ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = "ASTROSIS"
        self._show_inputs_for_mode("passes")
        self.set_interval(1, self._update_clock)
        self._update_clock()
        table = self.query_one("#results-table", DataTable)
        self._set_passes_columns(table)
        self._show_empty_state()

    def _update_clock(self) -> None:
        now = datetime.now(timezone.utc)
        header = self.query_one("#app-header", Static)
        backend = _get_backend_display()
        header.update(
            f"ASTROSIS  │  {backend}  │  {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

    # ── Mode switching ───────────────────────────────────────────────────────

    def _show_inputs_for_mode(self, mode: str) -> None:
        for w in self.query(".passes-input"):
            w.display = mode == "passes"
        for w in self.query(".prop-input"):
            w.display = mode == "propagate"
        for w in self.query(".conj-input"):
            w.display = mode == "conjunction"

    def action_switch_mode(self) -> None:
        lv = self.query_one("#mode-selector", ListView)
        order = ["passes", "propagate", "conjunction"]
        try:
            idx = order.index(self._active_tab)
        except ValueError:
            idx = 0
        next_idx = (idx + 1) % len(order)
        lv.index = next_idx
        self._select_mode(order[next_idx])

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item is not None:
            order = ["passes", "propagate", "conjunction"]
            lv = self.query_one("#mode-selector", ListView)
            self._select_mode(order[lv.index])

    def _select_mode(self, mode: str) -> None:
        if mode == self._active_tab:
            return
        self._active_tab = mode
        self._show_inputs_for_mode(mode)
        self._clear_results()
        if mode == "conjunction":
            table = self.query_one("#results-table", DataTable)
            self._set_conjunction_columns(table)
        else:
            table = self.query_one("#results-table", DataTable)
            self._set_passes_columns(table)
        self._show_empty_state()

    def _set_passes_columns(self, table: DataTable) -> None:
        table.clear(columns=True)
        table.add_columns("TIME (UTC)", "MAX EL", "AZIMUTH", "DURATION", "VISIBLE")

    def _set_conjunction_columns(self, table: DataTable) -> None:
        table.clear(columns=True)
        table.add_columns("SAT", "DEBRIS", "MISS DIST", "TCA", "SEVERITY", "Pc")

    def _clear_results(self) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear(columns=True)
        table.display = True
        self.query_one("#propagate-result", Static).display = False
        self.query_one("#propagate-result", Static).update("")
        self.query_one("#detail-strip", Static).update("")
        self._passes_data = []
        self._conjunction_data = []
        self._last_results = None
        self._propagate_initial = None
        self._propagate_final = None

    def _show_empty_state(self) -> None:
        self.query_one("#detail-strip", Static).update("")

    # ── Input validation ─────────────────────────────────────────────────────

    def _flash_input(self, input_widget: Input) -> None:
        input_widget.add_class("input-error")
        self.set_timer(1.0, lambda: input_widget.remove_class("input-error"))

    def _validate_passes(self) -> bool:
        ok = True
        norad = self.query_one("#norad-id", Input)
        city = self.query_one("#city", Input)
        if not norad.value.strip():
            self._flash_input(norad)
            ok = False
        if not city.value.strip():
            self._flash_input(city)
            ok = False
        # hours can default to 24 if empty
        hours = self.query_one("#hours", Input)
        if not hours.value.strip():
            hours.value = "24"
        return ok

    def _validate_propagate(self) -> bool:
        ok = True
        pid = self.query_one("#prop-id", Input)
        pstate = self.query_one("#prop-state", Input)
        if not pid.value.strip() and not pstate.value.strip():
            self._flash_input(pid)
            self._flash_input(pstate)
            ok = False
        pdt = self.query_one("#prop-dt", Input)
        if not pdt.value.strip():
            pdt.value = "60"
        psteps = self.query_one("#prop-steps", Input)
        if not psteps.value.strip():
            psteps.value = "1440"
        return ok

    def _validate_conjunction(self) -> bool:
        ok = True
        pcsv = self.query_one("#primary-csv", Input)
        scsv = self.query_one("#secondary-csv", Input)
        if not pcsv.value.strip():
            self._flash_input(pcsv)
            ok = False
        if not scsv.value.strip():
            self._flash_input(scsv)
            ok = False
        la = self.query_one("#lookahead", Input)
        if not la.value.strip():
            la.value = "86400"
        return ok

    # ── Run dispatch ─────────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-btn":
            self._run_active_tab()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._run_active_tab()

    def _run_active_tab(self) -> None:
        if self._active_tab == "passes":
            if not self._validate_passes():
                return
            self._run_passes()
        elif self._active_tab == "propagate":
            if not self._validate_propagate():
                return
            self._run_propagate()
        elif self._active_tab == "conjunction":
            if not self._validate_conjunction():
                return
            self._run_conjunction()

    # ── Passes mode ──────────────────────────────────────────────────────────

    def _run_passes(self) -> None:
        norad_str = self.query_one("#norad-id", Input).value.strip()
        city_str = self.query_one("#city", Input).value.strip()
        hours_str = self.query_one("#hours", Input).value.strip()

        try:
            norad_id = int(norad_str)
        except ValueError:
            self._show_error(f"Invalid NORAD ID: {norad_str}")
            return
        try:
            hours = float(hours_str)
        except ValueError:
            self._show_error(f"Invalid hours: {hours_str}")
            return

        if "," in city_str:
            parts = [p.strip() for p in city_str.split(",")]
            if len(parts) == 2:
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    display_city = city_str
                except ValueError:
                    self._show_error(
                        f"Invalid lat,lon format: {city_str}. Use 'lat,lon' or a city name."
                    )
                    return
            else:
                self._show_error(
                    f"Invalid format: {city_str}. Use 'lat,lon' or a city name."
                )
                return
        else:
            try:
                lat, lon, display_city = resolve_location(city_str.lower())
            except ValueError as e:
                self._show_error(str(e))
                return

        self._export_params = {
            "norad_id": norad_id,
            "city": display_city,
            "hours": hours,
        }
        self._show_loading("Fetching TLE and propagating...")
        self.run_passes_worker(norad_id, lat, lon, 0.0, hours)

    @work(thread=True, exclusive=True)
    def run_passes_worker(
        self, norad_id: int, lat: float, lon: float, alt: float, hours: float
    ) -> None:
        from engine.geo.analysis import report_passes

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = report_passes(norad_id, lat, lon, alt, now, hours)
        self.call_from_thread(self._show_passes_result, result)

    def _show_passes_result(self, result: dict) -> None:
        if "error" in result:
            self._show_error(result["error"])
            return
        passes = result.get("passes", [])
        if not passes:
            self._show_error("No passes found in this window — try a longer horizon")
            return
        self._last_results = result
        self._passes_data = passes
        table = self.query_one("#results-table", DataTable)
        table.display = True
        table.clear(columns=True)
        self._set_passes_columns(table)
        for i, p in enumerate(passes):
            points = p.get("points", [])
            az_at_max = ""
            max_el_time = p.get("start_time", "")
            if points:
                best_pt = max(points, key=lambda pt: pt["el_deg"])
                az_at_max = f'{best_pt["az_deg"]:.1f}°'
                max_el_time = best_pt.get("time", max_el_time)
            t_start = datetime.fromisoformat(p["start_time"])
            t_end = datetime.fromisoformat(p["end_time"])
            secs = int((t_end - t_start).total_seconds())
            duration_str = f"{secs // 60}m {secs % 60}s"
            visible = p.get("visible", False)
            vis_text = "[green]●[/green]" if visible else "[dim]○[/dim]"
            time_str = t_start.strftime("%H:%M:%S")
            table.add_row(
                time_str,
                f'{p["max_elevation"]:.1f}°',
                az_at_max,
                duration_str,
                vis_text,
                key=str(i),
            )

    # ── Propagate mode ───────────────────────────────────────────────────────

    def _run_propagate(self) -> None:
        pid_str = self.query_one("#prop-id", Input).value.strip()
        state_str = self.query_one("#prop-state", Input).value.strip()
        dt_str = self.query_one("#prop-dt", Input).value.strip()
        steps_str = self.query_one("#prop-steps", Input).value.strip()

        if state_str:
            state = _parse_state(state_str)
            if state is None:
                self._show_error(
                    "Invalid state vector. Expected 6 comma-separated values: x,y,z,vx,vy,vz"
                )
                return
        elif pid_str:
            try:
                norad_id = int(pid_str)
            except ValueError:
                self._show_error(f"Invalid NORAD ID: {pid_str}")
                return
            state_or_err = _tle_to_state_safe(norad_id)
            if isinstance(state_or_err, str):
                self._show_error(state_or_err)
                return
            state = state_or_err
            self._export_params = {"norad_id": norad_id}
        else:
            self._show_error("Provide a NORAD ID or a state vector")
            return

        try:
            dt = float(dt_str)
            steps = int(steps_str)
        except ValueError:
            self._show_error("Invalid dt or steps value")
            return

        self._propagate_initial = list(state)
        self._export_params.update({"dt": dt, "steps": steps})
        self._show_loading("Propagating...")
        self.run_propagate_worker(list(state), dt, steps)

    @work(thread=True, exclusive=True)
    def run_propagate_worker(self, state: list, dt: float, steps: int) -> None:
        total = steps * dt
        result = propagate_steps(
            state,
            total,
            dt,
            area=0.0,
            mass=1.0,
            cd=2.2,
            cr=1.5,
            with_drag=False,
            mjd0=0.0,
        )
        self.call_from_thread(self._show_propagate_result, state, result, steps, dt)

    def _show_propagate_result(
        self, initial: list, final: list, steps: int, dt: float
    ) -> None:
        self._propagate_initial = initial
        self._propagate_final = final
        self._propagate_steps = steps
        self._propagate_dt = dt

        table = self.query_one("#results-table", DataTable)
        table.display = False
        self.query_one("#propagate-result", Static).display = True
        self.query_one("#detail-strip", Static).update("")

        alt0 = _altitude(initial)
        alt1 = _altitude(final)
        spd0 = _speed(initial)
        spd1 = _speed(final)

        lines = [
            "  component      initial         final",
            f"  {'─' * 37}",
            f"  x (km)       {initial[0]:>12.6f}  {final[0]:>12.6f}",
            f"  y (km)       {initial[1]:>12.6f}  {final[1]:>12.6f}",
            f"  z (km)       {initial[2]:>12.6f}  {final[2]:>12.6f}",
            f"  vx (km/s)    {initial[3]:>12.6f}  {final[3]:>12.6f}",
            f"  vy (km/s)    {initial[4]:>12.6f}  {final[4]:>12.6f}",
            f"  vz (km/s)    {initial[5]:>12.6f}  {final[5]:>12.6f}",
            f"  {'─' * 37}",
            f"  altitude     {alt0:>9.1f} km    {alt1:>9.1f} km",
            f"  speed        {spd0:>9.3f} km/s  {spd1:>9.3f} km/s",
            "",
            f"  steps={steps}  dt={dt:.1f}s  total={steps * dt / 3600:.2f}h",
        ]
        self.query_one("#propagate-result", Static).update("\n".join(lines))

    # ── Conjunction mode ─────────────────────────────────────────────────────

    def _run_conjunction(self) -> None:
        primary = self.query_one("#primary-csv", Input).value.strip()
        secondary = self.query_one("#secondary-csv", Input).value.strip()
        la_str = self.query_one("#lookahead", Input).value.strip()

        try:
            lookahead = float(la_str)
        except ValueError:
            self._show_error(f"Invalid lookahead: {la_str}")
            return

        r1 = _load_csv_safe(primary)
        if isinstance(r1, str):
            self._show_error(r1)
            return
        sat_ids, sat_states = r1

        r2 = _load_csv_safe(secondary)
        if isinstance(r2, str):
            self._show_error(r2)
            return
        deb_ids, deb_states = r2

        self._conjunction_ids = (sat_ids, deb_ids)
        self._export_params = {
            "primary": primary,
            "secondary": secondary,
            "lookahead": lookahead,
        }
        self._show_loading(f"Screening {len(sat_states)}×{len(deb_states)} pairs...")
        self.run_conjunction_worker(sat_states, deb_states, lookahead, sat_ids, deb_ids)

    @work(thread=True, exclusive=True)
    def run_conjunction_worker(
        self,
        sat_states: list,
        deb_states: list,
        lookahead: float,
        sat_ids: list,
        deb_ids: list,
    ) -> None:
        warnings = detect_conjunctions(
            sat_states, deb_states, lookahead=lookahead, step_s=60.0, mjd0=0.0
        )
        self.call_from_thread(self._show_conjunction_result, warnings, sat_ids, deb_ids)

    def _show_conjunction_result(
        self, warnings: list, sat_ids: list, deb_ids: list
    ) -> None:
        self._conjunction_data = warnings
        table = self.query_one("#results-table", DataTable)
        table.display = True
        table.clear(columns=True)
        self._set_conjunction_columns(table)
        self.query_one("#propagate-result", Static).display = False

        if not warnings:
            self._show_error("No conjunctions detected.")
            return

        for i, w in enumerate(warnings):
            sid = sat_ids[w.sat_id] if w.sat_id < len(sat_ids) else str(w.sat_id)
            did = (
                deb_ids[w.debris_id] if w.debris_id < len(deb_ids) else str(w.debris_id)
            )
            pc_str = f"{w.pc:.4e}" if w.pc > 0 else "N/A"
            sev = w.severity.value
            sev_styles = {
                "CRITICAL": "[red]CRITICAL[/red]",
                "WARNING": "[yellow]WARNING[/yellow]",
                "ADVISORY": "ADVISORY",
            }
            sev_text = sev_styles.get(sev, sev)
            table.add_row(
                sid,
                did,
                f"{w.current_distance:.4f}",
                f"{w.time_to_closest_approach:.1f}",
                sev_text,
                pc_str,
                key=str(i),
            )

    # ── Shared display helpers ───────────────────────────────────────────────

    def _show_loading(self, message: str) -> None:
        self.query_one("#propagate-result", Static).display = False
        self.query_one("#detail-strip", Static).update("")
        if self._active_tab == "propagate":
            table = self.query_one("#results-table", DataTable)
            table.display = False
            self.query_one("#propagate-result", Static).display = True
            self.query_one("#propagate-result", Static).update(f"[dim]{message}[/dim]")
        else:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            if self._active_tab == "conjunction":
                self._set_conjunction_columns(table)
            else:
                self._set_passes_columns(table)
            if self._active_tab == "conjunction":
                table.add_row("[dim]Loading...[/dim]", "", "", "", "", "")
            else:
                table.add_row("[dim]Loading...[/dim]", "", "", "", "")

    def _show_error(self, message: str) -> None:
        self.query_one("#propagate-result", Static).display = False
        self.query_one("#detail-strip", Static).update("")
        if self._active_tab == "propagate":
            table = self.query_one("#results-table", DataTable)
            table.display = False
            self.query_one("#propagate-result", Static).display = True
            self.query_one("#propagate-result", Static).update(f"[red]{message}[/red]")
        else:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            if self._active_tab == "conjunction":
                self._set_conjunction_columns(table)
                table.add_row("", "", "", "", f"[red]{message}[/red]", "")
            else:
                self._set_passes_columns(table)
                table.add_row(f"[red]{message}[/red]", "", "", "", "")

    # ── Detail strip ─────────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail-strip", Static)
        try:
            idx = int(event.row_key.value)
        except (ValueError, AttributeError):
            return

        if self._active_tab == "passes" and idx < len(self._passes_data):
            p = self._passes_data[idx]
            points = p.get("points", [])
            t_start = datetime.fromisoformat(p["start_time"])
            t_end = datetime.fromisoformat(p["end_time"])
            max_el = p["max_elevation"]
            rise_str = t_start.strftime("%H:%M")
            set_str = t_end.strftime("%H:%M")
            max_str = rise_str
            illuminated = p.get("visible", False)
            illum_text = "illuminated" if illuminated else "not illuminated"
            if points:
                best_pt = max(points, key=lambda pt: pt["el_deg"])
                t_max = datetime.fromisoformat(best_pt["time"])
                max_str = t_max.strftime("%H:%M")
            detail.update(
                f"rise {rise_str} · max {max_el:.1f}° at {max_str} · "
                f"set {set_str} · {illum_text}"
            )

        elif self._active_tab == "conjunction" and idx < len(self._conjunction_data):
            w = self._conjunction_data[idx]
            rv = w.relative_velocity
            rv_mag = math.sqrt(rv[0] * rv[0] + rv[1] * rv[1] + rv[2] * rv[2])
            pc_str = f"{w.pc:.4e}" if w.pc > 0 else "N/A"
            detail.update(f"relative velocity: {rv_mag:.4f} km/s  ·  Pc: {pc_str}")

    # ── Export ───────────────────────────────────────────────────────────────

    def action_export(self) -> None:
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"astrosis_{self._active_tab}_{date_str}.json"

        data = {}
        if self._active_tab == "passes" and self._last_results:
            data = self._last_results
            norad = self._export_params.get("norad_id", "")
            city = self._export_params.get("city", "unknown")
            filename = f"astrosis_passes_{norad}_{city}_{date_str}.json"
        elif self._active_tab == "propagate" and self._propagate_final:
            data = {
                "initial": self._propagate_initial,
                "final": self._propagate_final,
                "steps": self._propagate_steps,
                "dt_seconds": self._propagate_dt,
                "total_seconds": self._propagate_steps * self._propagate_dt,
            }
            pid = self._export_params.get("norad_id", "state")
            filename = f"astrosis_propagate_{pid}_{date_str}.json"
        elif self._active_tab == "conjunction" and self._conjunction_data:
            data = {
                "conjunctions": [
                    {
                        "sat_id": w.sat_id,
                        "debris_id": w.debris_id,
                        "miss_distance_km": w.current_distance,
                        "tca_seconds": w.time_to_closest_approach,
                        "severity": w.severity.value,
                        "relative_velocity_magnitude": math.sqrt(
                            sum(v * v for v in w.relative_velocity)
                        ),
                        "pc": w.pc,
                    }
                    for w in self._conjunction_data
                ]
            }
            filename = f"astrosis_conjunction_{date_str}.json"
        else:
            self.query_one("#detail-strip", Static).update(
                "[red]Nothing to export[/red]"
            )
            return

        try:
            filename = filename.replace(" ", "_").replace("/", "_")
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            self.query_one("#detail-strip", Static).update(
                f"[dim]Exported to {filename}[/dim]"
            )
        except Exception as e:
            self.query_one("#detail-strip", Static).update(
                f"[red]Export failed: {e}[/red]"
            )

    # ── Refresh ──────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._clear_results()
        if self._active_tab == "conjunction":
            table = self.query_one("#results-table", DataTable)
            self._set_conjunction_columns(table)
        else:
            table = self.query_one("#results-table", DataTable)
            self._set_passes_columns(table)
        self._show_empty_state()
        self.query_one("#detail-strip", Static).update("[dim]Refreshed[/dim]")
        self.set_timer(1.5, lambda: self.query_one("#detail-strip", Static).update(""))
