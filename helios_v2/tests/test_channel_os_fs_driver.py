"""Tests for the sandboxed OS file-system channel driver (requirement 84).

All tests are deterministic and network-free. The default executor is the inline (synchronous)
executor, so a `send_outbound` leaves the result already enqueued and the next `drain_inbound`
returns it with no threads and no races. One test exercises the real thread-pool executor for
concurrency.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from helios_v2.channel import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelDriver,
    ChannelSubsystem,
    OutboundPacket,
)
from helios_v2.channel.drivers import (
    OsFileSystemChannelDriver,
    OsFileSystemDriverConfig,
    ThreadPoolFileOpExecutor,
)


def _connected_driver(sandbox: Path, **config_kwargs) -> OsFileSystemChannelDriver:
    driver = OsFileSystemChannelDriver(
        config=OsFileSystemDriverConfig(sandbox_root=sandbox, **config_kwargs)
    )
    driver.apply_management_op("connect", None)
    return driver


def _packet(op_name: str, **payload) -> OutboundPacket:
    return OutboundPacket(
        packet_id=f"out:{op_name}",
        target_driver_id="os_fs",
        op_name=op_name,
        payload=payload,
        provenance={"decision_id": "dec-1", "proposal_id": "prop-1"},
    )


def _drain_one(driver: OsFileSystemChannelDriver) -> dict:
    result = driver.drain_inbound(budget=16)
    assert len(result.packets) == 1
    return json.loads(result.packets[0].content)


# --- conformance / descriptor / readiness ---------------------------------------------------


def test_driver_conforms_to_channel_driver_protocol(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path)
    assert isinstance(driver, ChannelDriver)
    assert driver.driver_id == "os_fs"


def test_descriptor_declares_effector_capabilities(tmp_path: Path) -> None:
    descriptor = _connected_driver(tmp_path).descriptor()
    assert descriptor.directions == ("inbound", "outbound")
    assert descriptor.output_ops == ("fs_read", "fs_write", "fs_list", "fs_modify")
    assert descriptor.input_packet_types == ("tool_result",)
    assert "connect" in descriptor.management_ops


def test_static_readiness_ready_when_sandbox_exists(tmp_path: Path) -> None:
    readiness = _connected_driver(tmp_path).static_readiness()
    assert readiness.ready is True


def test_static_readiness_not_ready_when_sandbox_missing(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    driver = OsFileSystemChannelDriver(config=OsFileSystemDriverConfig(sandbox_root=missing))
    readiness = driver.static_readiness()
    assert readiness.ready is False


# --- core ops + result reafference ----------------------------------------------------------


def test_write_then_read_round_trip_with_correlation(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path)

    write_outcome = driver.send_outbound(_packet("fs_write", path="notes/a.txt", content="hello"))
    assert write_outcome.status == "delivered"
    write_result = _drain_one(driver)
    assert write_result["ok"] is True
    assert write_result["op"] == "fs_write"
    assert (tmp_path / "notes" / "a.txt").read_text(encoding="utf-8") == "hello"

    read_outcome = driver.send_outbound(_packet("fs_read", path="notes/a.txt"))
    assert read_outcome.status == "delivered"
    read_drain = driver.drain_inbound(budget=16)
    packet = read_drain.packets[0]
    body = json.loads(packet.content)
    assert body["ok"] is True
    assert body["result"]["content"] == "hello"
    # Correlation provenance flows back with the result reafference.
    assert packet.metadata["correlation"]["decision_id"] == "dec-1"
    assert packet.metadata["op"] == "fs_read"
    assert packet.packet_type == "tool_result"
    assert packet.qos_class == "bulk"


def test_fs_list_returns_entries(tmp_path: Path) -> None:
    (tmp_path / "f1.txt").write_text("x", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    driver = _connected_driver(tmp_path)
    driver.send_outbound(_packet("fs_list", path="."))
    body = _drain_one(driver)
    names = {e["name"]: e["kind"] for e in body["result"]["entries"]}
    assert names == {"f1.txt": "file", "sub": "dir"}


def test_fs_modify_appends_to_existing_file(tmp_path: Path) -> None:
    (tmp_path / "log.txt").write_text("a", encoding="utf-8")
    driver = _connected_driver(tmp_path)
    driver.send_outbound(_packet("fs_modify", path="log.txt", content="b"))
    body = _drain_one(driver)
    assert body["ok"] is True
    assert (tmp_path / "log.txt").read_text(encoding="utf-8") == "ab"


def test_fs_modify_missing_file_is_failure_reafference(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path)
    driver.send_outbound(_packet("fs_modify", path="nope.txt", content="b"))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "not_found"


def test_read_truncates_to_max_read_bytes(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("0123456789", encoding="utf-8")
    driver = _connected_driver(tmp_path, max_read_bytes=4)
    driver.send_outbound(_packet("fs_read", path="big.txt"))
    body = _drain_one(driver)
    assert body["result"]["content"] == "0123"
    assert body["result"]["truncated"] is True
    assert body["result"]["size_bytes"] == 10


# --- sandbox escape + write gating + structural rejection -----------------------------------


def test_relative_path_escape_is_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("classified", encoding="utf-8")
    driver = _connected_driver(sandbox)
    driver.send_outbound(_packet("fs_read", path="../secret.txt"))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "path_escape"


def test_absolute_outside_path_is_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("classified", encoding="utf-8")
    driver = _connected_driver(sandbox)
    driver.send_outbound(_packet("fs_read", path=str(outside)))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "path_escape"


def test_write_escape_does_not_touch_outside_file(tmp_path: Path) -> None:
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    driver = _connected_driver(sandbox)
    driver.send_outbound(_packet("fs_write", path="../escaped.txt", content="x"))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert not (tmp_path / "escaped.txt").exists()


def test_symlink_escape_is_rejected(tmp_path: Path) -> None:
    sandbox = tmp_path / "box"
    sandbox.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    link = sandbox / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform/privilege level")
    driver = _connected_driver(sandbox)
    driver.send_outbound(_packet("fs_read", path="link.txt"))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "path_escape"


def test_write_disabled_is_rejected_with_double_writeback(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path, allow_write=False)
    outcome = driver.send_outbound(_packet("fs_write", path="a.txt", content="x"))
    assert outcome.status == "failed"
    body = _drain_one(driver)  # failure also enqueued as reafference
    assert body["ok"] is False
    assert body["error"]["kind"] == "invalid_request"
    assert not (tmp_path / "a.txt").exists()


def test_unknown_op_structural_rejection_double_writeback(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path)
    outcome = driver.send_outbound(_packet("fs_teleport", path="a.txt"))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "invalid_request"


def test_missing_required_param_rejected(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path)
    outcome = driver.send_outbound(_packet("fs_read"))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert body["ok"] is False


def test_send_while_disconnected_is_failure(tmp_path: Path) -> None:
    driver = OsFileSystemChannelDriver(config=OsFileSystemDriverConfig(sandbox_root=tmp_path))
    outcome = driver.send_outbound(_packet("fs_read", path="a.txt"))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert body["error"]["kind"] == "not_connected"


# --- backlog overflow + concurrency ---------------------------------------------------------


def test_backlog_overflow_is_bounded_and_counted(tmp_path: Path) -> None:
    driver = _connected_driver(tmp_path, max_backlog=2)
    for i in range(4):
        driver.send_outbound(_packet("fs_list", path="."))
    result = driver.drain_inbound(budget=16)
    assert len(result.packets) == 2
    assert result.overflow_count == 2


def test_thread_pool_executor_is_race_free(tmp_path: Path) -> None:
    driver = OsFileSystemChannelDriver(
        config=OsFileSystemDriverConfig(sandbox_root=tmp_path, max_backlog=256),
        executor=ThreadPoolFileOpExecutor(max_workers=8),
    )
    driver.apply_management_op("connect", None)
    submitted = 50
    for i in range(submitted):
        driver.send_outbound(_packet("fs_write", path=f"f{i}.txt", content=str(i)))

    drained: list = []
    # Drain until quiescent (all worker results enqueued and consumed).
    for _ in range(200):
        result = driver.drain_inbound(budget=256)
        drained.extend(result.packets)
        if len(drained) >= submitted and result.pending_remaining == 0:
            break
        time.sleep(0.01)
    assert len(drained) == submitted
    assert all(json.loads(p.content)["ok"] for p in drained)
    assert sorted((tmp_path / f"f{i}.txt").read_text(encoding="utf-8") for i in range(submitted)) == sorted(
        str(i) for i in range(submitted)
    )


# --- subsystem integration ------------------------------------------------------------------


def test_result_drains_through_subsystem_as_raw_signal(tmp_path: Path) -> None:
    subsystem = ChannelSubsystem()
    driver = _connected_driver(tmp_path)
    subsystem.register_driver(driver)
    subsystem.dispatch_outbound((_packet("fs_write", path="a.txt", content="hi"),), budget=16)
    drain = subsystem.drain_inbound(budget=16)
    assert drain.drained_count == 1
    signal = drain.raw_signals[0]
    assert signal.source_name == "os_fs"
    assert signal.signal_type == "tool_result"
    assert signal.metadata[CHANNEL_QOS_METADATA_KEY] == "bulk"
    body = json.loads(signal.content)
    assert body["ok"] is True
    assert body["op"] == "fs_write"
