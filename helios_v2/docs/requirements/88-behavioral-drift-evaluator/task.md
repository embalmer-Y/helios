# Requirement 88 - Behavioral Drift Evaluator over the Long-Run Trace

## 1. Task Breakdown

### T1 - Evaluator package skeleton and dimension discovery
- Create `tests/r88_drift_evaluator/__init__.py` and `drift_evaluator.py`.
- Define `DriftClass`/`DivergenceFlag` constants, `_META_KEYS`, `_OWNER_DIM_PATTERN`.
- Define `DriftConfig` defaulting `expected_dimensions`/`dimension_bounds` from
  `r83_long_runner.TRACKED_FIELD_BOUNDS`.
- Implement `load_samples(path)` (JSONL parse, defensive skip of bad lines).

### T2 - Drift classification core
- Define `DimensionDrift` and `DriftReport` dataclasses with derived `analysis_ok` / `violations()` /
  `summary()`.
- Implement `evaluate_drift(samples, config)`: order-preserving materialize, empty-trace guard,
  per-dimension observation collection (finite-number guard), early/late window split, mean/delta/
  normalized-delta, deadband classification, saturation-toward-bound divergence, class counts,
  missing/divergent sets, `analysis_ok`.
- Implement `evaluate_trace_file(path, config)`.

### T3 - Tests: synthetic fixtures
- Rising -> `drift_positive`; falling -> `drift_negative`; flat -> `drift_neutral`; absent -> and
  sparse (< `min_samples_for_trend`) -> `dim_unavailable`.
- Deadband boundary: a normalized delta exactly at `neutral_band` classifies neutral.
- Divergence: a dimension ramped into the top `saturation_margin` -> `divergent_high` and
  `analysis_ok=False`; symmetric `divergent_low`.

### T4 - Tests: committed baseline trace + robustness
- `evaluate_trace_file(logs/r83/semantic_600.jsonl)`: 50 samples, 19 expected dims present, zero
  unexpected `dim_unavailable`, every dimension `drift_neutral` (the run settles to a fixed point
  within its first sampled tick, so early-vs-late deltas are inside the deadband), no divergence,
  `analysis_ok=True`; render `summary()`.
- Empty trace and malformed-line file -> `analysis_ok=False` with a recorded reason, no exception.

### T5 - Docs sync
- `requirements/index.md`: add row 88 (`baseline_implementation`).
- `ROADMAP.zh-CN.md`: move R88 from the P5 queue to delivered, with the ROADMAP-vs-real-substrate
  reconciliation note (19 owner dims, no `03` salience).

## 2. Dependencies

1. R83 (`tests/r83_long_runner/`): supplies the JSONL trace shape and `TRACKED_FIELD_BOUNDS`, and the
   committed baseline traces under `logs/r83/`.
2. No runtime/owner dependency; offline and network-free.

## 3. Files and Modules

1. `helios_v2/tests/r88_drift_evaluator/__init__.py` (new).
2. `helios_v2/tests/r88_drift_evaluator/drift_evaluator.py` (new).
3. `helios_v2/tests/r88_drift_evaluator/test_r88_drift_evaluator.py` (new).
4. `helios_v2/docs/requirements/index.md` (row 88).
5. `helios_v2/docs/ROADMAP.zh-CN.md` (R88 delivered).

## 4. Implementation Order

1. T1 evaluator skeleton + `load_samples`.
2. T2 classification core + report.
3. T3 synthetic fixture tests.
4. T4 committed-trace + robustness tests.
5. T5 docs sync.

## 5. Validation Plan

1. First narrow check: `pytest helios_v2/tests/r88_drift_evaluator -q` (set
   `PYTHONPATH=helios_v2/src`).
2. Falsifiability: the divergence/missing-dimension cases fail `analysis_ok`; the deadband regression
   fails the synthetic classification assertions.
3. Regression: `pytest helios_v2/tests -q` stays green; no runtime/owner code changed.

## 6. Completion Criteria

1. `evaluate_drift` / `evaluate_trace_file` classify each owner dimension per the early-vs-late
   deadband rule and flag saturation-toward-bound divergence, deterministically.
2. The committed `semantic_600.jsonl` real-data test passes with all 19 dims present, the documented
   plateau/warm-up classifications, no divergence, and `analysis_ok=True`.
3. Empty/malformed traces yield `analysis_ok=False` with a reason and no exception.
4. The full network-free suite is green; `index.md` row 88 and the ROADMAP delivered note are in place.
