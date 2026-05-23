"""QQChannel adapts QQBotClient into the channel abstraction layer."""

from __future__ import annotations

import logging
import queue
import time
from typing import Dict, List, Optional

from ..channel import BidirectionalChannel, ChannelDescriptor, ChannelMessage, ChannelOpDescriptor, ChannelStatus

try:
    from ..protocols.qq import RECONNECT_DELAYS as _QQ_RECONNECT_DELAYS
except Exception:  # pragma: no cover - runtime fallback for isolated loading
    _QQ_RECONNECT_DELAYS = [1, 2, 5, 10, 30, 60]

log = logging.getLogger("helios.helios_io.channels.qq_channel")

_SEC_KEYS = {
    "novelty",
    "pleasantness",
    "goal_relevance",
    "goal_congruence",
    "coping_potential",
    "agency",
    "norm_compatibility",
}


class WebSocketReconnector:
    """Tracks QQ websocket reconnect lifecycle without owning the retry loop."""

    def __init__(self, delays: Optional[List[float]] = None, max_backoff: float = 30.0):
        self._delays = list(delays or _QQ_RECONNECT_DELAYS)
        self._max_backoff = max_backoff
        self._attempt_count = 0
        self._last_disconnect_at = 0.0

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    @property
    def last_disconnect_at(self) -> float:
        return self._last_disconnect_at

    def sync_attempts(self, attempt_count: int) -> None:
        if attempt_count > self._attempt_count:
            self._attempt_count = attempt_count
            if self._last_disconnect_at <= 0.0:
                self._last_disconnect_at = time.time()

    def on_disconnect(self) -> int:
        self._attempt_count += 1
        self._last_disconnect_at = time.time()
        return self._attempt_count

    def on_reconnect(self) -> None:
        self._attempt_count = 0
        self._last_disconnect_at = 0.0

    def reset(self) -> None:
        self.on_reconnect()

    def get_backoff(self) -> float:
        if not self._delays:
            return 0.0
        index = min(max(self._attempt_count - 1, 0), len(self._delays) - 1)
        return min(float(self._delays[index]), self._max_backoff)


class QQChannel(BidirectionalChannel):
    CHANNEL_ID = "qq"
    poll_when_disconnected = True

    def __init__(self, msg_queue: queue.Queue, qq_client=None, sec_evaluator=None):
        self._queue = msg_queue
        self._qq_client = None
        self._qq_client_getter = None
        if qq_client is not None and callable(qq_client) and not hasattr(qq_client, "is_connected"):
            self._qq_client_getter = qq_client
        else:
            self._qq_client = qq_client
        self._sec_evaluator = sec_evaluator
        self._reconnector = WebSocketReconnector()
        self._status = ChannelStatus.DISCONNECTED
        self._last_connected = False
        self._manual_disconnect = False

    def _client(self):
        if self._qq_client_getter is not None:
            return self._qq_client_getter()
        return self._qq_client

    @property
    def channel_id(self) -> str:
        return self.CHANNEL_ID

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self.CHANNEL_ID,
            display_name="QQ Channel",
            input_types=["text_message"],
            output_types=["text_message"],
            input_formats=["qq:c2c", "qq:group"],
            output_formats=["qq:c2c", "qq:group"],
            capabilities=["poll", "send", "text_output", "text_input", "sec_annotation", "direct_message", "group_message"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description="Poll inbound QQ messages and normalize them into ChannelMessage objects.",
                    output_schema={"messages": "list[ChannelMessage]"},
                ),
                ChannelOpDescriptor(
                    name="send",
                    direction="output",
                    description="Send a QQ C2C or group text message.",
                    input_schema={"message": "ChannelMessage(text, user_id, metadata[message_id|group_id|is_group])"},
                    output_schema={"success": "bool"},
                ),
            ],
            management_ops=[
                ChannelOpDescriptor("connect", "management", "Connect the QQ websocket client."),
                ChannelOpDescriptor("disconnect", "management", "Disconnect the QQ websocket client."),
            ],
            startup_requirements=["qq_client available"],
            shutdown_requirements=["qq client stop when present"],
            health_signals=["is_connected", "get_status", "reconnect_attempts"],
            ack_schema={"success": "bool", "delivery": "best_effort"},
            limitations=["Current output support is text-only."],
        )

    def get_status(self) -> ChannelStatus:
        self._refresh_connection_state()
        return self._status

    def poll(self) -> List[ChannelMessage]:
        messages: List[ChannelMessage] = []
        while True:
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                break
            messages.append(self._annotate_inbound_message(self._normalize_message(msg)))

        return messages

    def send(self, message: ChannelMessage) -> bool:
        client = self._client()
        if not self.is_connected():
            return False

        metadata = dict(message.metadata)
        msg_id = metadata.get("message_id", "")
        is_group = metadata.get("is_group", False)
        group_id = metadata.get("group_id", "")

        try:
            if is_group and group_id:
                if msg_id:
                    return bool(client.send_group(group_id, message.text, msg_id=msg_id))
                return bool(client.send_group(group_id, message.text))
            if msg_id:
                return bool(client.send_c2c(message.user_id, message.text, msg_id=msg_id))
            return bool(client.send_c2c(message.user_id, message.text))
        except Exception as exc:
            log.warning("QQChannel send failed: %s", exc)
            return False

    def is_connected(self) -> bool:
        return self._refresh_connection_state()

    def _refresh_connection_state(self) -> bool:
        client = self._client()
        if client is None:
            self._status = ChannelStatus.DISCONNECTED
            self._last_connected = False
            return False

        try:
            connected = bool(client.is_connected())
        except Exception:
            self._status = ChannelStatus.DISCONNECTED if self._manual_disconnect else ChannelStatus.ERROR
            self._last_connected = False
            return False

        external_attempts = self._client_reconnect_attempts(client)
        if external_attempts > 0:
            self._reconnector.sync_attempts(external_attempts)

        if connected:
            if not self._last_connected:
                self._reconnector.on_reconnect()
            self._manual_disconnect = False
            self._status = ChannelStatus.CONNECTED
            self._last_connected = True
            return True

        if self._last_connected:
            attempt = self._reconnector.on_disconnect()
            self._status = ChannelStatus.RECONNECTING if attempt > 0 else ChannelStatus.DISCONNECTED
        elif self._reconnector.attempt_count > 0 or external_attempts > 0:
            self._status = ChannelStatus.RECONNECTING
        elif self._status == ChannelStatus.CONNECTING:
            self._status = ChannelStatus.CONNECTING
        else:
            self._status = ChannelStatus.DISCONNECTED

        self._last_connected = False
        return False

    def connect(self) -> None:
        client = self._client()
        if client is None:
            return
        if not self.is_connected() and hasattr(client, "start"):
            self._manual_disconnect = False
            self._status = ChannelStatus.CONNECTING
            client.start()

    def disconnect(self) -> None:
        client = self._client()
        if client is None:
            return
        if hasattr(client, "stop"):
            client.stop()
        self._reconnector.reset()
        self._manual_disconnect = True
        self._status = ChannelStatus.DISCONNECTED
        self._last_connected = False

    @staticmethod
    def _client_reconnect_attempts(client) -> int:
        attempts = getattr(client, "_reconnect_attempts", 0)
        try:
            return max(0, int(attempts))
        except Exception:
            return 0

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        cached_triggers = dict(message.metadata.get("event_triggers", {}) or {})
        if cached_triggers:
            return cached_triggers
        if self._sec_evaluator is None or not message.text:
            return {}
        try:
            result = self._sec_evaluator.evaluate(message.text)
            if self._looks_like_sec_result(result):
                return self._sec_to_triggers(result)
            return dict(result or {})
        except Exception as exc:
            log.warning("QQChannel SEC evaluation failed: %s", exc)
            return {}

    def _annotate_inbound_message(self, message: ChannelMessage) -> ChannelMessage:
        if not message.text:
            return message

        metadata = dict(message.metadata)
        triggers = dict(metadata.get("event_triggers", {}) or {})
        sec_result = dict(metadata.get("sec_result", {}) or {})

        if self._sec_evaluator is not None and not triggers:
            try:
                evaluation = self._sec_evaluator.evaluate(message.text)
            except Exception as exc:
                log.warning("QQChannel inbound annotation failed: %s", exc)
                evaluation = {}

            if self._looks_like_sec_result(evaluation):
                sec_result = dict(evaluation)
                triggers = self._sec_to_triggers(sec_result)
            else:
                triggers = dict(evaluation or {})
                sec_result = self._triggers_to_sec(triggers)
        elif triggers and not sec_result:
            sec_result = self._triggers_to_sec(triggers)

        if triggers:
            metadata["event_triggers"] = triggers
        if sec_result:
            metadata["sec_result"] = sec_result
            metadata["cognitive_impact"] = self._build_cognitive_impact(message.text, sec_result, triggers)

        return ChannelMessage(
            channel_id=message.channel_id,
            user_id=message.user_id,
            text=message.text,
            timestamp=message.timestamp,
            metadata=metadata,
            direction=message.direction,
        )

    @staticmethod
    def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(minimum, min(maximum, value))

    @classmethod
    def _looks_like_sec_result(cls, result: object) -> bool:
        return isinstance(result, dict) and bool(_SEC_KEYS.intersection(result.keys()))

    @classmethod
    def _sec_to_triggers(cls, sec_result: Dict[str, float]) -> Dict[str, float]:
        novelty = cls._clamp(sec_result.get("novelty", 0.0))
        pleasantness = sec_result.get("pleasantness", 0.0)
        goal_relevance = cls._clamp(sec_result.get("goal_relevance", 0.0))
        goal_congruence = sec_result.get("goal_congruence", 0.0)
        coping = cls._clamp(sec_result.get("coping_potential", 0.5))
        agency = sec_result.get("agency", 0.0)
        norm = sec_result.get("norm_compatibility", 0.0)

        triggers = {
            "SEEKING": cls._clamp(0.55 * novelty + 0.45 * goal_relevance + max(goal_congruence, 0.0) * 0.15),
            "CARE": cls._clamp(max(pleasantness, 0.0) * 0.55 + goal_relevance * 0.25 + max(norm, 0.0) * 0.20),
            "PLAY": cls._clamp(max(pleasantness, 0.0) * 0.45 + novelty * 0.35 + coping * 0.20),
            "PANIC": cls._clamp(max(-pleasantness, 0.0) * 0.45 + goal_relevance * 0.35 + (1.0 - coping) * 0.20),
            "FEAR": cls._clamp(max(-pleasantness, 0.0) * 0.35 + novelty * 0.35 + (1.0 - coping) * 0.30),
            "RAGE": cls._clamp(max(-goal_congruence, 0.0) * 0.45 + max(-pleasantness, 0.0) * 0.25 + max(-agency, 0.0) * 0.30),
        }
        return {key: value for key, value in triggers.items() if value > 0.0}

    @classmethod
    def _triggers_to_sec(cls, triggers: Dict[str, float]) -> Dict[str, float]:
        seeking = cls._clamp(triggers.get("SEEKING", 0.0))
        care = cls._clamp(triggers.get("CARE", 0.0))
        play = cls._clamp(triggers.get("PLAY", 0.0))
        panic = cls._clamp(triggers.get("PANIC", 0.0))
        fear = cls._clamp(triggers.get("FEAR", 0.0))
        rage = cls._clamp(triggers.get("RAGE", 0.0))

        pleasantness = cls._clamp(0.6 * care + 0.55 * play - 0.45 * panic - 0.4 * fear - 0.5 * rage, -1.0, 1.0)
        goal_congruence = cls._clamp(0.5 * seeking + 0.3 * care - 0.45 * fear - 0.55 * rage - 0.5 * panic, -1.0, 1.0)
        agency = cls._clamp(0.2 * seeking - 0.6 * rage - 0.2 * fear, -1.0, 1.0)
        norm = cls._clamp(0.35 * care + 0.25 * play - 0.3 * rage, -1.0, 1.0)

        return {
            "novelty": cls._clamp(max(seeking, play * 0.7, fear * 0.6)),
            "pleasantness": pleasantness,
            "goal_relevance": cls._clamp(max(seeking, care, panic, fear, rage)),
            "goal_congruence": goal_congruence,
            "coping_potential": cls._clamp(0.65 - 0.35 * panic - 0.25 * fear + 0.15 * play),
            "agency": agency,
            "norm_compatibility": norm,
        }

    @classmethod
    def _build_cognitive_impact(
        cls,
        text: str,
        sec_result: Dict[str, float],
        triggers: Dict[str, float],
    ) -> Dict[str, float]:
        novelty = cls._clamp(sec_result.get("novelty", 0.0))
        goal_relevance = cls._clamp(sec_result.get("goal_relevance", 0.0))
        pleasantness = abs(sec_result.get("pleasantness", 0.0))
        coping = cls._clamp(sec_result.get("coping_potential", 0.5))
        urgency = cls._clamp(max(triggers.values(), default=0.0))
        text_density = cls._clamp(len(text.strip()) / 80.0)

        return {
            "sensory": cls._clamp(0.20 + text_density * 0.35 + novelty * 0.45),
            "cognitive": cls._clamp(0.15 + goal_relevance * 0.45 + novelty * 0.20 + (1.0 - coping) * 0.20),
            "self_": cls._clamp(0.10 + goal_relevance * 0.45 + pleasantness * 0.15 + urgency * 0.30),
            "novelty": cls._clamp(max(novelty, urgency * 0.8)),
        }

    @staticmethod
    def _normalize_message(msg) -> ChannelMessage:
        if isinstance(msg, dict):
            metadata = dict(msg)
            return ChannelMessage(
                channel_id=QQChannel.CHANNEL_ID,
                user_id=msg.get("user_id", ""),
                text=msg.get("text", ""),
                timestamp=msg.get("timestamp", 0.0),
                metadata=metadata,
                direction="inbound",
            )

        return ChannelMessage(
            channel_id=QQChannel.CHANNEL_ID,
            user_id=getattr(msg, "user_id", ""),
            text=getattr(msg, "text", ""),
            timestamp=getattr(msg, "timestamp", 0.0),
            metadata={
                "message_id": getattr(msg, "message_id", ""),
                "is_group": getattr(msg, "is_group", False),
                "group_id": getattr(msg, "group_id", ""),
                "raw": getattr(msg, "raw", {}),
            },
            direction="inbound",
        )
