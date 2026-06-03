"""Owner: internal thought loop.

Ships two fired-path thought implementations:

1. `FirstVersionInternalThoughtPath` - deterministic content synthesis (test/default-off).
2. `LlmBackedInternalThoughtPath` - real cognition content from the `25` LLM gateway.

Both paths share one owner-private judgment helper (`_derive_thought_judgment`) so the
sufficiency, continuation, recall-intent, memory-handoff, and proposal decisions stay owned
by this owner and remain reproducible given a fixed thought content. The model supplies
content only; it never owns judgment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.llm import LlmGatewayAPI, LlmMessage, LlmRequest
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


@dataclass(frozen=True)
class _ThoughtJudgment:
    """Owner-private judgment outcome shared by every internal-thought path.

    This is the single source of the owner's fired-cycle decisions. It is computed from the
    retrieval window, the continuation state, the request, and the produced thought content.
    It is deterministic given those inputs, so any path (deterministic or LLM-backed) yields
    reproducible judgment once content is fixed.
    """

    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    recall_intent: str
    continuation_pressure_delta: float
    memory_handoff: MemoryHandoffDirective | None
    action_proposal: ThoughtActionProposalCarrier | None
    self_revision_proposal: SelfRevisionProposalCarrier | None


def _derive_thought_judgment(
    retrieval_bundle: ThoughtWindowBundle,
    continuation_state: ContinuationPressureState,
    request: InternalThoughtRequest,
    thought: ThoughtContent,
) -> _ThoughtJudgment:
    """Owner: internal thought loop.

    Purpose:
        Decide the owner-held fired-cycle judgment (sufficiency, continuation, recall intent,
        memory handoff, action proposal, self-revision proposal) from the retrieval window,
        continuation state, request, and the produced thought content.

    Inputs:
        `retrieval_bundle` - the directed-retrieval thought window for the cycle.
        `continuation_state` - the current continuation-pressure state.
        `request` - the validated fired-path request.
        `thought` - the produced thought content (deterministic or LLM-derived).

    Returns:
        A `_ThoughtJudgment` carrying every owner-held decision for the cycle.

    Notes:
        Judgment is owned here, never by the model or the gateway. It is deterministic given
        the inputs, so the same thought content always yields the same judgment.
    """

    short_term = retrieval_bundle.short_term_context
    mid_term = retrieval_bundle.mid_term_hits
    autobiographical = retrieval_bundle.autobiographical_hits
    long_term = retrieval_bundle.long_term_hits
    total_hits = len(short_term) + len(mid_term) + len(long_term) + len(autobiographical)
    sufficiency_level = min(
        1.0,
        0.35 + 0.20 * len(short_term) + 0.15 * len(mid_term) + 0.10 * len(autobiographical),
    )
    continuation_requested = continuation_state.active or total_hits <= 1
    continuation_reason = "need_more_context" if continuation_requested else "sufficient_for_current_cycle"
    recall_intent = (
        "continue retrieval around current unresolved thought"
        if continuation_requested
        else ""
    )
    continuation_pressure_delta = 0.35 if continuation_requested else 0.0

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
    return _ThoughtJudgment(
        sufficiency_level=sufficiency_level,
        continuation_requested=continuation_requested,
        continuation_reason=continuation_reason,
        recall_intent=recall_intent,
        continuation_pressure_delta=continuation_pressure_delta,
        memory_handoff=memory_handoff,
        action_proposal=action_proposal,
        self_revision_proposal=self_revision_proposal,
    )


def _assemble_completed_result(
    request: InternalThoughtRequest,
    gate_result: ThoughtGateResult,
    thought: ThoughtContent,
    judgment: _ThoughtJudgment,
) -> ThoughtCycleResult:
    """Owner-private assembly of a successful `completed` thought-cycle result."""

    return ThoughtCycleResult(
        result_id=f"thought-cycle-result:{request.request_id}",
        source_request_id=request.request_id,
        execution_status="completed",
        thought=thought,
        trigger_reason=gate_result.trigger_reason or gate_result.dominant_reason or "fired_gate",
        sufficiency_level=judgment.sufficiency_level,
        continuation_requested=judgment.continuation_requested,
        continuation_reason=judgment.continuation_reason,
        continuation_pressure_delta=judgment.continuation_pressure_delta,
        recall_intent=judgment.recall_intent,
        memory_handoff=judgment.memory_handoff,
        action_proposal=judgment.action_proposal,
        self_revision_proposal=judgment.self_revision_proposal,
        tick_id=request.tick_id,
    )


def _assemble_trace(result: ThoughtCycleResult, *, llm_used: bool, fallback_used: bool) -> InternalThoughtTrace:
    """Owner-private assembly of the bounded trace from a published result."""

    return InternalThoughtTrace(
        triggered=True,
        trigger_reason=result.trigger_reason,
        llm_used=llm_used,
        fallback_used=fallback_used,
        execution_status=result.execution_status,
        sufficiency_level=result.sufficiency_level,
        continuation_requested=result.continuation_requested,
        continuation_reason=result.continuation_reason,
        recall_intent=result.recall_intent,
        action_explicit=result.action_proposal is not None,
        action_parse_status="action_explicit" if result.action_proposal is not None else "no_action",
    )


def _assemble_insufficient_result(
    request: InternalThoughtRequest,
    gate_result: ThoughtGateResult,
    *,
    continuation_reason: str,
    recall_intent: str,
) -> ThoughtCycleResult:
    """Owner-private assembly of an explicit non-success `insufficient_generation` result.

    Used when a path cannot produce usable thought content (for example an empty LLM
    completion). It publishes no `ThoughtContent` and no downstream proposals, consistent
    with the thought execution-status taxonomy. It never fabricates content.
    """

    return ThoughtCycleResult(
        result_id=f"thought-cycle-result:{request.request_id}",
        source_request_id=request.request_id,
        execution_status="insufficient_generation",
        thought=None,
        trigger_reason=gate_result.trigger_reason or gate_result.dominant_reason or "fired_gate",
        sufficiency_level=0.0,
        continuation_requested=True,
        continuation_reason=continuation_reason,
        continuation_pressure_delta=0.35,
        recall_intent=recall_intent,
        memory_handoff=None,
        action_proposal=None,
        self_revision_proposal=None,
        tick_id=request.tick_id,
    )


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
    """Owner-private deterministic first-version thought path.

    Produces thought content by deterministic synthesis (`llm_used=False`). Retained for
    explicit test assembly and as a reproducible reference; it is no longer the default
    production path once an LLM-backed path is bound by composition.
    """

    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        del config
        thought = ThoughtContent(
            thought_id=f"thought:{request.request_id}",
            thought_type="reflective_retrieval_synthesis",
            content=self._render_content(request, retrieval_bundle),
            source_path="deterministic_first_version",
            llm_used=False,
            fallback_used=False,
        )
        judgment = _derive_thought_judgment(retrieval_bundle, continuation_state, request, thought)
        result = _assemble_completed_result(request, gate_result, thought, judgment)
        trace = _assemble_trace(result, llm_used=False, fallback_used=False)
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
class LlmBackedInternalThoughtPath(InternalThoughtPath):
    """Owner-private LLM-backed thought path.

    Owner: internal thought loop.

    Purpose:
        Source thought content from the `25` LLM gateway through a neutral request, then run
        the shared owner-held judgment to produce the formal thought-cycle result. The model
        supplies content only; sufficiency, continuation, and proposal decisions stay owned
        by this owner.

    Failure semantics:
        A gateway failure (`LlmError`) propagates as a hard stop; this path never fabricates
        content and never falls back to deterministic synthesis. An empty completion yields
        an explicit `insufficient_generation` result with no `ThoughtContent`.

    Notes:
        Adapting the request and retrieval window into neutral `LlmMessage` values is owned
        here (the consumer), so the gateway stays ignorant of cognitive structure.
    """

    gateway: LlmGatewayAPI
    profile_name: str
    thought_source_path: str = "llm_backed_v1"

    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        del config
        llm_request = LlmRequest(
            request_id=f"llm-thought:{request.request_id}",
            target_profile=self.profile_name,
            messages=self._build_messages(request, retrieval_bundle, continuation_state),
            response_format="text",
            metadata={"consumer": "internal_thought", "tick_id": request.tick_id},
        )
        # LlmError (unknown profile, missing key, provider failure) propagates as a hard stop.
        completion = self.gateway.complete(llm_request)
        content_text = completion.output_text.strip()
        if not content_text:
            result = _assemble_insufficient_result(
                request,
                gate_result,
                continuation_reason="empty_llm_completion",
                recall_intent="retry thought generation for current unresolved cycle",
            )
            trace = _assemble_trace(result, llm_used=True, fallback_used=False)
            return result, trace
        thought = ThoughtContent(
            thought_id=f"thought:{request.request_id}",
            thought_type="llm_reflective_synthesis",
            content=content_text,
            source_path=self.thought_source_path,
            llm_used=True,
            fallback_used=False,
        )
        judgment = _derive_thought_judgment(retrieval_bundle, continuation_state, request, thought)
        result = _assemble_completed_result(request, gate_result, thought, judgment)
        trace = _assemble_trace(result, llm_used=True, fallback_used=False)
        return result, trace

    def _build_messages(
        self,
        request: InternalThoughtRequest,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
    ) -> tuple[LlmMessage, ...]:
        """Adapt the fired-path inputs into neutral system/user messages (consumer-owned)."""

        summary = request.prompt_contract_summary
        layer_names = summary.get("layer_names", ())
        if isinstance(layer_names, (tuple, list)):
            layer_text = ", ".join(str(name) for name in layer_names) or "none"
        else:
            layer_text = str(layer_names)
        system_lines = [
            "You are the internal thought process of a continuous, brain-inspired runtime.",
            "Produce one concise internal thought for the current cycle.",
            "Do not perform theatrical self-narration; reflect the current state and context only.",
            f"Active prompt-contract layers: {layer_text}.",
        ]
        system_message = LlmMessage(role="system", content="\n".join(system_lines))

        user_lines = [f"Internal state: {request.internal_state_summary}"]
        if retrieval_bundle.short_term_context:
            user_lines.append(f"Current context: {retrieval_bundle.short_term_context[0].summary}")
        if retrieval_bundle.mid_term_hits:
            user_lines.append(f"Mid-term memory: {retrieval_bundle.mid_term_hits[0].summary}")
        if retrieval_bundle.autobiographical_hits:
            user_lines.append(
                f"Autobiographical anchor: {retrieval_bundle.autobiographical_hits[0].summary}"
            )
        user_lines.append(
            "Continuation pressure is "
            + ("active" if continuation_state.active else "inactive")
            + " for this cycle."
        )
        user_message = LlmMessage(role="user", content="\n".join(user_lines))
        return (system_message, user_message)


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
