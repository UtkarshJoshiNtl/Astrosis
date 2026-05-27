# Astrosis — AGENTS.md

## Project structure

Dual-language monorepo:

- **`engine/`** — Python orbital mechanics engine (CLI via `main.py`, REST via `server.py`)
- **`src/`** — TanStack Start + React frontend (Cloudflare Worker, port 8080)
- **`cpp/`** — C++/CUDA backends (pybind11 bridge, built via CMake)
- **`validation/`** — Physics validation scripts (analytical baselines, SGP4 comparison)
- **`benchmarks/`** — Performance regression suite
- **`tests/`** — Single test file `test_correctness.py`

## Commands

| Task                | Command                                                          |
| ------------------- | ---------------------------------------------------------------- |
| Install Python deps | `pip install -r requirements.txt`                                |
| Install JS deps     | `pnpm install`                                                   |
| Build C++/CUDA      | `./build-backends.sh` (auto-detects CUDA)                        |
| Run CLI             | `python main.py <command>`                                       |
| Start full app      | `./run.sh` (option 2 → backend port 8000 + frontend port 8080)   |
| Dev frontend only   | `pnpm dev` (proxies `/api` to `localhost:8000`)                  |
| Run Python tests    | `pytest tests/test_correctness.py -v`                            |
| Python lint         | `flake8 engine/`                                                 |
| Python format check | `black --check engine/`                                          |
| Python typecheck    | `mypy engine/ --ignore-missing-imports`                          |
| TS/JS lint          | `pnpm lint` (eslint)                                             |
| TS/JS format        | `pnpm format` (prettier)                                         |
| Validation          | `python validation/validate_physics.py --test energy --hours 24` |
| TLE cache refresh   | `./scripts/refresh-tle-cache.sh`                                 |

**Only one test file exists.** Run `pytest tests/test_correctness.py -v` — there are no other test files.

## Architecture

- **Backend auto-selection** in `engine/core/accelerator.py`: CUDA → C++/OpenMP → NumPy → Python fallback
- Physical constants are **single source of truth** in `engine/constants.py`
- **Julian Date**, **equation of equinoxes**, and **TEME→ECI conversion** are single-source in `engine/geo/frames.py` (`julian_date`, `equation_of_equinoxes`, `teme_to_eci`); do NOT reimplement elsewhere
- **Conjunction severity** uses `Severity` (StrEnum) from `engine/core/conjunction.py` — use enum members not string literals; C++ `Severity` enum in `conjunction.h` is converted to Python `Severity` via `_cpp_warnings_to_py` in `accelerator.py`
- **Fuel tracking** uses `FuelTracker` in `engine/core/fuel.py`; `apply_burn` raises `ValueError` on insufficient fuel; C++ `fuel.cpp:apply_burn` throws `std::runtime_error` (same semantics)
- **Maneuver fuel cost** in both Python (`maneuver.py`) and C++ (`maneuver.cpp`) uses total mass (`DRY_MASS + INITIAL_FUEL`), not `INITIAL_FUEL` alone — the recovery burn accounts for mass lost in evasion burn
- Entrypoints: `main.py` (CLI), `server.py` (FastAPI REST), `engine.cli.main` (argparse)
- Physics uses **FP64 everywhere** (FP32 insufficient for 24h integration)
- Fixed-step RK4 (not adaptive) — required for GPU warp uniformity
- Simulation state: 6-element list `[x, y, z, vx, vy, vz]` in ECI, units km and km/s
- **C++ `__constant__` variables** are single-source in `cpp/cuda_constants.cu`, declared `extern` in `cpp/cuda_physics.cuh` — do NOT add `static __constant__` in headers (UB, wastes constant memory)
- **RAII wrappers** in `cpp/cuda_physics.cuh`: `DeviceMem` (cudaMalloc/cudaFree) and `HostPinnedMem` (cudaHostAlloc/cudaFreeHost) prevent GPU memory leaks on exception — use them instead of raw cudaMalloc in CUDA host functions
- **C++ conjunction Brent refinement** propagates from the saved bracket-left state (`sat_lo`/`deb_lo`) instead of re-propagating from t=0 — limits propagation to at most 2× step_s per evaluation
- **Tempated Brent minimiser** in `conjunction.cpp` (`brent_minimise<F>`) avoids `std::function` heap allocation

## Frontend gotchas

- `vite.config.ts` uses `@lovable.dev/vite-tanstack-config` — **do not add** tanstackStart, viteReact, tailwindcss, tsConfigPaths, or cloudflare plugins manually (duplicate plugin error)
- satellite.js v7 **WASM modules are stubbed** (`src/lib/empty-wasm-stub.js`) — the pure JS SGP4 implementation is used instead
- `src/server.ts` wraps TanStack Start SSR with error capture; `src/start.ts` adds error middleware
- Route tree is auto-generated at `routeTree.gen.ts` — **do not edit manually**
- shadcn/ui components in `src/components/ui/`, configured via `components.json`
- Vite proxies `/api` → `http://localhost:8000` in dev

## CI pipeline (`.github/workflows/ci.yml`)

Order: `flake8` → `black --check` → `mypy` (best-effort, `|| true`) → `pytest tests/ -v`

Runs on push to `main`/`develop` and PRs to `main`. Only tests Python side; no frontend CI.

## Environment

- `.env` (copy from `.env.example`) — `CELESTRAK_API_URL`, `TLE_REFRESH_INTERVAL_HOURS`, `LOG_LEVEL`
- Optional: `SPACETRACK_USER` / `SPACETRACK_PASS` for Space-Track TLE source
- Python venv expected at `venv/` (activated by `run.sh` if present)
- Pre-commit hooks: none detected
