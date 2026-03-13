"""
tenacity-rs — drop-in replacement for tenacity with a Rust core.
"""
import asyncio
import functools
import time

from tenacity_rs.tenacity_rs import (
    # Stop strategies (functions returning strategy instances)
    stop_after_attempt,
    stop_after_delay,
    stop_before_delay,
    stop_never,
    # Wait strategies (classes: wait_none(), wait_fixed(seconds), etc.)
    WaitChain as wait_chain,
    WaitExponential as wait_exponential,
    WaitFixed as wait_fixed,
    WaitNone as wait_none,
    WaitRandom as wait_random,
    WaitRandomExponential as wait_random_exponential,
    # Retry conditions
    retry_all,
    retry_any,
    retry_if_exception,
    retry_if_exception_message,
    retry_if_exception_type,
    retry_if_not_exception_message,
    retry_if_not_exception_type,
    retry_if_not_result,
    retry_if_result,
    retry_unless_exception_type,
    # Core
    Retrying,
    RetryCallState,
    RetryError,
    TryAgain,
)

# Async retry engine (pure Python, reuses Rust stop/wait/retry)
from tenacity_rs._async import AsyncRetrying

# Tenacity API: retry_state.fn — native exposes fn_ref and fn_attr
if hasattr(RetryCallState, "fn_attr"):
    RetryCallState.fn = property(lambda self: getattr(self, "fn_ref", None))


# Logging helpers (pure Python — loggers are Python objects)
def before_log(logger, log_level):
    """Returns a before-callback that logs each attempt."""
    def callback(retry_state):
        fn = getattr(retry_state, "fn", None) or getattr(retry_state, "fn_ref", None)
        name = getattr(fn, "__name__", "unknown") if fn else "unknown"
        logger.log(
            log_level,
            "Starting call to '%s', this is the %d time calling it.",
            name,
            retry_state.attempt_number,
        )
    return callback


def after_log(logger, log_level):
    """Returns an after-callback that logs each failure."""
    def callback(retry_state):
        fn = getattr(retry_state, "fn", None) or getattr(retry_state, "fn_ref", None)
        name = getattr(fn, "__name__", "unknown") if fn else "unknown"
        logger.log(
            log_level,
            "Finished call to '%s' after %.3f(s), this is the %d time calling it.",
            name,
            retry_state.elapsed_time(),
            retry_state.attempt_number,
        )
    return callback


def before_sleep_log(logger, log_level, exc_info=False):
    """Returns a before_sleep-callback that logs before sleeping."""
    def callback(retry_state):
        logger.log(
            log_level,
            "Retrying %s: attempt %s ended with: %s",
            getattr(retry_state, "fn", getattr(retry_state, "fn_ref", None)),
            retry_state.attempt_number,
            retry_state.outcome,
            exc_info=exc_info,
        )
    return callback


def retry(*args, **kwargs):
    """
    @retry decorator — drop-in replacement for tenacity.retry.

    Usage:
        @retry                           # bare decorator
        @retry()                         # no-arg call
        @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    """
    # Handle @retry with no args (bare decorator)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        fn = args[0]
        return _wrap(fn, Retrying(
            stop=stop_never(),
            wait=wait_none(),
            retry=retry_if_exception_type(),
        ))

    # Handle @retry() or @retry(stop=..., wait=...)
    retrying = Retrying(
        stop=kwargs.get("stop", stop_never()),
        wait=kwargs.get("wait", wait_none()),
        retry=kwargs.get("retry", retry_if_exception_type()),
        before=kwargs.get("before"),
        after=kwargs.get("after"),
        before_sleep=kwargs.get("before_sleep"),
        reraise=kwargs.get("reraise", False),
        retry_error_callback=kwargs.get("retry_error_callback"),
        sleep=kwargs.get("sleep", time.sleep),
    )

    def decorator(fn):
        return _wrap(fn, retrying)
    return decorator


def _wrap(fn, retrying_obj):
    """Wrap fn with retrying_obj, handling both sync and async functions."""
    if asyncio.iscoroutinefunction(fn):
        from tenacity_rs._async import AsyncRetryingWrapper
        return AsyncRetryingWrapper(fn, retrying_obj)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return retrying_obj(fn, *args, **kwargs)

    # Attach tenacity-compatible attributes
    wrapper.statistics = retrying_obj.statistics
    wrapper.retry = retrying_obj

    def retry_with(**new_kwargs):
        merged = {
            "stop": retrying_obj.stop,
            "wait": retrying_obj.wait,
            "retry": retrying_obj.retry,
            "reraise": retrying_obj.reraise,
        }
        merged.update(new_kwargs)
        new_retrying = Retrying(**merged)
        return functools.wraps(fn)(lambda *a, **k: new_retrying(fn, *a, **k))

    wrapper.retry_with = retry_with

    return wrapper


__all__ = [
    "retry",
    "Retrying",
    "AsyncRetrying",
    "RetryCallState",
    "RetryError",
    "TryAgain",
    "stop_after_attempt",
    "stop_after_delay",
    "stop_before_delay",
    "stop_never",
    "wait_none",
    "wait_fixed",
    "wait_random",
    "wait_exponential",
    "wait_random_exponential",
    "wait_chain",
    "retry_if_exception",
    "retry_if_exception_type",
    "retry_if_not_exception_type",
    "retry_unless_exception_type",
    "retry_if_result",
    "retry_if_not_result",
    "retry_if_exception_message",
    "retry_if_not_exception_message",
    "retry_any",
    "retry_all",
    "before_log",
    "after_log",
    "before_sleep_log",
]
