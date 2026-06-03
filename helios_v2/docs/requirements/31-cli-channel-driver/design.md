# Requirement 31 - CLI channel driver design

## 1. Title

Requirement 31 - CLI channel driver

## 2. Design Overview

This design implements the first concrete `ChannelDriver` from `30`: a local CLI driver, and wires the channel subsystem into the assembled runtime through an explicit opt-in seam.

The CLI driver:

1. receives operator lines through an injected input source into a bounded inbound backlog (async relative to the tick),
2. drains queued lines as transport-intrinsic-QoS-tagged `InboundPacket` objects under the framework budget,
3. sends outbound decisions to an injected output sink,
4. exposes descriptor, config, lifecycle ops, status, health, and always-ready static readiness.

Composition gains an opt-in `assemble_runtime(channel_cli=True)`-style path that registers the channel subsystem with a CLI driver, adds an inbound drain stage (before sensory normalization) and an outbound dispatch stage (after planner), exposes the CLI driver's real channel state to the planner, and feeds drained `RawSignal` objects into the sensory owner. The default assembly is unchanged; tests use injected in-memory I/O.

This keeps every owner boundary: CLI driver = transport only; sensory normalizes; appraisal scores; planner selects/accepts; outward-expression shapes content.

## 3. Current State and Gap

Current state:

1. `30` ships `ChannelSubsystem`, the `ChannelDriver` protocol, bounded drain/dispatch, QoS taxonomy, readiness, and a fake driver, but no real driver and no runtime wiring.
2. The assembled runtime's inbound is `FirstVersionSensorySource` (hardcoded "hello runtime"); the planner channel state is hardcoded in `FirstVersionPlannerBridgeRequestBridge`.
3. `02` sensory accepts any `SensorySource`; `13` planner consumes channel snapshots from its request.

Gap: no concrete driver; the subsystem is not connected to sensory (inbound) or planner/dispatch (outbound).

## 4. Target Architecture

### 4.1 CLI driver

```
CliChannelDriver (implements ChannelDriver)
    driver_id = "cli"
    __init__(input_source: Callable[[], tuple[str,...]] | InputAdapter,
             output_sink: Callable[[str], None],
             config: CliDriverConfig)
    descriptor() -> ChannelDriverDescriptor(
        input_packet_types=("text",), output_ops=("reply_message",),
        management_ops=(init,connect,disconnect,deinit,pause,resume,health_check,get_config,update_config),
        directions=("inbound","outbound"), ...)
    # async-relative-to-tick: lines arrive via submit_line() (called by a reader adapter
    # or, in tests, directly) into a bounded deque
    submit_line(text: str) -> None            # enqueue into bounded backlog (overflow policy)
    drain_inbound(budget) -> InboundDrainResult   # <= budget non-empty lines as text InboundPackets, qos=interactive
    send_outbound(packet) -> OutboundDispatchOutcome   # write payload text to output_sink when connected
    apply_management_op(op, payload) -> ChannelManagementResult   # status machine
    status() -> ChannelDriverStatus
    config_snapshot() / update via op
    static_readiness() -> ready=True (no credential)
```

QoS: CLI operator text is tagged `interactive` (or `control` for management-style lines if later distinguished); the marker is transport-intrinsic and set without reading content meaning.

The driver's "async" is modeled by `submit_line` enqueuing into a bounded backlog; a production reader adapter (a background thread reading real stdin) calls `submit_line`, while tests call it directly. The driver never calls `print`; it writes through `output_sink`.

### 4.2 Inbound drain stage (channel-bound assembly only)

A new runtime stage `ChannelInboundDrainStage` runs at the start of the tick (before/with sensory). It calls `subsystem.drain_inbound(budget)` and exposes the resulting `RawSignal` tuple. The sensory owner consumes these via a `SubsystemBackedSensorySource` adapter: an adapter implementing `SensorySource` whose `emit_raw_signals()` returns the drained signals for the current tick. Sensory then normalizes them into stimuli as today. Normalization stays with sensory.

```
tick:
  ChannelInboundDrainStage -> subsystem.drain_inbound(budget) -> raw_signals (this tick)
  SubsystemBackedSensorySource.emit_raw_signals() returns those raw_signals
  sensory.collect_stimuli() normalizes -> StimulusBatch  (unchanged sensory behavior)
```

### 4.3 Outbound dispatch stage (channel-bound assembly only)

A new runtime stage `ChannelOutboundDispatchStage` runs after the planner stage. It collects planner-accepted decisions for the tick (an executed/accepted `ActionDecision` with a selected channel), converts them to `OutboundPacket` objects, and calls `subsystem.dispatch_outbound(packets, budget)`. Dispatch outcomes are exposed on the stage result for writeback/evaluation. The planner still owns selection/acceptance; the stage only transports.

### 4.4 Planner channel-state provider (channel-bound assembly only)

In the channel-bound assembly, the planner request bridge sources `channel_descriptor_snapshot` / `channel_status_snapshot` from `subsystem.channel_state_snapshot()` instead of the hardcoded dict. This makes the planner consume real CLI driver state. The default (non-channel) assembly keeps the existing shim, so existing tests are unaffected.

### 4.5 Composition seam

`assemble_runtime(..., channel_cli: bool = False)` (or a dedicated `assemble_channel_runtime(...)`): when set, constructs the `ChannelSubsystem`, registers a `CliChannelDriver` with injected I/O, registers the inbound drain and outbound dispatch stages, swaps in the subsystem-backed sensory source and the real planner channel-state provider, and registers `channel_drivers_ready` as a dependency. The canonical stage order is extended for this assembly variant (the 19-stage default stays as is for the non-channel assembly). Exact stage-order integration is finalized at implementation (the drain stage precedes sensory; the dispatch stage follows planner).

### 4.6 Round trip

```
submit_line("hello") -> backlog
tick:
  drain -> RawSignal("hello", qos=interactive)
  sensory -> Stimulus
  ... cognition chain ... thought externalizes -> planner accepts -> ActionDecision(cli, reply_message)
  dispatch stage -> subsystem.dispatch_outbound -> CliChannelDriver.send_outbound -> output_sink("...reply...")
```

## 5. Data Structures

1. `CliDriverConfig` (frozen): `driver_id="cli"`, `user_label`, `session_label`, `banner_enabled`, `max_backlog`.
2. `CliChannelDriver`: holds a bounded `deque` backlog, injected `output_sink: Callable[[str], None]`, status field, config.
3. `SubsystemBackedSensorySource` (composition adapter, implements `SensorySource`): wraps the latest drained `RawSignal` tuple for the current tick.
4. New stage results: `ChannelInboundDrainStageResult(raw_signals, pending_remaining, overflow_counts)`, `ChannelOutboundDispatchStageResult(outcomes, dispatched_count, deferred_count)`.
5. No change to `30` core contracts; no change to `02`/`13` owner contracts (adapters only).

## 6. Module Changes

1. `channel/drivers/cli.py`: `CliChannelDriver`, `CliDriverConfig`.
2. `channel/drivers/__init__.py` + `channel/__init__.py`: export the CLI driver.
3. `runtime/stages.py`: `ChannelInboundDrainStage`, `ChannelOutboundDispatchStage`, and their stage-result dataclasses.
4. `composition/bridges.py`: `SubsystemBackedSensorySource`, a real `ChannelStateProvider` for the planner request bridge, and an outbound-decision collector.
5. `composition/runtime_assembly.py`: the opt-in channel-bound assembly seam and its stage-order variant.
6. `scripts/run_runtime_driver.py`: optional `--channel-cli` to run a real local round trip (reads real stdin via a reader adapter, writes stdout via the injected sink).

## 7. Migration Plan

1. Additive: the default assembly and its tests are untouched; the channel-bound assembly is opt-in.
2. Tests use injected in-memory input (`submit_line`) and an in-memory output sink (a list collector), so the suite stays network-free and deterministic.
3. Default rollout: the channel-bound assembly is opt-in in this slice. Making it the default runnable runtime waits for a real external driver (later requirement).

### 7.1 Forward-compatibility intent

The CLI driver proves the `ChannelDriver` protocol and the inbound/outbound stage integration. Real external drivers reuse the same protocol and the same stages; only the driver and its readiness differ. The composition seam generalizes from "CLI bound" to "arbitrary drivers bound".

## 8. Failure Modes and Constraints

1. Backlog overflow: bounded deque + documented policy + counted, never silent.
2. Send while disconnected/paused: explicit non-delivered outcome, no write.
3. Unknown target driver on dispatch: framework yields `driver_unavailable` (from `30`).
4. The driver never normalizes, scores, re-selects, or semantically shapes content.
5. No `print`/`logging`; the driver writes only through its injected sink; guard test stays green.
6. No external transport: CLI is local only; real stdin is read only by an injected reader adapter in the driver entry point, never in tests.

## 9. Observability and Logging

1. No new logging mechanism. Drain/dispatch facts travel through the `30` contracts and the stage results; the `21` kernel timeline observes the new stages when the channel-bound runtime runs.
2. The output sink is an injected callable; production may pass a stdout writer, but the code never calls `print`.

## 10. Validation Strategy

1. CLI driver tests (`test_channel_cli_driver.py`): protocol conformance; submit_line + drain returns QoS-tagged text packets under budget with empty-line skipping; backlog overflow bounded/counted; send_outbound writes to the injected sink and returns delivered; send while disconnected returns non-delivered; lifecycle ops transition status; config update validates; static readiness always ready.
2. Composition round-trip test (`test_runtime_composition.py`): the opt-in channel-bound assembly drains an injected operator line into a stimulus, runs the chain, and dispatches an externalizing decision to the injected sink (assert the sink received the reply); an internal-only tick with no input completes without error; the default assembly is unchanged.
3. Guard + regression: `test_no_adhoc_logging_guard.py` green and `pytest helios_v2/tests -q` green and network-free.
