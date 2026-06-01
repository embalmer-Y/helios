"""QQChannel adapts QQBotClient into the channel abstraction layer."""

from __future__ import annotations

import logging
import queue
import time
from typing import Any, Dict, List, Optional

from ..channel import BidirectionalChannel, ChannelConfigFieldDescriptor, ChannelConfigSnapshot, ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelOpDescriptor, ChannelStatus
from ..expression_modulation import modulate_outbound_expression
from .inbound_text_annotation import annotate_inbound_text_message, evaluate_text_triggers

try:
    from ..protocols.qq import RECONNECT_DELAYS as _QQ_RECONNECT_DELAYS
except Exception:  # pragma: no cover - runtime fallback for isolated loading
    _QQ_RECONNECT_DELAYS = [1, 2, 5, 10, 30, 60]

log = logging.getLogger("helios.helios_io.channels.qq_channel")


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
        self._status = ChannelStatus.UNINITIALIZED
        self._last_connected = False
        self._manual_disconnect = False
        self._paused = False
        self._suspended = False

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
                    input_schema={"message": "ChannelMessage(text, user_id, metadata[message_id|group_id|is_group|normalized_intensity|outbound_intensity])"},
                    output_schema={"success": "bool"},
                ),
            ],
            management_ops=[
                ChannelOpDescriptor("init", "management", "Initialize the QQ channel runtime state."),
                ChannelOpDescriptor("deinit", "management", "Deinitialize the QQ channel runtime state."),
                ChannelOpDescriptor("connect", "management", "Connect the QQ websocket client."),
                ChannelOpDescriptor("disconnect", "management", "Disconnect the QQ websocket client."),
                ChannelOpDescriptor("pause", "management", "Pause QQ inbound/outbound handling while preserving registration."),
                ChannelOpDescriptor("resume", "management", "Resume QQ activity after pause."),
                ChannelOpDescriptor("suspend", "management", "Suspend QQ channel activity."),
                ChannelOpDescriptor("unsuspend", "management", "Unsuspend QQ channel activity."),
                ChannelOpDescriptor("get_config", "management", "Return the QQ channel config snapshot."),
                ChannelOpDescriptor("update_config", "management", "Update mutable QQ channel config fields.", input_schema={"config": "dict"}, output_schema={"snapshot": "ChannelConfigSnapshot"}),
                ChannelOpDescriptor("health_check", "management", "Return the QQ channel health snapshot."),
            ],
            startup_requirements=["qq_client available"],
            shutdown_requirements=["qq client stop when present"],
            health_signals=["is_connected", "get_status", "reconnect_attempts"],
            ack_schema={"success": "bool", "delivery": "best_effort"},
            config_fields=[
                ChannelConfigFieldDescriptor("poll_when_disconnected", "Whether inbound queue polling is allowed while the websocket is disconnected.", required=True, mutable_at_runtime=True, default_value=True, schema_hint="bool"),
                ChannelConfigFieldDescriptor("sec_evaluator_enabled", "Whether inbound SEC annotation is active for QQ inbound text.", required=True, mutable_at_runtime=True, default_value=True, schema_hint="bool"),
            ],
            limitations=["Current output support is text-only."],
        )

    def get_status(self) -> ChannelStatus:
        self._refresh_connection_state()
        return self._status

    def poll(self) -> List[ChannelMessage]:
        if self._paused or self._suspended:
            return []
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
        if not self.is_connected() or self._paused or self._suspended:
            return False

        metadata = dict(message.metadata)
        modulation = modulate_outbound_expression(message.text, metadata)
        rendered_text = modulation.rendered_text
        message.metadata["original_text"] = message.text
        message.metadata["rendered_text"] = rendered_text
        message.metadata["expression_profile"] = modulation.to_metadata()
        msg_id = metadata.get("message_id", "")
        is_group = metadata.get("is_group", False)
        group_id = metadata.get("group_id", "")

        try:
            if is_group and group_id:
                if msg_id:
                    return bool(client.send_group(group_id, rendered_text, msg_id=msg_id))
                return bool(client.send_group(group_id, rendered_text))
            if msg_id:
                return bool(client.send_c2c(message.user_id, rendered_text, msg_id=msg_id))
            return bool(client.send_c2c(message.user_id, rendered_text))
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
        if self._status == ChannelStatus.UNINITIALIZED:
            self._status = ChannelStatus.INITIALIZED
        if not self.is_connected() and hasattr(client, "start"):
            self._manual_disconnect = False
            self._paused = False
            self._suspended = False
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
        self._paused = False
        self._suspended = False

    def get_config_snapshot(self) -> ChannelConfigSnapshot:
        return ChannelConfigSnapshot(
            channel_id=self.channel_id,
            status=self.get_status().value,
            config_values={
                "poll_when_disconnected": bool(getattr(self, "poll_when_disconnected", True)),
                "sec_evaluator_enabled": self._sec_evaluator is not None,
            },
            mutable_fields=["poll_when_disconnected", "sec_evaluator_enabled"],
            validation_errors=[],
        )

    def update_config(self, updates: Optional[Dict[str, Any]] = None) -> ChannelConfigSnapshot:
        updates = dict(updates or {})
        errors: List[str] = []
        if "poll_when_disconnected" in updates:
            self.poll_when_disconnected = bool(updates["poll_when_disconnected"])
        if "sec_evaluator_enabled" in updates:
            desired = bool(updates["sec_evaluator_enabled"])
            if desired and self._sec_evaluator is None:
                errors.append("sec_evaluator cannot be enabled when no evaluator is configured")
            if not desired:
                self._sec_evaluator = None
        snapshot = self.get_config_snapshot()
        if errors:
            return ChannelConfigSnapshot(snapshot.channel_id, snapshot.status, snapshot.config_values, snapshot.mutable_fields, errors)
        return snapshot

    def health_check(self) -> Dict[str, Any]:
        return {
            "channel_id": self.channel_id,
            "status": self.get_status().value,
            "connected": self.is_connected(),
            "paused": self._paused,
            "suspended": self._suspended,
            "reconnect_attempts": self._reconnector.attempt_count,
        }

    def execute_management_op(self, op_name: str, payload: Optional[Dict[str, Any]] = None) -> ChannelManagementResult:
        payload = dict(payload or {})
        if op_name == "init":
            if self._status == ChannelStatus.UNINITIALIZED:
                self._status = ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel initialized.")
        if op_name == "deinit":
            self.disconnect()
            self._status = ChannelStatus.DEINITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel deinitialized.")
        if op_name == "pause":
            self._paused = True
            self._status = ChannelStatus.PAUSED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel paused.")
        if op_name == "resume":
            self._paused = False
            self._status = ChannelStatus.CONNECTED if self._last_connected else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel resumed.")
        if op_name == "suspend":
            self._suspended = True
            self._status = ChannelStatus.SUSPENDED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel suspended.")
        if op_name == "unsuspend":
            self._suspended = False
            self._status = ChannelStatus.CONNECTED if self._last_connected else ChannelStatus.INITIALIZED
            return ChannelManagementResult(self.channel_id, op_name, True, self._status.value, "QQ channel unsuspended.")
        if op_name == "get_config":
            snapshot = self.get_config_snapshot()
            return ChannelManagementResult(self.channel_id, op_name, True, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)})
        if op_name == "update_config":
            snapshot = self.update_config(dict(payload.get("config", {}) or {}))
            return ChannelManagementResult(self.channel_id, op_name, not snapshot.validation_errors, snapshot.status, payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)}, error_code="config_validation_failed" if snapshot.validation_errors else "")
        if op_name == "health_check":
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload=self.health_check())
        return super().execute_management_op(op_name, payload)

    @staticmethod
    def _client_reconnect_attempts(client) -> int:
        attempts = getattr(client, "_reconnect_attempts", 0)
        try:
            return max(0, int(attempts))
        except Exception:
            return 0

    def evaluate_message(self, message: ChannelMessage, state=None) -> Dict[str, float]:
        return evaluate_text_triggers(message, self._sec_evaluator, log, "QQChannel")

    def _annotate_inbound_message(self, message: ChannelMessage) -> ChannelMessage:
        return annotate_inbound_text_message(message, self._sec_evaluator, log, "QQChannel")

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
