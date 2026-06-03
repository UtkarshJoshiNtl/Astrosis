# Astrosis — orbital mechanics calculator

CLI + TUI orbital mechanics calculator — J2/J3/J4 propagation, conjunction screening,
pass prediction, and ephemeris. Auto-selects CUDA → C++/OpenMP → NumPy → Python backend.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

```console
$ astrosis passes --city "New York" --id 25544
Found 6 passes for ISS (ZARYA) over New York in the next 24.0h
┌──────────┬────────────────┬──────────┬──────────┬─────────┐
│ Time UTC │ Max Elevation  │ Azimuth  │ Duration │ Visible │
├──────────┼────────────────┼──────────┼──────────┼─────────┤
│ 14:52:30 │         54.3°  │  142.5°  │  6m 43s  │   Yes   │
│ 16:28:45 │         21.7°  │  226.8°  │  4m 12s  │   No    │
└──────────┴────────────────┴──────────┴──────────┴─────────┘
```

## Quick start

```bash
pip install astrosis

# TUI (no args)
astrosis

# CLI (with subcommand)
astrosis passes --city Mumbai --id 25544
astrosis info --id 25544
```

Running `astrosis` with no arguments launches the interactive TUI.
All existing CLI subcommands remain unchanged.

## TUI

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
│   ✓ CUDA  ✓ C++/OpenMP  ✓ NumPy batch  ✓ Python fallback                    │
│ GPU: NVIDIA GPU                                                             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

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

## Docs

| Resource | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | System design, backends, data flow |
| [docs/design.md](docs/design.md) | Design tradeoffs and rationale |
| [docs/performance.md](docs/performance.md) | Benchmarks, scaling, roofline analysis |
| [docs/api.md](docs/api.md) | Public Python API reference |
| [docs/validation.md](docs/validation.md) | Physics verification methodology |

## License

MIT
