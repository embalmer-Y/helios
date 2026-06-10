# Requirement 75 - Feedback Path Verification — Design

## 1. Design Overview

A read-only verification module with 6 tests covering the five critical feedback paths
in the 19-stage cognitive chain. Each test runs the assembled runtime for multiple
ticks and validates one feedback loop. A composite verdict aggregates all.

## 2. Current State and Gap

Individual feedback mechanisms are validated by their originating requirements (R54
no-fire closure, R62 drive urgency carry, R67 stable thread key, R68 identity carry).
No module validates the end-to-end feedback paths that span multiple requirements.

## 3. Target Architecture

```
test_feedback_path_verification.py
├── FeedbackCheck / FeedbackVerdict dataclasses
├── test_fp1_fire_path_autonomy_carry        — 3 ticks, gate fires, 18 carry
├── test_fp2_no_fire_closure_continuation    — high load, 18/17 still run
├── test_fp3_writeback_to_retrieval_loop     — 5 ticks, store count ≥ 5
├── test_fp4_neuromodulator_feeling_chain    — 04→05→07→09 evolve
├── test_fp5_continuity_checkpoint_round_trip — v3 save/restore
└── test_feedback_path_composite_verdict     — aggregate
```

## 4. Data Structures

### 4.1 FeedbackCheck / FeedbackVerdict

Same pattern as R72/R73 verdict dataclasses.

## 5. Module Changes

### 5.1 `tests/test_feedback_path_verification.py`

New module. Helpers: `_semantic_assembly()`, `_ready_gateway()`, `_embedding_gateway()`,
`_HighPressureSampler` (for FP-2 high-load scenario).

## 6. Migration Plan

No migration. Pure additive.

## 7. Failure Modes and Constraints

1. **Gate fire detection**: FP-1 checks `thought_gating_stage` result; if the gate
   never fires under default assembly, the test validates carry via other signals.
2. **High-load simulation**: `_HighPressureSampler` produces `RuntimePressureSample`
   with elevated `cpu_pressure`/`memory_pressure`, which biases the gate toward no-fire.
3. **Writeback timing**: records may not appear in the store until the next tick's
   `initialize()` call; tests account for this by checking after N ticks.

## 8. Observability and Logging

No new logging. Verdict via `pytest -s`.

## 9. Validation Strategy

1. Each test validates one feedback path end-to-end.
2. Composite aggregates all.
3. All offline with fake providers.
