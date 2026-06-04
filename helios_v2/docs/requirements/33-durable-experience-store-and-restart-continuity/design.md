# Requirement 33 - Durable experience store and restart continuity (design)

## 1. Design Overview

R33 introduces a new infrastructure owner, `helios_v2.persistence`, that durably stores the experience-writeback continuity stream and surfaces it back into the cognitive chain after a restart. It mirrors the architectural shape already proven by `21` observability: a fail-fast, read/write infrastructure owner with explicit contracts, an injected backend behind a protocol, and an opt-in composition seam that leaves the default assembly byte-for-byte unchanged.

The change has four additive pieces:

1. A persistence owner with a `PersistedExperienceRecord` contract, a backend protocol, a first-version SQLite file backend, an in-memory backend double, and an `ExperienceStore` facade (append / recent-N / count / prior-existence snapshot).
2. An owner-neutral composition seam that, after each completed tick, appends that tick's `15` continuity records to the store (mirroring the existing post-tick timeline carry on `RuntimeHandle`).
3. A store-backed directed-retrieval candidate provider that surfaces persisted experience records as `MemoryRetrievalCandidate`s for the `10` owner, replacing the fabricating shim when persistence is enabled.
4. An opt-in `persistence=` assembly argument plus an `experience_store_ready` critical dependency wired into the existing fail-fast startup gate.

Everything stays read/append-only with respect to runtime semantics. No cognitive owner changes policy. No embedding, vector, or semantic ranking is introduced (that is R34). Selection is deterministic recency/provenance.

## 2. Current State and Gap

Current state:

1. `15` `ExperienceWritebackEngine.write_experience` returns an `ExperienceWritebackResult` carrying a `ContinuityEvidencePacket` (with `source_provenance` linkage ids) and `ConsolidationCandidate`s. The runtime stage publishes these results per tick; the `15 -> 06` loop is in-memory only.
2. `10` directed retrieval consumes a `DirectedMemoryCandidateProvider`. In composition this is `FirstVersionDirectedMemoryCandidateProvider`, which fabricates three fixed candidates from the plan id, ignoring real experience.
3. `RuntimeHandle.tick()` already performs owner-neutral post-tick carries (`_carry_timeline`, `_carry_consequence_claim`) by reading the just-completed tick's stage results. This is the exact seam pattern R33 reuses for the append.
4. No module under `helios_v2/src` performs any durable write or read. Process exit loses all continuity.

Gap:

1. There is no durable store, so nothing survives a restart (`FG-5.1` unmet).
2. Even within one process, `10`'s candidates never reflect the real experience the runtime produced, because the candidate provider is a fabricating shim.

## 3. Target Architecture

### 3.1 Owner placement

`helios_v2.persistence` is a new infrastructure owner, peer to `helios_v2.observability`. It is not a cognitive owner: it stores and returns records, computes a store-assigned monotonic sequence, and performs deterministic recency reads. It never interprets meaning, never ranks by semantics, and never makes a cognitive decision.

### 3.2 Per-tick write data flow (persistence enabled)

```
kernel.tick()
  -> stage_results["execution_writeback_and_autobiographical_consolidation"]  (15 result)
RuntimeHandle.tick()
  -> _persist_experience(result)                      # NEW owner-neutral post-tick seam
       -> ExperienceRecordBridge.build_records(15_result, tick_id)   # owner-neutral projection
       -> ExperienceStore.append_records(records)     # durable append, store-assigned sequence
```

The append runs after `kernel.tick()` returns, exactly like `_carry_timeline`. It is not a runtime stage, so `CANONICAL_STAGE_ORDER` / `CHANNEL_BOUND_STAGE_ORDER` are untouched.

### 3.3 Startup reload + retrieval re-entry data flow (persistence enabled)

```
assemble_runtime(persistence=...)
  -> ExperienceStore opened on the durable backend (records from prior processes already present)
  -> StoreBackedDirectedMemoryCandidateProvider(store) wired into the 10 directed-retrieval stage
       (replaces FirstVersionDirectedMemoryCandidateProvider)

each tick, 10 directed retrieval:
  -> provider.collect_candidates(plan)
       -> store.read_recent(limit)                    # deterministic recency read
       -> map each PersistedExperienceRecord -> MemoryRetrievalCandidate (autobiographical/episodic tier)
```

After a restart against the same backend file, `read_recent` returns the prior session's records, so the prior session re-enters the new session's thought window. A cold store returns `()` candidates explicitly.

### 3.4 Owner responsibilities

1. Persistence owner (`helios_v2.persistence`) owns: the record contract, the backend protocol, the SQLite + in-memory backends, the `ExperienceStore` facade, and the store-backed candidate provider.
2. Composition owner owns: the owner-neutral record-projection bridge, the post-tick append seam on `RuntimeHandle`, the opt-in `persistence=` wiring, and the `experience_store_ready` dependency wiring. It computes no store policy and no candidate ranking.
3. `15` and `10` owners are unchanged in policy. `15` still produces results; `10` still owns retrieval planning and thought-window shaping. R33 only changes the candidate source feeding `10` when persistence is enabled.

### 3.5 Default rollout

Persistence is default-off. `assemble_runtime()` with no `persistence=` argument is byte-for-byte the current behavior: the fabricating candidate provider stays, no store is opened, no append occurs, and `experience_store_ready` is not registered. Persistence is an explicit opt-in, never an implicit default and never a hidden fallback.

## 4. Data Structures

### 4.1 `PersistedExperienceRecord` (persistence contract)

```
@dataclass(frozen=True)
class PersistedExperienceRecord:
    sequence: int                 # store-assigned, strictly increasing; -1 sentinel before assignment
    record_id: str                # stable id, e.g. f"experience:{source_result_id}"
    tick_id: int | None
    continuity_kind: str          # mirrors 15 ContinuityKind value (stored as str, not re-validated)
    outcome_class: str            # mirrors 15 ContinuityOutcomeClass value
    source_outcome_kind: str      # mirrors 15 ExperienceSourceOutcomeKind value
    source_outcome_id: str
    writeback_status: str         # mirrors 15 ExperienceWritebackStatus value
    summary: str
    requested_effect_summary: str
    applied_effect_summary: str
    reason_trace: tuple[str, ...]
    linkage: Mapping[str, str]    # preserved upstream provenance linkage ids (origin_thought_id, proposal_id, ...)
```

Construction validates: non-empty `record_id`, non-empty `source_outcome_id`, non-empty `summary`, non-empty `continuity_kind`/`outcome_class`/`source_outcome_kind`/`writeback_status`. The persistence owner stores taxonomy values as opaque strings; it does not re-validate `15`'s taxonomies (that is `15`'s ownership). `linkage` is frozen to an immutable mapping.

### 4.2 `PriorExistenceSnapshot` (persistence contract)

```
@dataclass(frozen=True)
class PriorExistenceSnapshot:
    total_record_count: int
    most_recent_sequence: int | None
    most_recent_tick_id: int | None
    recent_summaries: tuple[str, ...]   # bounded, for startup diagnostics only
```

A bounded read-only snapshot for startup diagnostics. It carries no authority and is never consumed as cognitive state.

### 4.3 Backend protocol

```
@runtime_checkable
class ExperienceStoreBackend(Protocol):
    def append(self, records: tuple[PersistedExperienceRecord, ...]) -> tuple[PersistedExperienceRecord, ...]:
        # persist the batch, assign each a strictly increasing sequence, return the stamped records
    def read_recent(self, limit: int) -> tuple[PersistedExperienceRecord, ...]:
        # return up to `limit` most-recent records, ascending by sequence
    def count(self) -> int:
    def initialize(self) -> None:
        # idempotent backend setup (create table/file); raises PersistenceError on unrecoverable failure
```

### 4.4 First-version backends

1. `SqliteExperienceStoreBackend(db_path)`: a `sqlite3` file backend (standard library). `initialize()` creates the table if absent. `append` inserts rows (sequence = autoincrement rowid). `read_recent` selects `ORDER BY sequence DESC LIMIT n` then reverses to ascending. `reason_trace`/`linkage` are JSON-encoded columns. Raises `PersistenceError` wrapping any `sqlite3.Error`.
2. `InMemoryExperienceStoreBackend()`: a deterministic list-backed double for tests and offline runs; same protocol, same sequence semantics, no file.

### 4.5 `ExperienceStore` facade

```
@dataclass
class ExperienceStore:
    backend: ExperienceStoreBackend
    def append_records(self, records) -> tuple[PersistedExperienceRecord, ...]
    def read_recent(self, limit) -> tuple[PersistedExperienceRecord, ...]
    def count(self) -> int
    def prior_existence_snapshot(self, recent_limit=...) -> PriorExistenceSnapshot
```

The facade validates inputs (positive limit, non-empty batch tolerated as a no-op append returning `()`), delegates durability to the backend, and assembles the snapshot. It performs no ranking.

### 4.6 Composition glue

1. `ExperienceRecordBridge` (owner-neutral): `build_records(writeback_stage_result, tick_id) -> tuple[PersistedExperienceRecord, ...]`. It projects each `ExperienceWritebackResult` into a record, preserving `source_provenance` linkage verbatim. It computes no status.
2. `StoreBackedDirectedMemoryCandidateProvider(store, limit)`: implements `DirectedMemoryCandidateProvider`. `collect_candidates(plan)` reads recent records and maps each to a `MemoryRetrievalCandidate` (autobiographical tier for `internal_thought_cycle`/identity continuity kinds, episodic otherwise; `score` a deterministic recency-rank in `[0,1]`; `source="experience_store"`; `summary` from the record). A cold store yields `()`.

### 4.7 Durable location

The default durable path lives under the repo-root `data/` directory (already git-ignored), for example `data/helios_v2/experience_store.sqlite3`. The path is composition-supplied; tests use a pytest `tmp_path` file or the in-memory backend.

## 5. Module Changes

### 5.1 `helios_v2/src/helios_v2/persistence/__init__.py` (new)
Export `PersistedExperienceRecord`, `PriorExistenceSnapshot`, `ExperienceStoreBackend`, `SqliteExperienceStoreBackend`, `InMemoryExperienceStoreBackend`, `ExperienceStore`, `StoreBackedDirectedMemoryCandidateProvider`, `PersistenceError`.

### 5.2 `helios_v2/src/helios_v2/persistence/contracts.py` (new)
`PersistenceError`, `PersistedExperienceRecord`, `PriorExistenceSnapshot`, `ExperienceStoreBackend` protocol.

### 5.3 `helios_v2/src/helios_v2/persistence/engine.py` (new)
`ExperienceStore`, `SqliteExperienceStoreBackend`, `InMemoryExperienceStoreBackend`, `StoreBackedDirectedMemoryCandidateProvider`.

### 5.4 `helios_v2/src/helios_v2/composition/bridges.py`
Add `ExperienceRecordBridge` (owner-neutral projection). It imports `PersistedExperienceRecord` from `helios_v2.persistence`.

### 5.5 `helios_v2/src/helios_v2/composition/runtime_assembly.py`
1. Add `persistence: PersistenceCompositionConfig | None = None` (or a simpler `experience_store: ExperienceStore | None`) to `assemble_runtime`. When provided, wire `StoreBackedDirectedMemoryCandidateProvider` into the directed-retrieval stage instead of `FirstVersionDirectedMemoryCandidateProvider`, register `experience_store_ready`, and pass the store + bridge to the handle.
2. Extend `RuntimeHandle` with optional `experience_store` and `record_bridge`; add `_persist_experience(result)` called from `tick()` after the existing carries. It appends the tick's `15` records when a store is present; otherwise it is a no-op.

### 5.6 `helios_v2/src/helios_v2/composition/dependencies.py`
Add `EXPERIENCE_STORE_READY` name, `experience_store_critical_dependency_spec()`, and an `ExperienceStoreReadinessDependencyProvider` that reports availability by attempting/confirming `backend.initialize()` success, wrapping the baseline provider. Unwritable/un-initializable backend -> not available -> fail-fast startup.

### 5.7 `helios_v2/.gitignore`
`data/` is already ignored; confirm the chosen store path lives under it (no new ignore needed unless the path differs).

## 6. Migration Plan

1. All new code is in a new owner package plus additive composition wiring. No existing contract changes shape.
2. `persistence=` defaults to `None`; the default assembly keeps `FirstVersionDirectedMemoryCandidateProvider`, opens no store, and registers no new dependency. Existing composition tests pass unmodified.
3. `RuntimeHandle.tick()` gains one guarded post-tick call that no-ops when no store is present, so uninstrumented/non-persistent ticks are unchanged.
4. No stage-order change; both `CANONICAL_STAGE_ORDER` and `CHANNEL_BOUND_STAGE_ORDER` are untouched, so the channel-bound assembly keeps working and can opt into persistence the same way.

## 7. Failure Modes and Constraints

1. Backend un-initializable or unwritable while persistence is enabled: `experience_store_ready` reports unavailable, startup fails fast through the existing gate. No degraded non-persistent run.
2. Append failure mid-run (e.g. disk error): `ExperienceStore.append_records` raises `PersistenceError`; the handle does not swallow it. No silent fallback to non-persistent.
3. Cold store / first ever run: `read_recent` returns `()`; the store-backed provider returns `()`; the tick completes; directed retrieval produces a bundle with empty tiers (the `10` owner already tolerates bounded/empty tiers).
4. Persistence disabled: every persistence path is inert; behavior identical to today.
5. The store never ranks by meaning, never mutates prior records, and never makes a cognitive decision. Read order is deterministic by store-assigned sequence, independent of wall-clock.
6. No `logging`/`print` anywhere under `src/`; durability facts travel through contracts only; the guard test stays green.

## 8. Observability and Logging

R33 introduces no new logging mechanism. If a recorder is attached, the existing kernel lifecycle events still describe the tick; the append seam runs outside stage execution and emits nothing itself. Durable facts (counts, sequences, snapshots) are returned through the `persistence` contracts, never through the log channel. The store must never become an authoritative inter-owner transport: owners still receive each other's decisions only through their existing result contracts.

## 9. Validation Strategy

Focused tests (network-free, deterministic; SQLite tests use pytest `tmp_path`):

1. `test_persistence_contracts.py`:
   - `PersistedExperienceRecord` validation (rejects empty `record_id`/`source_outcome_id`/`summary`; freezes `linkage`).
   - `PriorExistenceSnapshot` shape.
2. `test_persistence_engine.py`:
   - in-memory backend: append assigns strictly increasing sequence; `read_recent(n)` returns the most-recent n ascending; `count()` correct.
   - SQLite backend on `tmp_path`: append then read back; close and re-open the same file -> records persist (durability); `initialize()` idempotent; `PersistenceError` on an unwritable path.
   - `StoreBackedDirectedMemoryCandidateProvider`: maps records to tier-correct `MemoryRetrievalCandidate`s with deterministic recency scores; cold store yields `()`.
3. `test_runtime_composition.py`:
   - persistence-enabled assembly with in-memory backend: after a tick, the store `count()` increased and contains the tick's `15` record with preserved linkage.
   - restart continuity (the headline test): assemble handle A on a `tmp_path` SQLite store, run N ticks, drop A; assemble handle B on the same file, run one tick; assert B's directed-retrieval thought-window bundle contains a hit sourced from `experience_store` derived from a prior-session record.
   - cold store: persistence-enabled first tick completes; store-backed provider returns no persisted candidates (no fabrication).
   - fail-fast: persistence enabled with an un-initializable backend -> `RuntimeStartupError` naming `experience_store_ready`.
   - default assembly regression: no `persistence=` -> no store, fabricating provider still used, `experience_store_ready` absent, behavior unchanged.
4. `test_no_adhoc_logging_guard.py` stays green; full suite stays green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_persistence_contracts.py helios_v2/tests/test_persistence_engine.py -q
```
