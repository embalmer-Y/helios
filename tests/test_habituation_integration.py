"""
Tests for HabituationTracker integration into the event processing pipeline.

Validates Requirements 14.1, 14.2, 14.3:
- Event triggers pass through HabituationTracker before DAISY
- Novelty factor multiplies trigger intensity
- Recovery of novelty after stimulus gap
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from habituation import HabituationTracker


class TestHabituationIntegration:
    """Test habituation modulation of event triggers."""

    def test_first_exposure_full_intensity(self):
        """First time seeing an event → novelty = 1.0, no attenuation."""
        tracker = HabituationTracker()
        novelty = tracker.get_novelty_factor("SEEKING", cycle=1)
        assert novelty == 1.0

    def test_repeated_exposure_reduces_intensity(self):
        """Repeated exposure → novelty factor decreases below 1.0."""
        tracker = HabituationTracker()
        # Register several exposures
        for cycle in range(1, 11):
            tracker.register_exposure("PANIC", cycle)

        novelty = tracker.get_novelty_factor("PANIC", cycle=11)
        assert novelty < 1.0, "Novelty should decrease after repeated exposure"

    def test_novelty_modulates_trigger_intensity(self):
        """Trigger intensity × novelty_factor < original intensity after exposures."""
        tracker = HabituationTracker()
        raw_intensity = 0.8

        # First time: no modulation
        novelty_first = tracker.get_novelty_factor("FEAR", cycle=1)
        modulated_first = raw_intensity * novelty_first
        assert modulated_first == raw_intensity

        # Register several exposures
        for cycle in range(1, 20):
            tracker.register_exposure("FEAR", cycle)

        # After repeated exposure: modulated intensity should be lower
        novelty_after = tracker.get_novelty_factor("FEAR", cycle=20)
        modulated_after = raw_intensity * novelty_after
        assert modulated_after < raw_intensity

    def test_recovery_after_stimulus_gap(self):
        """After a gap, novelty factor recovers toward 1.0."""
        tracker = HabituationTracker()

        # Build up habituation
        for cycle in range(1, 51):
            tracker.register_exposure("PLAY", cycle)

        # Novelty right after exposures (at cycle 51)
        novelty_habituated = tracker.get_novelty_factor("PLAY", cycle=51)

        # After a large gap (500 cycles later)
        novelty_recovered = tracker.get_novelty_factor("PLAY", cycle=551)

        assert novelty_recovered > novelty_habituated, (
            "Novelty should recover after a stimulus gap"
        )

    def test_different_keys_independent(self):
        """Habituation is tracked independently per event key."""
        tracker = HabituationTracker()

        # Habituate to SEEKING only
        for cycle in range(1, 30):
            tracker.register_exposure("SEEKING", cycle)

        # SEEKING should be habituated
        novelty_seeking = tracker.get_novelty_factor("SEEKING", cycle=30)
        # CARE never seen → full novelty
        novelty_care = tracker.get_novelty_factor("CARE", cycle=30)

        assert novelty_care == 1.0
        assert novelty_seeking < 1.0

    def test_register_exposure_increments_count(self):
        """register_exposure increases the exposure count for that key."""
        tracker = HabituationTracker()
        assert tracker.exposure_count["TEST"] == 0

        tracker.register_exposure("TEST", cycle=1)
        assert tracker.exposure_count["TEST"] == 1

        tracker.register_exposure("TEST", cycle=2)
        assert tracker.exposure_count["TEST"] == 2

    def test_pipeline_integration_pattern(self):
        """
        Simulate the exact pattern used in _tick():
        for each trigger key, get novelty, multiply, register.
        """
        tracker = HabituationTracker()
        tick = 1

        # Simulate 5 ticks of the same event
        for tick in range(1, 6):
            events = {"SEEKING": 0.7, "PLAY": 0.5}
            for key, intensity in list(events.items()):
                novelty = tracker.get_novelty_factor(key, tick)
                events[key] = intensity * novelty
                if intensity > 0.01:
                    tracker.register_exposure(key, tick)

        # By tick 5, the intensities should be reduced
        events_tick5 = {"SEEKING": 0.7, "PLAY": 0.5}
        for key, intensity in list(events_tick5.items()):
            novelty = tracker.get_novelty_factor(key, cycle=6)
            events_tick5[key] = intensity * novelty

        assert events_tick5["SEEKING"] < 0.7
        assert events_tick5["PLAY"] < 0.5

    def test_novelty_never_below_minimum(self):
        """Novelty factor should never go below 0.05 (minimum floor)."""
        tracker = HabituationTracker()

        # Massive repeated exposure
        for cycle in range(1, 1001):
            tracker.register_exposure("RAGE", cycle)

        novelty = tracker.get_novelty_factor("RAGE", cycle=1001)
        assert novelty >= 0.05, "Novelty should have a minimum floor"
