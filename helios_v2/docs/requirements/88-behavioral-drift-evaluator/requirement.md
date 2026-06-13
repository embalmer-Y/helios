# Requirement 88 - Behavioral Drift Evaluator over the Long-Run Trace

## 1. Background and Problem

R83 closed the G0/G1 foundation gates and, as a deliberate substrate for later evaluation, made the
long-run harness stream one JSON object per sampled tick to an opt-in `jsonl_path`. Each line carries
`tick`, `tick_duration_ms`, `store_count`, `memory_mb`, and the tracked owner fields: the `04`
neuromodulator levels (9 channels), the `05` interoceptive feeling (7 dimensions), the `09`
`gate_score` and `continuation_level`, and the `18` `outward_drive` - 19 owner dimensions in total.
Committed baseline traces already exist under `helios_v2/logs/r83/` (`semantic_600.jsonl`,
`scale_2000.jsonl`, `scale_100k.jsonl`).

R83 verifies that every tracked field stays bounded / finite / non-NaN over the run (G1
boundedness). It does NOT report the DIRECTION of cross-tick movement: whether a dimension ramped up,
ramped down, or settled to a plateau over the horizon, nor whether it drifted toward a legal bound.
The committed `semantic_600.jsonl` shows the affect dimensions ramp during a ~12-sample warm-up and
then freeze to a fixed point; today nothing classifies or asserts on that behavior.

P5 (the learning loop) will deliberately change owner dynamics (learnable `04`/`05`/`09`/`18`
coefficients), so before P5 starts the project needs a falsifiable, read-only baseline drift readout:
a way to classify each owner dimension's long-horizon movement and catch pathological runaway drift,
so a later learning change can be measured against this baseline rather than judged by inspection.

ROADMAP reconciliation: the ROADMAP §4 sketch of R88 ("4 hormone + 4 feeling + 4 salience + 5
behavior = 17 dims") is a beta-branch-derived framing and does not match main's real R83 substrate.
Main's trace carries 19 owner dimensions across `04`/`05`/`09`/`18` and NO `03` salience. R88 is
grounded in what the trace actually emits today; adding `03` salience to the trace is a possible
future R83-trace extension, explicitly out of R88 scope.

## 2. Goal

Add a read-only, deterministic, network-free behavioral-drift evaluator that consumes an R83 long-run
JSONL trace and classifies each owner dimension's long-horizon drift as `drift_positive`,
`drift_negative`, `drift_neutral`, or `dim_unavailable`, computed from an early-window-vs-late-window
comparison with an explicit deadband, additionally flags a dimension whose drift saturates toward a
legal bound (divergent), and emits a structured drift report with a falsifiable analysis verdict -
validated against committed baseline traces and synthetic fixtures.

## 3. Functional Requirements

### 3.1 Reusable evaluator

1. A tests-only evaluator module (`tests/r88_drift_evaluator/`) must expose `evaluate_drift(samples,
   config)` that consumes an iterable of already-parsed per-tick sample mappings (the R83 JSONL line
   shape) and returns a structured `DriftReport`. It must assert nothing itself; the verdict lives on
   the report.
2. The evaluator must be read-only and offline: it must touch no runtime, mutate no state, perform no
   network or model call, and emit no `print`/`logging` (R21 discipline). A consuming test may render
   the report.
3. The module must also expose `load_samples(path)` (parse a JSONL file into sample dicts) and
   `evaluate_trace_file(path, config)` (load + evaluate) so it can run directly against the committed
   `helios_v2/logs/r83/*.jsonl` traces.
4. The evaluator must discover owner dimensions dynamically: any sample key matching the `NN.field`
   owner-dimension pattern (a two-digit owner prefix, a dot, then the field) is a tracked dimension;
   the meta keys (`tick`, `tick_duration_ms`, `store_count`, `memory_mb`) are excluded.

### 3.2 Drift classification

1. For each discovered dimension the evaluator must compute, over the dimension's observed values in
   tick order: the sample count, the early-window mean, the late-window mean, the signed
   `delta = late_mean - early_mean`, a `normalized_delta` (delta divided by the dimension's legal
   range), the observed min/max, and the late-window spread.
2. The early window is the first `window_fraction` of samples and the late window is the last
   `window_fraction` (default `0.25` each, each window at least one sample); when there are too few
   samples to form two non-overlapping windows, the early window is the first sample and the late
   window is the last sample.
3. Each dimension must be classified by `normalized_delta` against a deadband `neutral_band` (default
   `0.02`): `|normalized_delta| <= neutral_band` is `drift_neutral`; `normalized_delta > neutral_band`
   is `drift_positive`; `normalized_delta < -neutral_band` is `drift_negative`.
4. `drift_positive` / `drift_negative` denote only the SIGN of the cross-window change, not a quality
   or value judgment (a rising cortisol is `drift_positive`, not "good"). This neutrality must be
   stated in the report contract.
5. A dimension present in zero samples, or with fewer than `min_samples_for_trend` (default `4`)
   observations, must be classified `dim_unavailable` (a trend cannot be computed honestly), never
   silently treated as neutral.
6. The evaluator must additionally compute a `divergent` fact per dimension: a `drift_positive`
   dimension whose late-window mean is within `saturation_margin` (default `0.02` of the legal range)
   of its legal maximum is `divergent_high`; a `drift_negative` dimension whose late-window mean is
   within `saturation_margin` of its legal minimum is `divergent_low`. A dimension's legal range comes
   from the shared R83 `TRACKED_FIELD_BOUNDS`; a dimension with no known bounds uses observed min/max
   for normalization and is never flagged divergent.

### 3.3 Drift report

1. The `DriftReport` must expose: the per-dimension `DimensionDrift` records, the per-class counts
   (`drift_positive` / `drift_negative` / `drift_neutral` / `dim_unavailable`), the total sample count,
   the set of expected owner dimensions, the missing expected dimensions, the divergent dimensions, an
   explicit `analysis_ok`, a `violations()` list, and a human-readable `summary()`.
2. `analysis_ok` must be `True` only when the trace parsed into at least `min_samples_for_trend`
   samples, every expected owner dimension (default: the R83 `TRACKED_FIELD_BOUNDS` set) is present and
   classifiable (no unexpected `dim_unavailable`), and no dimension is flagged divergent.
3. The expected-dimension set must be configurable; when not supplied it defaults to the shared R83
   tracked set so a vanilla R83 trace is fully checked.

## 4. Non-Functional Requirements

1. Performance: evaluation is a single linear pass over the samples; it must stay fast enough to run a
   committed baseline trace (tens to a few hundred samples) inside the default test suite.
2. Reliability: a malformed or empty trace must produce an explicit `analysis_ok = False` report with a
   recorded reason, never an exception escaping the evaluator on routine bad input; a non-numeric or
   missing field value for a tick contributes no observation for that dimension on that tick.
3. Observability and logging: no `print`/`logging` in the evaluator (only tests render); `21` stays the
   single runtime logging mechanism. The evaluator consumes only the public JSONL sample shape.
4. Compatibility and migration: tests-only addition; no runtime/owner code changes; the full
   network-free suite stays green.

## 5. Code Behavior Constraints

1. Forbidden: the evaluator importing owner internals, touching the runtime, or using
   `print`/`logging`.
2. Forbidden: classifying a dimension with insufficient samples as `drift_neutral`; insufficient data
   is `dim_unavailable` (honest absence, not a fabricated stable reading).
3. Forbidden: ascribing a good/bad valence to `drift_positive`/`drift_negative`; the classes are
   direction-only.
4. The evaluator must be deterministic: the same samples and config always yield identical
   classifications, with an explicit, documented tie-break for the neutral deadband boundary.

## 6. Impacted Modules

1. `helios_v2/tests/r88_drift_evaluator/__init__.py`, `drift_evaluator.py` (the evaluator),
   `test_r88_drift_evaluator.py` (synthetic fixtures + committed-baseline-trace checks).
2. Reuses `r83_long_runner.TRACKED_FIELD_BOUNDS` as the shared legal-range / expected-dimension source.
3. Docs: `requirements/index.md` (row 88); `ROADMAP.zh-CN.md` (move R88 from queue to delivered).
   `PROGRESS_FLOW.*` and `OWNER_GUIDE.*` unchanged (no owner maturity, stage-chain, or boundary
   change - this is a tests-only diagnostic harness, mirroring R83).

## 7. Acceptance Criteria

1. `evaluate_drift(samples, config)` returns a `DriftReport` whose per-dimension classification matches
   the early-vs-late deadband rule on synthetic fixtures: a monotonically rising dimension is
   `drift_positive`, a falling one `drift_negative`, a flat one `drift_neutral`, and a missing or
   sparse one `dim_unavailable`.
2. A dimension that rises into the top `saturation_margin` of its legal range is flagged
   `divergent_high` and fails the report's `analysis_ok`; a symmetric low case is `divergent_low`.
3. `evaluate_trace_file` run against the committed `helios_v2/logs/r83/semantic_600.jsonl` parses all
   50 samples and finds all 19 expected owner dimensions (zero unexpected `dim_unavailable`). Because
   this run reaches a fixed point within its first sampled tick and stays frozen for the rest of the
   horizon, every dimension's early-vs-late normalized delta falls inside the deadband, so all 19
   dimensions classify `drift_neutral` (a settled run), no dimension is flagged divergent, and the
   report yields `analysis_ok = True`. (Direction classes `drift_positive`/`drift_negative` are
   exercised on synthetic fixtures, since the committed deterministic baseline is settled.)
4. A malformed/empty trace yields `analysis_ok = False` with a recorded reason and no escaping
   exception.
5. No runtime/owner code changed; the full network-free suite is green; `index.md` has a row 88 and the
   ROADMAP shows R88 delivered.
