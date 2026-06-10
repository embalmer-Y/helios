# Requirement 76 - Memory Stability Assessment

## 1. Background and Problem

The Helios v2 persistence layer (`33` durable experience store, `34` semantic retrieval,
`42` continuity checkpoint, `45` affect memory) provides the memory foundation for P2.
R33/R34 established SQLite-backed writes and cosine-based semantic recall. R45 added
affect-memory formation alongside experience-writeback records.

However, no single assessment validates memory system stability under sustained load:
write durability over 50+ ticks, semantic recall consistency (same query → same ranking),
cross-restart record integrity, checkpoint v3 round-trip fidelity, consolidation gating
correctness, and multi-record-kind coexistence.

## 2. Goal

Provide a read-only assessment module that validates memory system stability across six
dimensions, producing a structured `MemoryVerdict` for P2 exit governance.

## 3. Functional Requirements

### 3.1 MS-1: SQLite write durability

1. A test must verify that 50 ticks produce ≥ 50 records in a SQLite-backed store.

### 3.2 MS-2: Semantic recall consistency

1. A test must verify that two identical `search_similar` queries against a pre-populated
   in-memory store return the same ranking (deterministic cosine).

### 3.3 MS-3: Cross-restart record integrity

1. A test must verify that session A writes → session B reads with matching count
   and content.

### 3.4 MS-4: Checkpoint v3 round-trip

1. A test must verify that v3 checkpoint save → restore preserves thought gating
   continuation state and autonomy carry state.

### 3.5 MS-5: Consolidation gating

1. A test must verify that `SalienceGatedReplayCandidateSelector` gates consolidation
   based on affect-intensity: low-intensity records are not consolidated, high-intensity
   records are.

### 3.6 MS-6: Record kind coexistence

1. A test must verify that `experience_writeback` and `affect_memory` record kinds
   coexist in the same store without interference.

### 3.7 Composite verdict

1. Aggregate all checks into a `MemoryVerdict`.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: no persistence engine modification.
3. **Deterministic**: recall consistency tests use fixed embeddings.

## 5. Code Behavior Constraints

1. Tests must use `ExperienceStore.append_records()`, `read_recent()`, `count()`,
   `search_similar()` APIs.
2. `PersistedExperienceRecord` instances must include all required fields
   (`requested_effect_summary`, `applied_effect_summary`, `reason_trace`, `linkage`).
3. Embedding vectors must be non-zero to avoid `cosine_similarity` undefined behavior.

## 6. Impacted Modules

1. `helios_v2/tests/test_memory_stability_assessment.py` — new assessment module.
2. `helios_v2/docs/requirements/index.md` — new R76 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_memory_stability_assessment.py -v` passes all 7 tests.
2. Composite verdict covers MS-1 through MS-6.
3. Full suite still passes.
