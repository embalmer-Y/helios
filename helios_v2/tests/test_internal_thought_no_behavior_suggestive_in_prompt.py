"""R95: structural regression — the system prompt NEVER contains the 7 behavior-suggestive
family literals.

R94 retired the most visible offender (`i_want_to_say`). R95 retires the
entire family of behavior-suggestive fields. The system prompt must
NOT mention any of:

  - `reply_text` (verb "reply")
  - `i_want_to_use_tool` (first-person + verb "use")
  - `wants_to_continue` (verb "wants")
  - `intends_action` (verb "intends")
  - `intends_revision` (verb "intends")
  - `action_intent` (reply/tool/no_action taxonomy)
  - `target_user_id` (top-level identity-presupposition)

A future regression that reintroduces any of these literals in the
system prompt is caught at test time.
"""

from __future__ import annotations

import re

from helios_v2.llm import LlmMessage
from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.directed_retrieval import ThoughtWindowBundle

from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath
from helios_v2.llm import LlmGatewayAPI

from tests._internal_thought_test_fixtures import (
    build_test_config,
    fired_gate_result,
    populated_bundle,
)


# The 7 R95-retired behavior-suggestive literals.
_RETIRED_LITERALS: tuple[str, ...] = (
    "reply_text",
    "i_want_to_use_tool",
    "wants_to_continue",
    "intends_action",
    "intends_revision",
    "action_intent",
    "target_user_id",
)


class _CaptureGateway:
    """Minimal gateway that captures the system message it received."""

    def __init__(self):
        self.last_system_text = ""

    def complete(self, request):
        from helios_v2.llm import LlmCompletion, LlmUsage

        self.last_system_text = request.messages[0].content
        return LlmCompletion(
            completion_id=f"llm:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="fake-r95",
            output_text='{"thought": "x", "sufficiency": 0.5}',
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            latency_ms=1.0,
        )

    def is_profile_ready(self, profile_name: str) -> bool:
        return True

    def list_profile_names(self):
        return ("r95",)


def _build_system_text_with_channel_ops(channel_ops) -> str:
    """Build the system prompt text for the given channel ops, returning it directly."""
    from helios_v2.internal_thought import InternalThoughtRequest

    gateway = _CaptureGateway()
    path = LlmBackedInternalThoughtPath(gateway=gateway, profile_name="r95")
    gate = fired_gate_result()
    bundle = populated_bundle()
    continuation = ContinuationPressureState.inactive()
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
            "available_channel_ops": channel_ops,
        },
        tick_id=1,
    )
    messages = path._build_messages(request, bundle, continuation)
    return messages[0].content


def test_system_prompt_does_not_contain_reply_text() -> None:
    text = _build_system_text_with_channel_ops(
        (
            {
                "driver_id": "cli",
                "op_name": "reply_message",
                "required_params": ["outbound_text"],
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
        )
    )
    assert "reply_text" not in text, (
        "R95: the system prompt must not mention `reply_text` (R95-removed field). "
        f"system prompt:\n{text}"
    )


def test_system_prompt_does_not_contain_i_want_to_use_tool() -> None:
    text = _build_system_text_with_channel_ops(())
    assert "i_want_to_use_tool" not in text, (
        "R95: the system prompt must not mention `i_want_to_use_tool` (R95-removed field). "
        f"system prompt:\n{text}"
    )


def test_system_prompt_does_not_contain_wants_to_continue() -> None:
    text = _build_system_text_with_channel_ops(())
    assert "wants_to_continue" not in text, (
        "R95: the system prompt must not mention `wants_to_continue` (R95-removed field). "
        f"system prompt:\n{text}"
    )


def test_system_prompt_does_not_contain_action_intent_or_intends_or_target() -> None:
    text = _build_system_text_with_channel_ops(
        (
            {
                "driver_id": "cli",
                "op_name": "reply_message",
                "required_params": ["outbound_text"],
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
        )
    )
    for literal in ("action_intent", "intends_action", "intends_revision", "target_user_id"):
        assert literal not in text, (
            f"R95: the system prompt must not mention `{literal}` (R95-removed field). "
            f"system prompt:\n{text}"
        )
