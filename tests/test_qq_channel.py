"""Tests for QQChannel."""

from __future__ import annotations

import queue
import sys
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.channel import ChannelMessage, ChannelStatus
from helios_io.channels.qq_channel import QQChannel, WebSocketReconnector


@dataclass
class FakeQQMessage:
    text: str = ""
    user_id: str = ""
    message_id: str = ""
    timestamp: float = 0.0
    is_group: bool = False
    group_id: str = ""
    raw: dict = field(default_factory=dict)


class MockSECEvaluator:
    def __init__(self, triggers_map=None):
        self._triggers_map = triggers_map or {}

    def evaluate(self, text: str) -> dict:
        return self._triggers_map.get(text, {})


class TestQQChannelPoll:
    def test_poll_drains_queue_to_channel_messages(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        q.put(FakeQQMessage(text="hello", user_id="u1", message_id="m1", timestamp=123.0))

        channel = QQChannel(q, qq_client=client)
        messages = channel.poll()

        assert len(messages) == 1
        assert messages[0].channel_id == "qq"
        assert messages[0].user_id == "u1"
        assert messages[0].text == "hello"
        assert messages[0].metadata["message_id"] == "m1"
        assert channel.poll() == []

    def test_poll_still_drains_local_queue_when_disconnected(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = False
        q.put(FakeQQMessage(text="hello", user_id="u1"))

        channel = QQChannel(q, qq_client=client)

        messages = channel.poll()
        assert len(messages) == 1
        assert messages[0].text == "hello"

    def test_poll_enriches_inbound_metadata_with_sec_and_cognitive_impact(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        evaluator = MagicMock()
        evaluator.evaluate.return_value = {"CARE": 0.7, "SEEKING": 0.4}
        q.put(FakeQQMessage(text="想你了", user_id="u1", message_id="m1", timestamp=123.0))

        channel = QQChannel(q, qq_client=client, sec_evaluator=evaluator)
        messages = channel.poll()

        assert len(messages) == 1
        metadata = messages[0].metadata
        assert metadata["event_triggers"] == {"CARE": 0.7, "SEEKING": 0.4}
        assert "sec_result" in metadata
        assert "cognitive_impact" in metadata
        assert metadata["cognitive_impact"]["novelty"] >= 0.0
        assert metadata["cognitive_impact"]["self_"] > 0.0


class TestQQChannelSend:
    def test_send_routes_private_message_via_send_c2c(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        client.send_c2c.return_value = True
        channel = QQChannel(q, qq_client=client)

        ok = channel.send(
            ChannelMessage(
                channel_id="qq",
                user_id="target_user",
                text="reply",
                timestamp=1.0,
                metadata={"message_id": "mid"},
                direction="outbound",
            )
        )

        assert ok is True
        client.send_c2c.assert_called_once_with("target_user", "reply", msg_id="mid")

    def test_send_modulates_text_when_outbound_intensity_is_high(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        client.send_c2c.return_value = True
        channel = QQChannel(q, qq_client=client)

        ok = channel.send(
            ChannelMessage(
                channel_id="qq",
                user_id="target_user",
                text="reply...",
                timestamp=1.0,
                metadata={"message_id": "mid", "outbound_intensity": 0.91},
                direction="outbound",
            )
        )

        assert ok is True
        client.send_c2c.assert_called_once_with("target_user", "reply!", msg_id="mid")

    def test_send_records_original_and_rendered_text_on_message_metadata(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        client.send_c2c.return_value = True
        channel = QQChannel(q, qq_client=client)
        message = ChannelMessage(
            channel_id="qq",
            user_id="target_user",
            text="reply...",
            timestamp=1.0,
            metadata={"message_id": "mid", "outbound_intensity": 0.91},
            direction="outbound",
        )

        ok = channel.send(message)

        assert ok is True
        assert message.metadata["original_text"] == "reply..."
        assert message.metadata["rendered_text"] == "reply!"
        assert message.metadata["expression_profile"]["tone"] == "direct"

    def test_send_routes_group_message_via_send_group(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        client.send_group.return_value = True
        channel = QQChannel(q, qq_client=client)

        ok = channel.send(
            ChannelMessage(
                channel_id="qq",
                user_id="ignored",
                text="reply",
                timestamp=1.0,
                metadata={"is_group": True, "group_id": "g1", "message_id": "mid"},
                direction="outbound",
            )
        )

        assert ok is True
        client.send_group.assert_called_once_with("g1", "reply", msg_id="mid")

    def test_send_returns_false_when_disconnected(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = False
        channel = QQChannel(q, qq_client=client)

        ok = channel.send(
            ChannelMessage(
                channel_id="qq",
                user_id="u1",
                text="reply",
                timestamp=1.0,
                direction="outbound",
            )
        )

        assert ok is False
        client.send_c2c.assert_not_called()


class TestQQChannelStateAndEvaluation:
    def test_is_connected_delegates_to_client(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        channel = QQChannel(q, qq_client=client)

        assert channel.is_connected() is True

    def test_connect_and_disconnect_delegate_to_client(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = False
        channel = QQChannel(q, qq_client=client)

        channel.connect()
        channel.disconnect()

        client.start.assert_called_once()
        client.stop.assert_called_once()

    def test_get_status_reports_reconnecting_after_disconnect_transition(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.side_effect = [True, False]
        channel = QQChannel(q, qq_client=client)

        assert channel.is_connected() is True
        assert channel.get_status() == ChannelStatus.RECONNECTING

    def test_get_status_uses_client_reconnect_attempts_when_already_retrying(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = False
        client._reconnect_attempts = 3
        channel = QQChannel(q, qq_client=client)

        assert channel.get_status() == ChannelStatus.RECONNECTING

    def test_disconnect_resets_reconnector_state(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.side_effect = [True, False]
        channel = QQChannel(q, qq_client=client)

        assert channel.is_connected() is True
        channel.get_status()
        channel.disconnect()

        assert channel.get_status() == ChannelStatus.DISCONNECTED

    def test_evaluate_message_uses_sec_evaluator(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        evaluator = MockSECEvaluator({"你好": {"CARE": 0.7}})
        channel = QQChannel(q, qq_client=client, sec_evaluator=evaluator)

        triggers = channel.evaluate_message(
            ChannelMessage(
                channel_id="qq",
                user_id="u1",
                text="你好",
                timestamp=1.0,
            )
        )

        assert triggers == {"CARE": 0.7}

    def test_evaluate_message_prefers_precomputed_event_triggers(self):
        q = queue.Queue()
        client = MagicMock()
        client.is_connected.return_value = True
        evaluator = MagicMock()
        channel = QQChannel(q, qq_client=client, sec_evaluator=evaluator)

        triggers = channel.evaluate_message(
            ChannelMessage(
                channel_id="qq",
                user_id="u1",
                text="你好",
                timestamp=1.0,
                metadata={"event_triggers": {"CARE": 0.5}},
            )
        )

        assert triggers == {"CARE": 0.5}
        evaluator.evaluate.assert_not_called()


class TestWebSocketReconnector:
    def test_on_disconnect_increments_attempts(self):
        reconnector = WebSocketReconnector(delays=[1, 2, 5])

        reconnector.on_disconnect()
        reconnector.on_disconnect()

        assert reconnector.attempt_count == 2

    def test_get_backoff_caps_at_30_seconds(self):
        reconnector = WebSocketReconnector(delays=[1, 2, 5, 10, 30, 60], max_backoff=30.0)

        for _ in range(10):
            reconnector.on_disconnect()

        assert reconnector.get_backoff() == 30.0

    def test_on_reconnect_resets_attempts(self):
        reconnector = WebSocketReconnector(delays=[1, 2, 5])
        reconnector.on_disconnect()

        reconnector.on_reconnect()

        assert reconnector.attempt_count == 0
        assert reconnector.last_disconnect_at == 0.0