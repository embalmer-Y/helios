"""Abstract channel interfaces for external I/O integrations.

QQ is only one concrete channel. The abstractions in this module allow Helios
to receive and send messages through any transport while keeping the main tick
pipeline transport-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal


class ChannelStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass
class ChannelMessage:
    channel_id: str
    user_id: str
    text: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    direction: Literal["inbound", "outbound"] = "inbound"


class InputChannel(ABC):
    @property
    @abstractmethod
    def channel_id(self) -> str:
        ...

    @abstractmethod
    def poll(self) -> List[ChannelMessage]:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def connect(self) -> None:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...


class OutputChannel(ABC):
    @property
    @abstractmethod
    def channel_id(self) -> str:
        ...

    @abstractmethod
    def send(self, message: ChannelMessage) -> bool:
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        ...

    @abstractmethod
    def connect(self) -> None:
        ...

    @abstractmethod
    def disconnect(self) -> None:
        ...


class BidirectionalChannel(InputChannel, OutputChannel, ABC):
    """A channel that can both receive and send messages."""
