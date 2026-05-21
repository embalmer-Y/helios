"""Tests for QQEventSource — verifies queue draining, SEC evaluation, and message buffering."""

import queue
from dataclasses import dataclass, field

import pytest

from core.qq_event_source import QQEventSource
from core.helios_state import HeliosState


# ── Test helpers ──────────────────────────────────────────────


class MockSECEvaluator:
    """Mock SEC evaluator that returns configurable triggers."""

    def __init__(self, triggers_map: dict = None):
        """
        Args:
            triggers_map: dict mapping message text to trigger dicts.
                          If text not found, returns empty dict.
        """
        self._triggers_map = triggers_map or {}
        self.call_count = 0
        self.last_text = ""

    def evaluate(self, text: str) -> dict:
        self.call_count += 1
        self.last_text = text
        return self._triggers_map.get(text, {})


class FailingSECEvaluator:
    """SEC evaluator that always raises an exception."""

    def evaluate(self, text: str) -> dict:
        raise RuntimeError("LLM timeout")


@dataclass
class FakeQQMessage:
    """Mimics the QQMessage dataclass from io_qq.py."""
    text: str = ""
    user_id: str = ""
    message_id: str = ""
    timestamp: float = 0.0
    is_group: bool = False
    group_id: str = ""
    raw: dict = field(default_factory=dict)


# ── Tests ─────────────────────────────────────────────────────


class TestQQEventSourcePoll:
    """Tests for the poll() method."""

    def test_empty_queue_returns_empty(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator()
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        result = source.poll(state)

        assert result == {}
        assert evaluator.call_count == 0

    def test_single_message_returns_triggers(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"你好": {"CARE": 0.5, "SEEKING": 0.3}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="你好", user_id="user1"))
        result = source.poll(state)

        assert result == {"CARE": 0.5, "SEEKING": 0.3}
        assert evaluator.call_count == 1

    def test_multiple_messages_merge_with_max(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({
            "msg1": {"CARE": 0.3, "SEEKING": 0.7},
            "msg2": {"CARE": 0.8, "PANIC": 0.4},
        })
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="msg1"))
        q.put(FakeQQMessage(text="msg2"))
        result = source.poll(state)

        # Max-value merge: CARE=max(0.3,0.8)=0.8, SEEKING=0.7, PANIC=0.4
        assert result == {"CARE": 0.8, "SEEKING": 0.7, "PANIC": 0.4}

    def test_empty_text_message_skips_evaluation(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator()
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text=""))
        result = source.poll(state)

        assert result == {}
        assert evaluator.call_count == 0

    def test_sec_evaluation_failure_handled_gracefully(self):
        q = queue.Queue()
        evaluator = FailingSECEvaluator()
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="hello", user_id="user1"))
        result = source.poll(state)

        # Should not crash, returns empty triggers
        assert result == {}

    def test_dict_messages_handled(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"hi": {"PLAY": 0.6}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put({"text": "hi", "user_id": "u1"})
        result = source.poll(state)

        assert result == {"PLAY": 0.6}


class TestQQEventSourceGetMessages:
    """Tests for the get_messages() method."""

    def test_no_poll_returns_empty(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator()
        source = QQEventSource(q, evaluator)

        assert source.get_messages() == []

    def test_returns_messages_from_last_poll(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"hi": {"PLAY": 0.5}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="hi", user_id="user1", message_id="m1"))
        source.poll(state)

        messages = source.get_messages()
        assert len(messages) == 1
        assert messages[0]["text"] == "hi"
        assert messages[0]["user_id"] == "user1"
        assert messages[0]["message_id"] == "m1"

    def test_subsequent_poll_clears_previous_messages(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"a": {}, "b": {}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="a"))
        source.poll(state)
        assert len(source.get_messages()) == 1

        # Second poll with new message
        q.put(FakeQQMessage(text="b"))
        source.poll(state)
        messages = source.get_messages()
        assert len(messages) == 1
        assert messages[0]["text"] == "b"

    def test_empty_poll_clears_messages(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"x": {}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        q.put(FakeQQMessage(text="x"))
        source.poll(state)
        assert len(source.get_messages()) == 1

        # Empty poll
        source.poll(state)
        assert source.get_messages() == []


class TestQQEventSourceNormalization:
    """Tests for message normalization."""

    def test_qqmessage_object_normalized(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"text1": {}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        msg = FakeQQMessage(
            text="text1",
            user_id="uid",
            message_id="mid",
            timestamp=123.0,
            is_group=True,
            group_id="gid",
            raw={"key": "val"},
        )
        q.put(msg)
        source.poll(state)

        messages = source.get_messages()
        assert len(messages) == 1
        m = messages[0]
        assert m["text"] == "text1"
        assert m["user_id"] == "uid"
        assert m["message_id"] == "mid"
        assert m["timestamp"] == 123.0
        assert m["is_group"] is True
        assert m["group_id"] == "gid"
        assert m["raw"] == {"key": "val"}

    def test_plain_dict_passed_through(self):
        q = queue.Queue()
        evaluator = MockSECEvaluator({"hello": {}})
        source = QQEventSource(q, evaluator)
        state = HeliosState()

        msg_dict = {"text": "hello", "user_id": "u", "extra": "field"}
        q.put(msg_dict)
        source.poll(state)

        messages = source.get_messages()
        assert messages[0] == msg_dict
