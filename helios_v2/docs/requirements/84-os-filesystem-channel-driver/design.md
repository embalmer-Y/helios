# Requirement 84 - OS file-system channel driver (sandboxed effector with result reafference)

## 1. Design Overview

R84 adds a sandboxed OS file-system `ChannelDriver` and the asynchronous effector pattern the channel
framework was designed for but never exercised: an outbound op is *accepted* synchronously, executed
*asynchronously* by an injected executor, and its result is fed back into the driver's own bounded
inbound backlog so it re-enters `02` sensory as a `tool_result` stimulus on a later tick. This is the
NAPI-style async-receive model the `30` framework already encodes (drivers receive asynchronously into
their backlog; the framework drains synchronously at the tick boundary), now applied to an
efference → reafference effector loop. The driver is transport/effector only; `13` planner still owns
selection and acceptance. The change also generalizes the channel-bound assembly from a single CLI
driver to a set of drivers. Everything is additive and opt-in; default assemblies are unchanged.

## 2. Current State and Gap

1. `helios_v2.channel` ships the `ChannelDriver` protocol, `ChannelSubsystem` (round-robin bounded
   drain + priority-respecting bounded dispatch), the QoS taxonomy, and `CliChannelDriver`. The CLI
   driver's `send_outbound` renders text to a sink and terminates — there is no effector whose
   outbound op produces a result that returns as input.
2. The channel-bound assembly (`assemble_runtime(channel_cli=True)`) hard-wires exactly one CLI
   driver: it constructs `ChannelSubsystem`, registers + connects the CLI driver, registers a
   `SubsystemBackedSensorySource`, and gates startup via `ChannelReadinessDependencyProvider` over the
   single CLI driver id. There is no path to register additional drivers.
3. `ChannelSubsystemStateProvider` already projects *all* registered outbound-capable drivers into the
   planner snapshot, and `ChannelInboundDrainRuntimeStage` already drains *all* drivers into one
   sensory sink, so the framework is multi-driver-ready; only the assembly entry is single-driver.
4. The `ChannelInboundDrainRuntimeStage`/`ChannelOutboundDispatchRuntimeStage` and the
   `SubsystemBackedSensorySource` need no change; R84 reuses them verbatim.

## 3. Target Architecture

### 3.1 Owner module `helios_v2.channel.drivers.os_fs`

A new owner-private module siblings `cli.py`, depending only on the `30` contracts and the stdlib.

#### 3.1.1 Executor seam (asynchronous execution, injected)

```python
class FileOpExecutor(Protocol):
    def submit(self, work: Callable[[], None]) -> None: ...

class InlineFileOpExecutor:      # tests: runs work() synchronously on submit
class ThreadPoolFileOpExecutor:  # production: wraps concurrent.futures.ThreadPoolExecutor
```

- `InlineFileOpExecutor.submit(work)` calls `work()` immediately, so in tests a `send_outbound` leaves
  the result already enqueued and the *next* `drain_inbound` returns it deterministically (no threads,
  no races, network-free, bounded — safe for the `83` long-run harness).
- `ThreadPoolFileOpExecutor` submits `work` to a bounded `ThreadPoolExecutor` for true async
  execution; a slow op simply enqueues its result whenever it finishes, drained on whatever later tick
  follows completion ("有结果就返回").

#### 3.1.2 `OsFileSystemDriverConfig`

```python
@dataclass(frozen=True)
class OsFileSystemDriverConfig:
    sandbox_root: Path            # required; all I/O confined here
    driver_id: str = "os_fs"
    allow_write: bool = True      # gates fs_write / fs_modify
    max_backlog: int = 128        # bounded inbound backlog
    max_read_bytes: int = 262144  # read cap (256 KiB)
    max_result_chars: int = 8192  # result-string cap in the tool_result payload
```

`__post_init__` raises `ChannelError` on an empty driver id or a non-positive bound. The resolved
sandbox root (`sandbox_root.resolve()`) is stored once for path checks.

#### 3.1.3 `OsFileSystemChannelDriver(ChannelDriver)`

State: injected `executor: FileOpExecutor`, `config`, a status field, a `deque[InboundPacket]` backlog
guarded by a `threading.Lock`, and an overflow counter.

- `descriptor()` — directions `("inbound", "outbound")`, `output_ops=("fs_read","fs_write","fs_list",
  "fs_modify")`, `input_packet_types=("tool_result",)`, lifecycle/config/health ops, config fields for
  `sandbox_root`/`allow_write`/`max_backlog`/`max_read_bytes`/`max_result_chars`.
- `apply_management_op()` — the same lifecycle status machine as CLI (init/connect/disconnect/deinit/
  pause/resume/teardown + health_check/get_config), reusing the `30` status taxonomy.
- `status()` / `config_snapshot()` — pending-inbound = backlog length, overflow count in health.
- `static_readiness()` — `ready = sandbox_root_resolved.is_dir()`; detail states presence. Never
  creates the directory.
- `send_outbound(packet)` (synchronous acceptance):
  1. If status is not `connected` → failed outcome (mirrors CLI) + enqueue failure reafference.
  2. Structural validation: op in the four ops; required params present and `str`-typed; a write op
     requires `allow_write`. On failure → `OutboundDispatchOutcome(status="failed", detail=...)` **and**
     `_enqueue_result(failure, correlation)` (double write-back).
  3. On success → capture `(op, params, provenance)` into a closure `work()` and
     `self.executor.submit(work)`; return `OutboundDispatchOutcome(status="delivered",
     detail="accepted for async execution")`.
- `work()` (runs on the executor thread, or inline in tests):
  1. Resolve + sandbox-check the path; perform the op; build a success result dict.
  2. Any exception (`_PathEscapeError`, `FileNotFoundError`, `PermissionError`, `UnicodeError`,
     `OSError`, `ValueError`) is caught and turned into a failure result dict (`error.kind` +
     `error.detail`). No exception escapes `work()` (an escaped exception on a worker thread would be
     lost — the contract is that every op yields exactly one reafference).
  3. `_enqueue_result(result_dict, correlation)`.
- `_enqueue_result(payload_dict, correlation)`:
  - content = `json.dumps({"op", "ok", "path", "result"|"error"}, ensure_ascii=False)`, truncated to
    `max_result_chars`.
  - Under the lock: if backlog full → increment overflow, drop (counted, never unbounded); else append
    an `InboundPacket(packet_type="tool_result", qos_class="bulk", content=..., metadata={
    "correlation": correlation, "op": op, "ok": ok})`. packet_id is a monotonic per-driver counter.
- `drain_inbound(budget)` — under the lock, pop up to `budget` packets, return `InboundDrainResult`
  with `pending_remaining = len(backlog)` and the (reset) overflow count.

QoS: `tool_result` is classed `"bulk"` — a transport-intrinsic class for local data results, set
without reading content for meaning (consistent with `30` §5.4: only `03` may read QoS as salience).

#### 3.1.4 Path-escape defense

```python
def _resolve_in_sandbox(self, raw_path: str) -> Path:
    candidate = Path(raw_path)
    base = self.config.sandbox_root_resolved
    resolved = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if resolved != base and base not in resolved.parents:
        raise _PathEscapeError(raw_path)
    return resolved
```

`Path.resolve()` follows symlinks, so a symlink inside the sandbox that points outside resolves to the
outside target and is rejected. Absolute paths outside the sandbox are rejected. The sandbox root
itself is allowed (for `fs_list` with no/`"."` path).

#### 3.1.5 Operation semantics

| Op | Required params | Behavior | Success result |
| --- | --- | --- | --- |
| `fs_read` | `path` | Read UTF-8, up to `max_read_bytes` | `{content, truncated, size_bytes}` |
| `fs_write` | `path`, `content` | Create parent dirs in sandbox, write UTF-8 (overwrite) | `{bytes_written, path}` |
| `fs_modify` | `path`, `content` | Append UTF-8 to an **existing** file (else `FileNotFoundError`) | `{bytes_appended, size_bytes}` |
| `fs_list` | `path` (optional, default `"."`) | List directory entries (must be a dir) | `{entries: [{name, kind, size}]}` |

### 3.2 Generalized channel-bound assembly

`RuntimeProfile` gains `channel_drivers: tuple[ChannelDriver, ...] = ()`. The effective driver set is
`([CliChannelDriver(...)] if channel_cli else []) + list(channel_drivers)`. The assembly block (today
gated on `if channel_cli:`) becomes `if effective_drivers:`:

1. Build one `ChannelSubsystem`; register + `connect` every effective driver in order.
2. Register one `SubsystemBackedSensorySource` (source name `"channel_subsystem"`); the inbound drain
   stage already drains all drivers into it.
3. Gate startup via `ChannelReadinessDependencyProvider(subsystem, bound_driver_ids=all effective
   ids, baseline_provider=...)` (unchanged class; just a longer id tuple).
4. The planner channel-state provider (`ChannelSubsystemStateProvider`) and the two transport stages
   are wired exactly as today; `CHANNEL_BOUND_STAGE_ORDER` (21 stages) is unchanged (transport stages
   are per-subsystem, not per-driver).

`RuntimeProfile.__post_init__` extends the existing mutual-exclusion check: `external_signal_source`
must not be combined with `channel_cli` **or** a non-empty `channel_drivers` (both own the external
afferent). `channel_cli` with `channel_drivers` is allowed (CLI plus effectors coexist).

The cli-only path (`channel_cli=True`, `channel_drivers=()`) yields exactly today's single-CLI
subsystem, so R31 behavior is byte-for-byte preserved.

### 3.3 What R84 does NOT wire

The planner does not yet autonomously emit an `fs_*` decision; R84's end-to-end loop is demonstrated
at the subsystem level (dispatch an `OutboundPacket` → execute → drain the `tool_result`) and the
assembly test proves the OS driver is registered, readiness-gated, drained into sensory, and the
runtime stays stable. Autonomous LLM-driven tool selection is the deferred follow-on requirement
(ROADMAP).

## 4. Data Structures

1. `FileOpExecutor` (Protocol), `InlineFileOpExecutor`, `ThreadPoolFileOpExecutor` — new, in `os_fs.py`.
2. `OsFileSystemDriverConfig` — new frozen dataclass.
3. `OsFileSystemChannelDriver` — new `ChannelDriver` implementation.
4. `_PathEscapeError` — new module-private exception (caught inside `work()`).
5. `RuntimeProfile.channel_drivers: tuple[ChannelDriver, ...] = ()` — additive field.
6. No change to any `30` contract, `RawSignal`, the transport stages, or the planner/sensory owners.
   The `tool_result` reafference rides existing `InboundPacket`/`RawSignal` shapes and metadata.

## 5. Module Changes

1. `channel/drivers/os_fs.py` — new module (executors, config, driver, path helper, op handlers).
2. `channel/drivers/__init__.py` — export `OsFileSystemChannelDriver`, `OsFileSystemDriverConfig`,
   `FileOpExecutor`, `InlineFileOpExecutor`, `ThreadPoolFileOpExecutor`.
3. `channel/__init__.py` — re-export the above.
4. `composition/runtime_assembly.py` — add `RuntimeProfile.channel_drivers` + the
   `_UNSET`/kwarg plumbing; extend the mutual-exclusion validation; change the assembly block from
   single-CLI to effective-driver-set; keep the cli-only path identical.
5. Tests + docs (see §9 and `task.md`).

## 6. Migration Plan

1. Additive and opt-in. Default assemblies (`channel_drivers=()`, `channel_cli=False`) are unchanged.
2. `channel_cli=True` keeps its exact behavior; the generalized block reduces to the single-CLI case
   when `channel_drivers` is empty. Existing R31 tests stay green untouched.
3. Production deployment of the OS driver (with `ThreadPoolFileOpExecutor` and a real sandbox root
   under git-ignored `data/`) is a later entry-point/ops concern; R84 ships the capability injectable
   and proves it network-free with the inline executor. The CI/long-run suites continue to use the
   inline executor for determinism.

## 7. Failure Modes and Constraints

1. Not-ready sandbox (missing/not-a-dir root) → static readiness not-ready → startup gate fails fast
   when the OS driver is a bound critical driver. No degraded non-sandbox path.
2. Structural rejection (unknown op / missing param / write-disabled) → failed dispatch outcome +
   failure reafference (double write-back).
3. Execution failure (path escape, not found, permission, decode, I/O) → failure reafference only
   (the acceptance outcome already returned `delivered`); never a fabricated success, never a fallback
   op. `work()` never lets an exception escape the worker thread.
4. Path escape (absolute outside / `..` / symlink) → `_PathEscapeError` → failure reafference; no file
   outside the sandbox is ever touched.
5. Backlog overflow → bounded, counted, dropped (never unbounded, never silent).
6. Concurrency → backlog guarded by a lock; deque ops plus the lock make worker-thread enqueue and
   tick-thread drain race-free.
7. The driver holds no cognitive policy: no salience, no normalization, no channel re-selection, no
   content shaping, no interpretation of result meaning.

## 8. Observability and Logging

No new logging mechanism and no `logging`/`print` in `src/`. Transport facts travel through the `30`
contracts; operation results travel as re-entered `tool_result` stimuli carrying correlation
provenance, which flow through the existing `02`/`03` and `21`/`17`/`23` surfaces unchanged. The
outbound dispatch stage already records the `OutboundPacket` provenance in its stage result.

## 9. Validation Strategy

1. Unit (`test_channel_os_fs_driver.py`): protocol conformance; descriptor shape; readiness ready vs
   not-ready (existing dir vs missing dir).
2. Unit: `fs_write` then `fs_read` with the inline executor → drain returns a `tool_result` with the
   written content and correlation metadata equal to the dispatched packet's provenance.
3. Unit: `fs_list` returns entries; `fs_modify` appends to an existing file and fails on a missing
   file; `fs_write` while `allow_write=False` is rejected (failed outcome + failure reafference).
4. Unit: path-escape attempts (`../../outside`, an absolute outside path, a symlink pointing outside)
   are rejected, touch nothing outside the sandbox, and surface as failure `tool_result`s.
5. Unit: structural rejection returns a failed dispatch outcome and also enqueues a failure result;
   backlog overflow is bounded and counted.
6. Concurrency: with `ThreadPoolFileOpExecutor`, many concurrent submits all enqueue and drain without
   loss or error (a deterministic count assertion after draining to empty).
7. Subsystem loop (`test_channel_os_fs_driver.py`): register the OS driver on a `ChannelSubsystem`,
   `dispatch_outbound` an `fs_write`/`fs_read`, then `drain_inbound` and assert the mapped `RawSignal`
   (`source_name="os_fs"`, `signal_type="tool_result"`, QoS in metadata).
8. Composition (`test_runtime_composition.py`): `assemble_runtime(channel_drivers=(os_fs_driver,))`
   builds, gates readiness, runs a tick, stays stable; a `channel_cli=True` + `channel_drivers`
   assembly registers both; `external_signal_source` + `channel_drivers` raises `CompositionError`;
   the cli-only assembly is unchanged.
9. Guards: owner-boundary guard and ad-hoc-logging guard green; full network-free `helios_v2/tests`
   suite green.
