"""Focused tests for policy evaluation and execution planning."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.action_models import ActionProposal, BehaviorSpec
from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor, ChannelStatus
from helios_io.planning import ExecutionPlanner, PolicyEvaluator
from behavior_registry import RuntimeBehaviorCatalog


def make_descriptor(channel_id: str, capabilities: list[str], *, op_name: str = "send", input_schema: dict | None = None) -> ChannelDescriptor:
    return ChannelDescriptor(
        channel_id=channel_id,
        display_name=channel_id.upper(),
        output_types=["text_message"],
        output_formats=["text/plain"],
        capabilities=list(capabilities),
        supported_ops=[
            ChannelOpDescriptor(
                name=op_name,
                direction="output",
                description=f"{channel_id} output",
                input_schema=dict(input_schema or {}),
            )
        ],
    )


def test_policy_evaluator_rejects_unapproved_behavior_and_low_score():
    evaluator = PolicyEvaluator(min_score=0.2)
    proposal = ActionProposal(
        proposal_id="p-1",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="speak_share",
        score_bundle={"final": 0.1},
        candidate_channels=["qq"],
    )
    behavior = BehaviorSpec(
        behavior_id="b-1",
        name="speak_share",
        display_name="Speak Share",
        description="Share an idea with the user.",
        category="social",
        review_state="draft",
    )

    evaluation = evaluator.evaluate(
        proposal,
        behavior,
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert evaluation.accepted is False
    assert {item.code for item in evaluation.violations} == {"behavior_unreviewed", "score_below_threshold"}


def test_execution_planner_selects_preferred_connected_channel_with_capabilities():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-2",
        source_type="regulation",
        source_module="regulation_policy",
        intent_type="express",
        behavior_name="speak_care",
        score_bundle={"final": 0.72},
        candidate_channels=["tts", "qq"],
        suggested_modalities=["speech"],
    )
    behavior = BehaviorSpec(
        behavior_id="b-2",
        name="speak_care",
        display_name="Speak Care",
        description="Express care toward the target.",
        category="social",
        allowed_channel_ids=["tts", "qq"],
        required_capabilities=["speech_output"],
        supported_modalities=["speech"],
        parameter_schema={"target_id": {"required": False, "default": "master"}},
        cost_policy={"cost": 0.2},
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {
            "tts": make_descriptor("tts", ["send", "speech_output"]),
            "qq": make_descriptor("qq", ["send", "text_output"]),
        },
        {"tts": ChannelStatus.CONNECTED, "qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is True
    assert decision.selected_channel_id == "tts"
    assert decision.selected_op == "send"
    assert decision.execution_priority == 75
    assert decision.validated_params["target_id"] == "master"
    assert decision.selected_modality == "speech"
    assert decision.policy_trace["routing_trace"]["selection_reason"] == "proposal_candidate_preference"
    assert decision.policy_trace["routing_trace"]["executor_ready"] is True


def test_execution_planner_rejects_when_no_channel_satisfies_required_capability():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-3",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="speak_care",
        score_bundle={"final": 0.9},
    )
    behavior = BehaviorSpec(
        behavior_id="b-3",
        name="speak_care",
        display_name="Speak Care",
        description="Express care.",
        category="social",
        required_capabilities=["speech_output"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert decision.rejection_reason == "no_channel_available"
    assert decision.policy_trace["filtered_out_reasons"]["qq"] == "missing_capabilities"


def test_execution_planner_rejects_missing_output_operation_binding():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-3b",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="reply_message",
        score_bundle={"final": 0.9},
        candidate_channels=["silent"],
    )
    behavior = BehaviorSpec(
        behavior_id="b-3b",
        name="reply_message",
        display_name="Reply Message",
        description="Reply through a channel.",
        category="interaction",
        execution_mode="channel",
        allowed_channel_ids=["silent"],
        required_capabilities=["send"],
    )
    descriptor = ChannelDescriptor(
        channel_id="silent",
        display_name="Silent",
        output_types=["text_message"],
        output_formats=["text/plain"],
        capabilities=["send", "text_output"],
        supported_ops=[],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"silent": descriptor},
        {"silent": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert decision.rejection_reason == "missing_output_op"
    assert decision.policy_trace["routing_trace"]["rejection_reason"] == "missing_output_op"


def test_execution_planner_rejects_missing_target_user_binding_for_channel_behavior():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-3c",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="reply_message",
        score_bundle={"final": 0.9},
        candidate_channels=["qq"],
        parameters={"outbound_text": "hello", "target_user_id": ""},
    )
    behavior = BehaviorSpec(
        behavior_id="b-3c",
        name="reply_message",
        display_name="Reply Message",
        description="Reply through a channel.",
        category="interaction",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        applicable_context={"requires_target_user": True},
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert "missing_target_user_id" in decision.rejection_reason


def test_policy_evaluator_requires_connected_channel_by_default():
    evaluator = PolicyEvaluator()
    proposal = ActionProposal(
        proposal_id="p-3d",
        source_type="interaction",
        source_module="interaction_policy",
        intent_type="reply",
        behavior_name="reply_message",
        score_bundle={"final": 0.9},
        candidate_channels=["qq"],
        parameters={"target_user_id": "user1"},
    )
    behavior = BehaviorSpec(
        behavior_id="b-3d",
        name="reply_message",
        display_name="Reply Message",
        description="Reply through a channel.",
        category="interaction",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        applicable_context={"requires_target_user": True},
    )

    evaluation = evaluator.evaluate(
        proposal,
        behavior,
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.DISCONNECTED},
    )

    assert evaluation.accepted is False
    assert any(item.code == "no_channel_available" for item in evaluation.violations)
    assert evaluation.trace["filtered_out_reasons"]["qq"] == "channel_status:disconnected"


def test_execution_planner_can_plan_internal_behavior_without_channel():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4",
        source_type="regulation",
        source_module="regulation_policy",
        intent_type="internal_action",
        behavior_name="reflect",
        score_bundle={"final": 0.52},
        suggested_modalities=["internal"],
    )
    behavior = BehaviorSpec(
        behavior_id="b-4",
        name="reflect",
        display_name="Reflect",
        description="Run internal reflection.",
        category="meta",
        execution_mode="internal",
        supported_modalities=["internal"],
    )

    decision = planner.plan(proposal, {behavior.name: behavior}, {}, {})

    assert decision.accepted is True
    assert decision.selected_channel_id == ""
    assert decision.selected_op == "internal_execute"
    assert decision.selected_modality == "internal"


def test_execution_planner_rejects_internal_scope_external_behavior():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4b",
        source_type="preconscious",
        source_module="preconscious_policy",
        intent_type="internal_bias",
        behavior_name="speak_share",
        score_bundle={"final": 0.48},
        candidate_channels=["qq"],
        constraints={"execution_scope": "internal"},
        suggested_modalities=["internal"],
    )
    behavior = BehaviorSpec(
        behavior_id="b-4b",
        name="speak_share",
        display_name="Speak Share",
        description="Share something outwardly.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert "execution_scope_constraint" in decision.rejection_reason
    violations = decision.policy_trace["violations"]
    assert any(item["code"] == "execution_scope_constraint" for item in violations)


def test_execution_planner_accepts_thought_origin_external_behavior_and_normalizes_intensity():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4c",
        source_type="preconscious",
        source_module="preconscious_policy",
        origin_type="thought",
        origin_id="thought::7::rumination::1000",
        intent_type="thought_action",
        behavior_name="speak_share",
        score_bundle={"final": 0.52},
        candidate_channels=["qq"],
        suggested_modalities=["text"],
        parameters={"target_user_id": "master"},
        op_name="send",
        op_params={"outbound_metadata": {"origin_type": "thought"}},
        outbound_intensity=1.4,
    )
    behavior = BehaviorSpec(
        behavior_id="b-4c",
        name="speak_share",
        display_name="Speak Share",
        description="Share something outwardly.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"] )},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is True
    assert decision.selected_channel_id == "qq"
    assert decision.selected_op == "send"
    assert decision.normalized_intensity == 1.0
    assert decision.validated_params["target_user_id"] == "master"
    assert decision.validated_params["outbound_metadata"]["origin_type"] == "thought"


def test_execution_planner_rejects_requested_op_when_channel_does_not_support_it():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4d",
        source_type="preconscious",
        source_module="preconscious_policy",
        origin_type="thought",
        origin_id="thought::7::rumination::1000",
        intent_type="thought_action",
        behavior_name="speak_share",
        score_bundle={"final": 0.52},
        candidate_channels=["qq"],
        parameters={"target_user_id": "master"},
        op_name="broadcast",
    )
    behavior = BehaviorSpec(
        behavior_id="b-4d",
        name="speak_share",
        display_name="Speak Share",
        description="Share something outwardly.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"] )},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert "requested_op_unavailable" in decision.rejection_reason


def test_execution_planner_rejects_thought_origin_channel_behavior_without_explicit_op():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4e",
        source_type="preconscious",
        source_module="preconscious_policy",
        origin_type="thought",
        origin_id="thought::7::rumination::1000",
        intent_type="thought_action",
        behavior_name="speak_share",
        score_bundle={"final": 0.52},
        candidate_channels=["qq"],
        parameters={"target_user_id": "master"},
    )
    behavior = BehaviorSpec(
        behavior_id="b-4e",
        name="speak_share",
        display_name="Speak Share",
        description="Share something outwardly.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {"qq": make_descriptor("qq", ["send", "text_output"])},
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert "missing_requested_op" in decision.rejection_reason


def test_execution_planner_rejects_missing_required_op_inputs():
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-4f",
        source_type="preconscious",
        source_module="preconscious_policy",
        origin_type="thought",
        origin_id="thought::7::rumination::1000",
        intent_type="thought_action",
        behavior_name="speak_share",
        score_bundle={"final": 0.52},
        candidate_channels=["qq"],
        parameters={"target_user_id": "master"},
        op_name="send",
    )
    behavior = BehaviorSpec(
        behavior_id="b-4f",
        name="speak_share",
        display_name="Speak Share",
        description="Share something outwardly.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )

    decision = planner.plan(
        proposal,
        {behavior.name: behavior},
        {
            "qq": make_descriptor(
                "qq",
                ["send", "text_output"],
                input_schema={"outbound_metadata": {"required": True}},
            )
        },
        {"qq": ChannelStatus.CONNECTED},
    )

    assert decision.accepted is False
    assert decision.rejection_reason == "missing_op_inputs"
    assert decision.policy_trace["routing_trace"]["missing_op_inputs"] == ["outbound_metadata"]


def test_execution_planner_accepts_behavior_only_after_catalog_approval(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    planner = ExecutionPlanner(PolicyEvaluator())
    proposal = ActionProposal(
        proposal_id="p-5",
        source_type="llm",
        source_module="behavior_proposal",
        intent_type="express",
        behavior_name="compose_poem",
        score_bundle={"final": 0.62},
        candidate_channels=["qq"],
        suggested_modalities=["text"],
    )
    spec = BehaviorSpec(
        behavior_id="proposal.compose_poem",
        name="compose_poem",
        display_name="Compose Poem",
        description="Compose a short poem for the user.",
        category="social",
        execution_mode="channel",
        allowed_channel_ids=["qq"],
        required_capabilities=["send"],
        supported_modalities=["text"],
    )
    descriptor = {"qq": make_descriptor("qq", ["send", "text_output"])}
    statuses = {"qq": ChannelStatus.CONNECTED}

    proposed = catalog.propose_behavior(spec, source_summary="LLM proposed a poem behavior")
    pending_decision = planner.plan(proposal, {proposed.name: proposed}, descriptor, statuses)

    assert pending_decision.accepted is False
    assert "behavior_unreviewed" in pending_decision.rejection_reason

    approved = catalog.approve_behavior("compose_poem", approved_by="tester", review_note="safe")
    assert approved is not None

    accepted_decision = planner.plan(proposal, catalog.snapshot_by_name(), descriptor, statuses)

    assert accepted_decision.accepted is True
    assert accepted_decision.selected_channel_id == "qq"