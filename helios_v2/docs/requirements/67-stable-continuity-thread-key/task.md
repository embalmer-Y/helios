# Requirement 67 - Stable Continuity Thread Key: Task

## 1. Title
Task Plan: Stable Continuity Thread Key

## 2. Task Breakdown

### Task 1: Sharpen `_continuity_key` to drop tick-specific origin_ref
- **Description**: Remove `origin_ref` parameter from `FirstVersionAutonomyPath._continuity_key`; return `cls._base_reason(carry_reason)` as the stable key.
- **Completion**: Method signature updated; call sites compile without error.
- **Validation**: `python -m pytest tests/test_autonomy_engine.py -xvs` (no key-string assertion breaks).

### Task 2: Update call sites in `assemble_result`
- **Description**: Remove `origin_ref` argument from both `_continuity_key` call sites (blocked-outward path and carry-forward path). Keep `origin_ref` passed to `_build_deferred_record` separately.
- **Completion**: Both call sites use the new signature; `origin_ref` still flows to `_build_deferred_record` for provenance.
- **Validation**: `python -m pytest tests/test_autonomy_engine.py tests/test_runtime_composition.py -xvs` (existing thread tests still pass).

### Task 3: Add reinforcement-across-ticks integration test
- **Description**: Add `test_consecutive_deferring_ticks_reinforce_single_thread` to `test_runtime_composition.py`. Run 5 ticks with concluded+no-action; assert the `insufficient_outward_readiness` thread has `reinforcement_count >= 2` and `age_ticks >= 3`.
- **Completion**: Test passes.
- **Validation**: `python -m pytest tests/test_runtime_composition.py::test_consecutive_deferring_ticks_reinforce_single_thread -xvs`

### Task 4: Add reinforcement-survives-gap integration test
- **Description**: Add `test_reinforcement_survives_carry_forward_gap` to `test_runtime_composition.py`. Run 4 ticks where tick 3 breaks the deferral chain (different disposition); assert tick 4's thread is the same thread (age >= 2, reinforcement_count >= 1).
- **Completion**: Test passes.
- **Validation**: `python -m pytest tests/test_runtime_composition.py::test_reinforcement_survives_carry_forward_gap -xvs`

### Task 5: Run full test suite
- **Description**: Run the complete 744+ test suite to confirm no regression.
- **Completion**: All tests pass.
- **Validation**: `python -m pytest -q`

### Task 6: Update index.md and progress flow maps
- **Description**: Add R67 row to `docs/requirements/index.md`. Update `docs/PROGRESS_FLOW.zh-CN.md` and `docs/PROGRESS_FLOW.en.md` last-synced line.
- **Completion**: R67 appears in the index with correct maturity, dependencies, and notes.

## 3. Dependencies
- Task 2 depends on Task 1.
- Tasks 3, 4 depend on Task 2.
- Task 5 depends on Tasks 1-4.
- Task 6 depends on Task 5.

## 4. Files and Modules
| File | Change Type |
|------|-------------|
| `helios_v2/src/helios_v2/autonomy/engine.py` | Modify `_continuity_key` and 2 call sites |
| `helios_v2/tests/test_runtime_composition.py` | Add 2 integration tests |
| `helios_v2/tests/test_autonomy_engine.py` | Audit for key-string assertions |
| `helios_v2/docs/requirements/index.md` | Add R67 row |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` | Update last-synced |
| `helios_v2/docs/PROGRESS_FLOW.en.md` | Update last-synced |

## 5. Implementation Order
Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6

## 6. Validation Plan
- After Task 2: autonomy unit tests + existing thread integration tests.
- After Task 4: new reinforcement tests specifically.
- After Task 5: full suite.

## 7. Completion Criteria
- R67 acceptance criteria 1-4 all satisfied.
- No regression in the full test suite.
- Index and progress flow maps updated.
