# Requirement 30 - Channel driver subsystem framework task plan

## 1. Title

Requirement 30 - Channel driver subsystem framework

## 2. Task Breakdown

1. Add driver-facing contracts to `channel/contracts.py`: `ChannelDriverDescriptor`, `ChannelConfigField`, `ChannelConfigSnapshot`, `ChannelManagementResult`, `ChannelDriverStatus`, `ChannelDriverReadiness`, plus `ChannelError`.
2. Add inbound contracts: `ChannelQosClass` taxonomy, `InboundPacket`, `InboundDrainResult`, `SubsystemDrainResult`.
3. Add outbound contracts: `OutboundPacket`, `OutboundDispatchOutcome`, `SubsystemDispatchResult`.
4. Define the `ChannelDriver` protocol and the `ChannelSubsystemAPI` protocol.
5. Implement `ChannelSubsystem` in `channel/engine.py`: driver registry (register/deregister with teardown), `apply_management_op`, NAPI-style bounded fair `drain_inbound` (ready set, per-driver budget, pending carry, overflow counts) mapping `InboundPacket -> RawSignal` with the QoS marker in metadata, bounded `dispatch_outbound` respecting execution priority, `channel_state_snapshot`, and `check_static_readiness`.
6. Implement a deterministic in-memory fake driver in `channel/engine.py` (or a test helper) for validation; no real transport.
7. Export the public surface from `channel/__init__.py`.
8. Add `channel_drivers_ready` capability + readiness dependency provider to `composition/dependencies.py` (mechanism only; not wired into default assembly in this slice).
9. Add contract tests in `tests/test_channel_contracts.py`.
10. Add engine tests in `tests/test_channel_engine.py` (register/deregister, bounded drain + pending + overflow, QoS marker presence, dispatch outcomes + priority, channel state snapshot, static readiness), all network-free.
11. Decide and implement the QoS carriage (metadata key `channel_qos` preferred; typed `qos_class` passthrough on `RawSignal`/`Stimulus` only if chosen).
12. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/BRAIN_ARCHITECTURE_COMPARISON.md`, and both `PROGRESS_FLOW` maps (channel owner now exists as framework; transport gap narrowing).

## 3. Dependencies

1. `02 sensory ingress` provides the `RawSignal`/`SensorySource` boundary the inbound drain emits into.
2. `13 planner-bridge` provides the `ActionDecision`/channel-state shapes the outbound dispatch and state snapshot align with.
3. `25 LLM gateway` provides the capability-owner + readiness-gate pattern this owner mirrors.
4. `helios_v1` `helios_io` is the (debt-carrying) reference for descriptor/status/ops/registry shapes.
5. No real network or credential for any test; a deterministic fake driver covers all cases.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/channel/__init__.py`
2. `helios_v2/src/helios_v2/channel/contracts.py`
3. `helios_v2/src/helios_v2/channel/engine.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/src/helios_v2/sensory/contracts.py` (only if typed QoS passthrough is chosen)
6. `helios_v2/tests/test_channel_contracts.py`
7. `helios_v2/tests/test_channel_engine.py`
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
10. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 5. Implementation Order

1. Land the contracts and protocols in `channel/contracts.py`.
2. Implement `ChannelSubsystem` registry + lifecycle in `channel/engine.py`; add the fake driver; unit-test register/deregister.
3. Implement bounded NAPI-style `drain_inbound` + QoS marking; test budget/pending/overflow/QoS.
4. Implement bounded `dispatch_outbound` + `channel_state_snapshot` + readiness; test outcomes/priority/state/readiness.
5. Export from `channel/__init__.py`; add the `channel_drivers_ready` dependency plumbing (unbound).
6. Update boundary, grounding, index, and both progress-flow maps.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_channel_contracts.py helios_v2/tests/test_channel_engine.py -q`
4. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
5. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `helios_v2.channel` exposes the uniform `ChannelDriver` protocol, the driver descriptor/config/management/status/readiness contracts, the bounded inbound (QoS-tagged) and outbound contracts, `ChannelError`, and the `ChannelSubsystem` owner.
2. Runtime register/deregister works with descriptor/status discoverability and explicit teardown.
3. NAPI-style drain is bounded by budget with explicit pending carry and bounded counted overflow; each drained `RawSignal` carries a transport-intrinsic QoS marker derived without reading content.
4. Outbound dispatch is bounded, priority-respecting, and publishes explicit outcomes; the owner exposes real per-driver channel state for the planner.
5. Static readiness is deterministic and network-free and can gate startup when a critical driver is bound; no degraded transport mode exists.
6. The owner introduces no normalization, salience, channel-selection, or content-shaping logic; the logging-guard test passes and `pytest helios_v2/tests -q` is green and network-free.
