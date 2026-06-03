"""Tests for the local CLI channel driver (requirement 31).

All tests are deterministic and network-free, using injected in-memory input/output.
"""

from __future__ import annotations

import pytest

from helios_v2.channel import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelDriver,
    ChannelSubsystem,
    CliChannelDriver,
    CliDriverConfig,
    OutboundPacket,
)


def _driver(**kwargs) -> tuple[CliChannelDriver, list[str]]:
    sink: list[str] = []
    driver = CliChannelDriver(output_sink=sink.append, config=CliDriverConfig(**kwargs))
    return driver, sink


def test_cli_driver_conforms_to_channel_driver_protocol() -> None:
    driver, _ = _driver()
    assert isinstance(driver, ChannelDriver)
    assert driver.driver_id == "cli"


def test_descriptor_declares_real_capabilities() -> None:
    driver, _ = _driver()
    descriptor = driver.descriptor()
    assert descriptor.directions == ("inbound", "outbound")
    assert "text" in descriptor.input_packet_types
    assert "reply_message" in descriptor.output_ops
    assert "connect" in descriptor.management_ops
    assert descriptor.supports_direction("inbound")
    assert descriptor.supports_direction("outbound")


def test_static_readiness_always_ready() -> None:
    driver, _ = _driver()
    readiness = driver.static_readiness()
    assert readiness.ready is True


def test_submit_and_drain_yields_qos_tagged_packets() -> None:
    driver, _ = _driver()
    driver.submit_line("hello helios")
    result = driver.drain_inbound(budget=10)
    assert len(result.packets) == 1
    packet = result.packets[0]
    assert packet.driver_id == "cli"
    assert packet.packet_type == "text"
    assert packet.content == "hello helios"
    assert packet.qos_class == "interactive"
    assert result.pending_remaining == 0


def test_drain_skips_empty_lines() -> None:
    driver, _ = _driver()
    driver.submit_line("   ")
    driver.submit_line("real line")
    result = driver.drain_inbound(budget=10)
    assert [p.content for p in result.packets] == ["real line"]


def test_drain_is_bounded_by_budget() -> None:
    driver, _ = _driver()
    for i in range(5):
        driver.submit_line(f"line-{i}")
    first = driver.drain_inbound(budget=2)
    assert len(first.packets) == 2
    assert first.pending_remaining == 3


def test_backlog_overflow_is_bounded_and_counted() -> None:
    driver, _ = _driver(max_backlog=2)
    assert driver.submit_line("a") is True
    assert driver.submit_line("b") is True
    assert driver.submit_line("c") is False  # overflow
    result = driver.drain_inbound(budget=10)
    assert len(result.packets) == 2
    assert result.overflow_count == 1


def test_send_outbound_writes_to_sink_when_connected() -> None:
    driver, sink = _driver()
    driver.apply_management_op("connect", None)
    packet = OutboundPacket(
        packet_id="o1",
        target_driver_id="cli",
        op_name="reply_message",
        payload={"outbound_text": "hi there"},
    )
    outcome = driver.send_outbound(packet)
    assert outcome.status == "delivered"
    assert sink == ["[operator] hi there"]


def test_send_outbound_without_banner() -> None:
    driver, sink = _driver(banner_enabled=False)
    driver.apply_management_op("connect", None)
    packet = OutboundPacket(
        packet_id="o1",
        target_driver_id="cli",
        op_name="reply_message",
        payload={"outbound_text": "plain"},
    )
    driver.send_outbound(packet)
    assert sink == ["plain"]


def test_send_outbound_while_disconnected_returns_non_delivered() -> None:
    driver, sink = _driver()
    # default status is uninitialized (not connected)
    packet = OutboundPacket(
        packet_id="o1",
        target_driver_id="cli",
        op_name="reply_message",
        payload={"outbound_text": "hi"},
    )
    outcome = driver.send_outbound(packet)
    assert outcome.status == "failed"
    assert sink == []


def test_send_outbound_missing_text_returns_failed() -> None:
    driver, sink = _driver()
    driver.apply_management_op("connect", None)
    packet = OutboundPacket(packet_id="o1", target_driver_id="cli", op_name="reply_message")
    outcome = driver.send_outbound(packet)
    assert outcome.status == "failed"
    assert sink == []


def test_lifecycle_ops_transition_status() -> None:
    driver, _ = _driver()
    assert driver.status().status == "uninitialized"
    driver.apply_management_op("init", None)
    assert driver.status().status == "disconnected"
    driver.apply_management_op("connect", None)
    assert driver.status().connected is True
    driver.apply_management_op("pause", None)
    assert driver.status().status == "paused"
    driver.apply_management_op("resume", None)
    assert driver.status().status == "connected"
    driver.apply_management_op("disconnect", None)
    assert driver.status().status == "disconnected"


def test_unsupported_management_op_is_explicit_failure() -> None:
    driver, _ = _driver()
    result = driver.apply_management_op("warp_drive", None)
    assert result.success is False
    assert result.error_code == "unsupported_op"


def test_update_config_validates_mutable_fields() -> None:
    driver, _ = _driver()
    ok = driver.apply_management_op("update_config", {"user_label": "alice"})
    assert ok.success is True
    assert driver.config.user_label == "alice"

    rejected = driver.apply_management_op("update_config", {"max_backlog": 999})
    assert rejected.success is False
    assert rejected.error_code == "invalid_config_field"


def test_update_config_empty_payload_rejected() -> None:
    driver, _ = _driver()
    result = driver.apply_management_op("update_config", None)
    assert result.success is False
    assert result.error_code == "missing_payload"


def test_driver_works_through_subsystem_drain_with_qos_marker() -> None:
    subsystem = ChannelSubsystem()
    driver, _ = _driver()
    subsystem.register_driver(driver)
    driver.submit_line("via subsystem")
    drain = subsystem.drain_inbound(budget=10)
    assert drain.drained_count == 1
    signal = drain.raw_signals[0]
    assert signal.content == "via subsystem"
    assert signal.metadata[CHANNEL_QOS_METADATA_KEY] == "interactive"
    assert signal.source_name == "cli"
