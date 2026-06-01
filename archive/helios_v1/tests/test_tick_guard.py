"""Unit tests for TickGuard exception protection."""

import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from core.tick_guard import TickGuard


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _succeeding_tick():
    """A tick function that always succeeds."""
    pass


def _failing_tick():
    """A tick function that always raises."""
    raise RuntimeError("module failure")


def _counting_tick(counter: list):
    """A tick function that records invocation."""
    counter.append(1)


# ------------------------------------------------------------------
# Tests — error counter
# ------------------------------------------------------------------


class TestErrorCounter:
    def test_starts_at_zero(self):
        guard = TickGuard()
        assert guard.consecutive_errors == 0

    def test_increments_on_exception(self):
        guard = TickGuard()
        guard.execute(_failing_tick)
        assert guard.consecutive_errors == 1
        guard.execute(_failing_tick)
        assert guard.consecutive_errors == 2

    def test_resets_on_success(self):
        guard = TickGuard()
        guard.execute(_failing_tick)
        guard.execute(_failing_tick)
        assert guard.consecutive_errors == 2
        guard.execute(_succeeding_tick)
        assert guard.consecutive_errors == 0

    def test_multiple_successes_keep_counter_at_zero(self):
        guard = TickGuard()
        for _ in range(5):
            guard.execute(_succeeding_tick)
        assert guard.consecutive_errors == 0


# ------------------------------------------------------------------
# Tests — safe mode entry
# ------------------------------------------------------------------


class TestSafeModeEntry:
    def test_not_in_safe_mode_initially(self):
        guard = TickGuard()
        assert guard.in_safe_mode is False

    def test_enters_safe_mode_after_exceeding_threshold(self):
        guard = TickGuard(max_consecutive_errors=10)
        for _ in range(10):
            guard.execute(_failing_tick)
        # At exactly 10, threshold is not exceeded yet
        assert guard.in_safe_mode is False
        # 11th error exceeds threshold
        guard.execute(_failing_tick)
        assert guard.in_safe_mode is True

    def test_does_not_enter_safe_mode_at_threshold(self):
        guard = TickGuard(max_consecutive_errors=5)
        for _ in range(5):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is False

    def test_enters_safe_mode_at_threshold_plus_one(self):
        guard = TickGuard(max_consecutive_errors=5)
        for _ in range(6):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True

    def test_custom_threshold(self):
        guard = TickGuard(max_consecutive_errors=3)
        for _ in range(4):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True


# ------------------------------------------------------------------
# Tests — safe mode exit
# ------------------------------------------------------------------


class TestSafeModeExit:
    def test_exits_safe_mode_after_recovery_ticks(self):
        guard = TickGuard(max_consecutive_errors=2, safe_mode_recovery_ticks=5)
        # Enter safe mode
        for _ in range(3):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True
        # 5 consecutive successes to recover
        for _ in range(5):
            guard.execute(_succeeding_tick)
        assert guard.in_safe_mode is False

    def test_stays_in_safe_mode_with_insufficient_successes(self):
        guard = TickGuard(max_consecutive_errors=2, safe_mode_recovery_ticks=100)
        # Enter safe mode
        for _ in range(3):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True
        # Only 50 successes — not enough
        for _ in range(50):
            guard.execute(_succeeding_tick)
        assert guard.in_safe_mode is True

    def test_error_during_recovery_resets_success_count(self):
        guard = TickGuard(max_consecutive_errors=2, safe_mode_recovery_ticks=5)
        # Enter safe mode
        for _ in range(3):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True
        # 3 successes then an error
        for _ in range(3):
            guard.execute(_succeeding_tick)
        guard.execute(_failing_tick)
        # Still in safe mode, recovery counter should have been reset
        assert guard.in_safe_mode is True
        # Need full 5 again
        for _ in range(5):
            guard.execute(_succeeding_tick)
        assert guard.in_safe_mode is False


# ------------------------------------------------------------------
# Tests — tick function execution
# ------------------------------------------------------------------


class TestTickExecution:
    def test_tick_function_is_called(self):
        guard = TickGuard()
        counter = []
        guard.execute(_counting_tick, counter)
        assert len(counter) == 1

    def test_args_are_passed_through(self):
        guard = TickGuard()
        results = []

        def tick_with_args(a, b, key=None):
            results.append((a, b, key))

        guard.execute(tick_with_args, 1, 2, key="x")
        assert results == [(1, 2, "x")]

    def test_continues_after_exception(self):
        """Guard should not propagate the exception — execution continues."""
        guard = TickGuard()
        # This should NOT raise
        guard.execute(_failing_tick)
        # And we can still execute the next tick
        counter = []
        guard.execute(_counting_tick, counter)
        assert len(counter) == 1


# ------------------------------------------------------------------
# Tests — logging
# ------------------------------------------------------------------


class TestLogging:
    def test_logs_error_on_exception(self, caplog):
        guard = TickGuard()
        with caplog.at_level(logging.ERROR, logger="core.tick_guard"):
            guard.execute(_failing_tick)
        assert any("Tick exception" in r.message for r in caplog.records)

    def test_logs_critical_on_safe_mode_entry(self, caplog):
        guard = TickGuard(max_consecutive_errors=2)
        with caplog.at_level(logging.CRITICAL, logger="core.tick_guard"):
            for _ in range(3):
                guard.execute(_failing_tick)
        critical_records = [r for r in caplog.records if r.levelno == logging.CRITICAL]
        assert len(critical_records) >= 1
        assert "safe mode" in critical_records[0].message.lower()
