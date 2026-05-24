"""Abstract channel interfaces for external I/O integrations.

QQ is only one concrete channel. The abstractions in this module allow Helios
to receive and send messages through any transport while keeping the main tick
pipeline transport-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal


def _str_list() -> List[str]:
    return []


def _op_list() -> List["ChannelOpDescriptor"]:
    return []


def _any_dict() -> Dict[str, Any]:
    return {}


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


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


@dataclass(frozen=True)
class StimulusEnvelope:
    source_channel_id: str
    source_kind: str
    trigger_condition: str
    stimulus_intensity: float
    payload: Dict[str, Any] = field(default_factory=_any_dict)
    text_summary: str = ""
    cognitive_impact: Dict[str, Any] = field(default_factory=_any_dict)
    novelty_factor: float = 1.0
    sensitization_factor: float = 0.5
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=_any_dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_stimulus_envelope(message: ChannelMessage) -> StimulusEnvelope:
    metadata = dict(message.metadata)
    cognitive_impact = dict(metadata.get("cognitive_impact", {}) or {})
    sec_result = dict(metadata.get("sec_result", {}) or {})
    triggers = dict(metadata.get("event_triggers", {}) or {})
    payload = {
        "text": message.text,
        "user_id": message.user_id,
        "direction": message.direction,
    }
    source_kind = str(metadata.get("source_kind", "external_message") or "external_message")
    trigger_condition = str(metadata.get("trigger_condition", "channel_input") or "channel_input")
    intensity_candidates = [
        metadata.get("stimulus_intensity", 0.0),
        cognitive_impact.get("novelty", 0.0),
        cognitive_impact.get("cognitive", 0.0),
        cognitive_impact.get("self_", 0.0),
        sec_result.get("goal_relevance", 0.0),
        max(triggers.values(), default=0.0),
    ]
    text_weight = _clamp(len((message.text or "").strip()) / 80.0)
    base_intensity = _clamp(max([float(candidate or 0.0) for candidate in intensity_candidates] + [text_weight * 0.35]))
    return StimulusEnvelope(
        source_channel_id=message.channel_id,
        source_kind=source_kind,
        trigger_condition=trigger_condition,
        stimulus_intensity=base_intensity,
        payload=payload,
        text_summary=(message.text or "")[:120],
        cognitive_impact=cognitive_impact,
        timestamp=message.timestamp,
        metadata={
            "message_id": metadata.get("message_id", ""),
            "event_triggers": triggers,
            "sec_result": sec_result,
        },
    )


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

    def execute_op(self, op_name: str, message: ChannelMessage) -> bool:
        if op_name == "send":
            return self.send(message)
        return False


class BidirectionalChannel(InputChannel, OutputChannel, ABC):
    """A channel that can both receive and send messages."""
