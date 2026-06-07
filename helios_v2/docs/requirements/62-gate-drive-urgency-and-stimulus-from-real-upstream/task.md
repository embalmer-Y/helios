# Requirement 62 - Thought-Gate Drive-Urgency from the Prior-Tick Autonomy Drive

> Scope: converged to the `drive_urgency_signal` de-shim only. The `selected_stimuli` projection
> is deferred to R63 (see the scope note in `requirement.md`).

## 1. Task Breakdown

### T1 - Add the cold-start constant, holder, and helper
In `composition/bridges.py`, add `_DRIVE_URGENCY_COLD_START = 0.7`, a `PriorDriveUrgencyHolder`
(`set_from_drive_state` clamps the published `outward_drive`; `current()` returns it; defaults to
the cold start), and `_drive_urgency_signal(holder)` (holder value or cold-start when no holder).

### T2 - Rewire both gate-signal bridges
Give `FirstVersionThoughtGateSignalBridge` and `NeuromodulatorAwareThoughtGateSignalBridge` an
optional `drive_urgency_holder` field and read `_drive_urgency_signal(self.drive_urgency_holder)`
for `drive_urgency_signal`. Remove the `0.7` literal from snapshot construction. Leave
`selected_stimuli` as its first-version constant (R63).

### T3 - Wire the holder + post-tick carry in assembly
In `runtime_assembly.py`, construct one `PriorDriveUrgencyHolder`, pass it to the wired
gate-signal bridge, store it on `RuntimeHandle`, and add `_carry_drive_urgency(result)` to the
post-tick carry sequence (reads the `18` `drive_state` and calls `set_from_drive_state`).

### T4 - Tests
Add focused tests in `test_runtime_composition.py`: first tick uses cold-start `0.7`; an
externalizing prior tick raises tick 2's gate `drive_urgency_signal` to the clamped prior drive
(`1.0`); the carried urgency stays bounded `[0,1]` across ticks.

### T5 - Documentation
Update `index.md` (row 62 converged scope + note R63 defers `selected_stimuli`), both
`OWNER_GUIDE` files (`09` entry: `drive_urgency_signal` now real, `selected_stimuli` last constant
pending R63), both `PROGRESS_FLOW` maps (S09 node + status + sync), and
`BRAIN_ARCHITECTURE_COMPARISON.md` (`09-11` row).

## 2. Dependencies

1. T1 -> T2 -> T3 -> T4 -> T5.
2. External requirement dependencies: 09 (gate engine/contracts), 18 (`ProactiveDriveState`),
   48/55 (gate-signal bridge + carry-seam patterns). No new owner, no contract change.

## 3. Files and Modules

1. `src/helios_v2/composition/bridges.py` (T1, T2)
2. `src/helios_v2/composition/runtime_assembly.py` (T3)
3. `tests/test_runtime_composition.py` (T4)
4. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T5)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5.

## 5. Validation Plan

1. After T3:
   `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_thought_gating_engine.py -q`
   green (first tick unchanged -> no regression).
2. After T4:
   `pytest helios_v2/tests/test_runtime_composition.py -q -k drive_urgency` green.
3. Guards + full suite:
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   and `pytest helios_v2/tests -q` green; count = prior baseline (735) + 3 added tests.

## 6. Completion Criteria

1. `drive_urgency_signal` is the bounded clamped prior-tick `18` `outward_drive` carried forward
   (cold-start `0.7` on tick 1); no `0.7` gate constant remains except the documented cold-start.
2. A high-drive prior tick raises the next-tick gate `drive_urgency_signal`; the value stays
   bounded `[0,1]`; the first tick is unchanged.
3. The `09` gate decision policy/weights/thresholds and the other inputs (including the still-
   constant `selected_stimuli`) are unchanged (their tests stay green).
4. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `BRAIN_ARCHITECTURE_COMPARISON.md` record the converged scope (drive_urgency real,
   selected_stimuli deferred to R63), with sync lines naming R62.
