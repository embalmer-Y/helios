# Requirement 34 - Semantic experience retrieval (tasks)

## 1. Task Breakdown

### Task 1 - Embedding owner contracts
1. Create `helios_v2/src/helios_v2/embedding/contracts.py`: `EmbeddingError`, `EmbeddingProfile`, `EmbeddingRequest` (validates non-empty id/profile/text), `EmbeddingUsage`, `ProviderEmbedding`, `EmbeddingResult`, `EmbeddingProfileReadiness`/`EmbeddingReadinessReport` (mirror `25`), and the `EmbeddingProvider` protocol.
2. Create `helios_v2/src/helios_v2/embedding/__init__.py` exporting contract symbols (engine symbols added in Task 2).
3. Completion: contracts import cleanly; request validation rejects empty fields.
4. Validation: `pytest helios_v2/tests/test_embedding_contracts.py -q`.

### Task 2 - Embedding gateway + providers
1. Create `helios_v2/src/helios_v2/embedding/engine.py`: `EmbeddingProfileRegistry` (unique names), `EmbeddingGateway` (resolve profile, fail-fast key resolution from injected env, dispatch, latency, validate non-empty vector output), `OpenAICompatibleEmbeddingProvider` (lazy `openai` import), `check_static_readiness`, `probe_live_readiness`.
2. Export engine symbols from `__init__.py`.
3. Completion: gateway returns a vector via an injected fake provider; unknown profile / missing key / empty text / provider failure raise `EmbeddingError`; static readiness is network-free.
4. Validation: `pytest helios_v2/tests/test_embedding_engine.py -q`.

### Task 3 - Vector storage + similarity search in persistence
1. `persistence/contracts.py`: add `embedding: tuple[float,...] | None = None` and `with_embedding` to `PersistedExperienceRecord`; add `SimilarityHit`, `SimilaritySearchResult`; add `search_similar` to the backend protocol.
2. `persistence/engine.py`: add module-level `cosine_similarity` (standard-library; raises on dimension mismatch / zero-norm); persist/read the vector (nullable JSON column) in `SqliteExperienceStoreBackend`; store/return it in `InMemoryExperienceStoreBackend`; implement bounded deterministic `search_similar` in both (descending similarity, tie-break descending sequence, bounded by `max_scan`, excluding + counting non-embedded records); add `SemanticStoreBackedDirectedMemoryCandidateProvider` taking an injected `embed_query` callable.
3. Export new persistence symbols.
4. Completion: vector round-trips across SQLite re-open; `search_similar` ranks near above far and counts skipped; semantic provider maps hits and is cold-safe.
5. Validation: `pytest helios_v2/tests/test_persistence_engine.py -q`.

### Task 4 - Composition wiring
1. `composition/dependencies.py`: add `EMBEDDING_PROFILE_READY`, `embedding_profile_critical_dependency_spec()`, `EmbeddingReadinessDependencyProvider` (mirror `LlmReadinessDependencyProvider`).
2. `composition/runtime_assembly.py`: add `embedding_gateway` param; raise `CompositionError` if set without `experience_store`; when both present, select the semantic provider for `10` (inject an `embed_query` bound to the gateway + a composition embedding profile name), set `RuntimeHandle.embed_record` for embed-at-write, and register `embedding_profile_ready`.
3. `composition/bridges.py` (if needed): owner-neutral helpers binding the gateway into `embed_query`/`embed_record` callables.
4. `RuntimeHandle._persist_experience`: embed each record before append when `embed_record` is present; embedding failure is a hard stop.
5. Completion: semantic assembly runs a tick (embeds + stores vector); default/recency/channel-bound unchanged.
6. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 5 - Tests
1. `test_embedding_contracts.py`, `test_embedding_engine.py` (Tasks 1-2 surfaces) with a deterministic `FakeEmbeddingProvider`.
2. Extend `test_persistence_engine.py`: vector round-trip, `cosine_similarity`, `search_similar` ranking/skip/bound/tie-break, semantic provider mapping + cold store.
3. Extend `test_runtime_composition.py`: semantic ranking-over-recency; semantic restart recall (headline); `CompositionError` without store; fail-fast unready profile; embedding-failure hard stop; default/recency/channel-bound regression.
4. Completion: all new/extended tests pass; semantic restart test asserts `source="experience_store_semantic"` and similarity-over-recency, not just presence.
5. Validation: `pytest helios_v2/tests/test_embedding_contracts.py helios_v2/tests/test_embedding_engine.py helios_v2/tests/test_persistence_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 6 - Documentation sync
1. `index.md`: add the R34 row (depends on `33, 10, 25`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add the `helios_v2.embedding` owner to the core owner map; add an owner snapshot/migration-state note; record that the persistence owner gained vector storage + similarity but stays free of any embedding-owner import, and that composition injects `embed_query`/`embed_record`.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: narrow `gap_persistence_and_learning` (recall is now semantic, not recency-only); note `03` novelty-from-memory remains the next `P3` slice.
4. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): add the embedding capability owner node and mark the `store -> 10` edge as semantic when enabled; update last-synced to R34 and the test baseline count.
5. Completion: no doc/code drift across index, boundaries, comparison, both flow maps.
6. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `33` durable experience store (record, backends, `ExperienceStore`, candidate provider, append seam) — shipped.
2. Depends on `10` directed retrieval (`DirectedMemoryCandidateProvider`, `MemoryRetrievalCandidate`, `RetrievalQueryPlan.query_text`) — shipped.
3. Reuses the `25` gateway pattern as the model for the embedding owner (no code dependency; parallel structure) — shipped.
4. No dependency on `03` appraisal (novelty-from-memory is a later `P3` requirement).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/embedding/__init__.py` (Tasks 1-2)
2. `helios_v2/src/helios_v2/embedding/contracts.py` (Task 1)
3. `helios_v2/src/helios_v2/embedding/engine.py` (Task 2)
4. `helios_v2/src/helios_v2/persistence/contracts.py` (Task 3)
5. `helios_v2/src/helios_v2/persistence/engine.py` (Task 3)
6. `helios_v2/src/helios_v2/composition/dependencies.py` (Task 4)
7. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 4)
8. `helios_v2/src/helios_v2/composition/bridges.py` (Task 4)
9. `helios_v2/tests/test_embedding_contracts.py` (Task 5)
10. `helios_v2/tests/test_embedding_engine.py` (Task 5)
11. `helios_v2/tests/test_persistence_engine.py` (Task 5, extend)
12. `helios_v2/tests/test_runtime_composition.py` (Task 5, extend)
13. `helios_v2/docs/requirements/index.md` (Task 6)
14. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 6)
15. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 6)
16. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 6)
17. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 6)

## 4. Implementation Order

1. Task 1 (embedding contracts) — foundation.
2. Task 2 (embedding gateway + providers) — capability owner behavior.
3. Task 3 (vector storage + similarity in persistence) — store-side semantic substrate; independent of composition.
4. Task 4 (composition wiring) — opt-in semantic assembly + embed-at-write + dependency.
5. Task 5 (tests) — alongside Tasks 1-4, finalized here with the semantic restart headline test.
6. Task 6 (docs) — last, once behavior and maturity are evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_embedding_contracts.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_embedding_engine.py -q`.
3. After Task 3: `pytest helios_v2/tests/test_persistence_engine.py -q`.
4. After Task 4: `pytest helios_v2/tests/test_runtime_composition.py -q`.
5. After Task 5: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
6. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. A `helios_v2.embedding` capability owner exposes neutral request/result contracts, a named-profile registry, an injected provider protocol (lazy OpenAI-compatible + deterministic fake), a fail-fast gateway, network-free static readiness, and an opt-in live probe.
2. `PersistedExperienceRecord` carries an optional embedding vector that both backends persist and read back exactly across a SQLite re-open.
3. The store performs deterministic, bounded cosine similarity search ranking only embedded records, reporting skipped non-embedded records, with an explicit stable tie-break.
4. With semantic memory enabled, records are embedded at write and `10` recalls by similarity to the query; a near record ranks above a more-recent less-similar record.
5. Semantic restart recall is demonstrated end to end (hit `source="experience_store_semantic"`, similarity-over-recency, across a process restart on the same SQLite file).
6. Enabling semantic memory without a store raises `CompositionError`; an unready embedding profile fails fast through `embedding_profile_ready`; a runtime embedding failure is a hard stop with no recency fallback.
7. The default, recency-only persistent, and channel-bound assemblies are unchanged when semantic memory is off; their existing tests pass unmodified.
8. No new heavyweight dependency; the `03` appraisal owner and all other cognitive owners are unchanged; `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, and both `PROGRESS_FLOW` maps are updated in the same change set; the guard and full suites stay green and network-free.
