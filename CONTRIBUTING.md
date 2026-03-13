# Contributing to tenacity-rs

Thank you for your interest in contributing. This document explains how to set up the project and submit changes.

## Prerequisites

- **Rust**: [rustup](https://rustup.rs/)
- **Python**: 3.8+
- **maturin**: `pip install maturin`

## Setup

```bash
git clone https://github.com/wkargul/tenacity-rs.git
cd tenacity-rs
pip install -e ".[test]"
```

## Running tests

```bash
pytest tests/ -v
```

Optional: run benchmarks (requires `tenacity` for comparison):

```bash
pip install tenacity
cd benchmarks && python bench.py --iterations 100
```

## Code style

- **Rust**: `cargo fmt` and `cargo clippy` in the project root.
- **Python**: follow PEP 8; the test suite uses pytest.

## Submitting changes

1. **Open an issue** (optional but recommended for larger changes) to discuss the idea.
2. **Fork** the repository and create a branch from `main` (or default branch).
3. **Implement** your change and add or update tests.
4. **Run** the test suite and, if relevant, the benchmark script.
5. **Open a pull request** with a clear description and reference to any related issue.

By submitting a PR, you agree that your contributions will be licensed under the [MIT License](LICENSE).

## Reporting bugs

Use the [GitHub issue template](.github/ISSUE_TEMPLATE/bug_report.md) when reporting bugs. Include:

- Python and Rust versions
- Steps to reproduce
- Expected vs actual behavior

## Security

See [SECURITY.md](SECURITY.md) for how to report security vulnerabilities.

## Publishing to PyPI (maintainers)

See [PUBLISHING.md](PUBLISHING.md) for how to build and publish releases to PyPI.
