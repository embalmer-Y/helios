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
from typing import Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

import pytest

# ── Load helios_main via importlib to avoid import issues ──
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_main import Helios, HeliosConfig


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
    return h


# ═══════════════════════════════════════════════════
# Tests for ResponsePipeline wiring in _tick()
# ═══════════════════════════════════════════════════

class TestTickResponseWiring:
    """Test that ResponsePipeline is correctly wired into _tick()."""

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
