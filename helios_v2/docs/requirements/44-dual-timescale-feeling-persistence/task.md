# Requirement 44 - Dual-Timescale Interoceptive Feeling Persistence and Checkpoint

## 1. Title

Implementation tasks for dual-timescale `05` feeling persistence with prior-tick carry and R42
checkpoint v3.

## 2. Task Breakdown

### Task 1 - Protocol + engine signature extension; dead-duplicate cleanup
- Extend `FeelingConstructionPath.construct_feeling` with
  `prior_feeling: InteroceptiveFeelingVector | None = None`.
- Extend `InteroceptiveFeelingAPI.update_state` and `InteroceptiveFeelingEngine.update_state` with
  `prior_state: InteroceptiveFeelingState | None = None`; forward `prior_state.feeling`.
- Update `FirstVersionFeelingConstructionPath` and `NeuromodulatorDerivedFeelingConstructionPath`
  to accept and ignore `prior_feeling`.
- Remove the shadowed dead duplicate `NeuromodulatorDerivedFeelingConstructionPath` (keep one).
- Completion: existing feeling tests stay green.

### Task 2 - PersistentFeelingConstructionPath (05-owned)
- Add it to `feeling/engine.py`: wraps an inner `target_path`; constructor validates
  `0 < alpha_tonic < alpha_phasic <= 1`.
- `construct_feeling`: target = inner.construct_feeling(...); prior = prior_feeling or
  config.baseline_feeling; per dimension
  `clamp(prior + alpha_phasic*(target-prior) + alpha_tonic*(baseline-prior))`.
- Completion: focused engine tests for phasic carry, tonic regression, cold-start, boundedness,
  unstable-alpha rejection.

### Task 3 - Stage prior-state carry + seed seam
- `InteroceptiveFeelingRuntimeStage`: add `_prior_state` (init=False), feed into `update_state`,
  update after each tick; add `seed_prior_state(state)`.
- Completion: stage-chain tests stay green.

### Task 4 - Checkpoint snapshot v3
- `RuntimeContinuitySnapshot`: add `feeling: InteroceptiveFeelingVector | None = None`;
  `SNAPSHOT_VERSION = 3`.
- Facade encode/decode: add feeling (7-float dict); decode rejects version != 3.
- Completion: engine tests round-trip feeling; version-mismatch and corrupt-feeling hard-stop.

### Task 5 - Bridge + composition wiring
- `ContinuityCheckpointBridge.build_snapshot`: also read the `05` stage result's `state.feeling`;
  add `restore_feeling_state(snapshot)`.
- `runtime_assembly.py`: under the semantic opt-in, build
  `PersistentFeelingConstructionPath(target_path=NeuromodulatorDerivedFeelingConstructionPath())`;
  keep a `05` stage ref on the handle; `_checkpoint_continuity` saves `05` feeling;
  `_restore_continuity` seeds the `05` stage when the snapshot carries a feeling.
- Completion: default/recency/offline assemblies byte-for-byte unchanged.

### Task 6 - Tests
- Update `tests/test_interoceptive_feeling_engine.py` (dual-timescale behavior).
- Update `tests/test_continuity_checkpoint_{contracts,engine,resumption}.py` (v3 + `05` feeling).
- Update `tests/test_runtime_composition.py` (semantic `05` evolution; restart resumes `05`).
- Completion: all acceptance criteria covered; full suite green and network-free.

### Task 7 - Docs sync
- `index.md` (R44 row), both progress-flow maps (`05` node + checkpoint edge + Last synced R44),
  both owner guides (`05` entry), boundaries (migration note 25), brain comparison
  (`gap_persistence_and_learning` + `03-07` row: `05` no longer stateless).

## 3. Dependencies

1. Builds on R38 (the target path it wraps), R43 (the checkpoint shape + the `04` stage-ref
   pattern it mirrors), and R42 (the checkpoint).
2. Reuses `InteroceptiveFeelingVector`/`InteroceptiveFeelingState` contracts unchanged.

## 4. Files and Modules

- Changed: `feeling/{engine,contracts}.py`, `runtime/stages.py`,
  `continuity_checkpoint/{contracts,engine}.py`, `composition/{bridges,runtime_assembly}.py`.
- Tests: feeling engine, the three checkpoint test files, composition.
- Docs: index, both maps, both owner guides, boundaries, brain comparison.

## 5. Implementation Order

Task 1 → 2 → 3 → 4 → 5 → 6 → 7.

## 6. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_interoceptive_feeling_engine.py -q`.
2. After Task 5: the checkpoint + composition tests.
3. Final: full `pytest helios_v2/tests -q` green and network-free; no-adhoc-logging guard green.

## 7. Completion Criteria

1. All requirement acceptance criteria pass.
2. `05` evolves across ticks under the semantic assembly and resumes across restart by provenance.
3. Default/recency/offline keep stateless `05`; `prior_feeling=None` reproduces prior behavior.
4. Snapshot v3 carries `05` feeling; version mismatch / corrupt feeling hard-stop on load.
5. Full suite green and network-free; all truth docs synced; the dead duplicate removed.
