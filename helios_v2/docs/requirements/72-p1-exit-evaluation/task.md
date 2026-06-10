# Requirement 72 - P1 Exit Evaluation — Task

## 1. Task Breakdown

### Task A: Evaluation skeleton and wave tests

**Scope**: New module with helpers, verdict dataclasses, and wave_A/B/C tests.
**Dependency**: None.
**Touched modules**: `helios_v2/tests/test_p1_exit_evaluation.py`

**Completion definition**:
- `P1Indicator` / `P1ExitVerdict` defined.
- `test_p1_t2_wave_a_corroboration` passes.
- `test_p1_t3_wave_b_continuity_thread_persistence` passes.
- `test_p1_t4_wave_c_cli_channel_roundtrip` passes.

**Validation step**: `pytest helios_v2/tests/test_p1_exit_evaluation.py -v -k "wave"`

### Task B: Closure and hard-condition tests

**Scope**: Internal-only, no-fire, causal chain, and 10-tick tests.
**Dependency**: Task A.
**Touched modules**: `helios_v2/tests/test_p1_exit_evaluation.py`

**Completion definition**:
- `test_p1_t5_internal_only_tick_closure` passes.
- `test_p1_t6_no_fire_tick_closure` passes.
- `test_p1_h1_read_only_causal_chain_reconstruction` passes.
- `test_p1_h2_continuous_ten_ticks` passes.

**Validation step**: `pytest helios_v2/tests/test_p1_exit_evaluation.py -v -k "closure or causal or ten"`

### Task C: Composite verdict and docs

**Scope**: Aggregate verdict + index.md update.
**Dependency**: Task B.
**Touched modules**: `helios_v2/tests/test_p1_exit_evaluation.py`, `helios_v2/docs/requirements/index.md`

**Completion definition**: `test_p1_exit_verdict` passes; index.md has R72 row.

**Validation step**: `pytest helios_v2/tests/test_p1_exit_evaluation.py -v`

## 2. Dependencies

```
Task A (wave tests) → Task B (closure + hard conditions) → Task C (composite + docs)
```

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/tests/test_p1_exit_evaluation.py` | Add | 8 evaluation tests |
| `helios_v2/docs/requirements/index.md` | Add row | R72 entry |

## 4. Implementation Order

1. Task A: Skeleton + wave_A/B/C.
2. Task B: Closure + hard conditions.
3. Task C: Composite + docs.

## 5. Validation Plan

| Task | Validation command |
|------|-------------------|
| A | `pytest helios_v2/tests/test_p1_exit_evaluation.py -v -k "wave"` |
| B | `pytest helios_v2/tests/test_p1_exit_evaluation.py -v -k "closure or causal or ten"` |
| C | `pytest helios_v2/tests/test_p1_exit_evaluation.py -v` |

Final: `pytest helios_v2/tests/ -x`

## 6. Completion Criteria

1. All 8 P1 evaluation tests pass offline.
2. Composite verdict covers all P1-T* and P1-H* indicators.
3. `index.md` updated with R72 row.
