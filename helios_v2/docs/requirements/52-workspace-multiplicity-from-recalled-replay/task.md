# Requirement 52 - Workspace multiplicity from recalled affect-memory replay (tasks)

## 1. Task Breakdown

### Task 1 - Recalled-memory contract + provider protocol
In `helios_v2/src/helios_v2/memory/contracts.py`, add `RecalledMemoryFact` (frozen: `memory_id`, `family: MemoryFamily`, `summary`, `recall_similarity` in `[0,1]`, `affect: InteroceptiveFeelingVector`; validated, raises `MemoryAffectReplayError`) and the `RecalledMemoryProvider` protocol (`recall(binding_context, feeling_state) -> tuple[RecalledMemoryFact, ...]`). Export both from `memory/__init__.py`.

### Task 2 - Owner-owned recalled-replay surfacing
In `helios_v2/src/helios_v2/memory/engine.py`, add an optional `recalled_memory_provider: RecalledMemoryProvider | None = None` field to `MemoryAffectReplayEngine`. After the current-tick formation + selection in `record_state`, when the provider is present and a binding context exists, call `recall(...)` and append owner-re-formed recalled items + non-`forced_consolidation` candidates (`_surface_recalled`), with the priority from an owner-owned mapping over recall similarity + recalled affect intensity (`_recalled_priority`, weights as first-version constants) and reasons from the fixed taxonomy (`_recalled_reasons`). Skip a recalled fact whose `memory_id` collides with the current item. The combined set must pass all existing validators. When the provider is `None` / facts empty / no binding context, behavior is byte-for-byte the pre-R52 single-candidate state.

### Task 3 - Persist the affect vector (extend R45 carry)
In `helios_v2/src/helios_v2/composition/bridges.py`, extend `MemoryRecordBridge.build_records` to add `"affect_vector"` (a `,`-joined string of the 7 rounded `affect_tag` components) to the affect-memory record `metadata`. Add `_encode_affect_vector`/`_decode_affect_vector` helpers (decode returns `None` on absent/malformed).

### Task 4 - Store-backed recalled provider + wiring
In `bridges.py`, add `StoreBackedRecalledMemoryProvider` (embeds the binding-context content via the injected `embed_text`, runs the store `search_similar`, keeps only `affect_memory`-kind hits carrying a decodable affect vector, returns bounded `RecalledMemoryFact`s; cold/empty -> `()`; embedding/store failure propagates). In `runtime_assembly.py`, construct it under the semantic-memory assembly with the existing record-embedding callable and inject it into the `06` `MemoryAffectReplayEngine`; `None` otherwise.

### Task 5 - Validation
Extend `test_memory_engine.py` (owner-level: recalled surfacing additive + non-forced + invariants hold; priority monotonic/bounded/deterministic; collision skip; empty/no-provider unchanged) and `test_runtime_composition.py` (end-to-end: prior affect-memory persisted -> later tick `07` has >1 candidate, `08` ignites one focal winner with others demoted, `09` activation = max retained score; strong recalled memory wins; affect-vector round trip; default unchanged). Keep the suite network-free (fake provider / fake embedding gateway + in-memory store) and the logging guard green.

### Task 6 - Documentation truth sync
Update `index.md` (R52 row), `ARCHITECTURE_BOUNDARIES.md` (migration-state item: workspace multiplicity from recalled replay; `06` recalled-replay surfacing), `BRAIN_ARCHITECTURE_COMPARISON.md` (narrow the `08` and `09-11` multiplicity caveats and the `gap_persistence_and_learning` recall-into-workspace note), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`06`/`07`/`08` completeness + next-step), and both `PROGRESS_FLOW` maps (note multiplicity now active; update last-synced + baseline count).

## 2. Dependencies

1. Task 1 is independent.
2. Task 2 depends on Task 1.
3. Task 3 is independent (touches only the persist carry) but is required before Task 4's provider can reconstruct affect.
4. Task 4 depends on Tasks 1 and 3.
5. Task 5 depends on Tasks 1-4.
6. Task 6 depends on Task 5 being green.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/memory/contracts.py`, `memory/__init__.py` (Task 1)
2. `helios_v2/src/helios_v2/memory/engine.py` (Task 2)
3. `helios_v2/src/helios_v2/composition/bridges.py` (Tasks 3, 4)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 4)
5. `helios_v2/tests/test_memory_engine.py`, `helios_v2/tests/test_runtime_composition.py` (Task 5)
6. `helios_v2/docs/requirements/index.md` and the four truth docs + two progress maps (Task 6)

## 4. Implementation Order

1. Task 1 (contract + protocol).
2. Task 2 (owner surfacing) - independently testable with a fake provider.
3. Task 3 (persist affect vector) - prerequisite for faithful recall.
4. Task 4 (store-backed provider + wiring) - makes recall live.
5. Task 5 (validation) - owner-level then end-to-end multiplicity.
6. Task 6 (doc sync).

## 5. Validation Plan

1. After Task 2: `pytest helios_v2/tests/test_memory_engine.py -q` (recalled surfacing additive/non-forced/bounded/deterministic; invariants hold; empty unchanged).
2. After Task 4: `pytest helios_v2/tests/test_runtime_composition.py -q` (multiplicity active end to end; affect-vector round trip; default unchanged).
3. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. The `06` owner surfaces recalled prior affect-memories as additive, non-`forced_consolidation` replay candidates with an owner-computed priority from recall relevance + recalled affect; all existing `06` invariants hold; the current-tick memory is unchanged.
2. The recalled-memory source is injected behind a protocol; `06` imports no persistence/embedding owner; the composition provider reconstructs affect from durably persisted affect-memory metadata (affect vector now persisted, additively).
3. End-to-end: after a prior affect-memory is persisted, a later tick's `07` competes over >1 candidate, `08` ignites a single focal winner (rest demoted), `09` activation = max retained score; a strong recalled memory can win.
4. Cold store / empty context / no similar memory -> zero recalled candidates (unchanged); embedding/store failure is a hard stop; default/recency/non-semantic/offline assemblies byte-for-byte unchanged; existing store files read back.
5. Deterministic and bounded; full suite green and network-free; logging guard green.
6. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps updated in the same change set (multiplicity now active; R46/R47/R48 exercised end to end).
