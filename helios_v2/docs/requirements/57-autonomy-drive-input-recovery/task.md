# Requirement 57 - Owner Boundary Recovery of the Cognition-Derived Autonomy Drive Inputs

## 1. Task Breakdown

### T1 - Add the owner-owned cognition-facts input contract
In `autonomy/contracts.py` add `ProactiveCognitionFacts` (activated, has_action_proposal,
continuation_requested, continuation_active, has_self_revision, planner_status,
retrieval_hit_count) with fail-fast validation (non-empty planner_status, non-negative
retrieval_hit_count).

### T2 - Add the owner-owned drive-input projection
In `autonomy/engine.py` add a named `OUTWARD_ACTION_THRESHOLD = 1.6` owner constant and an
`AutonomyDriveInputProjection` whose `derive_drive_inputs(facts)` returns the five drive-input
summaries, transcribing verbatim from the composition bridge: the pressure constants, the
planner executed/blocked classification, the retrieval-pull `/4.0` normalization, the
fired/no-fire branching, and the `[0,1]` rounding. `FirstVersionAutonomyPath` is unchanged.

### T3 - Re-export from the owner package
Add `ProactiveCognitionFacts` and `AutonomyDriveInputProjection` to `autonomy/__init__.py`
imports and `__all__`.

### T4 - Reduce the composition bridge to fact forwarding
Rewrite `FirstVersionAutonomyRequestBridge.build_request` to: branch fired vs no-fire only to
choose which provenance ids to read, extract `ProactiveCognitionFacts` from the upstream stage
results, call `AutonomyDriveInputProjection.derive_drive_inputs(facts)`, and assemble
`ProactiveDriveRequest` from the returned summaries + provenance ids. Delete all pressure
constants (`_ACTION_*`, `_CONTINUE_*`, `_CONCLUDED_*`, `_BASELINE_*`, `_*_IDENTITY_PRESSURE`),
the `_PLANNER_*` tuples, the `/4.0` normalization, and the 1.6 reference.

### T5 - Tests
Add focused projection tests in `test_autonomy_engine.py` (each fact set -> summaries) and a
bridge-equivalence test (bridge output matches pre-relocation field values, including no-fire).

### T6 - Extend the recurrence guard
In `tests/test_composition_owner_boundary_guard.py` add a check that fails if composition
defines an autonomy drive-pressure constant pattern or references the autonomy action
threshold literal, with a positive-control assertion.

### T7 - Update documentation truth
Update `index.md` (row 57), both `OWNER_GUIDE` files (`18` + `22` entries), both
`PROGRESS_FLOW` maps (status note + sync line), and `ARCHITECTURE_BOUNDARIES.md`
migration-state notes to record the recovered ownership and the raw-fact-forwarding scope.

## 2. Dependencies

1. T1 → T2 → T3 → T4 (the contract and projection must exist before the bridge calls them).
2. T5 depends on T2 and T4. T6 depends on T4 (the tree must be clean before asserting it).
3. T7 depends on T1–T6 landing.
4. External requirement dependencies: 18, 29, 24, 28, 54 (existing autonomy owner + the
   cognition-derived drive and no-fire paths it must reproduce), 22 (composition wiring).

## 3. Files and Modules

1. `src/helios_v2/autonomy/contracts.py` (T1)
2. `src/helios_v2/autonomy/engine.py` (T2)
3. `src/helios_v2/autonomy/__init__.py` (T3)
4. `src/helios_v2/composition/bridges.py` (T4)
5. `tests/test_autonomy_engine.py` (T5)
6. `tests/test_composition_owner_boundary_guard.py` (T6)
7. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md` (T7)

## 4. Implementation Order

T1 → T2 → T3 → T4 → T5 → T6 → T7. Dependency and migration order: contract, projection,
export, repoint+remove, tests, guard, then document.

## 5. Validation Plan

1. After T1–T4 (focused slice):
   `pytest helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_autonomy_contracts.py helios_v2/tests/test_runtime_stage_chain.py -q`
   green (request shape + decision path unchanged).
2. After T6 (guards):
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   both green.
3. After T4 (no stale policy): a repo grep shows no `_ACTION_CONTINUATION_PRESSURE` / `1.6`
   autonomy-threshold literal under `helios_v2/composition`.
4. Full suite:
   `pytest helios_v2/tests -q`
   green; count = prior baseline (704) + the added focused/guard tests.

## 6. Completion Criteria

1. `ProactiveCognitionFacts` + `AutonomyDriveInputProjection` are defined in the `18` owner
   package and exported; the pressure constants, planner classification, retrieval
   normalization, and threshold knowledge are gone from `helios_v2/composition`.
2. The `ProactiveDriveRequest` produced for any upstream facts is field-for-field identical to
   before; the autonomy disposition/result is byte-for-byte unchanged for every assembly.
3. The owner-boundary guard fails on planted autonomy drive-pressure/threshold policy under
   composition and passes on the actual tree; the ad-hoc-logging guard stays green.
4. The full network-free suite is green with only the added focused/guard tests in the count.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `ARCHITECTURE_BOUNDARIES.md` record the recovered ownership and the raw-fact-forwarding
   scope, with the sync lines naming R57.
