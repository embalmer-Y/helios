"""Owner: execution writeback and autobiographical consolidation.

Owns:
- experience-writeback request, continuity packet, candidate, and result contracts
- continuity-preserving publication ops for post-outcome writeback
- bounded consolidation-candidate publication contracts

Does not own:
- planner or executor decision authority
- identity-governance judgment authority
- retrieval planning or ranking
- raw backend storage writes
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable


class ExperienceWritebackError(RuntimeError):
    """Hard-stop error raised when experience-writeback invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ExperienceWritebackError(f"{name} must be within [0.0, 1.0]")


ExperienceSourceOutcomeKind = Literal[
    "planner_bridge",
    "identity_governance",
]
ContinuityOutcomeClass = Literal[
    "world_changed",
    "world_blocked",
    "world_failed",
    "self_changed",
    "self_blocked",
]
ExperienceWritebackStatus = Literal[
    "written",
    "written_blocked_outcome",
    "written_identity_change",
    "written_unresolved_outcome",
]
ContinuityKind = Literal[
    "external_action",
    "blocked_action",
    "failed_action",
    "identity_change",
    "blocked_identity_change",
]
TargetMemoryFamily = Literal[
    "episodic",
    "autobiographical",
    "semantic",
]
ExperienceWritebackLearnedParameterCategory = Literal[
    "continuity_classification_policy",
    "consolidation_priority_policy",
    "autobiographical_salience_policy",
]

_SOURCE_OUTCOME_KINDS = {
    "planner_bridge",
    "identity_governance",
}
_OUTCOME_CLASSES = {
    "world_changed",
    "world_blocked",
    "world_failed",
    "self_changed",
    "self_blocked",
}
_WRITEBACK_STATUSES = {
    "written",
    "written_blocked_outcome",
    "written_identity_change",
    "written_unresolved_outcome",
}
_CONTINUITY_KINDS = {
    "external_action",
    "blocked_action",
    "failed_action",
    "identity_change",
    "blocked_identity_change",
}
_TARGET_MEMORY_FAMILIES = {
    "episodic",
    "autobiographical",
    "semantic",
}


@dataclass(frozen=True)
class ExperienceWritebackConfig:
    """Expose the confirmed initialization and learned-policy surface for writeback."""

    legal_min_priority: float
    legal_max_priority: float
    writeback_bootstrap_id: str
    mandatory_learned_parameters: tuple[ExperienceWritebackLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "continuity_classification_policy",
            "consolidation_priority_policy",
            "autobiographical_salience_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise ExperienceWritebackError(
                "Experience-writeback config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval(
            "ExperienceWritebackConfig.legal_min_priority",
            self.legal_min_priority,
        )
        _validate_unit_interval(
            "ExperienceWritebackConfig.legal_max_priority",
            self.legal_max_priority,
        )
        if self.legal_min_priority > self.legal_max_priority:
            raise ExperienceWritebackError("Experience-writeback priority range is inverted")
        if not self.writeback_bootstrap_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackConfig must declare a non-empty writeback_bootstrap_id"
            )


@dataclass(frozen=True)
class ExperienceWritebackRequest:
    """Explicit normalized writeback request for one continuity-relevant upstream outcome."""

    request_id: str
    source_outcome_kind: ExperienceSourceOutcomeKind
    source_outcome_id: str
    source_outcome_status: str
    outcome_class: ContinuityOutcomeClass
    source_provenance: Mapping[str, object]
    requested_effect_summary: str
    applied_effect_summary: str
    reason_trace: tuple[str, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare a non-empty request_id"
            )
        if self.source_outcome_kind not in _SOURCE_OUTCOME_KINDS:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest source_outcome_kind must use the fixed taxonomy"
            )
        if not self.source_outcome_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare a non-empty source_outcome_id"
            )
        if not self.source_outcome_status:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare a non-empty source_outcome_status"
            )
        if self.outcome_class not in _OUTCOME_CLASSES:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest outcome_class must use the fixed taxonomy"
            )
        if not self.requested_effect_summary:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare a non-empty requested_effect_summary"
            )
        if not self.applied_effect_summary:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare a non-empty applied_effect_summary"
            )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare non-empty reason_trace items"
            )
        provenance = MappingProxyType(dict(self.source_provenance))
        if not provenance:
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest must declare non-empty source_provenance"
            )
        link_keys = (
            "origin_thought_id",
            "proposal_id",
            "decision_id",
            "revision_id",
            "source_request_id",
        )
        if not any(isinstance(provenance.get(key), str) and provenance.get(key) for key in link_keys):
            raise ExperienceWritebackError(
                "ExperienceWritebackRequest source_provenance must preserve upstream linkage ids"
            )
        object.__setattr__(self, "source_provenance", provenance)


@dataclass(frozen=True)
class ContinuityEvidencePacket:
    """Immutable continuity-bearing packet published by the writeback owner."""

    packet_id: str
    continuity_kind: ContinuityKind
    source_outcome_kind: ExperienceSourceOutcomeKind
    source_outcome_id: str
    outcome_class: ContinuityOutcomeClass
    summary: str
    requested_effect_summary: str
    applied_effect_summary: str
    reason_trace: tuple[str, ...]
    source_provenance: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.packet_id:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket must declare a non-empty packet_id"
            )
        if self.continuity_kind not in _CONTINUITY_KINDS:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket continuity_kind must use the fixed taxonomy"
            )
        if self.source_outcome_kind not in _SOURCE_OUTCOME_KINDS:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket source_outcome_kind must use the fixed taxonomy"
            )
        if not self.source_outcome_id:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket must declare a non-empty source_outcome_id"
            )
        if self.outcome_class not in _OUTCOME_CLASSES:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket outcome_class must use the fixed taxonomy"
            )
        for attr_name in ("summary", "requested_effect_summary", "applied_effect_summary"):
            if not getattr(self, attr_name):
                raise ExperienceWritebackError(
                    f"ContinuityEvidencePacket must declare a non-empty {attr_name}"
                )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket must declare non-empty reason_trace items"
            )
        provenance = MappingProxyType(dict(self.source_provenance))
        if not provenance:
            raise ExperienceWritebackError(
                "ContinuityEvidencePacket must declare non-empty source_provenance"
            )
        object.__setattr__(self, "source_provenance", provenance)


@dataclass(frozen=True)
class ConsolidationCandidate:
    """Immutable bounded consolidation handoff candidate derived from one continuity packet."""

    candidate_id: str
    target_memory_family: TargetMemoryFamily
    priority_hint: float
    salience_reason: str
    continuity_packet: ContinuityEvidencePacket

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ExperienceWritebackError(
                "ConsolidationCandidate must declare a non-empty candidate_id"
            )
        if self.target_memory_family not in _TARGET_MEMORY_FAMILIES:
            raise ExperienceWritebackError(
                "ConsolidationCandidate target_memory_family must use the fixed taxonomy"
            )
        _validate_unit_interval(
            "ConsolidationCandidate.priority_hint",
            self.priority_hint,
        )
        if not self.salience_reason:
            raise ExperienceWritebackError(
                "ConsolidationCandidate must declare a non-empty salience_reason"
            )


@dataclass(frozen=True)
class ExperienceWritebackResult:
    """Immutable published writeback result for one continuity-relevant upstream outcome."""

    result_id: str
    source_request_id: str
    status: ExperienceWritebackStatus
    continuity_packet: ContinuityEvidencePacket
    consolidation_candidates: tuple[ConsolidationCandidate, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult must declare a non-empty result_id"
            )
        if not self.source_request_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult must declare a non-empty source_request_id"
            )
        if self.status not in _WRITEBACK_STATUSES:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult status must use the fixed taxonomy"
            )
        candidates = tuple(self.consolidation_candidates)
        if not candidates:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult must publish at least one consolidation candidate"
            )
        families = [candidate.target_memory_family for candidate in candidates]
        if len(set(families)) != len(families):
            raise ExperienceWritebackError(
                "ExperienceWritebackResult consolidation candidates must not duplicate target families"
            )
        object.__setattr__(self, "consolidation_candidates", candidates)


@dataclass(frozen=True)
class PublishExperienceWritebackOp:
    """Runtime-visible publication op for one experience-writeback result."""

    op_name: str
    owner: str
    result_id: str
    status: ExperienceWritebackStatus
    continuity_kind: ContinuityKind


@dataclass(frozen=True)
class PublishConsolidationCandidateOp:
    """Runtime-visible publication op for one consolidation candidate."""

    op_name: str
    owner: str
    result_id: str
    candidate_id: str
    target_memory_family: TargetMemoryFamily
    priority_hint: float


@runtime_checkable
class ExperienceWritebackAPI(Protocol):
    """Owner: execution writeback and autobiographical consolidation API."""

    def write_experience(
        self,
        request: ExperienceWritebackRequest,
    ) -> ExperienceWritebackResult:
        """Return one formal continuity-preserving writeback result."""

    def build_publish_experience_writeback_op(
        self,
        result: ExperienceWritebackResult,
    ) -> PublishExperienceWritebackOp:
        """Return one publication op describing experience-writeback publication."""

    def build_publish_consolidation_candidate_op(
        self,
        result: ExperienceWritebackResult,
        candidate: ConsolidationCandidate,
    ) -> PublishConsolidationCandidateOp:
        """Return one publication op describing one consolidation-candidate handoff."""