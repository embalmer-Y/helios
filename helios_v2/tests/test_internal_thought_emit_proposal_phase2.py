# -*- coding: utf-8 -*-
"""R93 Phase 2: emit_proposal precedence rewrite tests.

Owner: internal thought loop.

These tests exercise the new emit_proposal precedence order in
`_derive_thought_judgment` (the per-cycle owner judgment). They cover:

1. New precedence: explicit-tool wins over everything else.
2. `action_intent="reply"` with a resolved target builds an implicit reply.
3. `action_intent="no_action"` with otherwise-implicit content yields `action_proposal is None`.
4. The deterministic offline path (evidence=None) preserves the Phase 1 acceptance
   criterion: a reply proposal with `outbound_text=thought.content` is built.
5. `target_user_id` resolution priority: model-supplied > composition-projected.
6. Explicit `tool_op` wins over `action_intent="reply"`.
7. Missing operator id + `action_intent="reply"` yields `None` (silent-when-operator-empty).
8. The legacy `model_intends_action` flag is no longer sufficient to construct a reply.
"""

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


def _request_with_operator(
    current_operator_id: str = "operator:r93-test",
    ready_channels: tuple[str, ...] = ("cli",),
) -> InternalThoughtRequest:
    """A test request whose `prompt_contract_summary` carries `current_operator_id`."""

    return InternalThoughtRequest(
        request_id="internal-thought-request:r93-phase2",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={
            "mode": "internal_thought",
            "voice": "structured",
            "ready_channels": ready_channels,
            "current_operator_id": current_operator_id,
        },
        tick_id=1,
    )


def _run(
    payload: dict,
    *,
    current_operator_id: str = "operator:r93-test",
    ready_channels: tuple[str, ...] = ("cli",),
):
    engine = InternalThoughtEngine(
        config=build_test_config(),
        thought_path=structured_path(JsonReplyGateway(payload=payload)),
    )
    return engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(
            current_operator_id=current_operator_id,
            ready_channels=ready_channels,
        ),
    )


# ---------------------------------------------------------------------------
# Precedence tests
# ---------------------------------------------------------------------------


def test_action_intent_no_action_with_otherwise_implicit_content_yields_none() -> None:
    """action_intent="no_action" overrides every other signal: no proposal.

    Even when `i_want_to_say` is filled and a current operator is present, an
    explicit `no_action` closes the cycle internal-only. This is the documented
    Phase 2 fix to the "confiding machine" pattern.
    """

    payload = envelope(reply_text="would normally trigger compat reply",
        action_intent="no_action",
    )
    result, _ = _run(payload)
    assert result.continuation_requested is False
    assert result.action_proposal is None


def test_action_intent_reply_with_resolved_target_builds_explicit_reply() -> None:
    """action_intent="reply" + reply_text + target builds a reply proposal.

    R94: the model must supply BOTH `action_intent="reply"` AND `reply_text`
    for a reply proposal to be constructed. R93 P2's compat path
    (`reply_text` set without `action_intent`) is REMOVED in R94.
    """

    payload = envelope(
        action_intent="reply",
        reply_text="hello operator",
        target_user_id="user:target",
    )
    result, _ = _run(payload)
    assert result.continuation_requested is False
    assert result.action_proposal is not None
    assert result.action_proposal.requested_op == "reply_message"
    op_params = dict(result.action_proposal.op_params)
    assert op_params["target_user_id"] == "user:target"
    assert op_params["outbound_text"] == "hello operator"


def test_action_intent_reply_with_missing_target_yields_none() -> None:
    """action_intent="reply" with no resolved target: no proposal (silent-when-operator-empty)."""

    payload = envelope(action_intent="reply")
    result, _ = _run(payload, current_operator_id="")
    assert result.action_proposal is None


def test_explicit_tool_op_wins_over_action_intent_reply() -> None:
    """Explicit `i_want_to_use_tool=true` + `tool_op` wins over `action_intent="reply"`.

    Tool intents are the highest-precedence signal in the new emit_proposal
    precedence: the existing R85 path is unchanged. When the model also
    supplies a `target_user_id`, it is threaded into op_params so the planner's
    user-binding filter can route.
    """

    payload = envelope(
        action_intent="reply",
        target_user_id="user:target",
        i_want_to_use_tool=True,
        tool_op="os.fs.write",
        tool_params={"path": "/tmp/x", "content": "hi"},
    )
    result, _ = _run(payload)
    assert result.action_proposal is not None
    assert result.action_proposal.requested_op == "os.fs.write"
    op_params = dict(result.action_proposal.op_params)
    assert op_params["path"] == "/tmp/x"
    assert op_params["content"] == "hi"
    assert op_params["target_user_id"] == "user:target"


def test_action_intent_tool_with_target_threads_target_into_op_params() -> None:
    """`action_intent="tool"` + `target_user_id` threads the target into op_params.

    When the model picks tool via `action_intent` and supplies a target, the
    planner's user-binding filter can route to the right driver.
    """

    payload = envelope(
        action_intent="tool",
        target_user_id="user:002",
        i_want_to_use_tool=True,
        tool_op="os.fs.write",
        tool_params={"path": "/tmp/y", "content": "y"},
    )
    result, _ = _run(payload)
    assert result.action_proposal is not None
    assert result.action_proposal.requested_op == "os.fs.write"
    op_params = dict(result.action_proposal.op_params)
    assert op_params["target_user_id"] == "user:002"
    assert op_params["path"] == "/tmp/y"


# ---------------------------------------------------------------------------
# R94: action_intent="reply" without reply_text yields None (no fabrication)
# ---------------------------------------------------------------------------


def test_action_intent_reply_without_reply_text_yields_none() -> None:
    """R94: explicit `action_intent="reply"` requires non-None `reply_text`.

    R93 P2 would have used `thought.content` as the reply text when
    `action_intent="reply"` was set without `intended_reply_text`. R94 does
    NOT fabricate; the model must supply both: the action class choice AND
    the text to send.
    """

    payload = envelope(
        action_intent="reply",
        # no reply_text
    )
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# R94: reply_text without action_intent yields None (R93 P2 compat REMOVED)
# ---------------------------------------------------------------------------


def test_reply_text_without_action_intent_yields_none() -> None:
    """R94: R93 P2 compat path REMOVED. `reply_text` set without `action_intent`
    is silent (no proposal). The model MUST pick `action_intent` explicitly.
    """

    payload = envelope(
        reply_text="would normally trigger compat reply",
        # no action_intent
    )
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# R94: legacy i_want_to_say payload is silently ignored
# ---------------------------------------------------------------------------


def test_legacy_i_want_to_say_payload_silently_ignored() -> None:
    """R94: an envelope with only `i_want_to_say` (R93 P1) yields no proposal.

    The parser silently ignores the legacy field. R94 has no compat path that
    retro-promotes the legacy value to a reply.
    """
    import json as _json
    payload = {
        "thought": "a thought",
        "sufficiency": 0.9,
        "wants_to_continue": False,
        "continue_reason": "",
        "proposed_action": {"intends_action": False, "summary": ""},
        "self_revision": {"intends_revision": False, "summary": ""},
        "i_want_to_say": "operator-addressed reply (legacy)",
    }
    result, _ = _run(payload)
    assert result.action_proposal is None


def test_target_user_id_resolution_priority_model_supplied_wins() -> None:
    """`target_user_id` model-supplied wins over composition-projected operator.

    The composition-projected `current_operator_id` is a context fact, not a
    forced default. The model's `target_user_id` has priority.
    """

    payload = envelope(
        action_intent="reply",
        reply_text="hello",
        target_user_id="user:model-pick",
    )
    result, _ = _run(payload, current_operator_id="user:composition-default")
    assert result.action_proposal is not None
    op_params = dict(result.action_proposal.op_params)
    assert op_params["target_user_id"] == "user:model-pick"


def test_target_user_id_falls_back_to_composition_projected() -> None:
    """When the model omits `target_user_id`, the owner falls back to the operator."""

    payload = envelope(
        action_intent="reply",
        reply_text="hello",
        # no target_user_id
    )
    result, _ = _run(payload, current_operator_id="user:composition-default")
    assert result.action_proposal is not None
    op_params = dict(result.action_proposal.op_params)
    assert op_params["target_user_id"] == "user:composition-default"


def test_legacy_model_intends_action_alone_is_insufficient() -> None:
    """The legacy `intends_action=True` alone does NOT build a reply proposal.

    Phase 2 explicitly removes the legacy `emit_action` fallback. The model
    must also pick an action class (reply / tool / no_action) or fill
    `i_want_to_say` (compat path) for a reply to be constructed.
    """

    payload = envelope(
        intends_action=True,
        # no i_want_to_say, no action_intent, no tool
    )
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# R94: the R93 P2 compat path (`reply_text` set without `action_intent`) is REMOVED.
# These tests are now negative controls in R94.
# ---------------------------------------------------------------------------


def test_reply_text_alone_no_action_intent_yields_none() -> None:
    """R94: `reply_text` set without `action_intent` yields no proposal.

    R93 P2's compat path is REMOVED in R94. The model must pick an action
    class explicitly; setting `reply_text` alone is silent.
    """

    payload = envelope(
        reply_text="compat reply text",
        # no action_intent, no tool
    )
    result, _ = _run(payload)
    assert result.action_proposal is None


def test_reply_text_alone_no_operator_yields_none() -> None:
    """R94: `reply_text` set without `action_intent` AND no operator yields no proposal.

    Even if R94 had a compat path (it doesn't), the missing operator would
    suppress the reply construction (honest absence).
    """

    payload = envelope(reply_text="compat reply text")
    result, _ = _run(payload, current_operator_id="")
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# Deterministic offline path
# ---------------------------------------------------------------------------


def test_deterministic_offline_path_preserves_phase1_behavior() -> None:
    """The R93 Phase 1 acceptance criterion: the deterministic offline path
    (evidence=None) is byte-for-byte unchanged. The owner still emits a reply
    with `outbound_text=thought.content` and `preferred_channels=("cli",)`.
    """

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
    assert result.action_proposal.requested_op == "reply_message"
    assert result.action_proposal.outbound_text is not None
    assert result.action_proposal.preferred_channels == ("cli",)
