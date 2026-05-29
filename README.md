# Astrosis — orbital mechanics calculator

Batch propagation and conjunction screening for satellites, from a terminal.

```
python main.py passes --id 25544 --lat 40.7 --lon -74.0
```

Prints ISS pass times for New York over the next 24 hours. No server, no browser, no UI.

## Why

Existing tools are either:
- **Heavy** — STK, GMAT, Systems Tool Kit. Powerful but overkill for "when does the ISS fly over?"
- **Inaccurate** — phone apps and websites use SGP4, which drifts kilometers per day
- **Browser-only** — no CLI, no pipeable output, no scripting

Astrosis solves one thing well: give it a NORAD ID, a location, and a time window, and it tells you every pass with max elevation, azimuth, and duration. Optionally with conjunction warnings.

The physics is real — J2/J3/J4 perturbations, RK4 integration, 1e-7 energy conservation over 24 hours. The GPU backend runs 150× faster than pure Python for constellation-scale work.

## Quick Start

```bash
git clone https://github.com/your-org/astrosis.git && cd astrosis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Predict ISS passes over New York
python main.py passes --id 25544 --lat 40.7 --lon -74.0
```

## Installation

**Dependencies:** Python 3.10+, numpy, scipy, httpx, sgp4, matplotlib (optional, for validation plots).

```bash
pip install -r requirements.txt
```

**C++/CUDA backends** (optional, ~500× speedup for batch work):

```bash
./build-backends.sh
```

Auto-detects CUDA 12.x + CMake 3.15+. Falls back to C++/OpenMP or pure Python.

## Usage

### Predict satellite passes

```bash
# ISS over New York, next 48 hours
python main.py passes --id 25544 --lat 40.7 --lon -74.0 --hours 48

# Save to file
python main.py passes --id 25544 --lat 40.7 --lon -74.0 --output iss_passes.json
```

### Fetch TLE data

```bash
python main.py fetch --id 25544          # Fetch specific satellite
python main.py fetch                      # Fetch entire active catalog
python main.py fetch --id 25544 --force   # Force refresh cache
```

### Force CPU backend

```bash
python main.py --mock-gpu passes --id 25544 --lat 40.7 --lon -74.0
```

### Use as a Python library

```python
from engine.core.accelerator import propagate, propagate_batch, backend_info
from engine.core.conjunction import ConjunctionDetector, Severity
from engine.geo.analysis import report_passes
from engine.constants import MU, RE, J2

# Propagate a state vector
state = [RE + 400, 0, 0, 0, 7.66, 0]  # [x, y, z, vx, vy, vz], km & km/s
new_state = propagate(state, dt_seconds=60.0)

# Check backend
info = backend_info()
print(info["active"])  # "cuda", "cpp", or "python"

# Batch propagate many satellites
states = propagate_batch([state, state2, state3], dt_seconds=60, steps=100)

# Detect conjunctions
detector = ConjunctionDetector()
warnings = detector.detect(sat_states=[...], debris_states=[...],
                           lookahead_s=3600, step_s=60)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `CELESTRAK_API_URL` | `https://celestrak.org/NORAD/elements/gp.php` | TLE source |
| `TLE_REFRESH_INTERVAL_HOURS` | `6` | Cache refresh period |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `SPACETRACK_USER` | — | Space-Track.org username |
| `SPACETRACK_PASS` | — | Space-Track.org password |

Copy `.env.example` → `.env` to set these.

## Key Design

| Decision | Rationale |
|----------|-----------|
| Fixed-step RK4 | GPU warp uniformity; no adaptive stepping |
| J2/J3/J4 only | Captures >99.97% of gravity perturbation at 3 arithmetic ops |
| FP64 everywhere | FP32 insufficient for 24h integration (state spans 13 orders of magnitude) |
| Auto-backend | CUDA → C++ → NumPy → Python, selected by problem size |
| 6-element state | `[x, y, z, vx, vy, vz]`, ECI frame, km and km/s |

Full rationale: [docs/design.md](docs/design.md)

## Performance

| Workload | Python | C++ | CUDA |
|----------|--------|-----|------|
| 1 sat, 50k steps | 395 ms | 22 ms (18×) | — |
| 1k sats, 24h @ dt=10s | 7,034 ms | 14 ms (507×) | 47 ms (150×) |
| 400×400 conjunction | 46.7 s | 5.2 s (9×) | 564 ms (83×) |

**Hardware:** RTX 2050 (16 SMs), AMD Ryzen 5, CUDA 12.9. Full methodology: [docs/performance.md](docs/performance.md)

## Documentation

| Resource | Purpose |
|----------|---------|
| [docs/architecture.md](docs/architecture.md) | System design, backends, data flow |
| [docs/design.md](docs/design.md) | Design tradeoffs and rationale |
| [docs/performance.md](docs/performance.md) | Benchmarks, scaling, roofline analysis |
| [docs/profiling.md](docs/profiling.md) | CUDA profiling guide |
| [docs/validation.md](docs/validation.md) | Physics verification methodology |
| [docs/contributing.md](docs/contributing.md) | Development setup and contribution guide |

## Tests

```bash
pytest tests/test_correctness.py -v        # Unit tests (physics invariants)
python validation/validate_physics.py --test energy --hours 24  # Physics validation
python benchmarks/benchmark.py --quick     # Performance regression
```

## License

MIT
