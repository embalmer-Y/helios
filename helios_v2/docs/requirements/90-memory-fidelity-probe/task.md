# Requirement 90 - Memory Fidelity Probe (Real R10+R15 End-to-End)

## 1. Task Breakdown

### T1 - Probe package skeleton and report model
- Create `tests/r90_memory_fidelity_probe/__init__.py` and `memory_fidelity_probe.py`.
- Define `MemoryFidelityConfig`, `MemoryFidelityReport` (raw counts + three metrics + derived
  `fidelity_score`/`usable` + `violations()`/`summary()`), and `_has_store_hit`.

### T2 - Probe drive loop + metrics
- Implement `run_memory_fidelity_probe(handle_factory, config)`: startup, per-tick recall inspection
  (activated + pre-tick store non-empty → recall-possible; store-sourced bundle hit → recall-hit),
  store growth, latency + self-recall over embedded records, restart survival, metric computation,
  crash capture.

### T3 - R89 harness integration (additive)
- Add the optional `memory_fidelity_probe` parameter to `evaluate_turing`; when a usable report is
  supplied, emit an available reconstructed `memory_fidelity` axis (`score = fidelity_score`,
  provenance from the metrics); otherwise keep the existing stub path exactly.

### T4 - Tests
- Probe metrics: usable report, high `writeback_persistence_rate`, bounded metrics, `appended > 0`;
  render summary.
- R89 integration: with the report → `memory_fidelity` available/reconstructed/score==fidelity_score;
  without it → stubbed (R89 unchanged).
- Robustness: unusable/crash report → axis stays stubbed, `usable == False` with a reason.

### T5 - Docs sync
- `requirements/index.md`: add row 90 (`baseline_implementation`).
- `ROADMAP.zh-CN.md`: move R90 from the P5 queue to delivered (memory_fidelity stub replaced by the
  real R10+R15 probe).

## 2. Dependencies

1. R89 (`tests/r89_turing_harness/`): the harness whose `memory_fidelity` stub this replaces.
2. R83 (`tests/r83_long_runner/`): the deterministic-gateway production-assembly pattern.
3. `33` `ExperienceStore` + `10` `directed_retrieval_into_thought_window` stage result (read-only).
4. No runtime/owner code dependency to modify; offline and network-free.

## 3. Files and Modules

1. `helios_v2/tests/r90_memory_fidelity_probe/__init__.py` (new).
2. `helios_v2/tests/r90_memory_fidelity_probe/memory_fidelity_probe.py` (new).
3. `helios_v2/tests/r90_memory_fidelity_probe/test_r90_memory_fidelity_probe.py` (new).
4. `helios_v2/tests/r89_turing_harness/turing_harness.py` (additive parameter).
5. `helios_v2/docs/requirements/index.md` (row 90); `helios_v2/docs/ROADMAP.zh-CN.md` (R90 delivered).

## 4. Implementation Order

1. T1 skeleton + report model.
2. T2 probe drive loop + metrics.
3. T3 R89 harness integration.
4. T4 tests.
5. T5 docs sync.

## 5. Validation Plan

1. First narrow check: `pytest helios_v2/tests/r90_memory_fidelity_probe -q` (set
   `PYTHONPATH=helios_v2/src`).
2. R89 non-regression: `pytest helios_v2/tests/r89_turing_harness -q` stays green (stub path preserved).
3. Regression: `pytest helios_v2/tests -q` stays green; no runtime/owner code changed.

## 6. Completion Criteria

1. The probe measures the three metrics from real R10/R15/R33/R34 provenance and composes a bounded
   `fidelity_score`; `writeback_persistence_rate` demonstrates cross-restart durability.
2. The R89 `memory_fidelity` axis becomes a real available reconstructed axis when a usable report is
   supplied, and stays stubbed otherwise (all R89 tests green).
3. The full network-free suite is green; `index.md` row 90 and the ROADMAP delivered note are in place.
