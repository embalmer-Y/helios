# Requirement 31 - CLI channel driver

## 1. Background and Problem

Requirement `30` establishes the channel driver subsystem framework: a Linux-driver-style owner (`helios_v2.channel`) with a uniform `ChannelDriver` protocol, a runtime-pluggable registry, NAPI-style bounded inbound drain emitting `RawSignal` objects, bounded outbound dispatch of planner-accepted decisions, transport-intrinsic QoS marking, and fail-fast readiness. But `30` ships only the framework plus a deterministic fake driver for tests. No real transport driver exists, and the framework is not yet wired into the assembled runtime.

To prove the framework end to end and to give Helios its first real bidirectional transport with zero external side effects, the first concrete driver should be a local CLI driver: it receives operator text from a local input stream (stdin-style) and sends Helios output to a local output sink (stdout-style). CLI is the right first driver because it is local, low-frequency, requires no credentials, and has no network blast radius, so it validates the full driver protocol (descriptor, config, lifecycle ops, async inbound receive into a bounded backlog, sync drain, sync outbound send, QoS marking) and the framework's drain/dispatch/registry behavior without introducing any external dependency.

This requirement also performs the first composition wiring that connects the channel subsystem into the runnable runtime through an explicit opt-in seam, so a real local round trip (operator types a line, it becomes a stimulus; Helios externalizes, the reply is written to the CLI sink) becomes observable, while keeping the default test assembly network-free and deterministic.

## 2. Goal

Implement a local CLI channel driver that conforms to the `30` `ChannelDriver` protocol, receiving operator text asynchronously into a bounded inbound backlog and draining it as transport-intrinsic-QoS-tagged `RawSignal` objects, sending Helios outbound decisions to a local output sink, exposing descriptor/config/lifecycle/health/readiness, and wire the channel subsystem into the assembled runtime through an explicit opt-in seam so a local CLI round trip works, while introducing no external side effects, no cognitive evaluation, no normalization ownership, and no degraded transport.

## 3. Functional Requirements

### 3.1 Driver conformance
1. The CLI driver must implement the `30` `ChannelDriver` protocol fully: `driver_id`, `descriptor`, `apply_management_op`, `status`, `config_snapshot`, `drain_inbound`, `send_outbound`, and `static_readiness`.
2. The driver descriptor must declare its real capabilities: text input packet type, a local-reply output op, its management ops, its config fields, and its directions (inbound and outbound).
3. The driver must declare no critical external credential; its static readiness must always report ready (CLI has no network dependency).

### 3.2 Inbound (local receive -> bounded backlog -> drain)
1. The driver must accept operator input lines through an injected input source (for example a callable or stream adapter) into a bounded inbound backlog, asynchronously relative to the tick.
2. On `drain_inbound(budget)`, the driver must return at most `budget` queued lines as `InboundPacket` objects with a transport-intrinsic QoS marker, plus the pending-remaining count. Empty lines are skipped.
3. Backlog overflow must apply the framework's bounded overflow policy with a counted, non-silent outcome.
4. The QoS marker on CLI inbound packets must be transport-intrinsic only (for example a fixed control/interactive class for local operator text); the driver must not read the line content to decide importance.

### 3.3 Outbound (decision -> local sink)
1. On `send_outbound(packet)`, the driver must render the packet payload to its injected local output sink and return an explicit `OutboundDispatchOutcome` (delivered or failed).
2. The driver must not shape or rewrite outward content semantically; it transports the text it is given. (Any expression styling remains owned by `16`, not the driver.)
3. When the driver is not connected/paused, an outbound send must return an explicit non-delivered outcome rather than writing.

### 3.4 Lifecycle and config
1. The driver must implement the lifecycle management ops (init, connect, disconnect, deinit, pause, resume, health_check) with explicit status transitions, consistent with the `30` status taxonomy.
2. The driver must own its config snapshot (for example session/user labels, banner toggle) with validated runtime updates through the config op.

### 3.5 Composition wiring (opt-in)
1. Composition must provide an explicit opt-in way to assemble a runtime with the channel subsystem registered and a CLI driver bound, including the inbound and outbound stages that drain into sensory and dispatch planner-accepted decisions.
2. When the channel subsystem is bound, the CLI driver's real channel state must be exposed to the planner (replacing the hardcoded channel-state snapshot for that assembly), and the inbound drain must feed the sensory owner (replacing the hardcoded `FirstVersionSensorySource` for that assembly).
3. The default test assembly must remain network-free and deterministic. The CLI driver uses injected in-memory input/output for tests, never real stdin/stdout in the suite.
4. No degraded path: if the bound channel subsystem cannot satisfy its declared readiness, startup fails fast (CLI declares no credential, so it passes; the mechanism still routes through the gate).

### 3.6 End-to-end round trip
1. With the channel subsystem bound and a CLI driver fed an operator line through the injected input, a tick must drain that line into a `RawSignal`, the cognition chain must run, and when the thought owner externalizes, the planner-accepted decision must be dispatched to the CLI driver and rendered to the injected output sink, observable in a focused test.
2. A tick with no operator input and no externalization must complete without error (internal-only tick closure from `28` still holds).

## 4. Non-Functional Requirements

1. Performance: CLI inbound drain and outbound dispatch are bounded by the framework budgets; the driver's async receive must not block the tick.
2. Reliability: with injected in-memory input/output, the CLI driver and the bound runtime are deterministic and reproducible; no real stdin/stdout in tests.
3. Observability and logging: the driver must not introduce a second logging mechanism and must not use `logging` or `print` (it writes to its injected sink, which in production may be stdout but is passed in, not a `print` call). Transport facts travel through the `30` contracts and the `21` surface.
4. Compatibility and migration: additive. The CLI-bound assembly is an explicit opt-in; the existing default assemblies and tests are unaffected.

## 5. Code Behavior Constraints

1. The CLI driver lives in `helios_v2.channel` (for example `channel/drivers/cli.py`) and depends only on the `30` protocol and contracts.
2. The driver must not compute salience, must not normalize into stimuli, must not re-decide channel selection, and must not semantically shape outward content.
3. Inbound backlog and outbound behavior must respect the framework's bounded/overflow semantics; no unbounded buffering.
4. The driver must write only to its injected output sink and read only from its injected input source; it must not call `print` or touch real stdio except through the injected adapter chosen by the driver entry point.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/channel/drivers/__init__.py`
2. `helios_v2/src/helios_v2/channel/drivers/cli.py`
3. `helios_v2/src/helios_v2/channel/__init__.py` (export the CLI driver)
4. `helios_v2/src/helios_v2/runtime/stages.py` (inbound drain stage and outbound dispatch stage, only for the channel-bound assembly)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in channel-bound assembly seam)
6. `helios_v2/src/helios_v2/composition/bridges.py` (real channel-state provider and inbound source adapter for the bound assembly)
7. `helios_v2/tests/test_channel_cli_driver.py`
8. `helios_v2/tests/test_runtime_composition.py` (channel-bound round-trip test)
9. `helios_v2/scripts/run_runtime_driver.py` (optional `--channel-cli` real local run)
10. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`, `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The CLI driver fully implements the `30` `ChannelDriver` protocol and declares a real descriptor with text input, a local-reply output op, lifecycle ops, config fields, and both directions; its static readiness is always ready.
2. Operator lines injected through the in-memory input are drained as QoS-tagged `RawSignal` objects under the framework budget, with empty lines skipped and overflow bounded and counted.
3. An outbound decision dispatched to the CLI driver renders to the injected output sink and returns a delivered outcome; a send while disconnected/paused returns an explicit non-delivered outcome.
4. Lifecycle ops drive valid status transitions and config updates validate at the driver boundary.
5. An explicit opt-in channel-bound assembly runs a full local round trip: an injected operator line becomes a stimulus, the chain runs, and an externalizing decision is rendered to the injected sink, verified by a focused network-free test; an internal-only tick with no input still completes.
6. The default assemblies and the full `helios_v2/tests` suite remain green and network-free, and the single-logging-mechanism guard test still passes.

## 8. Future Extension Scope

This requirement is the first concrete driver and the first composition wiring of the channel subsystem. The following are explicitly anticipated future extensions, each via its own requirement package, and must preserve the owner boundaries established here:

1. Real network/external drivers (QQ, voice STT/TTS, vision), each with its own readiness gate and external side effects.
2. Making a channel-bound assembly (rather than the shim) the default runnable runtime once a real external driver is operational.
3. QoS-conditioned multi-lane scheduling once multiple high-frequency drivers coexist.
4. Richer CLI management commands and interactive operator affordances.

None of these may be smuggled into this slice. This requirement introduces only a local CLI driver with injected in-memory I/O in tests, does not introduce external network transport, and does not move any cognitive ownership into the channel subsystem.
