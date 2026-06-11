# Task 82 - R82 Behavior Drift Dimension and P5 Launch-Gate Evaluator

## 1. Task Breakdown

### Task T0: Read prior R79 plan rows and update the plan-level task list

**Scope**: This is a docs-only task to ensure the
`docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
T8 row and the R82 status header in `PROGRESS_FLOW.zh-CN.md`
correctly reference R82's full deliverable.

**Dependency**: None.

**Touched modules**:
- `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
  (T8 row updated from `pending` to `in_progress`; detail bullet list
  updated to match this task.md)
- `docs/requirements/index.md` (R82 row added)

**Completion definition**: T8 row reflects R82; R82 row in index.md
is in `in_progress` state.

**Validation step**: `grep -E "R82" docs/requirements/index.md
docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`

### Task T1: Declare `BehaviorDriftDimension` Literal

**Scope**: Add the 17-dim Literal type to
`src/helios_v2/evaluation/contracts.py` and export it from
`src/helios_v2/evaluation/__init__.py`.

**Dependency**: None.

**Touched modules**:
- `src/helios_v2/evaluation/contracts.py`
- `src/helios_v2/evaluation/__init__.py`

**Completion definition**: `BehaviorDriftDimension` is a
`Literal[...]` of exactly 17 strings in the prescribed family
order; `from helios_v2.evaluation import BehaviorDriftDimension`
succeeds.

**Validation step**:
```python
from helios_v2.evaluation import BehaviorDriftDimension
import typing
# confirm exactly 17 args
assert typing.get_args(BehaviorDriftDimension) == (
    "dopamine", "norepinephrine", "serotonin", "cortisol",
    "valence", "arousal", "tension", "comfort",
    "novelty", "uncertainty", "social_safety", "aggregate_salience",
    "i_want_to_say_freq", "i_send_through_freq", "i_want_to_think_more_freq",
    "remember_this_freq", "act_type_distribution",
)
```

### Task T2: Implement `DriftEvaluationResult` and `DriftEvaluationReport`

**Scope**: Declare the two frozen dataclasses in
`src/helios_v2/evaluation/r82_drift.py` (new file). No behavior yet.

**Dependency**: T1 (so the type can be imported).

**Touched modules**:
- `src/helios_v2/evaluation/r82_drift.py` (new)

**Completion definition**: The two dataclasses are importable
from `helios_v2.evaluation`.

**Validation step**:
```python
from helios_v2.evaluation import DriftEvaluationResult, DriftEvaluationReport
r = DriftEvaluationResult(scenario_id="A", family="hormone", dim="dopamine", start_value=0.5, end_value=0.7, min_value=0.3, max_value=0.8, abs_drift=0.2, range_drift=0.5, classification="drift_positive", sample_count=10, recalibration_recommendation="n/a")
```

### Task T3: Implement `AggressiveRadicalDriftEvaluator` core

**Scope**: Implement the `evaluate()` method that reads the JSONL
and produces the 17-dim `DriftEvaluationReport`. The
`_extract_dim_value` / `_classify_drift` /
`_classify_act_type_distribution` /
`_recalibration_recommendation` / `_family_summary` /
`_overall_drift_score` helpers are implemented in this task.

**Dependency**: T2.

**Touched modules**:
- `src/helios_v2/evaluation/r82_drift.py`

**Completion definition**: An end-to-end evaluator exists; a
10-tick A_praise JSONL can be processed and the report has 17
entries.

**Validation step**:
```python
from pathlib import Path
from helios_v2.evaluation import AggressiveRadicalDriftEvaluator
report = AggressiveRadicalDriftEvaluator(Path("logs/prompt_probe_scenarios/r79d/A_praise.jsonl")).evaluate()
assert len(report.results) == 17
assert report.tick_count == 10
```

### Task T4: Implement `is_p5_launch_gate_open` + constants

**Scope**: Add the `is_p5_launch_gate_open` function and the
`_P5_LAUNCH_GATE_THRESHOLD` constant. Both are exported from
`helios_v2.evaluation`.

**Dependency**: T3.

**Touched modules**:
- `src/helios_v2/evaluation/r82_drift.py`
- `src/helios_v2/evaluation/__init__.py`

**Completion definition**:
`from helios_v2.evaluation import is_p5_launch_gate_open`
succeeds; `is_p5_launch_gate_open(0.02) is True` and
`is_p5_launch_gate_open(0.019) is False`.

**Validation step**:
```python
from helios_v2.evaluation import is_p5_launch_gate_open
assert is_p5_launch_gate_open(0.02) is True
assert is_p5_launch_gate_open(0.019) is False
assert is_p5_launch_gate_open(1.0) is True
assert is_p5_launch_gate_open(0.0) is False
```

### Task T5: Write `tests/test_r82_drift_evaluator.py` (23 unit tests)

**Scope**: 17 per-dim tests + 4 family-aggregate tests + 1 P5
launch-gate test + 1 recalibration-recommendation test = 23 tests.

**Dependency**: T3, T4.

**Touched modules**:
- `tests/test_r82_drift_evaluator.py` (new)

**Completion definition**: `pytest
tests/test_r82_drift_evaluator.py -v` shows 23/23 PASS.

**Validation step**:
```bash
.venv/bin/python -m pytest tests/test_r82_drift_evaluator.py -v
```

The 23 tests are listed in §6.1 below.

### Task T6: Write `tests/test_r82_p5_launch_gate.py` (3 tests)

**Scope**: 3 tests verifying the P5 launch gate.

**Dependency**: T4.

**Touched modules**:
- `tests/test_r82_p5_launch_gate.py` (new)

**Completion definition**: `pytest tests/test_r82_p5_launch_gate.py
-v` shows 3/3 PASS.

**Validation step**:
```bash
.venv/bin/python -m pytest tests/test_r82_p5_launch_gate.py -v
```

The 3 tests are listed in §6.2 below.

### Task T7: Add `--with-drift-report` flag to R79-D CLI

**Scope**: Modify `src/helios_v2/tests/r79d/cli.py` to accept
`--with-drift-report` and write `drift_report.md` next to the
JSONL output.

**Dependency**: T3, T4.

**Touched modules**:
- `src/helios_v2/tests/r79d/cli.py`

**Completion definition**: `python -m helios_v2.tests.r79d run
--scenario A_praise --with-drift-report --ticks 10` produces both
`A_praise.jsonl` and `A_praise.drift_report.md`.

**Validation step**:
```bash
.venv/bin/python -m helios_v2.tests.r79d run --scenario A_praise --with-drift-report --ticks 10
ls logs/prompt_probe_scenarios/r79d/A_praise.*
# expect A_praise.jsonl and A_praise.drift_report.md
```

### Task T8: Doc sync (4 documents)

**Scope**: Update 4 documents to reflect R82's delivery.

**Dependency**: T7.

**Touched modules**:
- `docs/OWNER_GUIDE.md`: add §3.8.3 R82 entry
- `docs/ARCHITECTURE_BOUNDARIES.md`: add §10.d P5 launch gate
- `docs/PROGRESS_FLOW.zh-CN.md`: status header + new R82 module
  index block
- `docs/requirements/index.md`: R82 row

**Completion definition**: All 4 documents reference R82.

**Validation step**: `grep -E "R82" docs/OWNER_GUIDE.md
docs/ARCHITECTURE_BOUNDARIES.md docs/PROGRESS_FLOW.zh-CN.md
docs/requirements/index.md` shows R82 in all 4 files.

### Task T9: Full suite regression + R21 + composition guard

**Scope**: Verify the entire test suite still passes.

**Dependency**: T5, T6, T7, T8.

**Touched modules**: (none)

**Completion definition**:
- Full suite: 945 passed (R81 baseline 922 + R82 new 23) + 0
  regression
- R21 ad-hoc logging guard: 1/1 PASS
- Composition owner-boundary guard: 4/4 PASS
- 2 baseline perf fails (pre-existing, unrelated to R82) are
  acceptable

**Validation step**:
```bash
.venv/bin/python -m pytest tests/ -q --tb=no
.venv/bin/python -m pytest tests/test_no_adhoc_logging_guard.py tests/test_composition_owner_boundary_guard.py -v
```

### Task T10: Commit + push to origin

**Scope**: Commit R82 to the `aggressive-radical-persona-no-theater`
beta branch and push to origin.

**Dependency**: T9.

**Touched modules**: (none)

**Completion definition**: A single commit
`R82: BehaviorDriftDimension 17-dim taxonomy + AggressiveRadicalDriftEvaluator + P5 launch gate`
exists on `aggressive-radical-persona-no-theater`; the commit is
pushed to `origin/aggressive-radical-persona-no-theater`; the
branch is **not** merged to main (preserves the R79 plan's beta
branch lock).

**Validation step**:
```bash
git log --oneline -1
# expect the R82 commit hash
git push origin aggressive-radical-persona-no-theater
```

## 2. Dependencies

```
T0 (docs) ──┐
            ├──> T1 (Literal type) ──> T2 (dataclasses) ──> T3 (evaluator) ──┐
                                                                             ├──> T5 (23 unit tests)
                                                                             ├──> T6 (3 launch-gate tests)
                                                                             ├──> T7 (CLI --with-drift-report)
                                                                             │         │
                                                                             │         v
                                                                             ├──> T8 (4 docs) ──> T9 (regression) ──> T10 (commit + push)
                                                                             │
                                                                             └──> T4 (P5 launch gate) ──┘
```

T0 is a docs-only task that can be done in parallel with T1-T4.
T1-T4 are the core implementation. T5-T6 are the tests. T7 is the
CLI integration. T8 is the docs sync. T9 is the regression
verification. T10 is the commit + push.

## 3. Files and Modules

### 3.1 New files
- `src/helios_v2/evaluation/r82_drift.py` (~200 lines)
- `tests/test_r82_drift_evaluator.py` (~400 lines, 23 tests)
- `tests/test_r82_p5_launch_gate.py` (~50 lines, 3 tests)

### 3.2 Modified files
- `src/helios_v2/evaluation/contracts.py` (+10 lines: the
  `BehaviorDriftDimension` Literal)
- `src/helios_v2/evaluation/__init__.py` (+5 lines: the new
  exports)
- `src/helios_v2/tests/r79d/cli.py` (+30 lines: the
  `--with-drift-report` flag and the markdown rendering)
- `docs/OWNER_GUIDE.md` (+30 lines: §3.8.3 R82)
- `docs/ARCHITECTURE_BOUNDARIES.md` (+30 lines: §10.d P5 launch
  gate)
- `docs/PROGRESS_FLOW.zh-CN.md` (status header + R82 module
  index block)
- `docs/requirements/index.md` (R82 row)
- `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`
  (T8 row updated)

### 3.3 New docs files (this package)
- `docs/requirements/82-r82-behavior-drift-dimension-and-evaluator/requirement.md`
  (this task's parent)
- `docs/requirements/82-r82-behavior-drift-dimension-and-evaluator/design.md`
- `docs/requirements/82-r82-behavior-drift-dimension-and-evaluator/task.md`
  (this file)

## 4. Implementation Order

T0 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10

T0 can be done in parallel with T1-T4 (docs only).
T5 and T6 can be done in parallel with T7 (different files).
T8 must be done after T7 (the docs reference the CLI flag).
T9 must be done after T5, T6, T7, T8.
T10 must be done after T9.

## 5. Validation Plan

The validation is described in §1 above. The high-level checks are:
- 23 R82 unit tests + 3 R82 P5 launch-gate tests = 26 new tests
- Full suite 922 + 26 = 948 passed, 0 regression
- R21 ad-hoc logging guard 1/1 PASS
- Composition owner-boundary guard 4/4 PASS
- R79-D CLI `--with-drift-report` end-to-end smoke passes
- 4 doc files reference R82

## 6. Test Inventory

### 6.1 `tests/test_r82_drift_evaluator.py` (23 tests)

**Per-dim tests (17)**:
- `test_dim_dopamine_drift_positive`
- `test_dim_norepinephrine_drift_negative`
- `test_dim_serotonin_drift_neutral`
- `test_dim_cortisol_dim_unavailable`
- `test_dim_valence_drift_positive`
- `test_dim_arousal_drift_neutral`
- `test_dim_tension_drift_positive`
- `test_dim_comfort_dim_unavailable`
- `test_dim_novelty_drift_positive`
- `test_dim_uncertainty_drift_neutral`
- `test_dim_social_safety_drift_positive`
- `test_dim_aggregate_salience_drift_neutral`
- `test_dim_i_want_to_say_freq_drift_positive`
- `test_dim_i_send_through_freq_drift_neutral`
- `test_dim_i_want_to_think_more_freq_drift_positive`
- `test_dim_remember_this_freq_dim_unavailable`
- `test_dim_act_type_distribution_drift_positive`

**Family-aggregate tests (4)**:
- `test_family_hormone_summary`
- `test_family_feeling_summary`
- `test_family_cognition_summary`
- `test_family_behavior_summary`

**P5 launch-gate test (1)**:
- `test_p5_launch_gate_threshold`

**Recalibration-recommendation test (1)**:
- `test_recalibration_recommendation_for_i_want_to_think_more_freq`

### 6.2 `tests/test_r82_p5_launch_gate.py` (3 tests)

- `test_p5_launch_gate_open_at_threshold`
- `test_p5_launch_gate_closed_below_threshold`
- `test_p5_launch_gate_function_is_exported`

## 7. Completion Criteria

R82 is complete when:
1. All 10 tasks (T0-T10) are done.
2. All 26 new tests pass.
3. Full suite 922 + 26 = 948 passed, 0 regression.
4. R21 ad-hoc logging guard 1/1 PASS.
5. Composition owner-boundary guard 4/4 PASS.
6. R79-D CLI `--with-drift-report` end-to-end smoke passes.
7. 4 doc files reference R82.
8. R82 commit exists on
   `aggressive-radical-persona-no-theater` beta branch and is
   pushed to origin.
9. The R79 plan is closed: R79-A, R79-B, R79-C, R79-D, R80, R81,
   R82 are all delivered.
