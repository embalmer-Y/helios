# Requirement 76 - Memory Stability Assessment — Design

## 1. Design Overview

A read-only assessment module with 7 tests covering six memory stability dimensions.
Tests use both `SqliteExperienceStoreBackend` (durability, cross-restart) and
`InMemoryExperienceStoreBackend` (recall consistency, record coexistence). A composite
verdict aggregates all.

## 2. Current State and Gap

Individual persistence tests exist (R33 store, R34 retrieval, R42 checkpoint, R45 affect
memory). No module assesses memory stability holistically under sustained load with
consistency guarantees.

## 3. Target Architecture

```
test_memory_stability_assessment.py
├── MemoryCheck / MemoryVerdict dataclasses
├── test_ms1_sqlite_write_durability          — 50 ticks ≥ 50 records
├── test_ms2_semantic_recall_consistency      — same query → same ranking
├── test_ms3_cross_restart_record_integrity   — session A → B count match
├── test_ms4_checkpoint_v3_round_trip         — v3 save/restore
├── test_ms5_consolidation_gating             — affect-intensity threshold
├── test_ms6_record_kind_coexistence          — writeback + affect in same store
└── test_memory_stability_composite_verdict   — aggregate
```

## 4. Data Structures

### 4.1 MemoryCheck / MemoryVerdict

Same pattern as R72–R75 verdict dataclasses.

## 5. Module Changes

### 5.1 `tests/test_memory_stability_assessment.py`

New module. Helpers: `_semantic_assembly()`, `_ready_gateway()`, `_embedding_gateway()`,
`_record(i, kind, embedding)` factory.

## 6. Migration Plan

No migration. Pure additive.

## 7. Failure Modes and Constraints

1. **Zero-norm embeddings**: `cosine_similarity` raises on zero-norm vectors; test
   embeddings use `float(i % 5 + 1) * 0.1` to avoid zero vectors.
2. **Cross-restart count**: session B count is checked immediately after opening
   (before any tick), to avoid counting B's own writes.
3. **Consolidation gating**: uses `SalienceGatedReplayCandidateSelector` directly
   with constructed `ConsolidationCandidate` instances.

## 8. Observability and Logging

No new logging. Verdict via `pytest -s`.

## 9. Validation Strategy

1. Each test validates one memory stability dimension.
2. Composite aggregates all.
3. All offline with fake providers and SQLite temp files.
