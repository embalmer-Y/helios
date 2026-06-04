# Requirement 34 - Semantic experience retrieval (embedding + vector recall)

## 1. Background and Problem

R33 made the `15` experience-writeback continuity stream durable and re-entrant across restarts. When persistence is enabled, the `StoreBackedDirectedMemoryCandidateProvider` surfaces persisted experience back into the `10` directed-retrieval thought window. But its selection is **recency only**: it returns the most-recent N records regardless of whether they are relevant to what the system is currently thinking about.

This is a real limitation for the final goal:

1. Recency is not relevance. A current stimulus about "the user's deadline" should preferentially recall prior experience about deadlines, not merely whatever happened most recently. Recency-only recall cannot do this.
2. The locked final-goal standard `FG-1` requires the cognitive chain to be driven by real signals. A retrieval path that ignores content similarity is still a shim in spirit: the candidates it returns do not reflect what the tick is actually about.
3. The `gap_persistence_and_learning` entry in `BRAIN_ARCHITECTURE_COMPARISON.md` explicitly records that semantic/embedding retrieval is requirement `34`; until it lands, durable recall stays recency-bounded.

There is currently no embedding capability anywhere in `helios_v2/src`, and `PersistedExperienceRecord` stores no vector, so the store cannot rank by similarity at all.

R34 is the second slice of `P2`. It introduces a backend-neutral embedding capability owner, stores an embedding vector alongside each persisted experience record, and replaces recency-only recall with deterministic vector similarity search over the durable store, so the system recalls experience that is actually relevant to the current cycle. It is the substrate that the first `P3` de-shim (real `03` novelty as distance-from-memory) will build on; wiring embeddings into the `03` appraisal owner is explicitly out of scope here.

## 2. Goal

Introduce a backend-neutral embedding capability owner and extend the durable experience store with vector storage and deterministic similarity search, so that when semantic memory is enabled each persisted experience record is embedded at write time and the `10` directed-retrieval candidate path recalls experience by content similarity to the current retrieval query rather than by recency alone, while the embedding owner holds no cognitive policy, fails fast when an enabled embedding profile is unready, and the default (non-semantic, recency or non-persistent) assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Embedding capability owner
1. A new owner package (`helios_v2.embedding`) must own a backend-neutral embedding capability, mirroring the `25` LLM gateway pattern. It is a capability owner, not a cognitive owner: it turns text into a vector through a named profile and reports readiness; it never interprets meaning and holds no cognitive policy.
2. The owner must expose neutral `EmbeddingRequest` / `EmbeddingResult` contracts, a named `EmbeddingProfile` and registry, a vendor-neutral `EmbeddingProvider` protocol, and an `EmbeddingGateway` that resolves a request's target profile and dispatches to the injected provider.
3. The first-version concrete provider must be an OpenAI-compatible embedding provider that imports the vendor SDK lazily inside its call path, so importing `helios_v2.embedding` never requires the SDK. A deterministic, network-free fake provider must be available for tests.
4. The gateway must be fail-fast: an unknown profile, a missing or empty api key, empty input text, or a provider failure raises `EmbeddingError`. There is no degraded or fabricated embedding path.
5. The gateway must expose deterministic, network-free static readiness (profile registered and api-key env var non-empty), suitable for wiring into the startup dependency gate, plus an opt-in live readiness probe that issues a real call and is never part of the mandatory startup gate.

### 3.2 Vector storage in the durable store
1. `PersistedExperienceRecord` must gain an optional embedding vector field (absent by default), stored additively so a record without an embedding remains valid.
2. The `ExperienceStoreBackend` protocol and both first-version backends (SQLite file, in-memory double) must persist and read back the embedding vector when present, preserving it exactly across a process restart.
3. The store must expose a deterministic similarity search: given a query vector, a result limit, and a bounded maximum scan, it returns the most-similar embedded records ranked by cosine similarity, ascending-to-descending order made explicit and stable for equal scores.
4. Similarity search must consider only records that carry a stored embedding. A record without an embedding is excluded from semantic results explicitly (it is never silently treated as similar or dissimilar). The number of non-embedded records skipped must be observable through the search result for diagnostics.
5. Similarity computation must be bounded by the configured maximum scan (most-recent embedded records considered) so cost is bounded and deterministic; it must not require an external vector index or any new heavyweight dependency.

### 3.3 Embed-at-write and semantic recall wiring
1. When semantic memory is enabled, the composition append seam must embed each tick's `15` record (its summary) through the embedding gateway and persist the resulting vector with the record, preserving provenance unchanged.
2. When semantic memory is enabled, the `10` directed-retrieval candidate provider must be a semantic provider that embeds the retrieval query text through the gateway and returns candidates ranked by similarity search over the store, mapped to `MemoryRetrievalCandidate`s with the similarity score and store provenance, replacing the recency-only provider.
3. Semantic memory must require durable persistence: enabling the embedding path without a durable experience store is a composition error, not a silent no-op.
4. After a restart against the same durable backend, a current-cycle query must recall the prior session's most semantically similar experience (not merely its most recent), demonstrating semantic continuity across restart.

### 3.4 Opt-in rollout and fail-fast
1. Semantic memory must be an explicit opt-in assembly choice (for example an injected `embedding_gateway` alongside the R33 `experience_store`), default-off. The default assembly, the recency-only persistent assembly, and the channel-bound assembly must all keep working unchanged when semantic memory is off.
2. When semantic memory is enabled, embedding-profile static unreadiness must fail fast at startup through the dependency gate (a critical dependency such as `embedding_profile_ready`). There is no degraded "recall by recency instead" fallback when semantic memory is enabled.
3. There must be no silent fallback from an embedding failure to recency or to a fabricated vector. An embedding failure on an enabled path is a hard stop.

## 4. Non-Functional Requirements

1. Performance: embedding at write is one call per persisted record per tick; similarity search is bounded by the configured maximum scan. Neither changes runtime stage execution behavior in the default assembly.
2. Reliability and fault tolerance: for identical stored vectors and an identical query vector, similarity ranking must be deterministic and stable, independent of wall-clock time, with an explicit, documented tie-break.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Embedding facts (model, dimensions, usage) and similarity scores travel through the embedding and store contracts, never through the log channel.
4. Compatibility and migration: the embedding owner, the optional vector field, the store search method, and the semantic provider are additive and opt-in. A durable store written by a prior non-semantic (recency) session remains readable; its records without embeddings are simply excluded from semantic results until re-embedded (re-embedding/backfill is future work).
5. Dependency hygiene: the first-version embedding provider reuses the already-soft `openai` SDK dependency lazily; no new heavyweight dependency (no faiss/chroma/numpy requirement) is introduced. Similarity is computed with bounded standard-library math.

## 5. Code Behavior Constraints

1. The embedding owner is a capability owner, not a cognitive owner. It must not import or compute salience, thought, planner, governance, autonomy, or retrieval policy, and it must never interpret embedding meaning.
2. The durable store owns vector storage and similarity computation over vectors. It must not embed text itself (it receives vectors), must not rank by meaning beyond cosine over provided vectors, and must remain free of any embedding-owner import.
3. The semantic candidate provider must receive its query-embedding capability by injection (a callable or protocol), so the persistence owner does not depend on the embedding owner. Composition wires the two.
4. `10` directed retrieval remains the sole owner of retrieval planning and thought-window shaping; R34 only changes the candidate source to a semantic one when enabled. `03` appraisal is unchanged: wiring embedding distance into `03` novelty is explicitly deferred to `P3`.
5. No degraded or fallback path when semantic memory is enabled: a missing embedding profile fails fast at startup, and an embedding failure at runtime is a hard stop.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/embedding/__init__.py` (new owner package)
2. `helios_v2/src/helios_v2/embedding/contracts.py` (new: `EmbeddingRequest`, `EmbeddingResult`, `EmbeddingProfile`, registry, `EmbeddingProvider` protocol, `EmbeddingError`, readiness contracts)
3. `helios_v2/src/helios_v2/embedding/engine.py` (new: `EmbeddingGateway`, `OpenAICompatibleEmbeddingProvider`, deterministic fake provider, static + live readiness)
4. `helios_v2/src/helios_v2/persistence/contracts.py` (optional embedding vector on `PersistedExperienceRecord`; a `SimilaritySearchResult`/hit contract; `search_similar` on the backend protocol)
5. `helios_v2/src/helios_v2/persistence/engine.py` (persist/read vectors in both backends; bounded deterministic cosine `search_similar`; `SemanticStoreBackedDirectedMemoryCandidateProvider`)
6. `helios_v2/src/helios_v2/composition/bridges.py` (embed-at-append glue; semantic provider wiring)
7. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in `embedding_gateway` wiring; semantic provider selection; embed-at-write seam on `RuntimeHandle`)
8. `helios_v2/src/helios_v2/composition/dependencies.py` (`embedding_profile_ready` critical dependency + provider when semantic memory is enabled)
9. `helios_v2/tests/test_embedding_contracts.py` (new)
10. `helios_v2/tests/test_embedding_engine.py` (new)
11. `helios_v2/tests/test_persistence_engine.py` (extend: vector round-trip, similarity search)
12. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly, semantic restart recall, fail-fast)
13. `helios_v2/docs/requirements/index.md`
14. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
15. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
16. `helios_v2/docs/PROGRESS_FLOW.en.md`
17. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. A new `helios_v2.embedding` owner exposes documented neutral `EmbeddingRequest`/`EmbeddingResult` contracts, a named-profile registry, an injected `EmbeddingProvider` protocol with a lazy OpenAI-compatible provider and a deterministic fake provider, a fail-fast `EmbeddingGateway`, network-free static readiness, and an opt-in live probe.
2. `PersistedExperienceRecord` carries an optional embedding vector; both backends persist and read it back exactly, surviving a close/re-open of the same SQLite file.
3. The store exposes a deterministic, bounded cosine similarity search that ranks only embedded records, reports the count of non-embedded records skipped, and uses an explicit stable tie-break.
4. With semantic memory enabled, each tick's `15` record is embedded at write and stored with its vector, and the `10` candidate path returns candidates ranked by similarity to the retrieval query (verified: a query close to one stored record ranks that record above a less-similar, more-recent record).
5. Semantic restart recall is demonstrated: after running ticks in session A on a temp-file backend and reopening the same file in session B with semantic memory enabled, a query semantically close to a prior-session record recalls that record by similarity, not merely the most recent.
6. Enabling semantic memory without a durable store raises a composition error; an unready embedding profile fails fast at startup through `embedding_profile_ready`; an embedding failure at runtime is a hard stop with no recency fallback.
7. The default assembly, the recency-only persistent assembly (R33), and the channel-bound assembly are unchanged when semantic memory is off; their existing tests pass unmodified.
8. No new heavyweight dependency is added; the single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R34 builds the embedding/vector substrate and makes recall semantic. The following are explicitly anticipated future work, each via its own requirement package, and must preserve the owner boundaries established here:

1. Real `03` novelty as distance-from-memory (the first `P3` de-shim), consuming this embedding substrate to compute novelty from the nearest stored memory.
2. Re-embedding/backfill of records persisted by a prior non-semantic session.
3. An approximate-nearest-neighbor index or external vector store, replacing bounded brute-force scan, once scale requires it.
4. Embedding additional state families (`06` memory items, `14` identity) once they are de-shimmed and persisted.
5. Hybrid recall combining similarity, recency, and affect once `04`/`05` produce real signals.

None of these may be smuggled into this slice. R34 introduces no cognitive ownership in the embedding owner, does not change the `03` appraisal owner or any other cognitive owner's policy, and grants the store no runtime decision authority.
