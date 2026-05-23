"""Tests for channel abstractions and ChannelGateway routing."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.helios_state import HeliosState
from helios_io.channel import BidirectionalChannel, ChannelMessage, ChannelStatus
from helios_io.channel_gateway import ChannelGateway


@dataclass
class StubChannel(BidirectionalChannel):
    _channel_id: str
    connected: bool = True
    inbound_messages: List[ChannelMessage] = field(default_factory=list)
    sent_messages: List[ChannelMessage] = field(default_factory=list)
    connect_calls: int = 0
    disconnect_calls: int = 0

    @property
    def channel_id(self) -> str:
        return self._channel_id

    def poll(self) -> List[ChannelMessage]:
        messages = list(self.inbound_messages)
        self.inbound_messages.clear()
        return messages

    def send(self, message: ChannelMessage) -> bool:
        self.sent_messages.append(message)
        return True

    def is_connected(self) -> bool:
        return self.connected

    def connect(self) -> None:
        self.connect_calls += 1
        self.connected = True

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False


def make_message(channel_id: str, user_id: str, text: str, timestamp: float = 1.0) -> ChannelMessage:
    return ChannelMessage(
        channel_id=channel_id,
        user_id=user_id,
        text=text,
        timestamp=timestamp,
        metadata={"message_id": f"{channel_id}-{user_id}"},
        direction="inbound",
    )


class TestChannelGatewayRegistrationAndRouting:
    def test_route_outbound_to_matching_channel(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        tts = StubChannel("tts")
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        ok = gateway.route_outbound(
            ChannelMessage(
                channel_id="tts",
                user_id="user-1",
                text="hello",
                timestamp=2.0,
                direction="outbound",
            )
        )

        assert ok is True
        assert len(qq.sent_messages) == 0
        assert len(tts.sent_messages) == 1
        assert tts.sent_messages[0].text == "hello"

    def test_route_outbound_skips_disconnected_channel(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        ok = gateway.route_outbound(
            ChannelMessage(
                channel_id="qq",
                user_id="user-1",
                text="hello",
                timestamp=2.0,
                direction="outbound",
            )
        )

        assert ok is False
        assert qq.sent_messages == []

    def test_poll_all_collects_from_connected_channels_only(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "hello")])
        vision = StubChannel("vision", connected=False, inbound_messages=[make_message("vision", "cam", "frame")])
        gateway.register_channel(qq)
        gateway.register_channel(vision)

        polled = gateway.poll_all(HeliosState())

        assert [message.text for message in polled] == ["hello"]

    def test_get_channel_status_reports_connected_and_disconnected(self):
        gateway = ChannelGateway()
        gateway.register_channel(StubChannel("qq", connected=True))
        gateway.register_channel(StubChannel("tts", connected=False))

        statuses = gateway.get_channel_status()

        assert statuses["qq"] == ChannelStatus.CONNECTED
        assert statuses["tts"] == ChannelStatus.DISCONNECTED

    def test_get_channel_status_prefers_explicit_channel_status(self):
        gateway = ChannelGateway()

        class ReconnectingStub(StubChannel):
            def get_status(self) -> ChannelStatus:
                return ChannelStatus.RECONNECTING

        gateway.register_channel(ReconnectingStub("qq", connected=False))

        statuses = gateway.get_channel_status()

        assert statuses["qq"] == ChannelStatus.RECONNECTING

    def test_connect_and_disconnect_all_deduplicate_bidirectional_channels(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        gateway.connect_all()
        gateway.disconnect_all()

        assert qq.connect_calls == 1
        assert qq.disconnect_calls == 1


class TestChannelGatewayEventSourceAdapter:
    def test_poll_merges_triggers_from_registered_evaluators(self):
        gateway = ChannelGateway(
            evaluators={
                "qq": lambda message, state: {"CARE": 0.4 if state.tick == 7 else 0.2},
                "vision": lambda message, state: {"FEAR": 0.6},
            }
        )
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "你好")])
        vision = StubChannel("vision", inbound_messages=[make_message("vision", "camera", "motion")])
        gateway.register_channel(qq)
        gateway.register_channel(vision)

        triggers = gateway.poll(HeliosState(tick=7))

        assert triggers == {"CARE": 0.4, "FEAR": 0.6}

    def test_get_messages_returns_raw_message_dicts_from_last_poll(self):
        gateway = ChannelGateway(evaluators={"qq": lambda message, state: {}})
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "hello")])
        gateway.register_channel(qq)

        gateway.poll(HeliosState())
        messages = gateway.get_messages()

        assert len(messages) == 1
        assert messages[0]["channel_id"] == "qq"
        assert messages[0]["user_id"] == "u1"
        assert messages[0]["text"] == "hello"

    def test_broadcast_routes_to_all_non_excluded_channels(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        tts = StubChannel("tts")
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        results = gateway.broadcast("sync", exclude=["qq"])

        assert results == {"tts": True}
        assert len(qq.sent_messages) == 0
        assert len(tts.sent_messages) == 1
        assert tts.sent_messages[0].direction == "outbound"