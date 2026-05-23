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

            events = helios.behavior_catalog.registry.list_feedback_events(source_path="preconscious_thought")
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
                intent_type="internal_bias",
                behavior_name="speak_share",
                score_bundle={"final": 0.45},
                constraints={"internal_only": True},
                candidate_channels=["qq"],
                suggested_modalities=["internal"],
                provenance={"thought_type": "rumination"},
                parameters={"preconscious_context": {"thought_type": "rumination"}},
            )
            accepted = ActionProposal(
                proposal_id="proposal::preconscious::accept",
                source_type="preconscious",
                source_module="preconscious_policy",
                intent_type="internal_bias",
                behavior_name="reflect",
                score_bundle={"final": 0.52},
                constraints={"internal_only": True},
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
            assert helios.preconscious_policy.rejection_history[-1]["rejection_reason"] == "internal_only_constraint"
            assert helios.preconscious_policy.feedback_history[-1]["success"] is True
            assert helios.last_preconscious_trace["latest_rejection"]["rejection_reason"] == "internal_only_constraint"
            assert helios.last_preconscious_trace["latest_feedback"]["success"] is True
            assert helios.get_state()["preconscious"]["latest_feedback"]["success"] is True
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)