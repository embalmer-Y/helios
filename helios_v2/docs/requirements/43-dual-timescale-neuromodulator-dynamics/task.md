# Requirement 43 - Dual-Timescale Neuromodulator Dynamics and Checkpoint

## 1. Title

Implementation tasks for dual-timescale `04` dynamics with prior-tick carry and R42 checkpoint v2.

## 2. Task Breakdown

### Task 1 - Protocol + engine signature extension
- Extend `NeuromodulatorUpdatePath.update_levels` with `prior_levels: NeuromodulatorLevels | None = None`.
- Extend `NeuromodulatorSystemAPI.update_state` and `NeuromodulatorEngine.update_state` with
  `prior_state: NeuromodulatorState | None = None`; forward `prior_state.levels` to the path.
- Update the existing `FirstVersionNeuromodulatorUpdatePath` and (composition's)
  `AppraisalDerivedNeuromodulatorUpdatePath` to accept and ignore `prior_levels`.
- Completion: existing neuromodulator tests stay green (additive defaults).

### Task 2 - DualTimescaleNeuromodulatorUpdatePath (04-owned)
- Add it to `neuromodulation/engine.py`: wraps an inner `drive_path`; constructor validates
  `0 < alpha_tonic < alpha_phasic <= 1` (else `NeuromodulatorError`).
- `update_levels`: drive = inner.update_levels(...); prior = prior_levels or config.tonic_baseline;
  per channel `clamp(prior + alpha_phasic*(drive-prior) + alpha_tonic*(baseline-prior))`.
- Completion: focused engine tests for phasic carry, tonic regression, cold-start, boundedness,
  and unstable-alpha rejection.

### Task 3 - Stage prior-state carry + seed seam
- `NeuromodulatorRuntimeStage`: add `_prior_state` (init=False), feed into `update_state`, update
  after each tick; add `seed_prior_state(state)`.
- Completion: stage-chain tests stay green; seeding then ticking uses the seeded prior.

### Task 4 - Checkpoint snapshot v2
- `RuntimeContinuitySnapshot`: add `neuromodulator_levels: NeuromodulatorLevels | None = None`;
  `SNAPSHOT_VERSION = 2`.
- Facade encode/decode: add levels (9-float dict); decode rejects version != 2 with `CheckpointError`.
- Completion: engine tests round-trip levels; version-mismatch and corrupt-levels hard-stop.

### Task 5 - Bridge + composition wiring
- `ContinuityCheckpointBridge.build_snapshot`: also read the `04` stage result's `state.levels`;
  add `restore_neuromodulator_state(snapshot)` helper (reconstruct `NeuromodulatorState` from levels).
- `runtime_assembly.py`: under the semantic opt-in, build
  `DualTimescaleNeuromodulatorUpdatePath(drive_path=AppraisalDerivedNeuromodulatorUpdatePath())`;
  keep a `04` stage ref on the handle; `_checkpoint_continuity` saves `04` levels;
  `_restore_continuity` seeds the `04` stage when the snapshot carries levels.
- Completion: default/recency/offline assemblies byte-for-byte unchanged.

### Task 6 - Tests
- Update `tests/test_neuromodulator_engine.py` (dual-timescale behavior).
- Update `tests/test_continuity_checkpoint_{contracts,engine,resumption}.py` (v2 + `04` levels).
- Update `tests/test_runtime_composition.py` (semantic `04` evolution; restart resumes `04`).
- Completion: all acceptance criteria covered; full suite green and network-free.

### Task 7 - Docs sync
- `index.md` (R43 row, maturity `baseline_implementation`), both progress-flow maps (`04` node:
  "appraisal-derived + dual-timescale (semantic)"; "Last synced: R43"; checkpoint node note),
  both owner guides (`04` entry: stateless → dual-timescale; next-step update), boundaries
  (migration note 24), brain comparison (`gap_persistence_and_learning` + the `03-07` row's
  "`04` stateless" caveat narrowed).

## 3. Dependencies

1. Builds on R36 (the drive path it wraps) and R42 (the checkpoint it extends).
2. Reuses `NeuromodulatorLevels`/`NeuromodulatorState` contracts unchanged.

## 4. Files and Modules

- Changed: `neuromodulation/{engine,contracts}.py`, `runtime/stages.py`,
  `continuity_checkpoint/{contracts,engine}.py`, `composition/{bridges,runtime_assembly}.py`.
- Tests: neuromodulator engine, the three checkpoint test files, composition.
- Docs: index, both maps, both owner guides, boundaries, brain comparison.

## 5. Implementation Order

Task 1 → 2 → 3 → 4 → 5 → 6 → 7. Signatures first (no behavior change), then the path, the carry,
the snapshot, the wiring, the tests, the docs.

## 6. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_neuromodulator_engine.py -q`.
2. After Task 5: the checkpoint + composition tests.
3. Final: full `pytest helios_v2/tests -q` green and network-free; no-adhoc-logging guard green.

## 7. Completion Criteria

1. All requirement acceptance criteria pass.
2. `04` evolves across ticks under the semantic assembly and resumes across restart by provenance.
3. Default/recency/offline keep stateless `04`; `prior_levels=None` reproduces prior behavior.
4. Snapshot v2 carries `04` levels; version mismatch / corrupt levels hard-stop on load.
5. Full suite green and network-free; all truth docs synced in the same change set.
