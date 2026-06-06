# Requirement 53 - Workload pressure from the interoceptive afferent (tasks)

## 1. Task Breakdown

### Task 1 - Owner-neutral workload-pressure helper + bridge wiring
In `helios_v2/src/helios_v2/composition/bridges.py`, add `_WORKLOAD_PRESSURE_CHANNELS = frozenset({"cpu", "memory"})` and `_interoceptive_workload_pressure(frame, default=0.1)` reading the `02` `SensoryIngressStageResult` batch for interoceptive cpu/memory `pressure_value`s (from the reserved metadata keys), returning the bounded max or the default when none present (skip unrecognized/out-of-range/non-numeric; never raise). Replace `workload_pressure=0.1` with `workload_pressure=_interoceptive_workload_pressure(frame)` in both `NeuromodulatorAwareThoughtGateSignalBridge` and `FirstVersionThoughtGateSignalBridge`.

### Task 2 - Validation
Extend `test_runtime_composition.py`: high cpu/memory sampler raises `contributing_signals["workload_pressure"]` above 0.1 (equals max channel) and lowers the gate score vs at-rest; at-rest sampler yields real `0.0`; no interoceptive source keeps `0.1`; a very high load with low continuation exercises the block path. Keep network-free (fake sampler) and the logging guard green.

### Task 3 - Documentation truth sync
Update `index.md` (R53 row), `ARCHITECTURE_BOUNDARIES.md` (migration-state item: `09` `workload_pressure` grounded in the interoceptive afferent; second interoceptive consumer), `BRAIN_ARCHITECTURE_COMPARISON.md` (narrow the `09-11` gate-input shim note; narrow `gap_interoceptive_signal_source` second-consumer note), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`09` + interoception next-step), both `PROGRESS_FLOW` maps (note `09` workload now real under interoceptive assembly; update last-synced + baseline count).

## 2. Dependencies

1. Task 1 is independent (uses the existing `02` batch + R50 reserved metadata keys).
2. Task 2 depends on Task 1.
3. Task 3 depends on Task 2 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (Task 1)
2. `helios_v2/tests/test_runtime_composition.py` (Task 2)
3. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 3)

## 4. Implementation Order

1. Task 1 (helper + wiring).
2. Task 2 (validation).
3. Task 3 (doc sync).

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_runtime_composition.py -q -k "workload or interocept"`.
2. Final: `pytest helios_v2/tests -q` full suite green and network-free; logging guard green.

## 6. Completion Criteria

1. The gate-signal bridge derives `workload_pressure` from the `02` interoceptive cpu/memory load stimuli (bounded, monotonic, deterministic), surfacing in `contributing_signals["workload_pressure"]`; the `09` gate weight/threshold are unchanged.
2. High load raises `workload_pressure` above 0.1 and lowers the gate score (and can block at high load + low continuation); no interoceptive source keeps `0.1` byte-for-byte; unrecognized facts contribute nothing without raising.
3. The projection is owner-neutral (no gate score in the bridge, no interoception-owner import).
4. Full suite green and network-free; logging guard green.
5. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set.
