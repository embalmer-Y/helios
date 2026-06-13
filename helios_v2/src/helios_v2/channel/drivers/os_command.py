"""Owner: channel driver subsystem (governed OS command-execution effector driver).

A sandboxed OS command-execution `ChannelDriver` (requirement `86`). Like the `84` `os_fs` effector it
performs a real host action and feeds the RESULT back into `02` sensory as a `tool_result` stimulus, but
its action is running a process (`run_command`) instead of a file operation. It is GOVERNED: it executes
only an argv matched by its declarative default-deny allowlist, no-shell (argv list, never a shell
string), confined to a sandbox cwd, under a wall-clock timeout with bounded captured output, and it
never executes an interpreter / recursive-destructive / privileged / networked / repo-write command
(those are simply not allowlisted). The `governed` allowlist tier (sandbox-confined bounded mutations
like ``mkdir``/``cp``/``mv``) is authorized by the `14` owner through the `13` planner's enforced
risk-class gate before a binding ever reaches this driver; the driver's allowlist check is defense in
depth.

Boundary: transport/effector only. It does not normalize into stimuli, score salience, re-select
channels, shape outward content, interpret a result's meaning, decide authorization (that is `14`), or
enforce the risk-class gate (that is `13`). Two injected seams keep it testable and network-free in CI:
a `CommandExecutor` (the threading seam, inline for tests / thread-pool for production) and a
`CommandRunner` (the subprocess seam, a fake canned runner for tests / real ``subprocess`` for
production).
"""

from __future__ import annotations

import json
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol, runtime_checkable

from ..contracts import (
    ChannelCommandRule,
    ChannelConfigField,
    ChannelConfigSnapshot,
    ChannelDriver,
    ChannelDriverDescriptor,
    ChannelDriverReadiness,
    ChannelDriverStatus,
    ChannelDriverStatusReport,
    ChannelError,
    ChannelManagementResult,
    ChannelOpSpec,
    InboundDrainResult,
    InboundPacket,
    OpRiskClass,
    OutboundDispatchOutcome,
    OutboundPacket,
)

OS_COMMAND_DRIVER_ID = "os_command"
TOOL_RESULT_PACKET_TYPE = "tool_result"
RUN_COMMAND = "run_command"

# Command results are local data payloads; QoS is transport-intrinsic (`bulk`), set without reading the
# result content for meaning, consistent with `30` (only `03` appraisal reads QoS as a salience input).
_TOOL_RESULT_QOS_CLASS = "bulk"

# Shell metacharacters rejected in any argv token. The driver runs no shell, so these can only be an
# injection attempt or a malformed request; they are never interpreted.
_SHELL_METACHARACTERS = frozenset("|&;<>$`(){}*?\n\r")

_LIFECYCLE_TRANSITIONS: dict[str, ChannelDriverStatus] = {
    "init": "disconnected",
    "connect": "connected",
    "disconnect": "disconnected",
    "deinit": "uninitialized",
    "pause": "paused",
    "resume": "connected",
    "teardown": "disconnected",
}


@dataclass(frozen=True)
class CommandAllowRule:
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        One default-deny allow rule: a request's full argv (`[command, *args]`) must START WITH
        `argv_prefix` to match, and the rule's `risk_class` then applies. A driver never declares a
        `restricted` rule - "restricted" is the absence of any matching rule.

    Failure semantics:
        Construction raises `ChannelError` on an empty prefix, an empty prefix token, or a `restricted`
        risk class.
    """

    argv_prefix: tuple[str, ...]
    risk_class: OpRiskClass = "unrestricted"

    def __post_init__(self) -> None:
        if not self.argv_prefix:
            raise ChannelError("CommandAllowRule must declare a non-empty argv_prefix")
        for token in self.argv_prefix:
            if not token:
                raise ChannelError("CommandAllowRule argv_prefix must not contain empty tokens")
        if self.risk_class not in ("unrestricted", "governed"):
            raise ChannelError("CommandAllowRule risk_class must be 'unrestricted' or 'governed'")

    def matches(self, argv: tuple[str, ...]) -> bool:
        """Owner: channel driver subsystem. Report whether `argv` starts with this rule's prefix."""

        if len(argv) < len(self.argv_prefix):
            return False
        return tuple(argv[: len(self.argv_prefix)]) == self.argv_prefix


# First-version allowlist. `unrestricted` = read-only / diagnostic (auto-allowed). `governed` =
# sandbox-confined bounded mutation (requires `14` authorization through the `13` gate). No interpreter
# (python <script>/bash/sh/node/pytest), recursive/destructive (rm -rf), privileged (sudo), networked
# (curl/wget), package-installing (pip/npm), or repo-write (git add/commit) command is allowlisted; those
# are restricted by being absent.
DEFAULT_COMMAND_ALLOWLIST: tuple[CommandAllowRule, ...] = (
    CommandAllowRule(("ls",)),
    CommandAllowRule(("dir",)),
    CommandAllowRule(("cat",)),
    CommandAllowRule(("type",)),
    CommandAllowRule(("echo",)),
    CommandAllowRule(("git", "status")),
    CommandAllowRule(("git", "diff")),
    CommandAllowRule(("git", "log")),
    CommandAllowRule(("python", "--version")),
    CommandAllowRule(("python", "-V")),
    CommandAllowRule(("mkdir",), risk_class="governed"),
    CommandAllowRule(("cp",), risk_class="governed"),
    CommandAllowRule(("mv",), risk_class="governed"),
)


@dataclass(frozen=True)
class CommandRunResult:
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        The transport-level outcome of actually running one command: the process exit code, captured
        stdout/stderr, and whether it timed out. Carries no meaning interpretation.
    """

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


@runtime_checkable
class CommandRunner(Protocol):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        The injected subprocess seam. The driver hands an already-allowlisted, arg-safe argv plus the
        sandbox cwd and timeout; the runner actually executes it (or, in tests, returns a deterministic
        canned result). The driver owns neither the subprocess policy nor any shell.
    """

    def run(self, argv: tuple[str, ...], cwd: str, timeout_seconds: float) -> CommandRunResult:
        """Run `argv` no-shell in `cwd` under `timeout_seconds`; return the structured result."""

        ...


@dataclass
class FakeCommandRunner(CommandRunner):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        Deterministic, subprocess-free runner for tests/CI/long-run: returns a canned `CommandRunResult`
        keyed by the exact argv (else a default success), so the whole driver path is exercised without
        spawning a process or touching the host.
    """

    results: Mapping[tuple[str, ...], CommandRunResult] = field(default_factory=dict)
    default_result: CommandRunResult = field(
        default_factory=lambda: CommandRunResult(exit_code=0, stdout="", stderr="")
    )

    def run(self, argv: tuple[str, ...], cwd: str, timeout_seconds: float) -> CommandRunResult:
        del cwd, timeout_seconds
        return self.results.get(tuple(argv), self.default_result)


@dataclass
class SubprocessCommandRunner(CommandRunner):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        Production runner: executes the argv with the standard library `subprocess` no-shell
        (`shell=False`), confined to the sandbox cwd, under a wall-clock timeout, capturing bounded text
        output. Never invokes a shell and never enables the network itself.

    Failure semantics:
        A timeout returns `timed_out=True` with a non-zero exit code; a spawn failure propagates as
        `OSError` for the driver's `_execute` to turn into a failure reafference.
    """

    def run(self, argv: tuple[str, ...], cwd: str, timeout_seconds: float) -> CommandRunResult:
        import subprocess

        try:
            completed = subprocess.run(  # noqa: S603 - no-shell, allowlisted argv, sandbox cwd
                list(argv),
                cwd=cwd,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            return CommandRunResult(exit_code=124, stdout=stdout, stderr=stderr, timed_out=True)
        return CommandRunResult(
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


@runtime_checkable
class CommandExecutor(Protocol):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        The injected asynchronous-execution (threading) seam, mirroring the `84` `FileOpExecutor`: the
        driver submits one fire-and-forget unit of work per accepted command; the implementation decides
        inline (tests) or worker-thread (production) execution.
    """

    def submit(self, work: Callable[[], None]) -> None:
        """Submit one unit of work for execution (fire-and-forget)."""

        ...


@dataclass
class InlineCommandExecutor(CommandExecutor):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        Deterministic, race-free executor for tests/CI/long-run: runs the work synchronously on submit,
        so a `send_outbound` leaves the result already enqueued for the next `drain_inbound`.
    """

    def submit(self, work: Callable[[], None]) -> None:
        work()


@dataclass
class ThreadPoolCommandExecutor(CommandExecutor):
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        Production executor: submits work to a bounded `ThreadPoolExecutor` for true asynchronous
        execution, so a slow/timed-out command enqueues its result whenever it finishes without blocking
        the runtime tick.

    Failure semantics:
        Construction raises `ChannelError` on a non-positive worker count.
    """

    max_workers: int = 4
    _pool: ThreadPoolExecutor = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers <= 0:
            raise ChannelError("ThreadPoolCommandExecutor max_workers must be a positive integer")
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="helios-os-command"
        )

    def submit(self, work: Callable[[], None]) -> None:
        self._pool.submit(work)

    def shutdown(self) -> None:
        """Owner: channel driver subsystem. Shut the pool down (production teardown only)."""

        self._pool.shutdown(wait=False, cancel_futures=True)


@dataclass(frozen=True)
class OsCommandDriverConfig:
    """Owner: channel driver subsystem (OS command driver).

    Purpose:
        Declare the command driver's local configuration: the sandbox cwd all commands run in, the
        default-deny allowlist, the wall-clock timeout, and the bounded output/backlog caps.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id, an empty allowlist, or any
        non-positive bound.

    Notes:
        `sandbox_root_resolved` is the resolved sandbox cwd, computed once at construction.
    """

    sandbox_root: object
    driver_id: str = OS_COMMAND_DRIVER_ID
    allowlist: tuple[CommandAllowRule, ...] = DEFAULT_COMMAND_ALLOWLIST
    timeout_seconds: float = 10.0
    max_output_chars: int = 8192
    max_backlog: int = 128
    sandbox_root_resolved: object = field(init=False)

    def __post_init__(self) -> None:
        from pathlib import Path

        if not self.driver_id:
            raise ChannelError("OsCommandDriverConfig must declare a non-empty driver_id")
        if not self.allowlist:
            raise ChannelError("OsCommandDriverConfig must declare a non-empty allowlist")
        if self.timeout_seconds <= 0:
            raise ChannelError("OsCommandDriverConfig timeout_seconds must be positive")
        if self.max_output_chars <= 0:
            raise ChannelError("OsCommandDriverConfig max_output_chars must be a positive integer")
        if self.max_backlog <= 0:
            raise ChannelError("OsCommandDriverConfig max_backlog must be a positive integer")
        object.__setattr__(self, "sandbox_root", Path(self.sandbox_root))
        object.__setattr__(self, "sandbox_root_resolved", Path(self.sandbox_root).resolve())

    def match_rule(self, argv: tuple[str, ...]) -> CommandAllowRule | None:
        """Owner: channel driver subsystem.

        Return the first allow rule whose prefix matches `argv`, or `None` (denied) when none matches.
        """

        for rule in self.allowlist:
            if rule.matches(argv):
                return rule
        return None


def _os_command_descriptor(config: OsCommandDriverConfig) -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        driver_id=config.driver_id,
        display_name="Sandboxed OS Command-Execution Channel",
        directions=("inbound", "outbound"),
        input_packet_types=(TOOL_RESULT_PACKET_TYPE,),
        output_ops=(RUN_COMMAND,),
        management_ops=(
            "init",
            "connect",
            "disconnect",
            "deinit",
            "pause",
            "resume",
            "health_check",
            "get_config",
        ),
        config_fields=(
            ChannelConfigField(
                key="sandbox_root",
                description="absolute working directory all commands run in",
                required=True,
                mutable_at_runtime=False,
                schema_hint="path",
            ),
            ChannelConfigField(
                key="timeout_seconds",
                description="per-command wall-clock timeout",
                required=False,
                mutable_at_runtime=False,
                schema_hint="float",
            ),
            ChannelConfigField(
                key="max_output_chars",
                description="maximum characters in a tool_result payload",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
            ChannelConfigField(
                key="max_backlog",
                description="bounded inbound (result) backlog capacity",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
        ),
        health_signals=("pending_inbound", "overflow_count"),
        output_op_specs=(
            ChannelOpSpec(
                op_name=RUN_COMMAND,
                required_params=("command",),
                user_visible=False,
                effect_class="local_host",
                risk_class="governed",
            ),
        ),
        command_invocation_policy=tuple(
            ChannelCommandRule(argv_prefix=rule.argv_prefix, risk_class=rule.risk_class)
            for rule in config.allowlist
        ),
    )


@dataclass
class OsCommandChannelDriver(ChannelDriver):
    """Owner: channel driver subsystem (governed OS command-execution effector driver).

    Purpose:
        Accept a planner-accepted, `14`-authorized (for the governed tier) `run_command` op as an
        outbound packet, execute it asynchronously no-shell inside the sandbox through an injected
        executor + runner, and feed the result (success or failure) back into its bounded inbound backlog
        as a `tool_result` packet carrying correlation provenance.

    Failure semantics:
        A structurally invalid / non-allowlisted / unsafe-arg packet returns a failed dispatch outcome
        AND enqueues a failure reafference (double write-back). An execution failure (non-zero exit,
        timeout, spawn error) enqueues a failure reafference only. A failure is never reported as a
        success and the driver never falls back to a different command. Backlog overflow is bounded and
        counted, never raised.

    Notes:
        The backlog is lock-guarded because production execution runs on a worker thread while the tick
        thread drains on the main thread.
    """

    config: OsCommandDriverConfig
    executor: CommandExecutor = field(default_factory=InlineCommandExecutor)
    runner: CommandRunner = field(default_factory=SubprocessCommandRunner)
    _status: ChannelDriverStatus = field(default="uninitialized", init=False)
    _backlog: deque[InboundPacket] = field(default_factory=deque, init=False)
    _overflow_count: int = field(default=0, init=False)
    _result_seq: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def driver_id(self) -> str:
        return self.config.driver_id

    def descriptor(self) -> ChannelDriverDescriptor:
        return _os_command_descriptor(self.config)

    def apply_management_op(
        self,
        op_name: str,
        payload: Mapping[str, object] | None,
    ) -> ChannelManagementResult:
        if op_name == "health_check":
            with self._lock:
                pending = len(self._backlog)
                overflow = self._overflow_count
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message="os_command driver healthy",
                payload={"pending_inbound": pending, "overflow_count": overflow},
            )
        if op_name == "get_config":
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message="os_command driver config",
                payload=self._config_values(),
            )
        if op_name in _LIFECYCLE_TRANSITIONS:
            self._status = _LIFECYCLE_TRANSITIONS[op_name]
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message=f"os_command driver applied '{op_name}'",
            )
        return ChannelManagementResult(
            driver_id=self.driver_id,
            op_name=op_name,
            success=False,
            status=self._status,
            message=f"unsupported os_command management op '{op_name}'",
            error_code="unsupported_op",
        )

    def status(self) -> ChannelDriverStatusReport:
        with self._lock:
            pending = len(self._backlog)
            overflow = self._overflow_count
        return ChannelDriverStatusReport(
            driver_id=self.driver_id,
            status=self._status,
            connected=self._status == "connected",
            pending_inbound=pending,
            health={"overflow_count": overflow},
        )

    def config_snapshot(self) -> ChannelConfigSnapshot:
        return ChannelConfigSnapshot(
            driver_id=self.driver_id,
            status=self._status,
            config_values=self._config_values(),
            mutable_fields=(),
        )

    def _config_values(self) -> dict[str, object]:
        return {
            "sandbox_root": str(self.config.sandbox_root_resolved),
            "timeout_seconds": self.config.timeout_seconds,
            "max_output_chars": self.config.max_output_chars,
            "max_backlog": self.config.max_backlog,
            "allowlisted_prefixes": tuple(" ".join(rule.argv_prefix) for rule in self.config.allowlist),
        }

    def static_readiness(self) -> ChannelDriverReadiness:
        # Network-free, deterministic: ready iff the sandbox cwd exists as a directory. The driver never
        # creates the root to appear ready (no degraded path).
        if self.config.sandbox_root_resolved.is_dir():
            return ChannelDriverReadiness(
                driver_id=self.driver_id,
                ready=True,
                detail=f"sandbox root present: {self.config.sandbox_root_resolved}",
            )
        return ChannelDriverReadiness(
            driver_id=self.driver_id,
            ready=False,
            detail=f"sandbox root missing or not a directory: {self.config.sandbox_root_resolved}",
        )

    def send_outbound(self, packet: OutboundPacket) -> OutboundDispatchOutcome:
        """Accept one planner-accepted command for asynchronous no-shell execution.

        Returns a `delivered` outcome meaning "accepted for execution" (not "completed"); the command's
        success/failure is reported only through the result reafference. A structurally invalid /
        non-allowlisted / unsafe-arg packet returns a `failed` outcome and also enqueues a failure
        reafference.
        """

        correlation = self._correlation(packet)
        command = str(packet.payload.get("command", ""))
        if self._status != "connected":
            self._enqueue_result(
                command=command,
                ok=False,
                body={"kind": "not_connected", "detail": f"driver status={self._status}"},
                is_error=True,
                correlation=correlation,
            )
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail=f"os_command driver not connected (status={self._status})",
            )

        rejection = self._structural_rejection(packet)
        if rejection is not None:
            self._enqueue_result(
                command=command,
                ok=False,
                body={"kind": "invalid_request", "detail": rejection},
                is_error=True,
                correlation=correlation,
            )
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail=rejection,
            )

        argv = self._argv(packet.payload)

        def work() -> None:
            self._execute(argv, correlation)

        self.executor.submit(work)
        return OutboundDispatchOutcome(
            packet_id=packet.packet_id,
            target_driver_id=self.driver_id,
            status="delivered",
            detail=f"accepted command '{' '.join(argv)}' for async execution",
        )

    def _argv(self, payload: Mapping[str, object]) -> tuple[str, ...]:
        command = str(payload.get("command", ""))
        raw_args = payload.get("args", ())
        args: tuple[str, ...]
        if isinstance(raw_args, (list, tuple)):
            args = tuple(str(item) for item in raw_args)
        else:
            args = ()
        return (command, *args)

    def _structural_rejection(self, packet: OutboundPacket) -> str | None:
        if packet.op_name != RUN_COMMAND:
            return f"unsupported os_command op '{packet.op_name}'"
        command = packet.payload.get("command")
        if not isinstance(command, str) or not command:
            return "op 'run_command' requires a non-empty string 'command'"
        raw_args = packet.payload.get("args", ())
        if not isinstance(raw_args, (list, tuple)):
            return "op 'run_command' 'args' must be a list of strings when provided"
        for item in raw_args:
            if not isinstance(item, str):
                return "op 'run_command' 'args' must contain only string values"
        argv = self._argv(packet.payload)
        if self.config.match_rule(argv) is None:
            return f"command not allowlisted: '{' '.join(argv)}'"  # command_not_allowlisted
        unsafe = self._unsafe_token(argv)
        if unsafe is not None:
            return unsafe
        return None

    def _unsafe_token(self, argv: tuple[str, ...]) -> str | None:
        """Owner: channel driver subsystem.

        Reject any argv token carrying a shell metacharacter (no shell is used, so it can only be an
        injection attempt), or any token that is an absolute path or contains a `..` traversal. The
        sandbox cwd lies outside the repository source tree, so rejecting absolute and `..` arguments
        confines every relative path argument to the sandbox and structurally prevents writing the
        Helios source/requirement tree.
        """

        for token in argv:
            if any(char in _SHELL_METACHARACTERS for char in token):
                return f"unsafe argument (shell metacharacter): '{token}'"  # unsafe_argument
            if ".." in token.replace("\\", "/").split("/"):
                return f"unsafe path argument (parent traversal): '{token}'"  # unsafe_path_argument
            if token.startswith("/") or token.startswith("\\") or (len(token) >= 2 and token[1] == ":"):
                return f"unsafe path argument (absolute path): '{token}'"  # unsafe_path_argument
        return None

    def _execute(self, argv: tuple[str, ...], correlation: Mapping[str, object]) -> None:
        """Run one command through the injected runner and enqueue exactly one result reafference.

        Runs on the executor thread (or inline in tests). Every exception is caught and turned into a
        failure result so no exception escapes the worker thread and every command yields exactly one
        reafference.
        """

        command = argv[0] if argv else ""
        try:
            run_result = self.runner.run(
                argv,
                cwd=str(self.config.sandbox_root_resolved),
                timeout_seconds=self.config.timeout_seconds,
            )
        except OSError as exc:
            self._enqueue_result(
                command=command,
                ok=False,
                body={"kind": "spawn_error", "detail": str(exc)},
                is_error=True,
                correlation=correlation,
            )
            return
        if run_result.timed_out:
            self._enqueue_result(
                command=command,
                ok=False,
                body={
                    "kind": "timeout",
                    "detail": f"command timed out after {self.config.timeout_seconds}s",
                    "exit_code": run_result.exit_code,
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                },
                is_error=True,
                correlation=correlation,
            )
            return
        ok = run_result.exit_code == 0
        body = {
            "exit_code": run_result.exit_code,
            "stdout": run_result.stdout,
            "stderr": run_result.stderr,
        }
        if not ok:
            body["kind"] = "non_zero_exit"
        self._enqueue_result(
            command=command,
            ok=ok,
            body=body,
            is_error=not ok,
            correlation=correlation,
        )

    def _correlation(self, packet: OutboundPacket) -> dict[str, object]:
        correlation = dict(packet.provenance)
        correlation["outbound_packet_id"] = packet.packet_id
        return correlation

    def _enqueue_result(
        self,
        *,
        command: str,
        ok: bool,
        body: Mapping[str, object],
        is_error: bool,
        correlation: Mapping[str, object],
    ) -> None:
        payload: dict[str, object] = {"op": RUN_COMMAND, "ok": ok, "command": command}
        payload["error" if is_error else "result"] = dict(body)
        content = json.dumps(payload, ensure_ascii=False)[: self.config.max_output_chars]
        with self._lock:
            if len(self._backlog) >= self.config.max_backlog:
                self._overflow_count += 1
                return
            self._result_seq += 1
            seq = self._result_seq
            self._backlog.append(
                InboundPacket(
                    packet_id=f"os-command-result:{self.driver_id}:{seq}",
                    driver_id=self.driver_id,
                    packet_type=TOOL_RESULT_PACKET_TYPE,
                    content=content,
                    qos_class=_TOOL_RESULT_QOS_CLASS,
                    metadata={
                        "correlation": dict(correlation),
                        "op": RUN_COMMAND,
                        "ok": ok,
                    },
                )
            )

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        if budget < 0:
            raise ChannelError("OsCommandChannelDriver drain budget must be >= 0")
        packets: list[InboundPacket] = []
        with self._lock:
            while self._backlog and len(packets) < budget:
                packets.append(self._backlog.popleft())
            overflow = self._overflow_count
            self._overflow_count = 0
            pending_remaining = len(self._backlog)
        return InboundDrainResult(
            driver_id=self.driver_id,
            packets=tuple(packets),
            pending_remaining=pending_remaining,
            overflow_count=overflow,
        )
