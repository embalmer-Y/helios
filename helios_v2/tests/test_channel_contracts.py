"""Owner-boundary contract tests for the channel driver subsystem (requirement 30)."""

from __future__ import annotations

import pytest

from helios_v2.channel import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelConfigField,
    ChannelConfigSnapshot,
    ChannelDriverDescriptor,
    ChannelDriverReadiness,
    ChannelDriverStatusReport,
    ChannelError,
    ChannelManagementResult,
    ChannelReadinessReport,
    ChannelStateSnapshot,
    InboundDrainResult,
    InboundPacket,
    OutboundDispatchOutcome,
    OutboundPacket,
    SubsystemDispatchResult,
    SubsystemDrainResult,
)
from helios_v2.channel.contracts import ChannelReadinessReport as _ReportAlias


def _descriptor(driver_id: str = "fake") -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        driver_id=driver_id,
        display_name="Fake Driver",
        directions=("inbound", "outbound"),
        input_packet_types=("text",),
        output_ops=("emit_text",),
        management_ops=("connect", "disconnect"),
        config_fields=(
            ChannelConfigField(
                key="endpoint",
                description="endpoint url",
                required=True,
                mutable_at_runtime=False,
                schema_hint="str",
            ),
        ),
        health_signals=("overflow_count",),
    )


def test_qos_metadata_key_is_stable() -> None:
    assert CHANNEL_QOS_METADATA_KEY == "channel_qos"


def test_descriptor_rejects_empty_identity() -> None:
    with pytest.raises(ChannelError):
        ChannelDriverDescriptor(driver_id="", display_name="x", directions=("inbound",))
    with pytest.raises(ChannelError):
        ChannelDriverDescriptor(driver_id="x", display_name="", directions=("inbound",))


def test_descriptor_requires_direction_in_taxonomy() -> None:
    with pytest.raises(ChannelError):
        ChannelDriverDescriptor(driver_id="x", display_name="x", directions=())
    with pytest.raises(ChannelError):
        ChannelDriverDescriptor(driver_id="x", display_name="x", directions=("sideways",))  # type: ignore[arg-type]


def test_descriptor_rejects_duplicate_config_field_keys() -> None:
    field_a = ChannelConfigField(
        key="dup", description="a", required=True, mutable_at_runtime=False, schema_hint="str"
    )
    field_b = ChannelConfigField(
        key="dup", description="b", required=False, mutable_at_runtime=True, schema_hint="int"
    )
    with pytest.raises(ChannelError):
        ChannelDriverDescriptor(
            driver_id="x",
            display_name="x",
            directions=("inbound",),
            config_fields=(field_a, field_b),
        )


def test_descriptor_supports_direction_query() -> None:
    descriptor = _descriptor()
    assert descriptor.supports_direction("inbound") is True
    assert descriptor.supports_direction("outbound") is True


def test_config_snapshot_rejects_bad_status() -> None:
    with pytest.raises(ChannelError):
        ChannelConfigSnapshot(driver_id="x", status="bogus")  # type: ignore[arg-type]


def test_management_result_failure_requires_error_code() -> None:
    with pytest.raises(ChannelError):
        ChannelManagementResult(
            driver_id="x",
            op_name="connect",
            success=False,
            status="error",
            message="failed",
            error_code=None,
        )


def test_management_result_success_is_valid() -> None:
    result = ChannelManagementResult(
        driver_id="x",
        op_name="connect",
        success=True,
        status="connected",
        message="ok",
    )
    assert result.success is True
    assert result.payload == {}


def test_status_report_rejects_negative_pending() -> None:
    with pytest.raises(ChannelError):
        ChannelDriverStatusReport(
            driver_id="x", status="connected", connected=True, pending_inbound=-1
        )


def test_inbound_packet_enforces_qos_taxonomy() -> None:
    packet = InboundPacket(
        packet_id="p1",
        driver_id="x",
        packet_type="text",
        content="hello",
        qos_class="interactive",
    )
    assert packet.qos_class == "interactive"
    with pytest.raises(ChannelError):
        InboundPacket(
            packet_id="p2",
            driver_id="x",
            packet_type="text",
            content="hello",
            qos_class="urgent",  # type: ignore[arg-type]
        )


def test_inbound_packet_rejects_empty_identity() -> None:
    with pytest.raises(ChannelError):
        InboundPacket(packet_id="", driver_id="x", packet_type="text", content="c", qos_class="bulk")
    with pytest.raises(ChannelError):
        InboundPacket(packet_id="p", driver_id="", packet_type="text", content="c", qos_class="bulk")
    with pytest.raises(ChannelError):
        InboundPacket(packet_id="p", driver_id="x", packet_type="", content="c", qos_class="bulk")


def test_inbound_drain_result_rejects_foreign_packet() -> None:
    foreign = InboundPacket(
        packet_id="p", driver_id="other", packet_type="text", content="c", qos_class="control"
    )
    with pytest.raises(ChannelError):
        InboundDrainResult(driver_id="self", packets=(foreign,), pending_remaining=0)


def test_inbound_drain_result_rejects_negative_counts() -> None:
    with pytest.raises(ChannelError):
        InboundDrainResult(driver_id="x", packets=(), pending_remaining=-1)
    with pytest.raises(ChannelError):
        InboundDrainResult(driver_id="x", packets=(), pending_remaining=0, overflow_count=-1)


def test_subsystem_drain_result_validates_overflow_counts() -> None:
    result = SubsystemDrainResult(
        raw_signals=(),
        pending_remaining=0,
        drained_count=0,
        overflow_counts={"d1": 2},
    )
    assert result.overflow_counts["d1"] == 2
    with pytest.raises(ChannelError):
        SubsystemDrainResult(
            raw_signals=(), pending_remaining=0, drained_count=0, overflow_counts={"d1": -1}
        )


def test_outbound_packet_rejects_negative_priority() -> None:
    with pytest.raises(ChannelError):
        OutboundPacket(packet_id="p", target_driver_id="x", op_name="emit", execution_priority=-1)


def test_outbound_dispatch_outcome_enforces_status_taxonomy() -> None:
    outcome = OutboundDispatchOutcome(
        packet_id="p", target_driver_id="x", status="delivered", detail="ok"
    )
    assert outcome.status == "delivered"
    with pytest.raises(ChannelError):
        OutboundDispatchOutcome(packet_id="p", target_driver_id="x", status="maybe", detail="?")  # type: ignore[arg-type]


def test_subsystem_dispatch_result_rejects_negative_counts() -> None:
    with pytest.raises(ChannelError):
        SubsystemDispatchResult(outcomes=(), dispatched_count=-1, deferred_count=0)
    with pytest.raises(ChannelError):
        SubsystemDispatchResult(outcomes=(), dispatched_count=0, deferred_count=-1)


def test_readiness_report_rejects_duplicate_drivers() -> None:
    entry = ChannelDriverReadiness(driver_id="x", ready=True, detail="ok")
    with pytest.raises(ChannelError):
        _ReportAlias(report_id="r", entries=(entry, entry))


def test_readiness_report_all_ready() -> None:
    ready = ChannelReadinessReport(
        report_id="r",
        entries=(ChannelDriverReadiness(driver_id="x", ready=True, detail="ok"),),
    )
    assert ready.all_ready() is True
    not_ready = ChannelReadinessReport(
        report_id="r",
        entries=(ChannelDriverReadiness(driver_id="x", ready=False, detail="no cred"),),
    )
    assert not_ready.all_ready() is False
    empty = ChannelReadinessReport(report_id="r", entries=())
    assert empty.all_ready() is False


def test_channel_state_snapshot_rejects_duplicate_descriptor_ids() -> None:
    with pytest.raises(ChannelError):
        ChannelStateSnapshot(descriptors=(_descriptor("a"), _descriptor("a")), statuses=())
