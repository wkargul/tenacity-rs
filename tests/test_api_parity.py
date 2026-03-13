"""
API parity tests: verify that tenacity-rs behaves identically to tenacity.
Every test here is based on examples from the official tenacity README.
"""
import pytest
import time

from tenacity_rs import (
    retry,
    Retrying,
    RetryError,
    TryAgain,
    stop_after_attempt,
    stop_after_delay,
    stop_before_delay,
    stop_never,
    wait_fixed,
    wait_random,
    wait_exponential,
    wait_random_exponential,
    wait_chain,
    wait_none,
    retry_if_exception_type,
    retry_if_not_exception_type,
    retry_if_result,
    retry_if_not_result,
    retry_if_exception,
    retry_any,
)


# ── Basic retry ──────────────────────────────────────────────────────────────

def test_retry_forever_on_exception():
    """Default @retry retries until success."""
    attempts = [0]

    @retry
    def fn():
        attempts[0] += 1
        if attempts[0] < 5:
            raise OSError()
        return "ok"

    assert fn() == "ok"
    assert attempts[0] == 5


# ── Stop conditions ───────────────────────────────────────────────────────────

def test_stop_after_7_attempts():
    @retry(stop=stop_after_attempt(7))
    def fn():
        raise Exception("fail")

    with pytest.raises(RetryError) as exc_info:
        fn()
    # Should have tried exactly 7 times
    assert fn.statistics["attempt_number"] == 7


def test_stop_after_delay(monkeypatch):
    """stop_after_delay stops retrying after N seconds have elapsed."""
    elapsed = [0.0]
    original_monotonic = time.monotonic

    def fake_monotonic():
        elapsed[0] += 1.0
        return elapsed[0]

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    @retry(stop=stop_after_delay(5), wait=wait_none())
    def fn():
        raise Exception("fail")

    with pytest.raises(RetryError):
        fn()


def test_stop_combined():
    """| operator combines stop conditions."""
    @retry(stop=stop_after_delay(100) | stop_after_attempt(3), wait=wait_none())
    def fn():
        raise Exception("fail")

    with pytest.raises(RetryError):
        fn()
    assert fn.statistics["attempt_number"] == 3


# ── Wait strategies ───────────────────────────────────────────────────────────

def test_wait_fixed(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert all(s == 2.0 for s in slept)


def test_wait_random(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    @retry(stop=stop_after_attempt(5), wait=wait_random(min=0, max=1))
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert all(0 <= s <= 1 for s in slept)


def test_wait_exponential(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=1, max=10))
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert slept[0] == 1.0
    assert slept[1] == 2.0
    assert slept[2] == 4.0


def test_wait_fixed_plus_random(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(3) + wait_random(0, 2))
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert all(3.0 <= s <= 5.0 for s in slept)


def test_wait_chain(monkeypatch):
    slept = []
    monkeypatch.setattr(time, "sleep", lambda s: slept.append(s))

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_chain(wait_fixed(3), wait_fixed(3), wait_fixed(7)),
    )
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert slept[0] == 3.0
    assert slept[1] == 3.0
    assert slept[2] == 7.0


# ── Retry conditions ──────────────────────────────────────────────────────────

def test_retry_if_exception_type():
    class ClientError(Exception):
        pass

    attempts = [0]

    @retry(retry=retry_if_exception_type(OSError), stop=stop_after_attempt(5), wait=wait_none())
    def fn():
        attempts[0] += 1
        raise OSError("io fail")

    with pytest.raises(RetryError):
        fn()
    assert attempts[0] == 5


def test_retry_if_exception_type_reraises_other():
    class ClientError(Exception):
        pass

    @retry(retry=retry_if_exception_type(OSError), wait=wait_none())
    def fn():
        raise ClientError("client fail")

    with pytest.raises(ClientError):
        fn()


def test_retry_if_result():
    def is_none(value):
        return value is None

    attempts = [0]

    @retry(retry=retry_if_result(is_none), stop=stop_after_attempt(3), wait=wait_none())
    def fn():
        attempts[0] += 1
        return None if attempts[0] < 3 else "ok"

    assert fn() == "ok"


# ── Error handling ────────────────────────────────────────────────────────────

def test_reraise():
    class MyException(Exception):
        pass

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_none())
    def fn():
        raise MyException("Fail")

    with pytest.raises(MyException):
        fn()


def test_retry_error_callback():
    def return_last_value(retry_state):
        return retry_state.outcome.result()

    def is_false(value):
        return value is False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_none(),
        retry_error_callback=return_last_value,
        retry=retry_if_result(is_false),
    )
    def fn():
        return False

    assert fn() is False


def test_try_again():
    attempts = [0]

    @retry(stop=stop_after_attempt(5), wait=wait_none())
    def fn():
        attempts[0] += 1
        if attempts[0] < 3:
            raise TryAgain
        return "done"

    assert fn() == "done"


# ── Callbacks ────────────────────────────────────────────────────────────────

def test_before_callback():
    called_with = []

    def my_before(retry_state):
        called_with.append(retry_state.attempt_number)

    attempts = [0]

    @retry(stop=stop_after_attempt(3), wait=wait_none(), before=my_before)
    def fn():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OSError()
        return "ok"

    fn()
    assert 1 in called_with


def test_after_callback():
    called = [0]

    def my_after(retry_state):
        called[0] += 1

    @retry(stop=stop_after_attempt(3), wait=wait_none(), after=my_after)
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()
    assert called[0] >= 1


# ── Statistics ────────────────────────────────────────────────────────────────

def test_statistics_populated():
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    def fn():
        raise OSError()

    with pytest.raises(RetryError):
        fn()

    stats = fn.statistics
    assert "attempt_number" in stats
    assert stats["attempt_number"] == 3


# ── Retrying as context manager ───────────────────────────────────────────────

def test_retrying_for_loop():
    attempts = [0]
    try:
        for attempt in Retrying(stop=stop_after_attempt(3), wait=wait_none()):
            with attempt:
                attempts[0] += 1
                raise Exception("fail")
    except RetryError:
        pass
    assert attempts[0] == 3


# ── retry_with ────────────────────────────────────────────────────────────────

def test_retry_with_overrides():
    @retry(stop=stop_after_attempt(2), wait=wait_none())
    def fn():
        raise OSError()

    # Original uses 2 attempts
    with pytest.raises(RetryError):
        fn()
    assert fn.statistics["attempt_number"] == 2

    # retry_with uses 4 attempts, but doesn't mutate original
    new_fn = fn.retry_with(stop=stop_after_attempt(4))
    with pytest.raises(RetryError):
        new_fn()
    # Original still uses 2
    with pytest.raises(RetryError):
        fn()
    assert fn.statistics["attempt_number"] == 2
