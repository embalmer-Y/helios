# Requirement 73 - P2 Exit Evaluation

## 1. Background and Problem

`PHASE_METRICS.md` §4 defines the P2 persistent memory and knowledge foundation milestone
with six test indicators (P2-T1 through P2-T6) and four hard exit conditions (P2-H1 through
P2-H4). These validate durable experience store persistence, cross-restart continuity,
semantic retrieval by cosine ranking, checkpoint save/restore, dual-timescale dynamics,
subjective continuity across restarts, retrieval driven by real representation, and
embedding failure hard-stop semantics.

No automated assessment validates the full P2 exit signal. Individual tests exist in
R33/R34/R42/R43/R44 but no single evaluation aggregates them.

## 2. Goal

Provide a read-only evaluation module that validates all P2 exit indicators and hard
conditions, producing a structured `P2ExitVerdict` that makes the P2 phase exit decision
explicit and reproducible.

## 3. Functional Requirements

### 3.1 Store persistence

1. A test must verify that the experience store persists ≥ 100 records after 100 ticks
   (P2-T2).

### 3.2 Cross-restart continuity

1. A test must verify that session B reads records written by session A, with count
   matching (P2-T3).

### 3.3 Semantic recall

1. A test must verify that `search_similar` returns records ordered by cosine similarity
   against a query embedding (P2-T4).

### 3.4 Checkpoint save/restore

1. A test must verify that `ContinuityCheckpointStore` v3 snapshot survives save →
   new handle → restore with state preserved (P2-T5).

### 3.5 Dual-timescale dynamics

1. A test must verify that `04`/`05` states evolve across ticks away from cold-start
   baseline (P2-T6).

### 3.6 Hard exit conditions

1. Subjective continuity: session A write + session B read end-to-end (P2-H1).
2. Retrieval driven by real representation, not recency-only (P2-H2).
3. Embedding failure = hard stop, no silent degradation (P2-H3).
4. `06`/`04`/`05`/`14` persistence paths defined (P2-H4).

### 3.7 Composite verdict

1. Aggregate all P2 indicators into a `P2ExitVerdict`.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: no owner code modification.
3. **Durable**: SQLite-backed tests use `tmp_path` for isolation.

## 5. Code Behavior Constraints

1. Tests must use `ExperienceStore` and `ContinuityCheckpointStore` APIs only.
2. Embedding failure test must inject a raising provider, not mock internal state.

## 6. Impacted Modules

1. `helios_v2/tests/test_p2_exit_evaluation.py` — new evaluation module.
2. `helios_v2/docs/requirements/index.md` — new R73 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_p2_exit_evaluation.py -v` passes all 10 tests offline.
2. Composite verdict covers all P2-T* and P2-H* indicators.
3. Full suite still passes.
