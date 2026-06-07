# Requirement 63 - Real Selected-Stimuli Projection and Default-Assembly Ignition Source

## 1. Task Breakdown

### T1 - Raise FirstVersionAggregateEstimator and add the projection helper
In `composition/bridges.py`:
1. Change `FirstVersionAggregateEstimator.estimate_aggregate` from returning `0.4` to `0.7`.
2. Add `_STIMULUS_INTENSITY_COLD_START = 0.7`, `_NOVELTY_SIGNAL_COLD_START = 0.6`,
   `_SENSITIZATION_SIGNAL_COLD_START = 0.3` documented fallback constants.
3. Add `_selected_stimuli_from_appraisal(frame, tick_id)` helper that reads the `03`
   `RapidSalienceAppraisalStageResult` from `frame.stage_results`, projects batch-max
   `aggregate`/`novelty`/`uncertainty` (clamped, rounded) into a `SelectedStimulusSummary` tuple,
   and falls back to the cold-start constants when the appraisal result is absent or the batch is
   empty.

### T2 - Rewire both gate-signal bridges
In `FirstVersionThoughtGateSignalBridge.build_signal_snapshot` and
`NeuromodulatorAwareThoughtGateSignalBridge.build_signal_snapshot`, replace the hardcoded
`selected_stimuli=(SelectedStimulusSummary(stimulus_intensity=0.9, novelty_signal=0.6,
sensitization_signal=0.2),)` with a call to `_selected_stimuli_from_appraisal(frame, tick_id)`.

### T3 - Fix existing tests
Update any tests that assert the old `0.4` aggregate constant or the old hardcoded
`selected_stimuli` values (`stimulus_intensity=0.9`, `novelty_signal=0.6`,
`sensitization_signal=0.2`). The new expected values under the default assembly are the real `03`
appraisal outputs (aggregate `0.7` from the raised estimator, novelty `0.6` from
`FirstVersionDimensionEstimator`, uncertainty `0.3`).

### T4 - Add focused tests
Add tests in `test_runtime_composition.py`:
1. Real appraisal projection: a frame with a `RapidSalienceAppraisalStageResult` produces
   `selected_stimuli` matching the batch-max aggregate/novelty/uncertainty.
2. Absent-appraisal fallback: a frame without the appraisal result produces the cold-start
   constants.
3. Default-assembly gate firing: the gate decides `fire` on tick 1 under the default assembly.

### T5 - Documentation
Update `index.md` (row 63; update R09 notes to record all gate inputs real), both `OWNER_GUIDE`
files (`09` entry: `selected_stimuli` now real, no constant shim remains in the gate signal; `03`
entry: `FirstVersionAggregateEstimator` raised to `0.7`), both `PROGRESS_FLOW` maps (S09 node
status update), and `BRAIN_ARCHITECTURE_COMPARISON.md` (`09-11` row updated).

## 2. Dependencies

1. T1 -> T2 -> T3 -> T4 -> T5.
2. External requirement dependencies: 03 (appraisal result), 09 (gate engine/contracts),
   41 (`WeightedAggregateEstimator`, unaffected), 61 (mismatch bridge pattern for reading `03`
   from frame). No new owner, no contract change.

## 3. Files and Modules

1. `src/helios_v2/composition/bridges.py` (T1, T2)
2. `tests/test_runtime_composition.py` (T4)
3. `tests/test_appraisal_engine.py` (T3, if assertions on old `0.4` exist)
4. `tests/test_thought_gating_engine.py` (T3, if assertions on old `stimulus_intensity=0.9` exist)
5. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T5)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5.

## 5. Validation Plan

1. After T2:
   `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_thought_gating_engine.py helios_v2/tests/test_appraisal_engine.py -q`
   Identify failing tests; fix in T3.
2. After T3:
   Same command; all green. No regression from the raised aggregate or the real projection.
3. After T4:
   `pytest helios_v2/tests/test_runtime_composition.py -q -k selected_stimuli` green.
4. Guards + full suite:
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   and `pytest helios_v2/tests -q` green.

## 6. Completion Criteria

1. `selected_stimuli` `stimulus_intensity` equals the batch-max `03` appraisal `aggregate`
   (clamped); the hardcoded `0.9` constant is removed (present only as the documented cold-start
   fallback `_STIMULUS_INTENSITY_COLD_START = 0.7`).
2. `FirstVersionAggregateEstimator` returns `0.7` (raised from `0.4`); the default assembly's gate
   fires on tick 1 (score `~0.555 > 0.55`).
3. The `09` gate decision policy, weights, and thresholds are unchanged.
4. The semantic assembly's `WeightedAggregateEstimator` is unaffected.
5. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
6. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `BRAIN_ARCHITECTURE_COMPARISON.md` record that all `09` gate inputs are now real (no constant
   shim remains), with sync lines naming R63.
