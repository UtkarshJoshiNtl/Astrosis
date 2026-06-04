# Astrosis PyPI Release — Complete Overhaul Summary

## ✅ Complete Refactor & Release Prep

This document summarizes the full overhaul of the Astrosis repository for PyPI publication.

---

## 📋 What Was Done

### 1. **Package Restructure** (engine → astrosis)
- Renamed `engine/` → `astrosis/` (main implementation package)
- Updated **100+ import statements** across:
  - Python source files (astrosis/*, server.py, main.py)
  - Test suite (tests/test_correctness.py)
  - Scripts (scripts/check_backend.py, demo_tui.py)
  - Benchmarks & validation (benchmarks/, validation/)
  - CI workflows (.github/workflows/ci.yml)
  - Pre-commit hooks (.pre-commit-config.yaml)
- Updated package configuration:
  - `pyproject.toml`: entry point `astrosis.cli:main`, clean package list
  - `MANIFEST.in`: include `astrosis/` files
  - `package-data`: `astrosis.data` (TLE files)

### 2. **Documentation Updates**
- **README.md**: Changed `import engine` → `import astrosis` in Python API examples; updated architecture diagram
- **AGENTS.md**: Updated all 17 engine references to astrosis
- **RELEASE_CHECKLIST.md**: Added release-focused checklist
- **PUBLISH.md**: Comprehensive PyPI publishing guide (new)

### 3. **CI/CD Pipeline**
- **Fixed `.github/workflows/ci.yml`**: Removed duplicate jobs, unified into 4 jobs:
  - `lint`: flake8, black, mypy on `astrosis/`
  - `test`: pytest with editable install
  - `cpp`: C++ build (no CUDA in CI)
  - `build`: sdist + wheel + twine check
- **Pre-commit hooks**: Updated to lint `astrosis/` and `tests/`

### 4. **Quality Assurance**
- ✅ All **17 tests pass** (pytest)
- ✅ **Package builds successfully**: Both sdist (`.tar.gz`) and wheel (`.whl`)
- ✅ **Twine validation passes**: Metadata is PyPI-compliant
- ✅ **No import errors**: All imports use `astrosis.*`

---

## 📁 Repository Structure (Release Branch)

```
astrosis/                          ← Main package
  ├── __init__.py                  ← Exports & lazy loading
  ├── __main__.py                  ← `python -m astrosis`
  ├── cli.py                       ← CLI interface
  ├── tui.py                       ← TUI (Textual)
  ├── constants.py                 ← Physics constants
  ├── core/
  │   ├── propagator.py            ← RK4 integration
  │   ├── conjunction.py           ← Conjunction detection
  │   ├── ephemeris.py             ← Sun/Moon positions
  │   └── accelerator.py           ← Backend router (CUDA/C++/NumPy/Python)
  ├── geo/
  │   ├── frames.py                ← Coordinate transforms
  │   ├── analysis.py              ← Pass prediction
  │   ├── cities.py                ← City database
  │   └── visibility.py            ← Visibility checks
  ├── io/
  │   └── data.py                  ← TLE ingestion
  └── data/
      └── active.txt               ← Bundled TLE data

.github/workflows/
  └── ci.yml                       ← CI pipeline (lint, test, build)

tests/
  └── test_correctness.py          ← 17 physics tests

pyproject.toml                      ← Package metadata & dependencies
MANIFEST.in                         ← Includes for sdist
README.md                           ← User-facing docs
LICENSE                            ← MIT license
PUBLISH.md                         ← PyPI publishing guide (new)
RELEASE_CHECKLIST.md               ← Release checklist (new)
AGENTS.md                          ← Architecture & dev notes
```

---

## 🔄 Branches

### `release` (Current Production-Ready)
- ✅ Clean, refactored codebase
- ✅ All imports use `astrosis`
- ✅ Package validated and builds successfully
- ✅ Ready for `pip install astrosis`
- 📌 **This is what gets published to PyPI**

### `main` (Development)
- Old codebase with `engine/` (to be updated)
- Can keep experimental changes, validation scripts, benchmarks
- Merged into `release` when stable

**Recommended workflow:**
1. Work on `main` for development
2. When stable: cherry-pick or merge into `release`
3. Bump version, tag, and push to `release` → auto-publish

---

## 🚀 Next Steps to Publish

### Quick (< 5 minutes)
1. **Create PyPI account**: https://pypi.org/account/register/
2. **Generate API token**: Account Settings → API tokens
3. **Store token locally**: Create `~/.pypirc` or use environment
4. **Test build locally**:
   ```bash
   git checkout release
   python -m build
   python -m twine check dist/*
   ```

### Full (< 30 minutes)
1. Add GitHub Secrets: `PYPI_API_TOKEN`, `PYPI_USERNAME`
2. Create `.github/workflows/publish.yml` (see PUBLISH.md)
3. Bump version in `pyproject.toml` (release branch)
4. Tag & push: `git tag -a v0.1.1 -m "Release"` → triggers CI auto-publish

### Verify
```bash
# Wait for GitHub Actions to complete
pip install astrosis
python -c "import astrosis; print(astrosis.__version__)"
```

---

## 📊 Stats

| Metric | Value |
|--------|-------|
| Files Refactored | 37 |
| Import Statements Updated | 100+ |
| Tests Passing | 17/17 ✅ |
| Package Size | ~2.5 MB (wheel) |
| Python Versions Supported | 3.10–3.13 |
| Main Dependencies | numpy, scipy, sgp4, rich, textual |

---

## 🔍 Key Files for Publishing

- **[pyproject.toml](pyproject.toml)**: Package metadata, version (currently `0.1.0`)
- **[README.md](README.md)**: Long description (rendered on PyPI)
- **[LICENSE](LICENSE)**: MIT license
- **[PUBLISH.md](PUBLISH.md)**: Step-by-step PyPI guide
- **[.github/workflows/ci.yml](.github/workflows/ci.yml)**: CI pipeline
- **[release branch](../../tree/release)**: Production-ready code

---

## ⚠️ Important Before Publishing

1. **Confirm package name**: `astrosis` is available on PyPI (check https://pypi.org/project/astrosis/)
2. **Never reuse versions**: Each version can only be published once. Always bump before re-uploading.
3. **Test on TestPyPI first** (optional but recommended):
   ```bash
   python -m twine upload --repository testpypi dist/*
   pip install -i https://test.pypi.org/simple/ astrosis
   ```
4. **Include GitHub workflows**: CI will auto-test on push/PR and auto-publish on tag push
5. **Document native backends**: Users can install C++/CUDA backends optionally; pure-Python fallback always works

---

## 💡 Tips

- **Editable install for dev**: `pip install -e .`
- **Run full test suite**: `pytest tests/ -v`
- **Lint before commit**: `pre-commit run --all-files`
- **Build locally**: `python -m build`
- **Check metadata**: `python -m twine check dist/*`

---

## 📞 Support

Refer to:
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [PyPI Help](https://pypi.org/help/)
- This repo: [PUBLISH.md](PUBLISH.md) & [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)

---

**Ready to publish?** See [PUBLISH.md](PUBLISH.md) for step-by-step instructions.
