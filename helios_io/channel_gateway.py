"""ChannelGateway bridges channel abstractions into the EventSource pipeline."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .channel import ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelRuntimeSnapshot, ChannelStatus, InputChannel, OutputChannel, build_stimulus_envelope
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
        log.info(
            "channel_registry_event action=register channel_id=%s input=%s output=%s",
            channel_id,
            isinstance(channel, InputChannel),
            isinstance(channel, OutputChannel),
        )

    def deregister_channel(self, channel_id: str) -> None:
        removed_input = self._input_channels.pop(channel_id, None) is not None
        removed_output = self._output_channels.pop(channel_id, None) is not None
        removed_evaluator = self._evaluators.pop(channel_id, None) is not None
        log.info(
            "channel_registry_event action=deregister channel_id=%s input=%s output=%s evaluator=%s",
            channel_id,
            removed_input,
            removed_output,
            removed_evaluator,
        )

    def has_channel(self, channel_id: str) -> bool:
        return channel_id in self._input_channels or channel_id in self._output_channels

    def get_channel(self, channel_id: str) -> InputChannel | OutputChannel | None:
        return self._input_channels.get(channel_id) or self._output_channels.get(channel_id)

    def register_evaluator(self, channel_id: str, evaluator: object) -> None:
        self._evaluators[channel_id] = evaluator
        log.info("channel_registry_event action=register_evaluator channel_id=%s", channel_id)

    def register_runtime_channel(
        self,
        channel: InputChannel | OutputChannel,
        *,
        connect: bool = True,
        evaluator: object | None = None,
    ) -> ChannelManagementResult:
        self.register_channel(channel)
        resolved_evaluator = evaluator if evaluator is not None else (channel if hasattr(channel, "evaluate_message") else None)
        if resolved_evaluator is not None:
            self.register_evaluator(channel.channel_id, resolved_evaluator)
        if connect:
            return self.execute_management_op(channel.channel_id, "connect")
        status = channel.get_status() if hasattr(channel, "get_status") else (ChannelStatus.CONNECTED if channel.is_connected() else ChannelStatus.DISCONNECTED)
        return ChannelManagementResult(
            channel_id=channel.channel_id,
            op_name="register",
            success=True,
            status=status.value if isinstance(status, ChannelStatus) else str(status),
            message="Channel registered without connect.",
        )

    def deregister_runtime_channel(self, channel_id: str, *, disconnect: bool = True) -> ChannelManagementResult:
        if not self.has_channel(channel_id):
            result = ChannelManagementResult(
                channel_id=channel_id,
                op_name="deregister",
                success=False,
                status=ChannelStatus.ERROR.value,
                message=f"Channel {channel_id} is not registered.",
                error_code="channel_not_registered",
            )
            self._log_management_result(result)
            return result
        disconnect_result = None
        if disconnect:
            disconnect_result = self.execute_management_op(channel_id, "disconnect")
        self.deregister_channel(channel_id)
        if disconnect_result is not None and not disconnect_result.success:
            return disconnect_result
        result = ChannelManagementResult(
            channel_id=channel_id,
            op_name="deregister",
            success=True,
            status=ChannelStatus.DEINITIALIZED.value,
            message="Channel deregistered.",
        )
        self._log_management_result(result)
        return result

    def execute_management_op(self, channel_id: str, op_name: str, payload: Optional[Dict[str, Any]] = None) -> ChannelManagementResult:
        channel = self.get_channel(channel_id)
        if channel is None:
            result = ChannelManagementResult(
                channel_id=channel_id,
                op_name=op_name,
                success=False,
                status=ChannelStatus.ERROR.value,
                message=f"Channel {channel_id} is not registered.",
                error_code="channel_not_registered",
            )
            self._log_management_result(result)
            return result
        if hasattr(channel, "execute_management_op"):
            try:
                result = channel.execute_management_op(op_name, payload)
                self._log_management_result(result)
                return result
            except Exception as exc:
                result = ChannelManagementResult(
                    channel_id=channel_id,
                    op_name=op_name,
                    success=False,
                    status=ChannelStatus.ERROR.value,
                    message=str(exc),
                    error_code="management_op_failed",
                )
                self._log_management_result(result)
                return result
        result = ChannelManagementResult(
            channel_id=channel_id,
            op_name=op_name,
            success=False,
            status=ChannelStatus.ERROR.value,
            message=f"Channel {channel_id} does not expose management op dispatch.",
            error_code="management_op_unsupported",
        )
        self._log_management_result(result)
        return result

    def get_channel_config_snapshot(self, channel_id: str) -> ChannelManagementResult:
        return self.execute_management_op(channel_id, "get_config")

    def update_channel_config(self, channel_id: str, updates: Optional[Dict[str, Any]] = None) -> ChannelManagementResult:
        return self.execute_management_op(channel_id, "update_config", {"config": dict(updates or {})})

    def health_check_channel(self, channel_id: str) -> ChannelManagementResult:
        return self.execute_management_op(channel_id, "health_check")

    def execute_input_op(self, channel_id: str, op_name: str, payload: Optional[Dict[str, Any]] = None) -> List[ChannelMessage]:
        channel = self._input_channels.get(channel_id)
        if channel is None:
            log.warning(
                "channel_input_event result=failed reason=channel_not_registered channel_id=%s op_name=%s",
                channel_id,
                op_name,
            )
            return []
        try:
            descriptor = channel.get_descriptor()
        except Exception:
            descriptor = self.get_channel_descriptors().get(channel_id)
        if not self._supports_input_op(descriptor, op_name):
            log.warning(
                "channel_input_event result=failed reason=unsupported_input_op channel_id=%s op_name=%s",
                channel_id,
                op_name,
            )
            return []
        try:
            messages = channel.execute_input_op(op_name, payload)
            log.info(
                "channel_input_event result=success reason=executed channel_id=%s op_name=%s message_count=%s",
                channel_id,
                op_name,
                len(messages),
            )
            return list(messages)
        except Exception as exc:
            log.warning(
                "channel_input_event result=failed reason=execution_error channel_id=%s op_name=%s error=%s",
                channel_id,
                op_name,
                exc,
            )
            return []

    def poll_all(self, state: HeliosState) -> List[ChannelMessage]:
        messages: List[ChannelMessage] = []
        for channel_id, channel in self._input_channels.items():
            if not channel.is_connected() and not getattr(channel, "poll_when_disconnected", False):
                continue
            try:
                messages.extend(self.execute_input_op(channel_id, "poll", {"state": state}))
            except Exception as exc:
                log.warning("Input channel %s poll failed: %s", channel_id, exc)
        return messages

    def route_outbound(self, message: ChannelMessage) -> bool:
        channel = self._output_channels.get(message.channel_id)
        requested_op = str(message.metadata.get("op_name", "send") or "send")
        log.debug(
            "owner_path_node=channel_gateway_enter channel_id=%s op_name=%s user_id_present=%s text_len=%d owner_path=%s",
            message.channel_id,
            requested_op,
            bool(str(message.user_id or "").strip()),
            len(str(message.text or "")),
            str(message.metadata.get("owner_path", "") or ""),
        )
        if channel is None:
            log.warning(
                "channel_route_event result=failed reason=channel_not_registered channel_id=%s op_name=%s",
                message.channel_id,
                requested_op,
            )
            return False
        if not channel.is_connected():
            log.warning(
                "channel_route_event result=failed reason=channel_disconnected channel_id=%s op_name=%s",
                message.channel_id,
                requested_op,
            )
            return False
        descriptor = self.get_channel_descriptors().get(message.channel_id)
        if not self._supports_output_op(descriptor, requested_op):
            log.warning(
                "channel_route_event result=failed reason=unsupported_output_op channel_id=%s op_name=%s",
                message.channel_id,
                requested_op,
            )
            return False
        try:
            ok = channel.execute_op(requested_op, message)
            log.debug(
                "owner_path_node=channel_gateway_exit channel_id=%s op_name=%s ok=%s rendered_text_present=%s",
                message.channel_id,
                requested_op,
                ok,
                bool(str(message.metadata.get("rendered_text", "") or "").strip()),
            )
            log.info(
                "channel_route_event result=%s reason=executed channel_id=%s op_name=%s",
                "success" if ok else "failed",
                message.channel_id,
                requested_op,
            )
            return ok
        except Exception as exc:
            log.warning(
                "channel_route_event result=failed reason=execution_error channel_id=%s op_name=%s error=%s",
                message.channel_id,
                requested_op,
                exc,
            )
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

    def get_runtime_snapshot(self) -> ChannelRuntimeSnapshot:
        return ChannelRuntimeSnapshot(
            descriptors=self.get_channel_descriptors(),
            statuses=self.get_channel_status(),
        )

    def connect_all(self) -> None:
        seen = set()
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            if channel_id in seen:
                continue
            seen.add(channel_id)
            result = self.execute_management_op(channel_id, "connect")
            if not result.success:
                log.warning("Channel %s connect failed: %s", channel_id, result.message)

    def disconnect_all(self) -> None:
        seen = set()
        for channel_id, channel in {**self._input_channels, **self._output_channels}.items():
            if channel_id in seen:
                continue
            seen.add(channel_id)
            result = self.execute_management_op(channel_id, "disconnect")
            if not result.success:
                log.warning("Channel %s disconnect failed: %s", channel_id, result.message)

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

    @staticmethod
    def _supports_input_op(descriptor: Optional[ChannelDescriptor], op_name: str) -> bool:
        if descriptor is None:
            return False
        for op in descriptor.supported_ops:
            if op.name == op_name and op.direction in {"input", "bidirectional"}:
                return True
        return False

    @staticmethod
    def _log_management_result(result: ChannelManagementResult) -> None:
        level = logging.INFO if result.success else logging.WARNING
        log.log(
            level,
            "channel_management_event channel_id=%s op_name=%s success=%s status=%s error_code=%s message=%s",
            result.channel_id,
            result.op_name,
            result.success,
            result.status,
            result.error_code or "",
            result.message or "",
        )
