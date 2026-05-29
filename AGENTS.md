# Astrosis — AGENTS.md

## Identity
CLI-only orbital mechanics calculator. No frontend, no server.

## Structure
- `engine/` — Python orbital mechanics engine (CLI via `main.py`)
- `cpp/` — C++/CUDA backends (pybind11 bridge, built via CMake)
- `validation/` — Physics validation scripts
- `benchmarks/` — Performance regression suite
- `tests/` — Single file `test_correctness.py`

## Commands
| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Build C++/CUDA | `./build-backends.sh` (auto-detects CUDA) |
| Run CLI | `python main.py <command>` |
| Tests | `pytest tests/test_correctness.py -v` (17 tests) |
| Lint | `flake8 engine/` |
| Format check | `black --check engine/` |
| Typecheck | `mypy engine/ --ignore-missing-imports` (best-effort; CI passes with `|| true`) |
| Validation | `python validation/validate_physics.py --test energy --hours 24` |
| TLE refresh | `./scripts/refresh-tle-cache.sh` |

CI order (`.github/workflows/ci.yml`): `flake8` → `black --check` → `mypy \|\| true` → `pytest tests/ -v` + separate C++ build job.

## Architecture rules
- State: 6-element list `[x, y, z, vx, vy, vz]`, ECI frame, km and km/s
- FP64 everywhere — FP32 insufficient for 24 h integration
- Fixed-step RK4 only (no adaptive stepping; GPU warp uniformity constraint)
- Constants single-source in `engine/constants.py`
- `julian_date`, `equation_of_equinoxes`, `teme_to_eci` in `engine/geo/frames.py` — do NOT reimplement
- `Severity` (StrEnum) in `engine/core/conjunction.py` — use enum, not string literals
- Auto-backend: `engine/core/accelerator.py` picks CUDA → C++/OpenMP → NumPy → Python fallback
- Mock GPU: `ASTROSIS_MOCK_GPU=1` or `python main.py --mock-gpu`

## C++/CUDA specifics
- CMake in `cpp/`, flag `-DUSE_CUDA=ON/OFF`, default GPU arch `sm_75`
- Compile flags: `-O3 -march=native -ffast-math` (C++), `--use_fast_math -lineinfo` (CUDA)
- `__constant__` variables single-source in `cuda_physics.cuh`, `extern` in same header — do NOT add `static __constant__` in headers (UB)
- RAII wrappers: use `DeviceMem` / `HostPinnedMem` in `cuda_physics.cuh`, not raw `cudaMalloc`
- Brent minimiser: `brent_minimise<F>` in `conjunction.cpp` — templated, no `std::function`
- CUDA conjunction: 2-phase `k_prepropagate` (SoA per timestep) + `k_scan_pairs` (coalesced reads)
- C++ conjunction: pre-propagates all objects via `batch_propagate_full_history`, then pairwise distance scan + Brent refinement from nearest pre-propagated frame
- `monte_carlo_pc()` in `engine/core/accelerator.py` — CUDA → Python fallback
- `engine/__main__.py` enables `python -m engine`

## Pre-commit hooks
black, ruff, clang-format (C++/CUDA), trailing-whitespace, end-of-file-fixer, check-yaml, check-json. Install: `pre-commit install`

## Env
- Copy `.env.example` → `.env` (supports `CELESTRAK_API_URL`, `TLE_REFRESH_INTERVAL_HOURS`, `LOG_LEVEL`)
- Optional: `SPACETRACK_USER` / `SPACETRACK_PASS`
