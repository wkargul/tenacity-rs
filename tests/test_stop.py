"""Pytest tests for stop strategies (tenacity_rs.tenacity_rs)."""
import pytest

from tenacity_rs.tenacity_rs import (
    stop_after_attempt,
    stop_after_delay,
    stop_before_delay,
    stop_never,
)


class TestStopNever:
    """stop_never()"""

    def test_basic_never_stops(self):
        s = stop_never()
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 1.0) is False
        assert s.should_stop(100, 1000.0) is False

    def test_edge_attempt_zero_elapsed_zero(self):
        s = stop_never()
        assert s.should_stop(0, 0.0) is False

    def test_or_combination_stops_when_other_stops(self):
        s = stop_never() | stop_after_attempt(2)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 0.0) is False
        assert s.should_stop(2, 0.0) is True
        assert s.should_stop(3, 0.0) is True


class TestStopAfterAttempt:
    """stop_after_attempt(n)"""

    def test_basic_stops_at_and_after_max(self):
        s = stop_after_attempt(3)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 0.0) is False
        assert s.should_stop(2, 0.0) is False
        assert s.should_stop(3, 0.0) is True
        assert s.should_stop(4, 0.0) is True

    def test_edge_max_zero_stops_immediately(self):
        s = stop_after_attempt(0)
        assert s.should_stop(0, 0.0) is True
        assert s.should_stop(1, 0.0) is True

    def test_edge_max_one_stops_after_first_attempt(self):
        s = stop_after_attempt(1)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 0.0) is True

    def test_elapsed_ignored(self):
        s = stop_after_attempt(2)
        assert s.should_stop(2, 0.0) is True
        assert s.should_stop(2, 999.0) is True
        assert s.should_stop(1, 999.0) is False

    def test_or_combination_with_delay(self):
        s = stop_after_attempt(3) | stop_after_delay(10.0)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(3, 0.0) is True
        assert s.should_stop(0, 10.0) is True
        assert s.should_stop(2, 11.0) is True


class TestStopAfterDelay:
    """stop_after_delay(seconds)"""

    def test_basic_stops_when_elapsed_ge_limit(self):
        s = stop_after_delay(10.0)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(0, 9.9) is False
        assert s.should_stop(0, 10.0) is True
        assert s.should_stop(0, 10.1) is True

    def test_edge_zero_delay_stops_immediately(self):
        s = stop_after_delay(0.0)
        assert s.should_stop(0, 0.0) is True
        assert s.should_stop(0, 0.1) is True

    def test_edge_small_delay(self):
        s = stop_after_delay(0.001)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(0, 0.001) is True

    def test_attempt_ignored(self):
        s = stop_after_delay(5.0)
        assert s.should_stop(0, 5.0) is True
        assert s.should_stop(100, 5.0) is True
        assert s.should_stop(100, 4.9) is False

    def test_or_combination_with_attempt(self):
        s = stop_after_delay(10.0) | stop_after_attempt(1)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 0.0) is True
        assert s.should_stop(0, 10.0) is True


class TestStopBeforeDelay:
    """stop_before_delay(seconds)"""

    def test_basic_stops_when_elapsed_ge_limit(self):
        s = stop_before_delay(5.0)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(0, 4.9) is False
        assert s.should_stop(0, 5.0) is True
        assert s.should_stop(0, 5.1) is True

    def test_edge_zero_delay_stops_immediately(self):
        s = stop_before_delay(0.0)
        assert s.should_stop(0, 0.0) is True

    def test_or_combination_with_after_delay(self):
        s = stop_before_delay(3.0) | stop_after_delay(6.0)
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(0, 3.0) is True
        assert s.should_stop(0, 6.0) is True


class TestStopOrChaining:
    """| combination (stop_any) behavior."""

    def test_three_way_or(self):
        s = stop_after_attempt(1) | stop_after_attempt(2) | stop_after_delay(1.0)
        # (1 | 2) | delay: stops at attempt 1 or 2 or at 1s
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(1, 0.0) is True
        assert s.should_stop(0, 1.0) is True

    def test_never_or_never_never_stops(self):
        s = stop_never() | stop_never()
        assert s.should_stop(0, 0.0) is False
        assert s.should_stop(100, 1000.0) is False
