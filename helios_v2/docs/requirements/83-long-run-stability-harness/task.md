# Requirement 83 - Long-Run Stability and Owner-Boundedness Harness

## 1. Task Breakdown

### T1 - Reusable harness
Add `tests/r83_long_runner/long_runner.py`: `TRACKED_FIELD_BOUNDS`, `FieldStat`, `LongRunConfig`,
`LongRunReport` (with `boundedness_ok`/`memory_ok`/`completed_all`/`verdict_ok`/`violations`/`summary`),
`_extract_fields`, and `run_long_run(handle, config)`. No `print`/`logging`; read-only; defensive
field extraction.

### T2 - Package export
Add `tests/r83_long_runner/__init__.py` exporting the harness symbols so
`from r83_long_runner import ...` resolves under pytest.

### T3 - Tiered verification module
Add `tests/r83_long_runner/test_r83_long_run.py`: `_DeterministicThoughtProvider` (+ fixed hormone
forecast to exercise R81), `_deterministic_gateway`, `_run`; `test_r83_ci_long_run` (locked
`_CI_TICKS`, asserts G0/G1/memory/store + prints summary), `test_r83_run_is_repeatable`,
`test_r83_long_run_opt_in` (`HELIOS_R83_LONG_RUN`), `test_r83_real_llm_long_run` (`HELIOS_R83_REAL_LLM`).

### T4 - Tick-count tuning
Measure per-tick cost and lock `_CI_TICKS` so the CI tier stays reasonable (default 150); record the
O(n) novelty-cost finding in code comments and the requirement.

### T5 - Documentation sync
Update `index.md` (row 83). `OWNER_GUIDE.*`/`PROGRESS_FLOW.*` need no owner-maturity change (tests-only
harness); bump only if a maturity color changes (it does not).

## 2. Dependencies

1. T1 -> T2 -> T3 -> T4 -> T5.
2. External: R82 `assemble_production_runtime`, the LLM gateway doubles, and the published
   `RuntimeTickResult` owner fields. No runtime/owner code change.

## 3. Files and Modules

1. `tests/r83_long_runner/__init__.py`, `long_runner.py`, `test_r83_long_run.py` (T1-T3)
2. `docs/requirements/index.md` (T5)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5.

## 5. Validation Plan

1. `pytest helios_v2/tests/r83_long_runner -q` green (2 passed, 2 skipped).
2. Full: `pytest helios_v2/tests -q` green and network-free.
3. Manual: `HELIOS_R83_LONG_RUN=1` (100k) and `HELIOS_R83_REAL_LLM=1` (real-LLM) tiers.

## 6. Completion Criteria

1. `run_long_run` returns a `LongRunReport` with a falsifiable `verdict_ok` (no crash, full completion,
   bounded/finite/non-NaN owner fields, bounded memory).
2. The CI tier runs the R82 production-shaped assembly network-free for the locked tick count, passes
   the bounded verdict, and renders its summary; the determinism test passes.
3. The 100k and real-LLM tiers exist and are env-gated (skipped in CI).
4. No runtime/owner code changed; full network-free suite green; `index.md` row 83 records the harness,
   the locked tick counts, and the O(n) novelty-cost finding.
