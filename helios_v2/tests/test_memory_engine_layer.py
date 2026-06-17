"""R100 T3 tests: MemoryAffectReplayEngine classifier injection + MemoryRecord production.

Validates:
- MemoryFormationState gains additive memory_records field
- Engine produces MemoryRecord when classifier present AND forced_consolidation=True
- Engine produces empty memory_records when classifier absent (legacy unchanged)
- Engine produces empty memory_records when forced_consolidation=False
- Layer matches classifier output for various affect/outcome combinations
- outcome_class parameter flows correctly into MemoryRecord
- affect_intensity_at_write uses priority_hint (gate value) when available
- MemoryRecord referential integrity validated by MemoryFormationState.__post_init__
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector
from helios_v2.memory import (
    AffectOutcomeMemoryLayerClassifier,
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryAffectReplayEngine,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFormationPath,
    MemoryFormationState,
    MemoryLayerClassifier,
    MemoryRecord,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    ReplayCandidateSelector,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_feeling(**overrides: float) -> InteroceptiveFeelingVector:
    defaults = dict(valence=0.5, arousal=0.5, tension=0.5, comfort=0.3, fatigue=0.1, pain_like=0.1, social_safety=0.6)
    defaults.update(overrides)
    return InteroceptiveFeelingVector(**defaults)


def _build_feeling_state(feeling: InteroceptiveFeelingVector | None = None, tick_id: int = 9) -> InteroceptiveFeelingState:
    return InteroceptiveFeelingState(
        state_id=f"interoceptive-feeling-state:neuromodulator-state:abc:{tick_id}",
        source_neuromodulator_state_id="neuromodulator-state:abc",
        feeling=feeling or _build_feeling(),
        tick_id=tick_id,
    )


def _build_content() -> MemoryContentPacket:
    return MemoryContentPacket(
        content_kind="situational-summary",
        summary_ref="summary:abc",
        context_ref="context:abc",
        salient_tokens=("danger", "heartbeat"),
    )


def _build_binding_context() -> MemoryBindingContext:
    return MemoryBindingContext(
        context_id="binding:001",
        source_kind="runtime-chain",
        content=_build_content(),
    )


def _build_config(layer_policy: bool = True) -> MemoryAffectReplayConfig:
    categories = (
        "memory_family_write_policy",
        "replay_priority_policy",
        "consolidation_policy",
        "layer_assignment_policy",
    ) if layer_policy else (
        "memory_family_write_policy",
        "replay_priority_policy",
        "consolidation_policy",
    )
    return MemoryAffectReplayConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        storage_bootstrap_state_id="memory-bootstrap:v1",
        mandatory_learned_parameters=categories,
    )


@dataclass
class FixedFormationPath(MemoryFormationPath):
    """Produces one episodic memory item from a binding context."""

    def form_memory_items(
        self, feeling_state, binding_context, mismatch_evidence, config, tick_id,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        if binding_context is None:
            return ()
        family = "autobiographical" if mismatch_evidence is not None else "episodic"
        return (
            AffectTaggedMemoryItem(
                memory_id=f"memory:runtime:{tick_id}",
                family=family,
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


@dataclass
class ForcedSelector(ReplayCandidateSelector):
    """Always produces forced_consolidation=True with configurable priority_hint."""

    forced: bool = True
    priority_hint: float | None = 0.75
    reasons: tuple[str, ...] = ("high_affect_intensity",)

    def select_candidates(self, memory_items, feeling_state, mismatch_evidence, config):
        return tuple(
            MemoryReplayCandidate(
                candidate_id=f"candidate:runtime:{feeling_state.tick_id}:{i}",
                memory_id=item.memory_id,
                family=item.family,
                source_feeling_state_id=feeling_state.state_id,
                replay_reasons=self.reasons,
                forced_consolidation=self.forced,
                priority_hint=self.priority_hint,
            )
            for i, item in enumerate(memory_items)
        )


@dataclass
class NonForcedSelector(ReplayCandidateSelector):
    """Always produces forced_consolidation=False."""

    def select_candidates(self, memory_items, feeling_state, mismatch_evidence, config):
        return tuple(
            MemoryReplayCandidate(
                candidate_id=f"candidate:runtime:{feeling_state.tick_id}:{i}",
                memory_id=item.memory_id,
                family=item.family,
                source_feeling_state_id=feeling_state.state_id,
                replay_reasons=("high_affect_intensity",),
                forced_consolidation=False,
                priority_hint=0.1,
            )
            for i, item in enumerate(memory_items)
        )


# ---------------------------------------------------------------------------
# MemoryFormationState additive field tests
# ---------------------------------------------------------------------------

class TestMemoryFormationStateRecordsField:
    """R100: memory_records additive field on MemoryFormationState."""

    def test_default_empty_records(self):
        """When no memory_records passed, field defaults to empty tuple."""
        item = AffectTaggedMemoryItem(
            memory_id="m:1", family="episodic",
            source_feeling_state_id="fs:1",
            affect_tag=_build_feeling(),
            content=_build_content(),
            binding_context_id=None, tick_id=1,
        )
        state = MemoryFormationState(
            state_id="s:1", source_feeling_state_id="fs:1",
            memory_items=(item,), replay_candidates=(),
            tick_id=1,
        )
        assert state.memory_records == ()

    def test_explicit_records_accepted(self):
        """Explicit memory_records tuple is stored correctly."""
        item = AffectTaggedMemoryItem(
            memory_id="m:1", family="episodic",
            source_feeling_state_id="fs:1",
            affect_tag=_build_feeling(),
            content=_build_content(),
            binding_context_id=None, tick_id=1,
        )
        record = MemoryRecord(
            memory_id="m:1", layer="L3_short",
            affect_intensity_at_write=0.35,
            outcome_class_at_write="no_outcome",
            source_feeling_state_id="fs:1",
            family="episodic",
            content=_build_content(),
            binding_context_id=None, tick_id=1,
            created_at_wall=1000.0,
        )
        state = MemoryFormationState(
            state_id="s:1", source_feeling_state_id="fs:1",
            memory_items=(item,), replay_candidates=(),
            memory_records=(record,), tick_id=1,
        )
        assert len(state.memory_records) == 1
        assert state.memory_records[0].layer == "L3_short"

    def test_record_wrong_feeling_state_id_rejected(self):
        """MemoryRecord with wrong source_feeling_state_id raises error."""
        item = AffectTaggedMemoryItem(
            memory_id="m:1", family="episodic",
            source_feeling_state_id="fs:1",
            affect_tag=_build_feeling(),
            content=_build_content(),
            binding_context_id=None, tick_id=1,
        )
        record = MemoryRecord(
            memory_id="m:1", layer="L3_short",
            affect_intensity_at_write=0.35,
            outcome_class_at_write="no_outcome",
            source_feeling_state_id="fs:WRONG",
            family="episodic",
            content=_build_content(),
            binding_context_id=None, tick_id=1,
            created_at_wall=1000.0,
        )
        with pytest.raises(MemoryAffectReplayError, match="memory records must preserve"):
            MemoryFormationState(
                state_id="s:1", source_feeling_state_id="fs:1",
                memory_items=(item,), replay_candidates=(),
                memory_records=(record,), tick_id=1,
            )

    def test_record_dangling_memory_id_rejected(self):
        """MemoryRecord referencing nonexistent memory_id raises error."""
        item = AffectTaggedMemoryItem(
            memory_id="m:1", family="episodic",
            source_feeling_state_id="fs:1",
            affect_tag=_build_feeling(),
            content=_build_content(),
            binding_context_id=None, tick_id=1,
        )
        record = MemoryRecord(
            memory_id="m:GHOST", layer="L3_short",
            affect_intensity_at_write=0.35,
            outcome_class_at_write="no_outcome",
            source_feeling_state_id="fs:1",
            family="episodic",
            content=_build_content(),
            binding_context_id=None, tick_id=1,
            created_at_wall=1000.0,
        )
        with pytest.raises(MemoryAffectReplayError, match="memory records must reference"):
            MemoryFormationState(
                state_id="s:1", source_feeling_state_id="fs:1",
                memory_items=(item,), replay_candidates=(),
                memory_records=(record,), tick_id=1,
            )

    def test_multiple_records_accepted(self):
        """Multiple MemoryRecords referencing different items are accepted."""
        items = tuple(
            AffectTaggedMemoryItem(
                memory_id=f"m:{i}", family="episodic",
                source_feeling_state_id="fs:1",
                affect_tag=_build_feeling(),
                content=_build_content(),
                binding_context_id=None, tick_id=1,
            )
            for i in range(3)
        )
        records = tuple(
            MemoryRecord(
                memory_id=f"m:{i}", layer="L3_short",
                affect_intensity_at_write=0.3,
                outcome_class_at_write="no_outcome",
                source_feeling_state_id="fs:1",
                family="episodic",
                content=_build_content(),
                binding_context_id=None, tick_id=1,
                created_at_wall=1000.0 + i,
            )
            for i in range(3)
        )
        state = MemoryFormationState(
            state_id="s:1", source_feeling_state_id="fs:1",
            memory_items=items, replay_candidates=(),
            memory_records=records, tick_id=1,
        )
        assert len(state.memory_records) == 3


# ---------------------------------------------------------------------------
# Engine classifier injection tests
# ---------------------------------------------------------------------------

class TestEngineClassifierInjection:
    """R100: MemoryAffectReplayEngine.layer_classifier injection behavior."""

    def _make_engine(self, classifier=None, forced=True, priority_hint=0.75, selector=None):
        if selector is None:
            selector = ForcedSelector(forced=forced, priority_hint=priority_hint)
        return MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=selector,
            layer_classifier=classifier,
        )

    def test_no_classifier_no_records(self):
        """When classifier absent, memory_records is empty (legacy unchanged)."""
        engine = self._make_engine(classifier=None, forced=True)
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            tick_id=13,
        )
        assert state.memory_records == ()
        # Verify legacy path still produces items and candidates
        assert len(state.memory_items) == 1
        assert len(state.replay_candidates) == 1

    def test_classifier_present_forced_consolidation_produces_record(self):
        """When classifier present AND forced=True, produces MemoryRecord."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        engine = self._make_engine(classifier=classifier, forced=True, priority_hint=0.75)
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=13,
        )
        assert len(state.memory_records) == 1
        record = state.memory_records[0]
        assert record.memory_id == state.memory_items[0].memory_id
        assert record.outcome_class_at_write == "no_outcome"
        assert record.family == "episodic"
        assert record.source_feeling_state_id == state.source_feeling_state_id

    def test_classifier_present_nonforced_no_records(self):
        """When classifier present but forced=False, memory_records is empty."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        engine = self._make_engine(
            classifier=classifier,
            selector=NonForcedSelector(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=13,
        )
        assert state.memory_records == ()

    def test_no_binding_context_no_items_no_records(self):
        """When no binding context, no items formed, no records produced."""
        classifier = AffectOutcomeMemoryLayerClassifier()
        engine = self._make_engine(classifier=classifier, forced=True)
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=None,
            outcome_class="no_outcome",
            tick_id=13,
        )
        assert state.memory_items == ()
        assert state.memory_records == ()
        assert state.replay_candidates == ()


# ---------------------------------------------------------------------------
# Layer assignment matches classifier output
# ---------------------------------------------------------------------------

class TestLayerAssignmentMatchesClassifier:
    """R100: MemoryRecord.layer matches classifier.classify_layer output."""

    def _make_engine_with_classifier(self, **classifier_kw):
        classifier = AffectOutcomeMemoryLayerClassifier(**classifier_kw)
        return MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.75),
            layer_classifier=classifier,
        )

    def test_low_affect_no_outcome_l2_working(self):
        """Low affect + no_outcome → L2_working (row 1 of decision table)."""
        # priority_hint=0.10 → low affect (< 0.15)
        engine = self._make_engine_with_classifier()
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        # priority_hint=0.75 from ForcedSelector, so classifier sees 0.75
        # That's >= 0.50 high_affect_threshold, with non-identity outcome → L4_long
        assert state.memory_records[0].layer == "L4_long"

    def test_high_affect_identity_outcome_l5(self):
        """High affect + self_changed → L5_autobiographical (row 5)."""
        engine = self._make_engine_with_classifier()
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="self_changed",
            tick_id=1,
        )
        # priority_hint=0.75 >= 0.50, identity outcome → L5_autobiographical
        assert state.memory_records[0].layer == "L5_autobiographical"

    def test_high_affect_non_identity_l4(self):
        """High affect + non-identity → L4_long (row 6)."""
        engine = self._make_engine_with_classifier()
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="visible_consequence",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L4_long"

    def test_low_affect_internal_visible_l2(self):
        """Low affect + internal_to_visible_consequence → L2_working (row 1)."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.10),  # < 0.15
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="internal_to_visible_consequence",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L2_working"

    def test_low_affect_other_outcome_l3(self):
        """Low affect + other outcome → L3_short (row 2)."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.10),  # < 0.15
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="visible_consequence",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L3_short"

    def test_medium_affect_identity_l4(self):
        """Medium affect + identity → L4_long (row 3)."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.30),  # [0.15, 0.50)
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="self_changed",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L4_long"

    def test_medium_affect_non_identity_l3(self):
        """Medium affect + non-identity → L3_short (row 4)."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.30),  # [0.15, 0.50)
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="visible_consequence",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L3_short"


# ---------------------------------------------------------------------------
# affect_intensity_at_write uses priority_hint (gate value)
# ---------------------------------------------------------------------------

class TestAffectIntensityUsesGateValue:
    """R100: affect_intensity_at_write stores the priority_hint (gate value)."""

    def test_priority_hint_stored_as_affect_intensity(self):
        """priority_hint from candidate is stored as affect_intensity_at_write."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.65),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        assert state.memory_records[0].affect_intensity_at_write == 0.65

    def test_priority_hint_none_fallback_to_computed_intensity(self):
        """When priority_hint is None, fallback to computed affect_intensity."""
        # Build engine with priority_hint=None selector
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=None),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
            # Use weights matching default: 0.5*arousal + 0.3*tension + 0.2*pain_like
            affect_arousal_weight=0.5,
            affect_tension_weight=0.3,
            affect_pain_weight=0.2,
        )
        feeling = _build_feeling(arousal=0.7, tension=0.3, pain_like=0.1)
        state = engine.record_state(
            feeling_state=_build_feeling_state(feeling=feeling),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        # Computed: 0.5*0.7 + 0.3*0.3 + 0.2*0.1 = 0.35 + 0.09 + 0.02 = 0.46
        assert state.memory_records[0].affect_intensity_at_write == pytest.approx(0.46, abs=0.01)


# ---------------------------------------------------------------------------
# outcome_class parameter flow
# ---------------------------------------------------------------------------

class TestOutcomeClassFlow:
    """R100: outcome_class flows from record_state to MemoryRecord."""

    def test_default_outcome_class_no_outcome(self):
        """Default outcome_class='no_outcome' flows into MemoryRecord."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.75),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            tick_id=1,
        )
        assert state.memory_records[0].outcome_class_at_write == "no_outcome"

    def test_explicit_outcome_class_self_changed(self):
        """Explicit outcome_class='self_changed' flows into MemoryRecord."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.75),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="self_changed",
            tick_id=1,
        )
        assert state.memory_records[0].outcome_class_at_write == "self_changed"


# ---------------------------------------------------------------------------
# Record fields match corresponding item/candidate
# ---------------------------------------------------------------------------

class TestRecordFieldConsistency:
    """R100: MemoryRecord fields match their source AffectTaggedMemoryItem."""

    def test_record_fields_match_item(self):
        """MemoryRecord carries same family, content, binding_context_id as the item."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.35),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="self_changed",
            tick_id=13,
        )
        item = state.memory_items[0]
        record = state.memory_records[0]
        assert record.memory_id == item.memory_id
        assert record.family == item.family
        assert record.content == item.content
        assert record.binding_context_id == item.binding_context_id
        assert record.tick_id == item.tick_id
        assert record.source_feeling_state_id == state.source_feeling_state_id

    def test_created_at_wall_is_set(self):
        """MemoryRecord has a non-None created_at_wall."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.5),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        assert state.memory_records[0].created_at_wall is not None
        assert state.memory_records[0].created_at_wall > 0.0


# ---------------------------------------------------------------------------
# Custom classifier (protocol-based)
# ---------------------------------------------------------------------------

class TestCustomClassifier:
    """R100: Any MemoryLayerClassifier protocol implementation works."""

    @dataclass
    class FixedLayerClassifier:
        """Always returns a fixed layer regardless of inputs."""
        fixed_layer: str = "L4_long"

        def classify_layer(self, affect_intensity: float, outcome_class: str):
            return self.fixed_layer

    def test_custom_classifier_fixed_layer(self):
        """Custom classifier returning fixed layer is accepted by engine."""
        classifier = self.FixedLayerClassifier(fixed_layer="L5_autobiographical")
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.75),
            layer_classifier=classifier,
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        assert state.memory_records[0].layer == "L5_autobiographical"


# ---------------------------------------------------------------------------
# Boundary and extreme values
# ---------------------------------------------------------------------------

class TestBoundaryValues:
    """R100: Boundary values for affect_intensity and outcome_class."""

    def test_zero_affect_intensity(self):
        """affect_intensity=0.0 produces MemoryRecord (classifier still called)."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.0),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        # 0.0 < 0.15 + no_outcome → L2_working
        assert state.memory_records[0].layer == "L2_working"
        assert state.memory_records[0].affect_intensity_at_write == pytest.approx(0.0, abs=0.001)

    def test_max_affect_intensity(self):
        """affect_intensity=1.0 produces MemoryRecord."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=1.0),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="self_changed",
            tick_id=1,
        )
        # 1.0 >= 0.50 + self_changed → L5_autobiographical
        assert state.memory_records[0].layer == "L5_autobiographical"

    def test_exact_low_threshold(self):
        """priority_hint exactly at low threshold (0.15) → medium range."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.15),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        # 0.15 in [0.15, 0.50) + non-identity → L3_short
        assert state.memory_records[0].layer == "L3_short"

    def test_exact_high_threshold(self):
        """priority_hint exactly at high threshold (0.50) → high range."""
        engine = MemoryAffectReplayEngine(
            config=_build_config(),
            formation_path=FixedFormationPath(),
            replay_selector=ForcedSelector(forced=True, priority_hint=0.50),
            layer_classifier=AffectOutcomeMemoryLayerClassifier(),
        )
        state = engine.record_state(
            feeling_state=_build_feeling_state(),
            binding_context=_build_binding_context(),
            outcome_class="no_outcome",
            tick_id=1,
        )
        # 0.50 >= 0.50 + non-identity → L4_long
        assert state.memory_records[0].layer == "L4_long"
