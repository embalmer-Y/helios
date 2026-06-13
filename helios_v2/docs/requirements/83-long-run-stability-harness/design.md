# Requirement 83 - Long-Run Stability and Owner-Boundedness Harness

## 1. Design Overview

Add a tests-only package `tests/r83_long_runner/` with a reusable harness (`long_runner.py`) and a
three-tier verification module (`test_r83_long_run.py`). The harness drives an already-started
`RuntimeHandle` for N ticks, captures per-owner bounded facts and crash/memory facts into a
`LongRunReport`, and returns it without asserting or logging. The CI-tier test builds the R82
production-shaped assembly (`assemble_production_runtime`) with a deterministic fake LLM gateway and
runs the locked tick count network-free; the production-scale and real-LLM tiers are env-gated. No
runtime code changes.

## 2. Current State and Gap

1. The runtime exposes `RuntimeHandle.tick()` / `run_ticks(n)` and per-tick `RuntimeTickResult` with
   `stage_results` carrying each owner's published result (04 `state.levels`, 05 `state.feeling`, 09
   `result.gate_score` + `continuation_state.level`, 18 `result.drive_state.pressure_components`).
2. R82's `assemble_production_runtime(data_dir, gateway)` yields a durable, semantic, checkpointed
   runtime that runs offline when given a ready fake gateway and the offline hash embedding.
3. There is no harness that runs many ticks and produces a boundedness/stability verdict; R76/R77 are
   20-tick prerequisite checks, R71 is throughput.

## 3. Target Architecture

### 3.1 `long_runner.py`

- `TRACKED_FIELD_BOUNDS: dict[str, (low, high)]` - the 9 `04` channels and 7 `05` dimensions and the
  two `09` fields at `[0,1]`; `18.outward_drive` at `[0, 8.0]` (a divergence ceiling, not a unit
  interval, because the drive crosses an action threshold ~1.6).
- `FieldStat` - running stats for one field: observations, min, max, last, nan_count,
  nonfinite_count, out_of_range_count (with a `_RANGE_EPSILON` tolerance for a clamped edge value);
  `ok` iff no NaN / non-finite / out-of-range.
- `LongRunConfig(ticks, sample_every=0, memory_ceiling_mb=500.0)`; `resolved_sample_every()` defaults
  to ~50 evenly-spaced samples.
- `LongRunReport` - `crash`, `ticks_requested`/`ticks_completed`, `field_stats`, `evolution_samples`,
  `store_count_start`/`end`, `memory_start/peak/end_mb`, derived `boundedness_ok` / `memory_ok` /
  `completed_all` / `verdict_ok`, `violations()`, `summary()`.
- `_extract_fields(result)` - defensive `getattr` chain over `stage_results` returning the flat
  `{owner.field: float}` map for the tick; a missing/inactive stage simply contributes no field.
- `run_long_run(handle, config)` - starts `tracemalloc` (if not already tracing), loops `ticks`
  times calling `handle.tick()` inside a `try/except` (an exception -> `crash`, stop), updates each
  `FieldStat`, samples the evolution curve every `sample_every`, records memory peak/end and store
  counts, and returns the report.

### 3.2 `test_r83_long_run.py`

- `_DeterministicThoughtProvider` - a network-free LLM provider returning a fixed structured envelope
  every tick, including a fixed `hormone_response_i_predict` so the run also exercises the R81
  corroboration bias on `04` (the corroborated levels must stay bounded too).
- `_deterministic_gateway()` - `LlmGateway` over that provider with the default config profiles and a
  dummy api key (statically ready, offline).
- `_run(tmp_path, ticks)` - `assemble_production_runtime(data_dir=tmp_path, gateway=...)`, startup,
  `run_long_run`.
- `test_r83_ci_long_run` - runs `_CI_TICKS` (default 150), asserts no crash, full completion, every
  tracked field `ok`, memory under ceiling, store growth, and that the core owners were observed every
  tick; prints the report summary.
- `test_r83_run_is_repeatable` - two fresh 25-tick runs produce identical owner-field min/max.
- `test_r83_long_run_opt_in` - `_LONG_TICKS` (default 100000); `skipif` unless `HELIOS_R83_LONG_RUN`.
- `test_r83_real_llm_long_run` - real gateway from env; `skipif` unless `HELIOS_R83_REAL_LLM`.

## 4. Data Structures

`FieldStat`, `LongRunConfig`, `LongRunReport`, `TRACKED_FIELD_BOUNDS` (all tests-only). No runtime
contract changes.

## 5. Module Changes

1. New `tests/r83_long_runner/__init__.py` (exports the harness symbols).
2. New `tests/r83_long_runner/long_runner.py` (the harness).
3. New `tests/r83_long_runner/test_r83_long_run.py` (the three tiers).
4. Docs: `requirements/index.md` row 83.

## 6. Migration Plan

1. Tests-only and additive; no runtime/owner code is touched.
2. The CI tier is bounded (default 150 ticks) to keep the default suite reasonable; the package's
   `__init__.py` makes pytest insert `tests/` so `from r83_long_runner import ...` resolves alongside
   the flat test modules.
3. The production-scale and real-LLM tiers are env-gated and skipped in CI.

## 7. Failure Modes and Constraints

1. A per-tick runtime exception is captured as `crash` (not propagated from inside the harness); the
   consuming test fails its verdict on it. An out-of-range / NaN / non-finite owner value is recorded
   per field and fails `boundedness_ok`.
2. A store-count read failure degrades to `-1` (diagnostic only) and never aborts the run.
3. `18.outward_drive` is intentionally not a unit interval; it is bounded only against the divergence
   ceiling, so a legitimate above-1 drive is not a false violation while a runaway value is caught.
4. The harness uses no `print`/`logging` and imports no owner internals.

## 8. Observability and Logging

No new logging mechanism and no `print`/`logging` in the harness. The CI-tier test renders the report
summary via `print` (allowed in tests, not in `src/`), so the boundedness evidence appears in the CI
log. The report's evolution samples are the cross-tick curve evidence.

## 9. Validation Strategy

1. CI: `pytest helios_v2/tests/r83_long_runner -q` - the 150-tick run passes with a bounded verdict and
   the determinism test passes; the two opt-in tiers are skipped.
2. Boundedness is falsifiable: the per-field stats fail the verdict on any NaN / non-finite /
   out-of-range observation, and a crash fails completion.
3. Regression: the full network-free suite stays green; no runtime/owner code changed.
4. Manual: `HELIOS_R83_LONG_RUN=1 pytest ...::test_r83_long_run_opt_in` exercises the 100k G0 gate;
   `HELIOS_R83_REAL_LLM=1 pytest ...::test_r83_real_llm_long_run` exercises a real-LLM short run.
