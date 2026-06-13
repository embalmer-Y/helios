"""Tests for the governed OS command-execution channel driver (requirement 86).

All tests are deterministic and SUBPROCESS-FREE: a `FakeCommandRunner` returns canned results keyed by
argv, and the inline executor runs synchronously, so the whole driver path (allowlist, arg-safety,
async accept, result reafference) is exercised without spawning a process or touching the host.
"""

from __future__ import annotations

import json
from pathlib import Path

from helios_v2.channel import (
    CHANNEL_QOS_METADATA_KEY,
    ChannelDriver,
    ChannelSubsystem,
    OutboundPacket,
)
from helios_v2.channel.drivers import (
    CommandAllowRule,
    CommandRunResult,
    FakeCommandRunner,
    OsCommandChannelDriver,
    OsCommandDriverConfig,
)


def _driver(sandbox: Path, runner: FakeCommandRunner | None = None, **config_kwargs) -> OsCommandChannelDriver:
    driver = OsCommandChannelDriver(
        config=OsCommandDriverConfig(sandbox_root=sandbox, **config_kwargs),
        runner=runner if runner is not None else FakeCommandRunner(),
    )
    driver.apply_management_op("connect", None)
    return driver


def _packet(command: str, args: tuple[str, ...] = ()) -> OutboundPacket:
    payload: dict[str, object] = {"command": command}
    if args:
        payload["args"] = list(args)
    return OutboundPacket(
        packet_id=f"out:{command}",
        target_driver_id="os_command",
        op_name="run_command",
        payload=payload,
        provenance={"decision_id": "dec-1", "proposal_id": "prop-1"},
    )


def _drain_one(driver: OsCommandChannelDriver) -> dict:
    result = driver.drain_inbound(budget=16)
    assert len(result.packets) == 1
    return json.loads(result.packets[0].content)


# --- conformance / descriptor / readiness ---------------------------------------------------


def test_driver_conforms_to_channel_driver_protocol(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    assert isinstance(driver, ChannelDriver)
    assert driver.driver_id == "os_command"


def test_descriptor_declares_governed_run_command_op(tmp_path: Path) -> None:
    descriptor = _driver(tmp_path).descriptor()
    assert descriptor.output_ops == ("run_command",)
    assert descriptor.input_packet_types == ("tool_result",)
    spec = descriptor.op_spec("run_command")
    assert spec is not None
    assert spec.required_params == ("command",)
    assert spec.user_visible is False
    assert spec.effect_class == "local_host"
    assert spec.risk_class == "governed"


def test_static_readiness_reflects_sandbox(tmp_path: Path) -> None:
    assert _driver(tmp_path).static_readiness().ready is True
    missing = tmp_path / "nope"
    driver = OsCommandChannelDriver(config=OsCommandDriverConfig(sandbox_root=missing))
    assert driver.static_readiness().ready is False


def test_default_allowlist_tiers(tmp_path: Path) -> None:
    config = OsCommandDriverConfig(sandbox_root=tmp_path)
    # read-only / diagnostic are unrestricted
    assert config.match_rule(("git", "status")).risk_class == "unrestricted"
    assert config.match_rule(("ls", "-la")).risk_class == "unrestricted"
    # sandbox-confined mutations are governed
    assert config.match_rule(("mkdir", "build")).risk_class == "governed"
    assert config.match_rule(("mv", "a", "b")).risk_class == "governed"
    # subcommand granularity: git status allowed, git push not
    assert config.match_rule(("git", "push")) is None
    # interpreters / destructive are not allowlisted at all (restricted by absence)
    assert config.match_rule(("python", "script.py")) is None
    assert config.match_rule(("rm", "-rf", "x")) is None
    assert config.match_rule(("bash", "-c", "x")) is None


# --- execution + result reafference ---------------------------------------------------------


def test_unrestricted_command_executes_with_correlation(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        results={("git", "status"): CommandRunResult(exit_code=0, stdout="clean", stderr="")}
    )
    driver = _driver(tmp_path, runner=runner)
    outcome = driver.send_outbound(_packet("git", ("status",)))
    assert outcome.status == "delivered"
    result = driver.drain_inbound(budget=16)
    packet = result.packets[0]
    body = json.loads(packet.content)
    assert body["ok"] is True
    assert body["op"] == "run_command"
    assert body["command"] == "git"
    assert body["result"]["stdout"] == "clean"
    assert packet.metadata["correlation"]["decision_id"] == "dec-1"
    assert packet.packet_type == "tool_result"
    assert packet.qos_class == "bulk"


def test_governed_command_executes_when_dispatched(tmp_path: Path) -> None:
    # The driver does not gate governance (that is the 13 planner + 14). A governed allowlisted argv
    # that reaches the driver as a bound packet executes; the allowlist check is defense in depth.
    runner = FakeCommandRunner(
        results={("mkdir", "build"): CommandRunResult(exit_code=0, stdout="", stderr="")}
    )
    driver = _driver(tmp_path, runner=runner)
    outcome = driver.send_outbound(_packet("mkdir", ("build",)))
    assert outcome.status == "delivered"
    assert _drain_one(driver)["ok"] is True


def test_non_zero_exit_is_failure_reafference(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        results={("ls", "missing"): CommandRunResult(exit_code=2, stdout="", stderr="No such file")}
    )
    driver = _driver(tmp_path, runner=runner)
    driver.send_outbound(_packet("ls", ("missing",)))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "non_zero_exit"
    assert body["error"]["exit_code"] == 2


def test_timeout_is_failure_reafference(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        results={("ls",): CommandRunResult(exit_code=124, stdout="", stderr="", timed_out=True)}
    )
    driver = _driver(tmp_path, runner=runner)
    driver.send_outbound(_packet("ls"))
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "timeout"


def test_output_truncated_to_max(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        results={("echo", "x"): CommandRunResult(exit_code=0, stdout="A" * 1000, stderr="")}
    )
    driver = _driver(tmp_path, runner=runner, max_output_chars=64)
    driver.send_outbound(_packet("echo", ("x",)))
    result = driver.drain_inbound(budget=16)
    assert len(result.packets[0].content) <= 64


# --- structural rejection / arg-safety / allowlist ------------------------------------------


def test_non_allowlisted_command_rejected_double_writeback(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    outcome = driver.send_outbound(_packet("rm", ("-rf", "x")))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert body["ok"] is False
    assert body["error"]["kind"] == "invalid_request"
    assert "not allowlisted" in body["error"]["detail"]


def test_interpreter_with_script_is_not_allowlisted(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    outcome = driver.send_outbound(_packet("python", ("script.py",)))
    assert outcome.status == "failed"
    assert _drain_one(driver)["ok"] is False


def test_shell_metacharacter_argument_rejected(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    outcome = driver.send_outbound(_packet("echo", ("hi; rm -rf /",)))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert "shell metacharacter" in body["error"]["detail"]


def test_absolute_path_argument_rejected(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    outcome = driver.send_outbound(_packet("cat", ("/etc/passwd",)))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert "absolute path" in body["error"]["detail"]


def test_parent_traversal_argument_rejected(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    outcome = driver.send_outbound(_packet("cat", ("../secret.txt",)))
    assert outcome.status == "failed"
    body = _drain_one(driver)
    assert "parent traversal" in body["error"]["detail"]


def test_unknown_op_rejected(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    bad = OutboundPacket(
        packet_id="out:bad",
        target_driver_id="os_command",
        op_name="teleport",
        payload={"command": "ls"},
    )
    outcome = driver.send_outbound(bad)
    assert outcome.status == "failed"
    assert _drain_one(driver)["ok"] is False


def test_missing_command_rejected(tmp_path: Path) -> None:
    driver = _driver(tmp_path)
    bad = OutboundPacket(
        packet_id="out:nocmd",
        target_driver_id="os_command",
        op_name="run_command",
        payload={},
    )
    outcome = driver.send_outbound(bad)
    assert outcome.status == "failed"
    assert _drain_one(driver)["ok"] is False


def test_send_while_disconnected_is_failure(tmp_path: Path) -> None:
    driver = OsCommandChannelDriver(config=OsCommandDriverConfig(sandbox_root=tmp_path))
    outcome = driver.send_outbound(_packet("ls"))
    assert outcome.status == "failed"
    assert _drain_one(driver)["error"]["kind"] == "not_connected"


# --- backlog overflow + subsystem integration -----------------------------------------------


def test_backlog_overflow_bounded_and_counted(tmp_path: Path) -> None:
    driver = _driver(tmp_path, max_backlog=2)
    for _ in range(4):
        driver.send_outbound(_packet("ls"))
    result = driver.drain_inbound(budget=16)
    assert len(result.packets) == 2
    assert result.overflow_count == 2


def test_result_drains_through_subsystem_as_raw_signal(tmp_path: Path) -> None:
    runner = FakeCommandRunner(
        results={("git", "status"): CommandRunResult(exit_code=0, stdout="ok", stderr="")}
    )
    subsystem = ChannelSubsystem()
    driver = _driver(tmp_path, runner=runner)
    subsystem.register_driver(driver)
    subsystem.dispatch_outbound((_packet("git", ("status",)),), budget=16)
    drain = subsystem.drain_inbound(budget=16)
    assert drain.drained_count == 1
    signal = drain.raw_signals[0]
    assert signal.source_name == "os_command"
    assert signal.signal_type == "tool_result"
    assert signal.metadata[CHANNEL_QOS_METADATA_KEY] == "bulk"
    assert json.loads(signal.content)["ok"] is True


def test_custom_allowlist_overrides_default(tmp_path: Path) -> None:
    runner = FakeCommandRunner(results={("whoami",): CommandRunResult(exit_code=0, stdout="me", stderr="")})
    driver = _driver(
        tmp_path,
        runner=runner,
        allowlist=(CommandAllowRule(("whoami",)),),
    )
    driver.send_outbound(_packet("whoami"))
    assert _drain_one(driver)["ok"] is True
    # ls is no longer allowlisted under the custom allowlist
    outcome = driver.send_outbound(_packet("ls"))
    assert outcome.status == "failed"
    assert _drain_one(driver)["ok"] is False
