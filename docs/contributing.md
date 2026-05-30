# Contributing

## Dev Setup

```bash
git clone https://github.com/UtkarshJoshiNtl/astrosis.git && cd astrosis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install pytest black flake8 mypy
```

Optional: `./build-backends.sh` for C++/CUDA backends.

## Tests

```bash
pytest tests/ -v                           # Unit tests
python validation/validate_physics.py --test energy --hours 24  # Physics validation
python benchmarks/benchmark.py --quick      # Performance regression
```

## Code Style

Python: Black + Flake8 (`black engine/`, `flake8 engine/`). C++/CUDA: clang-format. Install pre-commit hooks: `pre-commit install`.

## PR Workflow

1. Branch from `main`
2. Run full test suite: `pytest tests/ -v`
3. Format: `black engine/`
4. Open PR with a description of changes
