"""Property-based tests for Phi integration.

# Feature: helios-architecture-enhancement
# Property 9: Phi Ignition from Active System Count
# Property 10: Phi Dynamic Range

**Validates: Requirements 4.4, 15.1, 15.2, 15.3, 15.4**
"""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    floats,
    dictionaries,
    fixed_dictionaries,
    just,
    sampled_from,
    lists,
    integers,
)

from cognition import AdaptiveAlphaICRI, CognitiveImpactProfile, UnifiedPhi

# All 7 Panksepp systems
PANKSEPP_SYSTEMS = ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]


def panksepp_vector(min_value=0.0, max_value=1.0):
    """Strategy: generate a full Panksepp activation vector."""
    return fixed_dictionaries(
        {s: floats(min_value=min_value, max_value=max_value) for s in PANKSEPP_SYSTEMS}
    )


# ------------------------------------------------------------------
# Property 9: Phi Ignition from Active System Count
#
# For any Panksepp activation vector, the ignition source value fed to
# Phi SHALL be derived from the count of systems exceeding baseline
# threshold. More active systems above baseline means higher ignition
# intensity.
# ------------------------------------------------------------------


class TestPhiIgnitionFromActiveSystemCount:
    """Property 9: Ignition intensity is derived from active system count."""

    @given(activation=panksepp_vector())
    @settings(max_examples=200)
    def test_ignition_equals_sqrt_of_active_ratio(self, activation: dict):
        """Ignition = sqrt(active_count / total_systems), clamped to [0,1]."""
        phi = UnifiedPhi()
        baseline = 0.15

        phi.feed_ignition_from_panksepp(activation, baseline=baseline)

        total_systems = len(activation)
        active_count = sum(1 for v in activation.values() if v > baseline)
        expected_ratio = active_count / max(total_systems, 1)
        expected_intensity = math.sqrt(expected_ratio)
        expected = max(0.0, min(1.0, expected_intensity))

        assert abs(phi.global_ignition - expected) < 1e-9, (
            f"With {active_count}/{total_systems} active systems, "
            f"expected ignition={expected:.6f} but got {phi.global_ignition:.6f}"
        )

    @given(
        low_count=integers(min_value=0, max_value=2),
        high_count=integers(min_value=4, max_value=7),
    )
    @settings(max_examples=100)
    def test_more_active_systems_means_higher_ignition(
        self, low_count: int, high_count: int
    ):
        """More systems above baseline produces higher ignition intensity."""
        assume(high_count > low_count)

        baseline = 0.15

        # Build vector with exactly low_count systems above baseline
        low_activation = {}
        for i, s in enumerate(PANKSEPP_SYSTEMS):
            if i < low_count:
                low_activation[s] = 0.5  # Above baseline
            else:
                low_activation[s] = 0.05  # Below baseline

        # Build vector with exactly high_count systems above baseline
        high_activation = {}
        for i, s in enumerate(PANKSEPP_SYSTEMS):
            if i < high_count:
                high_activation[s] = 0.5  # Above baseline
            else:
                high_activation[s] = 0.05  # Below baseline

        phi_low = UnifiedPhi()
        phi_high = UnifiedPhi()

        phi_low.feed_ignition_from_panksepp(low_activation, baseline=baseline)
        phi_high.feed_ignition_from_panksepp(high_activation, baseline=baseline)

        assert phi_high.global_ignition > phi_low.global_ignition, (
            f"With {high_count} active systems, ignition ({phi_high.global_ignition:.4f}) "
            f"should exceed {low_count} active systems ({phi_low.global_ignition:.4f})"
        )

    @given(activation=panksepp_vector(max_value=0.14))
    @settings(max_examples=100)
    def test_all_below_baseline_gives_zero_ignition(self, activation: dict):
        """When all systems are below baseline, ignition is zero."""
        phi = UnifiedPhi()
        phi.feed_ignition_from_panksepp(activation, baseline=0.15)

        assert phi.global_ignition == 0.0, (
            f"With all systems below baseline, ignition should be 0.0 "
            f"but got {phi.global_ignition:.6f}"
        )

    @given(activation=panksepp_vector(min_value=0.16, max_value=1.0))
    @settings(max_examples=100)
    def test_all_above_baseline_gives_maximum_ignition(self, activation: dict):
        """When all systems exceed baseline, ignition is sqrt(1.0) = 1.0."""
        phi = UnifiedPhi()
        phi.feed_ignition_from_panksepp(activation, baseline=0.15)

        assert abs(phi.global_ignition - 1.0) < 1e-9, (
            f"With all 7 systems above baseline, ignition should be 1.0 "
            f"but got {phi.global_ignition:.6f}"
        )

    def test_empty_activation_gives_zero_ignition(self):
        """Empty activation dict results in zero ignition."""
        phi = UnifiedPhi()
        phi.feed_ignition_from_panksepp({})

        assert phi.global_ignition == 0.0


# ------------------------------------------------------------------
# Property 10: Phi Dynamic Range
#
# For any complete set of all 5 Phi sources at high values (all > 0.7),
# the aggregate SHALL exceed 0.7. For any single active source with
# others at 0, the aggregate SHALL be below 0.4. The scaling function
# SHALL maintain meaningful differentiation at high input values
# (non-saturating).
# ------------------------------------------------------------------


class TestPhiDynamicRange:
    """Property 10: Phi has proper dynamic range with non-saturating scaling."""

    @given(
        sensory=floats(min_value=0.71, max_value=1.0),
        emotional=floats(min_value=0.71, max_value=1.0),
        temporal=floats(min_value=0.71, max_value=1.0),
        self_refl=floats(min_value=0.71, max_value=1.0),
        ignition=floats(min_value=0.71, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_all_five_sources_high_aggregate_exceeds_0_7(
        self,
        sensory: float,
        emotional: float,
        temporal: float,
        self_refl: float,
        ignition: float,
    ):
        """When all 5 sources are persistently > 0.7, steady-state aggregate exceeds 0.7.

        The aggregate uses EMA smoothing (alpha=0.25), so we run enough
        cycles for convergence to steady-state (20 cycles gives >99.7% convergence).
        """
        phi = UnifiedPhi()

        # Run multiple aggregate cycles with constant high sources to reach steady state
        for _ in range(30):
            phi.sensory_integration = sensory
            phi._sources_valid["sensory_integration"] = phi.source_ttl
            phi.emotional_coherence = emotional
            phi._sources_valid["emotional_coherence"] = phi.source_ttl
            phi.temporal_depth = temporal
            phi._sources_valid["temporal_depth"] = phi.source_ttl
            phi.self_reflection = self_refl
            phi._sources_valid["self_reflection"] = phi.source_ttl
            phi.global_ignition = ignition
            phi._sources_valid["global_ignition"] = phi.source_ttl

            result = phi.aggregate()

        assert result > 0.7, (
            f"With all 5 sources > 0.7 (si={sensory:.3f}, ec={emotional:.3f}, "
            f"td={temporal:.3f}, sr={self_refl:.3f}, gi={ignition:.3f}), "
            f"steady-state aggregate should exceed 0.7 but got {result:.4f}"
        )

    @given(
        active_source=sampled_from([
            "sensory_integration",
            "emotional_coherence",
            "temporal_depth",
            "self_reflection",
            "global_ignition",
        ]),
        value=floats(min_value=0.1, max_value=1.0),
    )
    @settings(max_examples=200)
    def test_single_source_active_aggregate_below_0_4(
        self, active_source: str, value: float
    ):
        """When only 1 source is active with others at 0, steady-state aggregate < 0.4.

        Run multiple cycles to allow EMA to converge to steady state.
        """
        phi = UnifiedPhi()

        # Run multiple aggregate cycles for convergence
        for _ in range(30):
            # Set only the active source
            setattr(phi, active_source, value)
            phi._sources_valid[active_source] = phi.source_ttl

            # All other sources remain at 0 with invalid TTL
            for key in phi._sources_valid:
                if key != active_source:
                    setattr(phi, key, 0.0)
                    phi._sources_valid[key] = 0.0

            result = phi.aggregate()

        assert result < 0.4, (
            f"With only {active_source}={value:.3f} active, "
            f"steady-state aggregate should be below 0.4 but got {result:.4f}"
        )

    @given(
        raw_low=floats(min_value=0.5, max_value=0.7),
        raw_high=floats(min_value=0.71, max_value=0.95),
    )
    @settings(max_examples=200)
    def test_nonlinear_scale_maintains_differentiation(
        self, raw_low: float, raw_high: float
    ):
        """
        The scaling function maintains meaningful differentiation at high
        values (non-saturating). tanh(x*1.6) for different high inputs
        must produce distinguishable outputs.
        """
        assume(raw_high > raw_low)
        assume(raw_high - raw_low > 0.05)

        scaled_low = UnifiedPhi._nonlinear_scale(raw_low)
        scaled_high = UnifiedPhi._nonlinear_scale(raw_high)

        # Monotonicity: higher input → higher output
        assert scaled_high > scaled_low, (
            f"scale({raw_high:.4f})={scaled_high:.4f} should exceed "
            f"scale({raw_low:.4f})={scaled_low:.4f}"
        )

        # Non-saturation: the difference should be meaningful (> 1% of input diff)
        input_diff = raw_high - raw_low
        output_diff = scaled_high - scaled_low
        assert output_diff > input_diff * 0.01, (
            f"Output difference ({output_diff:.6f}) is too small relative to "
            f"input difference ({input_diff:.6f}) — scaling is saturating"
        )

    @given(raw=floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=100)
    def test_nonlinear_scale_maps_unit_interval_to_unit_interval(self, raw: float):
        """The scaling function maps [0, 1] → [0, 1]."""
        result = UnifiedPhi._nonlinear_scale(raw)

        assert 0.0 <= result <= 1.0, (
            f"_nonlinear_scale({raw:.4f}) = {result:.4f} is outside [0, 1]"
        )

    @given(raw=floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=100)
    def test_nonlinear_scale_is_tanh_based(self, raw: float):
        """The scaling function is exactly tanh(raw * 1.6)."""
        result = UnifiedPhi._nonlinear_scale(raw)
        expected = math.tanh(raw * 1.6)

        assert abs(result - expected) < 1e-12, (
            f"_nonlinear_scale({raw:.4f}) = {result:.10f} "
            f"but expected tanh({raw:.4f} * 1.6) = {expected:.10f}"
        )


class TestAdaptiveAlphaTierSelection:
    """Property 28: Adaptive alpha tier selection follows the spec ranges."""

    @given(intensity=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_select_alpha_uses_expected_tiers(self, intensity: float):
        engine = AdaptiveAlphaICRI()

        alpha = engine.select_alpha(intensity)

        if intensity > 0.60:
            expected = 0.55
        elif intensity >= 0.30:
            expected = 0.30
        else:
            expected = 0.10

        assert alpha == expected, (
            f"select_alpha({intensity:.4f}) returned {alpha}, expected {expected}"
        )

    def test_strong_event_raises_phi_by_at_least_point_one(self):
        engine = AdaptiveAlphaICRI()

        baseline = engine.aggregate(max_event_intensity=0.0)

        engine.sensory_integration = 0.9
        engine._sources_valid["sensory_integration"] = engine.source_ttl
        engine.emotional_coherence = 0.8
        engine._sources_valid["emotional_coherence"] = engine.source_ttl
        engine.global_ignition = 1.0
        engine._sources_valid["global_ignition"] = engine.source_ttl

        elevated = engine.aggregate(max_event_intensity=1.0)

        assert engine.last_selected_alpha == 0.55
        assert elevated - baseline >= 0.10, (
            f"Expected strong event to raise aggregate by at least 0.10, "
            f"but got baseline={baseline:.4f}, elevated={elevated:.4f}"
        )


class TestCognitiveImpactProfileFeeding:
    """Property 30: CognitiveImpactProfile feeds the expected ICRI sources."""

    @given(
        sensory=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        cognitive=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        self_refl=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        novelty=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_feed_from_impact_maps_dimensions_to_sources(
        self,
        sensory: float,
        cognitive: float,
        self_refl: float,
        novelty: float,
    ):
        engine = AdaptiveAlphaICRI()
        impact = CognitiveImpactProfile(
            sensory=sensory,
            cognitive=cognitive,
            self_=self_refl,
            novelty=novelty,
        )

        engine.feed_from_impact(impact)

        assert abs(engine.sensory_integration - sensory) < 1e-9
        assert abs(engine.dmn_depth - cognitive) < 1e-9
        assert abs(engine.self_reflection - self_refl) < 1e-9
        assert abs(engine.global_ignition - novelty) < 1e-9
        assert engine._sources_valid["sensory_integration"] == engine.source_ttl
        assert engine._sources_valid["temporal_depth"] == engine.source_ttl
        assert engine._sources_valid["self_reflection"] == engine.source_ttl
        assert engine._sources_valid["global_ignition"] == engine.source_ttl

    def test_feed_from_impact_none_preserves_existing_sources(self):
        engine = AdaptiveAlphaICRI()
        engine.sensory_integration = 0.4
        engine.temporal_depth = 0.2
        engine.self_reflection = 0.6
        engine.global_ignition = 0.5

        before = (
            engine.sensory_integration,
            engine.temporal_depth,
            engine.self_reflection,
            engine.global_ignition,
        )

        engine.feed_from_impact(None)

        after = (
            engine.sensory_integration,
            engine.temporal_depth,
            engine.self_reflection,
            engine.global_ignition,
        )
        assert after == before
