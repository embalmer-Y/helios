from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from helios_v2.experience_writeback import (
    ConsolidationCandidate,
    ContinuityEvidencePacket,
    ExperienceWritebackConfig,
    ExperienceWritebackError,
    ExperienceWritebackRequest,
    ExperienceWritebackResult,
)


def _request() -> ExperienceWritebackRequest:
    return ExperienceWritebackRequest(
        request_id="experience-writeback-request:001",
        source_outcome_kind="planner_bridge",
        source_outcome_id="planner-bridge-result:001",
        source_outcome_status="executed",
        outcome_class="world_changed",
        source_provenance={
            "source_request_id": "planner-bridge-request:001",
            "proposal_id": "proposal:001",
            "decision_id": "decision:001",
        },
        requested_effect_summary="reply_message via cli",
        applied_effect_summary="reply_message reached cli transport",
        reason_trace=("planner selected cli output path",),
        tick_id=1,
    )


def _packet() -> ContinuityEvidencePacket:
    request = _request()
    return ContinuityEvidencePacket(
        packet_id="continuity-packet:001",
        continuity_kind="external_action",
        source_outcome_kind=request.source_outcome_kind,
        source_outcome_id=request.source_outcome_id,
        outcome_class=request.outcome_class,
        summary="External action changed the world",
        requested_effect_summary=request.requested_effect_summary,
        applied_effect_summary=request.applied_effect_summary,
        reason_trace=request.reason_trace,
        source_provenance=request.source_provenance,
    )


def test_contracts_freeze_provenance_and_candidate_payloads() -> None:
    request = _request()
    packet = _packet()
    candidate = ConsolidationCandidate(
        candidate_id="consolidation-candidate:episodic:001",
        target_memory_family="episodic",
        priority_hint=0.8,
        salience_reason="preserve the visible external consequence",
        continuity_packet=packet,
    )
    result = ExperienceWritebackResult(
        result_id="experience-writeback-result:001",
        source_request_id=request.request_id,
        status="written",
        continuity_packet=packet,
        consolidation_candidates=(candidate,),
        tick_id=1,
    )

    assert isinstance(request.source_provenance, MappingProxyType)
    assert isinstance(packet.source_provenance, MappingProxyType)
    with pytest.raises(TypeError):
        request.source_provenance["proposal_id"] = "proposal:mutated"
    with pytest.raises(TypeError):
        packet.source_provenance["decision_id"] = "decision:mutated"
    with pytest.raises(FrozenInstanceError):
        result.consolidation_candidates += (candidate,)


def test_config_requires_confirmed_learned_parameter_surface() -> None:
    with pytest.raises(
        ExperienceWritebackError,
        match="confirmed mandatory learned-parameter categories",
    ):
        ExperienceWritebackConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            writeback_bootstrap_id="experience-writeback-bootstrap:v1",
            mandatory_learned_parameters=("continuity_classification_policy",),
        )


def test_result_distinguishes_blocked_and_identity_change_statuses() -> None:
    packet = _packet()
    candidate = ConsolidationCandidate(
        candidate_id="consolidation-candidate:autobiographical:001",
        target_memory_family="autobiographical",
        priority_hint=0.7,
        salience_reason="retain world-facing continuity in self history",
        continuity_packet=packet,
    )
    blocked_result = ExperienceWritebackResult(
        result_id="experience-writeback-result:blocked",
        source_request_id="experience-writeback-request:blocked",
        status="written_blocked_outcome",
        continuity_packet=packet,
        consolidation_candidates=(candidate,),
        tick_id=1,
    )
    identity_result = ExperienceWritebackResult(
        result_id="experience-writeback-result:identity",
        source_request_id="experience-writeback-request:identity",
        status="written_identity_change",
        continuity_packet=packet,
        consolidation_candidates=(candidate,),
        tick_id=1,
    )

    assert blocked_result.status == "written_blocked_outcome"
    assert identity_result.status == "written_identity_change"