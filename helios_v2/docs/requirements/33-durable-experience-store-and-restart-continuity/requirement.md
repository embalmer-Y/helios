# Requirement 33 - Durable experience store and restart continuity (P2 opener)

## 1. Background and Problem

Helios v2 advances state every tick and closes a within-process continuity loop: `15` experience-writeback publishes `ExperienceWritebackResult` objects (each carrying a `ContinuityEvidencePacket` and `ConsolidationCandidate`s) that the `15 -> 06` loop feeds back so each tick is subjectively connected to the previous one.

But that continuity is entirely in-memory. There is no persistence anywhere in `helios_v2/src` (no durable store, no reload). Concretely:

1. When the process exits, every continuity packet, every autobiographical trace, and the whole experience stream are lost. The next start is a cold mind with no past.
2. `15` explicitly does not own raw backend storage writes, and `06` carries only a `storage_bootstrap_state_id` string with no real durable backing.
3. The `10` directed-retrieval candidate provider is a composition shim that fabricates fixed candidates; even within one process it never surfaces the real experience the runtime actually produced.

This is the single highest-leverage structural gap for the final goal. The locked phase roadmap in `ARCHITECTURE_PHILOSOPHY.zh-CN.md` (section 13) places `P2` (durable memory and knowledge base) as the common prerequisite for `P3-P7`: de-shimming, tool use, learning, self-revision, and code self-modification all require experience that survives a restart. The final-goal acceptance standard `FG-5.1` requires that "after a process restart, the system retains episodic/semantic/autobiographical memory and continuity and can subjectively re-enter its prior existence". A runtime that resets to empty on every start cannot meet that standard and cannot meaningfully self-evolve.

R33 is the first slice of `P2`. It establishes the durable experience store as a formal owner, persists the real experience stream, and makes the persisted experience re-enter the cognitive chain after a restart, so restart continuity becomes a verifiable runtime fact rather than an aspiration.

## 2. Goal

Introduce a durable experience-store owner that persists each tick's experience-writeback continuity records to a durable backend with preserved provenance, reloads them on startup, and surfaces the persisted experience back into the directed-retrieval candidate path through an explicit owner-neutral seam, so that after a process restart the system retrieves and re-enters its real prior-session experience, while the store holds no cognitive policy, fails fast when an enabled backend is unavailable, and the default (non-persistent) assembly stays byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Durable experience-store owner
1. A new owner package (`helios_v2.persistence`) must own the durable experience store. It is infrastructure, like observability: it holds no cognitive policy, makes no salience/selection/thought decision, and never interprets the meaning of what it stores.
2. The store must persist a formal, immutable `PersistedExperienceRecord` per stored item, preserving at minimum: a store-assigned monotonic sequence, the source tick id, the continuity kind, the outcome class, the source-outcome kind and id, the summary and requested/applied effect summaries, the reason trace, and the upstream linkage provenance carried by the originating `ContinuityEvidencePacket`.
3. The store must expose a narrow public API: append a bounded batch of records, read the most-recent-N records in deterministic order, count stored records, and produce a bounded read-only prior-existence snapshot for startup diagnostics.
4. The concrete durable backend must be injected behind a backend protocol. The first-version backend must be a local file-backed SQLite backend (standard library, no new dependency). Tests must be able to inject a deterministic in-memory backend double and a temp-file SQLite backend without touching any shared location.

### 3.2 Writing the experience stream
1. When persistence is enabled, the runtime must append each completed tick's `15` experience-writeback continuity records to the store after the writeback stage, through an explicit owner-neutral composition seam (mirroring the existing post-tick timeline carry), without adding a new runtime stage and without changing `CANONICAL_STAGE_ORDER` or `CHANNEL_BOUND_STAGE_ORDER`.
2. The append seam must preserve every record's upstream provenance (the `source_provenance` linkage ids and the source-outcome id) verbatim. It must not compute, reinterpret, or drop any owner status.
3. Appending must be append-only and ordered. The store must not mutate or delete prior records during normal runtime operation in this slice.

### 3.3 Reloading and restart re-entry
1. On startup, when persistence is enabled, the store must load the previously persisted records from the durable backend so that records written by a prior process are available to the new process.
2. The persisted experience must re-enter the cognitive chain: when persistence is enabled, the `10` directed-retrieval candidate provider must be a store-backed provider that surfaces persisted experience records as `MemoryRetrievalCandidate`s (mapped to the autobiographical/episodic tiers) using deterministic recency-based selection.
3. After a restart against the same durable backend, a tick must retrieve candidates derived from the prior session's persisted experience, so the prior session re-enters the new session's thought window.
4. On a cold store (no prior records), the store-backed provider must return zero persisted candidates explicitly rather than fabricating any, and the runtime must still complete the tick.

### 3.4 Opt-in rollout and fail-fast
1. Persistence must be an explicit opt-in assembly choice in this slice (for example `assemble_runtime(persistence=...)`), default-off, mirroring the established opt-in patterns for the observability recorder and the channel-bound assembly. The default assembly must remain non-persistent and behaviorally unchanged.
2. When persistence is enabled, store-backend unavailability (an un-initializable or unwritable backend) must fail fast at startup through the dependency gate (a critical dependency such as `experience_store_ready`). There must be no degraded "run without persisting" mode when persistence is enabled.
3. There must be no silent fallback from a persistence write failure to a non-persistent path. A write failure on an enabled store is a hard stop.

## 4. Non-Functional Requirements

1. Performance: appends and recent-record reads must be bounded per tick (bounded batch in, bounded most-recent-N out) and must not change runtime execution behavior in the default assembly.
2. Reliability and fault tolerance: for an identical sequence of appends, the store's recent-record reads must be deterministic and ordered by the store-assigned sequence, independent of wall-clock time. Durability must survive process exit and re-open of the same backend file.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Durability facts travel through the store contracts, never through the log channel.
4. Compatibility and migration: the store owner, the append seam, and the store-backed candidate provider are additive and opt-in. The default 19-stage and opt-in 21-stage assemblies must both keep working unchanged when persistence is off.
5. Repository hygiene: the durable store file/location must be git-ignored so runtime data is never committed.

## 5. Code Behavior Constraints

1. The persistence owner is infrastructure, not a cognitive owner. It must not import or compute salience, thought, planner, governance, or autonomy decisions, and it must not rank candidates by meaning in this slice (recency/provenance only).
2. The composition owner remains assembly-only. The append seam and the store-backed candidate provider wiring must be owner-neutral glue that forwards explicit upstream contract fields; they must not compute a downstream owner's decision.
3. `15` experience-writeback remains the sole owner of continuity classification and writeback results; `10` directed-retrieval remains the sole owner of retrieval planning and thought-window shaping. R33 only changes where `10`'s candidates come from (a real store instead of a fabricated shim) when persistence is enabled; it must not move retrieval policy into the store.
4. No embedding, vector index, or semantic similarity ranking may be introduced in this slice. Selection is deterministic recency/provenance-based. Semantic retrieval is requirement `34`.
5. No degraded or fallback persistence path is allowed when persistence is enabled. Missing/broken backend fails fast; write failure is a hard stop.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/persistence/__init__.py` (new owner package)
2. `helios_v2/src/helios_v2/persistence/contracts.py` (new: `PersistedExperienceRecord`, `PriorExistenceSnapshot`, backend protocol, store API, `PersistenceError`)
3. `helios_v2/src/helios_v2/persistence/engine.py` (new: `ExperienceStore`, `SqliteExperienceStoreBackend`, in-memory backend double, store-backed directed-retrieval candidate provider)
4. `helios_v2/src/helios_v2/composition/bridges.py` (owner-neutral writeback-to-record append bridge; store-backed candidate provider wiring)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (`persistence` opt-in assembly arg; post-tick append seam on `RuntimeHandle`; store-backed provider selection)
6. `helios_v2/src/helios_v2/composition/dependencies.py` (`experience_store_ready` critical dependency + provider when persistence is enabled)
7. `helios_v2/tests/test_persistence_contracts.py` (new)
8. `helios_v2/tests/test_persistence_engine.py` (new)
9. `helios_v2/tests/test_runtime_composition.py` (persistence-enabled assembly, restart-continuity test)
10. `helios_v2/.gitignore` (ignore the durable store location)
11. `helios_v2/docs/requirements/index.md`
12. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
13. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
14. `helios_v2/docs/PROGRESS_FLOW.en.md`
15. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. A new `helios_v2.persistence` owner exposes a documented, immutable `PersistedExperienceRecord`, a bounded `PriorExistenceSnapshot`, a backend protocol, and an `ExperienceStore` API (append batch, recent-N, count, snapshot), with fail-fast validation on malformed records and backend errors.
2. The first-version SQLite file backend persists records to a local file and reads them back, ordered by a store-assigned monotonic sequence, deterministically and independent of wall-clock time; an in-memory backend double supports fast deterministic unit tests.
3. When persistence is enabled, each completed tick's `15` continuity records are appended to the store with upstream provenance preserved verbatim, through an owner-neutral post-tick seam, with no change to `CANONICAL_STAGE_ORDER` or `CHANNEL_BOUND_STAGE_ORDER`.
4. With persistence enabled and a fresh (cold) store, a tick completes and the store-backed candidate provider returns zero persisted candidates explicitly (no fabrication).
5. Restart continuity is demonstrated: after running N ticks against a temp-file backend, tearing down the handle, assembling a new handle against the same backend file, and running one tick, the directed-retrieval thought-window bundle contains candidates derived from the prior session's persisted experience.
6. When persistence is enabled and the backend is un-initializable or unwritable, startup fails fast through the dependency gate (`experience_store_ready`); there is no degraded non-persistent execution and no silent fallback on write failure.
7. The default (non-persistent) assembly is byte-for-byte unchanged: existing composition tests pass without modification, and no persistence side effect occurs when persistence is off.
8. No embedding/vector/semantic ranking is introduced; selection is deterministic recency/provenance-based.
9. The single-logging-mechanism guard test still passes, the durable store location is git-ignored, and the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

This requirement establishes durable experience and restart re-entry while retrieval selection stays deterministic. The following are explicitly anticipated future work, each via its own requirement package, and must preserve the owner boundaries established here:

1. Embedding-based semantic retrieval and vector ranking over the same store (`34`), replacing recency-only selection.
2. Persisting and reloading additional state families (memory-affect items from `06`, neuromodulator/feeling state from `04`/`05`, identity state from `14`) as later P2/P3 slices.
3. Making a persistent assembly the default runtime once a real external driver and persistence are jointly proven.
4. Consolidation, forgetting/decay, and bounded compaction policies over the durable store.
5. Cross-run learning and parameter persistence built on this store (`P5`).

None of these may be smuggled into this slice. R33 introduces no embeddings, no semantic ranking, no cognitive ownership in the store, and no default-on persistence; it does not change any cognitive owner's policy and grants the store no runtime decision authority.
