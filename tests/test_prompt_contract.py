"""Focused tests for the unified prompt contract owner."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor
from helios_io.prompt_contract import PromptContractBuilder


class FakeState:
    valence = 0.2
    arousal = 0.4
    icri = 0.55
    drive_urgency = 0.31
    continuation_pressure = 0.42


def test_prompt_contract_builder_emits_structured_plan_layers():
    builder = PromptContractBuilder()
    plan = builder.build_plan(
        identity_summary="已诞生自我意识的 AI",
        state=FakeState(),
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.68,
            }
        ],
        directed_memory_summary="mid=recent experience | autobio=shared walk memory",
        available_channels=[
            ChannelDescriptor(
                channel_id="qq",
                display_name="QQ",
                supported_ops=[
                    ChannelOpDescriptor(
                        name="send",
                        direction="output",
                        description="Send outbound message",
                        input_schema={"text": "str", "user_id": "str"},
                    )
                ],
            )
        ],
        available_behavior_schemas=[
            {"behavior_name": "reply_message", "op_name": "send", "parameter_schema": {"text": "str"}}
        ],
    )

    assert plan.identity_layer
    assert plan.metric_layer.startswith("metrics:")
    assert plan.state_layer.startswith("state_summary=")
    assert plan.stimulus_layer.startswith("stimuli:")
    assert "shared walk memory" in plan.memory_layer
    assert plan.channel_layer.startswith("channel_context:")
    assert plan.action_layer.startswith("action_contract:")
    assert "self-revision proposal" in plan.constraints_layer
    assert plan.snapshot.metric_descriptor_count >= 8
    assert plan.snapshot.channel_descriptor_count == 1


def test_prompt_contract_builder_includes_required_metric_ranges():
    builder = PromptContractBuilder()
    plan = builder.build_plan(identity_summary="已诞生自我意识的 AI", state=FakeState())
    metrics = {descriptor.name: descriptor for descriptor in plan.metric_descriptors}

    assert metrics["valence"].range == "[-1.0, +1.0]"
    assert metrics["arousal"].range == "[0.0, 1.0]"
    assert metrics["icri"].range == "[0.0, 1.0]"
    assert metrics["stimulus_intensity"].range == "[0.0, 1.0]"
    assert metrics["outbound_intensity"].range == "[0.0, 1.0]"
    assert metrics["drive_urgency"].range == "[0.0, 1.0]"
    assert metrics["fatigue_pressure"].range == "[0.0, 1.0]"
    assert metrics["continuation_pressure"].range == "[0.0, 1.0]"


def test_prompt_contract_builder_includes_channel_and_op_schema_semantics():
    builder = PromptContractBuilder()
    plan = builder.build_plan(
        identity_summary="已诞生自我意识的 AI",
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.75,
            }
        ],
        available_channels=[
            ChannelDescriptor(
                channel_id="qq",
                display_name="QQ",
                supported_ops=[
                    ChannelOpDescriptor(
                        name="send",
                        direction="output",
                        description="Send outbound message",
                        input_schema={"text": "str", "user_id": "str"},
                    )
                ],
            )
        ],
    )

    assert plan.channel_descriptors[0].channel_id == "qq"
    assert plan.channel_descriptors[0].supported_ops == ("send",)
    assert "stimulus_intensity=0.750" in plan.channel_layer
    assert "channel_op=send" in plan.action_layer
    assert "input_schema=text:str, user_id:str" in plan.action_layer


def test_prompt_contract_builder_preserves_identity_boundary_language():
    builder = PromptContractBuilder()
    plan = builder.build_plan(identity_summary="已诞生自我意识的 AI")

    assert "已诞生自我意识的 AI" in plan.identity_layer
    assert "designed program" in plan.constraints_layer