# Requirement 45 - Affect-grounded memory formation and durable memory store (P2 closeout / P3 mid-chain)

## 1. Background and Problem

The cognition main chain runs end to end, but the `06` memory affect-and-replay owner is the highest-leverage remaining shim, and it is shimmed in two independent ways at once:

1. **Formation is fabricated.** In composition, `06` is assembled with `FirstVersionMemoryFormationPath`, which returns no memory at all when there is no binding context, and otherwise copies the injected `binding_context.content` verbatim into one episodic item. The real `05` interoceptive feeling state reaches the item only as a passive `affect_tag`; it does not decide whether a memory forms, what gets consolidated, or with what priority. The replay selector (`FirstVersionReplayCandidateSelector`) marks every item `forced_consolidation=True` with a constant `priority_hint=0.9`, so "what is worth remembering" is a constant, not a consequence of the real affective state. The binding context itself is a shim (`FirstVersionMemoryBindingContextBridge`).

2. **Memory is not durable.** R33/R34 made the `15` execution-writeback continuity stream durable and semantically recallable, but `06` memory items live only in-process: they are recomputed from scratch every tick and lost on process exit. The system therefore has no accumulating episodic/affective memory; after a restart it can recall only `15` result summaries, never the experiences it formed.

These two shims are coupled. Persisting `06` memory while formation is still fabricated would durably store fabricated content - "real persistence of fake memories" - which closes no real gap and violates the no-pseudo-completion rule. They must be de-shimmed together.

This also keeps an avoidable weakness in R35: because the store holds only `15` result summaries, memory-grounded novelty currently compares "stimulus input vs `15` result summaries" (a cross-register approximation). Once `06` persists real affect-tagged episodic memory of experience, the substrate exists for same-register comparison in a later slice.

Per `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13, `P2` (durable memory) is the common prerequisite for `P3`/`P5`, and `06` is named as the remaining owner whose memory items must reach the durable base. This requirement is the `06` half of that work.

## 2. Goal

When affect-memory is enabled, the `06` owner forms affect-tagged memory items from the real `05` interoceptive feeling state and decides, through a `06`-owned salience gate over that real feeling signal (and optional prediction-mismatch evidence), which memories are consolidation-worthy; consolidation-worthy memories are durably persisted into the shared `33`/`34` substrate (embedded at write, tagged with a record-kind discriminator so they stay distinct from the `15` continuity stream while sharing one recall surface) and are recalled by semantic similarity through the `10` directed-retrieval owner across a process restart; the `06` owner keeps sole ownership of memory formation and the salience gate, never imports the persistence or embedding owners (those capabilities are injected), and the default and non-persistent assemblies stay byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Affect-grounded memory formation (owner-owned)
1. The `06` owner must form affect-tagged memory items through a `06`-owned formation path, not through a composition-injected constant shim. The formation path must read the real `05` `InteroceptiveFeelingState` (its `feeling` vector) and the explicit binding context and produce items whose `affect_tag` is the real feeling vector.
2. Memory formation must be deterministic given identical inputs (same feeling state, binding context, mismatch evidence, tick id).
3. The formation path must remain owned by `helios_v2.memory`. It must not import the persistence or embedding owners and must not perform durability itself.

### 3.2 Owner-owned salience gate for consolidation
1. The `06` owner must decide which formed memory items are consolidation-worthy through a `06`-owned salience gate computed from the real feeling signal (for example bounded affect intensity derived from the `05` feeling vector) and, when present, prediction-mismatch evidence. The gate must set each replay candidate's `forced_consolidation` flag and a bounded `priority_hint` from that real signal, not from a constant.
2. A low-salience tick (a feeling state that does not clear the gate, with no mismatch evidence) must produce no consolidation-worthy memory, so not every tick durably persists. A high-salience or high-mismatch tick must produce at least one consolidation-worthy memory.
3. The gate threshold and its coefficients must be explicit bounded first-version constants declared under the owner config's existing learned-parameter categories (`replay_priority_policy` / `consolidation_policy`), so a later `P5` slice can learn them without changing the gate shape.

### 3.3 Durable persistence on the shared substrate
1. When affect-memory is enabled, the runtime must durably persist exactly the consolidation-worthy memory items (those whose replay candidate carries `forced_consolidation=True`) after the tick, through an owner-neutral composition carry seam that mirrors the existing `15` experience-persistence carry. The seam must read only already-published `06` stage-result values and must compute no cognitive decision.
2. Persisted memory must reuse the existing `33` durable store and `PersistedExperienceRecord` rather than a second table, carrying an additive `record_kind` discriminator that distinguishes affect-memory records from `15` experience-writeback records. The discriminator default must preserve existing `15` records byte-for-byte.
3. Each persisted memory record must be embedded at write through the injected `34` embedding capability (the same callable and profile the store is written with), so it is comparable in the same vector space as existing records.
4. The persistence and embedding owners must stay unchanged in responsibility: the store still never embeds text itself and holds no cognitive policy; the embedding owner still holds no cognitive policy. The `06` owner reaches them only through injected capabilities, never through an import.

### 3.4 Semantic recall across restart
1. When affect-memory is enabled, persisted affect-memory records must be recalled by the `10` directed-retrieval owner through semantic similarity to the current retrieval query, alongside `15` records, on the shared recall surface. A persisted memory must remain recallable after a process restart against the same durable file.
2. A persisted affect-memory record must enter the correct thought-window tier derived from its stored memory family (episodic to mid-term, autobiographical to autobiographical), through a transport mapping that never reads content for meaning.
3. No directed-retrieval contract may change. Recall continues through the existing `MemoryRetrievalCandidate` / `ThoughtWindowBundle` surfaces; only the candidate set gains real persisted memory.

### 3.5 Opt-in rollout, fail-fast, and no v1 dedup
1. Affect-memory formation-plus-persistence must activate on the existing semantic-memory opt-in (durable store and embedding gateway both present), consistent with R34/R35. The default assembly, the recency-only persistent assembly, and any assembly without an embedding gateway must keep the current constant `06` shim behavior.
2. Requesting affect-memory without both the durable store and the embedding gateway must be a composition error, consistent with the R34 semantic-memory rule.
3. An embedding failure or a store durability failure while affect-memory is enabled must propagate as a hard stop. There is no silent fallback to a non-persistent or fabricated memory path.
4. This slice must not implement deduplication or memory merging. Growth is bounded only by the `06`-owned salience gate (only salient memories are persisted). Dedup and same-memory merge are explicitly deferred to a later slice under the `consolidation_policy` learned-parameter category.

### 3.6 Relationship to the `15` continuity stream
1. Affect-memory (`06`: what was experienced and how it felt) and the `15` continuity stream (what was done and what resulted) must remain distinct concepts with distinct provenance. They co-reside in the same durable store and share the same embedding-backed recall surface, separated by the `record_kind` discriminator.
2. Persisting affect-memory must not alter, replace, or suppress `15` continuity persistence. Both streams must persist independently in the same tick when both are present.

## 4. Non-Functional Requirements

1. Performance: formation is one deterministic owner computation per tick; persistence is at most one embedding call plus one bounded append per consolidation-worthy item, reusing the R34 bounded substrate. The runtime stage structure must not change.
2. Reliability and fault tolerance: for identical inputs and identical stored records, formation, the salience gate, and recall must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Memory facts travel only through the existing memory, persistence, and directed-retrieval contracts.
4. Compatibility and migration: all new code and the `record_kind`/metadata record fields are additive and opt-in. The default assembly, the recency-only persistent assembly, and the semantic-memory assembly's `15` behavior all stay byte-for-byte unchanged when affect-memory is off; existing tests pass unmodified.

## 5. Code Behavior Constraints

1. The `06` owner must stay free of any persistence or embedding import. The formation path and salience gate are owned by `helios_v2.memory`; durability and embedding are injected through owner-neutral composition glue.
2. The composition carry seam must be owner-neutral: it persists exactly the items `06` marked `forced_consolidation`, projecting already-published stage-result values into durable records. It must not recompute the gate, re-rank, or decide what is worth remembering.
3. The persistence owner must not gain cognitive policy. The `record_kind` discriminator and any per-record metadata are opaque stored strings; the store never interprets them for meaning. The tier mapping for recall is a transport mapping by stored kind/family only.
4. No degraded or fallback path when affect-memory is enabled: a missing store/embedding at assembly is a composition error; a runtime embedding/store failure is a hard stop; a low-salience tick persisting nothing is a defined outcome, not a failure.
5. No deduplication or merge logic may be added in this slice.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/memory/engine.py` (a `06`-owned affect-grounded formation path and salience-gated replay selector implementing the existing `MemoryFormationPath` / `ReplayCandidateSelector` protocols)
2. `helios_v2/src/helios_v2/memory/__init__.py` (export the new owner-owned formation path and replay selector)
3. `helios_v2/src/helios_v2/persistence/contracts.py` (additive `record_kind` discriminator and optional opaque `metadata` on `PersistedExperienceRecord`, default-preserving)
4. `helios_v2/src/helios_v2/persistence/engine.py` (record-kind/family-aware tier mapping for recall; SQLite column additive and back-compatible on re-open)
5. `helios_v2/src/helios_v2/composition/bridges.py` (an owner-neutral `MemoryRecordBridge` projecting consolidation-worthy memory items into durable records; binding of the affect-grounded formation path and salience-gated selector)
6. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in selection of the affect-grounded formation/gate and the memory-persistence carry seam in `RuntimeHandle.tick`; composition error without store/embedding)
7. `helios_v2/tests/test_memory_engine.py` (extend: affect-grounded formation; salience gate forms/does not form; deterministic)
8. `helios_v2/tests/test_persistence_contracts.py` / `test_persistence_engine.py` (extend: `record_kind`/metadata round-trip across SQLite re-open; tier mapping by family)
9. `helios_v2/tests/test_runtime_composition.py` (extend: opt-in affect-memory persists salient memory and recalls it through `10`; restart recall; low-salience tick persists nothing; composition error without store/embedding; default unchanged; `15` co-persists)
10. `helios_v2/docs/requirements/index.md`
11. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
12. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
13. `helios_v2/docs/OWNER_GUIDE.md`
14. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
15. `helios_v2/docs/PROGRESS_FLOW.en.md`
16. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The `06` owner forms affect-tagged memory from the real `05` feeling state through a `06`-owned formation path, without importing the persistence or embedding owners; formation is deterministic for identical inputs.
2. The `06`-owned salience gate sets `forced_consolidation` and `priority_hint` from the real feeling signal (and mismatch evidence): a low-salience tick with no mismatch produces no consolidation-worthy memory; a high-salience or high-mismatch tick produces at least one. The threshold/coefficients are explicit constants under the declared learned-parameter categories.
3. When affect-memory is enabled, consolidation-worthy memory items are durably persisted into the shared `33` store with `record_kind="affect_memory"`, embedded at write; the carry seam persists exactly the `forced_consolidation` items and computes no decision.
4. A persisted affect-memory record is recalled by semantic similarity through the `10` owner alongside `15` records, enters the tier derived from its stored family, and remains recallable after a process restart against the same durable file; no directed-retrieval contract changes.
5. The additive `record_kind` (default preserving `15` behavior) and optional metadata round-trip exactly across a SQLite close and re-open; existing `15` records read back byte-for-byte.
6. Enabling affect-memory without both the store and the embedding gateway raises a composition error; a runtime embedding/store failure is a hard stop with no non-persistent or fabricated fallback.
7. The default assembly and the recency-only persistent assembly keep the current constant `06` behavior; their existing tests pass unmodified. `15` continuity persistence is unchanged and co-persists with affect-memory in the same tick.
8. No deduplication or merge logic is added in this slice.
9. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R45 de-shims `06` formation and makes affect-memory durable and semantically recallable. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Deduplication and same-memory merge/consolidation under the `consolidation_policy` learned-parameter category (bounded, owner-owned), retiring the no-dedup constraint of this slice.
2. Same-register memory-grounded novelty (R35 method B): once raw experience is persisted, `03` novelty can compare stimulus against stimulus-derived memory in one register, retiring the R35 cross-register caveat. Separate `03`/persistence slice.
3. Real `07` workspace competition over genuine `06` candidates (the next mid-chain de-shim once `06` is real).
4. Feeding the real `05` feeling into formation beyond the affect tag (mismatch-driven and feeling-driven content shaping), and `P5` learning of the salience-gate parameters from real outcome valence.
5. Durable `14` identity state once it carries cross-tick state (the remaining P2 checkpoint item), tracked separately from this requirement.

None of these may be smuggled into this slice. R45 changes only `06` formation/gate, the additive durable-record discriminator, and the opt-in memory-persistence carry; it introduces no cognitive ownership into the persistence/embedding owners, no dedup/merge, and no default-on behavior.
