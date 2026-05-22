"""utils/ws_reconnector.py — WebSocket Reconnection with Exponential Backoff

Provides automatic reconnection logic for the QQBotClient WebSocket connection
with exponential backoff capped at 30 seconds.

Requirements: 33.3, 33.4
"""

import time
import logging

logger = logging.getLogger("helios.ws_reconnector")


class WebSocketReconnector:
    """Manages WebSocket reconnection with exponential backoff.

    Tracks consecutive disconnection attempts and computes backoff delay.
    Capped at 30 seconds maximum backoff.
    """

    MAX_BACKOFF: float = 30.0
    BASE_BACKOFF: float = 1.0

    def __init__(self):
        self._attempt_count: int = 0
        self._last_disconnect_time: float = 0.0
        self._last_reconnect_time: float = 0.0

    @property
    def attempt_count(self) -> int:
        """Number of consecutive reconnection attempts."""
        return self._attempt_count

    def on_disconnect(self):
        """Called when the WebSocket connection drops.

        Increments the attempt counter for backoff calculation.
        """
        self._attempt_count += 1
        self._last_disconnect_time = time.time()
        logger.info(
            f"WebSocket disconnected (attempt #{self._attempt_count}), "
            f"backoff={self.get_backoff():.1f}s"
        )

    def get_backoff(self) -> float:
        """Compute exponential backoff delay based on attempt count.

        Returns:
            Backoff duration in seconds, capped at MAX_BACKOFF (30s).
        """
        delay = self.BASE_BACKOFF * (2 ** min(self._attempt_count - 1, 10))
        return min(delay, self.MAX_BACKOFF)

    def on_reconnect(self):
        """Called when reconnection succeeds.

        Resets the attempt counter and logs success.
        """
        logger.info(
            f"WebSocket reconnected after {self._attempt_count} attempt(s)"
        )
        self._attempt_count = 0
        self._last_reconnect_time = time.time()

    def should_attempt(self) -> bool:
        """Check if enough time has elapsed for the next reconnection attempt.

        Returns:
            True if the backoff period has elapsed since last disconnect.
        """
        if self._attempt_count == 0:
            return True
        elapsed = time.time() - self._last_disconnect_time
        return elapsed >= self.get_backoff()
