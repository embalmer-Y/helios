from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayConfig,
    MemoryAffectReplayError,
    MemoryContentPacket,
    MemoryFormationState,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    validate_prediction_mismatch_evidence,
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
        feeling=_build_feeling(0.6),
        tick_id=9,
    )


def _build_content() -> MemoryContentPacket:
    return MemoryContentPacket(
        content_kind="situational-summary",
        summary_ref="summary:abc",
        context_ref="context:abc",
        salient_tokens=("threat", "breath", "narrow-room"),
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


def test_prediction_mismatch_evidence_is_immutable_and_range_checked() -> None:
    evidence = PredictionMismatchEvidence(
        evidence_id="mismatch:001",
        source_reference_id="prediction:001",
        mismatch_score=0.8,
        anomaly_score=0.7,
        confidence=0.9,
    )

    with pytest.raises(FrozenInstanceError):
        evidence.confidence = 0.2

    with pytest.raises(MemoryAffectReplayError, match="mismatch_score"):
        PredictionMismatchEvidence(
            evidence_id="mismatch:002",
            source_reference_id="prediction:002",
            mismatch_score=1.2,
            anomaly_score=0.7,
            confidence=0.9,
        )


def test_prediction_mismatch_validation_rejects_non_contract_object() -> None:
    class ForeignEvidence:
        evidence_id = "foreign:001"
        source_reference_id = "prediction:001"
        mismatch_score = 0.7
        anomaly_score = 0.6
        confidence = 0.8

    with pytest.raises(MemoryAffectReplayError, match="explicit PredictionMismatchEvidence contract"):
        validate_prediction_mismatch_evidence(ForeignEvidence())  # type: ignore[arg-type]


def test_content_packet_requires_minimal_payload() -> None:
    packet = _build_content()

    assert packet.content_kind == "situational-summary"

    with pytest.raises(MemoryAffectReplayError, match="at least one summary_ref"):
        MemoryContentPacket(
            content_kind="situational-summary",
            summary_ref=None,
            context_ref=None,
            salient_tokens=(),
        )


def test_memory_item_reuses_feeling_vector_as_affect_tag() -> None:
    item = AffectTaggedMemoryItem(
        memory_id="memory:001",
        family="episodic",
        source_feeling_state_id=_build_feeling_state().state_id,
        affect_tag=_build_feeling(0.4),
        content=_build_content(),
        binding_context_id="binding:001",
        tick_id=9,
    )

    assert item.affect_tag.valence == 0.4
    assert item.content.summary_ref == "summary:abc"


def test_replay_candidate_uses_bounded_continuous_priority_hint() -> None:
    candidate = MemoryReplayCandidate(
        candidate_id="candidate:001",
        memory_id="memory:001",
        family="semantic",
        source_feeling_state_id=_build_feeling_state().state_id,
        replay_reasons=("high_affect_intensity", "prediction_mismatch_or_surprise"),
        forced_consolidation=True,
        priority_hint=0.85,
    )

    assert candidate.priority_hint == 0.85

    with pytest.raises(MemoryAffectReplayError, match="priority_hint"):
        MemoryReplayCandidate(
            candidate_id="candidate:002",
            memory_id="memory:001",
            family="semantic",
            source_feeling_state_id=_build_feeling_state().state_id,
            replay_reasons=("high_affect_intensity",),
            forced_consolidation=False,
            priority_hint=1.4,
        )

    with pytest.raises(MemoryAffectReplayError, match="source_feeling_state_id"):
        MemoryReplayCandidate(
            candidate_id="candidate:003",
            memory_id="memory:001",
            family="semantic",
            source_feeling_state_id="",
            replay_reasons=("high_affect_intensity",),
            forced_consolidation=False,
            priority_hint=0.4,
        )


def test_config_accepts_only_confirmed_learned_parameter_categories() -> None:
    config = _build_config()

    assert config.storage_bootstrap_state_id == "memory-bootstrap:v1"

    with pytest.raises(MemoryAffectReplayError, match="mandatory learned-parameter categories"):
        MemoryAffectReplayConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            storage_bootstrap_state_id="memory-bootstrap:v1",
            mandatory_learned_parameters=(
                "memory_family_write_policy",
                "replay_priority_policy",
            ),
        )


def test_memory_formation_state_preserves_provenance_and_payloads() -> None:
    item = AffectTaggedMemoryItem(
        memory_id="memory:001",
        family="autobiographical",
        source_feeling_state_id=_build_feeling_state().state_id,
        affect_tag=_build_feeling(0.5),
        content=_build_content(),
        binding_context_id="binding:001",
        tick_id=9,
    )
    candidate = MemoryReplayCandidate(
        candidate_id="candidate:001",
        memory_id="memory:001",
        family="autobiographical",
        source_feeling_state_id=_build_feeling_state().state_id,
        replay_reasons=("unresolved_tension_or_discomfort",),
        forced_consolidation=False,
        priority_hint=0.6,
    )
    state = MemoryFormationState(
        state_id="memory-formation-state:interoceptive-feeling-state:neuromodulator-state:abc:9:13",
        source_feeling_state_id=_build_feeling_state().state_id,
        memory_items=(item,),
        replay_candidates=(candidate,),
        tick_id=13,
    )

    assert state.source_feeling_state_id == _build_feeling_state().state_id
    assert state.memory_items[0].family == "autobiographical"
    assert state.replay_candidates[0].replay_reasons == ("unresolved_tension_or_discomfort",)


def test_memory_formation_state_rejects_replay_candidate_without_matching_memory_item() -> None:
    item = AffectTaggedMemoryItem(
        memory_id="memory:001",
        family="episodic",
        source_feeling_state_id=_build_feeling_state().state_id,
        affect_tag=_build_feeling(0.5),
        content=_build_content(),
        binding_context_id="binding:001",
        tick_id=9,
    )
    dangling_candidate = MemoryReplayCandidate(
        candidate_id="candidate:missing",
        memory_id="memory:missing",
        family="episodic",
        source_feeling_state_id=_build_feeling_state().state_id,
        replay_reasons=("high_affect_intensity",),
        forced_consolidation=False,
        priority_hint=0.5,
    )

    with pytest.raises(MemoryAffectReplayError, match="must reference published memory_items"):
        MemoryFormationState(
            state_id="memory-formation-state:bad:13",
            source_feeling_state_id=_build_feeling_state().state_id,
            memory_items=(item,),
            replay_candidates=(dangling_candidate,),
            tick_id=13,
        )


def test_memory_formation_state_rejects_replay_candidate_with_mismatched_feeling_provenance() -> None:
    item = AffectTaggedMemoryItem(
        memory_id="memory:001",
        family="episodic",
        source_feeling_state_id=_build_feeling_state().state_id,
        affect_tag=_build_feeling(0.5),
        content=_build_content(),
        binding_context_id="binding:001",
        tick_id=9,
    )
    mismatched_candidate = MemoryReplayCandidate(
        candidate_id="candidate:wrong-feeling",
        memory_id="memory:001",
        family="episodic",
        source_feeling_state_id="interoceptive-feeling-state:other",
        replay_reasons=("high_affect_intensity",),
        forced_consolidation=False,
        priority_hint=0.5,
    )

    with pytest.raises(MemoryAffectReplayError, match="source_feeling_state_id"):
        MemoryFormationState(
            state_id="memory-formation-state:bad-feeling:13",
            source_feeling_state_id=_build_feeling_state().state_id,
            memory_items=(item,),
            replay_candidates=(mismatched_candidate,),
            tick_id=13,
        )