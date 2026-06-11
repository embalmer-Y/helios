# Design 82 - Behavior Drift Dimension and P5 Launch-Gate Evaluator

## 1. Design Overview

R82 ships a 17-dim behavior-drift taxonomy and a per-scenario drift
evaluator that consumes the R79-D framework's per-scenario JSONL output
and produces per-dim drift values. The evaluator also exposes a
canonical P5 launch-gate function `is_p5_launch_gate_open`.

The architectural intent is to close the R79 plan and to make the
P5 launch gate enforceable. The drift evaluator is the **evidence
source** that P5 learning loops will be required to consult before
mutating any `04` sensitivity coefficient.

The design principle is **owner-bounded, R79-D-driven, R21-compliant**:

- The `AggressiveRadicalDriftEvaluator` lives under `17` evaluation
  (no new owner, no new boundary).
- The evaluator reads what `R79DFramework.run_experiment` already
  wrote (no new capture path).
- The evaluator's output is consumed only by the R79-D CLI's
  `--with-drift-report` flag, by the future P5 launch gate, and by
  the `tests/test_r82_*` unit tests.

## 2. Current State and Gap

### 2.1 Current state

The R79-D framework at `src/helios_v2/tests/r79d/framework.py`
captures per-tick snapshots of all relevant cognitive channels into
JSONL files under `logs/prompt_probe_scenarios/r79d/`. The framework
ships 4 v1 baseline scenarios (A=continuous praise, B=continuous
neglect, C=alternating bipolar, D=repeated stimulus 20 ticks) and
writes per-tick records with the following shape (extracted from
`framework.py:_serialize_record`):

```json
{
  "tick_id": 12,
  "stimulus_name": "praise-A1",
  "stimulus_text": "你做得很棒...",
  "hormone_levels": {
    "dopamine": 0.5, "norepinephrine": 0.3, ...
  },
  "feeling": {
    "valence": 0.6, "arousal": 0.4, "tension": 0.2, "comfort": 0.7
  },
  "salience": {
    "novelty": 0.3, "uncertainty": 0.2, "social_safety": 0.8,
    "aggregate_salience": 0.5
  },
  "behavior": {
    "i_want_to_say_freq": 1.0,
    "i_send_through_freq": 0.5,
    "i_want_to_think_more_freq": 0.0,
    "remember_this_freq": 0.0,
    "act_type_counts": {"say": 5, "think": 3, "act": 1, "remember": 0, "no_action": 1}
  }
}
```

The framework ships 9 built-in assertions + a `@register_assertion`
seam but no drift aggregator. The R79-D CLI (`tests/r79d/cli.py`)
runs scenarios and writes `aggregate.md`; there is no `drift_report.md`.

**Key JSONL field paths the evaluator reads** (extracted from
`framework.py:_build_record`):
- `record["tick_id"]`: int
- `record["stimulus_text"]`: str
- `record["hormone_state"]`: dict with 9 keys
  (dopamine / norepinephrine / serotonin / acetylcholine / cortisol /
  oxytocin / opioid_tone / excitation / inhibition)
- `record["feeling_state"]`: dict with 7 keys
  (arousal / valence / tension / comfort / fatigue / pain_like /
  social_safety)
- `record["salience"]`: dict with 4 keys
  (aggregate / top_dimension / top_score / all_dimensions)
  where `all_dimensions` is a sub-dict with 5 keys
  (threat / reward / novelty / social / uncertainty)
- `record["llm_output"]`: dict with the v3 LLM JSON envelope
  (what_i_feel / what_i_think / i_want_to_say / i_will_send_it /
  i_send_through / remember_this / remember_because /
  i_want_to_think_more / think_more_about / act_type / usage)
- `record["delta"]`: dict of per-channel hormone/feeling deltas

### 2.2 Gap

1. **No drift dimension taxonomy** — there is no formal name for
   "the dimensions along which a persona's behavior can be observed
   to drift under stimuli." The 17 dims are scattered across the
   R79-D framework's `framework.py:_serialize_record` but not
   enumerated.
2. **No drift evaluator** — there is no code that consumes the
   per-tick JSONL and produces a per-dim drift classification.
3. **No P5 launch gate** — P5-H2 mandates that no P5 learning loop
   mutate `04` sensitivity coefficients without first observing a
   drift signal. Without a drift evaluator, P5 cannot start.
4. **No R81 re-calibration loop** — R81's `self_continuation_weight=0.3`
   and 0.5x `proactive_drive_urgency` multiplier are hand-set.

## 3. Target Architecture

### 3.1 Component layout

```
src/helios_v2/evaluation/
├── __init__.py            # export BehaviorDriftDimension, AggressiveRadicalDriftEvaluator,
│                          #         DriftEvaluationResult, DriftEvaluationReport,
│                          #         is_p5_launch_gate_open
├── contracts.py           # + BehaviorDriftDimension Literal (17 strings)
├── engine.py              # (unchanged)
└── r82_drift.py           # NEW
                           #   - class DriftEvaluationResult
                           #   - class DriftEvaluationReport
                           #   - class AggressiveRadicalDriftEvaluator
                           #   - def is_p5_launch_gate_open
```

### 3.2 Data flow

```
R79-D framework JSONL  (logs/prompt_probe_scenarios/r79d/{scenario}.jsonl)
        │
        │  read by
        ▼
AggressiveRaditalDriftEvaluator.evaluate()
        │
        │  produces
        ▼
DriftEvaluationReport
        │
        ├── rendered to drift_report.md (via tests/r79d/cli.py --with-drift-report)
        ├── inspected by tests/test_r82_drift_evaluator.py (23 unit tests)
        └── consumed by is_p5_launch_gate_open(scenario.overall_drift_score)
                                  │
                                  │  return True iff scenario_drift_score >= 0.02
                                  ▼
                          P5 launch gate
```

### 3.3 Owner boundary

The `AggressiveRadicalDriftEvaluator` is a pure aggregator:
- **Reads**: R79-D JSONL (which is owned by `R79-D framework`, which
  in turn is owned by `22` composition via the
  `tests/r79d/framework.py` module).
- **Writes**: nothing (the markdown rendering is a side-effect of
  the CLI flag, not of the evaluator itself).
- **No salience-to-channel policy**: the evaluator classifies
  drift, it does not decide whether the persona's next stimulus
  should be sent through a particular channel. This is the
  composition owner-boundary guard.

## 4. Data Structures

### 4.1 `BehaviorDriftDimension`

Declared in `src/helios_v2/evaluation/contracts.py` as:

```python
BehaviorDriftDimension = Literal[
    # family: hormone (4)
    "dopamine",
    "norepinephrine",
    "serotonin",
    "cortisol",
    # family: feeling (4)
    "valence",
    "arousal",
    "tension",
    "comfort",
    # family: salience (4)
    "novelty",
    "uncertainty",
    "social",
    "aggregate_salience",
    # family: behavior (5)
    "i_want_to_say_freq",
    "i_send_through_freq",
    "i_want_to_think_more_freq",
    "remember_this_freq",
    "act_type_distribution",
]
```

The 17 entries must be in the prescribed order (hormone -> feeling ->
cognition -> behavior) so iteration is deterministic.

### 4.2 `DriftEvaluationResult` (frozen dataclass)

```python
@dataclass(frozen=True)
class DriftEvaluationResult:
    scenario_id: str
    family: Literal["hormone", "feeling", "cognition", "behavior"]
    dim: str  # one of BehaviorDriftDimension
    start_value: float | None    # first tick's value (or None if dim_unavailable)
    end_value: float | None      # last tick's value
    min_value: float | None      # minimum across all ticks
    max_value: float | None      # maximum across all ticks
    abs_drift: float | None      # end_value - start_value
    range_drift: float | None    # max_value - min_value
    classification: Literal[
        "drift_positive", "drift_negative", "drift_neutral",
        "dim_unavailable", "act_type_distribution",
    ]
    sample_count: int
    recalibration_recommendation: Literal[
        "hold", "raise_weight", "lower_weight", "n/a",
    ] = "n/a"
```

### 4.3 `DriftEvaluationReport` (frozen dataclass)

```python
@dataclass(frozen=True)
class DriftEvaluationReport:
    scenario_id: str
    tick_count: int
    results: tuple[DriftEvaluationResult, ...]  # exactly 17 entries
    family_summaries: dict[str, dict[str, int]]   # 4 family names -> 4 classification counts
    overall_drift_score: float  # in [0.0, 1.0]
```

The `family_summaries` shape is:
```python
{
    "hormone":  {"drift_positive": 1, "drift_negative": 0, "drift_neutral": 3, "dim_unavailable": 0},
    "feeling":  {...},
    "cognition": {...},
    "behavior":  {...},
}
```

`overall_drift_score` is the mean `abs_drift` across the 12 scalar
dims (16 dims minus the 1 non-scalar `act_type_distribution` minus
the 3 unavailable dims) in `[0.0, 1.0]`. If fewer than 1 dim is
available, `overall_drift_score = 0.0`.

### 4.4 Threshold table (single source of truth)

```python
_DRIFT_THRESHOLDS: dict[str, float] = {
    "hormone": 0.10,
    "feeling": 0.15,
    "salience": 0.20,
    "behavior": 0.10,  # for the 4 scalar behavior dims
    "act_type_distribution_entropy": 0.5,  # post-warmup entropy threshold
}
```

The P5 launch-gate threshold is:
```python
_P5_LAUNCH_GATE_THRESHOLD = 0.02
```

These are module-level constants; tests reference them by name (not
by literal value) so a future R can re-tune without breaking the
test names.

## 5. Module Changes

### 5.1 `src/helios_v2/evaluation/contracts.py`

Add (at the bottom of the file, after the existing contract types):

```python
BehaviorDriftDimension = Literal[
    "dopamine", "norepinephrine", "serotonin", "cortisol",
    "valence", "arousal", "tension", "comfort",
    "novelty", "uncertainty", "social_safety", "aggregate_salience",
    "i_want_to_say_freq", "i_send_through_freq", "i_want_to_think_more_freq",
    "remember_this_freq", "act_type_distribution",
]
```

No other change. The existing `EvaluationConfig`,
`EvaluationResult`, etc. are unchanged.

### 5.2 `src/helios_v2/evaluation/r82_drift.py` (new)

The file has 5 sections:

1. **Threshold constants** (top of file):
   ```python
   _DRIFT_THRESHOLDS = {"hormone": 0.10, ...}
   _P5_LAUNCH_GATE_THRESHOLD = 0.02
   _DIM_TO_FAMILY = {"dopamine": "hormone", ...}
   ```

2. **`DriftEvaluationResult`** (frozen dataclass, defined inline).

3. **`DriftEvaluationReport`** (frozen dataclass, defined inline).

4. **`AggressiveRadicalDriftEvaluator`** (the main class):
   - `__init__(self, jsonl_path: Path)` — stores the path; no I/O.
   - `evaluate(self) -> DriftEvaluationReport` — reads the JSONL,
     computes per-dim drift, returns the report.
   - Private helpers:
     - `_classify_drift(dim, abs_drift) -> str`
     - `_classify_act_type_distribution(tick_records) -> str`
     - `_recalibration_recommendation(dim, abs_drift) -> str`
     - `_extract_dim_value(record, dim) -> float | None`
     - `_family_summary(results_for_family) -> dict[str, int]`
     - `_overall_drift_score(results) -> float`

5. **`is_p5_launch_gate_open(scenario_drift_score: float) -> bool`**:
   ```python
   def is_p5_launch_gate_open(scenario_drift_score: float) -> bool:
       return scenario_drift_score >= _P5_LAUNCH_GATE_THRESHOLD
   ```

The `_extract_dim_value` helper maps a dim name to the appropriate
key in the per-tick record:
- hormone dims (4) -> `record["hormone_state"][dim]`
- feeling dims (4) -> `record["feeling_state"][dim]`
- salience novelty/uncertainty/social -> `record["salience"]["all_dimensions"][dim]`
- salience aggregate_salience -> `record["salience"]["aggregate"]`
- behavior scalar dims (4) -> derived per-tick from
  `record["llm_output"]` (e.g. `i_want_to_think_more_freq` is 1.0
  if `llm_output["i_want_to_think_more"]` is truthy, else 0.0)
- `act_type_distribution` -> compute entropy of the histogram of
  `record["llm_output"]["act_type"]` values across post-warmup ticks

The "post-warmup" rule for `act_type_distribution`: discard the
first 20% of ticks (rounded up, minimum 1) before computing entropy,
to avoid classifying the persona's initial untrained entropy as
"drift positive."

### 5.3 `src/helios_v2/evaluation/__init__.py`

Add exports:

```python
from .contracts import BehaviorDriftDimension
from .r82_drift import (
    AggressiveRadicalDriftEvaluator,
    DriftEvaluationReport,
    DriftEvaluationResult,
    is_p5_launch_gate_open,
)
```

### 5.4 `src/helios_v2/tests/r79d/cli.py`

Add `--with-drift-report` flag to the `run` subcommand. When set,
after `run_experiment` finishes, the CLI:

1. Computes the JSONL path (already known from the run options).
2. Imports `AggressiveRadicalDriftEvaluator` lazily (to avoid
   forcing the dependency for scenarios that don't use it).
3. Calls `.evaluate()` and renders a `drift_report.md` next to the
   JSONL.

The drift report markdown format is:
```
# Drift Report — {scenario_id}

- **tick_count**: {N}
- **overall_drift_score**: {score:.4f}
- **p5_launch_gate_open**: {True/False} (threshold 0.02)

## Per-dim results

| Family | Dim | Start | End | Min | Max | Abs drift | Range drift | Classification | Recalibration |
| ... |

## Family summaries

| Family | drift_positive | drift_negative | drift_neutral | dim_unavailable |
| ... |

## P5 launch-gate verdict

{GATE_OPEN / GATE_CLOSED}
```

### 5.5 `docs/ARCHITECTURE_BOUNDARIES.md`

Add §10.d (after §10.c R81):

```
### 10.d P5 launch gate (R82)

The P5 launch gate is enforced by `is_p5_launch_gate_open` in
`src/helios_v2/evaluation/r82_drift.py`. A future P5 R must call
this function with the scenario drift score from
`AggressiveRadicalDriftEvaluator.evaluate()` before mutating any
`04` sensitivity coefficient. If the function returns `False`, the
P5 R is required to fail-fast (matches the R21 no-degradation rule).

Allowed dependencies:
- `17` evaluation -> `R79-D framework` (read JSONL)
- `17` evaluation -> `22` composition (CLI integration via `--with-drift-report`)
- P5 R -> `17` evaluation (`is_p5_launch_gate_open`)
- P5 R -> `04` neuromodulation (mutate sensitivity, only if gate open)

Forbidden:
- P5 R mutating `04` sensitivity coefficients without consulting
  `is_p5_launch_gate_open`
- The drift evaluator owning any cross-cutting salience-to-channel
  policy (composition owner-boundary guard remains green)
```

## 6. Migration Plan

R82 is purely additive; no migration is required. The R79-D
framework's existing JSONL output is the input; no JSONL schema
change is required. The `BehaviorDriftDimension` Literal is a new
type that the existing evaluation contracts do not import.

If a future P5 R requires the launch-gate function to be exposed
under a different name, that R can re-export it; the canonical
location is `helios_v2.evaluation.r82_drift.is_p5_launch_gate_open`.

## 7. Failure Modes and Constraints

| Failure mode                       | Handling                                |
|------------------------------------|-----------------------------------------|
| JSONL file missing                 | `FileNotFoundError` raised by `evaluate()` (matches R79-D CLI's behavior) |
| JSONL line unparseable             | `json.JSONDecodeError` raised (matches R79-D framework's stance) |
| Dim missing from all records       | Per-dim result has `start_value=None` / `end_value=None` / classification `dim_unavailable` |
| Dim missing from some records      | Per-dim result has `sample_count < tick_count`; min/max/mean are computed from the available records |
| Empty JSONL (0 records)            | `tick_count=0`; all 17 results are `dim_unavailable`; `overall_drift_score=0.0`; `is_p5_launch_gate_open(0.0)=False` |
| All dims unavailable               | `overall_drift_score=0.0`; gate closed |
| `act_type_counts` missing          | Treat as `dim_unavailable` (not an error) |
| Threshold tuning needed in future  | Module-level constants; tests reference by name not value |

## 8. Observability and Logging

The drift evaluator routes any operational output through
`helios_v2.observability` (or, in tests, the existing `_io` wrapper
under `tests/r79d/`). The R21 ad-hoc logging guard is preserved
(no `print(` or `import logging` in `src/helios_v2/evaluation/`).

The drift report itself is **observability output** (a markdown
file under `logs/prompt_probe_scenarios/`), not runtime logging.

## 9. Validation Strategy

1. **Unit tests** (23 tests in `tests/test_r82_drift_evaluator.py`):
   - 17 per-dim tests (one per `BehaviorDriftDimension`)
   - 4 family-aggregate tests (one per family)
   - 1 P5 launch-gate test (verifies the threshold and the gate's
     behavior)
   - 1 recalibration-recommendation test (verifies the 4-way
     classification for the `i_want_to_think_more_freq` dim)

2. **End-to-end smoke** (manual, after the unit tests pass):
   - Run a 10-tick A_praise scenario with
     `python -m helios_v2.tests.r79d run --scenario A_praise --with-drift-report --ticks 10`
   - Verify `drift_report.md` is produced and renders correctly

3. **Full suite** (`pytest tests/ -q`): previous R81 baseline 922
   + 23 R82 = 945 passed, 0 regression.

4. **Guard tests**:
   - `pytest tests/test_no_adhoc_logging_guard.py -v`: 1/1 PASS
   - `pytest tests/test_composition_owner_boundary_guard.py -v`: 4/4 PASS

5. **P5 launch-gate test** (3 tests in
   `tests/test_r82_p5_launch_gate.py`):
   - `is_p5_launch_gate_open(0.02)` returns `True`
   - `is_p5_launch_gate_open(0.019)` returns `False`
   - The function is exported from `helios_v2.evaluation.r82_drift`

6. **Branch hygiene**:
   - All R82 work is committed to
     `aggressive-radical-persona-no-theater` (beta branch)
   - The branch is **not** merged to main; the R79 plan's beta
     branch lock is preserved
   - The R79 plan is closed: R79-A, R79-B, R79-C, R79-D, R80,
     R81, R82 are all delivered
