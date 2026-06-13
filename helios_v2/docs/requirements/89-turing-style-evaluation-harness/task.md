# Requirement 89 - Long-Run Turing-Style Evaluation Harness

## 1. Task Breakdown

### T1 - Harness package skeleton and rubric model
- Create `tests/r89_turing_harness/__init__.py` and `turing_harness.py`.
- Define axis constants + dimension membership, availability constants, judge-track constants,
  `InjectedAxisScore`, `TuringConfig`, `AxisScore`, `TuringVerdict` (with derived `passes` /
  `violations()` / `summary()`).

### T2 - Axis scoring + reconstructed internal axes
- Implement the per-axis resolver (injected override → reconstructed internal → unavailable/stubbed).
- Implement `bio_responsiveness` (health + movement over `04.*`/`05.*`), `cross_tick_continuity`
  (completion + continuation-level boundedness + affect carry), `agency_locking` (present/bounded
  owner-dim fraction proxy), `memory_fidelity` (stub), behavior-axis unavailability.
- Implement evidence anchoring (empty provenance → 0.0).

### T3 - Conservative aggregation + verdict
- Implement nearest-rank lower-quantile dimension scores over available axes, the
  `min(behavior, internal)` aggregate (both required), collapse detection, completeness, and `passes`.
- Implement `evaluate_turing(long_run_report, drift_report, config, injected_scores)` including the
  empty/degenerate-report guard.

### T4 - Tests
- Integration: short R83 run → R88 drift → R89 verdict (internal axes available + provenance,
  memory_fidelity stubbed, behavior unavailable, verdict incomplete/not-passing; render summary).
- Synthetic: full-injection pass; sub-collapse axis fail; empty-provenance → 0 fail; internal-only
  leaves behavior unscored not-passing; dual-dimension min aggregation; stubbed axis forces incomplete.
- Robustness: empty/degenerate report → non-passing with reason, no exception.

### T5 - Docs sync
- `requirements/index.md`: add row 89 (`baseline_implementation`).
- `ROADMAP.zh-CN.md`: move R89 from the P5 queue to delivered, with the explicit non-goal that the full
  §13.4 ≥ 300-stimulus acceptance (real afferents, real judges, R90 memory probe) is deferred.

## 2. Dependencies

1. R83 (`tests/r83_long_runner/`): `LongRunReport`, `run_long_run`, deterministic-gateway assembly,
   `TRACKED_FIELD_BOUNDS`.
2. R88 (`tests/r88_drift_evaluator/`): `DriftReport`, `evaluate_drift`.
3. No runtime/owner dependency; offline and network-free.

## 3. Files and Modules

1. `helios_v2/tests/r89_turing_harness/__init__.py` (new).
2. `helios_v2/tests/r89_turing_harness/turing_harness.py` (new).
3. `helios_v2/tests/r89_turing_harness/test_r89_turing_harness.py` (new).
4. `helios_v2/docs/requirements/index.md` (row 89).
5. `helios_v2/docs/ROADMAP.zh-CN.md` (R89 delivered).

## 4. Implementation Order

1. T1 skeleton + rubric model.
2. T2 axis scoring + reconstructed internal axes.
3. T3 aggregation + verdict.
4. T4 tests.
5. T5 docs sync.

## 5. Validation Plan

1. First narrow check: `pytest helios_v2/tests/r89_turing_harness -q` (set
   `PYTHONPATH=helios_v2/src`).
2. Falsifiability: collapse / missing-provenance / single-dimension / stubbed cases each fail `passes`;
   the offline baseline is provably incomplete/not-passing.
3. Regression: `pytest helios_v2/tests -q` stays green; no runtime/owner code changed.

## 6. Completion Criteria

1. `evaluate_turing` reconstructs the internal axes with provenance, stubs `memory_fidelity`, marks the
   behavior axes unavailable offline, and yields an `incomplete`/not-passing verdict on the baseline.
2. A fully-injected high-score run passes; the falsifiability cases fail as specified.
3. The full network-free suite is green; `index.md` row 89 and the ROADMAP delivered note (with the
   deferred-full-acceptance non-goal) are in place.
