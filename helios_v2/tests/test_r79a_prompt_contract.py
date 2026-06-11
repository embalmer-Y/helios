"""R79-A tests: R79 aggressive embodied prompt path produces correct layered contract.

Verifies the v3 system prompt is rendered into the expected 6 layers with
correct body_state / attention / channel catalog / schema / hard_rules.
"""
from __future__ import annotations

from helios_v2.prompt_contract import (
    EmbodiedPromptConfig,
    EmbodiedPromptConsumerKind,
    EmbodiedPromptRequest,
    PromptContractLayer,
    R79AggressiveEmbodiedPromptPath,
    R79_V3_REQUIRED_LAYER_COUNT,
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
    request_id: str = "r79-test-1",
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
        prompt_bootstrap_id="R79-aggressive-radical-v3",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )


def test_r79_path_emits_six_layers() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    assert len(contract.layers) == R79_V3_REQUIRED_LAYER_COUNT == 6
    names = tuple(layer.layer_name for layer in contract.layers)
    assert names == (
        "present_field",
        "embodied_state",
        "attention_breakdown",
        "channel_catalog",
        "response_schema",
        "v3_system_prompt",
    )


def test_r79_v3_system_prompt_contains_required_blocks() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    v3_layer = contract.layers[-1].content
    # identity philosophy: tells LLM it IS a person, forbids AI/runtime language
    assert "You are a person" in v3_layer
    assert "Not an AI" in v3_layer
    # body + attention gating
    assert "{body_state}" not in v3_layer  # placeholder was filled
    assert "focused" in v3_layer
    assert "peripheral" in v3_layer
    assert "filtered" in v3_layer
    # channel catalog + ready list
    assert "ready" in v3_layer.lower()
    assert "reply_cli" in v3_layer
    # response schema has 11 fields
    assert "what_i_feel" in v3_layer
    assert "i_want_to_say" in v3_layer
    assert "i_send_through" in v3_layer
    assert "remember_this" in v3_layer
    assert "i_want_to_think_more" in v3_layer
    # hard rules
    assert "Hard rules" in v3_layer
    assert "i_will_send_it" in v3_layer
    assert "act_type" in v3_layer


def test_r79_present_field_layer_renders_focused_stimulus() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(
        _make_request(focused="小黑叫我去吃宵夜", peripheral=("老妈在看电视",), filtered=("楼下有狗叫",)),
        _config(),
    )
    present = contract.layers[0].content
    assert "小黑叫我去吃宵夜" in present
    assert "老妈在看电视" in present
    assert "楼下有狗叫" in present


def test_r79_embodied_state_layer_renders_body() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(_make_request(body_state="心率偏快, 肚子平静"), _config())
    assert "心率偏快, 肚子平静" in contract.layers[1].content


def test_r79_channel_catalog_layer_lists_available_and_ready() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(
        _make_request(available_channels=("reply_cli", "send_qq", "log_file"), ready_channels=("reply_cli",)),
        _config(),
    )
    cat = contract.layers[3].content
    assert "reply_cli" in cat
    assert "send_qq" in cat
    assert "log_file" in cat


def test_r79_response_schema_layer_has_validation_list() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(_make_request(ready_channels=("reply_cli", "send_qq")), _config())
    schema = contract.layers[4].content
    assert "i_send_through MUST be one of" in schema
    assert "'reply_cli'" in schema
    assert "'send_qq'" in schema


def test_r79_action_boundary_distinguishes_thought_vs_outward_expression() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    thought_contract = path.build(_make_request(consumer_kind="thought"), _config())
    assert thought_contract.action_boundary.supports_internal_action is True
    assert thought_contract.action_boundary.supports_external_action_proposal is False
    assert thought_contract.action_boundary.supports_self_revision_proposal is True

    oe_contract = path.build(_make_request(consumer_kind="outward_expression"), _config())
    assert oe_contract.action_boundary.supports_internal_action is False
    assert oe_contract.action_boundary.supports_external_action_proposal is True
    assert oe_contract.action_boundary.supports_self_revision_proposal is False


def test_r79_forbidden_capabilities_passed_through() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(
        _make_request(forbidden_capabilities=("cannot_send_email",)),
        _config(),
    )
    assert "cannot_send_email" in contract.action_boundary.forbidden_capabilities


def test_r79_fails_fast_on_wrong_bootstrap_id() -> None:
    path = R79AggressiveEmbodiedPromptPath()
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
    except Exception as e:
        assert "prompt_bootstrap_id" in str(e)
        return
    raise AssertionError("expected PromptContractError on wrong bootstrap_id")


def test_r79_no_ready_channels_renders_none_in_prompt() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(
        _make_request(available_channels=("reply_cli",), ready_channels=()),
        _config(),
    )
    v3 = contract.layers[-1].content
    assert "(none" in v3
    schema = contract.layers[4].content
    assert "(none)" in schema


def test_r79_layer_contents_are_non_empty() -> None:
    path = R79AggressiveEmbodiedPromptPath()
    contract = path.build(_make_request(), _config())
    for layer in contract.layers:
        assert isinstance(layer, PromptContractLayer)
        assert layer.layer_name
        assert layer.content
        assert layer.required is True
