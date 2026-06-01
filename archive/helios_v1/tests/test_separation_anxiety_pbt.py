"""Property-based tests for SeparationAnxietySource formula.

# Feature: helios-architecture-enhancement, Property 8: Separation Anxiety Formula

**Validates: Requirements 10.2**
"""

import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import floats

from core.helios_state import HeliosState
from core.separation_source import SeparationAnxietySource


ANXIETY_THRESHOLD = 0.2
THRESHOLD_HOURS = -math.log(1.0 - ANXIETY_THRESHOLD) / 0.4
ABOVE_THRESHOLD_HOURS = THRESHOLD_HOURS + 1e-9


# ------------------------------------------------------------------
# Property 8: Separation Anxiety Formula
# ------------------------------------------------------------------


class TestSeparationAnxietyFormula:
    """Property 8: For any separation_hours value, the SeparationAnxietySource
    SHALL return PANIC = min(1.0, 1 - e^(-0.4 × hours)) when that value exceeds
    0.2, and return no triggers otherwise.
    """

    @given(hours=floats(min_value=ABOVE_THRESHOLD_HOURS, max_value=1000.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_panic_formula_when_anxiety_exceeds_threshold(self, hours: float):
        """When computed anxiety > 0.2, PANIC equals min(1.0, 1 - e^(-0.4 * hours))."""
        expected_anxiety = min(1.0, 1 - math.exp(-0.4 * hours))

        source = SeparationAnxietySource()
        state = HeliosState(separation_hours=hours)
        result = source.poll(state)

        assert "PANIC" in result
        assert math.isclose(result["PANIC"], expected_anxiety, rel_tol=1e-9)

    @given(hours=floats(min_value=0.0, max_value=THRESHOLD_HOURS, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_no_triggers_when_anxiety_at_or_below_threshold(self, hours: float):
        """When computed anxiety <= 0.2, no triggers are returned."""
        expected_anxiety = min(1.0, 1 - math.exp(-0.4 * hours))

        source = SeparationAnxietySource()
        state = HeliosState(separation_hours=hours)
        result = source.poll(state)

        assert result == {}

    @given(hours=floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_panic_value_never_exceeds_one(self, hours: float):
        """The PANIC value shall never exceed 1.0 regardless of separation hours."""
        source = SeparationAnxietySource()
        state = HeliosState(separation_hours=hours)
        result = source.poll(state)

        if "PANIC" in result:
            assert result["PANIC"] <= 1.0

    @given(hours=floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_get_messages_always_empty(self, hours: float):
        """SeparationAnxietySource never produces messages."""
        source = SeparationAnxietySource()
        assert source.get_messages() == []
