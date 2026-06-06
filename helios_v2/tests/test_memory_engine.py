from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryAffectReplayEngine,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFormationPath,
    MemoryFormationState,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    ReplayCandidateSelector,
)


def _build_feeling(value: float = 0.5) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=value,
        arousal=value,
        tension=value,
        comfort=value,
        fatigue=value,
        pain_like=value,
        social_safety=value,
    )


def _build_feeling_state() -> InteroceptiveFeelingState:
    return InteroceptiveFeelingState(
        state_id="interoceptive-feeling-state:neuromodulator-state:abc:9",
        source_neuromodulator_state_id="neuromodulator-state:abc",
        feeling=_build_feeling(0.7),
        tick_id=9,
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


def _build_mismatch_evidence() -> PredictionMismatchEvidence:
    return PredictionMismatchEvidence(
        evidence_id="mismatch:001",
        source_reference_id="prediction:001",
        mismatch_score=0.9,
        anomaly_score=0.85,
        confidence=0.8,
    )


def _build_config() -> MemoryAffectReplayConfig:
    return MemoryAffectReplayConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        storage_bootstrap_state_id="memory-bootstrap:v1",
        mandatory_learned_parameters=(
            "memory_family_write_policy",
            "replay_priority_policy",
            "consolidation_policy",
        ),
    )


@dataclass
class CountingFormationPath(MemoryFormationPath):
    calls: int = 0

    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        self.calls += 1
        assert feeling_state.state_id == "interoceptive-feeling-state:neuromodulator-state:abc:9"
        assert binding_context is not None
        assert binding_context.context_id == "binding:001"
        assert mismatch_evidence is not None
        assert mismatch_evidence.evidence_id == "mismatch:001"
        assert config.storage_bootstrap_state_id == "memory-bootstrap:v1"
        assert tick_id == 13
        return (
            AffectTaggedMemoryItem(
                memory_id="memory:001",
                family="episodic",
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


@dataclass
class CountingSelector(ReplayCandidateSelector):
    calls: int = 0

    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        self.calls += 1
        assert len(memory_items) == 1
        assert memory_items[0].family == "episodic"
        assert feeling_state.feeling.tension == 0.7
        assert mismatch_evidence is not None
        assert config.legal_max_priority == 1.0
        return (
            MemoryReplayCandidate(
                candidate_id="candidate:001",
                memory_id=memory_items[0].memory_id,
                family=memory_items[0].family,
                source_feeling_state_id=feeling_state.state_id,
                replay_reasons=(
                    "high_affect_intensity",
                    "unresolved_tension_or_discomfort",
                    "prediction_mismatch_or_surprise",
                ),
                forced_consolidation=True,
                priority_hint=0.92,
            ),
        )


@dataclass
class UnavailableFormationPath(MemoryFormationPath):
    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        raise MemoryAffectReplayError("Required memory formation capability is unavailable")


@dataclass
class WrongBindingContextFormationPath(MemoryFormationPath):
    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        assert binding_context is not None
        return (
            AffectTaggedMemoryItem(
                memory_id="memory:wrong-binding",
                family="episodic",
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id="binding:wrong",
                tick_id=tick_id,
            ),
        )


@dataclass
class DanglingReplaySelector(ReplayCandidateSelector):
    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        return (
            MemoryReplayCandidate(
                candidate_id="candidate:dangling",
                memory_id="memory:not-published",
                family="episodic",
                source_feeling_state_id=feeling_state.state_id,
                replay_reasons=("high_affect_intensity",),
                forced_consolidation=False,
                priority_hint=0.4,
            ),
        )


@dataclass
class WrongFeelingReplaySelector(ReplayCandidateSelector):
    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        return (
            MemoryReplayCandidate(
                candidate_id="candidate:wrong-feeling",
                memory_id=memory_items[0].memory_id,
                family=memory_items[0].family,
                source_feeling_state_id="interoceptive-feeling-state:other",
                replay_reasons=("high_affect_intensity",),
                forced_consolidation=False,
                priority_hint=0.4,
            ),
        )


@dataclass
class OptionalMismatchFormationPath(MemoryFormationPath):
    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        assert binding_context is not None
        assert mismatch_evidence is None
        return (
            AffectTaggedMemoryItem(
                memory_id="memory:002",
                family="semantic",
                source_feeling_state_id=feeling_state.state_id,
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


def test_engine_rejects_malformed_feeling_state_before_formation_invocation() -> None:
    formation_path = CountingFormationPath()
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=formation_path,
        replay_selector=CountingSelector(),
    )

    @dataclass
    class MalformedFeelingState:
        state_id: str = ""
        source_neuromodulator_state_id: str = "neuromodulator-state:abc"
        feeling: InteroceptiveFeelingVector = _build_feeling(0.7)
        tick_id: int | None = 9

    with pytest.raises(MemoryAffectReplayError, match="non-empty state_id"):
        engine.record_state(  # type: ignore[arg-type]
            MalformedFeelingState(),
            _build_binding_context(),
            _build_mismatch_evidence(),
            tick_id=13,
        )

    assert formation_path.calls == 0


def test_engine_records_memory_state_with_injected_collaborators() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=CountingSelector(),
    )

    state = engine.record_state(
        _build_feeling_state(),
        _build_binding_context(),
        _build_mismatch_evidence(),
        tick_id=13,
    )

    assert state.state_id == "memory-formation-state:interoceptive-feeling-state:neuromodulator-state:abc:9:13"
    assert state.memory_items[0].binding_context_id == "binding:001"
    assert state.replay_candidates[0].source_feeling_state_id == state.source_feeling_state_id
    assert state.replay_candidates[0].forced_consolidation is True


def test_engine_builds_record_request_op_from_valid_inputs() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=CountingSelector(),
    )

    op = engine.build_record_op(_build_feeling_state(), _build_binding_context(), _build_mismatch_evidence())

    assert op.op_name == "record_memory_affect_state"
    assert op.owner == "memory_affect_and_replay"
    assert op.binding_context_id == "binding:001"
    assert op.mismatch_evidence_id == "mismatch:001"


def test_engine_builds_publish_ops_from_valid_state() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=CountingSelector(),
    )
    state = engine.record_state(
        _build_feeling_state(),
        _build_binding_context(),
        _build_mismatch_evidence(),
        tick_id=13,
    )

    replay_op = engine.build_publish_replay_candidates_op(state)
    state_op = engine.build_publish_state_op(state)

    assert replay_op.op_name == "publish_memory_replay_candidates"
    assert replay_op.families == ("episodic",)
    assert state_op.op_name == "publish_memory_formation_state"
    assert state_op.memory_count == 1
    assert state_op.candidate_count == 1


def test_engine_fails_explicitly_when_required_formation_capability_is_unavailable() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=UnavailableFormationPath(),
        replay_selector=CountingSelector(),
    )

    with pytest.raises(MemoryAffectReplayError, match="formation capability is unavailable"):
        engine.record_state(_build_feeling_state(), _build_binding_context(), _build_mismatch_evidence(), tick_id=13)


def test_engine_supports_memory_record_without_optional_mismatch_evidence() -> None:
    @dataclass
    class NoMismatchSelector(ReplayCandidateSelector):
        def select_candidates(
            self,
            memory_items: tuple[AffectTaggedMemoryItem, ...],
            feeling_state: InteroceptiveFeelingState,
            mismatch_evidence: PredictionMismatchEvidence | None,
            config: MemoryAffectReplayConfig,
        ) -> tuple[MemoryReplayCandidate, ...]:
            assert mismatch_evidence is None
            return (
                MemoryReplayCandidate(
                    candidate_id="candidate:002",
                    memory_id=memory_items[0].memory_id,
                    family="semantic",
                    source_feeling_state_id=feeling_state.state_id,
                    replay_reasons=("high_affect_intensity",),
                    forced_consolidation=False,
                    priority_hint=0.55,
                ),
            )

    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=OptionalMismatchFormationPath(),
        replay_selector=NoMismatchSelector(),
    )
    state = engine.record_state(_build_feeling_state(), _build_binding_context(), None, tick_id=13)

    assert state.replay_candidates[0].replay_reasons == ("high_affect_intensity",)


def test_engine_rejects_memory_items_with_binding_context_id_mismatch() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=WrongBindingContextFormationPath(),
        replay_selector=CountingSelector(),
    )

    with pytest.raises(MemoryAffectReplayError, match="must preserve the binding_context_id"):
        engine.record_state(
            _build_feeling_state(),
            _build_binding_context(),
            _build_mismatch_evidence(),
            tick_id=13,
        )


def test_engine_rejects_replay_candidates_that_do_not_reference_published_memory_items() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=DanglingReplaySelector(),
    )

    with pytest.raises(MemoryAffectReplayError, match="must reference memory items published"):
        engine.record_state(
            _build_feeling_state(),
            _build_binding_context(),
            _build_mismatch_evidence(),
            tick_id=13,
        )


def test_engine_rejects_replay_candidates_with_feeling_provenance_mismatch() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=WrongFeelingReplaySelector(),
    )

    with pytest.raises(MemoryAffectReplayError, match="source feeling state provenance"):
        engine.record_state(
            _build_feeling_state(),
            _build_binding_context(),
            _build_mismatch_evidence(),
            tick_id=13,
        )


def test_engine_rejects_non_contract_prediction_mismatch_evidence() -> None:
    @dataclass
    class ForeignEvidence:
        evidence_id: str = "foreign:001"
        source_reference_id: str = "prediction:001"
        mismatch_score: float = 0.7
        anomaly_score: float = 0.6
        confidence: float = 0.8

    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=CountingFormationPath(),
        replay_selector=CountingSelector(),
    )

    with pytest.raises(MemoryAffectReplayError, match="explicit PredictionMismatchEvidence contract"):
        engine.build_record_op(
            _build_feeling_state(),
            _build_binding_context(),
            ForeignEvidence(),  # type: ignore[arg-type]
        )


# --- R45: affect-grounded formation + salience-gated consolidation (owner-owned) ---

from helios_v2.memory import (  # noqa: E402
    AffectGroundedMemoryFormationPath,
    SalienceGatedReplayCandidateSelector,
)


def _feeling_state_with(feeling: InteroceptiveFeelingVector, tick_id: int = 9) -> InteroceptiveFeelingState:
    return InteroceptiveFeelingState(
        state_id=f"interoceptive-feeling-state:nm:{tick_id}",
        source_neuromodulator_state_id="neuromodulator-state:nm",
        feeling=feeling,
        tick_id=tick_id,
    )


def _vector(
    *,
    arousal: float = 0.3,
    tension: float = 0.3,
    pain_like: float = 0.0,
    valence: float = 0.5,
    comfort: float = 0.5,
    fatigue: float = 0.3,
    social_safety: float = 0.5,
) -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=valence,
        arousal=arousal,
        tension=tension,
        comfort=comfort,
        fatigue=fatigue,
        pain_like=pain_like,
        social_safety=social_safety,
    )


def test_affect_grounded_formation_tags_item_with_real_feeling() -> None:
    path = AffectGroundedMemoryFormationPath()
    feeling = _vector(arousal=0.81, tension=0.42)
    state = _feeling_state_with(feeling, tick_id=7)

    items = path.form_memory_items(state, _build_binding_context(), None, _build_config(), 7)

    assert len(items) == 1
    item = items[0]
    # The affect tag is the REAL 05 feeling vector, not a constant.
    assert item.affect_tag == feeling
    assert item.source_feeling_state_id == state.state_id
    assert item.family == "episodic"  # no mismatch -> episodic
    assert item.binding_context_id == "binding:001"


def test_affect_grounded_formation_promotes_autobiographical_on_mismatch() -> None:
    path = AffectGroundedMemoryFormationPath()
    items = path.form_memory_items(
        _feeling_state_with(_vector()),
        _build_binding_context(),
        _build_mismatch_evidence(),
        _build_config(),
        7,
    )

    assert items[0].family == "autobiographical"


def test_affect_grounded_formation_returns_nothing_without_binding_context() -> None:
    path = AffectGroundedMemoryFormationPath()
    assert path.form_memory_items(_feeling_state_with(_vector()), None, None, _build_config(), 7) == ()


def test_affect_grounded_formation_is_deterministic() -> None:
    path = AffectGroundedMemoryFormationPath()
    feeling = _vector(arousal=0.6, tension=0.5)
    args = (_feeling_state_with(feeling), _build_binding_context(), None, _build_config(), 7)
    first = path.form_memory_items(*args)
    second = path.form_memory_items(*args)
    assert first[0].affect_tag == second[0].affect_tag
    assert first[0].memory_id == second[0].memory_id
    assert first[0].family == second[0].family


def _formed_item(family: str = "episodic") -> AffectTaggedMemoryItem:
    return AffectTaggedMemoryItem(
        memory_id="memory:001",
        family=family,  # type: ignore[arg-type]
        source_feeling_state_id="interoceptive-feeling-state:nm:9",
        affect_tag=_vector(),
        content=_build_content(),
        binding_context_id="binding:001",
        tick_id=9,
    )


def test_salience_gate_consolidates_high_affect_tick() -> None:
    selector = SalienceGatedReplayCandidateSelector()
    feeling = _vector(arousal=0.9, tension=0.8, pain_like=0.3)
    state = _feeling_state_with(feeling)

    candidates = selector.select_candidates((_formed_item(),), state, None, _build_config())

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.forced_consolidation is True
    assert candidate.priority_hint is not None and candidate.priority_hint >= 0.5
    assert 0.0 <= candidate.priority_hint <= 1.0


def test_salience_gate_does_not_consolidate_flat_low_affect_tick() -> None:
    selector = SalienceGatedReplayCandidateSelector()
    feeling = _vector(arousal=0.1, tension=0.1, pain_like=0.0)
    state = _feeling_state_with(feeling)

    candidates = selector.select_candidates((_formed_item(),), state, None, _build_config())

    assert candidates[0].forced_consolidation is False


def test_salience_gate_consolidates_on_high_mismatch_even_with_flat_feeling() -> None:
    selector = SalienceGatedReplayCandidateSelector()
    feeling = _vector(arousal=0.1, tension=0.1, pain_like=0.0)
    state = _feeling_state_with(feeling)

    candidates = selector.select_candidates(
        (_formed_item(),), state, _build_mismatch_evidence(), _build_config()
    )

    assert candidates[0].forced_consolidation is True
    assert "prediction_mismatch_or_surprise" in candidates[0].replay_reasons


def test_salience_gate_is_deterministic() -> None:
    selector = SalienceGatedReplayCandidateSelector()
    feeling = _vector(arousal=0.7, tension=0.6)
    state = _feeling_state_with(feeling)
    first = selector.select_candidates((_formed_item(),), state, None, _build_config())
    second = selector.select_candidates((_formed_item(),), state, None, _build_config())
    assert first[0].priority_hint == second[0].priority_hint
    assert first[0].forced_consolidation == second[0].forced_consolidation
    assert first[0].replay_reasons == second[0].replay_reasons


def test_salience_gated_selector_integrates_with_engine() -> None:
    engine = MemoryAffectReplayEngine(
        config=_build_config(),
        formation_path=AffectGroundedMemoryFormationPath(),
        replay_selector=SalienceGatedReplayCandidateSelector(),
    )
    feeling = _vector(arousal=0.9, tension=0.8)
    state = engine.record_state(
        _feeling_state_with(feeling, tick_id=9),
        _build_binding_context(),
        None,
        tick_id=9,
    )
    assert state.memory_items[0].affect_tag == feeling
    assert state.replay_candidates[0].forced_consolidation is True
