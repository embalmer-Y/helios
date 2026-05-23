"""Core package — foundational types and infrastructure for Helios."""

from helios_io.channel import (
    BidirectionalChannel,
    ChannelMessage,
    ChannelStatus,
    InputChannel,
    OutputChannel,
)
from helios_io.channel_gateway import ChannelGateway
from core.helios_state import HeliosState
from core.tick_guard import TickGuard
from core.event_source import EventSource
from core.separation_source import SeparationAnxietySource
from core.drive_source import InternalDriveSource

__all__ = [
    "ChannelGateway",
    "ChannelMessage",
    "ChannelStatus",
    "InputChannel",
    "OutputChannel",
    "BidirectionalChannel",
    "HeliosState",
    "TickGuard",
    "EventSource",
    "SeparationAnxietySource",
    "InternalDriveSource",
]
