"""Tests for AggressiveRadicalEmbodiedPromptPath (v3).

Verifies the v3 system prompt is rendered into the expected 6 layers with
correct body_state / attention / channel catalog / schema / hard_rules.
"""
from __future__ import annotations

from helios_v2.prompt_contract import (
    AggressiveRadicalEmbodiedPromptPath,
    EmbodiedPromptConfig,
    EmbodiedPromptConsumerKind,
    EmbodiedPromptRequest,
    PromptContractLayer,
)


def _make_request(
    consumer_kind: EmbodiedPromptConsumerKind = "thought",
    body_state: str = "heart rate a bit up, stomach calm",
    focused: str = "a friend just said hello",
    peripheral: tuple = ("foot tapping the floor",),
    filtered: tuple = ("a car passing outside",),
    available_channels: tuple = ("reply_cli", "send_qq"),
    ready_channels: tuple = ("reply_cli",),
    forbidden_capabilities: tuple = (),
    request_id: str = "aggressive-radical-test-1",
) -> EmbodiedPromptRequest:
    return EmbodiedPromptRequest(
        request_id=request_id,
        consumer_kind=consumer_kind,
        source_conscious_state_id="cs-test",
        source_gate_result_id="gr-test",
        source_retrieval_bundle_id="rb-test",
        stimulus_summary={
            "focused": focused,
            "peripheral": peripheral,
            "filtered": filtered,
        },
        state_summary={"body_state": body_state},
        retrieval_summary={"retrieval_context": "(none retrieved)", "continuity_context": "continue naturally"},
        capability_summary={
            "available_channels": available_channels,
            "ready_channels": ready_channels,
            "forbidden_capabilities": forbidden_capabilities,
        },
        identity_boundary_summary={"identity_boundary": "stay consistent with prior self-narrative"},
        tick_id=1,
    )


def _config() -> EmbodiedPromptConfig:
    return EmbodiedPromptConfig(
        max_layer_count=8,
        prompt_bootstrap_id="embodied-prompt-bootstrap:v3-aggressive-radical",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )


def test_aggressive_radical_path_emits_six_layers() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    assert len(contract.layers) == 6
    names = tuple(layer.layer_name for layer in contract.layers)
    assert names == (
        "present_field",
        "embodied_state",
        "attention_breakdown",
        "channel_catalog",
        "response_schema",
        "v3_system_prompt",
    )


def test_aggressive_radical_v3_system_prompt_contains_required_blocks() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    v3_layer = contract.layers[-1].content
    # identity philosophy: tells LLM it IS a person, forbids AI/runtime language
    assert "You are a person" in v3_layer
    assert "Not an AI, not a role, not a runtime" in v3_layer
    # 3 attention tiers
    assert "focused" in v3_layer
    assert "peripheral" in v3_layer
    assert "filtered" in v3_layer
    # channel catalog explanation
    assert "ready" in v3_layer
    # 11 natural-language field names appear
    for field in (
        "what_i_feel",
        "what_i_think",
        "i_want_to_say",
        "i_will_send_it",
        "i_send_through",
        "i_want_to_act",
        "act_type",
        "remember_this",
        "remember_because",
        "i_want_to_think_more",
        "think_more_about",
    ):
        assert field in v3_layer, f"missing field {field} in v3 system prompt"
    # 7 hard rules (cross-field invariants)
    assert "i_will_send_it" in v3_layer
    assert "i_send_through" in v3_layer
    assert "act_type" in v3_layer
    assert "remember_because" in v3_layer
    assert "think_more_about" in v3_layer
    # anti-theatrical directive absorbed, not as a rule
    assert "as a runtime" in v3_layer
    assert "Don't perform" in v3_layer


def test_aggressive_radical_present_field_layer_renders_focused_stimulus() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    present = contract.layers[0].content
    assert "a friend just said hello" in present
    assert "focused" in present


def test_aggressive_radical_embodied_state_layer_renders_body() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    body = contract.layers[1].content
    assert "heart rate a bit up" in body


def test_aggressive_radical_channel_catalog_layer_lists_available_and_ready() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    channel_layer = contract.layers[3].content
    assert "reply_cli" in channel_layer
    assert "send_qq" in channel_layer
    # ready subset is shown
    assert "ready" in channel_layer


def test_aggressive_radical_response_schema_layer_has_validation_list() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    schema_layer = contract.layers[4].content
    # 11 field names
    for field in (
        "what_i_feel",
        "what_i_think",
        "i_want_to_say",
        "i_will_send_it",
        "i_send_through",
        "i_want_to_act",
        "act_type",
        "remember_this",
        "remember_because",
        "i_want_to_think_more",
        "think_more_about",
    ):
        assert field in schema_layer, f"schema missing field {field}"
    # i_send_through validation list present
    assert "i_send_through MUST be one of" in schema_layer
    assert "'reply_cli'" in schema_layer


def test_aggressive_radical_action_boundary_distinguishes_thought_vs_outward_expression() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    thought_contract = path.build(_make_request(consumer_kind="thought"), _config())
    outward_contract = path.build(_make_request(consumer_kind="outward_expression"), _config())
    assert thought_contract.action_boundary.supports_internal_action is True
    assert thought_contract.action_boundary.supports_self_revision_proposal is True
    assert thought_contract.action_boundary.supports_external_action_proposal is False
    assert outward_contract.action_boundary.supports_internal_action is False
    assert outward_contract.action_boundary.supports_external_action_proposal is True
    assert outward_contract.action_boundary.supports_self_revision_proposal is False


def test_aggressive_radical_forbidden_capabilities_passed_through() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(
        _make_request(forbidden_capabilities=("send_email", "modify_filesystem")),
        _config(),
    )
    assert "send_email" in contract.action_boundary.forbidden_capabilities
    assert "modify_filesystem" in contract.action_boundary.forbidden_capabilities
    assert "send_email" in contract.capability_snapshot["forbidden_capabilities"]


def test_aggressive_radical_fails_fast_on_wrong_bootstrap_id() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    bad_config = EmbodiedPromptConfig(
        max_layer_count=8,
        prompt_bootstrap_id="WRONG-BOOTSTRAP",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )
    try:
        path.build(_make_request(), bad_config)
    except Exception as exc:
        assert "WRONG-BOOTSTRAP" in str(exc)
        assert "AggressiveRadicalEmbodiedPromptPath" in str(exc)
        assert "embodied-prompt-bootstrap:v3-aggressive-radical" in str(exc)
    else:
        raise AssertionError("expected PromptContractError on wrong bootstrap id")


def test_aggressive_radical_no_ready_channels_renders_none_in_prompt() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(
        _make_request(available_channels=(), ready_channels=()),
        _config(),
    )
    v3 = contract.layers[-1].content
    assert "(none — you cannot act right now)" in v3
    channel_layer = contract.layers[3].content
    assert "ready" in channel_layer
    assert "(none)" in channel_layer


def test_aggressive_radical_layer_contents_are_non_empty_and_required() -> None:
    path = AggressiveRadicalEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    for layer in contract.layers:
        assert isinstance(layer, PromptContractLayer)
        assert layer.content, f"layer {layer.layer_name} has empty content"
        assert layer.required is True
