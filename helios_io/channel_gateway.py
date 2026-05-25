"""ChannelGateway bridges channel abstractions into the EventSource pipeline."""

from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from .channel import ChannelDescriptor, ChannelMessage, ChannelStatus, InputChannel, OutputChannel, build_stimulus_envelope
from core.event_source import EventSource
from core.helios_state import HeliosState
from core.trigger_merge import merge_triggers

log = logging.getLogger("helios.helios_io.channel_gateway")


class ChannelGateway(EventSource):
    """Registry and adapter for pluggable inbound and outbound channels."""

    def __init__(self, evaluators: Optional[Dict[str, object]] = None):
        self._input_channels: Dict[str, InputChannel] = {}
        self._output_channels: Dict[str, OutputChannel] = {}
        self._evaluators: Dict[str, object] = dict(evaluators or {})
        self._pending_messages: List[dict] = []
        self._pending_stimuli: List[dict] = []

    def register_channel(self, channel: InputChannel | OutputChannel) -> None:
        channel_id = channel.channel_id
        if isinstance(channel, InputChannel):
            self._input_channels[channel_id] = channel
        if isinstance(channel, OutputChannel):
            self._output_channels[channel_id] = channel

    def deregister_channel(self, channel_id: str) -> None:
        self._input_channels.pop(channel_id, None)
        self._output_channels.pop(channel_id, None)
        self._evaluators.pop(channel_id, None)

    def register_evaluator(self, channel_id: str, evaluator: object) -> None:
        self._evaluators[channel_id] = evaluator

    def poll_all(self, state: HeliosState) -> List[ChannelMessage]:
        messages: List[ChannelMessage] = []
        for channel_id, channel in self._input_channels.items():
            if not channel.is_connected() and not getattr(channel, "poll_when_disconnected", False):
                continue
            try:
                messages.extend(channel.poll())
            except Exception as exc:
                log.warning("Input channel %s poll failed: %s", channel_id, exc)
        return messages

    def route_outbound(self, message: ChannelMessage) -> bool:
        channel = self._output_channels.get(message.channel_id)
        if channel is None:
            log.warning("No output channel registered for %s", message.channel_id)
            return False
        if not channel.is_connected():
            log.warning("Output channel %s is disconnected", message.channel_id)
            return False
        descriptor = self.get_channel_descriptors().get(message.channel_id)
        requested_op = str(message.metadata.get("op_name", "send") or "send")
        if not self._supports_output_op(descriptor, requested_op):
            log.warning("Output channel %s does not support op %s", message.channel_id, requested_op)
            return False
        try:
            return channel.execute_op(requested_op, message)
        except Exception as exc:
            log.warning("Output channel %s op %s failed: %s", message.channel_id, requested_op, exc)
            return False

    def broadcast(self, text: str, exclude: Optional[List[str]] = None) -> Dict[str, bool]:
        exclude_set = set(exclude or [])
        results: Dict[str, bool] = {}
        for channel_id in self._output_channels:
            if channel_id in exclude_set:
                continue
            results[channel_id] = self.route_outbound(
                ChannelMessage(
                    channel_id=channel_id,
                    user_id="broadcast",
                    text=text,
                    timestamp=0.0,
                    direction="outbound",
                )
            )
        return results

    def get_channel_status(self) -> Dict[str, ChannelStatus]:
        statuses: Dict[str, ChannelStatus] = {}
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            try:
                if hasattr(channel, "get_status"):
                    status = channel.get_status()
                    statuses[channel_id] = (
                        status if isinstance(status, ChannelStatus) else ChannelStatus(str(status))
                    )
                else:
                    statuses[channel_id] = (
                        ChannelStatus.CONNECTED if channel.is_connected() else ChannelStatus.DISCONNECTED
                    )
            except Exception:
                statuses[channel_id] = ChannelStatus.ERROR
        return statuses

    def get_channel_descriptors(self) -> Dict[str, ChannelDescriptor]:
        descriptors: Dict[str, ChannelDescriptor] = {}
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            try:
                descriptors[channel_id] = channel.get_descriptor()
            except Exception as exc:
                log.warning("Channel %s descriptor lookup failed: %s", channel_id, exc)
        return descriptors

    def connect_all(self) -> None:
        seen = set()
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            if channel_id in seen:
                continue
            seen.add(channel_id)
            try:
                channel.connect()
            except Exception as exc:
                log.warning("Channel %s connect failed: %s", channel_id, exc)

    def disconnect_all(self) -> None:
        seen = set()
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            if channel_id in seen:
                continue
            seen.add(channel_id)
            try:
                channel.disconnect()
            except Exception as exc:
                log.warning("Channel %s disconnect failed: %s", channel_id, exc)

    def poll(self, state: HeliosState) -> Dict[str, float]:
        inbound_messages = self.poll_all(state)
        self._pending_messages = [self._message_to_dict(message) for message in inbound_messages]
        self._pending_stimuli = [build_stimulus_envelope(message).to_dict() for message in inbound_messages]
        trigger_dicts: List[Dict[str, float]] = []
        for message in inbound_messages:
            triggers = self._evaluate_message(message, state)
            if triggers:
                trigger_dicts.append(triggers)
        return merge_triggers(trigger_dicts)

    def get_messages(self) -> List[dict]:
        return list(self._pending_messages)

    def get_stimuli(self) -> List[dict]:
        return list(self._pending_stimuli)

    def _evaluate_message(self, message: ChannelMessage, state: HeliosState) -> Dict[str, float]:
        evaluator = self._evaluators.get(message.channel_id)
        if evaluator is None:
            return {}

        try:
            if callable(evaluator):
                return evaluator(message, state)
            if hasattr(evaluator, "evaluate_message"):
                return evaluator.evaluate_message(message, state)
            if hasattr(evaluator, "evaluate"):
                return evaluator.evaluate(message.text)
        except Exception as exc:
            log.warning("Evaluator for channel %s failed: %s", message.channel_id, exc)
            return {}

        return {}

    @staticmethod
    def _message_to_dict(message: ChannelMessage) -> dict:
        data = dict(message.metadata)
        data.setdefault("channel_id", message.channel_id)
        data.setdefault("user_id", message.user_id)
        data.setdefault("text", message.text)
        data.setdefault("timestamp", message.timestamp)
        data.setdefault("direction", message.direction)
        return data

    @staticmethod
    def _supports_output_op(descriptor: Optional[ChannelDescriptor], op_name: str) -> bool:
        if descriptor is None:
            return False
        for op in descriptor.supported_ops:
            if op.name == op_name and op.direction in {"output", "bidirectional"}:
                return True
        return False
