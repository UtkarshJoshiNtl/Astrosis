# Contributing to Astrosis

## Development Setup

```bash
git clone https://github.com/your-org/astrosis.git && cd astrosis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install pytest black flake8 mypy
```

### Build C++/CUDA Backends (Optional)

```bash
./build-backends.sh
```

## Testing

### Unit Tests

```bash
pytest tests/test_correctness.py -v
```

All tests are in a single file (17 total). Categories:
- Energy conservation (1 orbit, 24h)
- RK4 4th-order convergence
- Conjunction detection (critical, advisory, converging pairs, TCA accuracy, partial window)
- Batch propagation equivalence
- Backend info and propagate API
- Mock GPU environment override
- Circular orbit stability, two-body analytic match

### Physics Validation

```bash
python validation/validate_physics.py --test energy --hours 24
python validation/sgp4_vs_rk4.py --id 25544 --hours 24
```

Expected: energy drift < 1e-7 over 24h, RK4 exactly 4th-order.

### Performance Regression

```bash
python benchmarks/benchmark.py --quick
```

## Code Style

- **Python:** Black + Flake8 (`black engine/`, `flake8 engine/`)
- **Type hints:** MyPy (`mypy engine/ --ignore-missing-imports || true`)
- **C++/CUDA:** Clang-format, C++17 standard
- **Commit hooks:** `pre-commit install` (black, ruff, clang-format, trailing-whitespace)

## PR Workflow

1. Branch from `main`
2. Run full test suite: `pytest tests/ -v`
3. Format: `black engine/`
4. Open PR with description of changes

## Areas for Contribution

- Higher-order gravity harmonics (J5+)
- Improved atmospheric drag (NRLMSISE-00)
- Additional backends (Vulkan, HIP, SYCL)
- Eccentric orbit validation
- Launch window and re-entry tools

## Reporting Issues

Include: minimal reproduction, expected vs actual behavior, environment (OS, Python/CUDA version), full traceback.
