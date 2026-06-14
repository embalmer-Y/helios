"""R94: emit_proposal precedence rewrite tests — drop the R93 P2 compat path.

Owner: internal thought loop.

These tests exercise the new emit_proposal precedence in
`_derive_thought_judgment` (the per-cycle owner judgment) under the R94
schema. They cover:

1. New explicit-reply path: `action_intent="reply" + reply_text + target` builds
   a `reply_message` proposal with `op_params={"outbound_text", "target_user_id"}`.
2. `reply_text` set without `action_intent` yields `None` (the R93 P2 compat
   path is REMOVED in R94).
3. `action_intent="reply"` without `reply_text` yields `None` (no fabrication
   of reply text from `thought.content`).
4. `action_intent="no_action"` with `reply_text` set yields `None` (no_action
   wins regardless of other signals).
5. Legacy `i_want_to_say` payload (no `action_intent`, no `reply_text`) yields
   `None` (the R93 P2 compat path is REMOVED in R94).
6. Explicit `tool_op` wins over `action_intent="reply"`.
7. Missing operator id + `action_intent="reply"` + `reply_text` yields `None`.
8. The deterministic offline path (`evidence is None`) preserves the Phase-1
   acceptance criterion: a reply proposal with `outbound_text=thought.content`
   is built.
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
    current_operator_id: str = "operator:r94-test",
    ready_channels: tuple[str, ...] = ("cli",),
) -> InternalThoughtRequest:
    """A test request whose `prompt_contract_summary` carries `current_operator_id`."""
    return InternalThoughtRequest(
        request_id="internal-thought-request:r94",
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
    current_operator_id: str = "operator:r94-test",
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
# 1. R94 explicit-reply path: action_intent="reply" + reply_text + target
# ---------------------------------------------------------------------------


def test_action_intent_reply_with_reply_text_and_target_builds_reply() -> None:
    """The R94 explicit-reply path: action_intent="reply" + reply_text + target."""
    payload = envelope(
        action_intent="reply",
        reply_text="hello operator",
    )
    result, _ = _run(payload, current_operator_id="operator:r94-test")
    assert result.action_proposal is not None
    proposal = result.action_proposal
    assert proposal.scope == "external"
    assert proposal.behavior_name == "reply_message"
    assert proposal.requested_op == "reply_message"
    assert proposal.outbound_text is None
    assert dict(proposal.op_params) == {
        "outbound_text": "hello operator",
        "target_user_id": "operator:r94-test",
    }


# ---------------------------------------------------------------------------
# 2. reply_text set without action_intent yields None (R93 P2 compat REMOVED)
# ---------------------------------------------------------------------------


def test_reply_text_set_without_action_intent_yields_none() -> None:
    """R93 P2 compat path REMOVED: `reply_text` set without `action_intent` is silent.

    R93 Phase 2 kept a backward-compat path: `action_intent=None +
    i_want_to_say set` still constructed a reply. R94 retires that aid;
    the model MUST pick `action_intent` explicitly.
    """
    payload = envelope(reply_text="would normally trigger compat reply")
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# 3. action_intent="reply" without reply_text yields None
# ---------------------------------------------------------------------------


def test_action_intent_reply_without_reply_text_yields_none() -> None:
    """`action_intent="reply"` requires a non-None `reply_text`; no fabrication.

    R93 P2 would have constructed a reply from `thought.content` if
    `action_intent="reply"` was set without `intended_reply_text`. R94 does
    not fabricate; the model must supply both: the action class choice AND
    the text to send.
    """
    payload = envelope(action_intent="reply")  # no reply_text
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# 4. action_intent="no_action" with reply_text set yields None
# ---------------------------------------------------------------------------


def test_action_intent_no_action_with_reply_text_yields_none() -> None:
    """`no_action` overrides every other signal; no fabrication even with `reply_text`."""
    payload = envelope(
        action_intent="no_action",
        reply_text="would normally trigger reply",
    )
    result, _ = _run(payload)
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# 5. Legacy i_want_to_say payload yields None (R93 P2 compat REMOVED)
# ---------------------------------------------------------------------------


def test_legacy_i_want_to_say_payload_ignored() -> None:
    """A payload with only `i_want_to_say` (R93 P1 field) yields no proposal.

    The parser silently ignores the legacy field (forward-compat with
    in-flight model checkpoints). R94 has no compat path that promotes the
    legacy value to a reply; the model is expected to start producing
    `reply_text` once it has the R94 prompt.
    """
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


# ---------------------------------------------------------------------------
# 6. Explicit tool_op wins over action_intent="reply"
# ---------------------------------------------------------------------------


def test_explicit_tool_op_wins_over_action_intent_reply() -> None:
    """R85 precedence: explicit `tool_op` wins over `action_intent="reply"`."""
    payload = envelope(
        i_want_to_use_tool=True,
        tool_op="fs_write",
        tool_params={"path": "/tmp/x", "content": "y"},
        action_intent="reply",
        reply_text="would normally trigger reply",
    )
    result, _ = _run(payload)
    assert result.action_proposal is not None
    proposal = result.action_proposal
    assert proposal.behavior_name == "fs_write"
    assert proposal.requested_op == "fs_write"
    assert proposal.op_params.get("path") == "/tmp/x"
    assert proposal.op_params.get("content") == "y"


# ---------------------------------------------------------------------------
# 7. Missing operator id + action_intent="reply" + reply_text yields None
# ---------------------------------------------------------------------------


def test_missing_operator_id_with_reply_yields_none() -> None:
    """No operator + reply intent = no proposal (honest absence)."""
    payload = envelope(
        action_intent="reply",
        reply_text="would normally trigger reply",
    )
    result, _ = _run(payload, current_operator_id="")
    assert result.action_proposal is None


# ---------------------------------------------------------------------------
# 8. Deterministic offline path: evidence=None preserves Phase-1 acceptance
# ---------------------------------------------------------------------------


def test_deterministic_offline_path_preserves_phase1_reply() -> None:
    """`assemble_runtime()` deterministic path: legacy reply with
    `outbound_text=thought.content` and `preferred_channels=("cli",)`.

    R94 preserves this Phase-1 acceptance criterion byte-for-byte; the
    deterministic offline assembly is the documented "byte-for-byte
    unchanged" R93 acceptance criterion that R94 also honors.
    """
    config = build_test_config()
    path = FirstVersionInternalThoughtPath()
    engine = InternalThoughtEngine(config=config, thought_path=path)
    result, _ = engine.run_thought_cycle(
        fired_gate_result(),
        populated_bundle(),
        ContinuationPressureState.inactive(),
        _request_with_operator(current_operator_id="operator:r94-test"),
    )
    assert result.action_proposal is not None
    proposal = result.action_proposal
    assert proposal.behavior_name == "reply_message"
    assert proposal.requested_op == "reply_message"
    assert proposal.outbound_text is not None
    assert proposal.preferred_channels == ("cli",)
