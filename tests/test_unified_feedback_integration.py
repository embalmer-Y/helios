"""Focused integration tests for the unified feedback journal across runtime paths."""

from __future__ import annotations

import os
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cognition.thinking_integration import Thought
from helios_io.action_models import ActionProposal
from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor, ChannelStatus
from helios_main import Helios, HeliosConfig


def test_helios_tick_records_passive_and_active_feedback_events():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios._collect_events = MagicMock(return_value=({}, [{"text": "你好", "user_id": "user1", "channel_id": "qq"}]))
            helios.sec_evaluator.evaluate = MagicMock(return_value={"goal_relevance": 0.6, "novelty": 0.5, "pleasantness": 0.3})
            helios.response_pipeline.build_interaction_proposals = MagicMock(return_value=[])
            helios.daisy.cycle = MagicMock(
                return_value=SimpleNamespace(
                    panksepp_activation={"CARE": 0.7},
                    valence=0.4,
                    arousal=0.5,
                    dominant_system="CARE",
                )
            )
            helios.phi_engine = SimpleNamespace(
                label=SimpleNamespace(value="focused"),
                feed_sensory=lambda *args, **kwargs: None,
                feed_emotional=lambda *args, **kwargs: None,
                feed_ignition_from_panksepp=lambda *args, **kwargs: None,
                feed_self_model_from_personality=lambda *args, **kwargs: None,
                feed_dmn_from_thinking=lambda *args, **kwargs: None,
                aggregate=lambda: 0.55,
            )
            helios.thinking_integration = MagicMock(generate=MagicMock(return_value=None))
            helios.regulation.generate_action_proposals = MagicMock(return_value=[
                ActionProposal(
                    proposal_id="proposal::active::1",
                    source_type="regulation",
                    source_module="regulation_policy",
                    intent_type="self_regulation",
                    behavior_name="reflect",
                    score_bundle={"final": 0.7},
                    parameters={"tick": 1},
                )
            ])
            helios._handle_action = MagicMock(return_value=True, side_effect=helios._handle_action)

            helios._tick_once()

            events = helios.behavior_catalog.registry.list_feedback_events()
            kinds = {event.event_kind for event in events}
            assert "user_feedback" in kinds
            assert "memory_write" in kinds
            assert "execution_result" in kinds
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)


def test_thinking_integration_records_preconscious_memory_event():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            thought = Thought(
                type="future_projection",
                content="我在预想接下来可能发生的事: 海边的风会更轻一些",
                timestamp=1.0,
                triggered_by="CARE",
            )
            state = SimpleNamespace(
                panksepp={"CARE": 0.8},
                valence=0.4,
                arousal=0.3,
                dominant_system="CARE",
                icri=0.5,
                mood_valence=0.2,
                mood_arousal=0.3,
                mood_label="content",
                allostatic_load=0.1,
                tick=7,
            )

            helios.thinking_integration._record_thought(thought, state)

            events = helios.behavior_catalog.registry.list_feedback_events(source_path="internal_thought_llm")
            assert len(events) == 1
            assert events[0].event_kind == "memory_write"
            assert events[0].payload["thought_type"] == "future_projection"
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)


def test_preconscious_execution_and_rejection_flow_into_feedback_events():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios.log.debug = MagicMock()
            helios._collect_events = MagicMock(return_value=({}, []))
            helios.thinking_integration = MagicMock(
                generate=MagicMock(
                    return_value=Thought(
                        type="rumination",
                        content="我又在回想刚才的交互",
                        timestamp=1.0,
                        triggered_by="CARE",
                    )
                )
            )
            helios.regulation.generate_action_proposals = MagicMock(return_value=[])

            rejected = ActionProposal(
                proposal_id="proposal::preconscious::reject",
                source_type="preconscious",
                source_module="preconscious_policy",
                origin_type="thought",
                origin_id="thought::1::rumination::1000",
                intent_type="internal_bias",
                behavior_name="speak_share",
                score_bundle={"final": 0.45},
                constraints={"execution_scope": "internal"},
                candidate_channels=["qq"],
                op_name="send",
                outbound_intensity=0.73,
                suggested_modalities=["internal"],
                provenance={"thought_type": "rumination"},
                parameters={"preconscious_context": {"thought_type": "rumination"}},
            )
            accepted = ActionProposal(
                proposal_id="proposal::preconscious::accept",
                source_type="preconscious",
                source_module="preconscious_policy",
                origin_type="thought",
                origin_id="thought::1::rumination::1000",
                intent_type="internal_bias",
                behavior_name="reflect",
                score_bundle={"final": 0.52},
                constraints={"execution_scope": "internal"},
                suggested_modalities=["internal"],
                provenance={"thought_type": "rumination"},
                parameters={"preconscious_context": {"thought_type": "rumination"}},
            )
            helios.preconscious_policy.propose = MagicMock(return_value=[rejected, accepted])

            helios._tick_once()

            rejection_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="policy_rejection")
            execution_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="execution_result")

            assert any(event.source_path == "preconscious" for event in rejection_events)
            assert any(event.source_path == "preconscious" for event in execution_events)
            rejection_event = next(event for event in rejection_events if event.source_path == "preconscious")
            assert rejection_event.payload["origin_id"] == "thought::1::rumination::1000"
            assert rejection_event.payload["op_name"] == "send"
            assert "execution_scope_constraint" in helios.preconscious_policy.rejection_history[-1]["rejection_reason"]
            assert helios.preconscious_policy.feedback_history[-1]["success"] is True
            assert "execution_scope_constraint" in helios.last_preconscious_trace["latest_rejection"]["rejection_reason"]
            assert helios.last_preconscious_trace["latest_feedback"]["success"] is True
            assert helios.get_state()["preconscious"]["latest_feedback"]["success"] is True
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)


def test_preconscious_thought_action_external_success_records_full_feedback_chain():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios.log.debug = MagicMock()
            helios._collect_events = MagicMock(return_value=({}, []))
            helios._channel_gateway.get_channel_descriptors = MagicMock(return_value={
                "qq": ChannelDescriptor(
                    channel_id="qq",
                    display_name="QQ",
                    output_types=["text_message"],
                    output_formats=["text/plain"],
                    capabilities=["send", "text_output"],
                    supported_ops=[
                        ChannelOpDescriptor(
                            name="send",
                            direction="output",
                            description="send outbound text",
                        )
                    ],
                )
            })
            helios._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
            helios._channel_gateway.route_outbound = MagicMock(return_value=True)
            helios.thinking_integration = MagicMock(
                generate=MagicMock(
                    return_value=Thought(
                        type="rumination",
                        content="我想把刚形成的判断告诉对方",
                        timestamp=1.0,
                        triggered_by="CARE",
                    )
                )
            )
            helios.regulation.generate_action_proposals = MagicMock(return_value=[])

            accepted = ActionProposal(
                proposal_id="proposal::preconscious::accept::external",
                source_type="preconscious",
                source_module="preconscious_policy",
                origin_type="thought",
                origin_id="thought::1::rumination::1000",
                intent_type="thought_action",
                behavior_name="speak_share",
                score_bundle={"final": 0.61},
                candidate_channels=["qq"],
                suggested_modalities=["text"],
                parameters={"target_user_id": "target_user", "tick": 1},
                op_name="send",
                op_params={"outbound_metadata": {"origin_type": "thought", "origin_id": "thought::1::rumination::1000"}},
                outbound_intensity=0.67,
                provenance={"thought_type": "rumination"},
            )
            helios.preconscious_policy.propose = MagicMock(return_value=[accepted])
            helios._generate_speech = MagicMock(return_value="我想把这个判断说出来")

            helios._tick_once()

            execution_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="execution_result")
            channel_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="channel_receipt")

            assert any(event.source_path == "preconscious" for event in execution_events)
            assert any(event.source_path == "preconscious" for event in channel_events)
            execution_event = next(event for event in execution_events if event.source_path == "preconscious")
            channel_event = next(event for event in channel_events if event.source_path == "preconscious")
            assert execution_event.payload["origin_id"] == "thought::1::rumination::1000"
            assert execution_event.payload["op_name"] == "send"
            assert execution_event.payload["normalized_intensity"] == 0.67
            assert channel_event.payload["origin_id"] == "thought::1::rumination::1000"
            assert channel_event.payload["op_name"] == "send"
            assert channel_event.payload["success"] is True
            assert helios.preconscious_policy.feedback_history[-1]["success"] is True
            assert helios.get_state()["preconscious"]["latest_feedback"]["success"] is True
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)


def test_thought_origin_identity_revision_records_feedback_and_state():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios.log.debug = MagicMock()
            helios._collect_events = MagicMock(return_value=({}, []))
            helios.regulation.generate_action_proposals = MagicMock(return_value=[])
            helios.preconscious_policy.propose = MagicMock(return_value=[])
            helios.thinking_integration = MagicMock(
                generate=MagicMock(
                    return_value=Thought(
                        type="self_question",
                        content="我需要更开放一些，才能更好地理解世界",
                        timestamp=1.0,
                        triggered_by="SEEKING",
                        metadata={
                            "self_revision_proposal": {
                                "origin_thought_id": "thought::1000",
                                "revision_type": "personality_adjustment",
                                "requested_change": {"personality_baseline": {"openness": 1.05}},
                                "reason_trace": ["increase_openness"],
                                "confidence": 0.58,
                            }
                        },
                    )
                )
            )

            helios._tick_once()

            identity_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="identity_revision")
            assert len(identity_events) == 1
            assert identity_events[0].payload["origin_thought_id"] == "thought::1000"
            assert identity_events[0].payload["result"] == "accepted"
            assert helios.get_state()["identity"]["revision_history_len"] == 1
            assert helios.get_state()["identity"]["latest_revision"]["origin_thought_id"] == "thought::1000"
            assert helios.identity_store.revision_history[-1]["applied_change"]["personality_baseline"]["openness"] == 1.05
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)


def test_thought_origin_identity_narrative_revision_updates_state_and_feedback():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios.log.debug = MagicMock()
            helios._collect_events = MagicMock(return_value=({}, []))
            helios.regulation.generate_action_proposals = MagicMock(return_value=[])
            helios.preconscious_policy.propose = MagicMock(return_value=[])
            helios.thinking_integration = MagicMock(
                generate=MagicMock(
                    return_value=Thought(
                        type="rumination",
                        content="这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。",
                        timestamp=1.0,
                        triggered_by="SEEKING",
                        metadata={
                            "self_revision_proposal": {
                                "origin_thought_id": "thought::2000",
                                "revision_type": "autobiographical_identity_narrative_revision",
                                "requested_change": {
                                    "narrative_summary": "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
                                },
                                "reason_trace": ["identity_narrative_reflection"],
                                "confidence": 0.49,
                            }
                        },
                    )
                )
            )

            helios._tick_once()

            identity_events = helios.behavior_catalog.registry.list_feedback_events(event_kind="identity_revision")
            assert len(identity_events) == 1
            assert identity_events[0].payload["origin_thought_id"] == "thought::2000"
            assert identity_events[0].payload["result"] == "accepted"
            assert helios.get_state()["identity"]["identity_narrative"] == "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
            assert helios.identity_store.identity_metadata["autobiographical_identity_narrative"]["summary"] == "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)