import pytest
import asyncio
from tenacity_rs import (
    retry,
    stop_after_attempt,
    wait_none,
    retry_if_exception_type,
    RetryError,
)
from tenacity_rs._async import AsyncRetrying


@pytest.mark.asyncio
async def test_async_retry_succeeds():
    attempts = [0]

    @retry(stop=stop_after_attempt(5), wait=wait_none())
    async def flaky():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OSError("fail")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert attempts[0] == 3


@pytest.mark.asyncio
async def test_async_retry_raises():
    @retry(stop=stop_after_attempt(3), wait=wait_none())
    async def always_fails():
        raise OSError("fail")

    with pytest.raises(RetryError):
        await always_fails()


@pytest.mark.asyncio
async def test_async_retrying_direct():
    attempts = [0]

    async def flaky():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OSError()
        return "done"

    r = AsyncRetrying(stop=stop_after_attempt(5), wait=wait_none())
    result = await r(flaky)
    assert result == "done"


@pytest.mark.asyncio
async def test_async_custom_sleep():
    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    attempts = [0]

    async def flaky():
        attempts[0] += 1
        if attempts[0] < 3:
            raise OSError()
        return "ok"

    r = AsyncRetrying(stop=stop_after_attempt(5), wait=wait_none(), sleep=fake_sleep)
    await r(flaky)
    # sleep was called between attempts
    assert len(sleep_calls) == 2
