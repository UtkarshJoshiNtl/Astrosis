# Astrosis — orbital mechanics calculator

Astrosis is a command-line orbital mechanics calculator — J2/J3/J4 propagation,
conjunction screening, and pass prediction — with an auto-selecting CUDA/C++/Python backend.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/UtkarshJoshiNtl/Astrosis/actions/workflows/ci.yml/badge.svg)](https://github.com/UtkarshJoshiNtl/Astrosis/actions/workflows/ci.yml)

```console
$ astrosis info --id 25544
╭───────────────────────────── Satellite Identity ─────────────────────────────╮
│ Name: ISS (ZARYA)                                                            │
│ NORAD ID: 25544                                                              │
│ TLE Epoch: 2026-05-29 11:39:12 UTC                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭────────────────────────────── Orbital Elements ──────────────────────────────╮
│   Parameter                      Value                                       │
│   Inclination                 51.6334°                                       │
│   Eccentricity                0.000732                                       │
│   Period             92.94 min (5576 s)                                      │
│   Perigee Alt.              413.3 km                                         │
│   Apogee Alt.               423.3 km                                         │
╰──────────────────────────────────────────────────────────────────────────────╯

$ astrosis passes --city "New York" --id 25544
Found 6 passes for ISS (ZARYA) over New York in the next 24.0h
┌──────────┬────────────────┬──────────┬──────────┬─────────┐
│ Time UTC │ Max Elevation  │ Azimuth  │ Duration │ Visible │
├──────────┼────────────────┼──────────┼──────────┼─────────┤
│ 14:52:30 │         54.3°  │  142.5°  │  6m 43s  │   Yes   │
│ 16:28:45 │         21.7°  │  226.8°  │  4m 12s  │   No    │
│ ...      │           ...  │     ...  │     ...  │   ...   │
└──────────┴────────────────┴──────────┴──────────┴─────────┘

$ astrosis backend
╭─────────────────────────────── Backend Status ───────────────────────────────╮
│ Active backend: CUDA                                                         │
│   ✓ CUDA                                                                     │
│   ✓ C++ / OpenMP                                                             │
│   ✓ NumPy batch                                                              │
│   ✓ Python fallback                                                          │
│                                                                              │
│ CUDA GPU (NVIDIA)                                                            │
│ GPU: NVIDIA GPU                                                              │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Install

```bash
pip install astrosis
astrosis passes --city "Mumbai" --id 25544
```

## What it does

| Command | What it does |
|---------|--------------|
| `passes` | Predict satellite passes for any city or lat/lon |
| `propagate` | Propagate an ECI state or NORAD ID forward in time |
| `conjunction` | Screen satellite vs debris pairs for close approaches |
| `batch` | Propagate thousands of satellites from a CSV |

## Performance

| Workload | Python | C++ | CUDA |
|----------|--------|-----|------|
| 1 sat, 50k steps | 395 ms | 22 ms (18×) | — |
| 1k sats, 24h @ dt=10s | 7,034 ms | 14 ms (507×) | 47 ms (150×) |
| 400×400 conjunction | 46.7 s | 5.2 s (9×) | 564 ms (83×) |

**Hardware:** RTX 2050 (16 SMs), AMD Ryzen 5, CUDA 12.9. Full methodology: [docs/performance.md](docs/performance.md)

## Backend

Astrosis automatically selects the fastest available backend for each operation.
CUDA GPU is preferred for large batch work (>1000 satellites), falling back to
C++/OpenMP for smaller sets or environments without a GPU. Further fallbacks
use NumPy vectorised propagation or a pure Python RK4 loop with no compiled
dependencies.

```console
$ astrosis backend
╭─────────────────────────────── Backend Status ───────────────────────────────╮
│ Active backend: CUDA                                                         │
│   ✓ CUDA                                                                     │
│   ✓ C++ / OpenMP                                                             │
│   ✓ NumPy batch                                                              │
│   ✓ Python fallback                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## Library usage

```python
from engine import propagate, propagate_batch, ConjunctionDetector

# Propagate a single state (6-element ECI: x, y, z, vx, vy, vz)
state = [RE + 400, 0, 0, 0, 7.66, 0]
new_state = propagate(state, dt_seconds=60.0)

# Batch propagate many satellites
states = propagate_batch([state, state2], dt_seconds=60, steps=100)

# Screen pairs for conjunction warnings
warnings = ConjunctionDetector().detect(sat_states=[...], debris_states=[...],
                                        lookahead_s=3600, step_s=60)
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
