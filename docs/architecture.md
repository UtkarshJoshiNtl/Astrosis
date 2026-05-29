# Architecture & Design

## System Overview

Astrosis uses a **modular, multi-backend architecture** that automatically selects the fastest available hardware for your workload.

```
                    User Interfaces
                ┌──────────┬──────────────┐
                │  CLI     │  Python API  │
                │ main.py  │  engine.*    │
                └──────────┴──────────────┘
                              │
                ┌─────────────┴─────────────┐
                │     Physics Core          │
                │  (engine/core/)           │
                │  propagator, conjunction, │
                │  ephemeris, accelerator   │
                └─────────────┬─────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        │                     │                      │
  ┌─────┴──────────┐  ┌───────┴─────────┐  ┌────────┴──────────┐
  │  Coordinate    │  │  I/O & Catalog  │  │  Backend Layer   │
  │  Transforms    │  │  TLE, caching   │  │  (auto-detected) │
  │  (geo/)        │  │  (io/)          │  │                   │
  └────────────────┘  └─────────────────┘  │  CUDA → C++       │
                                           │  → NumPy → Python │
                                           └────────────────────┘
```

## Backend Selection Strategy

Astrosis automatically chooses the best backend based on hardware availability and problem size:

### Decision Tree

```
┌─ CUDA available?
│  ├─ Yes ──┬─ Problem size > 500 satellites?
│  │        ├─ Yes → Use CUDA (82× speedup)
│  │        └─ No  → Use C++ (lower latency)
│  │
│  └─ No ──┬─ C++ compiled?
│           ├─ Yes → Use C++/OpenMP (18× speedup)
│           │
│           └─ No ──┬─ NumPy available?
│                    ├─ Yes → Use NumPy (3–5× speedup)
│                    └─ No  → Fall back to pure Python
```

### Heuristics & Thresholds

| Factor | Threshold | Decision |
|--------|-----------|----------|
| **Satellites** | < 500 | Prefer C++ (lower launch overhead) |
| **Satellites** | 500–2,000 | CUDA competitive; use available |
| **Satellites** | > 2,000 | Strongly prefer CUDA |
| **Propagation steps** | < 10,000 | CPU typically adequate |
| **Propagation steps** | > 100,000 | CUDA essential for real-time |
| **Integration dt** | > 60 seconds | CPU competitive (fewer steps) |
| **Integration dt** | 1–10 seconds | CUDA advantage grows |

### Manual Backend Override

```python
from engine.core.accelerator import backend_info
info = backend_info()  # Shows active backend, CUDA availability

# Force CPU via environment variable
# ASTROSIS_MOCK_GPU=1 python main.py ...
```

---

## Module Descriptions

### `engine/core/` — Physics Kernels

**Propagator** (`propagator.py`):
- RK4 numerical integration
- Force computation: J2–J4, drag, SRP, third-body
- State vector: [x, y, z, vx, vy, vz]
- Available in: CUDA, C++/OpenMP, NumPy, Python

**Conjunction** (`conjunction.py`):
- Pairwise distance computation (multi-backend: CUDA → C++ → NumPy → Python)
- Pre-propagation optimization: each object propagated once, not once per pair
- SoA layout in GPU memory for coalesced distance scanning
- Time-of-Closest-Approach (TCA) refinement (Brent minimisation)
- Collision probability (Chan approximation)
- Severity thresholds: CRITICAL (< 0.1 km), WARNING (< 1.0 km), ADVISORY (< 5.0 km)

**Accelerator** (`accelerator.py`):
- Auto-backend selection: CUDA → C++/OpenMP → NumPy → Python
- `propagate()`, `propagate_batch()`, `detect_conjunctions()`, `backend_info()`
- Mock GPU via `ASTROSIS_MOCK_GPU=1`

**Ephemeris** (`ephemeris.py`):
- Solar/lunar position (low-precision analytical)
- Julian Date handling
- Epoch conversions

### `engine/geo/` — Coordinate Transformations

**Frames** (`frames.py`):
- ECI ↔ ECEF conversions (with proper pole wandering)
- ECEF → LLA (latitude/longitude/altitude)
- Topocentric coordinates (local horizon system)
- Time system conversions: UTC ↔ TAI ↔ TT

**Analysis** (`analysis.py`):
- `report_passes()` — ground visibility and pass prediction
- Elevation/azimuth/range computation
- Rise/set time predictions

**Visibility** (`visibility.py`):
- Line-of-sight checks
- Coverage area computation

### `engine/io/` — Data I/O

**Data** (`data.py`):
- TLE parsing (Two-Line Element Set format)
- Celestrak TLE fetch + local file caching
- OEM file handling

---

### `cpp/` — High-Performance Backends

**Structure:**

```
cpp/
├── CMakeLists.txt          # Build configuration (find_package CUDAToolkit)
├── physics_constants.h     # J2, GM, R_E, etc.
├── propagator.cpp/.h       # RK4 implementation (pybind11 bindings)
├── conjunction.cpp/.h      # C++ conjunction + Brent minimiser
├── cuda_propagator.cu      # CUDA kernels: k_prop_soa, k_history, run_streamed
├── cuda_conjunction.cu     # CUDA kernels: k_prepropagate, k_scan_pairs
├── cuda_constants.cu       # Single-source __constant__ definitions
├── cuda_physics.cuh        # RAII wrappers (DeviceMem, HostPinnedMem) + accel()
├── cuda_bridge.h           # C++ declarations for CUDA functions
└── build/physics_engine.cpython-*.so  # pybind11 shared module
```

**Build:**

```bash
cd cpp && mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DUSE_CUDA=ON
make -j$(nproc)
```

---

## Data Flow: Batch Propagation

**Example:** Propagate 1,000 satellites for 24 hours

```
┌─ User code
│  propagate_batch(states, dt_seconds=10, steps=8640)
│
├─ accelerator.py
│  Detects: 1,000 satellites → CUDA beneficial
│  Selects backend: CUDA (assuming GPU available)
│
├─ Python ↔ C++ FFI (pybind11)
│  Pack state vectors into GPU memory
│  SoA layout: [x₁..x₁₀₀₀, y₁..y₁₀₀₀, z₁..z₁₀₀₀, ...]
│  (~48 KB for 1,000 6-element state vectors)
│
├─ GPU Memory Setup
│  Device memory allocation: SoA layout [x₀..xₙ₋₁, y₀..yₙ₋₁, ..., vz₀..vzₙ₋₁]
│  Transfer: 48 KB upload (negligible for 1,000 sats)
│
├─ CUDA Kernel Execution (8,640 steps × 10 s)
│  Launch grid: N/256 blocks × 256 threads (1,000 sats → 4 blocks)
│  Single k_prop_soa kernel handles all 4 RK4 stages internally:
│    for step in 0..steps:
│      rk4_step_device(x, y, z, vx, vy, vz)  ← all 4 substages
│  Total kernel launches: 1 (not 4 per step)
│
├─ GPU Memory Transfer (download results)
│  Final state: 48 KB download
│  Overhead: ~14 ms (negligible vs. 47 ms compute)
│
└─ Return to Python
   Final state array: [1,000 × 6]
   Full history: [8,640 timesteps × 1,000 sats × 6 components] (~830 MB)
   Time: 46.9 ± 2.1 ms (measured)
```

**Conjunction screening** uses a 2-phase GPU algorithm to eliminate redundant propagation.

## Data Flow: Conjunction Screening

**Example:** Screen 500 sats × 500 debris for conjunctions over 10 hours

```
┌─ accelerator.detect_conjunctions(sats, debs, lookahead=36000, step_s=60)
│
├─ Backend: CUDA → C++/OpenMP → NumPy → Python
│
├─ CUDA Path (2-phase):
│
│  Phase 1 — Pre-propagation (k_prepropagate)
│  │  Propagate all 500 sats + 500 debs for 600 steps each
│  │  Store trajectory in SoA per timestep:
│  │    [(step0)[X₀..X₄₉₉, Y₀..Y₄₉₉, ..., VZ₀..VZ₄₉₉](step1)[...]]
│  │  Memory: 601 × 500 × 6 × 8 × 2 = 28.8 MB
│  │  Cost: O((ns+nd) × nsteps) = 600K propagations
│  │
│  └─ Phase 2 — Pair Scan (k_scan_pairs)
│     Grid: (500/16, 500/16) blocks × (16,16) threads
│     Each thread: coalesced reads of pre-propagated SoA arrays
│     Cost: O(ns × nd × nsteps) = 150M distance calcs (no RK4)
│
│  Speedup vs naive: ~250× (150M → 600K propagations)
│
├─ C++: Brent refinement on detected candidates
│  Propagates from saved bracket-left state (sat_lo/deb_lo)
│  At most 2× step_s per refinement
│
└─ Return: vector<ConjunctionWarning>
```

For CUDA kernel details: `cpp/cuda_conjunction.cu` (`k_prepropagate`, `k_scan_pairs`).
For C++ refinement: `cpp/conjunction.cpp` (`brent_minimise<F>` — no heap alloc).

---

## Precision & Arithmetic

### Default Precision: FP64 (IEEE 754 Double)

**Rationale:**
- Orbital state spans 13 orders of magnitude (position to velocity)
- FP32 mantissa (24 bits) insufficient for differentiation
- Energy conservation requires FP64 for 24-hour stability

**Force Computation:** FP64 throughout
**Storage:** FP64 (future: compression/streaming for large catalogs)

---

## Extensibility Points

### Adding a New Force Model
1. Implement acceleration function (e.g., `AccelThirdBodyPluto()`)
2. Register in `ComputeAccel()` dispatcher in `propagator.py`
3. Add unit tests in `tests/test_correctness.py`
4. Benchmark impact on throughput

### Adding a New Coordinate System
1. Implement transformation matrices in `engine/geo/frames.py`
2. Update rotation/velocity chain rule
3. Add round-trip conversion tests

### Adding a New Backend
1. Port physics kernels to target architecture (e.g., OpenCL, HIP)
2. Update backend selection heuristics in `engine/core/accelerator.py`
3. Benchmark vs. CUDA baseline via `benchmarks/benchmark.py`

---

## Pre-commit Hooks

`.pre-commit-config.yaml` enforces: black, ruff, clang-format, trailing-whitespace, end-of-file-fixer, check-yaml, check-json.

Install with: `pre-commit install`

## Environment

See `.env.example`:
- `CELESTRAK_API_URL` — TLE source URL
- `TLE_REFRESH_INTERVAL_HOURS` — cache refresh period
- `LOG_LEVEL` — logging verbosity
- `SPACETRACK_USER` / `SPACETRACK_PASS` — Space-Track.org auth (optional)

---

## Testing & Validation Strategy

- **Unit tests:** `tests/test_correctness.py` (16 tests: energy, RK4 order, conjunction, batch propagation)
- **Physics validation:** `validation/validate_physics.py` (4 tests: energy 24h, SGP4 comparison, RAAN precession, RK4 convergence order)
- **SGP4 research:** `validation/sgp4_vs_rk4.py` (72-hour divergence analysis)
- **Performance regression:** `benchmarks/benchmark.py` (CSV output, strong/weak scaling, `--plot` flag)
- **Roofline analysis:** `validation/cuda_roofline.py` (RTX 2050 hardcoded limits, optional ncu metric parsing)
- **Reproducibility:** Deterministic for all operations

---

## API Stability

**Current Status: EXPERIMENTAL**

- **Core API** (propagation, conjunction): Stable
- **Coordinate transforms**: Stable
- **CLI interface**: May add new subcommands, existing ones stable
