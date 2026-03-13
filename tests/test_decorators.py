"""Pytest tests for Retrying decorator and retry loop."""
import pytest

from tenacity_rs import (
    Retrying,
    RetryError,
    TryAgain,
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_none,
    wait_fixed,
)


# --- Direct Retrying API (r(fn) runs the loop) ---

def test_basic_retry_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("fail")
        return "ok"

    r = Retrying(stop=stop_after_attempt(5), wait=wait_none())
    result = r(flaky)
    assert result == "ok"
    assert len(attempts) == 3


def test_retry_raises_after_limit():
    def always_fails():
        raise OSError("fail")

    r = Retrying(stop=stop_after_attempt(3), wait=wait_none())
    with pytest.raises(RetryError):
        r(always_fails)


def test_reraise():
    def always_fails():
        raise OSError("original error")

    r = Retrying(
        stop=stop_after_attempt(2), wait=wait_none(), reraise=True
    )
    with pytest.raises(OSError, match="original error"):
        r(always_fails)


def test_try_again():
    attempts = []

    def fn():
        attempts.append(1)
        if len(attempts) < 3:
            raise TryAgain
        return "done"

    r = Retrying(stop=stop_after_attempt(5), wait=wait_none())
    result = r(fn)
    assert result == "done"
    assert len(attempts) == 3


def test_statistics():
    call_count = [0]

    def fn():
        call_count[0] += 1
        if call_count[0] < 3:
            raise OSError()
        return "ok"

    r = Retrying(stop=stop_after_attempt(5), wait=wait_none())
    r(fn)
    assert r.statistics["attempt_number"] >= 3


def test_retry_error_callback():
    def return_last(retry_state):
        return "fallback"

    def always_fails():
        return False

    r = Retrying(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry=retry_if_result(lambda x: x is False),
        retry_error_callback=return_last,
    )
    result = r(always_fails)
    assert result == "fallback"


# --- @retry decorator API ---

def test_bare_retry_decorator():
    """@retry with no args retries forever on any exception."""
    attempts = [0]

    @retry
    def fn():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OSError("fail")
        return "ok"

    assert fn() == "ok"


def test_retry_with_stop():
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    def always_fails():
        raise OSError("fail")

    with pytest.raises(RetryError):
        always_fails()


def test_retry_preserves_return_value():
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    def fn():
        return 42

    assert fn() == 42


def test_retry_with_has_statistics():
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()

    assert fn.statistics["attempt_number"] >= 1


def test_retry_with_reraise():
    @retry(stop=stop_after_attempt(2), wait=wait_none(), reraise=True)
    def fn():
        raise ValueError("original")

    with pytest.raises(ValueError, match="original"):
        fn()


def test_retry_with_method():
    """retry_with() returns a new callable without mutating the original."""
    @retry(stop=stop_after_attempt(2), wait=wait_none())
    def fn():
        raise OSError()

    new_fn = fn.retry_with(stop=stop_after_attempt(4))
    # original should still use 2 attempts
    with pytest.raises(RetryError):
        fn()
