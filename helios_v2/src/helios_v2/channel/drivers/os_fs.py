"""Owner: channel driver subsystem (first effector driver).

A sandboxed OS file-system `ChannelDriver`. Unlike a pure I/O relay (the `31` CLI driver, whose
outbound is a terminal rendered reply), this driver is an EFFECTOR: an accepted outbound op
(`fs_read`/`fs_write`/`fs_list`/`fs_modify`) performs a real file-system action confined to a sandbox
root, and the operation's RESULT (success or failure) is fed back into the driver's own bounded
inbound backlog so it re-enters `02` sensory as a `tool_result` stimulus on a later tick. This is the
efference -> reafference loop the channel framework's NAPI-style async-receive model already encodes:
`send_outbound` accepts synchronously and submits to an injected executor; the result is enqueued
asynchronously and drained at a tick boundary ("有结果就返回").

Boundary: this driver is transport/effector only. It does not normalize into stimuli, score salience,
re-select channels, shape outward content, or interpret a result's meaning. It performs I/O only
inside the resolved sandbox root; an out-of-sandbox path is a rejected operation, never a redirected
one. It never spawns a process and never touches the network (those are requirements `85`/later).
"""

from __future__ import annotations

import json
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Protocol, runtime_checkable

from ..contracts import (
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
    OutboundDispatchOutcome,
    OutboundPacket,
)

OS_FS_DRIVER_ID = "os_fs"
TOOL_RESULT_PACKET_TYPE = "tool_result"

FS_READ = "fs_read"
FS_WRITE = "fs_write"
FS_LIST = "fs_list"
FS_MODIFY = "fs_modify"
_FS_OPS = (FS_READ, FS_WRITE, FS_LIST, FS_MODIFY)
_WRITE_OPS = frozenset({FS_WRITE, FS_MODIFY})

# Tool results are local data payloads. The QoS class is transport-intrinsic (a fixed `bulk` class
# for effector data results), set without reading the result content for meaning, consistent with
# `30`: only `03` appraisal may read QoS as a salience input.
_TOOL_RESULT_QOS_CLASS = "bulk"

_LIFECYCLE_TRANSITIONS: dict[str, ChannelDriverStatus] = {
    "init": "disconnected",
    "connect": "connected",
    "disconnect": "disconnected",
    "deinit": "uninitialized",
    "pause": "paused",
    "resume": "connected",
    "teardown": "disconnected",
}


class _PathEscapeError(Exception):
    """Module-private: a requested path resolved outside the sandbox root."""


@runtime_checkable
class FileOpExecutor(Protocol):
    """Owner: channel driver subsystem (OS file-system driver).

    Purpose:
        The injected asynchronous-execution seam. The driver submits one fire-and-forget unit of work
        per accepted operation; the implementation decides whether to run it inline (tests) or on a
        worker thread (production). The driver owns neither the threading policy nor the executor
        lifecycle beyond submitting work.
    """

    def submit(self, work: Callable[[], None]) -> None:
        """Submit one unit of work for execution (fire-and-forget)."""

        ...


@dataclass
class InlineFileOpExecutor(FileOpExecutor):
    """Owner: channel driver subsystem (OS file-system driver).

    Purpose:
        Deterministic, network-free executor for tests: runs the work synchronously on submit, so a
        `send_outbound` leaves the result already enqueued and the next `drain_inbound` returns it
        with no threads and no races (safe for the `83` long-run harness).
    """

    def submit(self, work: Callable[[], None]) -> None:
        """Run the work synchronously."""

        work()


@dataclass
class ThreadPoolFileOpExecutor(FileOpExecutor):
    """Owner: channel driver subsystem (OS file-system driver).

    Purpose:
        Production executor: submits work to a bounded `ThreadPoolExecutor` for true asynchronous
        execution, so a slow operation enqueues its result whenever it finishes (drained on a later
        tick) without blocking the runtime tick.

    Failure semantics:
        Construction raises `ChannelError` on a non-positive worker count.
    """

    max_workers: int = 4
    _pool: ThreadPoolExecutor = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers <= 0:
            raise ChannelError("ThreadPoolFileOpExecutor max_workers must be a positive integer")
        self._pool = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="helios-os-fs"
        )

    def submit(self, work: Callable[[], None]) -> None:
        """Submit the work to the bounded thread pool."""

        self._pool.submit(work)

    def shutdown(self) -> None:
        """Owner: channel driver subsystem. Shut the pool down (production teardown only)."""

        self._pool.shutdown(wait=False, cancel_futures=True)


@dataclass(frozen=True)
class OsFileSystemDriverConfig:
    """Owner: channel driver subsystem (OS file-system driver).

    Purpose:
        Declare the OS file-system driver's local configuration: the sandbox root all I/O is confined
        to, whether writes are enabled, and the bounded backlog/read/result caps.

    Failure semantics:
        Construction raises `ChannelError` on an empty driver id or any non-positive bound.

    Notes:
        `sandbox_root_resolved` is the resolved (symlink-followed) sandbox root used for every
        path-escape check; it is computed once at construction.
    """

    sandbox_root: Path
    driver_id: str = OS_FS_DRIVER_ID
    allow_write: bool = True
    max_backlog: int = 128
    max_read_bytes: int = 262144
    max_result_chars: int = 8192
    sandbox_root_resolved: Path = field(init=False)

    def __post_init__(self) -> None:
        if not self.driver_id:
            raise ChannelError("OsFileSystemDriverConfig must declare a non-empty driver_id")
        if self.max_backlog <= 0:
            raise ChannelError("OsFileSystemDriverConfig max_backlog must be a positive integer")
        if self.max_read_bytes <= 0:
            raise ChannelError("OsFileSystemDriverConfig max_read_bytes must be a positive integer")
        if self.max_result_chars <= 0:
            raise ChannelError("OsFileSystemDriverConfig max_result_chars must be a positive integer")
        object.__setattr__(self, "sandbox_root", Path(self.sandbox_root))
        object.__setattr__(self, "sandbox_root_resolved", Path(self.sandbox_root).resolve())


def _os_fs_descriptor(config: OsFileSystemDriverConfig) -> ChannelDriverDescriptor:
    return ChannelDriverDescriptor(
        driver_id=config.driver_id,
        display_name="Sandboxed OS File-System Channel",
        directions=("inbound", "outbound"),
        input_packet_types=(TOOL_RESULT_PACKET_TYPE,),
        output_ops=_FS_OPS,
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
                description="absolute root directory all file I/O is confined to",
                required=True,
                mutable_at_runtime=False,
                schema_hint="path",
            ),
            ChannelConfigField(
                key="allow_write",
                description="whether fs_write/fs_modify are permitted",
                required=False,
                mutable_at_runtime=False,
                schema_hint="bool",
            ),
            ChannelConfigField(
                key="max_backlog",
                description="bounded inbound (result) backlog capacity",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
            ChannelConfigField(
                key="max_read_bytes",
                description="maximum bytes read by fs_read",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
            ChannelConfigField(
                key="max_result_chars",
                description="maximum characters in a tool_result payload",
                required=False,
                mutable_at_runtime=False,
                schema_hint="int",
            ),
        ),
        health_signals=("pending_inbound", "overflow_count"),
        output_op_specs=(
            ChannelOpSpec(
                op_name=FS_READ,
                required_params=("path",),
                user_visible=False,
                effect_class="local_host",
                risk_class="unrestricted",
            ),
            ChannelOpSpec(
                op_name=FS_WRITE,
                required_params=("path", "content"),
                user_visible=False,
                effect_class="local_host",
                risk_class="unrestricted",
            ),
            ChannelOpSpec(
                op_name=FS_LIST,
                required_params=(),
                user_visible=False,
                effect_class="local_host",
                risk_class="unrestricted",
            ),
            ChannelOpSpec(
                op_name=FS_MODIFY,
                required_params=("path", "content"),
                user_visible=False,
                effect_class="local_host",
                risk_class="unrestricted",
            ),
        ),
    )


@dataclass
class OsFileSystemChannelDriver(ChannelDriver):
    """Owner: channel driver subsystem (OS file-system effector driver).

    Purpose:
        The first effector `ChannelDriver`: it accepts planner-accepted file operations as outbound
        packets, executes them asynchronously inside a sandbox root through an injected executor, and
        feeds each operation's result (success or failure) back into its bounded inbound backlog as a
        `tool_result` packet so the result re-enters `02` sensory carrying correlation provenance.

    Failure semantics:
        A structurally invalid packet returns a failed outcome AND enqueues a failure reafference
        (double write-back). An execution failure (path escape, not found, permission, decode, I/O)
        enqueues a failure reafference only (the acceptance outcome already returned `delivered`).
        Backlog overflow is bounded and counted, never raised. A failure is never reported as a
        success and never falls back to a different operation.

    Notes:
        The backlog is guarded by a lock because production execution runs the operation on a worker
        thread while the tick thread drains on the main thread.
    """

    config: OsFileSystemDriverConfig
    executor: FileOpExecutor = field(default_factory=InlineFileOpExecutor)
    _status: ChannelDriverStatus = field(default="uninitialized", init=False)
    _backlog: deque[InboundPacket] = field(default_factory=deque, init=False)
    _overflow_count: int = field(default=0, init=False)
    _result_seq: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    @property
    def driver_id(self) -> str:
        return self.config.driver_id

    def descriptor(self) -> ChannelDriverDescriptor:
        return _os_fs_descriptor(self.config)

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
                message="os_fs driver healthy",
                payload={"pending_inbound": pending, "overflow_count": overflow},
            )
        if op_name == "get_config":
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message="os_fs driver config",
                payload=self._config_values(),
            )
        if op_name in _LIFECYCLE_TRANSITIONS:
            self._status = _LIFECYCLE_TRANSITIONS[op_name]
            return ChannelManagementResult(
                driver_id=self.driver_id,
                op_name=op_name,
                success=True,
                status=self._status,
                message=f"os_fs driver applied '{op_name}'",
            )
        return ChannelManagementResult(
            driver_id=self.driver_id,
            op_name=op_name,
            success=False,
            status=self._status,
            message=f"unsupported os_fs management op '{op_name}'",
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
            "allow_write": self.config.allow_write,
            "max_backlog": self.config.max_backlog,
            "max_read_bytes": self.config.max_read_bytes,
            "max_result_chars": self.config.max_result_chars,
        }

    def static_readiness(self) -> ChannelDriverReadiness:
        # Network-free, deterministic: ready iff the sandbox root exists as a directory. The driver
        # never creates the root to appear ready (no degraded path).
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
        """Accept one planner-accepted file op for asynchronous execution.

        Returns a `delivered` outcome meaning "accepted for execution" (not "completed"); the op's
        success/failure is reported only through the result reafference. A structurally invalid
        packet returns a `failed` outcome and also enqueues a failure reafference.
        """

        correlation = self._correlation(packet)
        if self._status != "connected":
            self._enqueue_result(
                op_name=packet.op_name,
                ok=False,
                path=str(packet.payload.get("path", "")),
                body={"kind": "not_connected", "detail": f"driver status={self._status}"},
                is_error=True,
                correlation=correlation,
            )
            return OutboundDispatchOutcome(
                packet_id=packet.packet_id,
                target_driver_id=self.driver_id,
                status="failed",
                detail=f"os_fs driver not connected (status={self._status})",
            )

        rejection = self._structural_rejection(packet)
        if rejection is not None:
            self._enqueue_result(
                op_name=packet.op_name,
                ok=False,
                path=str(packet.payload.get("path", "")),
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

        op_name = packet.op_name
        params = dict(packet.payload)

        def work() -> None:
            self._execute(op_name, params, correlation)

        self.executor.submit(work)
        return OutboundDispatchOutcome(
            packet_id=packet.packet_id,
            target_driver_id=self.driver_id,
            status="delivered",
            detail=f"accepted op '{op_name}' for async execution",
        )

    def _structural_rejection(self, packet: OutboundPacket) -> str | None:
        op_name = packet.op_name
        if op_name not in _FS_OPS:
            return f"unsupported os_fs op '{op_name}'"
        if op_name in _WRITE_OPS and not self.config.allow_write:
            return f"write op '{op_name}' rejected: writes are disabled"
        params = packet.payload
        if op_name in (FS_READ, FS_WRITE, FS_MODIFY):
            path = params.get("path")
            if not isinstance(path, str) or not path:
                return f"op '{op_name}' requires a non-empty string 'path'"
        if op_name in (FS_WRITE, FS_MODIFY):
            content = params.get("content")
            if not isinstance(content, str):
                return f"op '{op_name}' requires a string 'content'"
        if op_name == FS_LIST:
            path = params.get("path", ".")
            if not isinstance(path, str):
                return "op 'fs_list' requires a string 'path' when provided"
        return None

    def _execute(
        self,
        op_name: str,
        params: Mapping[str, object],
        correlation: Mapping[str, object],
    ) -> None:
        """Run one operation on the executor and enqueue exactly one result reafference.

        This runs on the executor thread (or inline in tests). Every exception is caught and turned
        into a failure result so no exception escapes the worker thread and every op yields exactly
        one reafference.
        """

        raw_path = str(params.get("path", "." if op_name == FS_LIST else ""))
        try:
            result_body = self._dispatch_op(op_name, params)
            self._enqueue_result(
                op_name=op_name,
                ok=True,
                path=raw_path,
                body=result_body,
                is_error=False,
                correlation=correlation,
            )
        except _PathEscapeError as exc:
            self._enqueue_result(
                op_name=op_name,
                ok=False,
                path=raw_path,
                body={"kind": "path_escape", "detail": f"path escapes sandbox: {exc}"},
                is_error=True,
                correlation=correlation,
            )
        except FileNotFoundError as exc:
            self._enqueue_result(
                op_name=op_name,
                ok=False,
                path=raw_path,
                body={"kind": "not_found", "detail": str(exc)},
                is_error=True,
                correlation=correlation,
            )
        except PermissionError as exc:
            self._enqueue_result(
                op_name=op_name,
                ok=False,
                path=raw_path,
                body={"kind": "permission_denied", "detail": str(exc)},
                is_error=True,
                correlation=correlation,
            )
        except (UnicodeError, ValueError) as exc:
            self._enqueue_result(
                op_name=op_name,
                ok=False,
                path=raw_path,
                body={"kind": "decode_error", "detail": str(exc)},
                is_error=True,
                correlation=correlation,
            )
        except OSError as exc:
            self._enqueue_result(
                op_name=op_name,
                ok=False,
                path=raw_path,
                body={"kind": "io_error", "detail": str(exc)},
                is_error=True,
                correlation=correlation,
            )

    def _dispatch_op(self, op_name: str, params: Mapping[str, object]) -> dict[str, object]:
        if op_name == FS_READ:
            return self._do_read(str(params["path"]))
        if op_name == FS_WRITE:
            return self._do_write(str(params["path"]), str(params["content"]))
        if op_name == FS_MODIFY:
            return self._do_modify(str(params["path"]), str(params["content"]))
        if op_name == FS_LIST:
            return self._do_list(str(params.get("path", ".")))
        # Unreachable: structural validation already rejected unknown ops.
        raise ValueError(f"unsupported os_fs op '{op_name}'")

    def _do_read(self, raw_path: str) -> dict[str, object]:
        target = self._resolve_in_sandbox(raw_path)
        data = target.read_bytes()
        truncated = len(data) > self.config.max_read_bytes
        text = data[: self.config.max_read_bytes].decode("utf-8")
        return {"content": text, "truncated": truncated, "size_bytes": len(data)}

    def _do_write(self, raw_path: str, content: str) -> dict[str, object]:
        target = self._resolve_in_sandbox(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = content.encode("utf-8")
        target.write_bytes(encoded)
        return {"bytes_written": len(encoded), "path": self._relative(target)}

    def _do_modify(self, raw_path: str, content: str) -> dict[str, object]:
        target = self._resolve_in_sandbox(raw_path)
        if not target.is_file():
            raise FileNotFoundError(f"fs_modify target does not exist: {raw_path}")
        encoded = content.encode("utf-8")
        with target.open("ab") as handle:
            handle.write(encoded)
        return {"bytes_appended": len(encoded), "size_bytes": target.stat().st_size}

    def _do_list(self, raw_path: str) -> dict[str, object]:
        target = self._resolve_in_sandbox(raw_path)
        if not target.is_dir():
            raise FileNotFoundError(f"fs_list target is not a directory: {raw_path}")
        entries: list[dict[str, object]] = []
        for child in sorted(target.iterdir(), key=lambda p: p.name):
            kind = "dir" if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else 0
            entries.append({"name": child.name, "kind": kind, "size": size})
        return {"entries": entries}

    def _resolve_in_sandbox(self, raw_path: str) -> Path:
        base = self.config.sandbox_root_resolved
        candidate = Path(raw_path)
        resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
        if resolved != base and base not in resolved.parents:
            raise _PathEscapeError(raw_path)
        return resolved

    def _relative(self, target: Path) -> str:
        base = self.config.sandbox_root_resolved
        if target == base:
            return "."
        return str(target.relative_to(base))

    def _correlation(self, packet: OutboundPacket) -> dict[str, object]:
        correlation = dict(packet.provenance)
        correlation["outbound_packet_id"] = packet.packet_id
        return correlation

    def _enqueue_result(
        self,
        *,
        op_name: str,
        ok: bool,
        path: str,
        body: Mapping[str, object],
        is_error: bool,
        correlation: Mapping[str, object],
    ) -> None:
        payload: dict[str, object] = {"op": op_name, "ok": ok, "path": path}
        payload["error" if is_error else "result"] = dict(body)
        content = json.dumps(payload, ensure_ascii=False)[: self.config.max_result_chars]
        with self._lock:
            if len(self._backlog) >= self.config.max_backlog:
                self._overflow_count += 1
                return
            self._result_seq += 1
            seq = self._result_seq
            self._backlog.append(
                InboundPacket(
                    packet_id=f"os-fs-result:{self.driver_id}:{seq}",
                    driver_id=self.driver_id,
                    packet_type=TOOL_RESULT_PACKET_TYPE,
                    content=content,
                    qos_class=_TOOL_RESULT_QOS_CLASS,
                    metadata={
                        "correlation": dict(correlation),
                        "op": op_name,
                        "ok": ok,
                    },
                )
            )

    def drain_inbound(self, budget: int) -> InboundDrainResult:
        if budget < 0:
            raise ChannelError("OsFileSystemChannelDriver drain budget must be >= 0")
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
