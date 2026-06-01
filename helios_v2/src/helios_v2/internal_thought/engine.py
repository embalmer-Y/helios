"""Owner: internal thought loop."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.thought_gating import ContinuationPressureState, ThoughtGateResult

from .contracts import (
    InternalThoughtAPI,
    InternalThoughtConfig,
    InternalThoughtError,
    InternalThoughtRequest,
    InternalThoughtTrace,
    MemoryHandoffDirective,
    PublishThoughtCycleResultOp,
    RunInternalThoughtOp,
    SelfRevisionProposalCarrier,
    ThoughtActionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
)


def _validate_gate_result(gate_result: ThoughtGateResult) -> None:
    if not gate_result.result_id:
        raise InternalThoughtError("ThoughtGateResult must declare a non-empty result_id")
    if gate_result.decision != "fire":
        raise InternalThoughtError("Internal thought requires a fired ThoughtGateResult")


def _validate_retrieval_bundle(bundle: ThoughtWindowBundle, request: InternalThoughtRequest) -> None:
    if not bundle.bundle_id:
        raise InternalThoughtError("ThoughtWindowBundle must declare a non-empty bundle_id")
    if bundle.bundle_id != request.source_retrieval_bundle_id:
        raise InternalThoughtError(
            "InternalThoughtRequest must preserve the source retrieval-bundle id of the current cycle"
        )


def _validate_request(gate_result: ThoughtGateResult, request: InternalThoughtRequest) -> None:
    if request.source_gate_result_id != gate_result.result_id:
        raise InternalThoughtError(
            "InternalThoughtRequest must preserve the source gate-result id of the current cycle"
        )


def _validate_continuation_alignment(
    continuation_state: ContinuationPressureState,
    request: InternalThoughtRequest,
) -> None:
    if continuation_state.active != request.source_continuation_active:
        raise InternalThoughtError("InternalThoughtRequest must preserve the current continuation active flag")


@runtime_checkable
class InternalThoughtPath(Protocol):
    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        """Return one thought-cycle result and one trace from validated fired-path input."""


@dataclass
class FirstVersionInternalThoughtPath(InternalThoughtPath):
    """Owner-private deterministic first-version thought path."""

    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        del config
        short_term = retrieval_bundle.short_term_context
        mid_term = retrieval_bundle.mid_term_hits
        autobiographical = retrieval_bundle.autobiographical_hits
        long_term = retrieval_bundle.long_term_hits
        total_hits = len(short_term) + len(mid_term) + len(long_term) + len(autobiographical)
        sufficiency_level = min(1.0, 0.35 + 0.20 * len(short_term) + 0.15 * len(mid_term) + 0.10 * len(autobiographical))
        continuation_requested = continuation_state.active or total_hits <= 1
        continuation_reason = "need_more_context" if continuation_requested else "sufficient_for_current_cycle"
        recall_intent = (
            "continue retrieval around current unresolved thought"
            if continuation_requested
            else ""
        )
        continuation_pressure_delta = 0.35 if continuation_requested else 0.0
        thought = ThoughtContent(
            thought_id=f"thought:{request.request_id}",
            thought_type="reflective_retrieval_synthesis",
            content=self._render_content(request, retrieval_bundle),
            source_path="deterministic_first_version",
            llm_used=False,
            fallback_used=False,
        )
        memory_handoff = None
        action_proposal = None
        self_revision_proposal = None
        if continuation_requested:
            selected_memory_refs = tuple(hit.memory_id for hit in mid_term[:1] + autobiographical[:1])
            memory_handoff = MemoryHandoffDirective(
                recall_intent=recall_intent,
                selected_memory_refs=selected_memory_refs,
                saved_for_next_tick=True,
                source_thought_id=thought.thought_id,
            )
        else:
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name="reply_message",
                requested_op="reply_message",
                preferred_channels=("cli",),
                outbound_text=thought.content,
                outbound_intensity=0.75,
                reason_trace=("thought judged sufficient for current cycle",),
                governance_hints={"requires_identity_review": False},
            )
        if autobiographical and sufficiency_level >= 0.75:
            self_revision_proposal = SelfRevisionProposalCarrier(
                proposal_id=f"self-revision:{request.request_id}",
                revision_kind="identity_narrative_refinement",
                requested_change_summary="Refine autobiographical self-description using current continuity evidence",
                reason_trace="autobiographical continuity surfaced during internal thought",
            )
        result = ThoughtCycleResult(
            result_id=f"thought-cycle-result:{request.request_id}",
            source_request_id=request.request_id,
            execution_status="completed",
            thought=thought,
            trigger_reason=gate_result.trigger_reason or gate_result.dominant_reason or "fired_gate",
            sufficiency_level=sufficiency_level,
            continuation_requested=continuation_requested,
            continuation_reason=continuation_reason,
            continuation_pressure_delta=continuation_pressure_delta,
            recall_intent=recall_intent,
            memory_handoff=memory_handoff,
            action_proposal=action_proposal,
            self_revision_proposal=self_revision_proposal,
            tick_id=request.tick_id,
        )
        trace = InternalThoughtTrace(
            triggered=True,
            trigger_reason=result.trigger_reason,
            llm_used=False,
            fallback_used=False,
            execution_status=result.execution_status,
            sufficiency_level=result.sufficiency_level,
            continuation_requested=result.continuation_requested,
            continuation_reason=result.continuation_reason,
            recall_intent=result.recall_intent,
            action_explicit=result.action_proposal is not None,
            action_parse_status="action_explicit" if result.action_proposal is not None else "no_action",
        )
        return result, trace

    def _render_content(self, request: InternalThoughtRequest, retrieval_bundle: ThoughtWindowBundle) -> str:
        fragments = [request.internal_state_summary]
        if retrieval_bundle.short_term_context:
            fragments.append(f"Current context: {retrieval_bundle.short_term_context[0].summary}")
        if retrieval_bundle.mid_term_hits:
            fragments.append(f"Mid-term memory: {retrieval_bundle.mid_term_hits[0].summary}")
        if retrieval_bundle.autobiographical_hits:
            fragments.append(f"Autobiographical anchor: {retrieval_bundle.autobiographical_hits[0].summary}")
        return " | ".join(fragments)


@dataclass
class InternalThoughtEngine(InternalThoughtAPI):
    """Execute one fired internal-thought cycle using an injected private thought path."""

    config: InternalThoughtConfig
    thought_path: InternalThoughtPath | None

    def run_thought_cycle(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        _validate_retrieval_bundle(retrieval_bundle, request)
        _validate_continuation_alignment(continuation_state, request)
        if self.thought_path is None:
            raise InternalThoughtError("Internal thought requires an explicit thought capability")
        result, trace = self.thought_path.run(
            gate_result,
            retrieval_bundle,
            continuation_state,
            request,
            self.config,
        )
        if result.source_request_id != request.request_id:
            raise InternalThoughtError("ThoughtCycleResult must preserve the source request id")
        if trace.execution_status != result.execution_status:
            raise InternalThoughtError("InternalThoughtTrace must preserve the published execution status")
        return result, trace

    def build_run_op(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        request: InternalThoughtRequest,
    ) -> RunInternalThoughtOp:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        _validate_retrieval_bundle(retrieval_bundle, request)
        return RunInternalThoughtOp(
            op_name="run_internal_thought",
            owner="internal_thought_loop_owner",
            request_id=request.request_id,
            gate_result_id=gate_result.result_id,
            retrieval_bundle_id=retrieval_bundle.bundle_id,
        )

    def build_publish_result_op(
        self,
        result: ThoughtCycleResult,
    ) -> PublishThoughtCycleResultOp:
        if not result.result_id:
            raise InternalThoughtError("ThoughtCycleResult contains incomplete publication identity")
        return PublishThoughtCycleResultOp(
            op_name="publish_thought_cycle_result",
            owner="internal_thought_loop_owner",
            result_id=result.result_id,
            execution_status=result.execution_status,
            continuation_requested=result.continuation_requested,
            has_action_proposal=result.action_proposal is not None,
            has_self_revision_proposal=result.self_revision_proposal is not None,
        )
