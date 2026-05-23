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


def _str_list() -> List[str]:
    return []


def _op_list() -> List["ChannelOpDescriptor"]:
    return []


def _any_dict() -> Dict[str, Any]:
    return {}


class ChannelStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    RECONNECTING = "reconnecting"


@dataclass(frozen=True)
class ChannelOpDescriptor:
    name: str
    direction: Literal["input", "output", "management", "bidirectional"]
    description: str
    input_schema: Dict[str, Any] = field(default_factory=_any_dict)
    output_schema: Dict[str, Any] = field(default_factory=_any_dict)
    async_supported: bool = False


@dataclass(frozen=True)
class ChannelDescriptor:
    channel_id: str
    display_name: str
    input_types: List[str] = field(default_factory=_str_list)
    output_types: List[str] = field(default_factory=_str_list)
    input_formats: List[str] = field(default_factory=_str_list)
    output_formats: List[str] = field(default_factory=_str_list)
    capabilities: List[str] = field(default_factory=_str_list)
    supported_ops: List[ChannelOpDescriptor] = field(default_factory=_op_list)
    management_ops: List[ChannelOpDescriptor] = field(default_factory=_op_list)
    startup_requirements: List[str] = field(default_factory=_str_list)
    shutdown_requirements: List[str] = field(default_factory=_str_list)
    health_signals: List[str] = field(default_factory=_str_list)
    ack_schema: Dict[str, Any] = field(default_factory=_any_dict)
    limitations: List[str] = field(default_factory=_str_list)


@dataclass
class ChannelMessage:
    channel_id: str
    user_id: str
    text: str
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=_any_dict)
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

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self.channel_id,
            display_name=self.channel_id.upper(),
            input_types=["message"],
            output_types=[],
            input_formats=["text/plain"],
            output_formats=[],
            capabilities=["poll", "connect", "disconnect"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description="Poll inbound messages from the channel.",
                    output_schema={"messages": "list[ChannelMessage]"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("connect", "management", "Connect the channel."),
                ChannelOpDescriptor("disconnect", "management", "Disconnect the channel."),
            ],
            health_signals=["is_connected"],
            limitations=["Descriptor is generic because the channel does not override get_descriptor()."],
        )

    def list_supported_ops(self) -> List[ChannelOpDescriptor]:
        descriptor = self.get_descriptor()
        return [*descriptor.supported_ops, *descriptor.management_ops]


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

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self.channel_id,
            display_name=self.channel_id.upper(),
            input_types=[],
            output_types=["message"],
            input_formats=[],
            output_formats=["text/plain"],
            capabilities=["send", "connect", "disconnect"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="send",
                    direction="output",
                    description="Send an outbound message through the channel.",
                    input_schema={"message": "ChannelMessage"},
                    output_schema={"success": "bool"},
                )
            ],
            management_ops=[
                ChannelOpDescriptor("connect", "management", "Connect the channel."),
                ChannelOpDescriptor("disconnect", "management", "Disconnect the channel."),
            ],
            health_signals=["is_connected"],
            ack_schema={"success": "bool"},
            limitations=["Descriptor is generic because the channel does not override get_descriptor()."],
        )

    def list_supported_ops(self) -> List[ChannelOpDescriptor]:
        descriptor = self.get_descriptor()
        return [*descriptor.supported_ops, *descriptor.management_ops]


class BidirectionalChannel(InputChannel, OutputChannel, ABC):
    """A channel that can both receive and send messages."""
