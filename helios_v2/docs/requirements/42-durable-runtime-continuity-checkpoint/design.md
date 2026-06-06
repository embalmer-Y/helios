# Requirement 42 - Durable Runtime Continuity Checkpoint and Restart Resumption

## 1. Title

Durable Runtime Continuity Checkpoint and Restart Resumption (`helios_v2.continuity_checkpoint`).

## 2. Design Overview

Introduce a new infrastructure owner, `helios_v2.continuity_checkpoint`, modeled on the existing
`33` durable experience store but for a different kind of state. Where `33` durably *appends* the
episodic experience stream, this owner durably keeps one *latest-state* snapshot of the runtime's
genuinely cross-tick continuity state and restores it on restart.

The owner ships:

1. a `RuntimeContinuitySnapshot` contract (owner-neutral serializable projection of the cross-tick
   states),
2. a `CheckpointStoreBackend` protocol with a first-version SQLite file backend and an in-memory
   double,
3. a `ContinuityCheckpointStore` facade (`save_latest` / `load_latest`).

Composition wires it opt-in: a restore step at assembly time seeds the `09` and `18` stage prior-
state fields from the loaded snapshot, and a save step after each tick (mirroring the existing
`RuntimeHandle._persist_experience` seam) writes the latest snapshot. The owner holds no cognitive
policy; the projection of stage results into a snapshot and the reconstruction of owner state
contracts from a snapshot are owner-neutral composition bridges.

## 3. Current State and Gap

Genuinely cross-tick in-process state in the current runtime (confirmed by reading
`runtime/stages.py`):

1. `ThoughtGatingRuntimeStage._prior_continuation_state: ContinuationPressureState`
   (`init=False`, default `ContinuationPressureState.inactive()`), updated each tick to the gate's
   produced continuation state and fed into the next tick's `evaluate_gate`.
2. `AutonomyRuntimeStage._prior_deferred_records: tuple[DeferredContinuityRecord, ...]` and
   `._prior_continuity_threads: tuple[ContinuityThread, ...]` (`init=False`, default empty),
   updated each tick to the autonomy result's `deferred_records` and
   `long_horizon_state.threads`, and fed into the next tick's `ProactiveDriveRequest`.

No other owner carries cross-tick in-process state today: `04` neuromodulator and `05` feeling are
computed per-tick (stateless in the de-shim slices R36/R38), and `14` identity state is supplied
through request snapshots rather than carried in a stage field. The gap is purely that the two
state holders above reset on process exit, so restart resumption is inert.

`RuntimeHandle` already has the exact carry seams to mirror: `_carry_timeline`,
`_carry_consequence_claim`, and `_persist_experience` all read completed-tick stage results and
forward owner-published values to an injected sink without re-deriving anything.

## 4. Target Architecture

### 4.1 Owner package

```
helios_v2/continuity_checkpoint/
  __init__.py      # public exports
  contracts.py     # RuntimeContinuitySnapshot, CheckpointStoreBackend, CheckpointError
  engine.py        # ContinuityCheckpointStore facade, SqliteCheckpointBackend, InMemoryCheckpointBackend
```

Owner declaration: owns the durable latest-state continuity checkpoint. Does not own continuity
classification (`09`/`18`/`24`), retrieval, or any cognitive decision. It is infrastructure like
`21` observability and `33` persistence.

### 4.2 Save path (after tick)

`RuntimeHandle.tick()` gains a `_checkpoint_continuity(result)` step (next to `_persist_experience`):

1. read the `thought_gating_and_continuation_pressure` stage result -> its `continuation_state`,
2. read the `subjective_autonomy_and_proactive_evolution` stage result -> its
   `result.deferred_records` and `result.long_horizon_state`,
3. project them into a `RuntimeContinuitySnapshot` through the owner-neutral
   `ContinuityCheckpointBridge.build_snapshot(...)`,
4. `checkpoint_store.save_latest(snapshot)`.

Runs only when `checkpoint_store` and the bridge are present (opt-in). A save error propagates.

### 4.3 Restore path (at assembly/startup)

In `assemble_runtime(..., continuity_checkpoint=...)`, after the stages are constructed but before
the handle is returned, when checkpointing is enabled:

1. `snapshot = checkpoint_store.load_latest()`,
2. if present, reconstruct the owners' state contracts through
   `ContinuityCheckpointBridge.restore_continuation_state(snapshot)` and
   `.restore_long_horizon(snapshot)` (owner-neutral; calls the owners' own constructors so their
   validation runs),
3. seed `thought_gating_stage._prior_continuation_state` and
   `autonomy_stage._prior_deferred_records` / `._prior_continuity_threads` through explicit
   owner-neutral seed methods on the stages (a small public seed seam, not direct private mutation
   from outside the runtime package).

If absent, leave the existing inert defaults untouched.

### 4.4 Stage seed seam

Add explicit seed methods on the two stages rather than reaching into `_`-prefixed fields from
composition:

- `ThoughtGatingRuntimeStage.seed_prior_continuation_state(state: ContinuationPressureState) -> None`
- `AutonomyRuntimeStage.seed_prior_continuity(records, threads) -> None`

These are documented composition-time seed points (called once before the first tick), not
per-tick mutators. They keep the cross-tick fields owned by the stage while letting composition
restore them.

## 5. Data Structures

```python
@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    """Owner: durable runtime-continuity checkpoint.

    Owner-neutral serializable projection of the cross-tick continuity state at a tick.
    Stored/returned verbatim; the owner never interprets it.
    """
    tick_id: int | None
    continuation_state: ContinuationPressureState         # `09` owner contract, reused
    deferred_records: tuple[DeferredContinuityRecord, ...] # `18` owner contract, reused
    continuity_threads: tuple[ContinuityThread, ...]       # `24` owner contract, reused
    snapshot_version: int = 1
```

Design choice: the snapshot reuses the owners' own frozen dataclasses directly as its fields rather
than inventing parallel shapes. Serialization to the backend uses a documented field-by-field JSON
encoding (the owner contracts are simple value dataclasses). This keeps the owners as the sole
definition of their state shape and makes reconstruction run the owners' validation. The
`snapshot_version` field allows additive evolution (adding `04`/`05`/`14` state later) without
breaking older files (an older version loads its known fields; a newer field absent in an old row
reconstructs to the existing inert default).

```python
@runtime_checkable
class CheckpointStoreBackend(Protocol):
    def initialize(self) -> None: ...
    def save_latest(self, payload: str) -> None: ...      # one-row replace; payload is JSON text
    def load_latest(self) -> str | None: ...              # None when cold
```

The backend stores opaque JSON text keyed by a single fixed row id; the facade owns JSON
encode/decode of the `RuntimeContinuitySnapshot` so the backend stays a dumb durable byte sink
(mirrors how `33` keeps its backend free of cognitive meaning).

```python
@dataclass
class ContinuityCheckpointStore:
    backend: CheckpointStoreBackend
    def initialize(self) -> None: ...
    def save_latest(self, snapshot: RuntimeContinuitySnapshot) -> None: ...
    def load_latest(self) -> RuntimeContinuitySnapshot | None: ...
```

## 6. Module Changes

1. New `continuity_checkpoint` package (contracts + engine) as above.
2. `runtime/stages.py`: add the two seed methods; no change to per-tick behavior.
3. `composition/bridges.py`: add `ContinuityCheckpointBridge` (build snapshot from stage results;
   reconstruct owner states from a snapshot). Owner-neutral, provenance-preserving.
4. `composition/runtime_assembly.py`: add `continuity_checkpoint: ContinuityCheckpointStore | None`
   parameter to `assemble_runtime`; wire restore-at-assembly and the `RuntimeHandle` save-after-tick;
   add the `continuity_checkpoint_ready` critical dependency when enabled. Keep references to the
   thought-gating and autonomy stages so they can be seeded.
5. `composition/dependencies.py`: add `CONTINUITY_CHECKPOINT_READY`,
   `continuity_checkpoint_critical_dependency_spec()`, and a
   `ContinuityCheckpointReadinessDependencyProvider` (mirrors `ExperienceStoreReadinessDependencyProvider`).

## 7. Migration Plan

1. Land the owner package + backends + facade with focused contract/engine tests (no runtime wiring
   yet).
2. Add the stage seed seams (pure additive methods; existing tests unaffected).
3. Add the composition bridge + opt-in wiring + dependency spec.
4. Add the restart-resumption composition test (run ticks with one store/file, re-assemble against
   the same backend, assert resumed state by provenance).
5. Sync the docs (`index.md` maturity row, both progress-flow maps, owner guides, boundaries, brain
   comparison gap language).

No rewrite of existing owners; everything is additive and opt-in.

## 8. Failure Modes and Constraints

1. Backend cannot initialize (unwritable path): `continuity_checkpoint_ready` reports unavailable;
   the existing startup gate fails fast. No degraded path.
2. Save failure mid-run: `save_latest` raises `CheckpointError`; `RuntimeHandle.tick` propagates it.
3. Corrupt stored JSON or an invariant-violating snapshot: `load_latest` raises `CheckpointError`
   (JSON decode error) or the owner contract raises its own error on reconstruction; either way the
   restore fails fast rather than seeding invalid state.
4. Cold store: `load_latest` returns `None`; the runtime keeps inert defaults.
5. Owner-boundary constraint: the checkpoint owner imports the `09`/`18`/`24` contracts only to type
   the snapshot's reused fields and (in the facade) to JSON-encode/decode them; it computes no
   continuity decision. The stage-result projection and state reconstruction live in composition,
   not in the checkpoint owner.

## 9. Observability and Logging

No new logging mechanism. The owner emits nothing. The single logging mechanism remains `21`
observability, enforced by `tests/test_no_adhoc_logging_guard.py` (the new package must use no
`logging`/`print`).

## 10. Validation Strategy

1. `test_continuity_checkpoint_contracts.py`: snapshot construction validation; reused owner
   contracts round-trip through the snapshot fields.
2. `test_continuity_checkpoint_engine.py`: in-memory and SQLite backends save/replace/load latest;
   SQLite persists across a backend re-open; cold load returns `None`; corrupt row raises; a second
   save replaces (not appends) the latest.
3. Restart-resumption test (composition): assemble with an in-memory-or-temp-file checkpoint store,
   run ticks producing active continuation pressure and a thread, save snapshot; assemble a fresh
   runtime against the same backend; assert the first restored tick's prior states equal the saved
   snapshot (provenance assertion).
4. Default-unchanged: existing composition and stage-chain tests stay green with checkpointing off.
5. Full suite network-free.
