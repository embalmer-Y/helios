# Requirement 24 - Long-horizon continuity threads and reinforcement task plan

## 1. Title

Requirement 24 - Long-horizon continuity threads and reinforcement in autonomy

## 2. Task Breakdown

1. Add the immutable `ContinuityThread` and `LongHorizonContinuityState` contracts (with the thread-state taxonomy and `to_evidence`) to `autonomy/contracts.py`.
2. Extend `ProactiveDriveRequest` with `prior_continuity_threads` and `AutonomyResult` with `long_horizon_state` in `autonomy/contracts.py`.
3. Export the new contracts from `autonomy/__init__.py`.
4. Implement thread formation, recurrence reinforcement, conflict arbitration, and long-horizon state assembly in `FirstVersionAutonomyPath` (with an explicit `reinforcement_gain`), preserving existing decay/merge/expire/resolved accounting.
5. Add autonomy contract and engine tests in `tests/test_autonomy_contracts.py` and `tests/test_autonomy_engine.py`.
6. Carry prior continuity threads owner-privately across ticks in `AutonomyRuntimeStage` and inject them into each request; expose the long-horizon state on the stage result.
7. Extend the composition autonomy request bridge to carry prior threads and the evaluation evidence bridge to project the long-horizon state in `composition/bridges.py`.
8. Read long-horizon fields in `evaluation/engine.py` and publish a `long_horizon_continuity` diagnostic with explicit absence handling; extend `tests/test_evaluation_engine.py`.
9. Extend `tests/test_runtime_composition.py` for cross-tick thread reinforcement and dominant-thread reporting.
10. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` to record the thread layer and the narrowed wave B gap.

## 3. Dependencies

1. `18-subjective-autonomy-and-proactive-evolution` provides the deferred-continuity record layer the thread layer builds on.
2. `22-runtime-composition-root-and-runnable-runtime` provides the runnable runtime and the bridge surface for cross-tick thread carry.
3. `23-execution-timeline-aware-evaluation-and-consequence-binding` provides the evaluation diagnostics surface the long-horizon state extends.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/autonomy/contracts.py`
2. `helios_v2/src/helios_v2/autonomy/engine.py`
3. `helios_v2/src/helios_v2/autonomy/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/evaluation/engine.py`
6. `helios_v2/src/helios_v2/composition/bridges.py`
7. `helios_v2/tests/test_autonomy_contracts.py`
8. `helios_v2/tests/test_autonomy_engine.py`
9. `helios_v2/tests/test_evaluation_engine.py`
10. `helios_v2/tests/test_runtime_composition.py`
11. `helios_v2/docs/requirements/index.md`
12. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
13. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 5. Implementation Order

1. Land the thread and long-horizon-state contracts plus the request/result extensions in `autonomy/contracts.py`.
2. Implement thread formation, reinforcement, arbitration, and state assembly in `autonomy/engine.py`; add autonomy tests and validate the owner in isolation.
3. Wire the owner-private thread carry into `AutonomyRuntimeStage`.
4. Extend the composition autonomy request bridge and evaluation evidence bridge.
5. Extend evaluation scoring for the long-horizon diagnostic; add evaluation tests.
6. Extend composition cross-tick tests.
7. Update boundary, index, and grounding docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_autonomy_contracts.py helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_composition.py -q`
4. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
5. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. The autonomy owner exposes documented `ContinuityThread` and `LongHorizonContinuityState` contracts.
2. A recurring continuity key reinforces its thread deterministically while per-record decay still applies.
3. Multiple active threads produce an explicit dominant thread plus preserved suppressed threads.
4. The long-horizon state reports active count, dominant thread, suppressed ids, max age, and aggregate reinforcement, distinguishing fresh from reinforced threads.
5. Evaluation consumes the long-horizon state and reports an explicit long-horizon continuity diagnostic with explicit absence handling.
6. Existing decay/merge/expire/resolved accounting remains intact and threads retire only explicitly.
7. The logging-guard test passes and `pytest helios_v2/tests -q` is green.

## 8. Completion Snapshot

Status: pending implementation. This section will be updated with validated results and the final delivered file list once the implementation lands.
