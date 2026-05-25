"""Abstract base class for pluggable event input providers.

EventSource defines the interface for all event sources that feed Panksepp
triggers and messages into the Helios tick pipeline. New input sources (STT,
browser, sensors, etc.) can be added by implementing this interface without
modifying the main loop.
"""

from abc import ABC, abstractmethod
from typing import Dict, List

from core.helios_state import HeliosState


class EventSource(ABC):
    """Pluggable event input provider.

    Each EventSource is polled once per tick. It returns:
    - A Panksepp trigger dictionary (system name → intensity float)
    - A list of pending messages that may need a reply
    """

    @abstractmethod
    def poll(self, state: HeliosState) -> Dict[str, float]:
        """Return Panksepp trigger vector from this source.

        Args:
            state: The current tick's HeliosState for context-aware polling.

        Returns:
            Dictionary mapping Panksepp system names (e.g. "SEEKING", "PANIC")
            to trigger intensity values in [0.0, 1.0]. Empty dict if no
            triggers this tick.
        """
        ...

    @abstractmethod
    def get_messages(self) -> List[dict]:
        """Return pending messages needing reply (may be empty).

        Returns:
            List of message dicts. Each dict should contain at minimum
            a "text" key with the message content. Additional keys like
            "user_id", "timestamp", etc. are source-dependent.
            Returns empty list if this source does not produce messages.
        """
        ...

    def get_stimuli(self) -> List[dict]:
        """Return normalized stimuli emitted by this source.

        Sources that do not own a formal stimulus contract can keep returning
        an empty list. The main loop uses this to consume structured stimulus
        inputs without forcing every message payload to embed a stimulus blob.
        """
        return []
