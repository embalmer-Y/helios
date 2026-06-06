# Requirement 52 - Workspace multiplicity from recalled affect-memory replay

## 1. Background and Problem

R46/R47/R48 de-shimmed the `07` workspace competition, the `08` conscious-ignition commitment, and the `09` gate's `global_activation_level` into real, owner-owned behaviors. But all three are effectively **dormant**, because the chain forms exactly one workspace candidate per tick:

1. The `02 -> 06` path produces one `MemoryBindingContext` per tick, and the `06` `AffectGroundedMemoryFormationPath` forms exactly one `AffectTaggedMemoryItem` from it (one binding context -> one item).
2. The `06` salience gate produces one `MemoryReplayCandidate` for that one item.
3. The `07` `SalienceWeightedWorkspaceCompetitionPath` builds one `WorkspaceCandidate` per replay candidate, so it competes over a single candidate.
4. With one candidate, R46's competition score has nothing to rank against, R47's winner-take-all ignition always "wins" the only candidate (so the headline "multiplicity -> ignite winner" is owner-level tested but never exercised end to end, as R47's own note records), and R48's `global_activation_level` is just that one candidate's score.

This is the largest remaining "real behavior implemented but never activated" gap in the P3 chain. In a brain, the global workspace is a competition among *multiple simultaneous contents*: current perception plus replayed memories. Helios already durably stores affect-tagged memories (R45) and recalls them semantically (R34), but that recall feeds only the `10` thought window (for `11`), never the `07` workspace competition. So the workspace never has a genuine multiplicity to arbitrate, and the real competition/ignition logic stays unexercised.

A second, smaller gap blocks doing this honestly: the R45 affect-memory persistence writes the memory's family and a content summary but **not its affect vector**, so a recalled memory cannot retain its original felt charge — yet the entire point of affect-memory replay is that an emotionally charged memory competes strongly for attention.

## 2. Goal

Give the `07` workspace competition a genuine multiplicity to arbitrate by having the `06` memory owner surface recalled prior affect-memories as additional replay candidates alongside the current-tick formed memory, so that under the semantic-memory assembly the workspace competes over multiple real candidates (current perception plus semantically-recalled past affect-memories), R46/R47/R48 become exercised end to end (the workspace ignites a genuine winner among several candidates, and the gate activation reflects the strongest content held in attention), the recalled candidates carry their original persisted affect and a recall-relevance-derived priority through an owner-owned replay-priority mapping, and the default/recency/non-semantic and cold-store paths are unchanged (no recalled candidates, so behavior is byte-for-byte as before until a prior affect-memory exists to replay).

## 3. Functional Requirements

### 3.1 Recalled-memory replay surfacing in the `06` owner
1. The `06` memory owner must, when a recalled-memory source is available, surface zero or more recalled prior affect-memories as additional `MemoryReplayCandidate`s in the same `MemoryFormationState`, alongside the current-tick formed candidate.
2. Each recalled replay candidate must reference a re-formed `AffectTaggedMemoryItem` that preserves the recalled memory's original `memory_id`, its stored `family`, and its original persisted `affect_tag` (the felt affect at the time it was formed), and is anchored to the current tick's feeling state as the surfacing context (so the existing `MemoryFormationState` provenance invariants hold).
3. The recalled candidates' priority must be computed by an owner-owned replay-priority mapping from real facts (the recall relevance and the recalled affect intensity), under the owner's declared `replay_priority_policy` learned-parameter category. The recalled-memory source must supply only raw facts; the priority mapping is owned by `06`.
4. Recalled replay candidates must not be marked `forced_consolidation` (they are being replayed, not newly consolidated), so the R45 durable-persistence carry does not re-persist an already-stored memory.
5. The current-tick formed memory and its salience-gated candidate must be unchanged by this requirement; recalled candidates are strictly additive to the published candidate set.

### 3.2 Owner-neutral recalled-memory source
1. The recalled-memory source must be injected behind a narrow protocol; the `06` owner must not import the persistence or embedding owner.
2. A composition-owned implementation must semantically recall prior affect-memories from the durable store: it embeds the current binding context content through the injected embedding callable and ranks stored `affect_memory`-kind records by cosine similarity (reusing the R34 store similarity surface), returning bounded raw recalled-memory facts (memory id, family, summary, recall similarity, and the reconstructed affect vector).
3. The recalled affect vector must be reconstructed from the durably persisted affect-memory record. To make this possible, the durable affect-memory record (written by the R45 carry seam) must additionally carry the formed memory's affect vector as part of its opaque metadata; this is an additive metadata extension, not a persistence contract change.
4. Recall must be bounded (a small first-version limit and a bounded scan) and deterministic for a fixed store state and query.

### 3.3 End-to-end multiplicity activation
1. Under the semantic-memory assembly, once at least one prior consolidation-worthy affect-memory exists in the store, a later tick's `07` workspace competition must receive more than one candidate (the current-tick candidate plus one or more recalled candidates).
2. The `07` competition must rank them by the real competition score, the `08` ignition must commit the single highest-scoring retained candidate as focal content (and demote the rest to supporting context), and the `09` `global_activation_level` must reflect the maximum retained candidate score — all already implemented by R46/R47/R48 and now exercised over genuine multiplicity.
3. A recalled memory with sufficiently high recall relevance and affect must be able to win the workspace competition over a weaker current-tick candidate (a strong memory can dominate attention), and this outcome must be reconstructable from the published `07`/`08` stage results.

### 3.4 Opt-in rollout and fail-fast
1. Recalled replay surfacing must activate only under the semantic-memory assembly (store + embedding present). The default, recency-only, channel-bound-without-semantic, and offline assemblies must be byte-for-byte unchanged (no recalled candidates).
2. A cold store, an empty/absent binding context, or no similar prior memory must yield zero recalled candidates (the single-candidate behavior, unchanged), never a fabricated recalled memory.
3. An embedding or store failure during recall must be a hard stop (consistent with the R35 novelty source), never a silent fallback that drops to single-candidate behavior while pretending recall succeeded.

## 4. Non-Functional Requirements

1. Performance: recall is one bounded embedding call plus one bounded similarity scan per tick (the same cost class as the R35 novelty source); no new stage, no blocking I/O beyond the existing store, no network in tests.
2. Reliability and fault tolerance: for a fixed store state and query, the recalled candidates and their priorities are deterministic and bounded.
3. Observability and logging: no second logging mechanism; no `logging`/`print` under `helios_v2/src`. Recalled facts travel only through the existing memory/workspace contracts.
4. Compatibility and migration: additive — a new `06`-owned recalled-replay path, a new injected source protocol, an additive metadata extension on the affect-memory record write, and opt-in wiring. No change to `MemoryReplayCandidate`, `MemoryFormationState`, `WorkspaceCandidate`, or any downstream contract. Existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The recalled-replay priority mapping and the re-forming of recalled facts into items/candidates are owned by `helios_v2.memory`. The recalled-memory source supplies raw facts only; composition owns the store/embedding access and the affect reconstruction.
2. The `06` owner must not import the persistence or embedding owner. It reaches the store only through the injected recalled-memory source.
3. Recalled candidates must be additive and non-`forced_consolidation`; they must not alter the current-tick formed memory, its gate decision, or the R45 persistence carry.
4. No fabricated recall: a cold store or no similar memory yields zero recalled candidates; an outright embedding/store failure propagates as a hard stop.
5. No `logging`/`print` anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/memory/contracts.py` (new `RecalledMemoryFact` contract + `RecalledMemoryProvider` protocol)
2. `helios_v2/src/helios_v2/memory/engine.py` (owner-owned recalled-replay surfacing path + priority mapping; engine consumes the optional injected provider)
3. `helios_v2/src/helios_v2/memory/__init__.py` (exports)
4. `helios_v2/src/helios_v2/composition/bridges.py` (extend `MemoryRecordBridge` to persist the affect vector in metadata; new `StoreBackedRecalledMemoryProvider` reconstructing facts from the store)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (wire the provider into the `06` engine under the semantic-memory assembly)
6. `helios_v2/tests/test_memory_engine.py` (recalled surfacing: priority mapping, additive candidates, non-forced, deterministic, cold/empty yields none)
7. `helios_v2/tests/test_runtime_composition.py` (end-to-end: after a prior affect-memory is persisted, a later tick's `07` competes over >1 candidate, `08` ignites a winner, `09` activation reflects it; default unchanged)
8. `helios_v2/docs/requirements/index.md`
9. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
10. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (narrow the `08`/`09-11` multiplicity caveats and `gap_persistence_and_learning` recall-into-workspace note)
11. `helios_v2/docs/OWNER_GUIDE.md`, `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`, `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, the `06` owner surfaces recalled prior affect-memories as additional `MemoryReplayCandidate`s when the injected recalled-memory source returns facts; each references a re-formed `AffectTaggedMemoryItem` preserving the recalled `memory_id`, stored `family`, and original persisted `affect_tag`, anchored to the current feeling state, and the existing `MemoryFormationState` invariants hold.
2. Recalled candidates carry an owner-computed priority from recall relevance and recalled affect intensity (under `replay_priority_policy`), are not `forced_consolidation`, and are strictly additive (the current-tick candidate is unchanged).
3. The recalled-memory source is injected behind a protocol returning raw facts; the `06` owner imports neither the persistence nor the embedding owner; the composition provider reconstructs the affect vector from the durably persisted affect-memory metadata.
4. End-to-end: after at least one consolidation-worthy affect-memory is persisted, a later tick's `07` `WorkspaceCompetitionStageResult` carries more than one candidate, the `08` ignition commits the single highest-scoring retained candidate as focal content with the rest demoted to supporting context, and the `09` `global_activation_level` equals the maximum retained candidate score; a sufficiently strong recalled memory can be the ignited winner.
5. A cold store, empty/absent binding context, or no similar prior memory yields zero recalled candidates (single-candidate behavior unchanged); an embedding/store failure during recall is a hard stop, never a silent single-candidate fallback.
6. The default, recency-only, channel-bound-without-semantic, and offline assemblies are byte-for-byte unchanged (no recalled candidates); the affect-memory metadata extension is additive and an existing R33/R34/R45 store file still reads back.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R52 introduces workspace multiplicity from recalled affect-memory replay. The following remain explicitly future, each via its own requirement, and must preserve the owner boundaries established here:

1. Multiplicity from concurrent current-tick contents (multiple stimuli / binding contexts in one tick), once the `02`/`03` stimulus projection is de-shimmed (R54 territory).
2. Genuine semantic-conflict detection in `08` (the `semantic_conflict_unresolved` path R47 reserved) once competing candidates can genuinely contradict.
3. P5 learning of the recalled-replay priority mapping weights and the recall limit (under `replay_priority_policy`).
4. Feeding the recalled affect back into `04`/`05` (re-experiencing a memory re-evokes affect) as a closed affective-replay loop.
