"""
AsyncRetrying — async version of Retrying.
Pure Python implementation reusing Rust stop/wait/retry condition objects.
"""
import asyncio
import functools
import time

from tenacity_rs.tenacity_rs import (
    RetryCallState,
    RetryError,
    TryAgain,
)


class AsyncRetrying:
    """
    Async retry engine. Mirrors the Retrying API but uses `await asyncio.sleep()`.

    Usage as decorator:
        @retry
        async def my_func(): ...

    Usage as async context manager in async for loop:
        async for attempt in AsyncRetrying(stop=stop_after_attempt(3)):
            with attempt:
                await do_something()
    """

    def __init__(
        self,
        stop=None,
        wait=None,
        retry=None,
        before=None,
        after=None,
        before_sleep=None,
        reraise=False,
        retry_error_callback=None,
        sleep=asyncio.sleep,
    ):
        from tenacity_rs import (
            stop_never,
            wait_none,
            retry_if_exception_type,
        )
        self.stop = stop or stop_never()
        self.wait = wait or wait_none()
        self.retry = retry or retry_if_exception_type()
        self.before = before
        self.after = after
        self.before_sleep = before_sleep
        self.reraise = reraise
        self.retry_error_callback = retry_error_callback
        self.sleep = sleep

        self.statistics = {}

    async def __call__(self, fn, *args, **kwargs):
        start_time = time.monotonic()
        attempt_number = 1
        idle_for = 0.0

        self.statistics = {
            "attempt_number": attempt_number,
            "start_time": start_time,
            "delay_since_first_attempt": 0.0,
            "idle_for": 0.0,
        }

        while True:
            elapsed = time.monotonic() - start_time

            # Build a minimal state object for callbacks
            state = _AsyncRetryState(
                fn=fn,
                attempt_number=attempt_number,
                start_time=start_time,
                idle_for=idle_for,
            )

            # before callback
            if self.before is not None:
                self.before(state)

            should_retry = False
            last_exc = None
            result = None

            try:
                result = await fn(*args, **kwargs)
                state.set_result(result)

                # after callback (on success)
                if self.after is not None:
                    self.after(state)

                # check retry_if_result
                if hasattr(self.retry, "should_retry_on_result"):
                    should_retry = self.retry.should_retry_on_result(result)
                if not should_retry:
                    self.statistics["attempt_number"] = attempt_number
                    self.statistics["idle_for"] = idle_for
                    return result

            except TryAgain:
                should_retry = True

            except BaseException as exc:
                last_exc = exc
                state.set_exception(exc)

                # after callback (on failure)
                if self.after is not None:
                    self.after(state)

                # check stop condition
                elapsed = time.monotonic() - start_time
                if self.stop.should_stop(attempt_number, elapsed):
                    if self.reraise:
                        raise
                    if self.retry_error_callback is not None:
                        return self.retry_error_callback(state)
                    raise RetryError(str(exc)) from exc

                # check retry condition
                if hasattr(self.retry, "should_retry_on_exception"):
                    should_retry = self.retry.should_retry_on_exception(exc)
                else:
                    should_retry = True

                if not should_retry:
                    raise

            # Before waiting: check stop (we're about to retry)
            elapsed = time.monotonic() - start_time
            if self.stop.should_stop(attempt_number, elapsed):
                if self.retry_error_callback is not None:
                    return self.retry_error_callback(state)
                raise RetryError("Retrying failed")

            # Wait
            wait_secs = self.wait.compute(attempt_number)
            idle_for += wait_secs
            state.idle_for = idle_for

            if self.before_sleep is not None:
                self.before_sleep(state)

            await self.sleep(wait_secs)

            attempt_number += 1
            self.statistics["attempt_number"] = attempt_number
            self.statistics["idle_for"] = idle_for
            self.statistics["delay_since_first_attempt"] = idle_for

    def __call_as_decorator__(self, fn):
        """Used by the @retry decorator for async functions."""
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            return await self(fn, *args, **kwargs)
        wrapper.statistics = self.statistics
        wrapper.retry = self
        return wrapper

    # Support `async for attempt in AsyncRetrying(...):`
    def __aiter__(self):
        self._iter_attempt = 1
        self._iter_start = time.monotonic()
        self._iter_idle = 0.0
        return self

    async def __anext__(self):
        if self._iter_attempt > 1:
            # We're here because the previous attempt failed (set via attempt._retry)
            # Check stop before proceeding
            elapsed = time.monotonic() - self._iter_start
            if self.stop.should_stop(self._iter_attempt - 1, elapsed):
                raise StopAsyncIteration

        attempt = _AsyncAttempt(attempt_number=self._iter_attempt)
        self._iter_attempt += 1
        return attempt


class _AsyncRetryState:
    """Lightweight state object for async callbacks (mirrors RetryCallState API)."""
    def __init__(self, fn, attempt_number, start_time, idle_for):
        self.fn = fn
        self.attempt_number = attempt_number
        self.start_time = start_time
        self.idle_for = idle_for
        self.outcome = None

    def elapsed_time(self):
        return time.monotonic() - self.start_time

    def set_result(self, value):
        import concurrent.futures
        f = concurrent.futures.Future()
        f.set_result(value)
        self.outcome = f

    def set_exception(self, exc):
        import concurrent.futures
        f = concurrent.futures.Future()
        f.set_exception(exc)
        self.outcome = f


class AsyncRetryingWrapper:
    """Wraps an async function with AsyncRetrying. Returned by @retry for async functions."""
    def __init__(self, fn, retrying_obj):
        self._fn = fn
        self._retrying = retrying_obj
        self.statistics = {}
        functools.update_wrapper(self, fn)

    async def __call__(self, *args, **kwargs):
        # Create a fresh AsyncRetrying with same config as the Retrying object
        async_retrying = AsyncRetrying(
            stop=self._retrying.stop,
            wait=self._retrying.wait,
            retry=self._retrying.retry,
            reraise=self._retrying.reraise,
        )
        result = await async_retrying(self._fn, *args, **kwargs)
        self.statistics = async_retrying.statistics
        return result


class _AsyncAttempt:
    """Context manager for one attempt in `async for attempt in AsyncRetrying(...):`"""
    def __init__(self, attempt_number):
        self.attempt_number = attempt_number
        self.retry_state = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            # Store exception — the async for loop will handle retry decision
            self._exception = exc_val
            return True  # suppress exception, let the loop continue
        return False
