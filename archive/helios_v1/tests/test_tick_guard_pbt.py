"""Property-based tests for TickGuard error counter lifecycle.

# Feature: helios-architecture-enhancement, Property 3: Tick Error Counter Lifecycle

**Validates: Requirements 5.4, 5.5**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import integers

from core.tick_guard import TickGuard


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _failing_tick():
    """A tick function that always raises."""
    raise RuntimeError("simulated failure")


def _succeeding_tick():
    """A tick function that always succeeds."""
    pass


# ------------------------------------------------------------------
# Property 3: Tick Error Counter Lifecycle
# ------------------------------------------------------------------


class TestTickErrorCounterLifecycle:
    """Property 3: For any sequence of N consecutive tick exceptions followed
    by a successful tick, the error counter SHALL equal N before the success
    and SHALL reset to 0 after the success. When N exceeds 10, safe mode
    SHALL be entered.
    """

    @given(n=integers(min_value=1, max_value=200))
    @settings(max_examples=100)
    def test_error_counter_equals_n_after_n_failures(self, n: int):
        """After N consecutive failures, the error counter equals N."""
        guard = TickGuard(max_consecutive_errors=10)
        for _ in range(n):
            guard.execute(_failing_tick)
        assert guard.consecutive_errors == n

    @given(n=integers(min_value=1, max_value=200))
    @settings(max_examples=100)
    def test_error_counter_resets_to_zero_after_success(self, n: int):
        """After N consecutive failures followed by a success, counter resets to 0."""
        guard = TickGuard(max_consecutive_errors=10)
        for _ in range(n):
            guard.execute(_failing_tick)
        # Verify counter equals N before the success
        assert guard.consecutive_errors == n
        # Execute a successful tick
        guard.execute(_succeeding_tick)
        # Counter must reset to 0
        assert guard.consecutive_errors == 0

    @given(n=integers(min_value=11, max_value=200))
    @settings(max_examples=100)
    def test_safe_mode_entered_when_n_exceeds_10(self, n: int):
        """When N exceeds 10 (threshold), safe mode SHALL be entered."""
        guard = TickGuard(max_consecutive_errors=10)
        for _ in range(n):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is True

    @given(n=integers(min_value=1, max_value=10))
    @settings(max_examples=100)
    def test_safe_mode_not_entered_when_n_at_or_below_10(self, n: int):
        """When N does not exceed 10, safe mode SHALL NOT be entered."""
        guard = TickGuard(max_consecutive_errors=10)
        for _ in range(n):
            guard.execute(_failing_tick)
        assert guard.in_safe_mode is False
