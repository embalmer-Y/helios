# Requirement 56 - Owner Boundary Recovery of Appraisal-Derived Neuromodulation

## 1. Task Breakdown

### T1 - Relocate the owner-owned drive path into the `04` owner
Move `AppraisalDerivedNeuromodulatorUpdatePath`, `_AggregatedSalience`, and
`_aggregate_salience` from `composition/bridges.py` into `neuromodulation/engine.py`,
reusing the owner's existing module-level `_clamp`. Update the docstring ownership line to
"Owner: neuromodulator system (R36, recovered R56)". Conform to the unchanged
`NeuromodulatorUpdatePath` protocol.

### T2 - Re-export from the `04` owner package
Add `AppraisalDerivedNeuromodulatorUpdatePath` to `neuromodulation/__init__.py` imports and
`__all__`.

### T3 - Remove the policy from composition and repoint wiring
Delete the relocated definitions from `composition/bridges.py` (keep
`FirstVersionNeuromodulatorUpdatePath`, `FirstVersionActiveChannelReporter`, and `_clamp`).
In `composition/runtime_assembly.py`, import the path from `helios_v2.neuromodulation` and
drop it from the `.bridges` import. The `NeuromodulatorEngine` wiring expression stays the
same shape.

### T4 - Repoint the owner-behavior test
In `tests/test_neuromodulator_engine.py`, change the import to
`from helios_v2.neuromodulation import AppraisalDerivedNeuromodulatorUpdatePath`.

### T5 - Add the recurrence guard
Create `tests/test_composition_owner_boundary_guard.py`: scan `helios_v2/composition/*.py`
for a salience-to-neuromodulator-channel sensitivity-coefficient pattern and fail if found;
include a positive-control assertion so the guard is not vacuous; assert the post-relocation
tree is clean.

### T6 - Update documentation truth
Update `index.md` (row 56), both `OWNER_GUIDE` files (`04` entry), both `PROGRESS_FLOW` maps
(status note + "Last synced"/sync line), and `ARCHITECTURE_BOUNDARIES.md` migration-state
notes to record the recovered ownership and the accepted-glue scope.

## 2. Dependencies

1. T1 → T2 → T3 → T4 (symbol must exist in the owner before composition/tests repoint).
2. T5 depends on T3 (the tree must be clean before the guard asserts cleanliness).
3. T6 depends on T1–T5 landing (documents record the final code truth).
4. External requirement dependencies: 04, 36, 43, 22 (existing owners/wiring; no new owner).

## 3. Files and Modules

1. `src/helios_v2/neuromodulation/engine.py` (T1)
2. `src/helios_v2/neuromodulation/__init__.py` (T2)
3. `src/helios_v2/composition/bridges.py` (T3)
4. `src/helios_v2/composition/runtime_assembly.py` (T3)
5. `tests/test_neuromodulator_engine.py` (T4)
6. `tests/test_composition_owner_boundary_guard.py` (T5, new)
7. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/ARCHITECTURE_BOUNDARIES.md` (T6)

## 4. Implementation Order

T1 → T2 → T3 → T4 → T5 → T6. This is dependency order and migration order: relocate, export,
repoint+remove, repoint test, guard, then document.

## 5. Validation Plan

1. After T1–T4 (focused slice):
   `pytest helios_v2/tests/test_neuromodulator_engine.py -q`
   must be green with the owner-imported path.
2. After T5 (guard):
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   both guards green.
3. After T3 (no stale reference): a repo grep for `AppraisalDerivedNeuromodulatorUpdatePath`
   shows it defined only in `neuromodulation/engine.py` and imported (not defined) elsewhere.
4. Full suite:
   `pytest helios_v2/tests -q`
   green; count = prior baseline (702) + the new guard test(s).

## 6. Completion Criteria

1. `AppraisalDerivedNeuromodulatorUpdatePath` is defined in `neuromodulation/engine.py`,
   exported from `helios_v2.neuromodulation`, and no longer defined in `composition`.
2. The neuromodulator levels produced for any batch/config are byte-for-byte identical to
   before (behavioral-invariance tests green).
3. The owner-boundary guard fails on a planted salience-to-channel coefficient and passes on
   the actual tree; the ad-hoc-logging guard stays green.
4. The full network-free suite is green with only the guard test(s) added to the count.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `ARCHITECTURE_BOUNDARIES.md` record the recovered ownership and accepted-glue scope, with
   the sync lines naming R56.
