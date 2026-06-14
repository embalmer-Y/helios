"""R95: tests for the single-point emit_proposal decision.

R95 collapses the R94 five-branch precedence (explicit_no_action /
tool_intent / reply_explicit_path / explicit_tool_path_via_intent /
compat) into a single `if evidence.tool_op:` test. The legacy
`model_intends_action`, `i_want_to_use_tool`, `action_intent`,
`reply_text` fields are all REMOVED; the LLM picks one op via
`tool_op` (or picks none for no_action).
"""

from __future__ import annotations

from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.internal_thought.engine import (
    _derive_thought_judgment,
    StructuredThoughtEvidence,
    ThoughtContent,
)

from tests._internal_thought_test_fixtures import (
    fired_gate_result,
    populated_bundle,
)


def _evidence(tool_op: str = "", tool_params=None) -> StructuredThoughtEvidence:
    return StructuredThoughtEvidence(
        thought_text="x",
        model_sufficiency=0.9,
        thinking_complete=True,
        channel_request=None,
        hormone_prediction=None,
        tool_op=tool_op,
        tool_params=tool_params or {},
    )


def _request() -> InternalThoughtRequest:
    gate = fired_gate_result()
    return InternalThoughtRequest(
        request_id="r95-test",
        source_gate_result_id=gate.result_id,
        source_retrieval_bundle_id="b",
        source_continuation_active=False,
        internal_state_summary="state",
        prompt_contract_summary={
            "contract_id": "c",
            "consumer_kind": "thought",
            "layer_names": ("identity_grounding",),
            "supports_external_action_proposal": True,
            "supports_self_revision_proposal": True,
            "ready_channels": (),
            # R95 followup (C3): the offline deterministic default op is
            # data-driven from `available_channel_ops`. The engine reads
            # the first op's `op_name` from this key. Tests that exercise
            # the LLM path (with `evidence.tool_op` set) ignore this key;
            # tests that hit the offline path (`evidence=None`) use it.
            "available_channel_ops": (
                {
                    "driver_id": "cli",
                    "op_name": "reply_message",
                    "required_params": ("outbound_text", "target_user_id"),
                    "effect_class": "external_world",
                    "risk_class": "unrestricted",
                    "bound_user_ids": ("*",),
                },
            ),
        },
        tick_id=1,
    )


def _thought() -> ThoughtContent:
    return ThoughtContent(
        thought_id="t",
        thought_type="r95",
        content="x",
        source_path="r95",
        llm_used=True,
        fallback_used=False,
    )


def test_tool_op_non_empty_emits_proposal() -> None:
    """R95: tool_op='reply_message' + tool_params={'outbound_text': '...'}
    => action_proposal is non-None with behavior_name='reply_message'."""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(tool_op="reply_message", tool_params={"outbound_text": "hi"}),
    )
    assert j.action_proposal is not None
    assert j.action_proposal.behavior_name == "reply_message"


def test_tool_op_empty_emits_no_proposal() -> None:
    """R95: tool_op='' (or absent) => action_proposal is None (no_action)."""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(tool_op=""),
    )
    assert j.action_proposal is None


def test_tool_op_fs_read_emits_proposal() -> None:
    """R95: tool_op='fs_read' + tool_params={'path': '...'} => proposal
    with behavior_name='fs_read' (R95 KEY: a tool op, not a reply op)."""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(tool_op="fs_read", tool_params={"path": "/data/x.txt"}),
    )
    assert j.action_proposal is not None
    assert j.action_proposal.behavior_name == "fs_read"


def test_tool_op_qq_send_message_emits_proposal() -> None:
    """R95: tool_op='qq.send_message' + tool_params={'text': '...'} => proposal
    with behavior_name='qq.send_message' (R95 KEY: cross-channel routing)."""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(tool_op="qq.send_message", tool_params={"text": "hi"}),
    )
    assert j.action_proposal is not None
    assert j.action_proposal.behavior_name == "qq.send_message"


def test_deterministic_offline_path_unchanged() -> None:
    """R95: evidence=None => action_proposal is non-None with
    behavior_name='reply_message' (R93 P1 acceptance criterion preserved)."""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=None,
    )
    assert j.action_proposal is not None
    assert j.action_proposal.behavior_name == "reply_message"
    assert j.action_proposal.outbound_text == "x"


def test_target_user_id_passes_through_verbatim() -> None:
    """R95: when the LLM supplies tool_op='reply_message' with
    tool_params={'outbound_text': 'hi', 'target_user_id': 'user-123'},
    the proposal's op_params include exactly those keys/values
    (the engine makes no modification to the LLM's target_user_id).
    When the LLM does NOT supply target_user_id, the proposal's
    op_params is exactly {'outbound_text': 'hi'} (no auto-injection)."""
    # Case A: LLM supplies target_user_id
    j1 = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(
            tool_op="reply_message",
            tool_params={"outbound_text": "hi", "target_user_id": "user-123"},
        ),
    )
    assert j1.action_proposal is not None
    op1 = dict(j1.action_proposal.op_params)
    assert op1 == {"outbound_text": "hi", "target_user_id": "user-123"}

    # Case B: LLM does NOT supply target_user_id; engine does not inject
    j2 = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(tool_op="reply_message", tool_params={"outbound_text": "hi"}),
    )
    assert j2.action_proposal is not None
    op2 = dict(j2.action_proposal.op_params)
    assert op2 == {"outbound_text": "hi"}


def test_old_fields_silently_ignored() -> None:
    """R95: a payload with old R94 fields (wants_to_continue,
    i_want_to_use_tool, action_intent, reply_text, target_user_id)
    plus new R95 fields parses correctly; the old fields do not
    affect the evidence."""
    from helios_v2.internal_thought.engine import _parse_structured_thought

    raw = (
        '{"thought": "x", "sufficiency": 0.5, "tool_op": "reply_message",'
        ' "tool_params": {"outbound_text": "hi"},'
        ' "wants_to_continue": false, "i_want_to_use_tool": true,'
        ' "action_intent": "reply", "reply_text": "OLD-IGNORED",'
        ' "target_user_id": "OLD-IGNORED", "proposed_action": {"intends_action": true}}'
    )
    ev = _parse_structured_thought(raw)
    assert ev.tool_op == "reply_message"
    assert ev.tool_params == {"outbound_text": "hi"}
    assert ev.thinking_complete is True  # default
    # The engine does NOT add fields that weren't in the LLM's tool_params.


def test_self_revision_owner_only() -> None:
    """R95: self_revision_proposal is constructed when the OWNER's
    autobiographical + sufficiency floor is met, regardless of any
    model field. (No model field affects self-revision in R95.)"""
    j = _derive_thought_judgment(
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request(),
        _thought(),
        evidence=_evidence(),
    )
    # The bundle's autobiographical hits + sufficiency 0.9 (>= 0.75) ⇒ OWNER fires.
    assert j.self_revision_proposal is not None
