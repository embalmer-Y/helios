"""T2 tests: MemoryLayerClassifier protocol + AffectOutcomeMemoryLayerClassifier.

Owner: memory affect and replay layer (06).
Validates the 6-row C_engineering_hypothesis decision table, boundary values,
extreme values, and custom threshold/outcome_class configuration.
"""

from __future__ import annotations

import pytest

from helios_v2.memory.contracts import MemoryLayer, VALID_MEMORY_LAYERS
from helios_v2.memory.engine import (
    AffectOutcomeMemoryLayerClassifier,
    MemoryLayerClassifier,
)


# ── Protocol structural checks ──────────────────────────────────────────


class TestMemoryLayerClassifierProtocol:
    """Verify the protocol is runtime-checkable and structural."""

    def test_affect_outcome_classifier_satisfies_protocol(self) -> None:
        """AffectOutcomeMemoryLayerClassifier must satisfy MemoryLayerClassifier."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        assert isinstance(classifier, MemoryLayerClassifier)

    def test_protocol_is_runtime_checkable(self) -> None:
        """MemoryLayerClassifier must be runtime_checkable."""
        # A class that does NOT implement classify_layer should not satisfy the protocol.
        class BadClassifier:
            pass

        assert not isinstance(BadClassifier(), MemoryLayerClassifier)

    def test_custom_classifier_satisfies_protocol(self) -> None:
        """A custom class with classify_layer(affect_intensity, outcome_class) -> MemoryLayer satisfies the protocol."""

        class CustomClassifier:
            def classify_layer(self, affect_intensity: float, outcome_class: str) -> MemoryLayer:
                return "L4_long"

        assert isinstance(CustomClassifier(), MemoryLayerClassifier)


# ── 6-row decision table (C_engineering_hypothesis) ─────────────────────


class TestClassifierDecisionTable:
    """All 6 rows of the affect_intensity/outcome_class → MemoryLayer table."""

    # Row 1: affect_intensity < low + (internal_to_visible_consequence | no_outcome) → L2_working
    @pytest.mark.parametrize("outcome_class", ["internal_to_visible_consequence", "no_outcome"])
    def test_low_affect_low_outcome_yields_L2_working(self, outcome_class: str) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.10, outcome_class)
        assert result == "L2_working"

    # Row 2: affect_intensity < low + any other outcome → L3_short
    @pytest.mark.parametrize(
        "outcome_class",
        ["self_changed", "external_consequence", "mixed_consequence", "unknown_outcome"],
    )
    def test_low_affect_other_outcome_yields_L3_short(self, outcome_class: str) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.10, outcome_class)
        assert result == "L3_short"

    # Row 3: affect_intensity in [low, high) + identity outcome → L4_long
    def test_mid_affect_identity_outcome_yields_L4_long(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.30, "self_changed")
        assert result == "L4_long"

    # Row 4: affect_intensity in [low, high) + non-identity → L3_short
    @pytest.mark.parametrize(
        "outcome_class",
        ["internal_to_visible_consequence", "no_outcome", "external_consequence", "mixed_consequence"],
    )
    def test_mid_affect_non_identity_yields_L3_short(self, outcome_class: str) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.30, outcome_class)
        assert result == "L3_short"

    # Row 5: affect_intensity >= high + identity outcome → L5_autobiographical
    def test_high_affect_identity_outcome_yields_L5_autobiographical(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.70, "self_changed")
        assert result == "L5_autobiographical"

    # Row 6: affect_intensity >= high + non-identity → L4_long
    @pytest.mark.parametrize(
        "outcome_class",
        ["internal_to_visible_consequence", "no_outcome", "external_consequence", "mixed_consequence"],
    )
    def test_high_affect_non_identity_yields_L4_long(self, outcome_class: str) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.70, outcome_class)
        assert result == "L4_long"


# ── Boundary values ─────────────────────────────────────────────────────


class TestClassifierBoundaryValues:
    """Exact boundary values: low_affect_threshold=0.15 and high_affect_threshold=0.50."""

    def test_exact_low_threshold_internal_outcome_is_L3_short(self) -> None:
        """At exactly 0.15, affect_intensity is NOT < 0.15, so it falls into [low, high) band.
        internal_to_visible_consequence is non-identity → L3_short."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.15, "internal_to_visible_consequence")
        assert result == "L3_short"

    def test_exact_low_threshold_identity_outcome_is_L4_long(self) -> None:
        """At exactly 0.15, affect_intensity is NOT < 0.15, falls into [low, high) band.
        self_changed (identity) → L4_long."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.15, "self_changed")
        assert result == "L4_long"

    def test_exact_high_threshold_non_identity_is_L4_long(self) -> None:
        """At exactly 0.50, affect_intensity >= high_threshold.
        non-identity outcome → L4_long."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.50, "external_consequence")
        assert result == "L4_long"

    def test_exact_high_threshold_identity_is_L5_autobiographical(self) -> None:
        """At exactly 0.50, affect_intensity >= high_threshold.
        identity outcome (self_changed) → L5_autobiographical."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.50, "self_changed")
        assert result == "L5_autobiographical"

    def test_just_below_low_threshold_yields_L2_working(self) -> None:
        """0.1499 < 0.15, with no_outcome → L2_working."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.1499, "no_outcome")
        assert result == "L2_working"

    def test_just_above_low_threshold_yields_L3_short(self) -> None:
        """0.1501 >= 0.15 and < 0.50, with non-identity → L3_short."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.1501, "external_consequence")
        assert result == "L3_short"

    def test_just_below_high_threshold_yields_L3_short(self) -> None:
        """0.4999 < 0.50, with non-identity → L3_short."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.4999, "internal_to_visible_consequence")
        assert result == "L3_short"


# ── Extreme values ──────────────────────────────────────────────────────


class TestClassifierExtremeValues:
    """affect_intensity = 0.0 and 1.0."""

    def test_zero_affect_no_outcome_yields_L2_working(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.0, "no_outcome")
        assert result == "L2_working"

    def test_zero_affect_other_outcome_yields_L3_short(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.0, "self_changed")
        assert result == "L3_short"

    def test_max_affect_identity_yields_L5_autobiographical(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(1.0, "self_changed")
        assert result == "L5_autobiographical"

    def test_max_affect_non_identity_yields_L4_long(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(1.0, "external_consequence")
        assert result == "L4_long"


# ── Fallback and unknown outcome_class ──────────────────────────────────


class TestClassifierFallback:
    """Unknown outcome_class falls through existing branches safely."""

    def test_low_affect_unknown_outcome_yields_L3_short(self) -> None:
        """Low affect + unknown outcome → L3_short (not internal/no_outcome, so row 2)."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.05, "completely_unknown_outcome")
        assert result == "L3_short"

    def test_mid_affect_unknown_outcome_yields_L3_short(self) -> None:
        """Mid affect + unknown outcome → L3_short (not identity, so row 4)."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.30, "completely_unknown_outcome")
        assert result == "L3_short"

    def test_high_affect_unknown_outcome_yields_L4_long(self) -> None:
        """High affect + unknown outcome → L4_long (not identity, so row 6)."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        result = classifier.classify_layer(0.70, "completely_unknown_outcome")
        assert result == "L4_long"


# ── Custom threshold / identity_outcome_classes ─────────────────────────


class TestClassifierCustomConfiguration:
    """Custom thresholds and identity outcome classes."""

    def test_custom_low_threshold(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier(low_affect_threshold=0.30)
        # 0.20 < 0.30 with no_outcome → L2_working
        assert classifier.classify_layer(0.20, "no_outcome") == "L2_working"
        # 0.30 >= 0.30 with non-identity → L3_short (in [0.30, 0.50))
        assert classifier.classify_layer(0.30, "external_consequence") == "L3_short"

    def test_custom_high_threshold(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier(high_affect_threshold=0.80)
        # 0.70 < 0.80 with non-identity → L3_short (in [0.15, 0.80))
        assert classifier.classify_layer(0.70, "external_consequence") == "L3_short"
        # 0.80 >= 0.80 with self_changed → L5_autobiographical
        assert classifier.classify_layer(0.80, "self_changed") == "L5_autobiographical"

    def test_custom_identity_outcome_classes(self) -> None:
        classifier = AffectOutcomeMemoryLayerClassifier(
            identity_outcome_classes=("self_changed", "identity_shift"),
        )
        # Mid affect + identity_shift → L4_long
        assert classifier.classify_layer(0.30, "identity_shift") == "L4_long"
        # High affect + identity_shift → L5_autobiographical
        assert classifier.classify_layer(0.70, "identity_shift") == "L5_autobiographical"

    def test_default_thresholds_match_design(self) -> None:
        """Default thresholds must be exactly 0.15 and 0.50 as specified."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        assert classifier.low_affect_threshold == 0.15
        assert classifier.high_affect_threshold == 0.50
        assert classifier.identity_outcome_classes == ("self_changed",)

    def test_all_returns_are_valid_memory_layers(self) -> None:
        """Every classify_layer return must be in VALID_MEMORY_LAYERS."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        test_cases = [
            (0.0, "no_outcome"),
            (0.10, "internal_to_visible_consequence"),
            (0.10, "self_changed"),
            (0.30, "self_changed"),
            (0.30, "external_consequence"),
            (0.70, "self_changed"),
            (0.70, "external_consequence"),
            (1.0, "no_outcome"),
        ]
        for affect, outcome in test_cases:
            result = classifier.classify_layer(affect, outcome)
            assert result in VALID_MEMORY_LAYERS
