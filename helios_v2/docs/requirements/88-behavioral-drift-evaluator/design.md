# Requirement 88 - Behavioral Drift Evaluator over the Long-Run Trace

## 1. Design Overview

Add a tests-only package `tests/r88_drift_evaluator/` with a reusable evaluator (`drift_evaluator.py`)
and a verification module (`test_r88_drift_evaluator.py`). The evaluator consumes an iterable of
already-parsed R83 JSONL sample mappings (or a JSONL file via `load_samples` / `evaluate_trace_file`),
runs a single linear pass to build per-dimension running observations in tick order, classifies each
owner dimension's early-window-vs-late-window drift, flags saturation-toward-bound divergence, and
returns a `DriftReport` without asserting or logging. It reuses `r83_long_runner.TRACKED_FIELD_BOUNDS`
as the shared legal-range and expected-dimension source. No runtime code changes.

## 2. Current State and Gap

1. R83's `long_runner.py` streams one JSON object per sampled tick to `jsonl_path` with meta keys
   (`tick`, `tick_duration_ms`, `store_count`, `memory_mb`) plus the 19 owner dimensions
   (`04.*` x9, `05.*` x7, `09.gate_score`, `09.continuation_level`, `18.outward_drive`).
2. `TRACKED_FIELD_BOUNDS` already declares each owner dimension's legal range (`[0,1]` for `04`/`05`
   and the two `09` fields; `[0, 8.0]` divergence ceiling for `18.outward_drive`).
3. Committed baseline traces exist: `logs/r83/semantic_600.jsonl` (50 samples, affect ramps then
   plateaus), `logs/r83/scale_2000.jsonl`, `logs/r83/scale_100k.jsonl`.
4. R83 checks boundedness but reports no drift DIRECTION and no saturation-toward-bound signal; there
   is no offline classifier of long-horizon owner movement.

## 3. Target Architecture

### 3.1 `drift_evaluator.py`

- `DriftClass` - a string enum / `Final` constants: `DRIFT_POSITIVE = "drift_positive"`,
  `DRIFT_NEGATIVE = "drift_negative"`, `DRIFT_NEUTRAL = "drift_neutral"`,
  `DIM_UNAVAILABLE = "dim_unavailable"`.
- `DivergenceFlag` - `"none"`, `"divergent_high"`, `"divergent_low"`.
- `_META_KEYS = {"tick", "tick_duration_ms", "store_count", "memory_mb"}` and a
  `_OWNER_DIM_PATTERN = re.compile(r"^\d\d\..+")` so dimension discovery is mechanical and
  trace-driven.
- `DriftConfig(window_fraction=0.25, neutral_band=0.02, min_samples_for_trend=4,
  saturation_margin=0.02, expected_dimensions=None, dimension_bounds=None)`. When
  `expected_dimensions` / `dimension_bounds` are `None` they default to the keys / values of
  `r83_long_runner.TRACKED_FIELD_BOUNDS`.
- `DimensionDrift` (frozen) - `name`, `owner` (the `NN` prefix), `samples`, `early_mean`,
  `late_mean`, `delta`, `normalized_delta`, `minimum`, `maximum`, `late_spread`, `drift_class`,
  `divergence`. Helpers compute none of this lazily; `evaluate_drift` fills it.
- `DriftReport` (frozen-ish dataclass) - `source: str`, `total_samples: int`,
  `dimensions: dict[str, DimensionDrift]`, `expected_dimensions: frozenset[str]`,
  `missing_dimensions: tuple[str, ...]`, `class_counts: dict[str, int]`,
  `divergent_dimensions: tuple[str, ...]`, `parse_reason: str | None` (set when the trace was
  empty/malformed), with derived `analysis_ok`, `violations()`, `summary()`.
- `load_samples(path) -> list[dict]` - read a JSONL file, JSON-decode each non-blank line, skip
  (and count) un-decodable lines defensively.
- `evaluate_drift(samples, config=DriftConfig()) -> DriftReport` - the core pass (below).
- `evaluate_trace_file(path, config=DriftConfig()) -> DriftReport` - `load_samples` then
  `evaluate_drift`, with `source=path`.

### 3.2 Evaluation pass

1. Materialize `samples` into a list preserving order (the JSONL is already tick-ordered; the
   evaluator does not re-sort, matching the R83 sampling order, and is documented as order-preserving).
2. If the list is empty -> return a `DriftReport` with `parse_reason="empty_trace"`, all expected
   dimensions `dim_unavailable`, `analysis_ok=False`.
3. First pass: for each sample, for each key matching `_OWNER_DIM_PATTERN` and not in `_META_KEYS`,
   append the float value to `observations[key]` when it is a real finite number (a missing /
   non-numeric / NaN / inf value contributes nothing for that tick).
4. The discovered dimension set is `keys(observations) | expected_dimensions` (so an expected
   dimension absent from the trace still appears, as `dim_unavailable`).
5. For each dimension compute the `DimensionDrift`:
   - if `len(values) < min_samples_for_trend` -> `drift_class = DIM_UNAVAILABLE`, `divergence="none"`,
     means/delta `0.0`, samples recorded.
   - else split: `w = max(1, floor(len*window_fraction))`; `early = values[:w]`, `late = values[-w:]`
     (windows may overlap only in the degenerate tiny-sample case, which `min_samples_for_trend>=4`
     plus `window_fraction<=0.25` prevents for the normal path; documented).
   - `early_mean = mean(early)`, `late_mean = mean(late)`, `delta = late_mean - early_mean`.
   - legal range `rng = high - low` from `dimension_bounds[name]` if known else
     `max(values) - min(values)`; `normalized_delta = delta / rng` when `rng > 0` else `0.0`.
   - classify: `|normalized_delta| <= neutral_band` -> neutral (the boundary `==` is neutral, the
     documented tie-break); `> neutral_band` -> positive; `< -neutral_band` -> negative.
   - divergence (only when bounds known and class is directional): positive and
     `late_mean >= high - saturation_margin*rng` -> `divergent_high`; negative and
     `late_mean <= low + saturation_margin*rng` -> `divergent_low`; else `none`.
   - `late_spread = max(late) - min(late)`.
6. Build `class_counts`, `missing_dimensions` (expected but `dim_unavailable` because absent or
   sparse), `divergent_dimensions` (divergence != none).
7. `analysis_ok = parse_reason is None and total_samples >= min_samples_for_trend and not
   missing_expected and not divergent_dimensions`, where `missing_expected` is any expected dimension
   classified `dim_unavailable`.

### 3.3 `test_r88_drift_evaluator.py`

- Synthetic-fixture tests: build sample lists with a known rising / falling / flat / missing / sparse
  dimension and assert the four classes, the deadband boundary (a delta exactly at `neutral_band` is
  neutral), and `divergent_high`/`divergent_low` (a dimension ramped into the top/bottom
  `saturation_margin`).
- Committed-trace test: `evaluate_trace_file(REPO/logs/r83/semantic_600.jsonl)` - assert 50 samples,
  all 19 expected dims present, zero unexpected `dim_unavailable`, every dimension `drift_neutral`
  (this deterministic run settles to a fixed point within its first sampled tick, so early-vs-late
  deltas are inside the deadband), no divergence, `analysis_ok` True. Renders `summary()` via `print`
  (test-only). The direction classes are exercised on the synthetic fixtures, not this settled trace.
- Robustness tests: empty trace and a malformed-line file -> `analysis_ok False` with a recorded
  reason, no exception.

## 4. Data Structures

`DriftClass`/`DivergenceFlag` constants, `DriftConfig`, `DimensionDrift`, `DriftReport` (all
tests-only). No runtime contract changes. Reuses `r83_long_runner.TRACKED_FIELD_BOUNDS`.

## 5. Module Changes

1. New `tests/r88_drift_evaluator/__init__.py` (exports the evaluator symbols; ensures `tests/` is on
   `sys.path` so `from r83_long_runner import TRACKED_FIELD_BOUNDS` resolves, mirroring R83's package).
2. New `tests/r88_drift_evaluator/drift_evaluator.py`.
3. New `tests/r88_drift_evaluator/test_r88_drift_evaluator.py`.
4. Docs: `requirements/index.md` row 88; `ROADMAP.zh-CN.md` R88 delivered.

## 6. Migration Plan

1. Tests-only and additive; no runtime/owner code is touched.
2. The committed baseline traces under `logs/r83/` are the real-data fixtures; the path is resolved
   relative to the repo so the test is location-stable.
3. The evaluator depends on `r83_long_runner` for `TRACKED_FIELD_BOUNDS` only; if that import is
   unavailable the config can be passed explicit bounds (the dependency is a default, not a hard
   coupling).

## 7. Failure Modes and Constraints

1. Empty trace -> `parse_reason="empty_trace"`, `analysis_ok=False`.
2. Malformed JSONL lines are skipped and counted (`parse_reason="malformed_lines:<n>"` when any are
   skipped and no valid samples remain; otherwise the valid samples are evaluated and the skip is
   recorded in the reason without forcing failure if enough valid samples exist).
3. A dimension with `< min_samples_for_trend` real observations is `dim_unavailable`, never neutral.
4. A dimension with unknown bounds normalizes by observed range and is never flagged divergent (no
   false runaway claim without a legal range).
5. `18.outward_drive` uses its `[0, 8.0]` divergence ceiling, so its normalized delta and divergence
   are scaled correctly (a 1.3 -> 1.7 move is a small normalized delta, not a false positive).
6. No `print`/`logging` in the evaluator; no owner-internal imports.

## 8. Observability and Logging

No new logging mechanism and no `print`/`logging` in the evaluator. The committed-trace test renders
`summary()` via `print` (allowed in tests, not in `src/`) so the drift readout appears in the CI log.

## 9. Validation Strategy

1. CI: `pytest helios_v2/tests/r88_drift_evaluator -q` - synthetic-fixture classification, deadband
   boundary, divergence flags, the committed `semantic_600.jsonl` real-data assertions, and the
   malformed/empty robustness cases all pass.
2. Falsifiable: the classification fails the synthetic assertions if the early-vs-late deadband rule
   regresses; the divergence flag fails `analysis_ok` on a saturated dimension; a missing expected
   dimension fails `analysis_ok`.
3. Regression: the full network-free suite stays green; no runtime/owner code changed.
4. Optional manual: `evaluate_trace_file` against `scale_100k.jsonl` for a long-horizon readout.
