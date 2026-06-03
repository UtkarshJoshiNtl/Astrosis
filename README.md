# Astrosis — orbital mechanics calculator

CLI + TUI orbital mechanics calculator — J2/J3/J4 propagation, conjunction screening,
pass prediction, and ephemeris. Auto-selects CUDA → C++/OpenMP → NumPy → Python backend.

[![CI](https://img.shields.io/github/actions/workflow/status/UtkarshJoshiNtl/Astrosis/ci.yml?branch=main&label=CI&logo=github)](https://github.com/UtkarshJoshiNtl/Astrosis/actions)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20|%20macOS%20|%20windows-lightgrey)](https://pypi.org/project/astrosis/)

![TUI demo](assets/tui-demo.gif)

<details>
<summary><b>Table of Contents</b></summary>

- [Why Astrosis?](#why-astrosis)
- [Quick start](#quick-start)
- [Features](#features)
- [Architecture](#architecture)
- [TUI reference](#tui-reference)
- [CLI reference](#cli-reference)
- [Performance](#performance)
- [Install from source](#install-from-source)
- [Backend auto-selection](#backend-auto-selection)
- [Docs](#docs)
- [License](#license)

</details>

## Why Astrosis?

- **GPU auto-acceleration.** CUDA → C++/OpenMP → NumPy → Python fallback. No config required. Batch propagate 5000 satellites 2.4 h in **75 ms** — 500× faster than Python.
- **Conjunction screening ready.** Built-in pairwise collision detection with Brent TCA refinement and Chan probability. 400×400 pairs in **125 ms** (CUDA).
- **TUI + CLI duality.** Rich interactive TUI (6 modes, collapsible sections, export) plus full CLI for scripting. Same Python API under both.

## Quick start

```bash
pip install astrosis

# TUI (no args)
astrosis

# CLI (with subcommand)
astrosis passes --city Mumbai --id 25544
astrosis info --id 25544
```

## Features

| Category | Capabilities |
|----------|-------------|
| **Propagation** | RK4 with J2/J3/J4, atmospheric drag (US Standard 1976), SRP, lunisolar third-body |
| **Auto-backend** | CUDA GPU → C++ OpenMP → NumPy batch → Python fallback, transparent fallback |
| **Conjunction** | KDTree broad-phase, pairwise distance scan, Brent TCA refinement, Chan collision probability |
| **Pass prediction** | SGP4 → RK4 seamless handoff, elevation/visibility filtering, ~85 cities built-in |
| **Ephemeris** | Sun/Moon ECI positions via VSOP87/ELP-2000, eclipse state (umbra/penumbra) |
| **TUI** | 6 modes, help overlay, collapsible advanced sections, JSON export, persistence, autocomplete cities |
| **Coordinate frames** | ECI ⇄ ECEF, TEME → ECI, geodetic, topocentric (az/el/range), GMST + equation of equinoxes |

## Architecture

```mermaid
graph TB
    subgraph UI["User Interface"]
        direction LR
        CLI["main.py / CLI"]
        TUI["engine/tui.py<br/>Textual 8.x"]
        API["engine.*<br/>Python API"]
    end

    subgraph CORE["Physics Core"]
        direction TB
        PROP["Propagator<br/>RK4 · J2–J4 · Drag · SRP<br/>Lunisolar"]
        CONJ["Conjunction Detector<br/>KDTree · Brent TCA<br/>Chan Pc"]
        PASS["Pass Predictor<br/>SGP4→RK4 · AER<br/>Eclipse check"]
        EPHEM["Ephemeris<br/>Sun VSOP87 · Moon ELP-2000"]
        FRAMES["Frame Transforms<br/>ECI ↔ ECEF ↔ Geodetic<br/>TEME→ECI · Topocentric"]
    end

    subgraph BACKEND["Backend Layer<br/>(auto-selected)"]
        CUDA["CUDA GPU<br/>SoA kernels"]
        CPP["C++ / OpenMP<br/>pybind11"]
        NUMPY["NumPy batch<br/>Vectorised"]
        PYTHON["Python fallback"]
    end

    subgraph DATA["Data Sources"]
        TLE["TLE Ingestor<br/>CelesTrak / Space-Track"]
        CITIES["City Database<br/>~85 cities"]
    end

    CLI --> CORE
    TUI --> API
    API --> CORE
    PROP --> BACKEND
    CONJ --> BACKEND
    PASS --> FRAMES
    PASS --> PROP
    PASS --> EPHEM
    CONJ --> PROP
    TLE --> PROP
    CITIES --> PASS
```

The router in `engine/core/accelerator.py` probes `cuda_available()`, C++ module presence,
and falls back through the layers — all transparent to the caller.

## TUI reference

Six modes (switch with `Alt+1`–`Alt+6`):

| Mode | What it does |
|------|--------------|
| **passes** | Predict satellite passes for a city or lat/lon |
| **propagate** | Propagate a NORAD ID or state vector forward |
| **conjunction** | Load CSVs and screen pairs for close approaches |
| **info** | Orbital elements, current ECI state, ground track |
| **ephemeris** | Sun/Moon ECI positions and distances |
| **backend** | Active compute backend and GPU info |

Keybindings:

| Key | Action |
|-----|--------|
| `Alt+1`–`Alt+6` | Switch mode |
| `Enter` | Run current mode |
| `Escape` | Cancel running operation |
| `Ctrl+E` | Export results to JSON |
| `F5` | Refresh / clear results |
| `F1` / `?` | Show help overlay |
| `↑↓` | Select result row (detail strip) |
| `Ctrl+Q` | Quit |

Drag/SRP parameters and conjunction advanced options are hidden behind
clickable `[+]` section headers. Input values persist across sessions
via `~/.cache/astrosis/tui_state.json`.

## CLI reference

| Command | What it does |
|---------|--------------|
| `astrosis` | Launch interactive TUI |
| `astrosis passes --city <name> --id <norad>` | Predict satellite passes |
| `astrosis info --id <norad>` | Orbital elements and current state |
| `astrosis propagate <state or id> --dt 60 --steps 1440` | Propagate forward |
| `astrosis conjunction --primary a.csv --secondary b.csv` | Conjunction screening |
| `astrosis batch <file.csv> --steps 100` | Batch propagate from CSV |
| `astrosis backend` | Show active compute backend |
| `astrosis fetch --id <norad>` | Fetch and cache TLE data |
| `astrosis ephemeris --mjd 60000` | Sun/moon positions |

## Performance

| Operation | Python | C++ | CUDA |
|-----------|-------:|----:|-----:|
| Single sat (50k steps) | 391 ms | **21 ms (19×)** | N/A |
| Batch 1k sats × 864 steps | 7074 ms | **13 ms (566×)** | **245 ms (29×)** |
| Batch 5k sats × 864 steps | 36854 ms | **55 ms (676×)** | **291 ms (127×)** |
| Conjunction 200×200 1h | 6262 ms | 498 ms (13×) | **45 ms (139×)** |
| Conjunction 400×400 2h | 26677 ms | 3856 ms (7×) | **125 ms (214×)** |

C++ dominates < 500 satellites (no PCIe overhead). CUDA dominates > 500 with
up to 66,483 sats/s throughput. See [docs/performance.md](docs/performance.md)
for full crossover analysis, extended modes, and roofline.

## Install from source

```bash
git clone https://github.com/UtkarshJoshiNtl/Astrosis.git
cd Astrosis
pip install -r requirements.txt
pip install -e .
```

Optional: build C++/CUDA backends for faster computation:
```bash
./build-backends.sh   # auto-detects CUDA
python main.py backend  # verify
```

## Backend auto-selection

Astrosis automatically picks the fastest backend for each operation:
CUDA GPU → C++/OpenMP → NumPy batch → pure Python.

```bash
$ astrosis backend
╭─────────────────────────────── Backend Status ───────────────────────────────╮
│ Active backend: CUDA                                                         │
│       ✓ CUDA  ✓ C++/OpenMP  ✓ NumPy batch  ✓ Python fallback                │
│ GPU: NVIDIA GPU                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Docs

| Resource | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | System design, backends, data flow |
| [docs/design.md](docs/design.md) | Design tradeoffs and rationale |
| [docs/performance.md](docs/performance.md) | Benchmarks, scaling, roofline analysis |
| [docs/api.md](docs/api.md) | Public Python API reference |
| [docs/validation.md](docs/validation.md) | Physics verification methodology |
| [docs/configuration.md](docs/configuration.md) | Environment variables and runtime flags |
| [docs/contributing.md](docs/contributing.md) | Dev setup, tests, code style, PR workflow |

## License

MIT
