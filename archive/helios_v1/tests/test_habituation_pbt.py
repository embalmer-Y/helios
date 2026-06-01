"""
Property-based tests for HabituationTracker modulation.

# Feature: helios-architecture-enhancement, Property 13: Habituation Modulates Trigger Intensity

**Validates: Requirements 14.1, 14.2, 14.3**
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import integers, floats, text, composite

from habituation import HabituationTracker


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


@composite
def event_key(draw):
    """Generate a valid event key string."""
    # Use simple alphanumeric keys to avoid edge cases
    return draw(text(min_size=1, max_size=20, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ"))


# ------------------------------------------------------------------
# Property 13: Habituation Modulates Trigger Intensity
# ------------------------------------------------------------------


class TestHabituationModulatesTriggerIntensity:
    """Property 13: For any event trigger with key K that has been received
    N times with gap G cycles since last exposure, the effective intensity
    SHALL equal raw_intensity × novelty_factor(N, G), where novelty_factor
    decreases with N and recovers with G.

    Validates: Requirements 14.1, 14.2, 14.3
    """

    @given(
        raw_intensity=floats(min_value=0.01, max_value=1.0),
        key=event_key(),
    )
    @settings(max_examples=100)
    def test_first_exposure_novelty_is_one(self, raw_intensity: float, key: str):
        """
        Req 14.1: First exposure to an event → novelty factor = 1.0.

        The HabituationTracker SHALL pass triggers through with full intensity
        on first exposure.
        """
        tracker = HabituationTracker()
        novelty = tracker.get_novelty_factor(key, cycle=1)
        assert novelty == 1.0, "First exposure should have novelty = 1.0"

        # Verify effective intensity equals raw intensity
        effective = raw_intensity * novelty
        assert effective == raw_intensity

    @given(
        raw_intensity=floats(min_value=0.01, max_value=1.0),
        key=event_key(),
        n_exposures=integers(min_value=1, max_value=100),
    )
    @settings(max_examples=100)
    def test_novelty_decreases_with_repeated_exposure(
        self, raw_intensity: float, key: str, n_exposures: int
    ):
        """
        Req 14.2: Novelty factor decreases with repeated exposure.

        When HabituationTracker returns a novelty factor below 1.0, the
        effective trigger intensity SHALL be less than raw intensity.
        """
        tracker = HabituationTracker()

        # Register N exposures at consecutive cycles
        for cycle in range(1, n_exposures + 1):
            tracker.register_exposure(key, cycle)

        # Get novelty at next cycle (no gap)
        novelty = tracker.get_novelty_factor(key, cycle=n_exposures + 1)

        # After at least 1 exposure, novelty should be < 1.0
        assert novelty < 1.0, f"Novelty should decrease after {n_exposures} exposures"

        # Verify effective intensity is modulated
        effective = raw_intensity * novelty
        assert effective < raw_intensity, (
            f"Effective intensity ({effective}) should be less than "
            f"raw ({raw_intensity}) after exposures"
        )

    @given(
        raw_intensity=floats(min_value=0.01, max_value=1.0),
        key=event_key(),
        n_exposures=integers(min_value=10, max_value=100),
        gap=integers(min_value=100, max_value=1000),
    )
    @settings(max_examples=100)
    def test_novelty_recovers_after_stimulus_gap(
        self, raw_intensity: float, key: str, n_exposures: int, gap: int
    ):
        """
        Req 14.3: Novelty factor recovers after stimulus gap.

        When a stimulus has not been received for a duration exceeding
        the recovery time, the novelty factor SHALL restore toward 1.0.
        """
        tracker = HabituationTracker()

        # Register N exposures to build up habituation
        for cycle in range(1, n_exposures + 1):
            tracker.register_exposure(key, cycle)

        # Measure novelty immediately after exposures (no gap)
        novelty_habituated = tracker.get_novelty_factor(key, cycle=n_exposures + 1)

        # Measure novelty after a large gap
        novelty_recovered = tracker.get_novelty_factor(
            key, cycle=n_exposures + 1 + gap
        )

        # Novelty should recover (increase) after the gap
        assert novelty_recovered > novelty_habituated, (
            f"Novelty should recover after gap of {gap} cycles "
            f"(habituated={novelty_habituated}, recovered={novelty_recovered})"
        )

        # Verify effective intensity also recovers
        effective_habituated = raw_intensity * novelty_habituated
        effective_recovered = raw_intensity * novelty_recovered
        assert effective_recovered > effective_habituated

    @given(
        raw_intensity=floats(min_value=0.5, max_value=1.0),
        key=event_key(),
        n1=integers(min_value=1, max_value=20),
        n2=integers(min_value=21, max_value=50),
    )
    @settings(max_examples=50)
    def test_more_exposures_means_lower_novelty(
        self, raw_intensity: float, key: str, n1: int, n2: int
    ):
        """
        Additional property: More exposures → lower novelty factor.

        If N2 > N1 exposures, then novelty(N2) < novelty(N1).
        """
        assume(n2 > n1)

        tracker1 = HabituationTracker()
        tracker2 = HabituationTracker()

        # Tracker1: N1 exposures
        for cycle in range(1, n1 + 1):
            tracker1.register_exposure(key, cycle)

        # Tracker2: N2 exposures
        for cycle in range(1, n2 + 1):
            tracker2.register_exposure(key, cycle)

        novelty1 = tracker1.get_novelty_factor(key, cycle=n1 + 1)
        novelty2 = tracker2.get_novelty_factor(key, cycle=n2 + 1)

        assert novelty2 < novelty1, (
            f"More exposures ({n2}) should result in lower novelty "
            f"than fewer exposures ({n1})"
        )

    @given(
        raw_intensity=floats(min_value=0.01, max_value=1.0),
        key=event_key(),
        n_exposures=integers(min_value=1, max_value=500),
    )
    @settings(max_examples=100)
    def test_novelty_never_below_minimum_floor(
        self, raw_intensity: float, key: str, n_exposures: int
    ):
        """
        Invariant: Novelty factor has a minimum floor (0.05).

        No matter how many exposures, novelty never drops below the floor.
        """
        tracker = HabituationTracker()

        # Register many exposures
        for cycle in range(1, n_exposures + 1):
            tracker.register_exposure(key, cycle)

        novelty = tracker.get_novelty_factor(key, cycle=n_exposures + 1)
        assert novelty >= 0.05, "Novelty should have a minimum floor of 0.05"

        # Effective intensity should still be proportional
        effective = raw_intensity * novelty
        assert effective >= raw_intensity * 0.05

    @given(
        key1=event_key(),
        key2=event_key(),
    )
    @settings(max_examples=50)
    def test_different_keys_habituate_independently(self, key1: str, key2: str):
        """
        Invariant: Habituation is tracked independently per event key.

        Exposing key1 should not affect novelty of key2.
        """
        assume(key1 != key2)

        tracker = HabituationTracker()

        # Heavily expose key1
        for cycle in range(1, 100):
            tracker.register_exposure(key1, cycle)

        # key1 should be habituated
        novelty1 = tracker.get_novelty_factor(key1, cycle=100)
        assert novelty1 < 1.0

        # key2 should still have full novelty (never exposed)
        novelty2 = tracker.get_novelty_factor(key2, cycle=100)
        assert novelty2 == 1.0, "Unexposed key should have full novelty"

    @given(
        raw_intensity=floats(min_value=0.1, max_value=1.0),
        key=event_key(),
        exposures=integers(min_value=5, max_value=30),
        gap=integers(min_value=200, max_value=500),
    )
    @settings(max_examples=50)
    def test_larger_gap_means_more_recovery(
        self, raw_intensity: float, key: str, exposures: int, gap: int
    ):
        """
        Additional property: Larger gap → more recovery.

        If gap2 > gap1, then novelty after gap2 should be higher than
        novelty after gap1 (all else equal).
        """
        tracker = HabituationTracker()

        # Build up habituation
        for cycle in range(1, exposures + 1):
            tracker.register_exposure(key, cycle)

        # Measure novelty at two different gap sizes
        novelty_small_gap = tracker.get_novelty_factor(key, cycle=exposures + 1 + 50)
        novelty_large_gap = tracker.get_novelty_factor(key, cycle=exposures + 1 + gap)

        assert novelty_large_gap > novelty_small_gap, (
            f"Gap of {gap} should result in more recovery than gap of 50"
        )
