# Requirement 42 - Durable Runtime Continuity Checkpoint and Restart Resumption

## 1. Title

Implementation tasks for the durable runtime-continuity checkpoint owner and restart resumption.

## 2. Task Breakdown

### Task 1 - Checkpoint owner package (contracts)
- Create `helios_v2/continuity_checkpoint/contracts.py` with `CheckpointError`,
  `RuntimeContinuitySnapshot` (reusing the `09` `ContinuationPressureState`, `18`
  `DeferredContinuityRecord`, `24` `ContinuityThread` contracts as fields), and the
  `CheckpointStoreBackend` protocol (`initialize` / `save_latest(payload: str)` /
  `load_latest() -> str | None`).
- Document owner declaration (owns the durable latest-state continuity checkpoint; does not own
  continuity classification or any cognitive decision).
- Completion: contracts import cleanly; construction validation on empty/negative fields.

### Task 2 - Checkpoint engine (facade + backends)
- Create `helios_v2/continuity_checkpoint/engine.py` with:
  - `ContinuityCheckpointStore` facade owning JSON encode/decode of the snapshot and delegating
    durability to the backend (`save_latest`, `load_latest`, `initialize`),
  - `InMemoryCheckpointBackend` (deterministic double, single-slot replace),
  - `SqliteCheckpointBackend` (single-row table keyed by a fixed id; `INSERT OR REPLACE`;
    standard-library `sqlite3` + `json`; wraps `sqlite3.Error` in `CheckpointError`).
- Create `helios_v2/continuity_checkpoint/__init__.py` exporting the public surface.
- Completion: backends round-trip a snapshot exactly; SQLite persists across re-open; cold load
  returns `None`; corrupt payload raises `CheckpointError`.

### Task 3 - Stage seed seams
- Add `ThoughtGatingRuntimeStage.seed_prior_continuation_state(state)` and
  `AutonomyRuntimeStage.seed_prior_continuity(records, threads)` in `runtime/stages.py`.
- Documented as composition-time one-shot seed points; no per-tick behavior change.
- Completion: existing stage-chain tests stay green; seeding then ticking uses the seeded state.

### Task 4 - Composition bridge
- Add `ContinuityCheckpointBridge` in `composition/bridges.py`:
  - `build_snapshot(thought_gating_stage_result, autonomy_stage_result, tick_id) ->
    RuntimeContinuitySnapshot` (owner-neutral projection from published stage results),
  - `restore_continuation_state(snapshot) -> ContinuationPressureState`,
  - `restore_long_horizon(snapshot) -> tuple[records, threads]`.
- Reconstruction calls the owners' own constructors so owner validation runs.
- Completion: bridge unit-covered by the resumption test.

### Task 5 - Dependency spec + provider
- Add `CONTINUITY_CHECKPOINT_READY`, `continuity_checkpoint_critical_dependency_spec()`, and
  `ContinuityCheckpointReadinessDependencyProvider` in `composition/dependencies.py`, mirroring
  `ExperienceStoreReadinessDependencyProvider`.
- Completion: an unwritable backend surfaces unavailable; the gate fails fast.

### Task 6 - Opt-in assembly wiring
- Add `continuity_checkpoint: ContinuityCheckpointStore | None = None` to `assemble_runtime`.
- When present: register the dependency spec/provider; hold the thought-gating and autonomy stage
  refs; restore-at-assembly (load latest, seed both stages); attach the store + bridge to the
  `RuntimeHandle`.
- Add `RuntimeHandle._checkpoint_continuity(result)` called in `tick()` after `_persist_experience`.
- Default/`33`/`34`/channel-bound assemblies unchanged when `continuity_checkpoint is None`.
- Completion: default and existing opt-in assemblies byte-for-byte unchanged.

### Task 7 - Tests
- `tests/test_continuity_checkpoint_contracts.py`, `tests/test_continuity_checkpoint_engine.py`,
  and a restart-resumption test (in `tests/test_runtime_composition.py` or a new
  `tests/test_continuity_checkpoint_resumption.py`).
- Completion: all acceptance criteria covered; full suite green and network-free.

### Task 8 - Docs truth sync
- Update `requirements/index.md` (new R42 row, maturity `baseline_implementation`).
- Update `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (new infra owner node + "Last synced: R42").
- Update `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (new infra owner entry; update `09`/`18` next-step;
  update §5 whole-system view; "Last synced: R42").
- Update `ARCHITECTURE_BOUNDARIES.md` (owner map + migration-state note) and
  `BRAIN_ARCHITECTURE_COMPARISON.md` (`gap_persistence_and_learning` narrows: cross-tick continuity
  now survives restart; `04`/`05`/`14`/`06` persistence still future).

## 3. Dependencies

1. Builds on `33` (durable store seam pattern) and the existing `RuntimeHandle` carry seams.
2. Reuses `09` `ContinuationPressureState`, `18` `DeferredContinuityRecord`, `24` `ContinuityThread`
   contracts unchanged.
3. No dependency on `34` semantic memory (checkpointing is independent of the experience store).

## 4. Files and Modules

- New: `continuity_checkpoint/{__init__,contracts,engine}.py`; three test files.
- Changed: `runtime/stages.py`, `composition/{bridges,runtime_assembly,dependencies}.py`.
- Docs: index, both progress maps, both owner guides, boundaries, brain comparison.

## 5. Implementation Order

Task 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8. Owner package and backends first (independently
testable), then the additive stage seams, then composition wiring, then tests, then docs.

## 6. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_continuity_checkpoint_contracts.py
   helios_v2/tests/test_continuity_checkpoint_engine.py -q`.
2. After Task 6: the restart-resumption test plus `tests/test_runtime_composition.py` and
   `tests/test_runtime_stage_chain.py`.
3. Final: full `pytest helios_v2/tests -q` green and network-free; the no-adhoc-logging guard stays
   green (the new package uses no `logging`/`print`).

## 7. Completion Criteria

1. All requirement acceptance criteria pass.
2. Restart resumption verified by provenance (restored state equals last saved snapshot).
3. Cold store and checkpointing-off paths identical to current behavior.
4. Fail-fast on backend init and save failure; corrupt snapshot raises on load.
5. Full suite green and network-free; all truth docs synced in the same change set.
