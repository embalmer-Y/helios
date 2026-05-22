"""Abstract base class for bidirectional communication channels.

Channel extends EventSource with bidirectional capabilities: connect, disconnect,
send, health check, and identity. Any Channel can be used wherever an EventSource
is expected (backward compatible).

Requirements: 36.1, 36.2
"""

from abc import abstractmethod
from typing import Set

from core.event_source import EventSource


class Channel(EventSource):
    """Bidirectional communication channel extending EventSource.

    Adds outbound send capability, connection lifecycle, and identity
    on top of the inbound poll/get_messages interface from EventSource.
    """

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to the external service.

        Returns:
            True if connection succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def disconnect(self):
        """Gracefully shut down the connection."""
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Health check: whether this channel is currently connected."""
        ...

    @abstractmethod
    def send(self, message: dict) -> bool:
        """Send an outbound message through this channel.

        Args:
            message: Message dict containing at minimum "text" and "user_id".

        Returns:
            True if the message was sent successfully.
        """
        ...

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """Unique identifier for routing (e.g. "qq", "discord", "voice")."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> Set[str]:
        """Set of capability strings (e.g. {"text", "image", "voice"})."""
        ...
