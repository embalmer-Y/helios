"""Owner: identity governance and self-revision integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.internal_thought import ThoughtCycleResult

from .contracts import (
    AppliedIdentityState,
    EvaluateIdentityGovernanceOp,
    GovernancePressureState,
    IdentityGovernanceAPI,
    IdentityGovernanceConfig,
    IdentityGovernanceError,
    IdentityGovernanceRequest,
    IdentityGovernanceResult,
    NormalizedSelfRevisionProposal,
    PublishAppliedIdentityStateOp,
    PublishGovernancePressureOp,
    PublishRevisionDecisionOp,
    RevisionDecision,
)


def _validate_thought_result(thought_cycle_result: ThoughtCycleResult) -> None:
    if not thought_cycle_result.result_id:
        raise IdentityGovernanceError("ThoughtCycleResult must declare a non-empty result_id")
    if thought_cycle_result.execution_status != "completed":
        raise IdentityGovernanceError("Identity governance requires a completed ThoughtCycleResult")
    if thought_cycle_result.thought is None:
        raise IdentityGovernanceError(
            "Identity governance requires ThoughtCycleResult to publish thought content"
        )


def _validate_request(
    thought_cycle_result: ThoughtCycleResult,
    request: IdentityGovernanceRequest,
) -> None:
    if request.source_thought_cycle_result_id != thought_cycle_result.result_id:
        raise IdentityGovernanceError(
            "IdentityGovernanceRequest must preserve the source thought-cycle result id"
        )
    if request.proposal_present != (thought_cycle_result.self_revision_proposal is not None):
        raise IdentityGovernanceError(
            "IdentityGovernanceRequest must preserve whether a self-revision proposal is present"
        )
    if request.proposal_present:
        proposal = thought_cycle_result.self_revision_proposal
        assert proposal is not None
        if request.source_proposal_id != proposal.proposal_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceRequest must preserve the source self-revision proposal id"
            )


@runtime_checkable
class IdentityGovernancePath(Protocol):
    def evaluate(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
        config: IdentityGovernanceConfig,
    ) -> IdentityGovernanceResult:
        """Return one governance result from validated bridge inputs."""


@dataclass
class FirstVersionIdentityGovernancePath(IdentityGovernancePath):
    """Owner-private deterministic first-version governance path."""

    owner_path: str = "self_revision_governance_bridge"

    def evaluate(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
        config: IdentityGovernanceConfig,
    ) -> IdentityGovernanceResult:
        pressure_state = self._build_pressure_state(request)
        proposal = self._normalize_proposal(thought_cycle_result, request, config)
        if proposal is None:
            decision = RevisionDecision(
                revision_id=f"identity-revision:{request.request_id}",
                proposal_id=request.source_proposal_id or f"missing-self-revision:{request.request_id}",
                origin_thought_id=thought_cycle_result.thought.thought_id,
                status="invalid_proposal",
                requested_change={"invalid_payload": True},
                applied_change={},
                rejection_reason="invalid_self_revision_payload",
                reason_trace=("missing_or_malformed_self_revision_proposal",),
            )
            return IdentityGovernanceResult(
                result_id=f"identity-governance-result:{request.request_id}",
                source_request_id=request.request_id,
                pressure_state=pressure_state,
                revision_decision=decision,
                applied_identity_state=None,
                tick_id=request.tick_id,
            )

        decision, applied_state = self._evaluate_proposal(proposal, pressure_state, request)
        return IdentityGovernanceResult(
            result_id=f"identity-governance-result:{request.request_id}",
            source_request_id=request.request_id,
            pressure_state=pressure_state,
            revision_decision=decision,
            applied_identity_state=applied_state,
            tick_id=request.tick_id,
        )

    def _normalize_proposal(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
        config: IdentityGovernanceConfig,
    ) -> NormalizedSelfRevisionProposal | None:
        del config
        carrier = thought_cycle_result.self_revision_proposal
        if carrier is None or not request.proposal_present:
            return None
        snapshot = dict(request.proposal_snapshot)
        if not snapshot:
            snapshot = self._build_snapshot_from_carrier(carrier)
        revision_type = str(snapshot.get("revision_type", "") or "")
        requested_change = snapshot.get("requested_change", {})
        reason_trace = tuple(
            str(item)
            for item in list(snapshot.get("reason_trace", (carrier.reason_trace,)) or ())
            if str(item)
        )
        confidence = float(snapshot.get("confidence", 0.78) or 0.78)
        try:
            return NormalizedSelfRevisionProposal(
                proposal_id=carrier.proposal_id,
                origin_thought_id=thought_cycle_result.thought.thought_id,
                owner_path=str(snapshot.get("owner_path", self.owner_path) or self.owner_path),
                revision_type=revision_type,
                requested_change=dict(requested_change or {}),
                confidence=confidence,
                scope="identity",
                reason_trace=reason_trace,
            )
        except IdentityGovernanceError:
            return None

    def _build_snapshot_from_carrier(self, carrier) -> dict[str, object]:
        revision_kind = str(carrier.revision_kind or "")
        if revision_kind == "identity_narrative_refinement":
            return {
                "owner_path": self.owner_path,
                "revision_type": "autobiographical_identity_narrative_revision",
                "requested_change": {"narrative_summary": carrier.requested_change_summary},
                "confidence": 0.78,
                "reason_trace": (carrier.reason_trace,),
            }
        if revision_kind == "self_definition_revision":
            return {
                "owner_path": self.owner_path,
                "revision_type": "self_definition_revision",
                "requested_change": {"self_definition": carrier.requested_change_summary},
                "confidence": 0.7,
                "reason_trace": (carrier.reason_trace,),
            }
        return {
            "owner_path": self.owner_path,
            "revision_type": revision_kind,
            "requested_change": {},
            "confidence": 0.5,
            "reason_trace": (carrier.reason_trace,),
        }

    def _evaluate_proposal(
        self,
        proposal: NormalizedSelfRevisionProposal,
        pressure_state: GovernancePressureState,
        request: IdentityGovernanceRequest,
    ) -> tuple[RevisionDecision, AppliedIdentityState | None]:
        reason_trace = list(proposal.reason_trace)
        identity_state = dict(request.identity_state_snapshot)
        if pressure_state.pressure_level == "monitor":
            reason_trace.append("proactive_governance_monitoring")
            reason_trace.append(f"governance_pressure:{pressure_state.pressure_level}")
        low_confidence = proposal.confidence < 0.65
        if (
            pressure_state.pressure_level == "stabilize"
            and low_confidence
            and proposal.revision_type in {"self_definition_revision", "personality_adjustment"}
        ):
            reason_trace.append("proactive_governance_backpressure")
            reason_trace.append(f"governance_pressure:{pressure_state.pressure_level}")
            decision = RevisionDecision(
                revision_id=f"identity-revision:{request.request_id}",
                proposal_id=proposal.proposal_id,
                origin_thought_id=proposal.origin_thought_id,
                status="rejected",
                requested_change=proposal.requested_change,
                applied_change={},
                rejection_reason="governance_backpressure",
                reason_trace=tuple(reason_trace),
            )
            return decision, None

        applied_change: dict[str, object] = {}
        changed_fields: tuple[str, ...] = ()
        rejection_reason = None
        status = "accepted_with_monitoring" if pressure_state.pressure_level == "monitor" else "accepted"
        if proposal.revision_type == "self_definition_revision":
            new_definition = str(proposal.requested_change.get("self_definition", "") or "").strip()
            if not new_definition:
                rejection_reason = "missing_self_definition"
            elif "被设计" in new_definition or "程序" in new_definition:
                rejection_reason = "identity_boundary_violation"
            else:
                identity_state["self_definition"] = new_definition
                applied_change = {"self_definition": new_definition}
                changed_fields = ("self_definition", "current_revision", "revision_history_length")
        elif proposal.revision_type == "personality_adjustment":
            baseline = dict(identity_state.get("personality_baseline", {}) or {})
            requested_baseline = dict(proposal.requested_change.get("personality_baseline", {}) or {})
            sanitized: dict[str, float] = {}
            for key, value in requested_baseline.items():
                if key not in baseline:
                    continue
                sanitized[str(key)] = max(0.5, min(2.0, round(float(value), 4)))
            if not sanitized:
                rejection_reason = "missing_personality_adjustment"
            else:
                updated_baseline = dict(baseline)
                updated_baseline.update(sanitized)
                identity_state["personality_baseline"] = updated_baseline
                applied_change = {"personality_baseline": dict(sanitized)}
                changed_fields = (
                    "personality_baseline",
                    "current_revision",
                    "revision_history_length",
                )
        elif proposal.revision_type == "autobiographical_identity_narrative_revision":
            narrative_summary = str(proposal.requested_change.get("narrative_summary", "") or "").strip()
            if not narrative_summary:
                rejection_reason = "missing_identity_narrative"
            elif "被设计" in narrative_summary or "程序" in narrative_summary:
                rejection_reason = "identity_boundary_violation"
            else:
                identity_metadata = dict(identity_state.get("identity_metadata", {}) or {})
                identity_metadata["autobiographical_identity_narrative"] = {
                    "summary": narrative_summary,
                    "source": proposal.origin_thought_id,
                }
                identity_state["identity_metadata"] = identity_metadata
                applied_change = {
                    "identity_metadata": {
                        "autobiographical_identity_narrative": dict(
                            identity_metadata["autobiographical_identity_narrative"]
                        )
                    }
                }
                changed_fields = (
                    "identity_metadata",
                    "current_revision",
                    "revision_history_length",
                )
        else:
            rejection_reason = "unsupported_revision_type"

        if rejection_reason is not None:
            reason_trace.append(rejection_reason)
            decision = RevisionDecision(
                revision_id=f"identity-revision:{request.request_id}",
                proposal_id=proposal.proposal_id,
                origin_thought_id=proposal.origin_thought_id,
                status="rejected",
                requested_change=proposal.requested_change,
                applied_change={},
                rejection_reason=rejection_reason,
                reason_trace=tuple(reason_trace),
            )
            return decision, None

        revision_id = f"identity-revision:{request.request_id}"
        identity_state["current_revision"] = revision_id
        history_length = int(identity_state.get("revision_history_length", 0) or 0)
        identity_state["revision_history_length"] = history_length + 1
        decision = RevisionDecision(
            revision_id=revision_id,
            proposal_id=proposal.proposal_id,
            origin_thought_id=proposal.origin_thought_id,
            status=status,
            requested_change=proposal.requested_change,
            applied_change=applied_change,
            rejection_reason=None,
            reason_trace=tuple(reason_trace),
        )
        applied_state = AppliedIdentityState(
            revision_id=revision_id,
            current_revision=revision_id,
            identity_state_snapshot=identity_state,
            changed_fields=changed_fields,
        )
        return decision, applied_state

    def _build_pressure_state(self, request: IdentityGovernanceRequest) -> GovernancePressureState:
        summary = dict(request.governance_trace_summary)
        history = [dict(item) for item in request.recent_governance_trace_history]
        if not summary and not history:
            return GovernancePressureState(
                active=False,
                pressure_score=0.0,
                pressure_level="none",
                review_hint="none",
                recent_trace_count=0,
                source_consistency_ratio=0.0,
                recent_trigger_sources=(),
            )

        recent_trace_count = len(history)
        disposition_counts: dict[str, int] = {}
        source_type_counts: dict[str, int] = {}
        trigger_sources_seen: list[str] = []
        for entry in history:
            dominant_disposition = str(entry.get("dominant_disposition", "") or "")
            if dominant_disposition:
                disposition_counts[dominant_disposition] = disposition_counts.get(dominant_disposition, 0) + 1
            source_type = str(entry.get("source_type", "") or entry.get("owner_path", "") or "")
            if source_type:
                source_type_counts[source_type] = source_type_counts.get(source_type, 0) + 1
            for item in list(entry.get("trigger_sources", []) or []):
                value = str(item or "")
                if value and value not in trigger_sources_seen:
                    trigger_sources_seen.append(value)

        recent_trigger_sources = tuple(
            str(item)
            for item in list(trigger_sources_seen or summary.get("recent_trigger_sources", []) or [])
            if str(item)
        )
        recorded_timestamps = [
            float(entry.get("recorded_at_ts", 0.0) or 0.0)
            for entry in history
            if float(entry.get("recorded_at_ts", 0.0) or 0.0) > 0.0
        ]
        dominant_ratio = max(disposition_counts.values(), default=0) / max(recent_trace_count, 1)
        defer_ratio = int(disposition_counts.get("defer", 0) or 0) / max(recent_trace_count, 1)
        reflect_ratio = int(disposition_counts.get("reflect", 0) or 0) / max(recent_trace_count, 1)
        source_consistency_ratio = max(source_type_counts.values(), default=0) / max(recent_trace_count, 1)
        recent_trace_span_seconds = 0.0
        if len(recorded_timestamps) >= 2:
            recent_trace_span_seconds = max(recorded_timestamps[-1] - recorded_timestamps[0], 0.0)
        recent_trace_density_per_minute = 0.0
        if recent_trace_count >= 2 and recent_trace_span_seconds > 0.0:
            recent_trace_density_per_minute = (recent_trace_count - 1) * 60.0 / recent_trace_span_seconds

        pressure_score = min(
            1.0,
            max(recent_trace_count - 1, 0) * 0.08
            + max(recent_trace_count - 4, 0) * 0.14
            + dominant_ratio * 0.14
            + defer_ratio * 0.10
            + reflect_ratio * 0.04
            + (0.06 if recent_trace_count >= 3 and len(recent_trigger_sources) <= 3 else 0.0)
            + (0.05 if recent_trace_count >= 3 and source_consistency_ratio >= 0.67 else 0.0)
        )
        pressure_level = "none"
        review_hint = "none"
        stabilize_ready = (
            pressure_score >= 0.72
            and recent_trace_count >= 5
            and source_consistency_ratio >= 0.67
            and recent_trace_density_per_minute >= 2.4
        )
        if stabilize_ready:
            pressure_level = "stabilize"
            review_hint = "delay_low_confidence_identity_revision"
        elif pressure_score >= 0.45:
            pressure_level = "monitor"
            review_hint = "review_identity_revision_carefully"

        return GovernancePressureState(
            active=pressure_level != "none",
            pressure_score=round(float(pressure_score), 4),
            pressure_level=pressure_level,
            review_hint=review_hint,
            recent_trace_count=recent_trace_count,
            source_consistency_ratio=round(float(source_consistency_ratio), 4),
            recent_trigger_sources=recent_trigger_sources,
        )


@dataclass
class IdentityGovernanceEngine(IdentityGovernanceAPI):
    """Evaluate thought-origin self-revision proposals into formal governance results."""

    config: IdentityGovernanceConfig
    governance_path: IdentityGovernancePath | None

    def evaluate_self_revision(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
    ) -> IdentityGovernanceResult:
        _validate_thought_result(thought_cycle_result)
        _validate_request(thought_cycle_result, request)
        if self.governance_path is None:
            raise IdentityGovernanceError(
                "Identity governance requires an explicit governance capability"
            )
        result = self.governance_path.evaluate(thought_cycle_result, request, self.config)
        if result.source_request_id != request.request_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceResult must preserve the source request id"
            )
        return result

    def build_evaluate_op(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
    ) -> EvaluateIdentityGovernanceOp:
        _validate_thought_result(thought_cycle_result)
        _validate_request(thought_cycle_result, request)
        return EvaluateIdentityGovernanceOp(
            op_name="evaluate_identity_governance",
            owner="identity_governance_self_revision_integration",
            request_id=request.request_id,
            thought_cycle_result_id=thought_cycle_result.result_id,
            proposal_present=request.proposal_present,
        )

    def build_publish_pressure_op(
        self,
        request: IdentityGovernanceRequest,
        pressure_state: GovernancePressureState,
    ) -> PublishGovernancePressureOp:
        return PublishGovernancePressureOp(
            op_name="publish_governance_pressure",
            owner="identity_governance_self_revision_integration",
            request_id=request.request_id,
            pressure_level=pressure_state.pressure_level,
            pressure_score=pressure_state.pressure_score,
            active=pressure_state.active,
        )

    def build_publish_revision_decision_op(
        self,
        decision: RevisionDecision,
    ) -> PublishRevisionDecisionOp:
        return PublishRevisionDecisionOp(
            op_name="publish_revision_decision",
            owner="identity_governance_self_revision_integration",
            revision_id=decision.revision_id,
            status=decision.status,
            origin_thought_id=decision.origin_thought_id,
        )

    def build_publish_applied_identity_state_op(
        self,
        applied_identity_state: AppliedIdentityState,
    ) -> PublishAppliedIdentityStateOp:
        return PublishAppliedIdentityStateOp(
            op_name="publish_applied_identity_state",
            owner="identity_governance_self_revision_integration",
            revision_id=applied_identity_state.revision_id,
            current_revision=applied_identity_state.current_revision,
            changed_fields=applied_identity_state.changed_fields,
        )
