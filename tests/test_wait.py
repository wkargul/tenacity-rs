"""Pytest tests for wait strategies."""
from tenacity_rs import (
    wait_chain,
    wait_exponential,
    wait_fixed,
    wait_none,
    wait_random,
    wait_random_exponential,
)


def test_wait_none():
    assert wait_none().compute(1) == 0.0


def test_wait_fixed():
    w = wait_fixed(3.5)
    assert w.compute(1) == 3.5
    assert w.compute(5) == 3.5


def test_wait_exponential():
    w = wait_exponential(multiplier=1, min=0, max=100, exp_base=2)
    assert w.compute(1) == 1.0
    assert w.compute(2) == 2.0
    assert w.compute(3) == 4.0


def test_wait_exponential_capped():
    w = wait_exponential(multiplier=1, min=0, max=10, exp_base=2)
    assert w.compute(20) == 10.0


def test_wait_random_range():
    w = wait_random(min=1.0, max=2.0)
    for _ in range(50):
        v = w.compute(1)
        assert 1.0 <= v <= 2.0


def test_wait_chain():
    w = wait_chain(wait_fixed(3), wait_fixed(3), wait_fixed(7))
    assert w.compute(1) == 3.0
    assert w.compute(3) == 7.0
    assert w.compute(99) == 7.0  # last strategy used


def test_wait_sum():
    w = wait_fixed(3) + wait_random(0, 2)
    v = w.compute(1)
    assert 3.0 <= v <= 5.0
