# Requirement 45 - Affect-grounded memory formation and durable memory store (tasks)

## 1. Task Breakdown

### Task 1 - Owner-owned affect-grounded formation and salience gate (`06`)
Add `AffectGroundedMemoryFormationPath` and `SalienceGatedReplayCandidateSelector` to `helios_v2.memory`, implementing the existing `MemoryFormationPath` / `ReplayCandidateSelector` protocols. Formation reads the real `05` feeling vector into `affect_tag` and applies the owner-owned family mapping. The selector computes a bounded affect-intensity salience from the real feeling vector and optional mismatch evidence and sets `forced_consolidation` + `priority_hint` from it. Export both from `memory/__init__.py`. No persistence/embedding import.

### Task 2 - Additive durable-record discriminator (`33`/`34` substrate)
Add `record_kind: str = "experience_writeback"` and `metadata: Mapping[str, str] = {}` (frozen, validated like `linkage`) to `PersistedExperienceRecord`, threaded through `with_sequence`/`with_embedding`. Persist/read both columns in the SQLite backend with a guarded additive `ALTER TABLE` (PRAGMA table_info check) so existing files upgrade in place; `_row_to_record` maps missing/NULL `record_kind` to the default and missing `metadata` to empty. Make `_record_tier` family-aware (transport mapping only).

### Task 3 - Owner-neutral memory carry seam (composition)
Add `MemoryRecordBridge` to `composition/bridges.py` projecting exactly the `forced_consolidation` memory items from the published `06` stage result into `record_kind="affect_memory"` durable records (re-deriving no decision). Add `memory_record_bridge` to `RuntimeHandle` and a `_persist_memory(result)` carry seam in `tick` mirroring `_persist_experience` (embed-at-write via the existing `_embed_text`; hard stop on failure). `15` persistence untouched.

### Task 4 - Opt-in assembly wiring
In `assemble_runtime`, under the existing semantic-memory opt-in (store + embedding both present), assemble `06` with the owner-owned formation path + salience-gated selector and wire the memory carry seam. Keep `FirstVersion*` and no memory seam for default/recency-only. Raise `CompositionError` when affect-memory wiring is requested without both store and embedding.

### Task 5 - Validation
Extend the memory, persistence, and composition test modules per the design validation strategy. Keep the suite network-free and the logging guard green.

### Task 6 - Documentation truth sync
Update `index.md` (add R45 row; reassess `06` maturity), `ARCHITECTURE_BOUNDARIES.md` (persistence owner record-kind/affect-memory note; `06` owner), `BRAIN_ARCHITECTURE_COMPARISON.md` (narrow `gap_persistence_and_learning`: `06` now durable; note `06` formation de-shimmed), `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md` (`06` and `33` next-step/state; fix the stale R42/560 header to R45/new baseline), and both `PROGRESS_FLOW` maps (recolor `06`; update last-synced line and baseline count).

## 2. Dependencies

1. Task 1 is independent (owner-internal).
2. Task 2 is independent (substrate-internal).
3. Task 3 depends on Task 1 (reads the `forced_consolidation` flag the selector sets) and Task 2 (builds records with `record_kind`).
4. Task 4 depends on Tasks 1-3.
5. Task 5 depends on Tasks 1-4.
6. Task 6 depends on Task 5 being green (maturity reflects shipped+validated code).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/memory/engine.py`, `memory/__init__.py` (Task 1)
2. `helios_v2/src/helios_v2/persistence/contracts.py`, `persistence/engine.py` (Task 2)
3. `helios_v2/src/helios_v2/composition/bridges.py`, `composition/runtime_assembly.py` (Tasks 3, 4)
4. `helios_v2/tests/test_memory_engine.py`, `test_persistence_contracts.py`, `test_persistence_engine.py`, `test_runtime_composition.py` (Task 5)
5. `helios_v2/docs/requirements/index.md` and the five truth docs + two progress maps (Task 6)

## 4. Implementation Order

1. Task 1 (owner formation + gate) - the cognitive truth, independently testable.
2. Task 2 (durable discriminator) - the substrate, independently testable.
3. Task 3 (carry seam) - joins owner output to durability.
4. Task 4 (opt-in wiring) - activates the path end to end.
5. Task 5 (validation) - prove behavior, restart recall, no-persist-on-flat-tick, default unchanged.
6. Task 6 (doc sync) - align index, boundary, grounding, owner guide, progress maps.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_memory_engine.py -q` (formation from real feeling; gate forms/does-not-form; deterministic).
2. After Task 2: `pytest helios_v2/tests/test_persistence_contracts.py helios_v2/tests/test_persistence_engine.py -q` (record_kind/metadata round-trip + SQLite re-open back-compat; family tier mapping).
3. After Task 4: `pytest helios_v2/tests/test_runtime_composition.py -q` (persist+recall; restart recall; flat tick persists nothing while `15` co-persists; composition error; default unchanged; embedding-failure hard stop).
4. Final: `pytest helios_v2/tests -q` full suite green and network-free; `test_no_adhoc_logging_guard.py` green.

## 6. Completion Criteria

1. `06` forms affect-tagged memory from the real `05` feeling state through a `06`-owned path, with a `06`-owned salience gate setting `forced_consolidation`/`priority_hint` from the real signal; no persistence/embedding import.
2. Consolidation-worthy memory is durably persisted into the shared `33` store as `record_kind="affect_memory"`, embedded at write, via an owner-neutral carry seam that persists exactly the `forced_consolidation` items.
3. Persisted affect-memory is recalled semantically through `10` alongside `15`, enters the family-derived tier, and survives a process restart; no directed-retrieval contract change.
4. `record_kind`/`metadata` are additive and default-preserving; existing R33/R34 stores read back byte-for-byte and upgrade in place.
5. A low-salience tick persists no affect-memory while `15` still co-persists; enabling without store+embedding is a composition error; runtime embedding/store failure is a hard stop.
6. No dedup/merge added; default and recency-only assemblies unchanged; full suite green and network-free; logging guard green.
7. `index.md`, the boundary/grounding/owner-guide docs, and both progress maps are updated in the same change set; the stale owner-guide header is corrected.
