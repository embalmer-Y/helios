"""
tests/test_tick_response_wiring.py — Test ResponsePipeline wiring in main tick loop

Verifies that:
  1. When messages arrive, SEC evaluator is called for each message
  2. If should_reply() returns True, generate_reply() is called and message is sent via QQ
  3. Exchange is always recorded in conversation history

Requirements: 7.3
"""

import importlib.util
import sys
import time
import queue
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

import pytest

# ── Load helios_main via importlib to avoid import issues ──
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_main import Helios, HeliosConfig
from helios_io.action_models import ActionProposal


# ═══════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════

@pytest.fixture
def helios_instance(tmp_path, monkeypatch):
    """Create a Helios instance with mocked external dependencies."""
    # Suppress QQ bot, LLM, etc.
    monkeypatch.setenv("HELIOS_QQ_APP_ID", "")
    monkeypatch.setenv("HELIOS_QQ_CLIENT_SECRET", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("HELIOS_LLM_SPEECH_ENABLED", "0")
    monkeypatch.setenv("HELIOS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("HELIOS_DATA_DIR", str(tmp_path / "data"))

    config = HeliosConfig()
    config.LOG_DIR = str(tmp_path / "logs")
    config.DATA_DIR = str(tmp_path / "data")
    config.QQ_APP_ID = ""
    config.QQ_CLIENT_SECRET = ""
    config.LLM_API_KEY = ""
    config.LLM_SPEECH_ENABLED = False

    h = Helios(config)
    yield h
    for handler in list(h.log.handlers):
        handler.close()
        h.log.removeHandler(handler)


# ═══════════════════════════════════════════════════
# Tests for ResponsePipeline wiring in _tick()
# ═══════════════════════════════════════════════════

class TestTickResponseWiring:
    """Test that ResponsePipeline is correctly wired into _tick()."""

    def test_tick_enters_through_tick_guard(self, helios_instance):
        """_tick should delegate execution to TickGuard."""
        h = helios_instance
        original_tick_once = h._tick_once
        h._tick_once = MagicMock(side_effect=original_tick_once)
        h.tick_guard.execute = MagicMock(side_effect=lambda fn: fn())

        h._tick()

        h.tick_guard.execute.assert_called_once_with(h._tick_once)
        h._tick_once.assert_called_once()

    def test_safe_mode_skips_reply_pipeline(self, helios_instance):
        """When TickGuard is in safe mode, non-essential reply work should be skipped."""
        h = helios_instance
        h.tick_guard._safe_mode = True
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.8,
            "novelty": 0.5,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="hi")
        h.response_pipeline.record_exchange = MagicMock()

        h._msg_queue.put({"text": "hello", "user_id": "user1"})

        h._tick()

        h.sec_evaluator.evaluate.assert_not_called()
        h.response_pipeline.should_reply.assert_not_called()
        h.response_pipeline.record_exchange.assert_not_called()

    def test_sec_evaluator_called_for_each_message(self, helios_instance):
        """SEC evaluator should be called once per incoming message."""
        h = helios_instance
        # Mock the SEC evaluator
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.5,
            "novelty": 0.3,
            "pleasantness": 0.0,
        })
        # Mock should_reply to return False (avoid generate_reply)
        h.response_pipeline.should_reply = MagicMock(return_value=False)

        # Inject messages into queue
        h._msg_queue.put({"text": "hello", "user_id": "user_a"})
        h._msg_queue.put({"text": "world", "user_id": "user_b"})

        h._tick()

        # SEC evaluator called twice (once per message)
        assert h.sec_evaluator.evaluate.call_count == 2
        calls = h.sec_evaluator.evaluate.call_args_list
        assert calls[0][0][0] == "hello"  # first arg of first call
        assert calls[1][0][0] == "world"  # first arg of second call

    def test_generate_reply_called_when_should_reply_true(self, helios_instance):
        """When should_reply returns True, generate_reply should be invoked."""
        h = helios_instance
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.6,
            "novelty": 0.4,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="你好呀~")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "user1"})

        h._tick()

        h.response_pipeline.generate_reply.assert_called_once()
        call_args = h.response_pipeline.generate_reply.call_args
        msg_arg = call_args[0][0]
        assert msg_arg["text"] == "你好"
        assert msg_arg["user_id"] == "user1"

    def test_generate_reply_not_called_when_should_reply_false(self, helios_instance):
        """When should_reply returns False, generate_reply should not be called."""
        h = helios_instance
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.1,
            "novelty": 0.1,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=False)
        h.response_pipeline.generate_reply = MagicMock()
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "...", "user_id": "user1"})

        h._tick()

        h.response_pipeline.generate_reply.assert_not_called()

    def test_reply_sent_via_qq_when_connected(self, helios_instance):
        """Generated reply should be sent via QQ send_c2c when bot is connected."""
        h = helios_instance
        # Set up mocked QQ
        h.qq = MagicMock()
        h.qq.is_connected.return_value = True
        h.qq.send_c2c.return_value = True

        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.6,
            "novelty": 0.4,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="回复内容")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "target_user"})

        h._tick()

        h.qq.send_c2c.assert_called_once_with("target_user", "回复内容")

    def test_exchange_recorded_with_reply(self, helios_instance):
        """Exchange should be recorded with the reply when one is generated."""
        h = helios_instance
        sec_result = {"goal_relevance": 0.6, "novelty": 0.4}
        h.sec_evaluator.evaluate = MagicMock(return_value=sec_result)
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="hi!")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "hey", "user_id": "user1"})

        h._tick()

        h.response_pipeline.record_exchange.assert_called_once()
        call_kwargs = h.response_pipeline.record_exchange.call_args[1]
        assert call_kwargs["user_id"] == "user1"
        assert call_kwargs["message"] == "hey"
        assert call_kwargs["reply"] == "hi!"
        assert call_kwargs["sec_result"] == sec_result
        assert "dominant_system" in call_kwargs["emotional_context"]
        assert "valence" in call_kwargs["emotional_context"]

    def test_exchange_recorded_without_reply(self, helios_instance):
        """Exchange should be recorded with reply=None when should_reply is False."""
        h = helios_instance
        sec_result = {"goal_relevance": 0.1, "novelty": 0.05}
        h.sec_evaluator.evaluate = MagicMock(return_value=sec_result)
        h.response_pipeline.should_reply = MagicMock(return_value=False)
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "ok", "user_id": "user1"})

        h._tick()

        h.response_pipeline.record_exchange.assert_called_once()
        call_kwargs = h.response_pipeline.record_exchange.call_args[1]
        assert call_kwargs["user_id"] == "user1"
        assert call_kwargs["message"] == "ok"
        assert call_kwargs["reply"] is None

    def test_no_reply_logic_when_no_messages(self, helios_instance):
        """When no messages arrive, the reply pipeline should not be invoked."""
        h = helios_instance
        h.sec_evaluator.evaluate = MagicMock()
        h.response_pipeline.should_reply = MagicMock()
        h.response_pipeline.generate_reply = MagicMock()
        h.response_pipeline.record_exchange = MagicMock()

        # No messages in queue
        h._tick()

        h.sec_evaluator.evaluate.assert_not_called()
        h.response_pipeline.should_reply.assert_not_called()
        h.response_pipeline.record_exchange.assert_not_called()

    def test_conversation_context_passed_to_sec(self, helios_instance):
        """SEC evaluator should receive recent conversation context."""
        h = helios_instance
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        # Pre-populate conversation history using the real method
        h.response_pipeline.record_exchange(
            user_id="user1",
            message="之前的消息",
            reply="之前的回复",
            emotional_context={"valence": 0.3},
            sec_result={"goal_relevance": 0.4},
        )

        # Verify the history is populated before mocking
        assert len(h.response_pipeline.get_history("user1")) == 1

        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.1,
            "novelty": 0.1,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=False)
        # Don't mock record_exchange — let the real implementation record

        h._msg_queue.put({"text": "新消息", "user_id": "user1"})

        h._tick()

        # Verify context was passed as keyword argument
        h.sec_evaluator.evaluate.assert_called_once()
        call_args, call_kwargs = h.sec_evaluator.evaluate.call_args
        # First positional arg is the text
        assert call_args[0] == "新消息"
        # context keyword should contain the previous message
        context_arg = call_kwargs.get("context")
        assert context_arg is not None
        assert "之前的消息" in context_arg

    def test_active_expression_routes_through_channel_gateway(self, helios_instance):
        """Regulation-driven speech should send through ChannelGateway, not direct QQ calls."""
        h = helios_instance
        h.cfg.QQ_TARGET_ID = "target_user"
        h.regulation.generate_action_proposals = MagicMock(return_value=[
            ActionProposal(
                proposal_id="proposal::active::1",
                source_type="regulation",
                source_module="regulation_policy",
                intent_type="self_regulation",
                behavior_name="speak_care",
                score_bundle={"final": 0.72},
                candidate_channels=["qq"],
                parameters={"tick": 1, "target_user_id": "target_user"},
            )
        ])
        h._generate_speech = MagicMock(return_value="主动问候")
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.qq = MagicMock()

        h._tick()

        h._channel_gateway.route_outbound.assert_called_once()
        outbound = h._channel_gateway.route_outbound.call_args[0][0]
        assert outbound.channel_id == "qq"
        assert outbound.user_id == "target_user"
        assert outbound.text == "主动问候"
        h.qq.send_c2c.assert_not_called()

    def test_active_expression_uses_forwarded_state_for_speech_context(self, helios_instance):
        """Speech generation should receive the current tick state rather than stale runtime fields."""
        h = helios_instance
        h.cfg.QQ_TARGET_ID = "target_user"
        h.regulation.generate_action_proposals = MagicMock(return_value=[
            ActionProposal(
                proposal_id="proposal::active::2",
                source_type="regulation",
                source_module="regulation_policy",
                intent_type="self_regulation",
                behavior_name="speak_share",
                score_bundle={"final": 0.74},
                candidate_channels=["qq"],
                parameters={"tick": 1, "target_user_id": "target_user"},
            )
        ])
        h.daisy.cycle = MagicMock(return_value=SimpleNamespace(
            panksepp_activation={"FEAR": 0.7},
            valence=-0.4,
            arousal=0.8,
            dominant_system="FEAR",
        ))
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.speech = MagicMock()
        h.speech.total_generated = 3
        h.speech.generate = MagicMock(return_value="主动表达")

        h._tick()

        speech_ctx = h.speech.generate.call_args[0][0]
        assert speech_ctx.dominant_emotion == "FEAR"
        assert speech_ctx.valence == -0.4
        assert speech_ctx.arousal == 0.8
        assert speech_ctx.mood_label == h.mood.state.label

    def test_preconscious_proposals_can_drive_internal_behavior_before_regulation(self, helios_instance):
        h = helios_instance
        h.preconscious_policy.propose = MagicMock(return_value=[
            ActionProposal(
                proposal_id="proposal::preconscious::1",
                source_type="preconscious",
                source_module="preconscious_policy",
                intent_type="internal_bias",
                behavior_name="reflect",
                score_bundle={"final": 0.46},
                suggested_modalities=["internal"],
                parameters={"tick": 1},
            )
        ])
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h._handle_action = MagicMock(return_value=True)

        h._tick()

        h._handle_action.assert_called_once()
        assert h._handle_action.call_args[0][0] == "reflect"
        h.regulation.generate_action_proposals.assert_called_once()

    def test_channel_message_cognitive_impact_feeds_phi_engine(self, helios_instance):
        """Inbound channel metadata should flow into feed_from_impact before ICRI aggregation."""
        h = helios_instance

        class RecordingPhiEngine:
            def __init__(self):
                self.label = SimpleNamespace(value="focused")
                self.impacts = []

            def feed_sensory(self, *args, **kwargs):
                pass

            def feed_emotional(self, *args, **kwargs):
                pass

            def feed_ignition_from_panksepp(self, *args, **kwargs):
                pass

            def feed_self_model_from_personality(self, *args, **kwargs):
                pass

            def feed_dmn_from_thinking(self, *args, **kwargs):
                pass

            def feed_from_impact(self, impact):
                self.impacts.append(impact)

            def aggregate(self):
                return 0.55

        h.phi_engine = RecordingPhiEngine()
        h._qq_channel._sec_evaluator = MagicMock()
        h._qq_channel._sec_evaluator.evaluate.return_value = {
            "novelty": 0.8,
            "pleasantness": 0.6,
            "goal_relevance": 0.7,
            "goal_congruence": 0.4,
            "coping_potential": 0.6,
            "agency": 0.1,
            "norm_compatibility": 0.5,
        }
        h.daisy.cycle = MagicMock(return_value=SimpleNamespace(
            panksepp_activation={"CARE": 0.4},
            valence=0.4,
            arousal=0.5,
            dominant_system="CARE",
        ))
        h.sec_evaluator.evaluate = MagicMock(return_value={"goal_relevance": 0.1, "novelty": 0.1})
        h.response_pipeline.should_reply = MagicMock(return_value=False)
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好呀，我在想你", "user_id": "user1"})

        h._tick()

        assert len(h.phi_engine.impacts) == 1
        impact = h.phi_engine.impacts[0]
        assert impact.sensory > 0.0
        assert impact.cognitive > 0.0
        assert impact.self_ > 0.0
        assert impact.novelty > 0.0
