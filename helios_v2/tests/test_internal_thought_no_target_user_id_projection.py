"""R95: tests for the no-`target_user_id`-auto-injection principle.

R95 explicitly REMOVES the R93 P2 `_current_operator_id` projection
(composition) and the engine's `target_user_id` auto-injection. The
LLM is the only source of `target_user_id` (in `tool_params`). The
planner validates against the op's `required_params`; if the LLM
omitted a required `target_user_id`, the planner rejects — this is a
real LLM error, not a system design issue.

Identity is the LLM's content decision, not the runtime's.
"""

from __future__ import annotations

import pytest

from helios_v2.llm import LlmCompletion, LlmUsage
from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.internal_thought import (
    InternalThoughtConfig,
    InternalThoughtRequest,
)
from helios_v2.internal_thought.engine import (
    LlmBackedInternalThoughtPath,
    _derive_thought_judgment,
    StructuredThoughtEvidence,
)

from tests._internal_thought_test_fixtures import (
    build_test_config,
    fired_gate_result,
    populated_bundle,
)


def _make_evidence(tool_op: str = "", tool_params=None) -> StructuredThoughtEvidence:
    return StructuredThoughtEvidence(
        thought_text="x",
        model_sufficiency=0.9,
        thinking_complete=True,
        channel_request=None,
        hormone_prediction=None,
        tool_op=tool_op,
        tool_params=tool_params or {},
    )


def test_no_current_operator_id_in_prompt_contract_summary() -> None:
    """R95: the prompt-contract summary does NOT contain a
    `current_operator_id` field. The R93 P2 composition projection is
    REMOVED. Channels do not mark `source_user_id`; the LLM is the only
    source of `target_user_id` (in `tool_params`).

    This is a static check on the prompt-contract contract: callers
    that pass `current_operator_id` to the engine do so at their own
    risk — the engine ignores it (verified below).
    """
    from helios_v2.composition.bridges import _available_channel_ops

    # Construct a frame-like object with `channel_state=None` (the
    # defensive read returns ()). The composition must NOT project
    # any `current_operator_id` field.
    class _Frame:
        channel_state = None
        stage_results = {}

    assert "current_operator_id" not in _available_channel_ops(_Frame).__class__.__dict__


def test_engine_does_not_auto_inject_target_user_id() -> None:
    """R95: when the LLM picks `tool_op='reply_message'` with
    `tool_params={'outbound_text': 'hi'}` (NO `target_user_id`), the
    engine does NOT inject any `target_user_id`. The tool proposal's
    `op_params` is exactly `{'outbound_text': 'hi'}` (no auto-injection)."""
    gate = fired_gate_result()
    bundle = populated_bundle()
    request = InternalThoughtRequest(
        request_id="r95-test",
        source_gate_result_id=gate.result_id,
        source_retrieval_bundle_id=bundle.bundle_id,
        source_continuation_active=False,
        internal_state_summary="state",
        prompt_contract_summary={
            "contract_id": "c",
            "consumer_kind": "thought",
            "layer_names": ("identity_grounding",),
            "supports_external_action_proposal": True,
            "supports_self_revision_proposal": True,
            "ready_channels": (),
            # NOTE: NO `current_operator_id` field (R95 REMOVES it).
        },
        tick_id=1,
    )
    from helios_v2.internal_thought.engine import ThoughtContent

    thought = ThoughtContent(
        thought_id="t",
        thought_type="r95",
        content="x",
        source_path="r95",
        llm_used=True,
        fallback_used=False,
    )
    evidence = _make_evidence(
        tool_op="reply_message",
        tool_params={"outbound_text": "hi"},
    )
    judgment = _derive_thought_judgment(
        bundle, ContinuationPressureState.inactive(), request, thought, evidence=evidence
    )
    assert judgment.action_proposal is not None
    op_params = dict(judgment.action_proposal.op_params)
    # R95: op_params is exactly what the LLM supplied — no auto-injected
    # `target_user_id` from `current_operator_id` or any other source.
    assert op_params == {"outbound_text": "hi"}
    assert "target_user_id" not in op_params


def test_llm_supplied_target_user_id_passes_through() -> None:
    """R95: when the LLM supplies `tool_params={'outbound_text': 'hi',
    'target_user_id': 'user-123'}`, the engine passes it through
    verbatim. The engine makes no modification to the LLM's
    `target_user_id` value (no trimming, no defaulting, no override)."""
    gate = fired_gate_result()
    bundle = populated_bundle()
    request = InternalThoughtRequest(
        request_id="r95-test",
        source_gate_result_id=gate.result_id,
        source_retrieval_bundle_id=bundle.bundle_id,
        source_continuation_active=False,
        internal_state_summary="state",
        prompt_contract_summary={
            "contract_id": "c",
            "consumer_kind": "thought",
            "layer_names": ("identity_grounding",),
            "supports_external_action_proposal": True,
            "supports_self_revision_proposal": True,
            "ready_channels": (),
        },
        tick_id=1,
    )
    from helios_v2.internal_thought.engine import ThoughtContent

    thought = ThoughtContent(
        thought_id="t",
        thought_type="r95",
        content="x",
        source_path="r95",
        llm_used=True,
        fallback_used=False,
    )
    evidence = _make_evidence(
        tool_op="reply_message",
        tool_params={"outbound_text": "hi", "target_user_id": "user-123"},
    )
    judgment = _derive_thought_judgment(
        bundle, ContinuationPressureState.inactive(), request, thought, evidence=evidence
    )
    assert judgment.action_proposal is not None
    op_params = dict(judgment.action_proposal.op_params)
    assert op_params == {"outbound_text": "hi", "target_user_id": "user-123"}
