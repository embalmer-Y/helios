"""Routing preference policy for planner-owned channel ordering."""

from __future__ import annotations

from typing import Mapping

from .channel import ChannelDescriptor, ChannelStatus


class RoutingPreferencePolicy:
    """Own channel preference ordering without letting the executor guess transport."""

    def rank_reply_channels(
        self,
        *,
        message: Mapping[str, object],
        channel_descriptors: Mapping[str, ChannelDescriptor],
        channel_statuses: Mapping[str, ChannelStatus] | None = None,
        qq_target_id: str = "",
        personality_projection: object | None = None,
    ) -> list[str]:
        source_channel = str(message.get("channel_id") or "")
        ranked = self._rank_channels(
            channel_descriptors=channel_descriptors,
            channel_statuses=channel_statuses,
            personality_projection=personality_projection,
        )

        preferred: list[str] = []
        if source_channel:
            preferred.append(source_channel)
        if qq_target_id:
            preferred.append("qq")
        return self._merge_unique(preferred, ranked)

    def rank_active_channels(
        self,
        *,
        action: str,
        channel_descriptors: Mapping[str, ChannelDescriptor],
        channel_statuses: Mapping[str, ChannelStatus] | None = None,
        qq_target_id: str = "",
        personality_projection: object | None = None,
    ) -> list[str]:
        if action in {"browse", "search", "learn", "reflect", "check_system", "idle"}:
            return []

        ranked = self._rank_channels(
            channel_descriptors=channel_descriptors,
            channel_statuses=channel_statuses,
            personality_projection=personality_projection,
        )
        if not qq_target_id:
            ranked = [channel_id for channel_id in ranked if channel_id != "qq"]
        return ranked

    def _rank_channels(
        self,
        *,
        channel_descriptors: Mapping[str, ChannelDescriptor],
        channel_statuses: Mapping[str, ChannelStatus] | None,
        personality_projection: object | None,
    ) -> list[str]:
        output_channels = [
            channel_id
            for channel_id, descriptor in channel_descriptors.items()
            if self._supports_output(descriptor)
        ]
        if not output_channels:
            return []

        ranked = list(output_channels)
        if personality_projection is not None and hasattr(personality_projection, "rank_channels"):
            ranked = list(personality_projection.rank_channels(output_channels))
        else:
            ranked.sort()

        if not channel_statuses:
            return ranked

        connected = [
            channel_id for channel_id in ranked
            if channel_statuses.get(channel_id, ChannelStatus.ERROR) == ChannelStatus.CONNECTED
        ]
        degraded = [channel_id for channel_id in ranked if channel_id not in connected]
        return connected + degraded

    @staticmethod
    def _supports_output(descriptor: ChannelDescriptor) -> bool:
        if any(getattr(op, "direction", "") == "output" for op in descriptor.supported_ops):
            return True
        return "send" in descriptor.capabilities

    @staticmethod
    def _merge_unique(*groups: list[str]) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for group in groups:
            for channel_id in group:
                if not channel_id or channel_id in seen:
                    continue
                ordered.append(channel_id)
                seen.add(channel_id)
        return ordered


__all__ = ["RoutingPreferencePolicy"]