"""Property-based tests for significant event recording threshold.

# Feature: helios-architecture-enhancement, Property 12: Significant Event Recording Threshold

**Validates: Requirements 13.2**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import floats, text, dictionaries

from memory import MemorySystem
from helios_main import Helios


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


class FakeHelios:
    """Minimal stand-in with just the memory system for testing."""

    def __init__(self):
        self.memory_system = MemorySystem()


def _call_record(phi: float, valence: float, arousal: float = 0.3):
    """Call _record_significant_event on a fresh FakeHelios and return (instance, was_recorded)."""
    fake = FakeHelios()
    method = Helios._record_significant_event.__get__(fake, FakeHelios)
    method(phi=phi, valence=valence, arousal=arousal, dominant="SEEKING", events={"SEEKING": 0.4})
    was_recorded = len(fake.memory_system.episodic.items) > 0
    return fake, was_recorded


# ------------------------------------------------------------------
# Property 12: Significant Event Recording Threshold
# ------------------------------------------------------------------


class TestSignificantEventRecordingThreshold:
    """Property 12: For any tick state with phi > 0.3 OR |valence| > 0.5,
    the event SHALL be recorded to EpisodicMemory. For states where
    phi <= 0.3 AND |valence| <= 0.5, no recording SHALL occur.
    """

    @given(
        phi=floats(min_value=0.300001, max_value=1.0, allow_nan=False, allow_infinity=False),
        valence=floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        arousal=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_records_when_phi_above_threshold(self, phi: float, valence: float, arousal: float):
        """When phi > 0.3, the event SHALL be recorded regardless of valence."""
        _, was_recorded = _call_record(phi=phi, valence=valence, arousal=arousal)
        assert was_recorded, (
            f"Event should be recorded when phi={phi:.6f} > 0.3 "
            f"(valence={valence:.6f})"
        )

    @given(
        phi=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        valence=floats(min_value=0.500001, max_value=1.0, allow_nan=False, allow_infinity=False),
        arousal=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_records_when_positive_valence_above_threshold(self, phi: float, valence: float, arousal: float):
        """When valence > 0.5, the event SHALL be recorded regardless of phi."""
        _, was_recorded = _call_record(phi=phi, valence=valence, arousal=arousal)
        assert was_recorded, (
            f"Event should be recorded when valence={valence:.6f} > 0.5 "
            f"(phi={phi:.6f})"
        )

    @given(
        phi=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        valence=floats(min_value=-1.0, max_value=-0.500001, allow_nan=False, allow_infinity=False),
        arousal=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_records_when_negative_valence_above_threshold(self, phi: float, valence: float, arousal: float):
        """When |valence| > 0.5 (negative), the event SHALL be recorded."""
        _, was_recorded = _call_record(phi=phi, valence=valence, arousal=arousal)
        assert was_recorded, (
            f"Event should be recorded when valence={valence:.6f} (|valence| > 0.5) "
            f"(phi={phi:.6f})"
        )

    @given(
        phi=floats(min_value=0.0, max_value=0.3, allow_nan=False, allow_infinity=False),
        valence=floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
        arousal=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_no_recording_when_both_below_threshold(self, phi: float, valence: float, arousal: float):
        """When phi <= 0.3 AND |valence| <= 0.5, no recording SHALL occur."""
        _, was_recorded = _call_record(phi=phi, valence=valence, arousal=arousal)
        assert not was_recorded, (
            f"No recording should occur when phi={phi:.6f} <= 0.3 "
            f"AND |valence|={abs(valence):.6f} <= 0.5"
        )
