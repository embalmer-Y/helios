# Requirement 33 - Durable experience store and restart continuity (tasks)

## 1. Task Breakdown

### Task 1 - Persistence contracts
1. Create `helios_v2/src/helios_v2/persistence/contracts.py` with `PersistenceError`, `PersistedExperienceRecord` (validation per design 4.1; frozen immutable `linkage`), `PriorExistenceSnapshot`, and the `ExperienceStoreBackend` protocol.
2. Create `helios_v2/src/helios_v2/persistence/__init__.py` exporting the contract symbols (engine symbols added in Task 2).
3. Completion: contracts import cleanly; record validation rejects empty required fields and freezes `linkage`.
4. Validation: `pytest helios_v2/tests/test_persistence_contracts.py -q`.

### Task 2 - Store engine + backends + candidate provider
1. Create `helios_v2/src/helios_v2/persistence/engine.py` with `ExperienceStore`, `InMemoryExperienceStoreBackend`, `SqliteExperienceStoreBackend`, and `StoreBackedDirectedMemoryCandidateProvider`.
2. Implement strictly-increasing store-assigned sequence, deterministic `read_recent` (most-recent-N ascending), `count`, idempotent `initialize`, and `prior_existence_snapshot`.
3. SQLite backend: `sqlite3` file store, JSON-encoded `reason_trace`/`linkage`, `PersistenceError` wrapping `sqlite3.Error`.
4. `StoreBackedDirectedMemoryCandidateProvider.collect_candidates` maps records to tier-correct `MemoryRetrievalCandidate`s with deterministic recency scores; cold store yields `()`.
5. Export engine symbols from `__init__.py`.
6. Completion: in-memory and SQLite backends round-trip; provider maps correctly; cold store explicit empty.
7. Validation: `pytest helios_v2/tests/test_persistence_engine.py -q`.

### Task 3 - Composition wiring (record bridge + append seam + opt-in)
1. Add `ExperienceRecordBridge` to `composition/bridges.py` (owner-neutral projection of each `ExperienceWritebackResult` into a `PersistedExperienceRecord`, preserving `source_provenance` linkage verbatim).
2. In `composition/runtime_assembly.py`: add the opt-in `persistence` argument; when provided, wire `StoreBackedDirectedMemoryCandidateProvider` into the directed-retrieval stage, store + bridge into `RuntimeHandle`, and register `experience_store_ready`; otherwise keep `FirstVersionDirectedMemoryCandidateProvider` and register nothing new.
3. Add `RuntimeHandle._persist_experience(result)` called from `tick()` after the existing carries; no-op when no store.
4. In `composition/dependencies.py`: add `EXPERIENCE_STORE_READY`, `experience_store_critical_dependency_spec()`, and `ExperienceStoreReadinessDependencyProvider` (wraps baseline; available iff backend initializes).
5. Completion: opt-in persistence assembly runs a tick and appends; default assembly unchanged.
6. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Tests
1. `test_persistence_contracts.py`: record validation, snapshot shape.
2. `test_persistence_engine.py`: sequence monotonicity, recent-N order, count, SQLite durability across re-open (`tmp_path`), `initialize` idempotency, `PersistenceError` on unwritable path, provider mapping + cold-store empty.
3. `test_runtime_composition.py`: per-tick append with preserved linkage; the restart-continuity headline test (two handles, same SQLite file, prior session re-enters via `experience_store`-sourced hit); cold-store completes; fail-fast on un-initializable backend; default-assembly regression.
4. Completion: all new tests pass; restart-continuity test asserts provenance (`source == "experience_store"`), not just presence.
5. Validation: `pytest helios_v2/tests/test_persistence_contracts.py helios_v2/tests/test_persistence_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 5 - Documentation sync
1. `index.md`: add the R33 row (status draft, maturity per evidence), depends on `15, 10, 22`.
2. `ARCHITECTURE_BOUNDARIES.md`: add the `helios_v2.persistence` owner to the core owner map and an owner snapshot + migration-state note; record that composition carries the experience append as owner-neutral glue and that the store is never an authoritative inter-owner transport.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: add a `gap_persistence_and_learning` entry (or narrow it) noting R33 establishes durable episodic/autobiographical continuity and restart re-entry; link `P2`.
4. `PROGRESS_FLOW.en.md` and `PROGRESS_FLOW.zh-CN.md` (same change set): add the persistence infra owner node and the durable `15 -> store -> 10` re-entry edge; update last-synced to R33; update test baseline count.
5. `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 13 table: mark `P2` as in-progress with R33 as its opener (optional, only if the phase table tracks per-requirement status).
6. Completion: no doc/code drift; index, boundaries, comparison, both flow maps consistent.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `15` experience-writeback (`ExperienceWritebackResult`, `ContinuityEvidencePacket`, `source_provenance`) — shipped.
2. Depends on `10` directed retrieval (`DirectedMemoryCandidateProvider`, `MemoryRetrievalCandidate`) — shipped.
3. Depends on `22` composition assembly seam and `RuntimeHandle` post-tick carry pattern — shipped.
4. No dependency on embeddings/vectors (R34) or on the channel-bound assembly.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/persistence/__init__.py` (Tasks 1-2)
2. `helios_v2/src/helios_v2/persistence/contracts.py` (Task 1)
3. `helios_v2/src/helios_v2/persistence/engine.py` (Task 2)
4. `helios_v2/src/helios_v2/composition/bridges.py` (Task 3)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 3)
6. `helios_v2/src/helios_v2/composition/dependencies.py` (Task 3)
7. `helios_v2/tests/test_persistence_contracts.py` (Task 4)
8. `helios_v2/tests/test_persistence_engine.py` (Task 4)
9. `helios_v2/tests/test_runtime_composition.py` (Task 4)
10. `helios_v2/docs/requirements/index.md` (Task 5)
11. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 5)
12. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 5)
13. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 5)
14. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 5)

## 4. Implementation Order

1. Task 1 (contracts) — foundation.
2. Task 2 (engine + backends + provider) — owner behavior; independently testable.
3. Task 3 (composition wiring) — opt-in seam, append, dependency.
4. Task 4 (tests) — alongside Tasks 1-3, finalized here, with the restart-continuity headline test.
5. Task 5 (docs) — last, once behavior and maturity are evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_persistence_contracts.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_persistence_engine.py -q`.
3. After Task 3: `pytest helios_v2/tests/test_runtime_composition.py -q`.
4. After Task 4: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
5. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. A `helios_v2.persistence` owner exposes the record/snapshot contracts, backend protocol, SQLite + in-memory backends, the `ExperienceStore` facade, and the store-backed candidate provider, all fail-fast.
2. SQLite durability is proven across a close/re-open of the same file, ordered by store-assigned sequence and independent of wall-clock.
3. With persistence enabled, each tick appends its `15` continuity records with upstream linkage preserved verbatim, with no stage-order change.
4. Restart continuity is demonstrated end to end: a second handle on the same backend file retrieves prior-session experience into the directed-retrieval thought window (hit `source == "experience_store"`).
5. Cold store returns no fabricated candidates and the tick still completes; un-initializable backend fails fast through `experience_store_ready`.
6. The default (non-persistent) assembly is byte-for-byte unchanged; existing composition tests pass unmodified.
7. No embedding/vector/semantic ranking introduced; selection is deterministic recency/provenance.
8. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and both `PROGRESS_FLOW` maps are updated in the same change set; the durable store path is git-ignored.
9. The single-logging-mechanism guard and the full test suite remain green and network-free.
