"""R93: focused tests for the `_emit_proposal` implicit-reply branch.

Asserts:
  - When `i_want_to_say` is set + operator present (non-empty `current_operator_id`) + no
    explicit `tool_op`, the owner builds an implicit `reply_message` proposal with
    `op_params={"outbound_text": <reply>, "target_user_id": <operator>}`.
  - Explicit `tool_op` (R85) wins over the implicit reply.
  - When `i_want_to_say` is set but `current_operator_id` is empty, the implicit reply is
    silently absent (no fabricated target).
  - When `evidence is None` (deterministic offline path), behavior is byte-for-byte
    unchanged.
  - When continuation is requested, no proposal is emitted (continuation precedence).
  - When both `intends_action=True` and `i_want_to_say` are set, the implicit-reply path
    wins over the legacy `emit_action` branch (because explicit tool intent is absent).
"""

from __future__ import annotations

from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtEngine,
    InternalThoughtRequest,
)
from helios_v2.thought_gating import ContinuationPressureState

from _internal_thought_test_fixtures import (
    JsonReplyGateway,
    build_test_config,
    envelope,
    fired_gate_result,
    populated_bundle,
    structured_path,
)


def _request_with_operator(current_operator_id: str = "cli") -> InternalThoughtRequest:
    """A test request whose `prompt_contract_summary` carries the R93 `current_operator_id`
    key (composition projects this in production)."""
    return InternalThoughtRequest(
        request_id="internal-thought-request:r93",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={
            "mode": "internal_thought",
            "voice": "structured",
            "ready_channels": ("cli",),
            "current_operator_id": current_operator_id,
        },
        tick_id=1,
    )


# ---------------------------------------------------------------------------
# Implicit reply: built when i_want_to_say + operator + no explicit tool
# ---------------------------------------------------------------------------


def test_explicit_reply_built_when_i_want_to_say_and_operator_present() -> None:
    gateway = JsonReplyGateway(
        payload=envelope(reply_text="hello operator", action_intent="reply")
    )
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(current_operator_id="cli"),
    )

    assert result.action_proposal is not None
    proposal = result.action_proposal
    assert proposal.scope == "external"
    assert proposal.behavior_name == "reply_message"
    assert proposal.requested_op == "reply_message"
    assert proposal.outbound_text is None
    assert dict(proposal.op_params) == {
        "outbound_text": "hello operator",
        "target_user_id": "cli",
    }
    assert "intends to reply" in " ".join(proposal.reason_trace).lower()


def test_explicit_reply_uses_ready_channels_as_preferred() -> None:
    gateway = JsonReplyGateway(payload=envelope(reply_text="hi", action_intent="reply"))
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))
    request = InternalThoughtRequest(
        request_id="internal-thought-request:r93",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="state",
        prompt_contract_summary={
            "mode": "internal_thought",
            "voice": "structured",
            "ready_channels": ("cli", "another"),
            "current_operator_id": "operator-x",
        },
        tick_id=1,
    )
    result, _ = engine.run_thought_cycle(
        fired_gate_result(), populated_bundle(), ContinuationPressureState.inactive(), request
    )
    assert result.action_proposal is not None
    assert result.action_proposal.preferred_channels == ("cli", "another")


# ---------------------------------------------------------------------------
# Honest absence: no operator -> silent (no implicit reply)
# ---------------------------------------------------------------------------


def test_explicit_reply_absent_when_no_current_operator() -> None:
    gateway = JsonReplyGateway(
        payload=envelope(reply_text="hello operator", action_intent="reply")
    )
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(current_operator_id=""),
    )

    assert result.action_proposal is None


def test_explicit_reply_absent_when_i_want_to_say_empty() -> None:
    gateway = JsonReplyGateway(payload=envelope(reply_text=""))
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(),
    )
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# Explicit tool_op wins (R85 precedence preserved)
# ---------------------------------------------------------------------------


def test_explicit_tool_op_wins_over_explicit_reply() -> None:
    gateway = JsonReplyGateway(
        payload=envelope(
            reply_text="hello operator",
            action_intent="reply",
            i_want_to_use_tool=True,
            tool_op="fs_write",
            tool_params={"path": "a.txt", "content": "hi"},
        )
    )
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(),
    )

    assert result.action_proposal is not None
    proposal = result.action_proposal
    assert proposal.behavior_name == "fs_write"
    assert proposal.requested_op == "fs_write"
    # R93 Phase 2: the planner's user-binding filter needs `target_user_id` to route
    # the tool op, so the owner threads it into op_params when the composition-
    # projected operator is non-empty.
    op_params = dict(proposal.op_params)
    assert op_params["path"] == "a.txt"
    assert op_params["content"] == "hi"
    assert op_params["target_user_id"] == "cli"


# ---------------------------------------------------------------------------
# Legacy fallback: evidence is None -> byte-for-byte unchanged
# ---------------------------------------------------------------------------


def test_deterministic_offline_path_unchanged_when_evidence_is_none() -> None:
    """The deterministic offline path (no LLM, evidence=None) goes through the legacy
    `emit_action` branch with `outbound_text=thought.content`. R93 must not perturb it."""
    engine = InternalThoughtEngine(
        config=build_test_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(),
    )
    assert result.action_proposal is not None
    assert result.action_proposal.behavior_name == "reply_message"
    assert result.action_proposal.outbound_text  # non-empty narration (legacy field, not op_params)
    assert result.action_proposal.preferred_channels == ("cli",)


# ---------------------------------------------------------------------------
# Continuation precedence
# ---------------------------------------------------------------------------


def test_continuation_requested_takes_precedence_over_explicit_reply() -> None:
    gateway = JsonReplyGateway(
        payload=envelope(reply_text="hello operator",
            wants_to_continue=True,
            continue_reason="need to think more before replying",
        )
    )
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(),
    )

    assert result.action_proposal is None
    assert result.memory_handoff is not None


# ---------------------------------------------------------------------------
# intends_action=True + i_want_to_say -> implicit reply path
# ---------------------------------------------------------------------------


def test_intends_action_with_i_want_to_say_uses_explicit_reply_path() -> None:
    """R94: When the model fills `intends_action=true + action_intent="reply" + reply_text="..."`,
    the explicit-reply path is taken (it produces a complete proposal with op_params)."""
    gateway = JsonReplyGateway(
        payload=envelope(
            intends_action=True,
            reply_text="hello operator",
            action_intent="reply",
        )
    )
    engine = InternalThoughtEngine(config=build_test_config(), thought_path=structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(current_operator_id="cli"),
    )

    assert result.action_proposal is not None
    assert result.action_proposal.behavior_name == "reply_message"
    assert dict(result.action_proposal.op_params) == {
        "outbound_text": "hello operator",
        "target_user_id": "cli",
    }
    assert result.action_proposal.outbound_text is None
