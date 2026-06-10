# Requirement 76 - Memory Stability Assessment — Task

## 1. Task Breakdown

### Task A: Durability and recall tests

**Scope**: MS-1 and MS-2 tests.
**Dependency**: None.
**Touched modules**: `helios_v2/tests/test_memory_stability_assessment.py`

**Completion definition**: MS-1 (50 ticks) and MS-2 (recall consistency) pass.

**Validation step**: `pytest ... -v -k "ms1 or ms2"`

### Task B: Cross-restart and checkpoint tests

**Scope**: MS-3 and MS-4 tests.
**Dependency**: Task A.
**Touched modules**: `helios_v2/tests/test_memory_stability_assessment.py`

**Completion definition**: MS-3 (cross-restart) and MS-4 (checkpoint v3) pass.

**Validation step**: `pytest ... -v -k "ms3 or ms4"`

### Task C: Consolidation gating and record coexistence

**Scope**: MS-5 and MS-6 tests.
**Dependency**: Task B.
**Touched modules**: `helios_v2/tests/test_memory_stability_assessment.py`

**Completion definition**: MS-5 (consolidation) and MS-6 (coexistence) pass.

**Validation step**: `pytest ... -v -k "ms5 or ms6"`

### Task D: Composite verdict and docs

**Scope**: Composite + index.md.
**Dependency**: Task C.
**Touched modules**: `helios_v2/tests/test_memory_stability_assessment.py`, `helios_v2/docs/requirements/index.md`

**Completion definition**: All 7 tests pass; index.md has R76 row.

**Validation step**: `pytest ... -v`

## 2. Dependencies

```
Task A (durability + recall) → Task B (cross-restart + checkpoint)
    → Task C (consolidation + coexistence) → Task D (composite + docs)
```

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/tests/test_memory_stability_assessment.py` | Add | 7 assessment tests |
| `helios_v2/docs/requirements/index.md` | Add row | R76 entry |

## 4. Implementation Order

1. Task A: MS-1 durability + MS-2 recall.
2. Task B: MS-3 cross-restart + MS-4 checkpoint.
3. Task C: MS-5 consolidation + MS-6 coexistence.
4. Task D: Composite + docs.

## 5. Validation Plan

| Task | Validation command |
|------|-------------------|
| A | `pytest ... -v -k "ms1 or ms2"` |
| B | `pytest ... -v -k "ms3 or ms4"` |
| C | `pytest ... -v -k "ms5 or ms6"` |
| D | `pytest ... -v` |

Final: `pytest helios_v2/tests/ -x`

## 6. Completion Criteria

1. All 7 memory stability tests pass offline.
2. Composite verdict covers MS-1 through MS-6.
3. `index.md` updated with R76 row.
