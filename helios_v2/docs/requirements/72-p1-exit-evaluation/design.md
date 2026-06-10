# Requirement 72 - P1 Exit Evaluation — Design

## 1. Design Overview

A read-only evaluation module with 8 tests mapping 1:1 to P1 exit indicators defined in
`PHASE_METRICS.md` §3. Each test runs the assembled runtime for N ticks and checks one
specific indicator. A composite verdict test aggregates all into a structured report.

## 2. Current State and Gap

Individual tests for wave_A/B/C, internal-only, and no-fire closure exist in separate
modules (R28, R29, R31, R32, R54, R67). No single module aggregates them into a P1
exit assessment. Phase exit decisions require manual cross-referencing.

## 3. Target Architecture

```
test_p1_exit_evaluation.py
├── P1Indicator / P1ExitVerdict dataclasses
├── test_p1_t2_wave_a_corroboration          — 17 verdict kinds
├── test_p1_t3_wave_b_continuity_thread      — 18/24 persistence ≥ 5 ticks
├── test_p1_t4_wave_c_cli_channel_roundtrip  — CLI ≥ 3 ticks
├── test_p1_t5_internal_only_tick_closure    — no external stimulus
├── test_p1_t6_no_fire_tick_closure          — R54 path
├── test_p1_h1_read_only_causal_chain        — 17/23 reconstruction
├── test_p1_h2_continuous_ten_ticks          — 10 ticks no exception
└── test_p1_exit_verdict                     — composite aggregation
```

## 4. Data Structures

### 4.1 P1Indicator / P1ExitVerdict

```python
@dataclass
class P1Indicator:
    indicator_id: str     # "P1-T2", "P1-H1", etc.
    name: str
    passed: bool
    detail: str

@dataclass
class P1ExitVerdict:
    indicators: list[P1Indicator]
    def add(self, indicator): ...
    @property
    def overall_pass(self) -> bool: ...
```

## 5. Module Changes

### 5.1 `tests/test_p1_exit_evaluation.py`

New module. Helpers reuse patterns from `test_p3_exit_evaluation.py`:
- `_semantic_assembly()` / `_ready_gateway()` / `_embedding_gateway()`
- `_run_ticks(handle, n)` — run ticks and return results

## 6. Migration Plan

No migration. Pure additive evaluation module.

## 7. Failure Modes and Constraints

1. **No LLM available**: tests use `_FakeThoughtProvider` for offline operation.
2. **Wave-B thread detection**: requires ≥ 5 ticks to observe reinforcement;
   fewer ticks would produce false negatives.
3. **CLI channel**: uses in-memory channel driver, not real I/O.

## 8. Observability and Logging

No new logging. Verdict printed via `pytest -s` output.

## 9. Validation Strategy

1. Each test validates one P1 indicator.
2. Composite test aggregates all into one pass/fail.
3. All tests run offline with fake providers.
