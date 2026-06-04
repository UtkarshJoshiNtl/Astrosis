# Astrosis — AGENTS.md

CLI + TUI orbital mechanics calculator. No frontend, no server.

## Structure
- `astrosis/` — Python implementation (entrypoints: `main.py`, `python -m astrosis`, or `astrosis` after `pip install -e .`)
- `cpp/` — C++/CUDA backends (pybind11 module `physics_engine`, built via CMake)
- `tests/` — `test_correctness.py` (17 tests)
- `validation/` — Physics validation plots (run from repo root — scripts use `sys.path.insert(0, ...)`)
- `benchmarks/` — `run_benchmarks.py`
- `scripts/` — `refresh-tle-cache.sh`

## Commands
| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Install pybind11 | `pip install pybind11` (needed for C++ build) |
| Build C++/CUDA | `./build-backends.sh` (auto-detects CUDA) |
| Run CLI | `astrosis <command>` or `python -m astrosis` or `python main.py <command>` |
| Run TUI | `astrosis` (no args) |
| Tests | `pytest tests/test_correctness.py -v` (17 tests) |
| Lint | `flake8 astrosis/` |
| Format check | `black --check astrosis/` |
| Typecheck | `mypy astrosis/ --ignore-missing-imports \|\| true` (CI passes with `\|\| true`) |
| Validation | `python validation/validate_physics.py` (outputs PNGs to `validation/plots/`) |
| SGP4 comparison | `python validation/sgp4_vs_rk4.py` |
| TLE refresh | `./scripts/refresh-tle-cache.sh` |
| Pre-commit install | `pre-commit install` |
| Install editable | `pip install -e .` (makes `astrosis` available on PATH) |

CI order (`.github/workflows/ci.yml`): `flake8` → `black --check` → `mypy \|\| true` → `pytest tests/ -v` + separate C++ build job (no CUDA in CI).

## Architecture rules
- State: 6-element list `[x, y, z, vx, vy, vz]`, ECI frame, km and km/s
- FP64 everywhere — FP32 insufficient for 24 h integration
- Fixed-step RK4 only (no adaptive stepping; GPU warp uniformity constraint)
- Constants single-source in `astrosis/constants.py`
- `julian_date`, `equation_of_equinoxes`, `teme_to_eci` in `astrosis/geo/frames.py` — do NOT reimplement
- `Severity` (StrEnum) in `astrosis/core/conjunction.py` — use enum, not string literals
- Auto-backend: `astrosis/core/accelerator.py` picks CUDA → C++/OpenMP → NumPy → Python fallback
- Mock GPU: `ASTROSIS_MOCK_GPU=1` or `python main.py --mock-gpu`

## C++/CUDA specifics
- CMake in `cpp/`, flag `-DUSE_CUDA=ON/OFF` (default **ON**), GPU arch `sm_75;80;86;89`
- Compile flags: `-O3 -march=native` (C++), `-O3 -lineinfo` (CUDA) — **no `-ffast-math` or `--use_fast_math`** (removed for FP64 IEEE 754 compliance)
- `__constant__` variables single-source in `cuda_physics.cuh`, `extern` in same header — do NOT add `static __constant__` in headers (UB)
- RAII wrappers: use `DeviceMem` / `HostPinnedMem` in `cuda_physics.cuh`, not raw `cudaMalloc`
- Brent minimiser: `brent_minimise<F>` in `conjunction.cpp` — templated, no `std::function`
- CUDA conjunction: 2-phase `k_prepropagate` (SoA per timestep) + `k_scan_pairs` (coalesced reads)
- C++ conjunction: pre-propagates all objects via `batch_propagate_full_history`, then pairwise distance scan + Brent refinement from nearest pre-propagated frame
- `monte_carlo_pc()` in `astrosis/core/accelerator.py` — CUDA → Python fallback
- `astrosis/__main__.py` enables `python -m astrosis`

## TUI gotchas (Textual 8.x)
- **Do NOT name an attribute `_current_mode`** — Textual's `App` uses this internally for its MODES dict. Use `_active_tab` or similar.
- **`DataTable.clear()` does NOT clear columns** — always use `table.clear(columns=True)` or columns accumulate across mode switches.
- **`Static` has no `.renderable` property** in Textual 8.x. Use `ListView.index` or set `ListItem(name=...)` to identify items.
- **Textual CSS** is a subset. `flex: 1` is invalid — use `height: 100%` or `width: 100%`.
- **Propagate results** are text shown in a `Static` widget (`#propagate-result`), not in the DataTable. Hide the DataTable (`table.display = False`) when showing text output, or results get hidden behind the empty table.

## CSV format (conjunction mode)
- **6 columns (headerless):** `x, y, z, vx, vy, vz` — first row IS data
- **7 columns (with header row):** `id, x, y, z, vx, vy, vz` — first row is skipped as header
- **Bug to avoid:** The CSV loader always consumes the first row. For 6-col files, it tries to parse it as data (numeric); if that fails, it treats it as a header. For 7-col files, the first row is always treated as a header.

## Pre-commit hooks
black (astrosis/ + tests/), ruff (astrosis/ + tests/), clang-format (cpp/), trailing-whitespace, end-of-file-fixer, check-yaml, check-json.

## TLE cache
- Location: `~/.cache/astrosis/tle/`
- Per-satellite: `<norad_id>.txt`, bulk: `active.txt`
- Refresh interval: 6h by default (`.env.example`), configurable via `TLE_REFRESH_INTERVAL_HOURS`

## Env
- Copy `.env.example` → `.env`. Supports `CELESTRAK_API_URL`, `TLE_REFRESH_INTERVAL_HOURS`, `LOG_LEVEL`.
- Optional: `SPACETRACK_USER` / `SPACETRACK_PASS`
