"""Owner: action proposal externalization contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.internal_thought import ThoughtCycleResult

from .contracts import (
    ActionExternalizationAPI,
    ActionExternalizationConfig,
    ActionExternalizationError,
    EquivalentBridgeEvidence,
    NormalizedThoughtActionProposal,
    PublishThoughtExternalizationOp,
    PublishThoughtExternalizationRejectionOp,
    RequestThoughtExternalizationOp,
    ThoughtExternalizationRequest,
    ThoughtExternalizationResult,
)


def _validate_thought_result(thought_cycle_result: ThoughtCycleResult) -> None:
    if not thought_cycle_result.result_id:
        raise ActionExternalizationError("ThoughtCycleResult must declare a non-empty result_id")
    if thought_cycle_result.execution_status != "completed":
        raise ActionExternalizationError(
            "Action externalization requires a completed ThoughtCycleResult"
        )
    if thought_cycle_result.thought is None:
        raise ActionExternalizationError(
            "Action externalization requires ThoughtCycleResult to publish thought content"
        )


def _validate_request(
    thought_cycle_result: ThoughtCycleResult,
    request: ThoughtExternalizationRequest,
) -> None:
    if request.source_thought_cycle_result_id != thought_cycle_result.result_id:
        raise ActionExternalizationError(
            "ThoughtExternalizationRequest must preserve the source thought-cycle result id"
        )
    if request.proposal_carrier_present != (thought_cycle_result.action_proposal is not None):
        raise ActionExternalizationError(
            "ThoughtExternalizationRequest must preserve whether an action proposal carrier is present"
        )


@runtime_checkable
class ThoughtExternalizationPath(Protocol):
    def externalize(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
        config: ActionExternalizationConfig,
    ) -> ThoughtExternalizationResult:
        """Return one thought externalization result from validated bridge inputs."""


@dataclass
class FirstVersionThoughtExternalizationPath(ThoughtExternalizationPath):
    """Owner-private deterministic first-version externalization path."""

    owner_path: str = "thought_action_bridge"

    def externalize(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
        config: ActionExternalizationConfig,
    ) -> ThoughtExternalizationResult:
        del config
        proposal = thought_cycle_result.action_proposal
        if proposal is None:
            if thought_cycle_result.continuation_requested:
                return ThoughtExternalizationResult(
                    result_id=f"thought-externalization-result:{request.request_id}",
                    source_request_id=request.request_id,
                    status="no_externalization",
                    normalized_proposal=None,
                    bridge_rejection_reason=None,
                    equivalent_evidence=None,
                    tick_id=request.tick_id,
                )
            evidence = EquivalentBridgeEvidence(
                origin_thought_id=thought_cycle_result.thought.thought_id,
                bridge_evidence_kind="completed_thought_without_explicit_action",
                reason_trace=("completed_thought_without_action_proposal",),
                candidate_summary={
                    "thought_type": thought_cycle_result.thought.thought_type,
                    "trigger_reason": thought_cycle_result.trigger_reason,
                },
            )
            return ThoughtExternalizationResult(
                result_id=f"thought-externalization-result:{request.request_id}",
                source_request_id=request.request_id,
                status="equivalent_evidence_only",
                normalized_proposal=None,
                bridge_rejection_reason=None,
                equivalent_evidence=evidence,
                tick_id=request.tick_id,
            )

        if not proposal.preferred_channels:
            return self._rejected_result(request, "missing_candidate_channels")
        # R85/D2a: op-aware validation (required params, including a reply's outbound_text/target_user_id,
        # and user-visibility) is the planner's responsibility - only `13` has the driver's per-op spec
        # through the channel-state snapshot. `12` performs structural normalization only.

        normalized = NormalizedThoughtActionProposal(
            proposal_id=proposal.proposal_id,
            origin_thought_id=thought_cycle_result.thought.thought_id,
            owner_path=self.owner_path,
            scope=proposal.scope,
            behavior_name=proposal.behavior_name,
            preferred_op=proposal.requested_op,
            params=self._build_params(proposal, request),
            channel_constraints={
                "preferred_channels": proposal.preferred_channels,
                "channel_hints": dict(request.channel_hint_context),
            },
            outbound_intensity=proposal.outbound_intensity,
            reason_trace=proposal.reason_trace,
            governance_hints=proposal.governance_hints,
        )
        return ThoughtExternalizationResult(
            result_id=f"thought-externalization-result:{request.request_id}",
            source_request_id=request.request_id,
            status="normalized",
            normalized_proposal=normalized,
            bridge_rejection_reason=None,
            equivalent_evidence=None,
            tick_id=request.tick_id,
        )

    def _build_params(self, proposal, request: ThoughtExternalizationRequest) -> dict[str, object]:
        params: dict[str, object] = {}
        if proposal.outbound_text is not None:
            params["outbound_text"] = proposal.outbound_text
        params.update(dict(proposal.op_params))
        params.update(dict(request.target_binding_context))
        return params

    def _rejected_result(
        self,
        request: ThoughtExternalizationRequest,
        reason: str,
    ) -> ThoughtExternalizationResult:
        return ThoughtExternalizationResult(
            result_id=f"thought-externalization-result:{request.request_id}",
            source_request_id=request.request_id,
            status="bridge_rejected",
            normalized_proposal=None,
            bridge_rejection_reason=reason,
            equivalent_evidence=None,
            tick_id=request.tick_id,
        )


@dataclass
class ActionExternalizationEngine(ActionExternalizationAPI):
    """Normalize thought-origin proposal carriers into formal externalization contracts."""

    config: ActionExternalizationConfig
    externalization_path: ThoughtExternalizationPath | None

    def externalize_action_proposal(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
    ) -> ThoughtExternalizationResult:
        _validate_thought_result(thought_cycle_result)
        _validate_request(thought_cycle_result, request)
        if self.externalization_path is None:
            raise ActionExternalizationError(
                "Action externalization requires an explicit bridge capability"
            )
        result = self.externalization_path.externalize(
            thought_cycle_result,
            request,
            self.config,
        )
        if result.source_request_id != request.request_id:
            raise ActionExternalizationError(
                "ThoughtExternalizationResult must preserve the source request id"
            )
        return result

    def build_request_op(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
    ) -> RequestThoughtExternalizationOp:
        _validate_thought_result(thought_cycle_result)
        _validate_request(thought_cycle_result, request)
        return RequestThoughtExternalizationOp(
            op_name="request_thought_externalization",
            owner="action_proposal_externalization_contract",
            request_id=request.request_id,
            thought_cycle_result_id=thought_cycle_result.result_id,
            proposal_carrier_present=request.proposal_carrier_present,
        )

    def build_publish_externalization_op(
        self,
        result: ThoughtExternalizationResult,
    ) -> PublishThoughtExternalizationOp:
        if result.status != "normalized" or result.normalized_proposal is None:
            raise ActionExternalizationError(
                "PublishThoughtExternalizationOp requires a normalized ThoughtExternalizationResult"
            )
        return PublishThoughtExternalizationOp(
            op_name="publish_thought_externalization",
            owner="action_proposal_externalization_contract",
            result_id=result.result_id,
            proposal_id=result.normalized_proposal.proposal_id,
            scope=result.normalized_proposal.scope,
            behavior_name=result.normalized_proposal.behavior_name,
        )

    def build_publish_rejection_op(
        self,
        result: ThoughtExternalizationResult,
    ) -> PublishThoughtExternalizationRejectionOp:
        if result.status != "bridge_rejected" or result.bridge_rejection_reason is None:
            raise ActionExternalizationError(
                "PublishThoughtExternalizationRejectionOp requires a bridge-rejected ThoughtExternalizationResult"
            )
        return PublishThoughtExternalizationRejectionOp(
            op_name="publish_thought_externalization_rejection",
            owner="action_proposal_externalization_contract",
            result_id=result.result_id,
            bridge_rejection_reason=result.bridge_rejection_reason,
        )
