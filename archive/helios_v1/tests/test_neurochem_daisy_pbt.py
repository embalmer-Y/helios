"""Property-based tests for Neurochem-DAISY modulation.

# Feature: helios-architecture-enhancement
# Property 1: Neurochem Dopamine Modulates SEEKING Decay
# Property 2: Neurochem Cortisol Amplifies FEAR

**Validates: Requirements 1.3, 1.4**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import floats

from daisy_emotion import DaisySystemEngine, CHRONOMETRY, BASELINE
from neurochem import NeurochemState


# ------------------------------------------------------------------
# Property 1: Neurochem Dopamine Modulates SEEKING Decay
#
# For any NeurochemState where dopamine > 0.5, when DAISY runs a cycle,
# the SEEKING system's effective decay rate SHALL be reduced proportionally
# to (dopamine - 0.5). Higher dopamine means slower SEEKING decay.
# ------------------------------------------------------------------


class TestDopamineModulatesSeekingDecay:
    """Property 1: Dopamine > 0.5 reduces SEEKING decay rate proportionally."""

    @given(dopamine=floats(min_value=0.51, max_value=1.0))
    @settings(max_examples=100)
    def test_high_dopamine_increases_seeking_inertia(self, dopamine: float):
        """When dopamine > 0.5, SEEKING inertia is boosted above baseline."""
        nc = NeurochemState()
        nc.dopamine.current = dopamine

        engine = DaisySystemEngine()
        engine.cycle(None, neurochem=nc)

        original_inertia = CHRONOMETRY["SEEKING"][3]
        actual_inertia = engine.systems["SEEKING"].inertia

        # Inertia should be boosted above the original baseline
        assert actual_inertia > original_inertia, (
            f"With dopamine={dopamine:.4f}, inertia {actual_inertia:.4f} "
            f"should exceed baseline {original_inertia:.4f}"
        )

    @given(dopamine=floats(min_value=0.51, max_value=1.0))
    @settings(max_examples=100)
    def test_inertia_boost_proportional_to_dopamine_excess(self, dopamine: float):
        """The inertia boost equals (dopamine - 0.5) * (1 - original_inertia)."""
        nc = NeurochemState()
        nc.dopamine.current = dopamine

        engine = DaisySystemEngine()
        engine.cycle(None, neurochem=nc)

        original_inertia = CHRONOMETRY["SEEKING"][3]
        excess = dopamine - 0.5
        expected_boost = excess * (1.0 - original_inertia)
        expected_inertia = original_inertia + expected_boost

        actual_inertia = engine.systems["SEEKING"].inertia
        assert abs(actual_inertia - expected_inertia) < 1e-9, (
            f"With dopamine={dopamine:.4f}, expected inertia={expected_inertia:.6f} "
            f"but got {actual_inertia:.6f}"
        )

    @given(
        da_low=floats(min_value=0.51, max_value=0.74),
        da_high=floats(min_value=0.76, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_higher_dopamine_means_slower_decay(self, da_low: float, da_high: float):
        """Higher dopamine produces higher inertia (slower decay)."""
        assume(da_high > da_low)

        nc_low = NeurochemState()
        nc_low.dopamine.current = da_low

        nc_high = NeurochemState()
        nc_high.dopamine.current = da_high

        engine_low = DaisySystemEngine()
        engine_high = DaisySystemEngine()

        # Trigger SEEKING, then let it decay
        engine_low.cycle({"SEEKING": 0.7}, neurochem=nc_low)
        engine_high.cycle({"SEEKING": 0.7}, neurochem=nc_high)

        # Run enough decay cycles to pass the peak period (τ_peak = 4.0)
        for _ in range(7):
            state_low = engine_low.cycle(None, neurochem=nc_low)
            state_high = engine_high.cycle(None, neurochem=nc_high)

        # Higher dopamine should retain more SEEKING activation
        seeking_low = state_low.panksepp_activation["SEEKING"]
        seeking_high = state_high.panksepp_activation["SEEKING"]

        assert seeking_high >= seeking_low, (
            f"Higher dopamine ({da_high:.4f}) should retain more SEEKING "
            f"({seeking_high:.4f}) than lower ({da_low:.4f}) → ({seeking_low:.4f})"
        )

    @given(dopamine=floats(min_value=0.0, max_value=0.5))
    @settings(max_examples=100)
    def test_dopamine_at_or_below_threshold_no_boost(self, dopamine: float):
        """When dopamine <= 0.5, inertia stays at baseline (no modulation)."""
        nc = NeurochemState()
        nc.dopamine.current = dopamine

        engine = DaisySystemEngine()
        engine.cycle(None, neurochem=nc)

        original_inertia = CHRONOMETRY["SEEKING"][3]
        actual_inertia = engine.systems["SEEKING"].inertia

        assert abs(actual_inertia - original_inertia) < 1e-9, (
            f"With dopamine={dopamine:.4f} (<= 0.5), inertia should remain "
            f"at baseline {original_inertia:.4f} but got {actual_inertia:.4f}"
        )


# ------------------------------------------------------------------
# Property 2: Neurochem Cortisol Amplifies FEAR
#
# For any NeurochemState where cortisol > 0.5, when DAISY runs a cycle,
# the FEAR system's activation SHALL be increased proportionally to
# (cortisol - 0.5). Higher cortisol means higher FEAR.
# ------------------------------------------------------------------


class TestCortisolAmplifiesFear:
    """Property 2: Cortisol > 0.5 increases FEAR activation proportionally."""

    @given(cortisol=floats(min_value=0.51, max_value=1.0))
    @settings(max_examples=100)
    def test_high_cortisol_increases_fear_above_baseline(self, cortisol: float):
        """When cortisol > 0.5, FEAR activation exceeds the no-neurochem case."""
        nc = NeurochemState()
        nc.cortisol.current = cortisol

        engine_with = DaisySystemEngine()
        engine_without = DaisySystemEngine()

        state_with = engine_with.cycle(None, neurochem=nc)
        state_without = engine_without.cycle(None)

        fear_with = state_with.panksepp_activation["FEAR"]
        fear_without = state_without.panksepp_activation["FEAR"]

        assert fear_with > fear_without, (
            f"With cortisol={cortisol:.4f}, FEAR ({fear_with:.4f}) should "
            f"exceed baseline FEAR ({fear_without:.4f})"
        )

    @given(cortisol=floats(min_value=0.51, max_value=1.0))
    @settings(max_examples=100)
    def test_fear_increase_proportional_to_cortisol_excess(self, cortisol: float):
        """The FEAR increase equals (cortisol - 0.5) * 0.5, capped at 1.0."""
        nc = NeurochemState()
        nc.cortisol.current = cortisol

        engine = DaisySystemEngine()
        # Run cycle — neurochem modulation applies after natural tick
        engine.cycle(None, neurochem=nc)

        excess = cortisol - 0.5
        expected_increase = excess * 0.5
        fear_baseline = BASELINE["FEAR"]
        # The fear activation after one tick (natural evolution) is close to baseline
        # then cortisol adds excess * 0.5
        expected_fear = min(1.0, fear_baseline + expected_increase)

        actual_fear = engine.systems["FEAR"].activation
        assert abs(actual_fear - expected_fear) < 1e-9, (
            f"With cortisol={cortisol:.4f}, expected FEAR={expected_fear:.6f} "
            f"but got {actual_fear:.6f}"
        )

    @given(
        cort_low=floats(min_value=0.51, max_value=0.74),
        cort_high=floats(min_value=0.76, max_value=1.0),
    )
    @settings(max_examples=100)
    def test_higher_cortisol_means_higher_fear(self, cort_low: float, cort_high: float):
        """Higher cortisol produces higher FEAR activation (monotonic)."""
        assume(cort_high > cort_low)

        nc_low = NeurochemState()
        nc_low.cortisol.current = cort_low

        nc_high = NeurochemState()
        nc_high.cortisol.current = cort_high

        engine_low = DaisySystemEngine()
        engine_high = DaisySystemEngine()

        state_low = engine_low.cycle(None, neurochem=nc_low)
        state_high = engine_high.cycle(None, neurochem=nc_high)

        fear_low = state_low.panksepp_activation["FEAR"]
        fear_high = state_high.panksepp_activation["FEAR"]

        assert fear_high > fear_low, (
            f"Higher cortisol ({cort_high:.4f}) should produce more FEAR "
            f"({fear_high:.4f}) than lower ({cort_low:.4f}) → ({fear_low:.4f})"
        )

    @given(cortisol=floats(min_value=0.0, max_value=0.5))
    @settings(max_examples=100)
    def test_cortisol_at_or_below_threshold_no_amplification(self, cortisol: float):
        """When cortisol <= 0.5, no FEAR amplification occurs."""
        nc = NeurochemState()
        nc.cortisol.current = cortisol

        engine_with = DaisySystemEngine()
        engine_without = DaisySystemEngine()

        state_with = engine_with.cycle(None, neurochem=nc)
        state_without = engine_without.cycle(None)

        fear_with = state_with.panksepp_activation["FEAR"]
        fear_without = state_without.panksepp_activation["FEAR"]

        # With cortisol <= 0.5, FEAR should not be amplified
        # (may differ slightly due to generic RAGE cortisol modulation, but not from
        # the specialized FEAR amplification path)
        # The specialized path adds nothing, so FEAR should be <= baseline behavior
        assert abs(fear_with - fear_without) < 0.05, (
            f"With cortisol={cortisol:.4f} (<= 0.5), FEAR should not be "
            f"specifically amplified: with={fear_with:.4f}, without={fear_without:.4f}"
        )
