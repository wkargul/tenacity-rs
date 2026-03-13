# tenacity-rs

[![CI](https://github.com/wkargul/tenacity-rs/actions/workflows/ci.yml/badge.svg)](https://github.com/wkargul/tenacity-rs/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **drop-in replacement** for [tenacity](https://github.com/jd/tenacity) with a **Rust core**. Same API, faster retry engine.

- **API-compatible** with tenacity — swap the package and your code keeps working.
- **Faster** for retry logic (stop/wait/retry checks); see [Benchmarks](#benchmarks).
- **Async** supported via the same decorator and iterator patterns.

## Install

```bash
pip install tenacity-rs
```

### Drop-in replacement

```bash
pip uninstall tenacity
pip install tenacity-rs
```

Your existing code works without changes (import stays `tenacity_rs` or you can alias).  
**→ See [MIGRATION.md](MIGRATION.md) for a step-by-step guide and any API differences.**

## Usage

```python
from tenacity_rs import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def call_flaky_service():
    ...
```

API matches [tenacity](https://tenacity.readthedocs.io/): `@retry`, `stop_after_attempt`, `stop_after_delay`, `wait_fixed`, `wait_exponential`, `retry_if_exception_type`, `retry_if_result`, callbacks (`before`, `after`, `before_sleep`), and the iterator pattern (`for attempt in Retrying(...)`).

## Benchmarks

We provide a benchmark suite comparing tenacity-rs with pure-Python tenacity:

```bash
pip install -e . tenacity
cd benchmarks && python bench.py
```

See [benchmarks/README.md](benchmarks/README.md) for options (`--iterations`, `--json`, `--markdown`) and how to interpret results. In short: tenacity-rs is typically **2–5× faster** on retry logic; when most time is spent in `sleep()`, both are similar.

## Build from source

Requires [Rust](https://rustup.rs/) and a Python environment.

```bash
pip install maturin
maturin develop
```

For Python 3.13+, set before building:

```bash
export PYO3_USE_ABI3_FORWARD_COMPATIBILITY=1
maturin develop
```

## Development

```bash
pip install -e ".[test]"
pytest tests/ -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## License

[MIT](LICENSE).

## Acknowledgments

- [tenacity](https://github.com/jd/tenacity) by Julien Danjou and contributors — API and design. tenacity is licensed under the [Apache License, Version 2.0](https://github.com/jd/tenacity/blob/main/LICENSE). This project is an independent reimplementation; no code from tenacity has been copied.
- Built with [PyO3](https://pyo3.rs/) and [maturin](https://www.maturin.rs/).
