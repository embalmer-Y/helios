# Requirement 73 - P2 Exit Evaluation — Design

## 1. Design Overview

A read-only evaluation module with 10 tests covering all P2 exit indicators from
`PHASE_METRICS.md` §4. Tests use `SqliteExperienceStoreBackend` for durability tests
and `InMemoryExperienceStoreBackend` for recall tests. A composite verdict aggregates
all results.

## 2. Current State and Gap

Individual P2 tests exist: `test_persistence_store.py` (R33), `test_semantic_retrieval.py`
(R34), `test_continuity_checkpoint.py` (R42), `test_dual_timescale_dynamics.py` (R43/R44).
No single evaluation aggregates them for P2 exit.

## 3. Target Architecture

```
test_p2_exit_evaluation.py
├── P2Indicator / P2ExitVerdict dataclasses
├── test_p2_t2_store_persists_experience       — 100 ticks ≥ 100 records
├── test_p2_t3_cross_restart_continuity        — session A → B count match
├── test_p2_t4_semantic_recall_cosine          — cosine ranking
├── test_p2_t5_checkpoint_save_restore         — v3 round-trip
├── test_p2_t6_dual_timescale_evolution        — 04/05 ≠ baseline
├── test_p2_h1_subjective_continuity           — A write + B read end-to-end
├── test_p2_h2_retrieval_driven_by_real        — semantic not recency-only
├── test_p2_h3_embedding_failure_hard_stop     — raising provider
├── test_p2_h4_persistence_paths_defined       — paths exist
└── test_p2_exit_verdict                       — composite
```

## 4. Data Structures

### 4.1 P2Indicator / P2ExitVerdict

Same pattern as R72 `P1ExitVerdict`: list of `P2Indicator(indicator_id, name, passed, detail)`
with `add()` and `overall_pass`.

## 5. Module Changes

### 5.1 `tests/test_p2_exit_evaluation.py`

New module. Helpers: `_semantic_assembly()`, `_ready_gateway()`, `_embedding_gateway()`,
`_embedding_gateway_raising()` (for H3).

## 6. Migration Plan

No migration. Pure additive.

## 7. Failure Modes and Constraints

1. **SQLite temp files**: tests use `tmp_path` for isolation; no cleanup needed.
2. **Embedding failure test**: inject a `_RaisingEmbeddingProvider` that raises on `.embed()`.
3. **Cross-restart test**: capture store count before `handle_b.tick()` to avoid
   counting session B's own writes.

## 8. Observability and Logging

No new logging. Verdict via `pytest -s` output.

## 9. Validation Strategy

1. Each test validates one P2 indicator.
2. Composite aggregates all.
3. All offline with fake providers.
