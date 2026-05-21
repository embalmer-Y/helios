"""QQEventSource — consumes QQ message queue and returns Panksepp triggers + messages.

Implements the EventSource interface to drain the QQ message queue each tick,
evaluate each message through an SEC evaluator (LLM-based or keyword fallback),
and return merged Panksepp trigger vectors along with pending messages that
may need a reply from the ResponsePipeline.
"""

from __future__ import annotations

import logging
import queue
from typing import Dict, List, Protocol

from core.event_source import EventSource
from core.helios_state import HeliosState

log = logging.getLogger("helios.qq_event_source")


class SECEvaluator(Protocol):
    """Protocol for SEC evaluator — allows LLM-based or keyword-based implementations."""

    def evaluate(self, text: str) -> Dict[str, float]:
        """Evaluate text and return Panksepp trigger dictionary.

        Returns:
            Dictionary mapping Panksepp system names to trigger intensities.
        """
        ...


class QQEventSource(EventSource):
    """Consumes QQ message queue, returns Panksepp triggers and pending messages.

    Each call to poll() drains all messages currently in the queue, evaluates
    each through the SEC evaluator, and returns the merged trigger dictionary
    using max-value semantics for overlapping keys. Messages are buffered and
    returned by get_messages() for the ResponsePipeline to process.

    Args:
        msg_queue: Thread-safe queue of QQ message dicts/objects with at least
                   a "text" attribute or key.
        sec_evaluator: An object implementing evaluate(text) -> Dict[str, float]
                       that converts message text to Panksepp triggers.
    """

    def __init__(self, msg_queue: queue.Queue, sec_evaluator: SECEvaluator):
        self._queue = msg_queue
        self._sec_evaluator = sec_evaluator
        self._pending_messages: List[dict] = []

    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Drain the message queue, evaluate via SEC, return merged triggers.

        Drains all messages from the queue, evaluates each through the SEC
        evaluator, and merges trigger dictionaries using max-value semantics.
        Messages are buffered internally for retrieval via get_messages().

        Args:
            state: The current tick's HeliosState (available for context but
                   not currently used by this source).

        Returns:
            Merged Panksepp trigger dictionary with max-value semantics for
            overlapping system keys. Empty dict if no messages were queued.
        """
        # Clear pending messages from previous tick
        self._pending_messages = []
        merged_triggers: Dict[str, float] = {}

        # Drain the queue
        while True:
            try:
                msg = self._queue.get_nowait()
            except queue.Empty:
                break

            # Normalize message to dict format
            msg_dict = self._normalize_message(msg)
            self._pending_messages.append(msg_dict)

            # Evaluate message text via SEC evaluator
            text = msg_dict.get("text", "")
            if text:
                try:
                    triggers = self._sec_evaluator.evaluate(text)
                except Exception as e:
                    log.warning("SEC evaluation failed for message: %s", e)
                    triggers = {}

                # Merge using max-value semantics
                for system, intensity in triggers.items():
                    merged_triggers[system] = max(
                        merged_triggers.get(system, 0.0), intensity
                    )

        if self._pending_messages:
            log.debug(
                "QQEventSource polled %d message(s), triggers: %s",
                len(self._pending_messages),
                merged_triggers,
            )

        return merged_triggers

    def get_messages(self) -> List[dict]:
        """Return pending messages needing reply from the last poll.

        Returns:
            List of message dicts accumulated during the most recent poll()
            call. Each dict contains at minimum a "text" key. Additional keys
            like "user_id", "message_id", "timestamp", "is_group" depend on
            the source message format.
        """
        return self._pending_messages

    @staticmethod
    def _normalize_message(msg) -> dict:
        """Normalize a QQMessage object or dict into a standard dict format.

        Handles both QQMessage dataclass instances (from io_qq.py) and plain
        dicts for flexibility.

        Returns:
            Dict with keys: text, user_id, message_id, timestamp, is_group,
            group_id, raw.
        """
        if isinstance(msg, dict):
            return msg

        # Assume QQMessage dataclass or similar object with attributes
        return {
            "text": getattr(msg, "text", ""),
            "user_id": getattr(msg, "user_id", ""),
            "message_id": getattr(msg, "message_id", ""),
            "timestamp": getattr(msg, "timestamp", 0.0),
            "is_group": getattr(msg, "is_group", False),
            "group_id": getattr(msg, "group_id", ""),
            "raw": getattr(msg, "raw", {}),
        }
