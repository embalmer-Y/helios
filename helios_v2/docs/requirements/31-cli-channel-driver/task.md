# Requirement 31 - CLI channel driver task plan

## 1. Title

Requirement 31 - CLI channel driver

## 2. Task Breakdown

1. Implement `CliDriverConfig` and `CliChannelDriver` in `channel/drivers/cli.py`, conforming fully to the `30` `ChannelDriver` protocol: descriptor (text input, reply_message output, lifecycle ops, config fields, both directions), `submit_line` into a bounded backlog, `drain_inbound` returning QoS-tagged text `InboundPacket`s under budget with empty-line skipping and counted overflow, `send_outbound` writing to the injected sink with explicit outcomes, lifecycle `apply_management_op` status machine, `config_snapshot`/update, and always-ready `static_readiness`.
2. Export the CLI driver from `channel/drivers/__init__.py` and `channel/__init__.py`.
3. Add `ChannelInboundDrainStage` and `ChannelOutboundDispatchStage` (plus their stage-result dataclasses) to `runtime/stages.py`.
4. Add `SubsystemBackedSensorySource`, a real planner `ChannelStateProvider`, and an outbound-decision collector to `composition/bridges.py`.
5. Add the opt-in channel-bound assembly seam and its stage-order variant to `composition/runtime_assembly.py`, registering the subsystem + CLI driver + the two new stages, swapping the subsystem-backed sensory source and the real planner channel-state provider, and registering `channel_drivers_ready`.
6. Add `--channel-cli` to `scripts/run_runtime_driver.py` for a real local round trip (reader adapter for real stdin; injected stdout writer).
7. Add CLI driver tests in `tests/test_channel_cli_driver.py` (network-free, injected in-memory I/O).
8. Add a channel-bound round-trip test plus an internal-only-no-input test to `tests/test_runtime_composition.py`.
9. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, `docs/BRAIN_ARCHITECTURE_COMPARISON.md`, and both `PROGRESS_FLOW` maps (channel transport now real for CLI; inbound/outbound shims replaced in the opt-in assembly).

## 3. Dependencies

1. `30 channel driver subsystem framework` provides the `ChannelDriver` protocol, `ChannelSubsystem`, bounded drain/dispatch, QoS taxonomy, and readiness.
2. `02 sensory ingress` provides the `SensorySource`/`RawSignal` boundary the inbound drain feeds.
3. `13 planner-bridge` provides the `ActionDecision`/channel-state shapes the dispatch and state provider align with.
4. `22 composition root` provides the assembly seam and stage registration.
5. `28 internal-only tick closure` guarantees a no-input tick still completes.
6. No real network or credential for any test; injected in-memory input/output covers all cases.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/channel/drivers/__init__.py`
2. `helios_v2/src/helios_v2/channel/drivers/cli.py`
3. `helios_v2/src/helios_v2/channel/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`
7. `helios_v2/scripts/run_runtime_driver.py`
8. `helios_v2/tests/test_channel_cli_driver.py`
9. `helios_v2/tests/test_runtime_composition.py`
10. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`, `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 5. Implementation Order

1. Implement and unit-test `CliChannelDriver` against the `30` protocol with injected I/O.
2. Add the inbound drain and outbound dispatch stages.
3. Add the composition adapters (subsystem-backed sensory source, real planner channel-state provider, outbound collector).
4. Add the opt-in channel-bound assembly seam and the stage-order variant.
5. Add the composition round-trip test and the internal-only-no-input test.
6. Add the optional `--channel-cli` driver entry point.
7. Update boundary, grounding, index, and both progress-flow maps.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_channel_cli_driver.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_channel_engine.py -q`
5. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
6. `pytest helios_v2/tests -q`
7. Optional real local run: `python helios_v2/scripts/run_runtime_driver.py --channel-cli --ticks 3` (reads real stdin; offline, no network).

## 7. Completion Criteria

1. `CliChannelDriver` fully conforms to the `30` `ChannelDriver` protocol with a real descriptor and always-ready static readiness.
2. Injected operator lines drain as QoS-tagged `RawSignal` objects under budget (empty lines skipped, overflow bounded/counted); outbound decisions render to the injected sink with explicit outcomes; lifecycle/config ops behave correctly.
3. The opt-in channel-bound assembly runs a full local round trip (line -> stimulus -> chain -> externalize -> reply rendered to sink) in a network-free test; an internal-only no-input tick still completes.
4. The default assemblies and the full `helios_v2/tests` suite remain green and network-free; the logging-guard test passes.
5. The CLI driver introduces no salience, normalization, channel-selection, or content-shaping logic, and no external network transport.
