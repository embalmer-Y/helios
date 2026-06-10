# Requirement 73 - P2 Exit Evaluation — Task

## 1. Task Breakdown

### Task A: Evaluation skeleton and persistence tests

**Scope**: New module + P2-T2/T3/T4/T5 tests.
**Dependency**: None.
**Touched modules**: `helios_v2/tests/test_p2_exit_evaluation.py`

**Completion definition**: P2-T2 through P2-T5 pass.

**Validation step**: `pytest helios_v2/tests/test_p2_exit_evaluation.py -v -k "t2 or t3 or t4 or t5"`

### Task B: Dual-timescale and hard-condition tests

**Scope**: P2-T6, P2-H1 through P2-H4.
**Dependency**: Task A.
**Touched modules**: `helios_v2/tests/test_p2_exit_evaluation.py`

**Completion definition**: All P2-T6 and P2-H* tests pass.

**Validation step**: `pytest helios_v2/tests/test_p2_exit_evaluation.py -v -k "t6 or h1 or h2 or h3 or h4"`

### Task C: Composite verdict and docs

**Scope**: Aggregate verdict + index.md.
**Dependency**: Task B.
**Touched modules**: `helios_v2/tests/test_p2_exit_evaluation.py`, `helios_v2/docs/requirements/index.md`

**Completion definition**: `test_p2_exit_verdict` passes; index.md has R73 row.

**Validation step**: `pytest helios_v2/tests/test_p2_exit_evaluation.py -v`

## 2. Dependencies

```
Task A (persistence) → Task B (timescale + hard conditions) → Task C (composite + docs)
```

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/tests/test_p2_exit_evaluation.py` | Add | 10 evaluation tests |
| `helios_v2/docs/requirements/index.md` | Add row | R73 entry |

## 4. Implementation Order

1. Task A: Persistence tests (T2-T5).
2. Task B: Dual-timescale + hard conditions (T6, H1-H4).
3. Task C: Composite + docs.

## 5. Validation Plan

| Task | Validation command |
|------|-------------------|
| A | `pytest helios_v2/tests/test_p2_exit_evaluation.py -v -k "t2 or t3 or t4 or t5"` |
| B | `pytest helios_v2/tests/test_p2_exit_evaluation.py -v -k "t6 or h"` |
| C | `pytest helios_v2/tests/test_p2_exit_evaluation.py -v` |

Final: `pytest helios_v2/tests/ -x`

## 6. Completion Criteria

1. All 10 P2 evaluation tests pass offline.
2. Composite verdict covers all P2-T* and P2-H* indicators.
3. `index.md` updated with R73 row.
