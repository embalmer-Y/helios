# Requirement 84 - OS file-system channel driver (sandboxed effector with result reafference)

## 1. Background and Problem

Requirement `30` established the channel driver subsystem (a Linux-kernel-driver-style owner
`helios_v2.channel`: a uniform `ChannelDriver` protocol, a runtime-pluggable registry, NAPI-style
bounded inbound drain emitting `RawSignal` objects, bounded outbound dispatch of planner-accepted
decisions, transport-intrinsic QoS, and fail-fast readiness). Requirement `31` shipped the first
concrete driver (local CLI) and the opt-in channel-bound assembly, proving the inbound-drain →
sensory and planner → outbound-dispatch seams with a real local round trip.

Every concrete driver so far is a pure I/O relay: CLI inbound is operator text, CLI outbound is a
rendered reply that terminates at a sink. Helios still has no **effector** — a driver whose outbound
op performs a real action on the host (read/write a file, list a directory) and whose **result must
flow back into perception as a new stimulus**. Without such a driver there is no tool-use loop, and
the final-goal capability axis FG-4 ("会熟练使用工具") and stage P4 cannot begin: the
`ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13.3.2 P4 gate requires a real OS driver whose execution result
re-enters `02` sensory (FG-4.2), with failures formally written back and never silently swallowed
(FG-4.4).

This requirement adds the first effector driver: a sandboxed OS file-system driver. It is the
cleanest, lowest-risk P4 slice (local, no network, no process spawning — command execution is the
separate, higher-risk requirement `85`). It also generalizes the channel-bound assembly so a set of
drivers can be registered together, preparing for the later coexistence of multiple real drivers
(QQ / Lark / voice).

## 2. Goal

Implement a sandboxed OS file-system `ChannelDriver` (`helios_v2.channel.drivers.os_fs`) that accepts
planner-accepted file operations (`fs_read` / `fs_write` / `fs_list` / `fs_modify`) as outbound
packets, executes them asynchronously through an injected executor within a configured sandbox root
(with strict path-escape defense), and enqueues each operation's result — success or failure — into
its own bounded inbound backlog so the result re-enters `02` sensory as a `tool_result` stimulus
carrying correlation provenance back to the originating decision; and generalize the channel-bound
assembly to register a set of drivers, all without granting the driver any cognitive ownership, any
degraded/fabricated-success path, or any escape from its sandbox.

## 3. Functional Requirements

### 3.1 Driver conformance
1. The OS file-system driver must implement the `30` `ChannelDriver` protocol fully: `driver_id`,
   `descriptor`, `apply_management_op`, `status`, `config_snapshot`, `drain_inbound`,
   `send_outbound`, and `static_readiness`.
2. The descriptor must declare directions `("inbound", "outbound")`, `output_ops` =
   `("fs_read", "fs_write", "fs_list", "fs_modify")`, `input_packet_types` = `("tool_result",)`,
   its lifecycle/management ops, and its config fields (sandbox root, write-enable, bounds).
3. Static readiness must be deterministic and network-free: ready iff the configured sandbox root
   exists and is a directory. A missing or non-directory sandbox root reports not-ready (so the
   startup gate fails fast); the driver must not create or fabricate the root to appear ready.

### 3.2 Outbound (planner decision -> sandboxed file operation, asynchronous)
1. On `send_outbound(packet)` the driver must validate the op name and required params
   structurally. A structurally invalid packet (unknown op, missing/ill-typed param, or a write op
   while writes are disabled) must return an explicit `OutboundDispatchOutcome(status="failed", ...)`
   **and** enqueue a failure `tool_result` so the rejection is also observable as reafference.
2. A structurally valid packet must be submitted to the injected executor for asynchronous
   execution and must return `OutboundDispatchOutcome(status="delivered", ...)` whose meaning is
   "accepted for execution", not "completed". The driver must not block the tick on the operation.
3. Execution must occur strictly inside the sandbox root. Every path must be resolved
   (`Path.resolve()`, following symlinks) and rejected unless it is relative to the resolved sandbox
   root. An absolute path outside the sandbox or a symlink escaping the sandbox must be rejected.
4. The four operations must behave as: `fs_read` returns bounded UTF-8 file content; `fs_write`
   creates-or-overwrites a UTF-8 file (creating parent dirs inside the sandbox); `fs_modify` appends
   UTF-8 to an existing file (failing if it does not exist); `fs_list` returns the entries of a
   directory. Result payloads must be bounded (read size cap, result-string cap).
5. An execution failure (path escape, not found, permission, decode error, I/O error) must enqueue a
   failure `tool_result` describing the error. Execution failure must never be reported as success
   and must never fall back to a different operation or a fabricated result.

### 3.3 Result reafference (effector result -> bounded backlog -> drain -> sensory)
1. On completion (success or failure) the executor callback must enqueue exactly one `tool_result`
   packet into the driver's bounded inbound backlog, asynchronously relative to the tick.
2. The packet content must be a JSON string carrying at least `op`, `ok`, `path`, and either
   `result` or `error`. The packet metadata must carry a `correlation` projection of the originating
   `OutboundPacket.provenance` (the decision/proposal ids) plus the op name and `ok`, so the result
   stimulus is traceable back to the action that produced it.
3. On `drain_inbound(budget)` the driver must return at most `budget` queued `tool_result` packets as
   `InboundPacket` objects with a transport-intrinsic QoS class (a fixed class for local data
   results, set without reading the result content for meaning), plus the pending-remaining count.
4. Backlog overflow must apply a bounded, counted, non-silent policy; the backlog must never grow
   unbounded.
5. Backlog reads and writes must be thread-safe, because production execution runs the operation on a
   worker thread while the tick thread drains on the main thread.

### 3.4 Asynchronous executor seam
1. The driver must execute operations through an injected executor conforming to a small protocol
   (`submit(fn)` fire-and-forget). The driver must own neither the threading policy nor the lifecycle
   of the executor beyond submitting work.
2. A deterministic inline executor (executes synchronously on submit) must exist for tests so the
   network-free suite is deterministic and free of thread races; a thread-pool-backed executor must
   exist for real asynchronous production execution.

### 3.5 Composition wiring (opt-in, generalized to a set of drivers)
1. The channel-bound assembly must be generalized so a caller can register a set of drivers (not only
   CLI). The existing `channel_cli` opt-in must keep its exact current behavior when no additional
   drivers are supplied.
2. When one or more drivers are bound, the assembly must register all of them on one subsystem,
   connect them, feed all drained inbound signals into the subsystem-backed sensory source, expose
   all outbound-capable drivers' real state to the planner, and gate startup on every bound driver's
   static readiness.
3. Binding any channel driver remains mutually exclusive with an injected `external_signal_source`
   (both own the external afferent position); supplying both must be a fail-fast `CompositionError`.
4. The default assemblies (no channel binding) must remain byte-for-byte unchanged.

### 3.6 End-to-end effector loop
1. Through the subsystem, dispatching a valid `fs_write` then `fs_read` outbound packet must cause the
   file to be written under the sandbox and the read result to be drained back as a `tool_result`
   `RawSignal` carrying the file content and the correlation provenance — demonstrated network-free
   with the inline executor.
2. A path-escape attempt (e.g. `../../etc/hosts`) must be rejected, must not touch any file outside
   the sandbox, and must surface as a failure `tool_result` reafference.
3. A channel-bound assembly that registers the OS driver must run a tick and stay stable; a tick with
   no planner-accepted file op dispatches nothing to the driver and closes cleanly (internal-only tick
   closure from `28` holds).

## 4. Non-Functional Requirements

1. Performance: outbound submission and inbound drain are bounded by the framework budgets and never
   block the tick; per-tick cost stays bounded (consistent with the `83` long-run finding).
2. Reliability and fault tolerance: every operation failure is captured as a structured failure
   reafference; no failure is silently swallowed and no failure is reported as success. The sandbox
   boundary is enforced on every path with no exception.
3. Observability and logging: the driver must not introduce a second logging mechanism and must not
   use `logging` or `print`; transport and result facts travel only through the `30` contracts and the
   re-entered stimulus. The single-logging-mechanism guard must stay green.
4. Compatibility and migration: additive and opt-in. The generalized assembly preserves `channel_cli`
   behavior exactly; default assemblies and the full network-free suite stay green.
5. Security: no path may resolve outside the sandbox root; writes are gated by an explicit config flag;
   no process is spawned and no network is touched (command execution and network drivers are out of
   scope).

## 5. Code Behavior Constraints

1. The OS file-system driver lives in `helios_v2.channel.drivers.os_fs` and depends only on the `30`
   protocol/contracts plus the Python standard library (`pathlib`, `concurrent.futures`); it
   introduces no third-party dependency.
2. The driver must not compute salience, must not normalize into stimuli, must not re-decide channel
   selection, and must not semantically shape outward content or interpret a result's meaning.
3. The driver must perform file I/O only inside the resolved sandbox root; an out-of-sandbox path is a
   rejected operation, never a clamped or redirected one.
4. `send_outbound` must not block on the operation; it submits to the injected executor and returns an
   acceptance outcome. Operation success/failure is reported only through the result reafference (plus
   the synchronous structural-rejection outcome).
5. No degraded path: a not-ready sandbox fails the startup gate; a failed operation is written back as
   failure, never as a fabricated success or a fallback op.
6. No `logging` or `print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/channel/drivers/os_fs.py` (new: config, executor protocol + inline/thread
   implementations, the `OsFileSystemChannelDriver`)
2. `helios_v2/src/helios_v2/channel/drivers/__init__.py` (export the OS driver + executors)
3. `helios_v2/src/helios_v2/channel/__init__.py` (re-export)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (`RuntimeProfile.channel_drivers`,
   generalized channel-bound assembly, mutual-exclusion validation)
5. `helios_v2/tests/test_channel_os_fs_driver.py` (new: driver unit + subsystem loop tests)
6. `helios_v2/tests/test_runtime_composition.py` (multi-driver channel-bound assembly test)
7. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/OWNER_GUIDE.md`,
   `helios_v2/docs/OWNER_GUIDE.zh-CN.md`, `helios_v2/docs/PROGRESS_FLOW.en.md`,
   `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`,
   `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`, `helios_v2/docs/ROADMAP.zh-CN.md`

## 7. Acceptance Criteria

1. `OsFileSystemChannelDriver` fully implements the `30` `ChannelDriver` protocol; its descriptor
   declares both directions, the four `fs_*` output ops, the `tool_result` input packet type,
   lifecycle ops, and config fields; static readiness is ready iff the sandbox root exists as a
   directory and is not-ready otherwise (verified by a focused test).
2. A valid `fs_write` executes inside the sandbox and a following `fs_read` returns the written
   content drained back as a `tool_result` `RawSignal` whose metadata carries the correlation
   provenance of the originating decision (verified network-free with the inline executor).
3. `fs_list` returns directory entries; `fs_modify` appends to an existing file and fails on a missing
   file; a write op while writes are disabled is rejected.
4. A path-escape attempt (absolute outside-sandbox path, `..` traversal, or symlink escape) is
   rejected, touches no file outside the sandbox, and surfaces as a failure `tool_result`; a
   structurally invalid packet returns a failed dispatch outcome and also enqueues a failure result.
5. Backlog overflow is bounded and counted; concurrent enqueue (worker thread) and drain (tick thread)
   are race-free with the thread-pool executor.
6. The generalized channel-bound assembly registers the OS driver alongside (or instead of) CLI, runs
   a tick, stays stable, and gates startup on the OS driver readiness; `channel_cli`-only behavior is
   unchanged; the default assemblies and the full `helios_v2/tests` suite remain green and
   network-free; the single-logging-mechanism guard test still passes.

## 8. Future Extension Scope

This requirement is the first effector driver and the result-reafference mechanism. The following are
explicitly anticipated future work, each via its own requirement package, and must preserve the owner
boundaries established here:

1. LLM-driven planner tool selection (`11` thought → `12` action → `13` planner function-calling) so
   the system **autonomously** chooses and binds an `fs_*` op rather than the op being supplied by a
   deterministic test or external driver. R84 ships the effector and the loop mechanism; autonomous
   tool selection is the next requirement.
2. Requirement `85`: OS command-execution driver with default-deny allowlist and `13`/`14` fail-closed
   governance (higher risk; pending owner sign-off on governance boundaries).
3. Requirement `86`: upgrading `17`/`23` consequence corroboration from "flow-completed" to
   "really-delivered, falsifiable" using these real effectors (closing blocker B4).
4. Real network/external drivers (QQ, Lark, voice) reusing the generalized multi-driver assembly.

None of these may be smuggled into this slice. R84 introduces only a local sandboxed file-system
effector with an injected executor (inline in tests), performs no process spawning and no network
I/O, does not make the planner autonomously select file tools, and moves no cognitive ownership into
the channel subsystem.
