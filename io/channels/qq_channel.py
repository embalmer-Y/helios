"""QQChannel — Channel implementation wrapping QQEventSource logic.

Migrates the existing QQEventSource (core/qq_event_source.py) into the Channel
interface, adding bidirectional send capability and connection lifecycle.

The poll/get_messages logic is preserved unchanged from QQEventSource.

Requirements: 36.6
"""

from __future__ import annotations

import logging
import queue
from typing import Dict, List, Set

from core.channel import Channel
from core.helios_state import HeliosState

log = logging.getLogger("helios.channel.qq")


class QQChannel(Channel):
    """QQ communication channel implementing the Channel interface.

    Wraps the existing QQ message queue consumption and SEC evaluation logic
    from QQEventSource, adding outbound send() and connection lifecycle.

    Args:
        msg_queue: Thread-safe queue of QQ message dicts/objects.
        sec_evaluator: An object implementing evaluate(text) -> Dict[str, float].
        qq_client: Optional QQBotClient for send() operations.
    """

    def __init__(self, msg_queue: queue.Queue, sec_evaluator, qq_client=None):
        self._queue = msg_queue
        self._sec_evaluator = sec_evaluator
        self._qq_client = qq_client
        self._pending_messages: List[dict] = []
        self._connected: bool = False

    # ── Channel interface ──

    def connect(self) -> bool:
        self._connected = True
        log.info("QQChannel connected")
        return True

    def disconnect(self):
        self._connected = False
        log.info("QQChannel disconnected")

    @property
    def is_connected(self) -> bool:
        if self._qq_client:
            return self._connected and self._qq_client.is_connected()
        return self._connected

    def send(self, message: dict) -> bool:
        if not self._qq_client:
            log.warning("QQChannel: no qq_client configured, cannot send")
            return False
        user_id = message.get("user_id", "")
        text = message.get("text", "")
        if not user_id or not text:
            return False
        return self._qq_client.send_c2c(user_id, text)

    @property
    def channel_id(self) -> str:
        return "qq"

    @property
    def capabilities(self) -> Set[str]:
        return {"text", "image"}

    # ── EventSource interface (preserved from QQEventSource) ──

    def poll(self, state: HeliosState) -> Dict[str, float]:
        self._pending_messages = []
        merged_triggers: Dict[str, float] = {}

        while True:
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                break

            msg_dict = self._normalize_message(msg)
            self._pending_messages.append(msg_dict)

            text = msg_dict.get("text", "")
            if text:
                try:
                    triggers = self._sec_evaluator.evaluate(text)
                except Exception as e:
                    log.warning("SEC evaluation failed for message: %s", e)
                    triggers = {}

                for system, intensity in triggers.items():
                    merged_triggers[system] = max(
                        merged_triggers.get(system, 0.0), intensity
                    )

        if self._pending_messages:
            log.debug(
                "QQChannel polled %d message(s), triggers: %s",
                len(self._pending_messages),
                merged_triggers,
            )

        return merged_triggers

    def get_messages(self) -> List[dict]:
        return self._pending_messages

    @staticmethod
    def _normalize_message(msg) -> dict:
        if isinstance(msg, dict):
            return msg
        return {
            "text": getattr(msg, "text", ""),
            "user_id": getattr(msg, "user_id", ""),
            "message_id": getattr(msg, "message_id", ""),
            "timestamp": getattr(msg, "timestamp", 0.0),
            "is_group": getattr(msg, "is_group", False),
            "group_id": getattr(msg, "group_id", ""),
            "raw": getattr(msg, "raw", {}),
        }
