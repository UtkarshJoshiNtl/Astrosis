Release checklist for publishing Astrosis

- [ ] Confirm `pyproject.toml` `name` is the intended PyPI project (astrosis)
- [ ] Bump `version` in `pyproject.toml` (do not reuse published versions)
- [ ] Run test suite: `pytest -q`
- [ ] Build sdist and wheel: `python -m build`
- [ ] Run `python -m twine check dist/*`
- [ ] Upload to TestPyPI and validate installation there
- [ ] Create Git tag and GitHub release notes
- [ ] Publish to PyPI using a PyPI API token stored in GitHub Secrets
- [ ] Verify README renders on PyPI and GitHub
- [ ] Confirm C++/CUDA backend docs explain optional native build steps

Notes:
- This repository contains native backends under `cpp/`. For user-friendly
  prebuilt wheels consider adding `cibuildwheel` to CI and producing manylinux
  wheels for Linux (and platform-specific CUDA wheels if desired).
- The package exposes functionality via `astrosis` (the main implementation) and is published as
  `astrosis` on PyPI.
