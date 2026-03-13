#!/usr/bin/env python3
"""
tenacity-rs vs tenacity benchmark suite.
Uses time.perf_counter(), warmup, and multiple iterations for reliable comparison.
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

# ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"


def mean_ms(times_ns):
    return statistics.mean(times_ns) / 1e6


def stdev_ms(times_ns):
    if len(times_ns) < 2:
        return 0.0
    return statistics.stdev(times_ns) / 1e6


def median_ms(times_ns):
    return statistics.median(times_ns) / 1e6


def min_ms(times_ns):
    return min(times_ns) / 1e6


def max_ms(times_ns):
    return max(times_ns) / 1e6


def run_timed(func, warmup=20, iterations=500):
    """Run func() warmup times, then iterations times; return list of durations in ns."""
    for _ in range(warmup):
        func()
    times_ns = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        func()
        t1 = time.perf_counter_ns()
        times_ns.append(t1 - t0)
    return times_ns


def run_benchmark(name, run_a, run_b, warmup=20, iterations=500):
    """Run both implementations; return (times_a_ns, times_b_ns) or (None, None) on skip."""
    try:
        times_a = run_timed(run_a, warmup=warmup, iterations=iterations)
    except Exception as e:
        print(f"  {C_RED}tenacity failed: {e}{C_RESET}")
        times_a = None
    try:
        times_b = run_timed(run_b, warmup=warmup, iterations=iterations)
    except Exception as e:
        print(f"  {C_RED}tenacity_rs failed: {e}{C_RESET}")
        times_b = None
    return times_a, times_b


def print_section(title, times_py, times_rs, name):
    """Print one benchmark result block."""
    print(f"\n{C_BOLD}{name}{C_RESET}")
    print("=" * 58)
    if times_py is not None:
        print("tenacity (Python):")
        print(f"  Mean:   {mean_ms(times_py):.3f}ms ± {stdev_ms(times_py):.3f}ms")
        print(f"  Median: {median_ms(times_py):.3f}ms")
        print(f"  Min:    {min_ms(times_py):.3f}ms")
        print(f"  Max:    {max_ms(times_py):.3f}ms")
    if times_rs is not None:
        print("tenacity-rs (Rust):")
        print(f"  Mean:   {mean_ms(times_rs):.3f}ms ± {stdev_ms(times_rs):.3f}ms")
        print(f"  Median: {median_ms(times_rs):.3f}ms")
        print(f"  Min:    {min_ms(times_rs):.3f}ms")
        print(f"  Max:    {max_ms(times_rs):.3f}ms")
    if times_py and times_rs:
        ratio = mean_ms(times_py) / mean_ms(times_rs)
        if ratio >= 1.5:
            speedup = f"{C_GREEN}Speedup: {ratio:.2f}x faster{C_RESET}"
        elif ratio >= 1.0:
            speedup = f"{C_CYAN}Speedup: {ratio:.2f}x faster{C_RESET}"
        else:
            speedup = f"{C_YELLOW}tenacity-rs: {1/ratio:.2f}x slower{C_RESET}"
        print(speedup)
    print()


def get_speedup(times_py, times_rs):
    if not times_py or not times_rs:
        return None
    return mean_ms(times_py) / mean_ms(times_rs)


def main():
    parser = argparse.ArgumentParser(description="tenacity-rs vs tenacity benchmarks")
    parser.add_argument("--iterations", type=int, default=500, help="Iterations per benchmark")
    parser.add_argument("--warmup", type=int, default=20, help="Warmup iterations")
    parser.add_argument("--no-tenacity", action="store_true", help="Skip tenacity (only run tenacity-rs)")
    parser.add_argument("--json", type=str, metavar="FILE", help="Save raw results to JSON")
    parser.add_argument("--markdown", type=str, metavar="FILE", help="Save summary table to Markdown")
    args = parser.parse_args()

    try:
        import tenacity
        tenacity_version = getattr(tenacity, "__version__", "?")
    except ImportError:
        tenacity = None
        tenacity_version = "not installed"
        if not args.no_tenacity:
            print(f"{C_YELLOW}tenacity not installed; install with: pip install tenacity{C_RESET}")
            args.no_tenacity = True

    try:
        import tenacity_rs
        tenacity_rs_version = getattr(tenacity_rs, "__version__", "0.1.0")
    except ImportError as e:
        print(f"{C_RED}Cannot import tenacity_rs: {e}. Run from project root and install with: pip install -e .{C_RESET}")
        sys.exit(1)

    print(f"{C_BOLD}{'=' * 58}{C_RESET}")
    print(f"{C_BOLD}tenacity-rs vs tenacity Benchmark Suite{C_RESET}")
    print(f"{C_BOLD}{'=' * 58}{C_RESET}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"tenacity: {tenacity_version}")
    print(f"tenacity-rs: {tenacity_rs_version}")
    print(f"{'=' * 58}\n")

    results = []

    def run(name, run_tenacity_fn, run_tenacity_rs_fn):
        print(f"Running: {name} ({args.iterations} iterations, {args.warmup} warmup)...", end=" ", flush=True)
        run_py = run_tenacity_fn if tenacity and not args.no_tenacity else lambda: None
        run_rs = run_tenacity_rs_fn
        times_py, times_rs = None, None
        if tenacity and not args.no_tenacity:
            try:
                times_py = run_timed(run_py, warmup=args.warmup, iterations=args.iterations)
            except Exception as e:
                print(f"{C_RED}tenacity failed: {e}{C_RESET}")
        try:
            times_rs = run_timed(run_rs, warmup=args.warmup, iterations=args.iterations)
        except Exception as e:
            print(f"{C_RED}tenacity_rs failed: {e}{C_RESET}")
        print(f"{C_GREEN}✓{C_RESET}")
        speedup = get_speedup(times_py, times_rs) if times_py else None
        results.append((name, times_py, times_rs, speedup))
        print_section("", times_py, times_rs, name)

    # --- Basic scenarios ---
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_none())
        def tenacity_simple_success():
            return 42
    else:
        tenacity_simple_success = lambda: 42

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(5), wait=tenacity_rs.wait_none())
    def tenacity_rs_simple_success():
        return 42

    run("Simple success (no retry)", tenacity_simple_success, tenacity_rs_simple_success)

    # Retry once
    if tenacity and not args.no_tenacity:
        attempt_py = [0]
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none())
        def tenacity_retry_once():
            attempt_py[0] += 1
            if attempt_py[0] < 2:
                raise OSError("fail")
            return "ok"
    else:
        tenacity_retry_once = lambda: "ok"

    attempt_rs = [0]
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_once():
        attempt_rs[0] += 1
        if attempt_rs[0] < 2:
            raise OSError("fail")
        return "ok"

    run("Retry once (fail then succeed)", tenacity_retry_once, tenacity_rs_retry_once)

    # Retry 3 times
    if tenacity and not args.no_tenacity:
        a3 = [0]
        @tenacity.retry(stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_none())
        def tenacity_retry_3():
            a3[0] += 1
            if a3[0] < 4:
                raise OSError()
            return "ok"
    else:
        tenacity_retry_3 = lambda: "ok"

    a3rs = [0]
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(5), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_3():
        a3rs[0] += 1
        if a3rs[0] < 4:
            raise OSError()
        return "ok"

    run("Retry 3 times", tenacity_retry_3, tenacity_rs_retry_3)

    # Retry 10 times
    if tenacity and not args.no_tenacity:
        a10 = [0]
        @tenacity.retry(stop=tenacity.stop_after_attempt(15), wait=tenacity.wait_none())
        def tenacity_retry_10():
            a10[0] += 1
            if a10[0] < 11:
                raise OSError()
            return "ok"
    else:
        tenacity_retry_10 = lambda: "ok"

    a10rs = [0]
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(15), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_10():
        a10rs[0] += 1
        if a10rs[0] < 11:
            raise OSError()
        return "ok"

    run("Retry 10 times", tenacity_retry_10, tenacity_rs_retry_10)

    # --- Stop conditions ---
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_none())
        def tenacity_stop_attempt():
            raise OSError()
        try:
            tenacity_stop_attempt()
        except tenacity.RetryError:
            pass
    else:
        def tenacity_stop_attempt():
            pass

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(5), wait=tenacity_rs.wait_none())
    def tenacity_rs_stop_attempt():
        raise OSError()
    def run_rs_stop_attempt():
        try:
            tenacity_rs_stop_attempt()
        except tenacity_rs.RetryError:
            pass

    run("Stop after 5 attempts (raise RetryError)", tenacity_stop_attempt, run_rs_stop_attempt)

    # Stop after delay - use tiny delay so benchmark finishes
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_delay(0.001), wait=tenacity.wait_none())
        def tenacity_stop_delay():
            raise OSError()
        def run_py_stop_delay():
            try:
                tenacity_stop_delay()
            except tenacity.RetryError:
                pass
    else:
        run_py_stop_delay = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_delay(0.001), wait=tenacity_rs.wait_none())
    def tenacity_rs_stop_delay():
        raise OSError()
    def run_rs_stop_delay():
        try:
            tenacity_rs_stop_delay()
        except tenacity_rs.RetryError:
            pass

    run("Stop after delay (1ms)", run_py_stop_delay, run_rs_stop_delay)

    # Stop combined
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(5) | tenacity.stop_after_delay(0.01), wait=tenacity.wait_none())
        def tenacity_stop_combined():
            raise OSError()
        def run_py_stop_combined():
            try:
                tenacity_stop_combined()
            except tenacity.RetryError:
                pass
    else:
        run_py_stop_combined = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(5) | tenacity_rs.stop_after_delay(0.01), wait=tenacity_rs.wait_none())
    def tenacity_rs_stop_combined():
        raise OSError()
    def run_rs_stop_combined():
        try:
            tenacity_rs_stop_combined()
        except tenacity_rs.RetryError:
            pass

    run("Stop combined (attempt | delay)", run_py_stop_combined, run_rs_stop_combined)

    # --- Wait strategies (minimal sleep) ---
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none())
        def tenacity_wait_none():
            raise OSError()
        def run_py_wait_none():
            try:
                tenacity_wait_none()
            except tenacity.RetryError:
                pass
    else:
        run_py_wait_none = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none())
    def tenacity_rs_wait_none():
        raise OSError()
    def run_rs_wait_none():
        try:
            tenacity_rs_wait_none()
        except tenacity_rs.RetryError:
            pass

    run("Wait none (3 attempts, RetryError)", run_py_wait_none, run_rs_wait_none)

    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(0.001))
        def tenacity_wait_fixed():
            raise OSError()
        def run_py_wait_fixed():
            try:
                tenacity_wait_fixed()
            except tenacity.RetryError:
                pass
    else:
        run_py_wait_fixed = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_fixed(0.001))
    def tenacity_rs_wait_fixed():
        raise OSError()
    def run_rs_wait_fixed():
        try:
            tenacity_rs_wait_fixed()
        except tenacity_rs.RetryError:
            pass

    run("Wait fixed (1ms)", run_py_wait_fixed, run_rs_wait_fixed)

    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_random(0.001, 0.002))
        def tenacity_wait_random():
            raise OSError()
        def run_py_wait_random():
            try:
                tenacity_wait_random()
            except tenacity.RetryError:
                pass
    else:
        run_py_wait_random = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_random(0.001, 0.002))
    def tenacity_rs_wait_random():
        raise OSError()
    def run_rs_wait_random():
        try:
            tenacity_rs_wait_random()
        except tenacity_rs.RetryError:
            pass

    run("Wait random (1–2ms)", run_py_wait_random, run_rs_wait_random)

    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(4), wait=tenacity.wait_exponential(multiplier=0.001, max=0.01))
        def tenacity_wait_exp():
            raise OSError()
        def run_py_wait_exp():
            try:
                tenacity_wait_exp()
            except tenacity.RetryError:
                pass
    else:
        run_py_wait_exp = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(4), wait=tenacity_rs.wait_exponential(multiplier=0.001, max=0.01))
    def tenacity_rs_wait_exp():
        raise OSError()
    def run_rs_wait_exp():
        try:
            tenacity_rs_wait_exp()
        except tenacity_rs.RetryError:
            pass

    run("Wait exponential (0.001, max 0.01)", run_py_wait_exp, run_rs_wait_exp)

    # Wait combined (fixed + random)
    if tenacity and not args.no_tenacity:
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_fixed(0.001) + tenacity.wait_random(0, 0.001))
        def tenacity_wait_combined():
            raise OSError()
        def run_py_wait_combined():
            try:
                tenacity_wait_combined()
            except tenacity.RetryError:
                pass
    else:
        run_py_wait_combined = lambda: None

    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_fixed(0.001) + tenacity_rs.wait_random(0, 0.001))
    def tenacity_rs_wait_combined():
        raise OSError()
    def run_rs_wait_combined():
        try:
            tenacity_rs_wait_combined()
        except tenacity_rs.RetryError:
            pass

    run("Wait combined (fixed + random)", run_py_wait_combined, run_rs_wait_combined)

    # --- Retry conditions ---
    if tenacity and not args.no_tenacity:
        @tenacity.retry(retry=tenacity.retry_if_exception_type(OSError), stop=tenacity.stop_after_attempt(5), wait=tenacity.wait_none())
        def tenacity_retry_io():
            raise OSError()
        def run_py_retry_io():
            try:
                tenacity_retry_io()
            except tenacity.RetryError:
                pass
    else:
        run_py_retry_io = lambda: None

    @tenacity_rs.retry(retry=tenacity_rs.retry_if_exception_type(OSError), stop=tenacity_rs.stop_after_attempt(5), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_io():
        raise OSError()
    def run_rs_retry_io():
        try:
            tenacity_rs_retry_io()
        except tenacity_rs.RetryError:
            pass

    run("Retry if OSError (5 attempts)", run_py_retry_io, run_rs_retry_io)

    if tenacity and not args.no_tenacity:
        @tenacity.retry(retry=tenacity.retry_if_result(lambda x: x is None), stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none())
        def tenacity_retry_result():
            return None
        def run_py_retry_result():
            try:
                tenacity_retry_result()
            except tenacity.RetryError:
                pass
    else:
        run_py_retry_result = lambda: None

    @tenacity_rs.retry(retry=tenacity_rs.retry_if_result(lambda x: x is None), stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_result():
        return None
    def run_rs_retry_result():
        try:
            tenacity_rs_retry_result()
        except tenacity_rs.RetryError:
            pass

    run("Retry if result is None", run_py_retry_result, run_rs_retry_result)

    # Retry combined conditions (exception type | result)
    if tenacity and not args.no_tenacity:
        retry_comb = tenacity.retry_if_exception_type(OSError) | tenacity.retry_if_result(lambda x: x is None)
        @tenacity.retry(retry=retry_comb, stop=tenacity.stop_after_attempt(4), wait=tenacity.wait_none())
        def tenacity_retry_combined():
            return None  # retry on None
        def run_py_retry_combined():
            try:
                tenacity_retry_combined()
            except tenacity.RetryError:
                pass
    else:
        run_py_retry_combined = lambda: None

    retry_comb_rs = tenacity_rs.retry_if_exception_type(OSError) | tenacity_rs.retry_if_result(lambda x: x is None)
    @tenacity_rs.retry(retry=retry_comb_rs, stop=tenacity_rs.stop_after_attempt(4), wait=tenacity_rs.wait_none())
    def tenacity_rs_retry_combined():
        return None
    def run_rs_retry_combined():
        try:
            tenacity_rs_retry_combined()
        except tenacity_rs.RetryError:
            pass

    run("Retry combined (OSError | result None)", run_py_retry_combined, run_rs_retry_combined)

    # --- Callbacks ---
    if tenacity and not args.no_tenacity:
        def before_cb(_):
            pass
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none(), before=before_cb)
        def tenacity_before():
            raise OSError()
        def run_py_before():
            try:
                tenacity_before()
            except tenacity.RetryError:
                pass
    else:
        run_py_before = lambda: None

    def before_cb_rs(_):
        pass
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none(), before=before_cb_rs)
    def tenacity_rs_before():
        raise OSError()
    def run_rs_before():
        try:
            tenacity_rs_before()
        except tenacity_rs.RetryError:
            pass

    run("Before callback", run_py_before, run_rs_before)

    if tenacity and not args.no_tenacity:
        def after_cb(_):
            pass
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none(), after=after_cb)
        def tenacity_after():
            raise OSError()
        def run_py_after():
            try:
                tenacity_after()
            except tenacity.RetryError:
                pass
    else:
        run_py_after = lambda: None

    def after_cb_rs(_):
        pass
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none(), after=after_cb_rs)
    def tenacity_rs_after():
        raise OSError()
    def run_rs_after():
        try:
            tenacity_rs_after()
        except tenacity_rs.RetryError:
            pass

    run("After callback", run_py_after, run_rs_after)

    if tenacity and not args.no_tenacity:
        def before_sleep_cb(_):
            pass
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none(), before_sleep=before_sleep_cb)
        def tenacity_before_sleep():
            raise OSError()
        def run_py_before_sleep():
            try:
                tenacity_before_sleep()
            except tenacity.RetryError:
                pass
    else:
        run_py_before_sleep = lambda: None

    def before_sleep_cb_rs(_):
        pass
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none(), before_sleep=before_sleep_cb_rs)
    def tenacity_rs_before_sleep():
        raise OSError()
    def run_rs_before_sleep():
        try:
            tenacity_rs_before_sleep()
        except tenacity_rs.RetryError:
            pass

    run("Before-sleep callback", run_py_before_sleep, run_rs_before_sleep)

    # All callbacks (before + after + before_sleep)
    if tenacity and not args.no_tenacity:
        def all_cb_before(_): pass
        def all_cb_after(_): pass
        def all_cb_sleep(_): pass
        @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none(), before=all_cb_before, after=all_cb_after, before_sleep=all_cb_sleep)
        def tenacity_all_callbacks():
            raise OSError()
        def run_py_all_callbacks():
            try:
                tenacity_all_callbacks()
            except tenacity.RetryError:
                pass
    else:
        run_py_all_callbacks = lambda: None

    def all_cb_before_rs(_): pass
    def all_cb_after_rs(_): pass
    def all_cb_sleep_rs(_): pass
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none(), before=all_cb_before_rs, after=all_cb_after_rs, before_sleep=all_cb_sleep_rs)
    def tenacity_rs_all_callbacks():
        raise OSError()
    def run_rs_all_callbacks():
        try:
            tenacity_rs_all_callbacks()
        except tenacity_rs.RetryError:
            pass

    run("All callbacks (before + after + before_sleep)", run_py_all_callbacks, run_rs_all_callbacks)

    # --- Reraise ---
    if tenacity and not args.no_tenacity:
        @tenacity.retry(reraise=True, stop=tenacity.stop_after_attempt(2), wait=tenacity.wait_none())
        def tenacity_reraise():
            raise OSError("x")
        def run_py_reraise():
            try:
                tenacity_reraise()
            except OSError:
                pass
    else:
        run_py_reraise = lambda: None

    @tenacity_rs.retry(reraise=True, stop=tenacity_rs.stop_after_attempt(2), wait=tenacity_rs.wait_none())
    def tenacity_rs_reraise():
        raise OSError("x")
    def run_rs_reraise():
        try:
            tenacity_rs_reraise()
        except OSError:
            pass

    run("Reraise (OSError)", run_py_reraise, run_rs_reraise)

    # --- Iterator pattern ---
    if tenacity and not args.no_tenacity:
        def run_py_iterator():
            attempts = [0]
            try:
                for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none()):
                    with attempt:
                        attempts[0] += 1
                        raise OSError()
            except tenacity.RetryError:
                pass
    else:
        run_py_iterator = lambda: None

    def run_rs_iterator():
        attempts = [0]
        try:
            for attempt in tenacity_rs.Retrying(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none()):
                with attempt:
                    attempts[0] += 1
                    raise OSError()
        except tenacity_rs.RetryError:
            pass

    run("Iterator pattern (for attempt in Retrying)", run_py_iterator, run_rs_iterator)

    # --- High attempt count ---
    if tenacity and not args.no_tenacity:
        a50_py = [0]
        @tenacity.retry(stop=tenacity.stop_after_attempt(60), wait=tenacity.wait_none())
        def tenacity_high():
            a50_py[0] += 1
            if a50_py[0] < 51:
                raise OSError()
            return "ok"
    else:
        tenacity_high = lambda: "ok"

    a50_rs = [0]
    @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(60), wait=tenacity_rs.wait_none())
    def tenacity_rs_high():
        a50_rs[0] += 1
        if a50_rs[0] < 51:
            raise OSError()
        return "ok"

    run("High attempt count (50 retries)", tenacity_high, tenacity_rs_high)

    # --- Async ---
    try:
        import asyncio
        if tenacity and not args.no_tenacity:
            @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_none())
            async def tenacity_async_simple():
                return 42
            _async_attempt_py = [0]
            @tenacity.retry(stop=tenacity.stop_after_attempt(4), wait=tenacity.wait_none())
            async def tenacity_async_retry_3():
                _async_attempt_py[0] += 1
                if _async_attempt_py[0] < 4:
                    raise OSError()
                return 42
            def run_py_async_simple():
                asyncio.run(tenacity_async_simple())
            def run_py_async_retry_3():
                _async_attempt_py[0] = 0
                asyncio.run(tenacity_async_retry_3())
        else:
            run_py_async_simple = lambda: None
            run_py_async_retry_3 = lambda: None

        @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(3), wait=tenacity_rs.wait_none())
        async def tenacity_rs_async_simple():
            return 42
        _async_attempt_rs = [0]
        @tenacity_rs.retry(stop=tenacity_rs.stop_after_attempt(4), wait=tenacity_rs.wait_none())
        async def tenacity_rs_async_retry_3():
            _async_attempt_rs[0] += 1
            if _async_attempt_rs[0] < 4:
                raise OSError()
            return 42
        def run_rs_async_simple():
            asyncio.run(tenacity_rs_async_simple())
        def run_rs_async_retry_3():
            _async_attempt_rs[0] = 0
            asyncio.run(tenacity_rs_async_retry_3())

        run("Async simple success", run_py_async_simple, run_rs_async_simple)
        run("Async retry 3 times", run_py_async_retry_3, run_rs_async_retry_3)
    except Exception as e:
        print(f"Skipping async benchmarks: {e}")

    # --- Summary ---
    print(f"\n{C_BOLD}{'=' * 58}{C_RESET}")
    print(f"{C_BOLD}SUMMARY{C_RESET}")
    print(f"{C_BOLD}{'=' * 58}{C_RESET}\n")

    speedups = [(name, speedup) for name, _, _, speedup in results if speedup is not None]
    if speedups:
        avg = statistics.mean(s for _, s in speedups)
        print(f"Average speedup (tenacity / tenacity_rs): {avg:.2f}x\n")
        print("Results by speedup:")
        print("-" * 58)
        for name, s in sorted(speedups, key=lambda x: -x[1]):
            if s >= 1.5:
                icon = "🚀"
            elif s >= 1.0:
                icon = "✓ "
            else:
                icon = "⚠️ "
            print(f"  {icon} {name[:45]:<45} {s:.2f}x")
    else:
        print("No comparison (tenacity not run or no results).")

    print(f"\n{C_BOLD}{'=' * 58}{C_RESET}")
    print("Legend: 🚀 = >1.5x faster, ✓ = faster, ⚠️ = slower")
    print(f"{C_BOLD}{'=' * 58}{C_RESET}")

    # Save JSON
    if args.json:
        data = {
            "python": sys.version.split()[0],
            "tenacity": tenacity_version,
            "tenacity_rs": tenacity_rs_version,
            "iterations": args.iterations,
            "warmup": args.warmup,
            "results": [
                {
                    "name": name,
                    "tenacity_mean_ms": mean_ms(tpy) if tpy else None,
                    "tenacity_rs_mean_ms": mean_ms(trs) if trs else None,
                    "speedup": get_speedup(tpy, trs),
                }
                for name, tpy, trs, _ in results
            ],
        }
        Path(args.json).write_text(json.dumps(data, indent=2))
        print(f"\nRaw results saved to {args.json}")

    # Save Markdown
    if args.markdown:
        lines = [
            "| Benchmark | tenacity (ms) | tenacity-rs (ms) | Speedup |",
            "|-----------|---------------|------------------|---------|",
        ]
        for name, tpy, trs, _ in results:
            py_ms = f"{mean_ms(tpy):.3f}" if tpy else "—"
            rs_ms = f"{mean_ms(trs):.3f}" if trs else "—"
            sp = get_speedup(tpy, trs)
            sp_s = f"{sp:.2f}x" if sp else "—"
            lines.append(f"| {name} | {py_ms} | {rs_ms} | {sp_s} |")
        Path(args.markdown).write_text("\n".join(lines))
        print(f"Markdown table saved to {args.markdown}")


if __name__ == "__main__":
    main()
