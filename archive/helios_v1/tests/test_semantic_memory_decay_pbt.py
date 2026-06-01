"""Property-based tests for Semantic Memory Decay and Forgetting.

# Feature: helios-architecture-enhancement, Property 19: Semantic Memory Decay and Forgetting

**Validates: Requirements 19.1, 19.2, 19.3, 19.4**
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import floats, integers, text, lists, tuples
from unittest.mock import patch

from memory import SemanticMemory


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

SECONDS_PER_DAY = 86400.0
GRACE_PERIOD_DAYS = 7
DECAY_RATE = 0.001
REMOVAL_THRESHOLD = 0.15


def _create_memory_with_idle_fact(key: str, confidence: float, idle_days: float) -> SemanticMemory:
    """Create a SemanticMemory with a fact that has been idle for the given number of days."""
    mem = SemanticMemory()
    mem.learn(key, f"value_for_{key}", confidence=confidence)
    # Backdate the last_accessed time to simulate idle days
    item = mem.facts[key]
    item.last_accessed = time.time() - (idle_days * SECONDS_PER_DAY)
    return mem


# ------------------------------------------------------------------
# Property 19: Semantic Memory Decay and Forgetting
# ------------------------------------------------------------------


class TestSemanticMemoryDecayAndForgetting:
    """Property 19: For any semantic fact not accessed for more than 7 days,
    confidence SHALL decrease at 0.001 per idle day beyond the grace period.
    When confidence drops below 0.15, the fact SHALL be removed. Accessing a
    fact via know() SHALL reset its idle timer.
    """

    @given(
        idle_days=floats(min_value=7.01, max_value=500.0, allow_nan=False, allow_infinity=False),
        initial_confidence=floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_confidence_decreases_by_rate_per_idle_day_beyond_grace(
        self, idle_days: float, initial_confidence: float
    ):
        """Facts idle > 7 days SHALL have confidence decreased at 0.001 per excess day."""
        excess_days = idle_days - GRACE_PERIOD_DAYS
        expected_confidence = initial_confidence - DECAY_RATE * excess_days

        # Only test decay amount for facts that remain above removal threshold
        # (removal is tested separately)
        assume(expected_confidence >= REMOVAL_THRESHOLD + 0.01)

        mem = _create_memory_with_idle_fact("test_fact", initial_confidence, idle_days)

        mem.decay(rate=DECAY_RATE)

        item = mem.facts.get("test_fact")
        assert item is not None, "Fact should still exist above removal threshold"

        actual_confidence = item.content["confidence"]

        # Allow small floating point tolerance due to time passage between setup and decay
        assert abs(actual_confidence - expected_confidence) < 0.002, (
            f"Expected confidence≈{expected_confidence:.6f}, got {actual_confidence:.6f} "
            f"(idle_days={idle_days:.2f}, excess={excess_days:.2f})"
        )

    @given(
        idle_days=floats(min_value=0.0, max_value=6.99, allow_nan=False, allow_infinity=False),
        initial_confidence=floats(min_value=0.2, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_no_decay_within_grace_period(self, idle_days: float, initial_confidence: float):
        """Facts idle <= 7 days SHALL NOT have their confidence reduced."""
        mem = _create_memory_with_idle_fact("test_fact", initial_confidence, idle_days)

        mem.decay(rate=DECAY_RATE)

        item = mem.facts.get("test_fact")
        assert item is not None, "Fact should still exist within grace period"
        actual_confidence = item.content["confidence"]
        assert actual_confidence == initial_confidence, (
            f"Confidence should remain unchanged within grace period. "
            f"Expected {initial_confidence}, got {actual_confidence}"
        )

    @given(
        idle_days=floats(min_value=7.01, max_value=5000.0, allow_nan=False, allow_infinity=False),
        initial_confidence=floats(min_value=0.15, max_value=0.30, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_fact_removed_when_confidence_drops_below_threshold(
        self, idle_days: float, initial_confidence: float
    ):
        """When confidence drops below 0.15, the fact SHALL be removed."""
        excess_days = idle_days - GRACE_PERIOD_DAYS
        new_confidence = initial_confidence - DECAY_RATE * excess_days

        # Only test cases where confidence actually drops below threshold
        assume(new_confidence < REMOVAL_THRESHOLD)

        mem = _create_memory_with_idle_fact("doomed_fact", initial_confidence, idle_days)

        mem.decay(rate=DECAY_RATE)

        assert "doomed_fact" not in mem.facts, (
            f"Fact should be removed when confidence ({new_confidence:.6f}) < {REMOVAL_THRESHOLD}. "
            f"idle_days={idle_days:.2f}, initial_conf={initial_confidence:.4f}"
        )

    @given(
        idle_days=floats(min_value=7.01, max_value=500.0, allow_nan=False, allow_infinity=False),
        initial_confidence=floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_know_resets_idle_timer_preventing_decay(
        self, idle_days: float, initial_confidence: float
    ):
        """Accessing a fact via know() SHALL reset its idle timer."""
        mem = _create_memory_with_idle_fact("accessed_fact", initial_confidence, idle_days)

        # Access the fact — this should reset the idle timer
        result = mem.know("accessed_fact")
        assert result == "value_for_accessed_fact"

        # Now decay should not reduce confidence (idle timer was just reset)
        mem.decay(rate=DECAY_RATE)

        item = mem.facts.get("accessed_fact")
        assert item is not None, "Accessed fact should not be removed"
        actual_confidence = item.content["confidence"]
        assert actual_confidence == initial_confidence, (
            f"Confidence should remain unchanged after know() reset idle timer. "
            f"Expected {initial_confidence}, got {actual_confidence}"
        )
