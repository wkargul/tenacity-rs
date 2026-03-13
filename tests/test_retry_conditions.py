"""Pytest tests for retry conditions."""
import pytest

from tenacity_rs import (
    retry_all,
    retry_any,
    retry_if_exception,
    retry_if_exception_type,
    retry_if_not_exception_type,
    retry_if_not_result,
    retry_if_result,
)


def make_exc(exc_type, message="error"):
    try:
        raise exc_type(message)
    except exc_type as e:
        return e


def test_retry_if_exception_type():
    cond = retry_if_exception_type(IOError)
    assert cond.should_retry_on_exception(make_exc(IOError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(ValueError, "fail"))


def test_retry_if_not_exception_type():
    cond = retry_if_not_exception_type(ValueError)
    assert cond.should_retry_on_exception(make_exc(IOError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(ValueError, "fail"))


def test_retry_if_result():
    cond = retry_if_result(lambda x: x is None)
    assert cond.should_retry_on_result(None)
    assert not cond.should_retry_on_result(42)


def test_retry_if_not_result():
    cond = retry_if_not_result(lambda x: x is None)
    assert not cond.should_retry_on_result(None)
    assert cond.should_retry_on_result(42)


def test_or_combinator():
    cond = retry_if_exception_type(IOError) | retry_if_exception_type(ValueError)
    assert cond.should_retry_on_exception(make_exc(IOError, "fail"))
    assert cond.should_retry_on_exception(make_exc(ValueError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(RuntimeError, "fail"))


def test_retry_any():
    cond = retry_any(
        retry_if_exception_type(IOError),
        retry_if_exception_type(ValueError),
    )
    assert cond.should_retry_on_exception(make_exc(IOError, "fail"))
    assert cond.should_retry_on_exception(make_exc(ValueError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(RuntimeError, "fail"))


def test_and_combinator():
    cond = retry_if_exception_type(IOError) & retry_if_exception_type(Exception)
    assert cond.should_retry_on_exception(make_exc(IOError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(ValueError, "fail"))


def test_retry_all():
    cond = retry_all(
        retry_if_exception_type(Exception),
        retry_if_exception(lambda e: "fail" in str(e)),
    )
    assert cond.should_retry_on_exception(make_exc(ValueError, "fail"))
    assert not cond.should_retry_on_exception(make_exc(ValueError, "other"))
