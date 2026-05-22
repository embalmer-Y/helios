"""ChannelGateway — manages lifecycle and routing for all Channel instances.

Provides centralized registration, polling, trigger merging, and reply routing
for external communication channels. Internal event sources (SeparationAnxiety,
InternalDrive) remain outside the Gateway as direct EventSources.

Requirements: 36.3, 36.4, 36.5
"""

import logging
from typing import Dict, List, Optional, Tuple

from core.channel import Channel
from core.helios_state import HeliosState

logger = logging.getLogger("helios.gateway")


class ChannelGateway:
    """Manages the lifecycle of all Channel instances.

    Responsibilities:
      - Register/deregister channels (calling connect/disconnect)
      - Poll all channels and merge triggers (max-value semantics)
      - Tag inbound messages with _channel_id for reply routing
      - Route outbound replies to the correct originating channel
    """

    def __init__(self):
        self._channels: Dict[str, Channel] = {}

    def register(self, channel: Channel):
        """Register a channel: add to registry and call connect().

        Args:
            channel: A Channel instance to register.
        """
        cid = channel.channel_id
        if cid in self._channels:
            logger.warning(f"Channel '{cid}' already registered, replacing")
            self._channels[cid].disconnect()

        self._channels[cid] = channel
        ok = channel.connect()
        if ok:
            logger.info(f"Channel '{cid}' registered and connected")
        else:
            logger.warning(f"Channel '{cid}' registered but connect() returned False")

    def deregister(self, channel_id: str):
        """Deregister a channel: call disconnect() and remove from registry.

        Args:
            channel_id: The channel_id of the channel to remove.
        """
        channel = self._channels.pop(channel_id, None)
        if channel:
            channel.disconnect()
            logger.info(f"Channel '{channel_id}' deregistered")
        else:
            logger.warning(f"Channel '{channel_id}' not found in registry")

    def poll_all(self, state: HeliosState) -> Tuple[Dict[str, float], List[dict]]:
        """Poll all registered channels, merge triggers, collect messages.

        Triggers are merged using max-value semantics for overlapping keys.
        Each inbound message is tagged with _channel_id metadata identifying
        its source for reply routing.

        Args:
            state: The current tick's HeliosState.

        Returns:
            Tuple of (merged_triggers, tagged_messages).
        """
        merged_triggers: Dict[str, float] = {}
        all_messages: List[dict] = []

        for cid, channel in self._channels.items():
            try:
                triggers = channel.poll(state)
                for system, intensity in triggers.items():
                    merged_triggers[system] = max(
                        merged_triggers.get(system, 0.0), intensity
                    )
                messages = channel.get_messages()
                for msg in messages:
                    msg["_channel_id"] = cid
                all_messages.extend(messages)
            except Exception as e:
                logger.warning(f"Channel '{cid}' poll failed: {e}")

        return merged_triggers, all_messages

    def route_reply(self, message: dict, reply: str) -> bool:
        """Route an outbound reply to the correct channel based on message metadata.

        Uses the _channel_id tag in the original message to find the originating
        channel and dispatch the reply through it.

        Args:
            message: The original inbound message dict (must contain _channel_id).
            reply: The reply text to send.

        Returns:
            True if the reply was sent successfully, False otherwise.
        """
        cid = message.get("_channel_id", "")
        if not cid:
            logger.warning("Cannot route reply: message has no _channel_id")
            return False

        channel = self._channels.get(cid)
        if not channel:
            logger.warning(f"Cannot route reply: channel '{cid}' not registered")
            return False

        if not channel.is_connected:
            logger.warning(f"Cannot route reply: channel '{cid}' is disconnected")
            return False

        reply_msg = {
            "text": reply,
            "user_id": message.get("user_id", ""),
        }
        return channel.send(reply_msg)

    def get_channel(self, channel_id: str) -> Optional[Channel]:
        """Look up a channel by its ID.

        Args:
            channel_id: The channel_id to look up.

        Returns:
            The Channel instance, or None if not found.
        """
        return self._channels.get(channel_id)

    def get_status(self) -> Dict[str, bool]:
        """Return connection status for all registered channels.

        Returns:
            Dictionary mapping channel_id to is_connected boolean.
        """
        return {cid: ch.is_connected for cid, ch in self._channels.items()}
