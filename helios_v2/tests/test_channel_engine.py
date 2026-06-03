"""Engine tests for the channel driver subsystem (requirement 30).

All tests are deterministic and network-free; they exercise the framework against the
in-memory fake driver only.
"""

from __future__ import annotations

import pytest

from helios_v2.channel import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelConfigField,
    ChannelDriverDescriptor,
    ChannelError,
    ChannelSubsystem,
    InMemoryChannelDriver,
    OutboundPacket,
)
from helios_v2.sensory.contracts import RawSignal


def _descriptor(driver_id: str) -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        driver_id=driver_id,
        display_name=f"Fake {driver_id}",
        directions=("inbound", "outbound"),
        input_packet_types=("text",),
        output_ops=("emit_text",),
        management_ops=("connect", "disconnect", "pause", "teardown"),
        config_fields=(
            ChannelConfigField(
                key="backlog_capacity",
                description="max queued packets",
                required=False,
                mutable_at_runtime=True,
                schema_hint="int",
            ),
        ),
        health_signals=("overflow_count",),
    )


def _driver(driver_id: str, **kwargs) -> InMemoryChannelDriver:
    return InMemoryChannelDriver(_descriptor=_descriptor(driver_id), **kwargs)


def test_register_makes_driver_discoverable() -> None:
    subsystem = ChannelSubsystem()
    result = subsystem.register_driver(_driver("cli"))
    assert result.success is True
    assert result.op_name == "register_driver"
    assert tuple(d.driver_id for d in subsystem.descriptors()) == ("cli",)


def test_duplicate_registration_is_rejected() -> None:
    subsystem = ChannelSubsystem()
    subsystem.register_driver(_driver("cli"))
    with pytest.raises(ChannelError):
        subsystem.register_driver(_driver("cli"))


def test_deregister_tears_down_then_removes() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    result = subsystem.deregister_driver("cli")
    assert result.success is True
    assert result.payload["teardown_status"] == "disconnected"
    assert subsystem.descriptors() == ()
    with pytest.raises(ChannelError):
        subsystem.deregister_driver("cli")


def test_apply_management_op_routes_to_driver() -> None:
    subsystem = ChannelSubsystem()
    subsystem.register_driver(_driver("cli"))
    result = subsystem.apply_management_op("cli", "connect", None)
    assert result.success is True
    assert result.status == "connected"
    statuses = {s.driver_id: s for s in subsystem.statuses()}
    assert statuses["cli"].connected is True


def test_apply_management_op_unknown_driver_raises() -> None:
    subsystem = ChannelSubsystem()
    with pytest.raises(ChannelError):
        subsystem.apply_management_op("ghost", "connect", None)


def test_drain_maps_packets_to_raw_signals_with_qos_marker() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    driver.enqueue_inbound("p1", "text", "hello", qos_class="control")
    result = subsystem.drain_inbound(budget=10)
    assert result.drained_count == 1
    assert result.pending_remaining == 0
    signal = result.raw_signals[0]
    assert isinstance(signal, RawSignal)
    assert signal.signal_id == "p1"
    assert signal.source_name == "cli"
    assert signal.channel == "cli"
    assert signal.metadata[CHANNEL_QOS_METADATA_KEY] == "control"


def test_drain_is_bounded_by_budget_with_pending_carry() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    for index in range(5):
        driver.enqueue_inbound(f"p{index}", "text", f"msg-{index}")
    first = subsystem.drain_inbound(budget=2)
    assert first.drained_count == 2
    assert first.pending_remaining == 3
    second = subsystem.drain_inbound(budget=2)
    assert second.drained_count == 2
    assert second.pending_remaining == 1
    third = subsystem.drain_inbound(budget=2)
    assert third.drained_count == 1
    assert third.pending_remaining == 0


def test_drain_is_fair_round_robin_across_drivers() -> None:
    subsystem = ChannelSubsystem()
    driver_a = _driver("a")
    driver_b = _driver("b")
    subsystem.register_driver(driver_a)
    subsystem.register_driver(driver_b)
    for index in range(3):
        driver_a.enqueue_inbound(f"a{index}", "text", "x")
        driver_b.enqueue_inbound(f"b{index}", "text", "y")
    # budget 1 should start at driver a, then advance the cursor to b next tick
    first = subsystem.drain_inbound(budget=1)
    assert [s.source_name for s in first.raw_signals] == ["a"]
    second = subsystem.drain_inbound(budget=1)
    assert [s.source_name for s in second.raw_signals] == ["b"]


def test_drain_zero_budget_drains_nothing() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    driver.enqueue_inbound("p1", "text", "hello")
    result = subsystem.drain_inbound(budget=0)
    assert result.drained_count == 0
    assert result.pending_remaining == 1


def test_drain_negative_budget_raises() -> None:
    subsystem = ChannelSubsystem()
    with pytest.raises(ChannelError):
        subsystem.drain_inbound(budget=-1)


def test_backlog_overflow_is_bounded_and_counted() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli", backlog_capacity=2)
    subsystem.register_driver(driver)
    assert driver.enqueue_inbound("p1", "text", "a") is True
    assert driver.enqueue_inbound("p2", "text", "b") is True
    assert driver.enqueue_inbound("p3", "text", "c") is False  # overflow dropped
    result = subsystem.drain_inbound(budget=10)
    assert result.drained_count == 2
    assert result.overflow_counts["cli"] == 1


def test_dispatch_delivers_to_target_driver() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    packet = OutboundPacket(packet_id="o1", target_driver_id="cli", op_name="emit_text")
    result = subsystem.dispatch_outbound((packet,), budget=10)
    assert result.dispatched_count == 1
    assert result.outcomes[0].status == "delivered"
    assert driver.sent_packets[0].packet_id == "o1"


def test_dispatch_respects_execution_priority() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    low = OutboundPacket(packet_id="low", target_driver_id="cli", op_name="emit_text", execution_priority=1)
    high = OutboundPacket(packet_id="high", target_driver_id="cli", op_name="emit_text", execution_priority=9)
    subsystem.dispatch_outbound((low, high), budget=10)
    assert [p.packet_id for p in driver.sent_packets] == ["high", "low"]


def test_dispatch_budget_defers_remainder() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    packets = tuple(
        OutboundPacket(packet_id=f"o{i}", target_driver_id="cli", op_name="emit_text")
        for i in range(3)
    )
    result = subsystem.dispatch_outbound(packets, budget=1)
    assert result.dispatched_count == 1
    assert result.deferred_count == 2


def test_dispatch_unknown_driver_yields_driver_unavailable() -> None:
    subsystem = ChannelSubsystem()
    packet = OutboundPacket(packet_id="o1", target_driver_id="ghost", op_name="emit_text")
    result = subsystem.dispatch_outbound((packet,), budget=10)
    assert result.dispatched_count == 0
    assert result.outcomes[0].status == "driver_unavailable"


def test_dispatch_failed_delivery_is_reported() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    driver.set_send_failure(True)
    subsystem.register_driver(driver)
    packet = OutboundPacket(packet_id="o1", target_driver_id="cli", op_name="emit_text")
    result = subsystem.dispatch_outbound((packet,), budget=10)
    assert result.outcomes[0].status == "failed"


def test_dispatch_negative_budget_raises() -> None:
    subsystem = ChannelSubsystem()
    with pytest.raises(ChannelError):
        subsystem.dispatch_outbound((), budget=-1)


def test_channel_state_snapshot_reports_real_state() -> None:
    subsystem = ChannelSubsystem()
    driver = _driver("cli")
    subsystem.register_driver(driver)
    subsystem.apply_management_op("cli", "connect", None)
    driver.enqueue_inbound("p1", "text", "hello")
    snapshot = subsystem.channel_state_snapshot()
    assert tuple(d.driver_id for d in snapshot.descriptors) == ("cli",)
    status = snapshot.statuses[0]
    assert status.connected is True
    assert status.pending_inbound == 1


def test_static_readiness_reports_missing_credential() -> None:
    subsystem = ChannelSubsystem()
    subsystem.register_driver(_driver("ready", credential_present=True))
    subsystem.register_driver(_driver("unready", credential_present=False))
    report = subsystem.check_static_readiness(("ready", "unready", "ghost"))
    by_id = {entry.driver_id: entry for entry in report.entries}
    assert by_id["ready"].ready is True
    assert by_id["unready"].ready is False
    assert by_id["ghost"].ready is False
    assert report.all_ready() is False


def test_static_readiness_all_ready_is_deterministic() -> None:
    subsystem = ChannelSubsystem()
    subsystem.register_driver(_driver("cli", credential_present=True))
    first = subsystem.check_static_readiness(("cli",))
    second = subsystem.check_static_readiness(("cli",))
    assert first.report_id == second.report_id
    assert first.all_ready() is True
