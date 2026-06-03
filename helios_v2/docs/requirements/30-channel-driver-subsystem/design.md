# Requirement 30 - Channel driver subsystem framework design

## 1. Title

Requirement 30 - Channel driver subsystem framework

## 2. Design Overview

This design adds one capability owner, `helios_v2.channel`, structured as a Linux-kernel-driver-style subsystem:

1. a thin framework (`ChannelSubsystem`) that owns a driver registry plus two tick-boundary schedulers (inbound drain, outbound dispatch),
2. one uniform `ChannelDriver` protocol that every concrete driver implements (descriptor, config, lifecycle/management ops, async inbound receive, sync drain, sync outbound send),
3. a NAPI-style bounded drain: drivers receive asynchronously into a bounded backlog; the framework drains them at the tick boundary under a global budget, fairly, leaving remainder pending for the next tick,
4. a transport-intrinsic QoS marker on every inbound packet, carried opaquely on `RawSignal` and preserved onto `Stimulus`, used by the framework only for transport scheduling and interpreted as salience only by the `03` appraisal owner,
5. bounded outbound dispatch of planner-accepted decisions, respecting planner execution priority, publishing explicit dispatch outcomes,
6. fail-fast readiness for drivers that declare critical credentials.

The framework owns transport only. Normalization stays with `02` sensory (the framework emits `RawSignal`, sensory turns it into `Stimulus`). Salience stays with `03` appraisal. Channel selection and acceptance stay with `13` planner. Outward content shaping stays with `16`.

This requirement ships the framework and its contracts plus a deterministic fake driver for tests. The first real driver (CLI) is `31`. Composition wiring that replaces the inbound shim and the planner channel-state shim is deferred (it lands when a real driver is bound), so this slice is additive and the existing runtime stays green.

## 3. Current State and Gap

Current state:

1. `02` sensory owns `register_source` + `SensorySource` protocol + raw->stimulus normalization. `RawSignal` already carries `channel`, `modality`, and a free `metadata` mapping. `FirstVersionSensorySource` is a hardcoded shim.
2. `13` planner consumes `channel_descriptor_snapshot` / `channel_status_snapshot` from `PlannerBridgeRequest`, populated by `FirstVersionPlannerBridgeRequestBridge` with hardcoded `cli` data.
3. `25` LLM gateway established the pattern this design mirrors: a backend-neutral capability owner, a provider protocol, an injected first-version provider with lazy SDK import, a profile/registry, and a static-readiness dependency gate.
4. `helios_v1` provides a proven (debt-carrying) reference: `ChannelDescriptor`, `ChannelStatus`, `ChannelOpDescriptor`, `ChannelConfigSnapshot`, `ChannelManagementResult`, `ChannelGateway` registry, `OptionalChannelBootstrap*` dynamic registration.

Gap: no transport owner; inbound and planner channel-state are shims; no bounded drain/dispatch; no QoS marker.

## 4. Target Architecture

### 4.1 Owner and driver protocol

```
ChannelDriver (Protocol)                # one uniform driver API (Linux-driver-style)
    @property driver_id: str
    descriptor() -> ChannelDriverDescriptor
    # lifecycle / management (returns structured ChannelManagementResult)
    apply_management_op(op_name: str, payload: Mapping | None) -> ChannelManagementResult
    status() -> ChannelDriverStatus
    config_snapshot() -> ChannelConfigSnapshot
    # inbound: async receive happens inside the driver; drain is sync and bounded
    drain_inbound(budget: int) -> InboundDrainResult        # <= budget packets + pending count
    # outbound: sync send of one already-accepted decision
    send_outbound(packet: OutboundPacket) -> OutboundDispatchOutcome
    # readiness (fail-fast); content-agnostic, no network in the static path
    static_readiness() -> ChannelDriverReadiness
```

`ChannelSubsystem` (the framework, a dataclass owner):

```
ChannelSubsystem
    register_driver(driver) -> ChannelManagementResult       # runtime pluggable
    deregister_driver(driver_id) -> ChannelManagementResult  # teardown then remove
    apply_management_op(driver_id, op_name, payload) -> ChannelManagementResult
    drain_inbound(budget) -> SubsystemDrainResult            # NAPI-style, fair, bounded
    dispatch_outbound(decisions, budget) -> SubsystemDispatchResult
    channel_state_snapshot() -> ChannelStateSnapshot         # real state for the planner
    descriptors() / statuses()
    check_static_readiness(driver_ids) -> ChannelReadinessReport
```

The framework holds no cognitive policy. It is a registry + scheduler, exactly like a kernel driver framework.

### 4.2 Inbound flow (transport -> RawSignal -> sensory)

```
driver bg loop receives pkt --> driver bounded backlog (overflow policy + count)
   tick boundary:
   ChannelSubsystem.drain_inbound(budget)
     -> for each ready driver (fair, round-robin):
          driver.drain_inbound(remaining_budget) -> InboundPacket[]  (+ pending)
     -> map each InboundPacket -> RawSignal (preserve driver provenance + QoS marker in metadata)
     -> return SubsystemDrainResult(raw_signals, pending_by_driver, overflow_counts)
   composition source adapter (later) feeds raw_signals into 02 sensory.register_source/collect
```

The framework emits `RawSignal`; it does not normalize. The QoS marker is placed in `RawSignal.metadata` under the reserved key `channel_qos` (decision 5.4). Sensory preserves it onto `Stimulus.metadata` unchanged (sensory already passes metadata through).

### 4.3 NAPI-style bounded drain

1. `drain_inbound(budget)` iterates drivers that report pending packets (the "ready set"), round-robin, each `driver.drain_inbound(remaining)` returning at most `remaining` packets and its own pending count.
2. The loop stops when the global budget is exhausted or no driver has pending packets.
3. Drivers with remainder stay in the ready set; the next tick continues. This is the NAPI poll-list + budget + napi_complete analog.
4. Per-driver backlog is bounded; overflow applies the driver's documented policy and increments an overflow counter surfaced in the drain result.

### 4.4 Transport-intrinsic QoS marker

```
ChannelQosClass = Literal["control", "interactive", "bulk", "background"]   # transport-intrinsic
InboundPacket carries qos_class derived only from transport-visible facts.
```

The framework may order the ready set or choose drop victims by `qos_class` (transport scheduling only). It never maps `qos_class` to cognitive importance. The marker rides `RawSignal.metadata["channel_qos"]` (reserved key, see 5.4) and is preserved onto `Stimulus`. Only `03` appraisal interprets it as a salience input. First version: taxonomy + propagation only; multi-lane scheduling and selective dropping are design-reserved.

### 4.5 Outbound flow (planner decision -> driver)

```
13 planner publishes accepted ActionDecision (selected_channel_id, selected_op, params, execution_priority)
   tick boundary:
   ChannelSubsystem.dispatch_outbound(decisions, budget)
     -> sort by execution_priority (planner-provided), bounded by budget
     -> for each: target driver.send_outbound(OutboundPacket) -> OutboundDispatchOutcome
     -> return SubsystemDispatchResult(outcomes, deferred_for_next_tick)
   outcomes are published for writeback / evaluation
```

The framework does not re-select the channel; it uses `selected_channel_id`. Unknown/unavailable driver yields an explicit `driver_unavailable` outcome.

### 4.6 Planner channel-state provider

`channel_state_snapshot()` returns the real per-driver descriptor/status (supported ops, connected, ready). A later composition change feeds this into the planner request instead of the hardcoded snapshot. This requirement ships the provider; the wiring swap is deferred to when a real driver is bound.

### 4.7 Fail-fast readiness

Mirrors `25`: `check_static_readiness(driver_ids)` is deterministic and network-free (a driver reports whether its declared credential/resource is present). Composition can register `channel_drivers_ready` as a critical dependency when a critical driver is bound. CLI (`31`) declares no credential, so it is always ready and never trips the gate.

## 5. Data Structures

### 5.1 Driver-facing contracts (frozen)
- `ChannelDriverDescriptor`: `driver_id`, `display_name`, `input_packet_types: tuple[str,...]`, `output_ops: tuple[str,...]`, `management_ops: tuple[str,...]`, `config_fields: tuple[ChannelConfigField,...]`, `health_signals: tuple[str,...]`, `directions: tuple[Literal["inbound","outbound"],...]`.
- `ChannelConfigField`: `key`, `description`, `required`, `mutable_at_runtime`, `schema_hint`.
- `ChannelConfigSnapshot`: `driver_id`, `status`, `config_values: Mapping`, `mutable_fields: tuple[str,...]`, `validation_errors: tuple[str,...]`.
- `ChannelManagementResult`: `driver_id`, `op_name`, `success`, `status`, `message`, `error_code`, `payload: Mapping`.
- `ChannelDriverStatus = Literal["uninitialized","connected","disconnected","paused","error"]` (first-version minimal taxonomy; v1's 10-state set is reserved).
- `ChannelDriverReadiness`: `driver_id`, `ready: bool`, `detail: str`.

### 5.2 Inbound contracts (frozen)
- `ChannelQosClass = Literal["control","interactive","bulk","background"]`.
- `InboundPacket`: `packet_id`, `driver_id`, `packet_type: str`, `content: str`, `qos_class: ChannelQosClass`, `metadata: Mapping`.
- `InboundDrainResult` (driver-level): `packets: tuple[InboundPacket,...]`, `pending_remaining: int`, `overflow_count: int`.
- `SubsystemDrainResult` (framework-level): `raw_signals: tuple[RawSignal,...]`, `pending_remaining: int`, `drained_count: int`, `overflow_counts: Mapping[str,int]`.

The framework maps `InboundPacket -> RawSignal` with `signal_id=packet_id`, `source_name=driver_id`, `signal_type=packet_type`, `content=content`, `channel=driver_id`, and `metadata` including the QoS marker.

### 5.3 Outbound contracts (frozen)
- `OutboundPacket`: `packet_id`, `target_driver_id`, `op_name`, `payload: Mapping`, `execution_priority: int`, `provenance: Mapping` (decision/proposal ids).
- `OutboundDispatchOutcome`: `packet_id`, `target_driver_id`, `status: Literal["delivered","failed","driver_unavailable","dropped_overflow"]`, `detail: str`.
- `SubsystemDispatchResult`: `outcomes: tuple[OutboundDispatchOutcome,...]`, `dispatched_count: int`, `deferred_count: int`.

### 5.4 QoS marker carriage decision (resolved: metadata reserved key)
Decision: the QoS marker rides `RawSignal.metadata["channel_qos"]` as a reserved string-valued key. No `RawSignal`/`Stimulus` contract change is made.

Rationale (grounded in `02` sensory's actual responsibility):
1. `02` sensory is a narrow normalization owner. `_normalize_signal` passes `RawSignal.metadata` through to `Stimulus.metadata` verbatim (frozen `MappingProxyType`), never reading or validating any key. The metadata mapping is already the cross-owner opaque-provenance channel; QoS carriage is exactly that use.
2. `ChannelQosClass` is a transport-intrinsic type owned by `30` channel. A typed `qos_class` field on `RawSignal`/`Stimulus` would force `02` to reference a `30`-owned type, inverting the owner dependency direction (`02` is upstream of `30`). The only way to avoid the inversion with a typed field is to degrade it to `str`, which discards the sole benefit of a typed field while still mutating the sensory contract.
3. With the metadata key, typed enum validation stays fully inside the channel owner (enforced when constructing `InboundPacket.qos_class`); at the owner boundary it degrades to a reserved key + string value, which is precisely what the metadata channel exists for.

Carriage contract:
- The framework writes `RawSignal.metadata["channel_qos"] = <qos_class string>` when mapping `InboundPacket -> RawSignal`. The constant key is `CHANNEL_QOS_METADATA_KEY = "channel_qos"`, exported from `channel/contracts.py`.
- `02` sensory preserves it onto `Stimulus.metadata` unchanged (no sensory change).
- `03` appraisal is the only owner that reads `stimulus.metadata["channel_qos"]` as a salience input (out of scope for `30`; appraisal wiring is a later requirement).
- `sensory/contracts.py` is unchanged by this requirement.

## 6. Module Changes

1. `channel/contracts.py`: all contracts in section 5, the `ChannelDriver` protocol, the `ChannelSubsystemAPI` protocol, and `ChannelError`.
2. `channel/engine.py`: `ChannelSubsystem` (registry + drain + dispatch + readiness + state snapshot) and a deterministic `Fake/InMemoryChannelDriver` for tests (a real driver is `31`).
3. `channel/__init__.py`: export the public surface.
4. `composition/dependencies.py`: optional `channel_drivers_ready` capability + readiness provider, added only when a critical driver is bound (mechanism ships here; binding is later).
5. `sensory/contracts.py`: unchanged (QoS rides the `channel_qos` metadata reserved key; see 5.4).

## 7. Migration Plan

1. Additive: new package, no change to the assembled runtime in this slice (no driver is bound yet, drain/dispatch stages are not registered until a real driver + composition wiring land).
2. The framework + fake driver are validated in isolation. The existing 19-stage runtime and its tests are untouched.
3. Default rollout: off at composition until `31` (CLI driver) and the composition wiring that replaces the inbound shim and planner channel-state shim land. This requirement ships the owner and contracts so later requirements wire it in additively.

### 7.1 Forward-compatibility intent

The `ChannelDriver` protocol, the bounded drain/dispatch contracts, and the QoS taxonomy are the stable seams. Real drivers (CLI in `31`, then QQ/voice/vision), QoS-conditioned scheduling, and the composition swap build on these without changing the core contracts.

## 8. Failure Modes and Constraints

1. Backlog/queue overflow: explicit policy + counted; never silent or unbounded.
2. Budget exhaustion: remainder stays pending; never a tick explosion.
3. Unknown/unavailable target driver on dispatch: explicit `driver_unavailable` outcome; no fabricated transport.
4. Missing critical driver readiness: fail-fast through the dependency gate; no degraded transport.
5. The framework never normalizes, scores salience, re-selects channels, or shapes content.
6. No `logging`/`print`; guard test stays green.

## 9. Observability and Logging

1. No new logging mechanism. Drain counts, overflow counts, dispatch outcomes, and status transitions travel through formal owner contracts.
2. When the subsystem is later wired into the runtime, its stage execution is observed by the existing `21` kernel timeline; the subsystem itself emits nothing.

## 10. Validation Strategy

1. Contract tests (`test_channel_contracts.py`): construction/validation for descriptor, config snapshot, management result, inbound packet (QoS taxonomy enforcement), inbound/outbound drain/dispatch results; QoS taxonomy rejects unknown classes.
2. Engine tests (`test_channel_engine.py`) with a deterministic fake driver:
   - register/deregister at runtime; descriptor/status visible while registered, gone after deregister; deregister tears down first.
   - drain returns <= budget RawSignals across drivers, with explicit pending; a driver supplying more than budget retains remainder for the next drain; backlog overflow is bounded and counted.
   - each drained RawSignal carries a transport-intrinsic QoS marker in metadata, derived without reading content.
   - dispatch transports a decision to the target driver under budget, respects execution priority, and yields explicit outcomes for delivered/failed/unavailable/dropped; unknown driver -> driver_unavailable.
   - `channel_state_snapshot()` reports real per-driver state.
   - static readiness: a fake driver declaring an unmet credential reports not-ready; the readiness report is deterministic and network-free.
3. Guard + regression: `test_no_adhoc_logging_guard.py` green and `pytest helios_v2/tests -q` green and network-free.
