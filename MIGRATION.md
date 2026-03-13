# Migration guide: tenacity → tenacity-rs

This guide helps you switch from [tenacity](https://github.com/jd/tenacity) to **tenacity-rs** with minimal changes.

## Quick switch

1. **Replace the package**

   ```bash
   pip uninstall tenacity
   pip install tenacity-rs
   ```

2. **Update imports**

   Change:

   ```python
   from tenacity import retry, stop_after_attempt, wait_fixed
   ```

   to:

   ```python
   from tenacity_rs import retry, stop_after_attempt, wait_fixed
   ```

   Or use an alias and keep the rest of your code unchanged:

   ```python
   import tenacity_rs as tenacity
   # existing code: tenacity.retry, tenacity.stop_after_attempt, etc.
   ```

3. **Run your tests** and fix any edge case listed below if needed.

---

## What stays the same

- **Decorator:** `@retry`, `@retry()`, `@retry(stop=..., wait=..., retry=...)`
- **Stop:** `stop_after_attempt(n)`, `stop_after_delay(seconds)`, `stop_never()`, `stop_before_delay()`, and `|` combination
- **Wait:** `wait_none()`, `wait_fixed(sec)`, `wait_random(min, max)`, `wait_exponential(multiplier=..., min=..., max=...)`, `wait_fixed(1) + wait_random(0, 2)`, `wait_chain(...)`
- **Retry conditions:** `retry_if_exception_type(OSError)`, `retry_if_result(predicate)`, `retry_if_exception(predicate)`, `retry_if_exception_message(...)`, and `|` / `&` combination
- **Callbacks:** `before=`, `after=`, `before_sleep=`
- **Options:** `reraise=True`, `retry_error_callback=`, `sleep=`
- **Iterator pattern:** `for attempt in Retrying(...): with attempt: ...`
- **Async:** `@retry` on `async def`; `AsyncRetrying` for `async for attempt in ...`
- **Helpers:** `before_log`, `after_log`, `before_sleep_log`
- **Exceptions:** `RetryError`, `TryAgain`
- **State:** `RetryCallState` (including `.fn` for compatibility), `.statistics`, `.retry_with(...)` on the decorated function

So in most projects you only need to change the import (or alias as above).

---

## Differences and notes

### Package and module name

- **tenacity** → **tenacity_rs** (underscore). Imports must use `tenacity_rs`; you can alias to `tenacity` if you want to avoid editing the rest of the code.

### Wait strategies

- **`wait_exponential_jitter`** (tenacity): tenacity-rs provides **`wait_random_exponential`** with a similar role (exponential backoff with jitter). If you used `wait_exponential_jitter`, switch to `wait_random_exponential` and adjust parameters to match your previous behavior (see [tenacity docs](https://tenacity.readthedocs.io/) for the exact formula if needed).

### Retry conditions

- **`retry_if_exception_cause_type`**: Not implemented in tenacity-rs. If you rely on it, you can use `retry_if_exception` with a predicate that checks `exc.__cause__`.

### RetryCallState

- tenacity-rs exposes `fn_ref` / `fn_attr` internally; a compatibility property **`.fn`** is provided so callbacks that use `retry_state.fn` work as in tenacity.

### Async

- tenacity: async is often used via `tenacity.asyncio` or a separate import.
- tenacity-rs: **`AsyncRetrying`** and async support are in the main module. Use `from tenacity_rs import AsyncRetrying` or use `@retry` on `async def`; no separate asyncio submodule.

### Performance

- tenacity-rs uses a Rust core for stop/wait/retry logic, so it is typically **2–5× faster** when retries are frequent and wait times are short. When most time is spent in `sleep()`, both libraries behave similarly.

---

## Step-by-step checklist

1. [ ] `pip uninstall tenacity` and `pip install tenacity-rs`
2. [ ] Replace `from tenacity import ...` with `from tenacity_rs import ...` (or `import tenacity_rs as tenacity`)
3. [ ] If you use `wait_exponential_jitter`, switch to `wait_random_exponential` and adjust parameters
4. [ ] If you use `retry_if_exception_cause_type`, replace with `retry_if_exception` + predicate on `__cause__`
5. [ ] Run tests and fix any remaining edge cases
6. [ ] (Optional) Run the [benchmarks](benchmarks/README.md) to compare behavior and performance

---

## Example: before and after

**Before (tenacity):**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OSError),
)
def flaky_request():
    ...
```

**After (tenacity-rs) — only import changes:**

```python
from tenacity_rs import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(OSError),
)
def flaky_request():
    ...
```

If you hit an unimplemented feature or different behavior, please open an [issue](https://github.com/wkargul/tenacity-rs/issues).
