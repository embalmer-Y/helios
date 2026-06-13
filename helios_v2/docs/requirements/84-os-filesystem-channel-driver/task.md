# Requirement 84 - OS file-system channel driver task plan

## 1. Title

Requirement 84 - OS file-system channel driver (sandboxed effector with result reafference)

## 2. Task Breakdown

1. Implement the executor seam in `channel/drivers/os_fs.py`: the `FileOpExecutor` protocol,
   `InlineFileOpExecutor` (synchronous, for tests), and `ThreadPoolFileOpExecutor` (bounded
   `concurrent.futures.ThreadPoolExecutor`, for production).
2. Implement `OsFileSystemDriverConfig` (sandbox root + bounds + write flag) with fail-fast
   `__post_init__` and a stored resolved sandbox root.
3. Implement `OsFileSystemChannelDriver` conforming to the `30` `ChannelDriver` protocol: descriptor
   (both directions, four `fs_*` ops, `tool_result` input type, lifecycle/config ops), lifecycle status
   machine, `status`/`config_snapshot`, thread-safe bounded backlog, `static_readiness` from sandbox
   presence.
4. Implement `send_outbound`: not-connected guard, structural validation with double-write-back on
   rejection, executor submission on acceptance returning a `delivered` outcome.
5. Implement `work()` + the four op handlers + `_resolve_in_sandbox` path-escape defense +
   `_enqueue_result` (JSON content, correlation metadata, bounded backlog with counted overflow) +
   `drain_inbound`.
6. Export the new symbols from `channel/drivers/__init__.py` and `channel/__init__.py`.
7. Add `RuntimeProfile.channel_drivers`, extend the mutual-exclusion validation, and generalize the
   channel-bound assembly block from single-CLI to the effective-driver-set in
   `composition/runtime_assembly.py`, preserving the cli-only path byte-for-byte.
8. Add `tests/test_channel_os_fs_driver.py` (driver unit + subsystem loop + concurrency).
9. Add the multi-driver channel-bound assembly tests to `tests/test_runtime_composition.py`.
10. Update `docs/requirements/index.md` (row 84), `OWNER_GUIDE.*`, both `PROGRESS_FLOW` maps,
    `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and `ROADMAP.zh-CN.md`
    (move R84 to done; add the deferred LLM-driven planner tool-selection requirement).

## 3. Dependencies

1. `30 channel driver subsystem` — the `ChannelDriver` protocol, `ChannelSubsystem` drain/dispatch,
   QoS taxonomy, readiness, and the `InboundPacket`/`OutboundPacket`/`RawSignal` shapes.
2. `31 CLI channel driver` — the driver implementation pattern and the channel-bound assembly seam
   being generalized (`SubsystemBackedSensorySource`, `ChannelSubsystemStateProvider`, the two
   transport stages, `ChannelReadinessDependencyProvider`), all reused unchanged.
3. `02 sensory ingress` — the `SensorySource`/`RawSignal` boundary the result reafference feeds.
4. `28 internal-only tick closure` — a tick with no planner-accepted file op still completes.
5. Python standard library only (`pathlib`, `concurrent.futures`, `threading`, `json`); no new
   third-party dependency; no network, no process spawning.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/channel/drivers/os_fs.py` (new)
2. `helios_v2/src/helios_v2/channel/drivers/__init__.py`
3. `helios_v2/src/helios_v2/channel/__init__.py`
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
5. `helios_v2/tests/test_channel_os_fs_driver.py` (new)
6. `helios_v2/tests/test_runtime_composition.py`
7. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/OWNER_GUIDE.md`,
   `helios_v2/docs/OWNER_GUIDE.zh-CN.md`, `helios_v2/docs/PROGRESS_FLOW.en.md`,
   `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`,
   `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`, `helios_v2/docs/ROADMAP.zh-CN.md`

## 5. Implementation Order

1. Implement the executor seam, config, and driver in `os_fs.py`; unit-test against the `30` protocol
   with the inline executor.
2. Add path-escape defense and the four op handlers; unit-test ops + escape rejection + failure
   write-back.
3. Add the subsystem loop test (dispatch → execute inline → drain → `RawSignal`) and the
   thread-pool concurrency test.
4. Generalize the channel-bound assembly (`channel_drivers` field, effective-driver-set, mutual
   exclusion); preserve cli-only behavior.
5. Add the composition multi-driver tests.
6. Run the focused suites, then the full network-free suite and the guards.
7. Update index, owner guide, both progress-flow maps, boundary, grounding, and roadmap docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_channel_os_fs_driver.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_channel_engine.py helios_v2/tests/test_channel_cli_driver.py -q`
5. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`
6. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `OsFileSystemChannelDriver` fully conforms to the `30` `ChannelDriver` protocol with a real
   descriptor (both directions, four `fs_*` ops, `tool_result` input type) and sandbox-presence
   static readiness.
2. A valid `fs_write`/`fs_read` executes inside the sandbox and the read result drains back as a
   `tool_result` `RawSignal` with correlation provenance; `fs_list`/`fs_modify` behave per spec; a
   write while disabled is rejected.
3. Path-escape attempts (absolute outside, `..`, symlink) are rejected with no out-of-sandbox file
   touched and a failure reafference; structural rejection double-writes-back; overflow is bounded and
   counted; concurrent enqueue/drain is race-free with the thread-pool executor.
4. The generalized channel-bound assembly registers the OS driver (alone or with CLI), gates startup
   on its readiness, runs a stable tick, and rejects `external_signal_source` + channel binding;
   cli-only behavior is byte-for-byte unchanged.
5. The default assemblies and the full `helios_v2/tests` suite remain green and network-free; the
   logging-guard and owner-boundary-guard tests pass.
6. The driver introduces no salience, normalization, channel-selection, content-shaping, or
   result-interpretation logic, no process spawning, and no network transport; index, owner guide,
   both progress-flow maps, boundary, grounding, and roadmap docs are updated in the same change set.
