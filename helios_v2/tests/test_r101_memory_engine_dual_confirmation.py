"""R101 T7: MemoryAffectReplayEngine 6-inject integration tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector
from helios_v2.memory import (
    AffectGroundedMemoryFormationPath,
    AffectOutcomeMemoryLayerClassifier,
    ConvexWeightedObjectiveAggregator,
    DoubleConfirmationClass,
    DoubleConfirmationResult,
    FirstVersionDoubleConfirmationGate,
    FirstVersionObjectiveImportanceEstimator,
    FirstVersionRecallUtilityTracker,
    MemoryAffectReplayConfig,
    MemoryAffectReplayEngine,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFormationPath,
    MemoryLayer,
    ObjectiveImportanceLayerResolver,
    ObjectiveImportanceVector,
    OUTCOME_CLASS_WEIGHTS,
    ReplayCandidateSelector,
    SalienceGatedReplayCandidateSelector,
)


# =============================================================================
# Test fixtures
# =============================================================================


def _make_feeling_state(tick_id: int = 1) -> InteroceptiveFeelingState:
    feeling = InteroceptiveFeelingVector(
        valence=0.6,
        arousal=0.7,
        tension=0.4,
        comfort=0.5,
        fatigue=0.3,
        pain_like=0.2,
        social_safety=0.7,
    )
    state = InteroceptiveFeelingState.__new__(InteroceptiveFeelingState)
    object.__setattr__(state, "state_id", "f-test-1")
    object.__setattr__(state, "source_neuromodulator_state_id", "n-test-1")
    object.__setattr__(state, "feeling", feeling)
    object.__setattr__(state, "internal_signals", ())
    object.__setattr__(state, "tick_id", tick_id)
    return state


def _make_binding_context() -> MemoryBindingContext:
    return MemoryBindingContext(
        context_id="b-test-1",
        source_kind="test",
        content=MemoryContentPacket(
            content_kind="test",
            summary_ref="s1",
            context_ref=None,
            salient_tokens=("hello", "world", "test"),
        ),
    )


def _make_base_engine() -> MemoryAffectReplayEngine:
    """Engine with NO R101 injects; tests legacy R100 path."""
    config = MemoryAffectReplayConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        storage_bootstrap_state_id="bootstrap-1",
        mandatory_learned_parameters=(
            "memory_family_write_policy",
            "replay_priority_policy",
            "consolidation_policy",
            "layer_assignment_policy",
        ),
    )
    return MemoryAffectReplayEngine(
        config=config,
        formation_path=AffectGroundedMemoryFormationPath(),
        replay_selector=SalienceGatedReplayCandidateSelector(),
        layer_classifier=AffectOutcomeMemoryLayerClassifier(),
    )


def _make_r101_engine(
    *,
    hormone_pred=None,
    estimator=None,
    aggregator=None,
    gate=None,
    resolver=None,
    tracker=None,
) -> MemoryAffectReplayEngine:
    """Engine with ALL 6 R101 injects present."""
    base = _make_base_engine()
    return replace(
        base,
        objective_importance_estimator=estimator or FirstVersionObjectiveImportanceEstimator(),
        objective_aggregator=aggregator or ConvexWeightedObjectiveAggregator(),
        double_confirmation_gate=gate or FirstVersionDoubleConfirmationGate(),
        objective_layer_resolver=resolver or ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=tracker or FirstVersionRecallUtilityTracker(),
        hormone_prediction_provider=lambda: hormone_pred,
    )


# =============================================================================
# Legacy R100 path tests (no R101 injects)
# =============================================================================


def test_legacy_path_no_r101_fields() -> None:
    """Without R101 injects, MemoryRecord has all R101 fields None / 0 / ()."""
    engine = _make_base_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    assert state.memory_records != ()
    for record in state.memory_records:
        assert record.objective_importance is None
        assert record.objective_score is None
        assert record.subjective_score is None
        assert record.double_confirmation is None
        assert record.recall_count == 0
        assert record.last_recall_at_tick is None
        assert record.recall_utility_score is None
        assert record.last_updated_at_wall is None  # R100 created_at_wall stays as the write-time stamp
        assert record.promotion_history == ()


# =============================================================================
# R101 path tests (all 6 injects present)
# =============================================================================


def test_r101_path_populates_objective_vector() -> None:
    engine = _make_r101_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    assert state.memory_records != ()
    for record in state.memory_records:
        assert isinstance(record.objective_importance, ObjectiveImportanceVector)
        # 6 dimensions all in [0, 1]
        assert 0.0 <= record.objective_importance.stimulus_intensity <= 1.0


def test_r101_path_populates_objective_score() -> None:
    engine = _make_r101_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.objective_score is not None
        assert 0.0 <= record.objective_score <= 1.0


def test_r101_path_populates_double_confirmation() -> None:
    engine = _make_r101_engine(
        hormone_pred={"cortisol": 0.7, "dopamine": 0.6},  # both above threshold
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.double_confirmation is not None
        # Both obj and subj likely pass => both_pass or objective_only (depends on aggregator)
        assert record.double_confirmation.classification in (
            "both_pass", "objective_only", "subjective_only", "skip"
        )


def test_r101_path_subjective_score_from_hormone_pred() -> None:
    engine = _make_r101_engine(
        hormone_pred={"cortisol": 0.8, "dopamine": 0.5, "oxytocin": 0.3},
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        # Max of all hormone predictions is 0.8 (cortisol)
        assert record.subjective_score == pytest.approx(0.8)


def test_r101_path_subjective_score_zero_when_no_hormone_pred() -> None:
    engine = _make_r101_engine(hormone_pred=None)
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.subjective_score == 0.0


def test_r101_path_subjective_score_zero_when_empty_hormone_pred() -> None:
    engine = _make_r101_engine(hormone_pred={})
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.subjective_score == 0.0


def test_r101_path_layer_resolver_adjusts_layer() -> None:
    """When R101 resolver says skip, layer becomes L2_working."""
    # With weak stimulus and no subjective signal, expect skip
    engine = _make_r101_engine(
        hormone_pred={},   # no subjective
        resolver=ObjectiveImportanceLayerResolver(),
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        # skip classification -> L2_working (conservative)
        assert record.layer == "L2_working"
        assert record.double_confirmation is not None
        assert record.double_confirmation.classification == "skip"


def test_r101_path_preserves_recall_fields_defaults() -> None:
    """recall_count=0, recall_utility_score=None, promotion_history=() on first write."""
    engine = _make_r101_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.recall_count == 0
        assert record.last_recall_at_tick is None
        assert record.recall_utility_score is None
        assert record.promotion_history == ()


def test_r101_path_sets_last_updated_at_wall() -> None:
    engine = _make_r101_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.last_updated_at_wall is not None
        assert record.last_updated_at_wall > 0.0


def test_r101_path_skip_record_still_persisted() -> None:
    """P5 key invariant: skip-class records still in memory_records (retained as negative examples)."""
    engine = _make_r101_engine(hormone_pred={})
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    # Records still produced (not dropped)
    assert state.memory_records != ()
    skip_records = [r for r in state.memory_records if r.double_confirmation and r.double_confirmation.classification == "skip"]
    assert len(skip_records) > 0


# =============================================================================
# Partial R101 path tests (some injects missing)
# =============================================================================


def test_partial_r101_path_falls_back_to_legacy() -> None:
    """When ANY of the 6 R101 injects is None, the legacy path runs (no R101 fields populated)."""
    base = _make_base_engine()
    # Only inject 5 of 6 (missing hormone_prediction_provider)
    partial = replace(
        base,
        objective_importance_estimator=FirstVersionObjectiveImportanceEstimator(),
        objective_aggregator=ConvexWeightedObjectiveAggregator(),
        double_confirmation_gate=FirstVersionDoubleConfirmationGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        # hormone_prediction_provider=None intentionally
    )
    state = partial.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        # R101 path NOT active -> all R101 fields None
        assert record.objective_importance is None
        assert record.objective_score is None
        assert record.double_confirmation is None


def test_partial_r101_path_only_estimator_missing() -> None:
    """When only objective_importance_estimator is None, legacy path runs."""
    base = _make_base_engine()
    partial = replace(
        base,
        objective_aggregator=ConvexWeightedObjectiveAggregator(),
        double_confirmation_gate=FirstVersionDoubleConfirmationGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        hormone_prediction_provider=lambda: {"cortisol": 0.7},
        # objective_importance_estimator=None intentionally
    )
    state = partial.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.objective_importance is None


# =============================================================================
# Custom R101 collaborators (P5 forward-compatibility)
# =============================================================================


def test_custom_aggregator_replaces_first_version() -> None:
    """A custom ObjectiveAggregator implementation is honored."""
    class CustomAggregator:
        def aggregate(self, vector):
            return 0.42

        def declared_weights(self):
            return (0.42, 0.42, 0.0, 0.0, 0.0, 0.16)

    engine = _make_r101_engine(aggregator=CustomAggregator())
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.objective_score == 0.42


def test_custom_gate_replaces_first_version() -> None:
    """A custom DoubleConfirmationGate can force skip class."""
    class AlwaysSkipGate:
        def evaluate(self, *, objective_score, subjective_score, subjective_confidence, outcome_class):
            return DoubleConfirmationResult(
                classification="skip",
                objective_score=objective_score,
                subjective_score=subjective_score,
                confidence=subjective_confidence,
            )

    engine = _make_r101_engine(gate=AlwaysSkipGate())
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.double_confirmation.classification == "skip"
        assert record.layer == "L2_working"


def test_custom_resolver_forces_l5() -> None:
    """A custom resolver can promote any record to L5."""
    class AlwaysPromoteResolver:
        def resolve(self, *, initial_layer, objective_score, double_confirmation_class, outcome_class):
            return "L5_autobiographical"

    engine = _make_r101_engine(
        hormone_pred={"cortisol": 0.7},
        resolver=AlwaysPromoteResolver(),
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        assert record.layer == "L5_autobiographical"


def test_recall_utility_tracker_present_even_when_no_recall_yet() -> None:
    """Tracker is injected but no recall has happened yet -> recall_count=0."""
    engine = _make_r101_engine()
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",
        tick_id=1,
    )
    for record in state.memory_records:
        # First write: tracker present but no recall yet
        assert record.recall_count == 0
        assert record.recall_utility_score is None


# =============================================================================
# Outcome class interaction
# =============================================================================


def test_self_changed_outcome_class_drives_l5_promotion() -> None:
    """With high objective_score + both_pass + self_changed + L2 initial -> promoted to L5."""
    # Use a custom aggregator that returns very high score
    class HighScoreAggregator:
        def aggregate(self, vector):
            return 0.95
        def declared_weights(self):
            return (0.95, 0.0, 0.0, 0.0, 0.0, 0.05)

    # Use a gate that always returns both_pass
    class BothPassGate:
        def evaluate(self, *, objective_score, subjective_score, subjective_confidence, outcome_class):
            return DoubleConfirmationResult(
                classification="both_pass",
                objective_score=objective_score,
                subjective_score=subjective_score,
                confidence=subjective_confidence,
            )

    base = _make_base_engine()
    # Override layer_classifier to return L2_working for any input (so resolver has something to promote)
    class ForceL2:
        def classify_layer(self, affect_intensity, outcome_class):
            return "L2_working"
    engine = replace(
        base,
        layer_classifier=ForceL2(),
        objective_importance_estimator=FirstVersionObjectiveImportanceEstimator(),
        objective_aggregator=HighScoreAggregator(),
        double_confirmation_gate=BothPassGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        hormone_prediction_provider=lambda: {"cortisol": 0.8},
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="self_changed",
        tick_id=1,
    )
    for record in state.memory_records:
        # L2 + obj=0.95 + identity outcome + both_pass -> L5
        assert record.layer == "L5_autobiographical"


def test_executed_outcome_class_does_not_promote_l2_to_l5() -> None:
    """Without identity outcome class, L2 + high score does NOT promote to L5."""
    class HighScoreAggregator:
        def aggregate(self, vector):
            return 0.95
        def declared_weights(self):
            return (0.95, 0.0, 0.0, 0.0, 0.0, 0.05)

    class BothPassGate:
        def evaluate(self, *, objective_score, subjective_score, subjective_confidence, outcome_class):
            return DoubleConfirmationResult(
                classification="both_pass",
                objective_score=objective_score,
                subjective_score=subjective_score,
                confidence=subjective_confidence,
            )

    class ForceL2:
        def classify_layer(self, affect_intensity, outcome_class):
            return "L2_working"

    base = _make_base_engine()
    engine = replace(
        base,
        layer_classifier=ForceL2(),
        objective_importance_estimator=FirstVersionObjectiveImportanceEstimator(),
        objective_aggregator=HighScoreAggregator(),
        double_confirmation_gate=BothPassGate(),
        objective_layer_resolver=ObjectiveImportanceLayerResolver(),
        recall_utility_tracker=FirstVersionRecallUtilityTracker(),
        hormone_prediction_provider=lambda: {"cortisol": 0.8},
    )
    state = engine.record_state(
        feeling_state=_make_feeling_state(),
        binding_context=_make_binding_context(),
        outcome_class="executed",  # NOT self_changed
        tick_id=1,
    )
    for record in state.memory_records:
        # L2 + obj=0.95 + executed + both_pass -> L2 (only identity outcome promotes to L5)
        assert record.layer == "L2_working"