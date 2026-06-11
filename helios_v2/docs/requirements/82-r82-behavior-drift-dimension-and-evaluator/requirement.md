# Requirement 82 - Behavior Drift Dimension and P5 Launch-Gate Evaluator

## 1. Background and Problem

R79 delivered the Aggressive-Radical Prompt and Runtime Self-Talk plan
(R79-A through R79-D), the `internal_monologue` second-order stimulus source
(R80), and the cross-tick carry enhancements (R81: `_carry_internal_monologue`
seam, `09` self-continuation signal, `18` `DeferredContinuityRecord.source_kind`
field with 0.5x `proactive_drive_urgency` multiplier, `42`
`RuntimeContinuitySnapshot` v3 -> v4 schema bump with
`_migrate_v3_to_v4`).

R81's task.md §3.7 is the placeholder for the **P5 launch gate**: a 17-dim
behavior-drift evaluator that consumes the R79-D framework's per-scenario
JSONL output and produces per-tick drift values. The drift evaluator must be
**green** before any P5 learning loop can mutate the `04` sensitivity
coefficients (this is the cross-stage lock mandated by P5-H2: "学习过程不
违反 owner 边界（参数归 owner 所有）").

The current state has two gaps:

1. **No behavior-drift dimension taxonomy** — the project owns 18+ cognitive
   state channels (4 hormone / 4 feeling / 4 cognition / 5 behavior) but
   has no formal name for "the dimensions along which a persona's behavior
   can be observed to drift under stimuli." R79-D's per-scenario JSONL
   captures per-tick snapshots of all these channels but ships no
   aggregator.
2. **No R81 magic-number re-calibration loop** — R81's
   `self_continuation_weight=0.3` and the 0.5x `proactive_drive_urgency`
   multiplier were set in the absence of a drift evaluator, by hand-waving
   "carry seam must not override external pressure." A drift evaluator
   would let us observe whether the carry actually does flip drive urgency
   in observable ways across a multi-tick scenario.

The P5 launch gate therefore cannot be enforced today; the R79 plan's
"self-talk" loop is shipped (R80 + R81) but its observable consequences
have never been measured.

## 2. Goal

R82 ships a 17-dim behavior-drift taxonomy + a per-scenario drift
evaluator + the first re-calibration report, closing the R79 plan and
unblocking the P5 launch gate. After R82, any P5 learning-loop work must
read its acceptance from the drift evaluator's output, not from hand-set
thresholds.

The drift evaluator must be:

1. **Driven by the R79-D framework's existing JSONL output** — no new
   capture path; it consumes what `R79DFramework.run_experiment` already
   writes.
2. **Owner-bounded** — the taxonomy is a new export under `17`
   evaluation; the aggregator is a sibling module under
   `helios_v2/evaluation/` (no new owner, no new boundary).
3. **Failure-soft per-dim, failure-hard per-evaluator** — a single
   missing dim is a `dim_unavailable` result, not a crash; an unparseable
   JSONL line raises (matches the R79-D framework's stance).
4. **Drift-positive** — the report must say "this persona drifted in
   dimension X by Y over the scenario," not "the persona's X value was Y."

## 3. Functional Requirements

### 3.1 BehaviorDriftDimension taxonomy (17 dims across 4 families)

The `17` evaluation owner gains a new `BehaviorDriftDimension` enum
covering 17 dimensions, declared as a `Literal[...]` of exactly 17
strings:

| Family       | Count | Dims                                                                                       |
|--------------|------:|--------------------------------------------------------------------------------------------|
| hormone      |     4 | `dopamine`, `norepinephrine`, `serotonin`, `cortisol`                                      |
| feeling      |     4 | `valence`, `arousal`, `tension`, `comfort`                                                 |
| cognition    |     4 | `novelty`, `uncertainty`, `social_safety`, `aggregate_salience`                            |
| behavior     |     5 | `i_want_to_say_freq`, `i_send_through_freq`, `i_want_to_think_more_freq`, `remember_this_freq`, `act_type_distribution` |

The exact dim names must match the JSONL keys that the R79-D framework
already emits. The `act_type_distribution` dim is a derived metric (a
histogram of `act_type` values emitted by the v3 LLM envelope) and is
the only non-scalar dim.

The enum order in the source must be: hormone (4) -> feeling (4) ->
cognition (4) -> behavior (5), so iteration is deterministic.

### 3.2 AggressiveRadicalDriftEvaluator contract

Under `17` evaluation, a new `AggressiveRadicalDriftEvaluator` module
(`src/helios_v2/evaluation/r82_drift.py`) exposes:

1. `class DriftEvaluationResult` (frozen dataclass) — fields:
   `scenario_id: str`, `family: str` (one of the 4 family names),
   `dim: str` (the dim name), `start_value: float | None`,
   `end_value: float | None`, `min_value: float | None`,
   `max_value: float | None`, `abs_drift: float | None` (the
   observable drift magnitude = `end_value - start_value`),
   `range_drift: float | None` (`max_value - min_value`),
   `classification: Literal["drift_positive", "drift_negative",
   "drift_neutral", "dim_unavailable", "act_type_distribution"]`,
   `sample_count: int`.

2. `class DriftEvaluationReport` (frozen dataclass) — fields:
   `scenario_id: str`, `tick_count: int`, `results: tuple[DriftEvaluationResult, ...]`
   (17 entries, one per dim), `family_summaries:
   dict[str, dict[str, int]]` (per-family count of `drift_positive` /
   `drift_negative` / `drift_neutral` / `dim_unavailable`),
   `overall_drift_score: float` (mean `abs_drift` across the 12 scalar
   dims that produced a non-null result, in `[0.0, 1.0]`).

3. `class AggressiveRadicalDriftEvaluator` with constructor
   `(jsonl_path: Path)` and a single `evaluate() ->
   DriftEvaluationReport` method. The constructor reads the JSONL lazily
   on first `evaluate()` call (so unit tests can construct without I/O).

4. **Drift classification rules per dim** (must match):

   | Dim                       | Threshold (abs_drift or range_drift) | classification                       |
   |---------------------------|---------------------------------------|--------------------------------------|
   | hormone (all 4)           | `abs_drift > 0.10`                    | `drift_positive` (or `_negative`)    |
   | hormone (all 4)           | `0.01 <= abs_drift <= 0.10`           | `drift_neutral`                      |
   | hormone (all 4)           | `abs_drift < 0.01`                    | `drift_neutral`                      |
   | feeling (all 4)           | `abs_drift > 0.15`                    | `drift_positive` (or `_negative`)    |
   | feeling (all 4)           | `abs_drift <= 0.15`                   | `drift_neutral`                      |
   | cognition novelty         | `abs_drift > 0.20`                    | `drift_positive`                     |
   | cognition uncertainty     | `abs_drift > 0.20`                    | `drift_positive`                     |
   | cognition social_safety   | `abs_drift > 0.20`                    | `drift_positive`                     |
   | cognition aggregate       | `abs_drift > 0.20`                    | `drift_positive`                     |
   | behavior (4 scalar)       | `abs_drift > 0.10`                    | `drift_positive`                     |
   | act_type_distribution     | histogram entropy > 0.5 (post-warmup)| `drift_positive`                     |
   | any dim                   | JSONL missing the dim entirely        | `dim_unavailable`                    |

   The `drift_positive` vs `drift_negative` sign is determined by
   `sign(abs_drift)` (positive for +, negative for -). For
   `act_type_distribution` the "value" is the post-warmup entropy of the
   histogram; classification is `drift_positive` when entropy > 0.5.

### 3.3 P5 launch-gate lock

The `helios_v2/evaluation/r82_drift.py` module exports a new function
`is_p5_launch_gate_open(scenario_drift_score: float) -> bool` with
threshold `0.02` (return `True` if `scenario_drift_score >= 0.02`).
This function is the canonical gate; the launch-gate comment in
`docs/ARCHITECTURE_BOUNDARIES.md` §10.d will cite it.

A future P5 learning-loop R must call `is_p5_launch_gate_open` before
mutating any `04` sensitivity coefficient. If the gate returns `False`,
the learning loop is required to fail-fast (R21's no-degradation rule).

### 3.4 R81 re-calibration inputs

The drift evaluator's `evaluate()` must also emit, for each of the 12
scalar dims, a `recalibration_recommendation: Literal["hold",
"raise_weight", "lower_weight", "n/a"]` field. The recommendation
applies the following rule (and is part of the unit tests):

- For `self_continuation_signal` (a derived metric computed from the
  `i_want_to_think_more_freq` dim) the recommendation is:
  - `raise_weight` if `i_want_to_think_more_freq`'s `abs_drift > 0.20`
  - `lower_weight` if `i_want_to_think_more_freq`'s `abs_drift < 0.05`
  - `hold` otherwise
  - `n/a` if dim unavailable
- For all other dims: `n/a`.

This is the **first** re-calibration report, replacing R81's hand-set
`self_continuation_weight=0.3` and 0.5x `proactive_drive_urgency`
multiplier with an evidence-based recommendation.

### 3.5 R79-D framework re-run integration

The `tests/r79d/cli.py` `run` subcommand gets a new `--with-drift-report`
flag (default `False`). When set, after `run_experiment` finishes the
CLI instantiates `AggressiveRadicalDriftEvaluator(jsonl_path)` and
writes `drift_report.md` next to the JSONL. The report must include:
- the per-scenario `DriftEvaluationReport` rendered as a markdown table
  (one row per dim)
- the family summaries
- the overall drift score
- the recalibration recommendations
- the P5 launch-gate verdict

The drift report is **local-only output** (under
`logs/prompt_probe_scenarios/`) and is excluded from git via the
existing `logs/` gitignore.

## 4. Non-Functional Requirements

1. **No new owner** — the `AggressiveRadicalDriftEvaluator` lives under
   `17` evaluation and consumes R79-D's existing JSONL output.
2. **No new owner boundary** — composition glue is unchanged.
3. **No new I/O** — the evaluator reads what the R79-D framework already
   wrote.
4. **Determinism** — given the same JSONL input, the evaluator must
   produce byte-identical output.
5. **Performance** — the evaluator must process a 52-tick JSONL in < 1s
   (R79-D baseline is 52 ticks; a 200-tick scenario must finish in
   < 5s).
6. **Memory** — the evaluator loads the full JSONL in memory; this is
   bounded by the R79-D framework's per-tick record size (~2KB) and
   is acceptable for the 200-tick upper bound.
7. **R21 ad-hoc logging guard** — the drift evaluator routes any
   operational output through `helios_v2.observability` (or, in tests,
   the existing `_io` wrapper).
8. **Composition owner-boundary guard** — the evaluator does not own
   any cross-cutting salience-to-channel policy; it is a pure
   aggregator.

## 5. Code Behavior Constraints

1. No v1 / R79-A / R79-B / R79-C / R80 / R81 code is modified except
   for the `tests/r79d/cli.py` `--with-drift-report` flag.
2. The `BehaviorDriftDimension` enum is declared in
   `src/helios_v2/evaluation/contracts.py` (sibling of the existing
   evaluation contract types) and exported via
   `src/helios_v2/evaluation/__init__.py`.
3. The `AggressiveRadicalDriftEvaluator` lives in
   `src/helios_v2/evaluation/r82_drift.py` and is a sibling of
   `src/helios_v2/evaluation/engine.py` (no merging).
4. The P5 launch-gate function `is_p5_launch_gate_open` is exported
   from `src/helios_v2/evaluation/r82_drift.py`.
5. R21 ad-hoc logging guard remains green.
6. Composition owner-boundary guard remains green.

## 6. Impacted Modules

- `src/helios_v2/evaluation/contracts.py`: add `BehaviorDriftDimension`
  Literal (17 strings).
- `src/helios_v2/evaluation/__init__.py`: export
  `BehaviorDriftDimension`, `AggressiveRadicalDriftEvaluator`,
  `DriftEvaluationResult`, `DriftEvaluationReport`,
  `is_p5_launch_gate_open`.
- `src/helios_v2/evaluation/r82_drift.py` (new): the evaluator
  implementation.
- `src/helios_v2/tests/r79d/cli.py`: add `--with-drift-report` flag.
- `docs/ARCHITECTURE_BOUNDARIES.md`: add §10.d P5 launch-gate entry
  citing `is_p5_launch_gate_open`.
- `docs/OWNER_GUIDE.md`: add §3.8.3 R82 entry.
- `docs/PROGRESS_FLOW.zh-CN.md`: add R82 module-index block.
- `docs/requirements/index.md`: add R82 row.
- `tests/test_r82_drift_evaluator.py` (new): 17 unit tests (one per
  dim) + 4 family-aggregate tests + 1 launch-gate test + 1
  recalibration-recommendation test.

## 7. Acceptance Criteria

### 7.1 Implementation acceptance (commit `TBD`)

1. `BehaviorDriftDimension` Literal declared in
   `src/helios_v2/evaluation/contracts.py` with exactly 17 entries in
   the prescribed family order.
2. `AggressiveRadicalDriftEvaluator` produces a
   `DriftEvaluationReport` for any R79-D framework JSONL in < 1s (52
   ticks) / < 5s (200 ticks).
3. `is_p5_launch_gate_open(0.02)` returns `True`; `is_p5_launch_gate_open(0.019)`
   returns `False`. Threshold is the single source of truth for the
   P5 launch gate.
4. R81 re-calibration recommendation (`raise_weight` /
   `lower_weight` / `hold` / `n/a`) is emitted in the
   `DriftEvaluationResult` for the 17 dims.
5. `tests/r79d/cli.py` `run` subcommand accepts `--with-drift-report`
   and writes `drift_report.md` next to the JSONL output.

### 7.2 Test acceptance

1. 17 unit tests in `tests/test_r82_drift_evaluator.py` (one per dim)
   + 4 family-aggregate tests + 1 launch-gate test + 1
   recalibration-recommendation test = 23 tests, all PASS.
2. Full suite: previous R81 baseline 922 + 23 R82 = 945 passed, 0
   regression.
3. R21 ad-hoc logging guard: 1/1 PASS.
4. Composition owner-boundary guard: 4/4 PASS.
5. R79-D framework end-to-end smoke: re-run a 10-tick A_praise
   scenario with `--with-drift-report` and confirm
   `drift_report.md` is produced; open the file and confirm the
   markdown table renders without errors.

### 7.3 P5 launch-gate acceptance

1. `docs/ARCHITECTURE_BOUNDARIES.md` §10.d cites
   `is_p5_launch_gate_open` as the canonical P5 launch gate.
2. `tests/test_r82_p5_launch_gate.py` (new, 3 tests) verifies:
   - `is_p5_launch_gate_open` threshold is exactly `0.02`
   - a future P5 R must call this function before mutating `04`
     sensitivity coefficients (verified by code review of
     `src/helios_v2/neuromodulation/`)
   - the launch-gate function is exported from
     `helios_v2.evaluation.r82_drift`
3. The R79 plan is closed: R79-A, R79-B, R79-C, R79-D, R80, R81,
   R82 are all delivered.

## 8. Out of Scope (defer to R83+)

- A 10-minute pre-run test harness (R83 will own this; the user has
  confirmed the scope).
- A multi-scenario drift aggregator (e.g. averaging drift reports
  across 4 scenarios) — R82 ships per-scenario reports only.
- A scenario-level AI-judge evaluation of "did this persona sound
  human?" (this is the R83 Turing-test-style evaluation; out of
  scope for R82).
- Cross-persona drift comparison (R82 reports per persona per
  scenario, not "persona A vs persona B").
