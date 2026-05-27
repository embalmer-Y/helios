"""
tests/test_tick_response_wiring.py — Test passive message wiring in main tick loop

Verifies that:
    1. When messages arrive, SEC evaluator is called for each message
    2. Runtime no longer calls a parallel reply LLM owner in the passive path
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
from helios_io.action_models import ActionDecision, ActionProposal, ThoughtActionProposal
from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor, ChannelStatus
from personality_contract import build_personality_contract


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


def make_output_descriptor(channel_id: str) -> ChannelDescriptor:
    return ChannelDescriptor(
        channel_id=channel_id,
        display_name=channel_id.upper(),
        output_types=["text_message"],
        output_formats=["text/plain"],
        capabilities=["send", "text_output"],
        supported_ops=[
            ChannelOpDescriptor(
                name="send",
                direction="output",
                description=f"{channel_id} output",
            )
        ],
    )


def make_thought_cycle_result(*, triggered: bool, thought=None, trigger_reason: str = "test", action_proposal=None):
    return SimpleNamespace(
        triggered=triggered,
        trigger_reason=trigger_reason,
        thought=thought,
        action_proposal=action_proposal or {},
    )


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


class TestCLIChannelBootstrap:
    def test_cli_channel_registers_when_enabled(self, tmp_path, monkeypatch):
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
        config.CLI_ENABLED = True
        config.CLI_USER_ID = "local-user"
        config.CLI_SESSION_NAME = "session-a"

        h = Helios(config)
        try:
            descriptors = h._channel_gateway.get_channel_descriptors()
            cli_channel = h.get_runtime_channel("cli")

            assert "cli" in descriptors
            assert descriptors["cli"].display_name == "Terminal CLI Channel"
            assert cli_channel is not None
            assert cli_channel.is_available is True
        finally:
            h._channel_gateway.disconnect_all()
            for handler in list(h.log.handlers):
                handler.close()
                h.log.removeHandler(handler)

    def test_cli_channel_is_not_registered_when_disabled(self, tmp_path, monkeypatch):
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
        config.CLI_ENABLED = False

        h = Helios(config)
        try:
            descriptors = h._channel_gateway.get_channel_descriptors()
            cli_channel = h.get_runtime_channel("cli")

            assert "cli" not in descriptors
            assert cli_channel is None
        finally:
            h._channel_gateway.disconnect_all()
            for handler in list(h.log.handlers):
                handler.close()
                h.log.removeHandler(handler)

    def test_cli_ordinary_text_enters_passive_runtime_path(self, tmp_path, monkeypatch):
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
        config.CLI_ENABLED = True
        config.CLI_USER_ID = "local-user"
        config.CLI_SESSION_NAME = "session-a"

        h = Helios(config)
        try:
            cli_channel = h.get_runtime_channel("cli")
            h.sec_evaluator.evaluate = MagicMock(return_value={
                "goal_relevance": 0.2,
                "novelty": 0.1,
                "pleasantness": 0.0,
            })
            h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
            h.regulation.generate_action_proposals = MagicMock(return_value=[])
            h.response_pipeline.record_exchange = MagicMock()

            assert cli_channel is not None
            cli_channel.submit_input("hello helios")
            h._tick()

            assert h.sec_evaluator.evaluate.call_count == 2
            assert h.sec_evaluator.evaluate.call_args_list[0].args[0] == "hello helios"
            assert h.sec_evaluator.evaluate.call_args_list[1].args[0] == "hello helios"
            h.response_pipeline.record_exchange.assert_called_once()
            kwargs = h.response_pipeline.record_exchange.call_args.kwargs
            assert kwargs["user_id"] == "local-user"
            assert kwargs["message"] == "hello helios"
            assert kwargs["conversation_key"] == "session-a"
        finally:
            h._channel_gateway.disconnect_all()
            for handler in list(h.log.handlers):
                handler.close()
                h.log.removeHandler(handler)

    def test_cli_management_command_does_not_enter_stimulus_path(self, tmp_path, monkeypatch):
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
        config.CLI_ENABLED = True

        h = Helios(config)
        try:
            cli_channel = h.get_runtime_channel("cli")
            h.sec_evaluator.evaluate = MagicMock(return_value={
                "goal_relevance": 0.2,
                "novelty": 0.1,
                "pleasantness": 0.0,
            })
            h.response_pipeline.record_exchange = MagicMock()
            h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
            h.regulation.generate_action_proposals = MagicMock(return_value=[])

            assert cli_channel is not None
            cli_channel.submit_input("/help")
            h._tick()

            h.sec_evaluator.evaluate.assert_not_called()
            h.response_pipeline.record_exchange.assert_not_called()
            results = cli_channel.get_command_results()
            assert len(results) == 1
            assert results[0].command_name == "help"
            assert results[0].handled is True
        finally:
            h._channel_gateway.disconnect_all()
            for handler in list(h.log.handlers):
                handler.close()
                h.log.removeHandler(handler)

    def test_cli_text_does_not_auto_capture_qq_target(self, tmp_path, monkeypatch):
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
        config.QQ_TARGET_ID = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False
        config.CLI_ENABLED = True
        config.CLI_USER_ID = "local-user"
        config.CLI_SESSION_NAME = "session-a"

        h = Helios(config)
        try:
            cli_channel = h.get_runtime_channel("cli")
            h.sec_evaluator.evaluate = MagicMock(return_value={
                "goal_relevance": 0.2,
                "novelty": 0.1,
                "pleasantness": 0.0,
            })
            h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
            h.regulation.generate_action_proposals = MagicMock(return_value=[])
            h.response_pipeline.record_exchange = MagicMock()

            assert cli_channel is not None
            cli_channel.submit_input("hello helios")
            h._tick()

            assert h.cfg.QQ_TARGET_ID == ""
        finally:
            h._channel_gateway.disconnect_all()
            for handler in list(h.log.handlers):
                handler.close()
                h.log.removeHandler(handler)

    def test_generate_reply_not_called_even_when_should_reply_true(self, helios_instance):
        """Passive path should not call a parallel reply LLM owner anymore."""
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.6,
            "novelty": 0.4,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="你好呀~")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "user1", "channel_id": "qq"})

        h._tick()

        h.response_pipeline.generate_reply.assert_not_called()

    def test_generate_reply_not_called_when_should_reply_false(self, helios_instance):
        """When no thought is produced and reply policy declines, fallback reply generation should not run."""
        h = helios_instance
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
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

    def test_no_passive_reply_is_sent_without_thought_owned_payload(self, helios_instance):
        """No passive reply should be routed when no thought-origin outbound payload exists."""
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))

        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.6,
            "novelty": 0.4,
        })
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="回复内容")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "target_user", "channel_id": "qq"})

        h._tick()

        h._channel_gateway.route_outbound.assert_not_called()

    def test_exchange_recorded_without_reply_when_no_thought_owned_payload(self, helios_instance):
        """Passive path should still record the exchange even when no reply is emitted."""
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
        sec_result = {"goal_relevance": 0.6, "novelty": 0.4}
        h.sec_evaluator.evaluate = MagicMock(return_value=sec_result)
        h.response_pipeline.should_reply = MagicMock(return_value=True)
        h.response_pipeline.generate_reply = MagicMock(return_value="hi!")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "hey", "user_id": "user1", "channel_id": "qq"})

        h._tick()

        h.response_pipeline.record_exchange.assert_called_once()
        call_kwargs = h.response_pipeline.record_exchange.call_args[1]
        assert call_kwargs["user_id"] == "user1"
        assert call_kwargs["message"] == "hey"
        assert call_kwargs["reply"] is None
        assert call_kwargs["sec_result"] == sec_result
        assert "dominant_system" in call_kwargs["emotional_context"]
        assert "valence" in call_kwargs["emotional_context"]

    def test_exchange_recorded_without_reply(self, helios_instance):
        """No-thought fallback path should still record reply=None when reply policy declines."""
        h = helios_instance
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
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

    def test_quiet_tick_internal_thought_stays_internal_and_observable(self, helios_instance):
        h = helios_instance
        h.qq = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.response_pipeline.generate_reply = MagicMock()
        h.response_pipeline.record_exchange = MagicMock()
        h.thinking_integration = MagicMock(
            generate=MagicMock(
                side_effect=lambda state: (
                    setattr(state, "dmn_active", True),
                    setattr(state, "thought_generated_this_tick", True),
                    setattr(
                        state,
                        "last_internal_thought_trace",
                        {
                            "triggered": True,
                            "trigger_reason": "eligible",
                            "llm_used": False,
                            "fallback_used": True,
                            "output_destination": "internal_log,memory,preconscious",
                            "write_result": "written",
                            "rejected_reason": "missing_api_key",
                        },
                    ),
                    make_thought_cycle_result(
                        triggered=True,
                        thought=SimpleNamespace(
                            type="self_question",
                            content="我在整理刚才盘旋的念头。",
                            timestamp=time.time(),
                            triggered_by="SEEKING",
                            source_path="internal_thought_llm",
                            llm_used=False,
                            fallback_used=True,
                            metadata={"behavior_name": "think_message"},
                        ),
                    ),
                )[-1]
            )
        )

        h._tick()

        h.response_pipeline.generate_reply.assert_not_called()
        h.response_pipeline.record_exchange.assert_not_called()
        h.qq.send_c2c.assert_not_called()
        assert h.get_state()["internal_thought"]["triggered"] is True
        assert h.get_state()["internal_thought"]["output_destination"] == "internal_log,memory,preconscious"
        assert "continuation_pressure" in h.get_state()
        assert "thought_cycle" in h.get_state()

    def test_tick_exposes_stimulus_and_thought_gate_observability(self, helios_instance):
        h = helios_instance
        h._msg_queue.put({"text": "突然想到一件事", "user_id": "u1", "channel_id": "qq"})
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._tick()

        state = h.get_state()
        assert state["current_stimuli"]
        assert state["current_stimuli"][0]["source_channel_id"] == "qq"
        assert "thought_gate" in state
        assert "gate_score" in state["thought_gate"]
        assert "continuation" in state
        assert "active" in state["continuation"]
        assert "directed_retrieval" in state
        assert "query_text" in state["directed_retrieval"]
        assert "retrieval_sec_trace" in state["directed_retrieval"]
        assert isinstance(state["directed_retrieval"]["retrieval_sec_trace"], list)
        assert "public_tiers" in state["memory"]
        assert state["memory"]["public_tiers"][0]["tier_name"] == "short-term"
        assert "tier_snapshots" in state["memory"]

    def test_internal_thought_memory_writes_use_internal_thought_source_path(self, helios_instance):
        h = helios_instance
        h.cfg.INTERNAL_THINK_EPISODIC_WRITE = True
        h.feedback_recorder.record_memory_write = MagicMock()
        h.memory_system.remember = MagicMock(return_value=SimpleNamespace(id="episode-1", summary="内在念头"))

        thought = SimpleNamespace(
            type="self_question",
            content="我在重新整理这个问题。",
            triggered_by="SEEKING",
            source_path="internal_thought_llm",
            llm_used=True,
            fallback_used=False,
            metadata={"behavior_name": "think_message"},
        )
        state = SimpleNamespace(tick=9, valence=0.2, arousal=0.3, icri=0.5)
        moment = SimpleNamespace(moment_id="moment-1", narrative="我在重新整理这个问题。")

        h._on_thought_recorded(thought, state, moment)

        calls = h.feedback_recorder.record_memory_write.call_args_list
        assert calls[0].kwargs["source_path"] == "internal_thought_llm"
        assert calls[0].kwargs["memory_type"] == "autobiographical"
        assert calls[1].kwargs["source_path"] == "internal_thought_llm"
        assert calls[1].kwargs["memory_type"] == "episodic"
        h.memory_system.remember.assert_called_once()

    def test_handle_action_rejects_missing_channel_binding_instead_of_defaulting_to_qq(self, helios_instance):
        h = helios_instance
        h._route_outbound_text = MagicMock(return_value=True)

        ok = h._handle_action(
            "reply_message",
            params={"outbound_text": "hello", "target_user_id": "user1"},
        )

        assert ok is False
        h._route_outbound_text.assert_not_called()

    def test_helios_enables_connected_channel_gating_by_default(self, helios_instance):
        h = helios_instance

        assert h.policy_evaluator._require_connected_channel is True

    def test_route_outbound_text_rejects_missing_qq_target_without_cfg_fallback(self, helios_instance):
        h = helios_instance
        h.cfg.QQ_TARGET_ID = "fallback-user"
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.feedback_recorder.record_execution_consistency_failure = MagicMock()

        ok = h._route_outbound_text(
            channel_id="qq",
            user_id="",
            text="hello",
            metadata={},
            action_label="reply_message",
        )

        assert ok is False
        h._channel_gateway.route_outbound.assert_not_called()
        h.feedback_recorder.record_execution_consistency_failure.assert_called_once()
        assert h.feedback_recorder.record_execution_consistency_failure.call_args.kwargs["payload"]["rejection_reason"] == "missing_target_user_id"

    def test_route_outbound_text_records_consistency_failure_when_channel_disconnects_after_acceptance(self, helios_instance):
        h = helios_instance
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.DISCONNECTED})
        h.feedback_recorder.record_execution_consistency_failure = MagicMock()

        ok = h._route_outbound_text(
            channel_id="qq",
            user_id="user1",
            text="hello",
            metadata={},
            action_label="reply_message",
        )

        assert ok is False
        assert h.decisions_failed_after_acceptance == 1
        h._channel_gateway.route_outbound.assert_not_called()
        h.feedback_recorder.record_execution_consistency_failure.assert_called_once()

    def test_route_outbound_text_records_consistency_failure_when_channel_binding_is_missing(self, helios_instance):
        h = helios_instance
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.feedback_recorder.record_execution_consistency_failure = MagicMock()

        ok = h._route_outbound_text(
            channel_id="",
            user_id="user1",
            text="hello",
            metadata={},
            action_label="reply_message",
        )

        assert ok is False
        assert h.decisions_failed_after_acceptance == 1
        h._channel_gateway.route_outbound.assert_not_called()
        h.feedback_recorder.record_execution_consistency_failure.assert_called_once()
        assert h.feedback_recorder.record_execution_consistency_failure.call_args.kwargs["payload"]["rejection_reason"] == "missing_channel_binding"

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
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
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
        assert outbound.metadata["op_name"] == "send"
        h.qq.send_c2c.assert_not_called()

    def test_active_expression_uses_forwarded_state_for_speech_context(self, helios_instance):
        """Speech generation should receive the current tick state rather than stale runtime fields."""
        h = helios_instance
        h.cfg.QQ_TARGET_ID = "target_user"
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
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
        expected_descriptor, expected_trace = build_personality_contract(
            projection=getattr(h.personality, "get_projection")(),
            traits=h.personality._trait_dict(),
            identity_store=h.identity_store.to_dict(),
            source_path="active_speech_generation",
        )
        assert speech_ctx.dominant_emotion == "FEAR"
        assert speech_ctx.valence == -0.4
        assert speech_ctx.arousal == 0.8
        assert speech_ctx.mood_label == h.mood.state.label
        assert speech_ctx.personality_summary == expected_descriptor.persona_text_summary
        assert speech_ctx.personality_influence_trace == expected_trace.to_dict()

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

    def test_direct_thought_bridge_external_proposal_can_route_before_regulation(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(
            triggered=True,
            thought=SimpleNamespace(
                type="rumination",
                content="我想把这个想法告诉你",
                timestamp=time.time(),
                triggered_by="CARE",
                source_path="internal_thought_llm",
                llm_used=False,
                fallback_used=True,
                metadata={},
            ),
            action_proposal=ThoughtActionProposal(
                origin_thought_id="thought::1::rumination::1000",
                thought_type="rumination",
                scope="external",
                behavior_name="speak_share",
                preferred_op="send",
                params={"target_user_id": "target_user"},
                channel_constraints={"candidate_channels": ["qq"], "requires_target_user": True},
                outbound_intensity=0.68,
                score=0.68,
                reason_trace=["trigger_reason=external_stimulus"],
            ),
        ))
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h._generate_speech = MagicMock(return_value="我想把这个想法告诉你")
        h._channel_gateway.route_outbound = MagicMock(return_value=True)

        h._tick()

        h._channel_gateway.route_outbound.assert_called_once()
        outbound = h._channel_gateway.route_outbound.call_args[0][0]
        assert outbound.channel_id == "qq"
        assert outbound.user_id == "target_user"
        assert outbound.text == "我想把这个想法告诉你"
        assert outbound.metadata["op_name"] == "send"
        assert outbound.metadata["origin_type"] == "thought"
        assert outbound.metadata["origin_id"] == "thought::1::rumination::1000"

    def test_direct_thought_bridge_reply_message_with_outbound_text_routes_without_speech_generation(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(
            triggered=True,
            thought=SimpleNamespace(
                type="rumination",
                content="这次我直接把要说的话作为 payload 给出去。",
                timestamp=time.time(),
                triggered_by="CARE",
                source_path="internal_thought_llm",
                llm_used=False,
                fallback_used=True,
                metadata={},
            ),
            action_proposal=ThoughtActionProposal(
                origin_thought_id="thought::1::reply::1001",
                thought_type="rumination",
                scope="external",
                behavior_name="reply_message",
                preferred_op="send",
                params={
                    "target_user_id": "target_user",
                    "outbound_text": "这是 thought-origin 的直接回复。",
                    "outbound_metadata": {
                        "origin_type": "thought",
                        "origin_id": "thought::1::reply::1001",
                    },
                },
                channel_constraints={"candidate_channels": ["qq"], "requires_target_user": True},
                outbound_intensity=0.81,
                score=0.81,
                reason_trace=["trigger_reason=external_stimulus"],
            ),
        ))
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h._generate_speech = MagicMock(return_value="不应走 speech fallback")
        def route_outbound_with_render(message):
            message.metadata["rendered_text"] = "这是 thought-origin 的直接回复！"
            message.metadata["expression_profile"] = {
                "tone": "direct",
                "compactness": "compact",
                "applied": True,
            }
            return True

        h._channel_gateway.route_outbound = MagicMock(side_effect=route_outbound_with_render)

        h._tick()

        h._generate_speech.assert_not_called()
        h._channel_gateway.route_outbound.assert_called_once()
        outbound = h._channel_gateway.route_outbound.call_args[0][0]
        assert outbound.channel_id == "qq"
        assert outbound.user_id == "target_user"
        assert outbound.text == "这是 thought-origin 的直接回复。"
        assert outbound.metadata["op_name"] == "send"
        assert outbound.metadata["origin_type"] == "thought"
        assert outbound.metadata["origin_id"] == "thought::1::reply::1001"
        assert outbound.metadata["outbound_intensity"] == pytest.approx(0.81)
        channel_events = h.behavior_catalog.registry.list_feedback_events(event_kind="channel_receipt")
        channel_event = next(event for event in channel_events if event.source_path == "thought_action_bridge")
        assert channel_event.payload["original_text"] == "这是 thought-origin 的直接回复。"
        assert channel_event.payload["rendered_text"] == "这是 thought-origin 的直接回复！"
        assert channel_event.payload["expression_profile"]["tone"] == "direct"

    def test_passive_inbound_prefers_direct_thought_bridge_before_reply_and_preconscious_helper(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.7,
            "novelty": 0.4,
            "pleasantness": 0.1,
        })
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(
            triggered=True,
            thought=SimpleNamespace(
                type="rumination",
                content="我想把这段感受说出来",
                timestamp=time.time(),
                triggered_by="CARE",
                source_path="internal_thought_llm",
                llm_used=False,
                fallback_used=True,
                metadata={},
            ),
            action_proposal=ThoughtActionProposal(
                origin_thought_id="thought::1::rumination::1000",
                thought_type="rumination",
                scope="external",
                behavior_name="speak_share",
                preferred_op="send",
                params={"target_user_id": "user1"},
                channel_constraints={"candidate_channels": ["qq"], "requires_target_user": True},
                outbound_intensity=0.72,
                score=0.72,
                reason_trace=["trigger_reason=external_stimulus"],
            ),
        ))
        h.preconscious_policy.propose = MagicMock(return_value=[
            ActionProposal(
                proposal_id="proposal::preconscious::passive::1",
                source_type="preconscious",
                source_module="preconscious_policy",
                origin_type="thought",
                origin_id="thought::1::rumination::1000",
                intent_type="internal_bias",
                behavior_name="reflect",
                score_bundle={"final": 0.61},
                suggested_modalities=["internal"],
                parameters={"tick": 1},
            )
        ])
        h.response_pipeline.generate_reply = MagicMock(return_value="不应直接走 reply pipeline")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h._generate_speech = MagicMock(return_value="我想把这个想法告诉你")

        h._msg_queue.put({"text": "你好", "user_id": "user1", "channel_id": "qq"})

        h._tick()

        h.response_pipeline.generate_reply.assert_not_called()
        h._channel_gateway.route_outbound.assert_called_once()
        outbound = h._channel_gateway.route_outbound.call_args[0][0]
        assert outbound.user_id == "user1"
        assert outbound.text == "我想把这个想法告诉你"

    def test_passive_inbound_can_consume_direct_thought_action_bridge_without_preconscious(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.7,
            "novelty": 0.4,
            "pleasantness": 0.1,
        })
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(
            triggered=True,
            thought=SimpleNamespace(
                type="rumination",
                content="我想把这段判断直接说出来。",
                timestamp=time.time(),
                triggered_by="CARE",
                source_path="internal_thought_llm",
                llm_used=False,
                fallback_used=True,
                metadata={},
            ),
            action_proposal=ThoughtActionProposal(
                origin_thought_id="thought::1::rumination::1000",
                thought_type="rumination",
                scope="external",
                behavior_name="speak_share",
                preferred_op="send",
                params={
                    "target_user_id": "user1",
                    "outbound_metadata": {
                        "origin_type": "thought",
                        "origin_id": "thought::1::rumination::1000",
                    },
                },
                channel_constraints={
                    "candidate_channels": ["qq"],
                    "requires_target_user": True,
                },
                outbound_intensity=0.74,
                score=0.74,
                reason_trace=["trigger_reason=external_stimulus"],
            ),
        ))
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.response_pipeline.generate_reply = MagicMock(return_value="不应直接走 reply pipeline")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])
        h._generate_speech = MagicMock(return_value="我想把这个判断告诉你")

        h._msg_queue.put({"text": "你好", "user_id": "user1", "channel_id": "qq"})

        h._tick()

        h.preconscious_policy.propose.assert_called_once()
        h.response_pipeline.generate_reply.assert_not_called()
        h._channel_gateway.route_outbound.assert_called_once()
        outbound = h._channel_gateway.route_outbound.call_args[0][0]
        assert outbound.user_id == "user1"
        assert outbound.metadata["origin_id"] == "thought::1::rumination::1000"

    def test_passive_direct_reply_fallback_is_suppressed_when_thought_owner_is_active_without_externalization(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.7,
            "novelty": 0.4,
            "pleasantness": 0.0,
        })
        h.thinking_integration.generate = MagicMock(side_effect=lambda state: (
            setattr(state, "thought_generated_this_tick", True),
            setattr(state, "last_thought_type", "rumination"),
            make_thought_cycle_result(
                triggered=True,
                thought=SimpleNamespace(
                    type="rumination",
                    content="我先保留这个念头，不立即说出来。",
                    timestamp=time.time(),
                    triggered_by="CARE",
                    source_path="internal_thought_llm",
                    llm_used=False,
                    fallback_used=True,
                    metadata={},
                ),
            ),
        )[-1])
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.response_pipeline.generate_reply = MagicMock(return_value="不应直接生成")
        h.response_pipeline.record_exchange = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "user1", "channel_id": "qq"})

        h._tick()

        h.response_pipeline.generate_reply.assert_not_called()
        h._channel_gateway.route_outbound.assert_not_called()
        h.response_pipeline.record_exchange.assert_called_once()
        assert h.response_pipeline.record_exchange.call_args[1]["reply"] is None

    def test_no_thought_tick_does_not_consume_removed_response_pipeline_external_proposals(self, helios_instance):
        h = helios_instance
        h._channel_gateway.get_channel_descriptors = MagicMock(return_value={"qq": make_output_descriptor("qq")})
        h._channel_gateway.get_channel_status = MagicMock(return_value={"qq": ChannelStatus.CONNECTED})
        h._channel_gateway.route_outbound = MagicMock(return_value=True)
        h.sec_evaluator.evaluate = MagicMock(return_value={
            "goal_relevance": 0.7,
            "novelty": 0.4,
            "pleasantness": 0.0,
        })
        h.thinking_integration.generate = MagicMock(return_value=make_thought_cycle_result(triggered=False))
        h.preconscious_policy.propose = MagicMock(return_value=[])
        h.response_pipeline.record_exchange = MagicMock()
        h.feedback_recorder.record_execution_consistency_failure = MagicMock()
        h.execution_planner.plan = MagicMock()
        h.limb_bridge.enqueue_decision = MagicMock()
        h.regulation.generate_action_proposals = MagicMock(return_value=[])

        h._msg_queue.put({"text": "你好", "user_id": "user1", "channel_id": "qq", "message_id": "m1"})

        h._tick()

        h.execution_planner.plan.assert_not_called()
        h.limb_bridge.enqueue_decision.assert_not_called()
        h._channel_gateway.route_outbound.assert_not_called()
        h.feedback_recorder.record_execution_consistency_failure.assert_not_called()
        h.response_pipeline.record_exchange.assert_called_once()
        assert h.response_pipeline.record_exchange.call_args[1]["reply"] is None

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
