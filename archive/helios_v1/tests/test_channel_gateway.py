"""Tests for channel abstractions and ChannelGateway routing."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.helios_state import HeliosState
from helios_io.channel import BidirectionalChannel, ChannelDescriptor, ChannelManagementResult, ChannelMessage, ChannelOpDescriptor, ChannelStatus
from helios_io.channel_gateway import ChannelGateway


@dataclass
class StubChannel(BidirectionalChannel):
    _channel_id: str
    connected: bool = True
    paused: bool = False
    suspended: bool = False
    inbound_messages: List[ChannelMessage] = field(default_factory=list)
    sent_messages: List[ChannelMessage] = field(default_factory=list)
    executed_ops: List[tuple[str, ChannelMessage]] = field(default_factory=list)
    connect_calls: int = 0
    disconnect_calls: int = 0
    management_ops: list[tuple[str, dict]] = field(default_factory=list)
    input_ops: list[tuple[str, dict]] = field(default_factory=list)
    config: dict[str, object] = field(default_factory=lambda: {"enabled": True, "label": "stub"})

    @property
    def channel_id(self) -> str:
        return self._channel_id

    def poll(self) -> List[ChannelMessage]:
        messages = list(self.inbound_messages)
        self.inbound_messages.clear()
        return messages

    def execute_input_op(self, op_name: str, payload: dict | None = None) -> List[ChannelMessage]:
        self.input_ops.append((op_name, dict(payload or {})))
        return super().execute_input_op(op_name, payload)

    def send(self, message: ChannelMessage) -> bool:
        self.sent_messages.append(message)
        return True

    def execute_op(self, op_name: str, message: ChannelMessage) -> bool:
        self.executed_ops.append((op_name, message))
        if op_name == "send":
            return self.send(message)
        return True

    def is_connected(self) -> bool:
        return self.connected

    def get_status(self) -> ChannelStatus:
        if self.suspended:
            return ChannelStatus.SUSPENDED
        if self.paused:
            return ChannelStatus.PAUSED
        return ChannelStatus.CONNECTED if self.connected else ChannelStatus.DISCONNECTED

    def get_config_snapshot(self):
        from helios_io.channel import ChannelConfigSnapshot

        return ChannelConfigSnapshot(
            channel_id=self.channel_id,
            status=self.get_status().value,
            config_values=dict(self.config),
            mutable_fields=["enabled"],
            validation_errors=[],
        )

    def update_config(self, updates: dict | None = None):
        from helios_io.channel import ChannelConfigSnapshot

        updates = dict(updates or {})
        errors: list[str] = []
        if "label" in updates and str(updates["label"] or "") != str(self.config.get("label", "")):
            errors.append("label is immutable at runtime")
        if "enabled" in updates:
            self.config["enabled"] = bool(updates["enabled"])
        snapshot = self.get_config_snapshot()
        if errors:
            return ChannelConfigSnapshot(
                channel_id=snapshot.channel_id,
                status=snapshot.status,
                config_values=snapshot.config_values,
                mutable_fields=snapshot.mutable_fields,
                validation_errors=errors,
            )
        return snapshot

    def health_check(self) -> dict:
        return {
            "channel_id": self.channel_id,
            "status": self.get_status().value,
            "connected": self.connected,
            "paused": self.paused,
            "suspended": self.suspended,
        }

    def connect(self) -> None:
        self.connect_calls += 1
        self.connected = True
        self.paused = False
        self.suspended = False

    def disconnect(self) -> None:
        self.disconnect_calls += 1
        self.connected = False
        self.paused = False
        self.suspended = False

    def get_descriptor(self) -> ChannelDescriptor:
        return ChannelDescriptor(
            channel_id=self._channel_id,
            display_name=f"Stub {self._channel_id}",
            input_types=["text_message"],
            output_types=["text_message"],
            input_formats=["text/plain"],
            output_formats=["text/plain"],
            capabilities=["poll", "send", "text_input", "text_output"],
            supported_ops=[
                ChannelOpDescriptor(
                    name="poll",
                    direction="input",
                    description=f"poll via {self._channel_id}",
                ),
                ChannelOpDescriptor(
                    name="send",
                    direction="output",
                    description=f"send via {self._channel_id}",
                )
            ],
            management_ops=[
                ChannelOpDescriptor(name="connect", direction="management", description="connect"),
                ChannelOpDescriptor(name="disconnect", direction="management", description="disconnect"),
                ChannelOpDescriptor(name="get_config", direction="management", description="config"),
            ],
        )

    def execute_management_op(self, op_name: str, payload: dict | None = None) -> ChannelManagementResult:
        self.management_ops.append((op_name, dict(payload or {})))
        if op_name == "connect":
            self.connect()
            return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.CONNECTED.value)
        if op_name == "disconnect":
            self.disconnect()
            return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.DISCONNECTED.value)
        if op_name == "pause":
            self.paused = True
            return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.PAUSED.value)
        if op_name == "resume":
            self.paused = False
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value)
        if op_name == "suspend":
            self.suspended = True
            return ChannelManagementResult(self.channel_id, op_name, True, ChannelStatus.SUSPENDED.value)
        if op_name == "unsuspend":
            self.suspended = False
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value)
        if op_name == "get_config":
            snapshot = self.get_config_snapshot()
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload={"snapshot": dict(snapshot.config_values), "validation_errors": []})
        if op_name == "update_config":
            snapshot = self.update_config((payload or {}).get("config", {}))
            return ChannelManagementResult(
                self.channel_id,
                op_name,
                not snapshot.validation_errors,
                self.get_status().value,
                payload={"snapshot": dict(snapshot.config_values), "validation_errors": list(snapshot.validation_errors)},
                error_code="config_validation_failed" if snapshot.validation_errors else "",
            )
        if op_name == "health_check":
            return ChannelManagementResult(self.channel_id, op_name, True, self.get_status().value, payload=self.health_check())
        return ChannelManagementResult(self.channel_id, op_name, False, self.get_status().value, error_code="unsupported")


def make_message(channel_id: str, user_id: str, text: str, timestamp: float = 1.0) -> ChannelMessage:
    return ChannelMessage(
        channel_id=channel_id,
        user_id=user_id,
        text=text,
        timestamp=timestamp,
        metadata={"message_id": f"{channel_id}-{user_id}"},
        direction="inbound",
    )


class TestChannelGatewayRegistrationAndRouting:
    def test_register_and_deregister_emit_registry_logs(self, caplog):
        gateway = ChannelGateway()
        qq = StubChannel("qq")

        with caplog.at_level(logging.INFO, logger="helios.helios_io.channel_gateway"):
            gateway.register_channel(qq)
            gateway.register_evaluator("qq", object())
            gateway.deregister_channel("qq")

        assert "channel_registry_event action=register channel_id=qq" in caplog.text
        assert "channel_registry_event action=register_evaluator channel_id=qq" in caplog.text
        assert "channel_registry_event action=deregister channel_id=qq" in caplog.text

    def test_route_outbound_to_matching_channel(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        tts = StubChannel("tts")
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        ok = gateway.route_outbound(
            ChannelMessage(
                channel_id="tts",
                user_id="user-1",
                text="hello",
                timestamp=2.0,
                direction="outbound",
            )
        )

        assert ok is True
        assert len(qq.sent_messages) == 0
        assert len(tts.sent_messages) == 1
        assert tts.sent_messages[0].text == "hello"
        assert tts.executed_ops[0][0] == "send"

    def test_route_outbound_skips_disconnected_channel(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        ok = gateway.route_outbound(
            ChannelMessage(
                channel_id="qq",
                user_id="user-1",
                text="hello",
                timestamp=2.0,
                direction="outbound",
            )
        )

        assert ok is False
        assert qq.sent_messages == []

    def test_route_outbound_rejects_unsupported_explicit_op(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        gateway.register_channel(qq)

        ok = gateway.route_outbound(
            ChannelMessage(
                channel_id="qq",
                user_id="user-1",
                text="hello",
                timestamp=2.0,
                metadata={"op_name": "broadcast"},
                direction="outbound",
            )
        )

        assert ok is False
        assert qq.executed_ops == []

    def test_poll_all_collects_from_connected_channels_only(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "hello")])
        vision = StubChannel("vision", connected=False, inbound_messages=[make_message("vision", "cam", "frame")])
        gateway.register_channel(qq)
        gateway.register_channel(vision)

        polled = gateway.poll_all(HeliosState())

        assert [message.text for message in polled] == ["hello"]
        assert qq.input_ops[0][0] == "poll"
        assert vision.input_ops == []

    def test_execute_input_op_rejects_unsupported_explicit_input_op(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        gateway.register_channel(qq)

        messages = gateway.execute_input_op("qq", "stream")

        assert messages == []
        assert qq.input_ops == []

    def test_get_channel_status_reports_connected_and_disconnected(self):
        gateway = ChannelGateway()
        gateway.register_channel(StubChannel("qq", connected=True))
        gateway.register_channel(StubChannel("tts", connected=False))

        statuses = gateway.get_channel_status()

        assert statuses["qq"] == ChannelStatus.CONNECTED
        assert statuses["tts"] == ChannelStatus.DISCONNECTED

    def test_get_channel_status_prefers_explicit_channel_status(self):
        gateway = ChannelGateway()

        class ReconnectingStub(StubChannel):
            def get_status(self) -> ChannelStatus:
                return ChannelStatus.RECONNECTING

        gateway.register_channel(ReconnectingStub("qq", connected=False))

        statuses = gateway.get_channel_status()

        assert statuses["qq"] == ChannelStatus.RECONNECTING

    def test_connect_and_disconnect_all_deduplicate_bidirectional_channels(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        gateway.connect_all()
        gateway.disconnect_all()

        assert qq.connect_calls == 1
        assert qq.disconnect_calls == 1

    def test_get_channel_descriptors_returns_registered_descriptors(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        tts = StubChannel("tts")
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        descriptors = gateway.get_channel_descriptors()

        assert descriptors["qq"].display_name == "Stub qq"
        assert descriptors["tts"].output_types == ["text_message"]

    def test_get_runtime_snapshot_returns_descriptor_and_status_owner_view(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=True)
        tts = StubChannel("tts", connected=False)
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        snapshot = gateway.get_runtime_snapshot()

        assert snapshot.descriptors["qq"].display_name == "Stub qq"
        assert snapshot.statuses["qq"] == ChannelStatus.CONNECTED
        assert snapshot.statuses["tts"] == ChannelStatus.DISCONNECTED

    def test_execute_management_op_dispatches_to_registered_channel(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        result = gateway.execute_management_op("qq", "connect")

        assert result.success is True
        assert qq.connected is True
        assert qq.management_ops[0][0] == "connect"

    def test_gateway_owner_api_surfaces_config_snapshot_and_validated_update(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        gateway.register_channel(qq)

        config_result = gateway.get_channel_config_snapshot("qq")
        ok_update = gateway.update_channel_config("qq", {"enabled": False})
        bad_update = gateway.update_channel_config("qq", {"label": "other"})

        assert config_result.success is True
        assert config_result.payload["snapshot"]["enabled"] is True
        assert ok_update.success is True
        assert ok_update.payload["snapshot"]["enabled"] is False
        assert bad_update.success is False
        assert bad_update.error_code == "config_validation_failed"
        assert "label is immutable at runtime" in bad_update.payload["validation_errors"]

    def test_gateway_owner_api_surfaces_health_check_payload(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=True)
        gateway.register_channel(qq)

        result = gateway.health_check_channel("qq")

        assert result.success is True
        assert result.payload["channel_id"] == "qq"
        assert result.payload["status"] == ChannelStatus.CONNECTED.value
        assert result.payload["connected"] is True

    def test_execute_management_op_updates_status_for_pause_resume_suspend_unsuspend(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=True)
        gateway.register_channel(qq)

        pause_result = gateway.execute_management_op("qq", "pause")
        paused_snapshot = gateway.get_runtime_snapshot()
        resume_result = gateway.execute_management_op("qq", "resume")
        suspend_result = gateway.execute_management_op("qq", "suspend")
        suspended_snapshot = gateway.get_runtime_snapshot()
        unsuspend_result = gateway.execute_management_op("qq", "unsuspend")

        assert pause_result.status == ChannelStatus.PAUSED.value
        assert paused_snapshot.statuses["qq"] == ChannelStatus.PAUSED
        assert resume_result.status == ChannelStatus.CONNECTED.value
        assert suspend_result.status == ChannelStatus.SUSPENDED.value
        assert suspended_snapshot.statuses["qq"] == ChannelStatus.SUSPENDED
        assert unsuspend_result.status == ChannelStatus.CONNECTED.value

    def test_execute_management_op_reports_missing_channel(self):
        gateway = ChannelGateway()

        result = gateway.execute_management_op("missing", "connect")

        assert result.success is False
        assert result.error_code == "channel_not_registered"

    def test_register_and_deregister_runtime_channel_delegate_connect_and_cleanup(self):
        gateway = ChannelGateway()
        dynamic = StubChannel("dynamic", connected=False)

        register_result = gateway.register_runtime_channel(dynamic)

        assert register_result.success is True
        assert gateway.has_channel("dynamic") is True
        assert gateway.get_channel_status()["dynamic"] == ChannelStatus.CONNECTED

        deregister_result = gateway.deregister_runtime_channel("dynamic")

        assert deregister_result.success is True
        assert dynamic.disconnect_calls == 1
        assert gateway.has_channel("dynamic") is False

    def test_register_runtime_channel_registers_default_evaluator_for_evaluable_channel(self):
        gateway = ChannelGateway()

        class EvaluableStub(StubChannel):
            def evaluate_message(self, message, state=None):
                return {"CARE": 0.1}

        dynamic = EvaluableStub("dynamic", connected=False)

        gateway.register_runtime_channel(dynamic, connect=False)

        assert gateway._evaluators["dynamic"] is dynamic

    def test_execute_management_op_emits_structured_log(self, caplog):
        gateway = ChannelGateway()
        qq = StubChannel("qq", connected=False)
        gateway.register_channel(qq)

        with caplog.at_level(logging.INFO, logger="helios.helios_io.channel_gateway"):
            gateway.execute_management_op("qq", "connect")

        assert "channel_management_event channel_id=qq op_name=connect success=True status=connected" in caplog.text

    def test_route_outbound_failure_emits_structured_log(self, caplog):
        gateway = ChannelGateway()

        with caplog.at_level(logging.WARNING, logger="helios.helios_io.channel_gateway"):
            ok = gateway.route_outbound(
                ChannelMessage(
                    channel_id="missing",
                    user_id="user-1",
                    text="hello",
                    timestamp=2.0,
                    direction="outbound",
                )
            )

        assert ok is False
        assert "channel_route_event result=failed reason=channel_not_registered channel_id=missing op_name=send" in caplog.text

    def test_register_and_deregister_change_registry_visibility(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")

        gateway.register_channel(qq)
        assert gateway.has_channel("qq") is True

        gateway.deregister_channel("qq")

        assert gateway.has_channel("qq") is False
        assert "qq" not in gateway.get_channel_descriptors()


class TestChannelGatewayEventSourceAdapter:
    def test_poll_merges_triggers_from_registered_evaluators(self):
        gateway = ChannelGateway(
            evaluators={
                "qq": lambda message, state: {"CARE": 0.4 if state.tick == 7 else 0.2},
                "vision": lambda message, state: {"FEAR": 0.6},
            }
        )
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "你好")])
        vision = StubChannel("vision", inbound_messages=[make_message("vision", "camera", "motion")])
        gateway.register_channel(qq)
        gateway.register_channel(vision)

        triggers = gateway.poll(HeliosState(tick=7))

        assert triggers == {"CARE": 0.4, "FEAR": 0.6}

    def test_get_messages_returns_raw_message_dicts_from_last_poll(self):
        gateway = ChannelGateway(evaluators={"qq": lambda message, state: {}})
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "hello")])
        gateway.register_channel(qq)

        gateway.poll(HeliosState())
        messages = gateway.get_messages()

        assert len(messages) == 1
        assert messages[0]["channel_id"] == "qq"
        assert messages[0]["user_id"] == "u1"
        assert messages[0]["text"] == "hello"

    def test_get_stimuli_returns_normalized_stimulus_contract_from_last_poll(self):
        gateway = ChannelGateway(evaluators={"qq": lambda message, state: {}})
        qq = StubChannel("qq", inbound_messages=[make_message("qq", "u1", "hello")])
        gateway.register_channel(qq)

        gateway.poll(HeliosState())
        stimuli = gateway.get_stimuli()

        assert len(stimuli) == 1
        assert stimuli[0]["source_channel_id"] == "qq"
        assert stimuli[0]["payload"]["user_id"] == "u1"
        assert 0.0 <= stimuli[0]["stimulus_intensity"] <= 1.0

    def test_broadcast_routes_to_all_non_excluded_channels(self):
        gateway = ChannelGateway()
        qq = StubChannel("qq")
        tts = StubChannel("tts")
        gateway.register_channel(qq)
        gateway.register_channel(tts)

        results = gateway.broadcast("sync", exclude=["qq"])

        assert results == {"tts": True}
        assert len(qq.sent_messages) == 0
        assert len(tts.sent_messages) == 1
        assert tts.sent_messages[0].direction == "outbound"