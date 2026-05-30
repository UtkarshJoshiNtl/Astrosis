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

```
┌─ ASTROSIS ──────────────── CUDA · RTX 2050 ─── 2026-05-30 13:42 UTC ─────┐
│                                                                              │
│  NORAD ID    TIME          EL      AZ     DUR    VIS                        │
│  ─────────   ─────────────────────────────────────────                      │
│  > 25544     14:12:33   72.4°   312°    6m41s  ●                            │
│              15:48:10   34.1°   248°    4m12s  ●                            │
│  CITY        17:24:55   12.3°   195°    2m08s  ○                            │
│  > Mumbai                                                                   │
│                                                                              │
│  HOURS      tab·switch  ↑↓·select  e·export  r·refresh  q·quit             │
│  > 24                                                                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

Three modes (switch with Tab):

| Mode | What it does |
|------|--------------|
| **passes** | Predict satellite passes for a city or lat/lon |
| **propagate** | Propagate a NORAD ID or state vector forward |
| **conjunction** | Load CSVs and screen pairs for close approaches |

Keys: `Tab` switch mode, `↑↓` select row, `Enter`/Run button execute, `e` export JSON,
`r` clear results, `q` quit.

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

## Docs

| Resource | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | System design, backends, data flow |
| [docs/design.md](docs/design.md) | Design tradeoffs and rationale |
| [docs/performance.md](docs/performance.md) | Benchmarks, scaling, roofline analysis |
| [docs/profiling.md](docs/profiling.md) | CUDA profiling guide |
| [docs/validation.md](docs/validation.md) | Physics verification methodology |

## License

MIT
