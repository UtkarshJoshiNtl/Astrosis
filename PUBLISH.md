# Publishing Astrosis to PyPI

## Current Status

✅ **Release Branch** (`release`): Production-ready, fully refactored  
- ✅ All 17 tests pass
- ✅ Package builds (sdist + wheel)
- ✅ `twine check` passes
- ✅ Clean imports: `astrosis` (no `engine` references)
- ✅ Entry point: `astrosis = "astrosis.cli:main"`
- ✅ README updated with `astrosis` examples
- ✅ CI workflow: lint, test, C++ build, package check

📌 **Main Branch** (`main`): Development  
- Current state with development tools
- Can be merged with release changes or kept separate

## Quick Start: Publish to PyPI

### 1. Create PyPI Account & API Token
- Go to https://pypi.org/account/register/
- Create account and verify email
- Go to Account Settings → API tokens → Add API token
- Generate a token with "Entire account" scope
- **Save token securely** (you'll only see it once)

### 2. Set GitHub Secrets (for CI publish)
```bash
# In your GitHub repo: Settings → Secrets and variables → Actions
# Add two secrets:
PYPI_API_TOKEN = pypi-<your-token>
PYPI_USERNAME = __token__
```

### 3. Create Release Workflow (CI/CD Auto-Publish)
Copy this to `.github/workflows/publish.yml`:
```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build twine
      - run: python -m build
      - run: >
          python -m twine upload dist/*
          -u __token__
          -p ${{ secrets.PYPI_API_TOKEN }}
```

### 4. Bump Version (on release branch)
```bash
# On release branch
git checkout release
# Edit pyproject.toml: version = "0.1.1"
git add pyproject.toml
git commit -m "Bump version to 0.1.1"
git tag -a v0.1.1 -m "Release v0.1.1"
git push origin release --tags
```

This triggers the publish workflow automatically. Or manually:

```bash
# Manual publish
git checkout release
python -m build
python -m twine upload dist/* \
  -u __token__ \
  -p pypi-<your-token>
```

### 5. Verify on PyPI
After publish, visit: https://pypi.org/project/astrosis/

Install and test:
```bash
pip install astrosis
python -c "import astrosis; print(astrosis.__version__)"
```

## Branch Strategy

| Branch | Purpose | Merge Into PyPI |
|--------|---------|-----------------|
| `main` | Development, experiments | ❌ No |
| `release` | Production-ready, clean | ✅ Yes |

## Pre-Publish Checklist

- [ ] Confirm package name `astrosis` is available (not taken by someone else)
- [ ] Bump version in `pyproject.toml` (don't reuse old versions)
- [ ] Run tests: `pytest tests/ -v`
- [ ] Build: `python -m build`
- [ ] Validate: `python -m twine check dist/*`
- [ ] (Optional) Test on TestPyPI first:
  ```bash
  python -m twine upload --repository testpypi dist/* \
    -u __token__ -p pypi-<test-token>
  ```
  Then: `pip install -i https://test.pypi.org/simple/ astrosis==0.1.1`

## Important Notes

- **Native backends** (C++/CUDA) are optional. Users can install and use the pure-Python fallback. Prebuilt wheels are not included in this release.
- **Dependencies**: Ensure all required packages (`numpy`, `scipy`, `sgp4`, `rich`, `textual`) are pinned to tested versions.
- **License**: Package uses MIT license (see `LICENSE` file).
- **GitHub**: Point users to https://github.com/UtkarshJoshiNtl/Astrosis for source, issues, docs.

## What Happens When Users Install

```bash
pip install astrosis
```

- Downloads `astrosis-0.1.0-py3-none-any.whl` (or `.tar.gz`)
- Installs `astrosis` package
- Sets up CLI entry point: `astrosis` command available
- Users can `import astrosis` or run `astrosis --help`

## Post-Publish

- [ ] Create GitHub Release: https://github.com/UtkarshJoshiNtl/Astrosis/releases
- [ ] Link PyPI URL and version
- [ ] Add release notes (changelog)
- [ ] Update README badge: [![PyPI - Version](https://img.shields.io/pypi/v/astrosis)](https://pypi.org/project/astrosis/)

---

**Questions?** Refer to [pypa.io](https://packaging.python.org/tutorials/packaging-projects/) or [twine docs](https://twine.readthedocs.io/).
