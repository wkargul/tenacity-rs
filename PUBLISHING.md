# Publishing tenacity-rs to PyPI

This document is for maintainers who want to publish releases to [PyPI](https://pypi.org/project/tenacity-rs/). The PyPI project is linked to the **wkargul** account.

## Option A: GitHub Action with Trusted Publishing (recommended)

Releases are built and published automatically when you **create a GitHub Release** (or run the workflow manually). Authentication uses **PyPI Trusted Publishing (OIDC)** — no API token is stored in GitHub.

### Setup (once)

1. **Register the project on PyPI** (if not already)  
   Log in to [pypi.org](https://pypi.org) as **wkargul**, go to "Add new project", and create **tenacity-rs** (the name must match `name` in `pyproject.toml`).

2. **Add a Trusted Publisher**  
   On PyPI: open the project **tenacity-rs** → **Publishing** (or go to `https://pypi.org/manage/project/tenacity-rs/settings/publishing/`).  
   Under **Trusted publishers**, click **Add a new pending publisher** and set:
   - **Owner:** `wkargul`
   - **Repository name:** `tenacity-rs`
   - **Workflow name:** `release.yml`
   - **Environment:** leave empty (or set e.g. `release` if you use a GitHub Environment)

   Save. After the first successful run of the workflow, the publisher will be activated. No repository secrets are needed.

### How to release

1. Bump version in `pyproject.toml` and `Cargo.toml`, and update [CHANGELOG.md](CHANGELOG.md).
2. Commit and push.
3. Create a **GitHub Release**: **Releases** → **Draft a new release** → choose a tag (e.g. `v0.1.0`, create the tag if needed) → publish.
4. The **Release to PyPI** workflow will run: it builds wheels for Linux (manylinux), macOS (x64 + arm64), Windows, and the sdist, then publishes to PyPI.
5. Verify: `pip install tenacity-rs` and check [pypi.org/project/tenacity-rs](https://pypi.org/project/tenacity-rs/).

---

## Option B: Manual publish (local)

### Prerequisites

- [PyPI](https://pypi.org/) account (and [TestPyPI](https://test.pypi.org/) for dry runs)
- [maturin](https://www.maturin.rs/) installed: `pip install maturin`

## Before the first release

1. **Register the project on PyPI**  
   Log in to [pypi.org](https://pypi.org), go to “Add new project”, and create **tenacity-rs** (the name must match `name` in `pyproject.toml`). You can reserve the name even before uploading.

2. **API token (recommended)**  
   In PyPI: Account settings → API tokens → Add API token. Use a token scoped to this project.  
   Configure once locally:
   ```bash
   # ~/.pypirc or environment variables
   export MATURIN_PYPI_TOKEN="pypi-..."
   ```

3. **Optional: add author email**  
   In `pyproject.toml`, under `[project]` → `authors`, you can add `email = "your@email.com"` if you want it shown on PyPI.

## Release steps

1. **Bump version**  
   In `pyproject.toml` and `Cargo.toml`, set the new version (e.g. `0.1.1`).  
   Update [CHANGELOG.md](CHANGELOG.md) with the release date and changes.

2. **Build**  
   From the project root:
   ```bash
   maturin build --release
   ```
   This produces wheels and an sdist in `target/wheels/` (or `dist/` depending on maturin version).

3. **Upload to PyPI**  
   ```bash
   maturin publish
   ```
   Or, if you use twine:
   ```bash
   pip install twine
   twine upload target/wheels/*
   ```

4. **Test install**  
   In a clean environment:
   ```bash
   pip install tenacity-rs
   python -c "import tenacity_rs; print(tenacity_rs.__file__)"
   ```

5. **Tag the release**  
   ```bash
   git tag -a v0.1.0 -m "Release 0.1.0"
   git push origin v0.1.0
   ```

## TestPyPI (optional)

To try the release without publishing to the real PyPI:

```bash
maturin build --release
maturin publish -r testpypi
```

Then install with:

```bash
pip install -i https://test.pypi.org/simple/ tenacity-rs
```

## Notes

- **Wheels**: maturin builds platform-specific wheels (e.g. manylinux, macOS, Windows) when you run it on those platforms or use CI (e.g. [maturin-action](https://github.com/PyO3/maturin-action)) to build for multiple platforms.
- **Version**: Keep `version` in sync in both `pyproject.toml` and `Cargo.toml` (maturin can read from pyproject.toml; check [maturin docs](https://www.maturin.rs/metadata.html) for single-source versioning if you prefer).
