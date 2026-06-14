"""R95: tests for the "Available channels" section in the system prompt.

R95 exposes the ready channels × ops to the LLM via the system prompt.
Each op is rendered with `op_name`, `required_params`, `effect_class`,
`risk_class`, and `bound_user_ids`. `reply_message` is NOT special-cased
— it appears as one of the `cli` driver's ops alongside any other op
the driver offers.
"""

from __future__ import annotations

from helios_v2.llm import LlmCompletion, LlmUsage
from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath

from tests._internal_thought_test_fixtures import (
    fired_gate_result,
    populated_bundle,
)


class _CaptureGateway:
    def __init__(self):
        self.last_system_text = ""

    def complete(self, request):
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


def _build_system_text(channel_ops) -> str:
    gateway = _CaptureGateway()
    path = LlmBackedInternalThoughtPath(gateway=gateway, profile_name="r95")
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
            "available_channel_ops": channel_ops,
        },
        tick_id=1,
    )
    # _build_messages returns (system, user) tuple; we want the system text.
    return path._build_messages(request, bundle, ContinuationPressureState.inactive())[0].content


def test_available_channels_section_rendered_when_ops_present() -> None:
    """R95: when `available_channel_ops` is non-empty, the system prompt
    contains an 'Available channels' section listing each op."""
    text = _build_system_text(
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
    assert "Available channels" in text
    assert "cli" in text
    assert "reply_message" in text


def test_available_channels_section_omitted_when_empty() -> None:
    """R95: when `available_channel_ops` is empty, the system prompt does
    NOT contain the 'Available channels' section header (the model has no
    channels to act on). The schema/guidance can still reference the
    concept of 'available channels' generically."""
    text = _build_system_text(())
    # The section header specifically, not the word generically.
    assert "Available channels (you may pick" not in text


def test_available_channels_includes_op_required_params() -> None:
    """R95: each op listed in the Available channels section includes
    `op_name`, `required_params`, `effect_class`, `risk_class`."""
    text = _build_system_text(
        (
            {
                "driver_id": "fs_sandbox",
                "op_name": "fs_read",
                "required_params": ["path"],
                "effect_class": "local_host",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
            {
                "driver_id": "fs_sandbox",
                "op_name": "fs_write",
                "required_params": ["path", "content"],
                "effect_class": "local_host",
                "risk_class": "governed",
                "bound_user_ids": ("*",),
            },
        )
    )
    assert "fs_read" in text
    assert "fs_write" in text
    assert "path" in text
    assert "content" in text
    assert "local_host" in text
    assert "unrestricted" in text
    assert "governed" in text


def test_available_channels_does_not_special_case_reply_message() -> None:
    """R95: `reply_message` appears in the Available channels section only
    if a driver offers it as an op (it is not promoted or called out
    as a special case). The cli driver offers reply_message as one of
    its ops; the LLM is free to pick it (or any other op) or none."""
    text = _build_system_text(
        (
            {
                "driver_id": "cli",
                "op_name": "reply_message",
                "required_params": ["outbound_text", "target_user_id"],
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
            {
                "driver_id": "cli",
                "op_name": "send_status",
                "required_params": ["text"],
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
        )
    )
    # Both ops appear, side-by-side, without any "special" indicator.
    assert "reply_message" in text
    assert "send_status" in text
    # There is no "Reply" or "Tool" or "no_action" header / class.
    assert "Reply:" not in text
    assert "Tool:" not in text
    assert "no_action:" not in text


def test_available_channels_uses_explicit_driver_op_prefixes() -> None:
    """R95 followup (C6): the Available channels section uses explicit
    `Driver: X` and `Op: Y` prefixes (not the legacy indented-list
    `1. cli / - reply_message:` format). Empirical evidence: the
    indented format caused some LLMs to confuse a driver name with an
    op name (e.g. picking `tool_op: "cli"` instead of
    `tool_op: "reply_message"`); the explicit prefixes remove the
    ambiguity.

    The section also carries an explicit prose warning that DRIVER
    names are NEVER valid `tool_op` values — the LLM must use the
    token after `Op:`."""
    text = _build_system_text(
        (
            {
                "driver_id": "cli",
                "op_name": "reply_message",
                "required_params": ("outbound_text",),
                "effect_class": "external_world",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
            {
                "driver_id": "fs_sandbox",
                "op_name": "fs_read",
                "required_params": ("path",),
                "effect_class": "local_host",
                "risk_class": "unrestricted",
                "bound_user_ids": ("*",),
            },
        )
    )
    # The new format prefixes are present.
    assert "Driver: cli" in text
    assert "Driver: fs_sandbox" in text
    assert "Op: reply_message" in text
    assert "Op: fs_read" in text
    # The legacy indented-list format is gone.
    assert "1. cli" not in text
    assert "  - reply_message:" not in text
    # The section explains that DRIVER names are NEVER valid tool_op values.
    assert "NEVER valid `tool_op`" in text
    assert "DRIVER names" in text
    # The schema line for tool_op also forbids driver names explicitly.
    assert "NEVER a driver name" in text or "NEVER a driver" in text
