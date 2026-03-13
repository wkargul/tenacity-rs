# tenacity-rs vs tenacity Benchmarks

This directory contains a benchmark suite comparing **tenacity-rs** (Rust core) with the original **tenacity** (pure Python).

## Installation

From the **project root** (not from `benchmarks/`):

```bash
# Install tenacity-rs in development mode
pip install -e .

# Install tenacity for comparison
pip install tenacity
```

Or install only tenacity-rs and run with `--no-tenacity` to benchmark tenacity-rs alone.

## Running benchmarks

From the **project root**:

```bash
cd benchmarks
python bench.py
```

Or from anywhere:

```bash
python benchmarks/bench.py
```

### Options

- `--iterations N` — Number of timed iterations per benchmark (default: 500).
- `--warmup N` — Warmup iterations before timing (default: 20).
- `--no-tenacity` — Skip tenacity; only run tenacity-rs (useful if tenacity is not installed).
- `--json FILE` — Save raw results (mean, speedup, etc.) to a JSON file.
- `--markdown FILE` — Save a Markdown table of results.

Example:

```bash
python bench.py --iterations 1000 --warmup 30 --json results.json --markdown results.md
```

## Interpreting results

- **Speedup** — `tenacity_time / tenacity_rs_time`. Values &gt; 1 mean tenacity-rs is faster.
- **Mean ± stdev** — Average duration and standard deviation across iterations.
- **Legend:**
  - 🚀 — tenacity-rs is more than 1.5× faster
  - ✓ — tenacity-rs is faster
  - ⚠️ — tenacity-rs is slower (e.g. when dominated by Python callbacks or FFI)

### What to expect

- **Retry logic (stop/wait/retry checks)** — tenacity-rs is typically **2–5× faster** due to the Rust core.
- **Scenarios with real `sleep()`** — Both are similar; most time is spent in the OS sleep.
- **Heavy use of Python callbacks (before/after/before_sleep)** — tenacity-rs can be slightly slower due to FFI when calling back into Python.
- **High retry counts** — tenacity-rs tends to shine because the per-attempt overhead is lower.

## Reliable results

- Close other heavy applications to reduce variance.
- Run multiple times and compare; use `--iterations 1000` for smoother means.
- On laptops, plug in and avoid thermal throttling; or run in a cool environment.
- Results vary by machine and Python version; use the suite to compare relative performance on your setup.

## Output files

- **JSON** — Machine-readable: per-benchmark mean times and speedup for plotting or further analysis.
- **Markdown** — Table suitable for pasting into docs or README.
