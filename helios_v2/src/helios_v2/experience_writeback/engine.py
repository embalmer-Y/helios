"""Owner: execution writeback and autobiographical consolidation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import (
    ConsolidationCandidate,
    ContinuityEvidencePacket,
    ExperienceWritebackAPI,
    ExperienceWritebackConfig,
    ExperienceWritebackError,
    ExperienceWritebackRequest,
    ExperienceWritebackResult,
    PublishConsolidationCandidateOp,
    PublishExperienceWritebackOp,
)


def _validate_request(request: ExperienceWritebackRequest) -> None:
    if request.outcome_class in {"world_changed", "world_blocked", "world_failed"}:
        if request.source_outcome_kind != "planner_bridge":
            raise ExperienceWritebackError(
                "World-outcome writeback requests must originate from planner_bridge"
            )
    if request.outcome_class in {"self_changed", "self_blocked"}:
        if request.source_outcome_kind != "identity_governance":
            raise ExperienceWritebackError(
                "Self-outcome writeback requests must originate from identity_governance"
            )
    if request.outcome_class == "internal_only":
        if request.source_outcome_kind != "internal_thought_cycle":
            raise ExperienceWritebackError(
                "Internal-only writeback requests must originate from internal_thought_cycle"
            )


@runtime_checkable
class ExperienceWritebackPath(Protocol):
    def write(
        self,
        request: ExperienceWritebackRequest,
        config: ExperienceWritebackConfig,
    ) -> ExperienceWritebackResult:
        """Return one deterministic writeback result for one normalized request."""


@dataclass
class FirstVersionExperienceWritebackPath(ExperienceWritebackPath):
    """Owner-private deterministic first-version writeback path."""

    def write(
        self,
        request: ExperienceWritebackRequest,
        config: ExperienceWritebackConfig,
    ) -> ExperienceWritebackResult:
        continuity_kind = self._continuity_kind_for(request.outcome_class)
        status = self._status_for(request.outcome_class)
        continuity_packet = ContinuityEvidencePacket(
            packet_id=f"continuity-packet:{request.request_id}",
            continuity_kind=continuity_kind,
            source_outcome_kind=request.source_outcome_kind,
            source_outcome_id=request.source_outcome_id,
            outcome_class=request.outcome_class,
            summary=self._build_summary(request),
            requested_effect_summary=request.requested_effect_summary,
            applied_effect_summary=request.applied_effect_summary,
            reason_trace=request.reason_trace,
            source_provenance=request.source_provenance,
        )
        candidates = tuple(
            ConsolidationCandidate(
                candidate_id=f"consolidation-candidate:{family}:{request.request_id}",
                target_memory_family=family,
                priority_hint=self._priority_for(request.outcome_class, family, config),
                salience_reason=self._salience_reason_for(request.outcome_class, family),
                continuity_packet=continuity_packet,
            )
            for family in ("episodic", "autobiographical", "semantic")
        )
        return ExperienceWritebackResult(
            result_id=f"experience-writeback-result:{request.request_id}",
            source_request_id=request.request_id,
            status=status,
            continuity_packet=continuity_packet,
            consolidation_candidates=candidates,
            tick_id=request.tick_id,
        )

    def _continuity_kind_for(self, outcome_class: str) -> str:
        return {
            "world_changed": "external_action",
            "world_blocked": "blocked_action",
            "world_failed": "failed_action",
            "self_changed": "identity_change",
            "self_blocked": "blocked_identity_change",
            "internal_only": "internal_thought_cycle",
        }[outcome_class]

    def _status_for(self, outcome_class: str) -> str:
        return {
            "world_changed": "written",
            "world_blocked": "written_blocked_outcome",
            "world_failed": "written_unresolved_outcome",
            "self_changed": "written_identity_change",
            "self_blocked": "written_unresolved_outcome",
            "internal_only": "written_internal_only",
        }[outcome_class]

    def _build_summary(self, request: ExperienceWritebackRequest) -> str:
        prefix = {
            "world_changed": "External action changed the world",
            "world_blocked": "External action remained blocked",
            "world_failed": "External action failed after selection",
            "self_changed": "Identity governance changed the self",
            "self_blocked": "Identity governance rejected the proposed self-change",
            "internal_only": "A thinking cycle concluded without outward action",
        }[request.outcome_class]
        return (
            f"{prefix}: requested {request.requested_effect_summary}; "
            f"applied {request.applied_effect_summary}"
        )

    def _priority_for(
        self,
        outcome_class: str,
        family: str,
        config: ExperienceWritebackConfig,
    ) -> float:
        base_priorities = {
            "world_changed": {"episodic": 0.85, "autobiographical": 0.70, "semantic": 0.55},
            "world_blocked": {"episodic": 0.72, "autobiographical": 0.68, "semantic": 0.50},
            "world_failed": {"episodic": 0.78, "autobiographical": 0.72, "semantic": 0.58},
            "self_changed": {"episodic": 0.65, "autobiographical": 0.92, "semantic": 0.76},
            "self_blocked": {"episodic": 0.60, "autobiographical": 0.82, "semantic": 0.60},
            "internal_only": {"episodic": 0.55, "autobiographical": 0.50, "semantic": 0.40},
        }
        base_value = base_priorities[outcome_class][family]
        return max(config.legal_min_priority, min(config.legal_max_priority, base_value))

    def _salience_reason_for(self, outcome_class: str, family: str) -> str:
        salience_reasons = {
            "world_changed": {
                "episodic": "preserve the visible external consequence",
                "autobiographical": "retain world-facing continuity in self history",
                "semantic": "extract stable task or preference learning",
            },
            "world_blocked": {
                "episodic": "preserve the blocked action attempt",
                "autobiographical": "retain continuity around prevented outward behavior",
                "semantic": "extract stable rejection or routing constraints",
            },
            "world_failed": {
                "episodic": "preserve the failed execution outcome",
                "autobiographical": "retain continuity around failed outward action",
                "semantic": "extract stable execution failure lessons",
            },
            "self_changed": {
                "episodic": "preserve the accepted self-revision event",
                "autobiographical": "retain identity-continuity mutation",
                "semantic": "extract stable self-model updates",
            },
            "self_blocked": {
                "episodic": "preserve the rejected self-revision event",
                "autobiographical": "retain continuity around denied self-change",
                "semantic": "extract stable governance constraints",
            },
            "internal_only": {
                "episodic": "preserve that a thinking cycle occurred without outward action",
                "autobiographical": "retain continuity of an internally consequential cycle",
                "semantic": "extract stable patterns of internal-only deliberation",
            },
        }
        return salience_reasons[outcome_class][family]


@dataclass
class ExperienceWritebackEngine(ExperienceWritebackAPI):
    """Transform normalized runtime outcomes into continuity-preserving writeback results."""

    config: ExperienceWritebackConfig
    writeback_path: ExperienceWritebackPath | None

    def write_experience(
        self,
        request: ExperienceWritebackRequest,
    ) -> ExperienceWritebackResult:
        _validate_request(request)
        if self.writeback_path is None:
            raise ExperienceWritebackError(
                "Experience writeback requires an explicit writeback capability"
            )
        result = self.writeback_path.write(request, self.config)
        if result.source_request_id != request.request_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult must preserve the source request id"
            )
        if result.continuity_packet.source_outcome_id != request.source_outcome_id:
            raise ExperienceWritebackError(
                "ExperienceWritebackResult must preserve the source outcome id"
            )
        return result

    def build_publish_experience_writeback_op(
        self,
        result: ExperienceWritebackResult,
    ) -> PublishExperienceWritebackOp:
        return PublishExperienceWritebackOp(
            op_name="publish_experience_writeback",
            owner="execution_writeback_and_autobiographical_consolidation",
            result_id=result.result_id,
            status=result.status,
            continuity_kind=result.continuity_packet.continuity_kind,
        )

    def build_publish_consolidation_candidate_op(
        self,
        result: ExperienceWritebackResult,
        candidate: ConsolidationCandidate,
    ) -> PublishConsolidationCandidateOp:
        return PublishConsolidationCandidateOp(
            op_name="publish_consolidation_candidate",
            owner="execution_writeback_and_autobiographical_consolidation",
            result_id=result.result_id,
            candidate_id=candidate.candidate_id,
            target_memory_family=candidate.target_memory_family,
            priority_hint=candidate.priority_hint,
        )