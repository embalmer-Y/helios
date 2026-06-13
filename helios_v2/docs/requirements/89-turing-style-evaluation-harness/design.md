# Requirement 89 - Long-Run Turing-Style Evaluation Harness

## 1. Design Overview

Add a tests-only package `tests/r89_turing_harness/` with a reusable harness (`turing_harness.py`)
and a verification module (`test_r89_turing_harness.py`). The harness consumes an R83 `LongRunReport`
and an R88 `DriftReport`, scores the six §13.4 rubric axes (reconstructing the internal axes from real
runtime provenance in those two reports, accepting injected human/LLM-judge scores for the behavior
axes, stubbing `memory_fidelity`), applies the locked conservative aggregation, and returns a
`TuringVerdict` without asserting or logging. It reuses `r83_long_runner` and `r88_drift_evaluator`.
No runtime code changes.

## 2. Current State and Gap

1. R83 `run_long_run` returns a `LongRunReport` with `field_stats[name]` (`minimum`/`maximum`/
   `observations`/`ok`), `completed_all`, `crash`, `ticks_completed`/`ticks_requested`, and a JSONL
   trace; `TRACKED_FIELD_BOUNDS` declares the 19 owner dimensions.
2. R88 `evaluate_drift` returns a `DriftReport` with per-dimension `DimensionDrift`
   (`drift_class`/`divergence`/`samples`) and the expected-dimension set.
3. There is no harness combining these into the §13.4 six-axis Turing-style verdict, no reconstruction
   of the internal axes from provenance, and no enforcement of the anti-theatrical aggregation.

## 3. Target Architecture

### 3.1 `turing_harness.py`

- Axis constants and dimension membership:
  - BEHAVIOR axes: `LINGUISTIC_NATURALNESS`, `STIMULUS_RESPONSE_COHERENCE`.
  - INTERNAL axes: `BIO_RESPONSIVENESS`, `MEMORY_FIDELITY`, `AGENCY_LOCKING`, `CROSS_TICK_CONTINUITY`.
  - `DIMENSION_BEHAVIOR = "behavior"`, `DIMENSION_INTERNAL = "internal"`.
- Availability constants: `AVAILABLE`, `STUBBED` (`"stubbed_pending_real_probe"`),
  `UNAVAILABLE` (`"unavailable_needs_real_afferent"`).
- Judge-track constants: `RECONSTRUCTED`, `LLM_JUDGE`, `HUMAN`.
- `InjectedAxisScore(score, provenance, judge_track=LLM_JUDGE)` - a caller-supplied judge score for
  one axis (models the §13.4 dual judge track).
- `TuringConfig(pass_threshold=0.80, axis_collapse_threshold=0.50, lower_quantile=0.25,
  memory_fidelity_stub=0.5, movement_epsilon=1e-3, affect_prefixes=("04", "05"))`.
- `AxisScore(frozen)` - `axis`, `dimension`, `score`, `availability`, `judge_track`, `provenance`.
- `TuringVerdict` - `axis_scores: dict[str, AxisScore]`, `behavior_dimension_score: float | None`,
  `internal_dimension_score: float | None`, `aggregate: float | None`, `completeness: str`
  (`"complete"` / `"incomplete"`), `collapsed_axes: tuple[str, ...]`, `unavailable_axes`,
  `stubbed_axes`, `reason: str | None`, derived `passes`, `violations()`, `summary()`.
- `evaluate_turing(long_run_report, drift_report, config=TuringConfig(), injected_scores=None)
  -> TuringVerdict`.

### 3.2 Axis scoring

1. For each axis, the resolver order is: an injected score (overrides), else the axis's reconstructed
   scorer (internal axes), else `UNAVAILABLE` (behavior axes with no injection), with `MEMORY_FIDELITY`
   defaulting to `STUBBED` at `memory_fidelity_stub`.
2. Injected score: `availability = AVAILABLE`, `judge_track` from the injection; if its provenance is
   empty/blank, the score is forced to `0.0` (evidence anchoring).
3. `bio_responsiveness` (internal, reconstructed):
   - affect dims = expected dims whose prefix is in `affect_prefixes` (the `04.*`/`05.*` set).
   - `health` = fraction of affect dims that are in the drift report, not `dim_unavailable`, and not
     divergent.
   - `movement` = fraction of affect dims whose R83 `field_stats[name].maximum - minimum >
     movement_epsilon` (the affect actually evolved over the run).
   - `score = 0.5 * health + 0.5 * movement`; provenance names the drift report + field stats.
4. `cross_tick_continuity` (internal, reconstructed):
   - `completion` = `1.0` if `long_run_report.completed_all` else `0.0`.
   - `continuity_tracked` = `1.0` if `09.continuation_level` is present and not `dim_unavailable` and
     bounded (`field_stats["09.continuation_level"].ok`) else `0.0`.
   - `affect_carry` = `1.0` if any affect dim moved over the run (reuses the movement check) else
     `0.0`.
   - `score = mean(completion, continuity_tracked, affect_carry)`; provenance.
5. `agency_locking` (internal, reconstructed proxy):
   - `score` = fraction of the expected owner dims that are present, classifiable (not
     `dim_unavailable`), and non-divergent (real bounded owner state every tick). Documented as a
     partial proxy; full agency-locking via owner-decision provenance (`21`/`17`) is deferred.
6. `memory_fidelity` (internal): `STUBBED`, `score = memory_fidelity_stub`,
   `provenance = "stub_pending_R90"`; excluded from the dimension aggregate and forces `incomplete`.
7. `linguistic_naturalness` / `stimulus_response_coherence` (behavior): `UNAVAILABLE` unless injected;
   provenance names the missing real afferent + judge.

### 3.3 Conservative aggregation (locked, §13.4)

1. For each dimension, collect the `AVAILABLE` axis scores; the dimension score is the nearest-rank
   lower quantile (`lower_quantile`, default `0.25`) of the sorted available scores (risk-averse; for
   small n this approaches the minimum). A dimension with no available axis has score `None`.
2. `aggregate = min(behavior_dimension_score, internal_dimension_score)` only when both are not
   `None`, else `None`.
3. `collapsed_axes` = available axes scoring `< axis_collapse_threshold`.
4. `completeness = "complete"` iff every axis is `AVAILABLE` (no stubbed/unavailable), else
   `"incomplete"`.
5. `passes` (derived) = `completeness == "complete"` and `aggregate is not None` and
   `aggregate >= pass_threshold` and not `collapsed_axes`.
6. A `None`/empty report input sets `reason` and yields `passes == False`.

### 3.3 `test_r89_turing_harness.py`

- Integration: run a short R83 long run (reuse R83's deterministic-gateway production-shaped assembly),
  `evaluate_drift` over its JSONL samples, then `evaluate_turing(long_run_report, drift_report)`;
  assert the internal axes are `AVAILABLE` with provenance, `memory_fidelity` `STUBBED`, behavior axes
  `UNAVAILABLE`, verdict `incomplete` and not passing; render `summary()`.
- Synthetic: a fully-injected high-score run passes; an injected sub-collapse axis fails; an injected
  empty-provenance axis scores 0 and fails; internal-only injection leaves behavior unscored and not
  passing; the dual-dimension `min` aggregation is asserted.
- Robustness: an empty/degenerate report yields a non-passing verdict with a reason, no exception.

## 4. Data Structures

`InjectedAxisScore`, `TuringConfig`, `AxisScore`, `TuringVerdict`, the axis/dimension/availability/
judge-track constants (all tests-only). No runtime contract changes. Reuses R83/R88 types.

## 5. Module Changes

1. New `tests/r89_turing_harness/__init__.py` (exports; ensures `tests/` on `sys.path` for the R83/R88
   sibling imports, mirroring those packages).
2. New `tests/r89_turing_harness/turing_harness.py`.
3. New `tests/r89_turing_harness/test_r89_turing_harness.py`.
4. Docs: `requirements/index.md` row 89; `ROADMAP.zh-CN.md` R89 delivered.

## 6. Migration Plan

1. Tests-only and additive; no runtime/owner code is touched.
2. The harness layers strictly on the R83 and R88 report types (its stated dependencies); the test
   drives the real R83→R88→R89 pipeline with the existing deterministic offline gateway.
3. The behavior axes and `memory_fidelity` are explicit deferral seams: R90 supplies the real
   `memory_fidelity` probe; P4 real afferents + real judges supply the behavior axes.

## 7. Failure Modes and Constraints

1. The offline baseline can never pass (behavior dimension unavailable + `memory_fidelity` stubbed →
   `incomplete`); this is the intended anti-theatrical result, asserted by a test.
2. An `available` axis with empty provenance scores `0.0` (evidence anchoring).
3. A single dimension cannot produce an aggregate (both-dimension rule).
4. A degenerate/empty report yields a recorded `reason` and a non-passing verdict, no exception.
5. No `print`/`logging`; no owner-internal imports.

## 8. Observability and Logging

No new logging mechanism and no `print`/`logging` in the harness. The integration test renders
`summary()` via `print` (allowed in tests, not in `src/`) so the per-axis readout and the honest
incompleteness appear in the CI log.

## 9. Validation Strategy

1. CI: `pytest helios_v2/tests/r89_turing_harness -q` - the real short-run integration (internal axes
   reconstructed + provenance, behavior axes unavailable, verdict incomplete/not-passing), the
   synthetic pass/fail/aggregation cases, and the robustness case all pass.
2. Falsifiable: the collapse, missing-provenance, single-dimension, and stubbed-axis cases each fail
   `passes`; the offline baseline is provably not-passing.
3. Regression: the full network-free suite stays green; no runtime/owner code changed.
