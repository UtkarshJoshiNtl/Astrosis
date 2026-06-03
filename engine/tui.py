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
from textual.suggester import SuggestFromList
from textual.widgets import (
    Footer,
    Button,
    Input,
    DataTable,
    Static,
    TabbedContent,
    TabPane,
)
from textual import work
from textual.binding import Binding
from textual.worker import Worker, WorkerState

from engine.core.accelerator import backend_info, propagate_steps, detect_conjunctions
from engine.core.ephemeris import sun_position_eci, moon_position_eci
from engine.geo.cities import CITIES, resolve_location
from engine.constants import RE

# ── Safe helpers ─────────────────────────────────────────────────────────────


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


def _tle_get_satrec(norad_id: int) -> tuple | str:
    try:
        from engine.io.data import tle_ingestor
        from sgp4.api import Satrec

        sats = tle_ingestor.get_satellites(
            satellite_id=str(norad_id), force_refresh=False
        )
        if not sats:
            return f"Satellite {norad_id} not found in TLE cache."
        tle = sats[0]
        satrec = Satrec.twoline2rv(tle["line1"], tle["line2"])
        return tle, satrec
    except Exception as e:
        return f"Error loading TLE for NORAD ID {norad_id}: {e}"


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


# ── App ─────────────────────────────────────────────────────────────────────


class AstrosisApp(App[None]):
    CSS_PATH = "tui.css"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+e", "export", "Export"),
        Binding("f5", "refresh", "Refresh"),
        Binding("alt+1", "show_passes", "Passes", show=False),
        Binding("alt+2", "show_propagate", "Propagate", show=False),
        Binding("alt+3", "show_conjunction", "Conjunction", show=False),
        Binding("alt+4", "show_info", "Info", show=False),
        Binding("alt+5", "show_ephemeris", "Ephemeris", show=False),
        Binding("alt+6", "show_backend", "Backend", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._active_tab = "passes"
        self._worker_running = False
        self._spinner_idx = 0
        self._passes_data: list = []
        self._conjunction_data: list = []
        self._conjunction_ids: tuple[list, list] = ([], [])
        self._last_results: dict | None = None
        self._propagate_initial: list | None = None
        self._propagate_final: list | None = None
        self._propagate_steps = 0
        self._propagate_dt = 0.0
        self._export_params: dict = {}

    # ── Compose ──────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static(id="app-header")
        with Horizontal():
            with Vertical(id="input-panel"):
                with TabbedContent(initial="passes", id="mode-tabs"):
                    with TabPane("Passes", id="passes"):
                        yield Input(
                            id="passes-norad",
                            placeholder="NORAD ID",
                        )
                        yield Input(
                            id="passes-city",
                            placeholder='City name  or  "lat, lon"',
                            suggester=SuggestFromList(
                                list(CITIES.keys()), case_sensitive=False
                            ),
                        )
                        yield Input(
                            id="passes-hours",
                            placeholder="Hours  [24]",
                            value="24",
                        )
                        yield Static("── Drag ──", classes="section-label")
                        yield Input(
                            id="passes-area",
                            placeholder="Area (m²)  [10]",
                            value="10",
                        )
                        yield Input(
                            id="passes-mass",
                            placeholder="Mass (kg)  [1000]",
                            value="1000",
                        )
                        yield Input(
                            id="passes-cd",
                            placeholder="Cd  [2.2]",
                            value="2.2",
                        )
                    with TabPane("Propagate", id="propagate"):
                        yield Input(
                            id="prop-norad",
                            placeholder="NORAD ID",
                        )
                        yield Input(
                            id="prop-state",
                            placeholder="State  x,y,z,vx,vy,vz",
                        )
                        yield Input(
                            id="prop-dt",
                            placeholder="dt (s)  [60]",
                            value="60",
                        )
                        yield Input(
                            id="prop-steps",
                            placeholder="Steps  [1440]",
                            value="1440",
                        )
                        yield Static("── Drag / SRP ──", classes="section-label")
                        yield Input(
                            id="prop-area",
                            placeholder="Area (m²)  [0]",
                            value="0",
                        )
                        yield Input(
                            id="prop-mass",
                            placeholder="Mass (kg)  [1]",
                            value="1",
                        )
                        yield Input(
                            id="prop-cd",
                            placeholder="Cd  [2.2]",
                            value="2.2",
                        )
                        yield Input(
                            id="prop-cr",
                            placeholder="Cr  [1.5]",
                            value="1.5",
                        )
                        yield Input(
                            id="prop-mjd0",
                            placeholder="MJD0  [0]",
                            value="0",
                        )
                    with TabPane("Conjunction", id="conjunction"):
                        yield Input(
                            id="conj-primary",
                            placeholder="Primary CSV path",
                        )
                        yield Input(
                            id="conj-secondary",
                            placeholder="Secondary CSV path",
                        )
                        yield Input(
                            id="conj-lookahead",
                            placeholder="Lookahead (s)  [86400]",
                            value="86400",
                        )
                        yield Static("── Advanced ──", classes="section-label")
                        yield Input(
                            id="conj-step",
                            placeholder="Step (s)  [60]",
                            value="60",
                        )
                        yield Input(
                            id="conj-mjd0",
                            placeholder="MJD0  [0]",
                            value="0",
                        )
                    with TabPane("Info", id="info"):
                        yield Input(
                            id="info-norad",
                            placeholder="NORAD ID",
                        )
                    with TabPane("Ephemeris", id="ephemeris"):
                        yield Input(
                            id="eph-mjd",
                            placeholder="MJD  (blank = now)",
                            value="",
                        )
                    with TabPane("Backend", id="backend"):
                        yield Static("Press Run to query backend status")
                yield Button("Find Passes", id="run-btn", variant="success")
                yield Static("Ready", id="status-line")
            with Vertical(id="results-panel", classes="mode-passes"):
                yield DataTable(id="results-table")
                yield Static(id="text-result", classes="hidden")
                yield Static(id="detail-strip")
        yield Footer()

    # ── Mount ────────────────────────────────────────────────────────────────

    def on_mount(self) -> None:
        self.title = "ASTROSIS"
        table = self.query_one("#results-table", DataTable)
        self._set_passes_columns(table)
        self._show_empty_state()
        self.set_interval(0.25, self._update_clock)
        self._update_clock()
        self._update_button_for_mode("passes")
        self._set_status("[dim]Ready — pick a mode and press Run[/dim]")

    _spinner_frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def _update_clock(self) -> None:
        now = datetime.now(timezone.utc)
        header = self.query_one("#app-header", Static)
        backend = _get_backend_display()
        mode_name = self._active_tab.capitalize()
        utc_str = now.strftime("%Y-%m-%d %H:%M:%S")
        if self._worker_running:
            self._spinner_idx = (self._spinner_idx + 1) % len(self._spinner_frames)
            utc_str += f"  {self._spinner_frames[self._spinner_idx]}"
        header.update(f"ASTROSIS  │  {mode_name}  │  {backend}  │  {utc_str} UTC")

    # ── Mode switching ───────────────────────────────────────────────────────

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        pane = event.pane
        if pane and pane.id in {
            "passes",
            "propagate",
            "conjunction",
            "info",
            "ephemeris",
            "backend",
        }:
            self._select_mode(pane.id)

    def _select_mode(self, mode: str) -> None:
        if mode == self._active_tab:
            return
        self._active_tab = mode
        self._clear_results()
        table = self.query_one("#results-table", DataTable)
        if mode == "conjunction":
            self._set_conjunction_columns(table)
        else:
            self._set_passes_columns(table)
        self._show_empty_state()
        self._set_status("Ready")
        self._update_clock()
        self._update_button_for_mode(mode)
        panel = self.query_one("#results-panel")
        for cls in self._MODE_CLASSES.values():
            panel.remove_class(cls)
        panel.add_class(self._MODE_CLASSES.get(mode, "mode-passes"))

    def _switch_tab(self, mode: str) -> None:
        tabs = self.query_one("#mode-tabs", TabbedContent)
        if tabs.active != mode:
            tabs.active = mode

    def action_show_passes(self) -> None:
        self._switch_tab("passes")

    def action_show_propagate(self) -> None:
        self._switch_tab("propagate")

    def action_show_conjunction(self) -> None:
        self._switch_tab("conjunction")

    def action_show_info(self) -> None:
        self._switch_tab("info")

    def action_show_ephemeris(self) -> None:
        self._switch_tab("ephemeris")

    def action_show_backend(self) -> None:
        self._switch_tab("backend")

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
        text_result = self.query_one("#text-result", Static)
        text_result.display = False
        text_result.update("")
        self.query_one("#detail-strip", Static).update("")
        self._passes_data = []
        self._conjunction_data = []
        self._last_results = None
        self._propagate_initial = None
        self._propagate_final = None

    def _show_empty_state(self) -> None:
        self.query_one("#detail-strip", Static).update("")

    def _set_status(self, message: str) -> None:
        self.query_one("#status-line", Static).update(message)

    _MODE_LABELS = {
        "passes": "Find Passes",
        "propagate": "Propagate",
        "conjunction": "Screen",
        "info": "Get Info",
        "ephemeris": "Show Ephemeris",
        "backend": "Query",
    }

    _MODE_CLASSES = {
        "passes": "mode-passes",
        "propagate": "mode-propagate",
        "conjunction": "mode-conjunction",
        "info": "mode-info",
        "ephemeris": "mode-ephemeris",
        "backend": "mode-backend",
    }

    def _update_button_for_mode(self, mode: str) -> None:
        if self._worker_running:
            return
        label = self._MODE_LABELS.get(mode, "Run")
        self.query_one("#run-btn", Button).label = label

    def _set_worker_running(self, running: bool) -> None:
        self._worker_running = running
        btn = self.query_one("#run-btn", Button)
        if running:
            btn.label = "Running…"
            btn.disabled = True
        else:
            btn.disabled = False
            self._update_button_for_mode(self._active_tab)

    # ── Input validation ─────────────────────────────────────────────────────

    def _flash_input(self, input_widget: Input) -> None:
        input_widget.add_class("input-error")
        self.set_timer(1.0, lambda: input_widget.remove_class("input-error"))

    def _validate_passes(self) -> bool:
        ok = True
        norad = self.query_one("#passes-norad", Input)
        city = self.query_one("#passes-city", Input)
        if not norad.value.strip():
            self._flash_input(norad)
            ok = False
        if not city.value.strip():
            self._flash_input(city)
            ok = False
        hours = self.query_one("#passes-hours", Input)
        if not hours.value.strip():
            hours.value = "24"
        area = self.query_one("#passes-area", Input)
        if not area.value.strip():
            area.value = "10"
        mass = self.query_one("#passes-mass", Input)
        if not mass.value.strip():
            mass.value = "1000"
        cd = self.query_one("#passes-cd", Input)
        if not cd.value.strip():
            cd.value = "2.2"
        return ok

    def _validate_propagate(self) -> bool:
        ok = True
        pid = self.query_one("#prop-norad", Input)
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
        pcsv = self.query_one("#conj-primary", Input)
        scsv = self.query_one("#conj-secondary", Input)
        if not pcsv.value.strip():
            self._flash_input(pcsv)
            ok = False
        if not scsv.value.strip():
            self._flash_input(scsv)
            ok = False
        la = self.query_one("#conj-lookahead", Input)
        if not la.value.strip():
            la.value = "86400"
        step = self.query_one("#conj-step", Input)
        if not step.value.strip():
            step.value = "60"
        return ok

    def _validate_info(self) -> bool:
        ok = True
        norad = self.query_one("#info-norad", Input)
        if not norad.value.strip():
            self._flash_input(norad)
            ok = False
        return ok

    def _validate_ephemeris(self) -> bool:
        return True  # MJD can be blank (use current time)

    # ── Run dispatch ─────────────────────────────────────────────────────────

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state in (
            WorkerState.SUCCESS,
            WorkerState.ERROR,
            WorkerState.CANCELLED,
        ):
            self._set_worker_running(False)

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
        elif self._active_tab == "info":
            if not self._validate_info():
                return
            self._run_info()
        elif self._active_tab == "ephemeris":
            if not self._validate_ephemeris():
                return
            self._run_ephemeris()
        elif self._active_tab == "backend":
            self._run_backend()

    # ── Passes mode ──────────────────────────────────────────────────────────

    def _run_passes(self) -> None:
        norad_str = self.query_one("#passes-norad", Input).value.strip()
        city_str = self.query_one("#passes-city", Input).value.strip()
        hours_str = self.query_one("#passes-hours", Input).value.strip()
        area_str = self.query_one("#passes-area", Input).value.strip()
        mass_str = self.query_one("#passes-mass", Input).value.strip()
        cd_str = self.query_one("#passes-cd", Input).value.strip()

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
        try:
            area = float(area_str)
            mass = float(mass_str)
            cd = float(cd_str)
        except ValueError:
            self._show_error("Invalid drag parameter (area, mass, or cd)")
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
                        f"Invalid lat,lon format: {city_str}."
                        " Use 'lat,lon' or a city name."
                    )
                    return
            else:
                self._show_error(
                    f"Invalid format: {city_str}." " Use 'lat,lon' or a city name."
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
        self._set_worker_running(True)
        self._show_loading("Fetching TLE and propagating...")
        self.run_passes_worker(norad_id, lat, lon, 0.0, hours, area, mass, cd)

    @work(thread=True, exclusive=True)
    def run_passes_worker(
        self,
        norad_id: int,
        lat: float,
        lon: float,
        alt: float,
        hours: float,
        area: float,
        mass: float,
        cd: float,
    ) -> None:
        from engine.geo.analysis import report_passes

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        result = report_passes(
            norad_id,
            lat,
            lon,
            alt,
            now,
            hours,
            sat_area=area,
            sat_mass=mass,
            sat_cd=cd,
        )
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
        self.query_one("#text-result", Static).display = False
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
        self._set_status(f"[dim]Found {len(passes)} passes[/dim]")

    # ── Propagate mode ───────────────────────────────────────────────────────

    def _run_propagate(self) -> None:
        pid_str = self.query_one("#prop-norad", Input).value.strip()
        state_str = self.query_one("#prop-state", Input).value.strip()
        dt_str = self.query_one("#prop-dt", Input).value.strip()
        steps_str = self.query_one("#prop-steps", Input).value.strip()
        area_str = self.query_one("#prop-area", Input).value.strip()
        mass_str = self.query_one("#prop-mass", Input).value.strip()
        cd_str = self.query_one("#prop-cd", Input).value.strip()
        cr_str = self.query_one("#prop-cr", Input).value.strip()
        mjd0_str = self.query_one("#prop-mjd0", Input).value.strip()

        if state_str:
            state = _parse_state(state_str)
            if state is None:
                self._show_error(
                    "Invalid state vector. Expected 6 comma-separated"
                    " values: x,y,z,vx,vy,vz"
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
            area = float(area_str) if area_str else 0.0
            mass = float(mass_str) if mass_str else 1.0
            cd = float(cd_str) if cd_str else 2.2
            cr = float(cr_str) if cr_str else 1.5
            mjd0 = float(mjd0_str) if mjd0_str else 0.0
        except ValueError:
            self._show_error("Invalid numeric parameter")
            return

        with_drag = area > 0
        self._propagate_initial = list(state)
        self._export_params.update({"dt": dt, "steps": steps, "with_drag": with_drag})
        self._set_worker_running(True)
        self._show_loading("Propagating...")
        self.run_propagate_worker(
            list(state), dt, steps, area, mass, cd, cr, with_drag, mjd0
        )

    @work(thread=True, exclusive=True)
    def run_propagate_worker(
        self,
        state: list,
        dt: float,
        steps: int,
        area: float,
        mass: float,
        cd: float,
        cr: float,
        with_drag: bool,
        mjd0: float,
    ) -> None:
        total = steps * dt
        result = propagate_steps(
            state,
            total,
            dt,
            area=area,
            mass=mass,
            cd=cd,
            cr=cr,
            with_drag=with_drag,
            mjd0=mjd0,
        )
        self.call_from_thread(
            self._show_propagate_result,
            state,
            result,
            steps,
            dt,
            with_drag,
        )

    def _show_propagate_result(
        self,
        initial: list,
        final: list,
        steps: int,
        dt: float,
        with_drag: bool,
    ) -> None:
        self._propagate_initial = initial
        self._propagate_final = final
        self._propagate_steps = steps
        self._propagate_dt = dt

        table = self.query_one("#results-table", DataTable)
        table.display = False
        text_result = self.query_one("#text-result", Static)
        text_result.display = True
        self.query_one("#detail-strip", Static).update("")

        alt0 = _altitude(initial)
        alt1 = _altitude(final)
        spd0 = _speed(initial)
        spd1 = _speed(final)
        drag_label = "with drag" if with_drag else "no drag"

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
            f"  steps={steps}  dt={dt:.1f}s"
            f"  total={steps * dt / 3600:.2f}h  ({drag_label})",
        ]
        text_result.update("\n".join(lines))
        self._set_status(f"[dim]Propagated {steps} steps ({drag_label})[/dim]")

    # ── Conjunction mode ─────────────────────────────────────────────────────

    def _run_conjunction(self) -> None:
        primary = self.query_one("#conj-primary", Input).value.strip()
        secondary = self.query_one("#conj-secondary", Input).value.strip()
        la_str = self.query_one("#conj-lookahead", Input).value.strip()
        step_str = self.query_one("#conj-step", Input).value.strip()
        mjd0_str = self.query_one("#conj-mjd0", Input).value.strip()

        try:
            lookahead = float(la_str)
            step_s = float(step_str) if step_str else 60.0
            mjd0 = float(mjd0_str) if mjd0_str else 0.0
        except ValueError:
            self._show_error("Invalid numeric parameter")
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
            "step_s": step_s,
            "mjd0": mjd0,
        }
        self._set_worker_running(True)
        self._show_loading(f"Screening {len(sat_states)}×{len(deb_states)} pairs...")
        self.run_conjunction_worker(
            sat_states, deb_states, lookahead, step_s, mjd0, sat_ids, deb_ids
        )

    @work(thread=True, exclusive=True)
    def run_conjunction_worker(
        self,
        sat_states: list,
        deb_states: list,
        lookahead: float,
        step_s: float,
        mjd0: float,
        sat_ids: list,
        deb_ids: list,
    ) -> None:
        warnings = detect_conjunctions(
            sat_states,
            deb_states,
            lookahead=lookahead,
            step_s=step_s,
            mjd0=mjd0,
        )
        self.call_from_thread(self._show_conjunction_result, warnings, sat_ids, deb_ids)

    def _show_conjunction_result(
        self, warnings: list, sat_ids: list, deb_ids: list
    ) -> None:
        self._conjunction_data = warnings
        table = self.query_one("#results-table", DataTable)
        table.display = True
        self.query_one("#text-result", Static).display = False
        table.clear(columns=True)
        self._set_conjunction_columns(table)

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

        counts = {"CRITICAL": 0, "WARNING": 0, "ADVISORY": 0, "NONE": 0}
        for w in warnings:
            sev = w.severity.value
            counts[sev] = counts.get(sev, 0) + 1
        summary_parts = []
        for sev in ("CRITICAL", "WARNING", "ADVISORY", "NONE"):
            c = counts.get(sev, 0)
            if c > 0:
                summary_parts.append(f"{sev}: {c}")
        summary = "  │  ".join(summary_parts) if summary_parts else "No events"
        self._set_status(f"[dim]{summary}[/dim]")

    # ── Info mode ────────────────────────────────────────────────────────────

    def _run_info(self) -> None:
        norad_str = self.query_one("#info-norad", Input).value.strip()
        try:
            norad_id = int(norad_str)
        except ValueError:
            self._show_error(f"Invalid NORAD ID: {norad_str}")
            return

        self._export_params = {"norad_id": norad_id}
        self._set_worker_running(True)
        self._show_loading("Fetching satellite data...")
        self.run_info_worker(norad_id)

    @work(thread=True, exclusive=True)
    def run_info_worker(self, norad_id: int) -> None:
        import numpy as np
        from engine.geo.frames import (
            teme_to_eci,
            eci_to_ecef,
            ecef_to_geodetic,
        )
        from engine.constants import MU
        from sgp4.api import jday

        tle_or_err = _tle_get_satrec(norad_id)
        if isinstance(tle_or_err, str):
            self.call_from_thread(self._show_error, tle_or_err)
            return
        tle, satrec = tle_or_err

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

        epoch_str = (
            tle["epoch"].strftime("%Y-%m-%d %H:%M:%S UTC")
            if tle.get("epoch")
            else "Unknown"
        )
        sat_name = tle.get("satellite_name", "Unknown")

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
            self.call_from_thread(
                self._show_error, f"SGP4 error (code {err}) for NORAD ID {norad_id}"
            )
            return

        r_eci, v_eci = teme_to_eci(np.array(r_teme), np.array(v_teme), now)
        altitude = float(np.linalg.norm(r_eci)) - RE
        speed = float(np.linalg.norm(v_eci))

        r_ecef = eci_to_ecef(r_eci, now)
        lat_rad, lon_rad, _ = ecef_to_geodetic(r_ecef)
        lat_deg = float(np.degrees(lat_rad))
        lon_deg = float(np.degrees(lon_rad))

        self.call_from_thread(
            self._show_info_result,
            norad_id,
            sat_name,
            epoch_str,
            inclination,
            raan,
            eccentricity,
            arg_perigee,
            mean_anomaly,
            period_min,
            period_sec,
            a,
            perigee_alt,
            apogee_alt,
            list(r_eci),
            list(v_eci),
            altitude,
            speed,
            lat_deg,
            lon_deg,
            now.strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _show_info_result(  # noqa: C901
        self,
        norad_id: int,
        sat_name: str,
        epoch_str: str,
        inclination: float,
        raan: float,
        eccentricity: float,
        arg_perigee: float,
        mean_anomaly: float,
        period_min: float,
        period_sec: float,
        semi_major_axis: float,
        perigee_alt: float,
        apogee_alt: float,
        r_eci: list,
        v_eci: list,
        altitude: float,
        speed: float,
        lat_deg: float,
        lon_deg: float,
        now_str: str,
    ) -> None:
        table = self.query_one("#results-table", DataTable)
        table.display = False
        text_result = self.query_one("#text-result", Static)
        text_result.display = True
        self.query_one("#detail-strip", Static).update("")

        lon_dir = "E" if lon_deg >= 0 else "W"
        lat_dir = "N" if lat_deg >= 0 else "S"

        lines = [
            f"  Satellite:    {sat_name} ({norad_id})",
            f"  TLE Epoch:    {epoch_str}",
            "",
            f"  Inclination:     {inclination:.4f}°",
            f"  RAAN:            {raan:.4f}°",
            f"  Eccentricity:    {eccentricity:.6f}",
            f"  Arg. of Perigee: {arg_perigee:.4f}°",
            f"  Mean Anomaly:    {mean_anomaly:.4f}°",
            f"  Period:          {period_min:.2f} min  ({period_sec:.0f} s)",
            f"  Semi-major Axis: {semi_major_axis:.3f} km",
            f"  Perigee Alt.:    {perigee_alt:.1f} km",
            f"  Apogee Alt.:     {apogee_alt:.1f} km",
            "",
            f"  Current State (as of {now_str} UTC):",
            f"    Position: [{r_eci[0]:.3f}, {r_eci[1]:.3f}, {r_eci[2]:.3f}] km",
            f"    Velocity: [{v_eci[0]:.6f}, {v_eci[1]:.6f}, {v_eci[2]:.6f}] km/s",
            f"    Altitude: {altitude:.1f} km",
            f"    Speed:    {speed:.4f} km/s",
            f"    Ground:   {abs(lat_deg):.4f}°{lat_dir}, {abs(lon_deg):.4f}°{lon_dir}",
        ]
        text_result.update("\n".join(lines))
        self._set_status(f"[dim]Satellite {norad_id} loaded[/dim]")

    # ── Ephemeris mode ───────────────────────────────────────────────────────

    def _run_ephemeris(self) -> None:
        mjd_str = self.query_one("#eph-mjd", Input).value.strip()
        if mjd_str:
            try:
                mjd = float(mjd_str)
            except ValueError:
                self._show_error(f"Invalid MJD: {mjd_str}")
                return
        else:
            from engine.geo.frames import julian_date

            now = datetime.now(timezone.utc)
            mjd = julian_date(now) - 2400000.5

        self._export_params = {"mjd": mjd}
        self._set_worker_running(True)
        self._show_loading("Computing ephemeris...")
        self.run_ephemeris_worker(mjd)

    @work(thread=True, exclusive=True)
    def run_ephemeris_worker(self, mjd: float) -> None:
        sx, sy, sz = sun_position_eci(mjd)
        mx, my, mz = moon_position_eci(mjd)
        r_sun = math.sqrt(sx * sx + sy * sy + sz * sz)
        r_moon = math.sqrt(mx * mx + my * my + mz * mz)
        self.call_from_thread(
            self._show_ephemeris_result, mjd, sx, sy, sz, r_sun, mx, my, mz, r_moon
        )

    def _show_ephemeris_result(
        self,
        mjd: float,
        sx: float,
        sy: float,
        sz: float,
        r_sun: float,
        mx: float,
        my: float,
        mz: float,
        r_moon: float,
    ) -> None:
        table = self.query_one("#results-table", DataTable)
        table.display = False
        text_result = self.query_one("#text-result", Static)
        text_result.display = True
        self.query_one("#detail-strip", Static).update("")

        lines = [
            f"  Ephemeris at MJD {mjd}",
            "",
            f"  Sun:   [{sx:.3f}, {sy:.3f}, {sz:.3f}]  distance: {r_sun:.3f} km",
            f"  Moon:  [{mx:.3f}, {my:.3f}, {mz:.3f}]  distance: {r_moon:.3f} km",
        ]
        text_result.update("\n".join(lines))
        self._set_status(f"[dim]Ephemeris at MJD {mjd}[/dim]")

    # ── Backend mode ─────────────────────────────────────────────────────────

    def _run_backend(self) -> None:
        self._set_worker_running(True)
        self._show_loading("Querying backends...")
        self.run_backend_worker()

    @work(thread=True, exclusive=True)
    def run_backend_worker(self) -> None:
        info = backend_info()
        gpu_name = "N/A"
        if info.get("cuda"):
            try:
                import physics_engine as _pe

                gpu_name = getattr(_pe, "cuda_device_name", lambda: "NVIDIA GPU")()
            except Exception:
                gpu_name = "NVIDIA GPU (unknown model)"
        self.call_from_thread(self._show_backend_result, info, gpu_name)

    def _show_backend_result(self, info: dict, gpu_name: str) -> None:
        table = self.query_one("#results-table", DataTable)
        table.display = False
        text_result = self.query_one("#text-result", Static)
        text_result.display = True
        self.query_one("#detail-strip", Static).update("")

        lines = [
            f"  Active backend:    {info.get('active', 'N/A')}",
            f"  Description:       {info.get('description', 'N/A')}",
            "",
            "  Available backends:",
            f"    CUDA:            {'yes' if info.get('cuda') else 'no'}  ({gpu_name})",
            f"    C++/OpenMP:      {'yes' if info.get('cpp') else 'no'}",
            f"    NumPy batch:     {'yes' if info.get('numpy_batch') else 'no'}",
            f"    Python fallback: {'yes' if info.get('python') else 'no'}",
        ]
        text_result.update("\n".join(lines))
        self._set_status("[dim]Backend info updated[/dim]")

    # ── Shared display helpers ───────────────────────────────────────────────

    def _show_loading(self, message: str) -> None:
        self.query_one("#text-result", Static).display = False
        self.query_one("#detail-strip", Static).update("")
        if self._active_tab in ("propagate", "info", "ephemeris", "backend"):
            table = self.query_one("#results-table", DataTable)
            table.display = False
            text_result = self.query_one("#text-result", Static)
            text_result.display = True
            text_result.update(f"[dim]{message}[/dim]")
            self._set_status(f"[dim]{message}[/dim]")
        else:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            if self._active_tab == "conjunction":
                self._set_conjunction_columns(table)
                table.add_row("[dim]Loading...[/dim]", "", "", "", "", "")
            else:
                self._set_passes_columns(table)
                table.add_row("[dim]Loading...[/dim]", "", "", "", "")
            self._set_status(f"[dim]{message}[/dim]")

    def _show_error(self, message: str) -> None:
        self.query_one("#text-result", Static).display = False
        self.query_one("#detail-strip", Static).update("")
        if self._active_tab in ("propagate", "info", "ephemeris", "backend"):
            table = self.query_one("#results-table", DataTable)
            table.display = False
            text_result = self.query_one("#text-result", Static)
            text_result.display = True
            text_result.update(f"[red]{message}[/red]")
        else:
            table = self.query_one("#results-table", DataTable)
            table.clear(columns=True)
            if self._active_tab == "conjunction":
                self._set_conjunction_columns(table)
                table.add_row("", "", "", "", f"[red]{message}[/red]", "")
            else:
                self._set_passes_columns(table)
                table.add_row(f"[red]{message}[/red]", "", "", "", "")
        self._set_status(f"[red]{message}[/red]")

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
            self._set_status("[red]Nothing to export[/red]")
            return

        try:
            filename = filename.replace(" ", "_").replace("/", "_")
            with open(filename, "w") as f:
                json.dump(data, f, indent=2)
            self._set_status(f"[dim]Exported to {filename}[/dim]")
        except Exception as e:
            self._set_status(f"[red]Export failed: {e}[/red]")

    # ── Refresh ──────────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self._clear_results()
        table = self.query_one("#results-table", DataTable)
        if self._active_tab == "conjunction":
            self._set_conjunction_columns(table)
        else:
            self._set_passes_columns(table)
        self._show_empty_state()
        self._set_status("[dim]Refreshed[/dim]")
        self.set_timer(1.5, lambda: self._set_status("Ready"))
