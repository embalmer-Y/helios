# Requirement 41 - Dimension-grounded aggregate salience judgment (tasks)

## 1. Task Breakdown

### Task 1 - Owner-owned weighted aggregate estimator
1. In `helios_v2/src/helios_v2/appraisal/engine.py`, add `WeightedAggregateEstimator` implementing the existing `AggregateJudgmentEstimator` protocol, with explicit first-version per-dimension weight fields summing to `1.0` (`threat 0.25, reward 0.25, novelty 0.20, uncertainty 0.15, social 0.15`).
2. `estimate_aggregate(stimulus, dimensions)` ignores `stimulus` and returns `clamp(sum(weight_k * dimension_k), 0, 1)` (rounded), a convex combination of the five dimensions.
3. The combination is monotonic non-decreasing in each dimension, deterministic, stateless, bounded; no NN/LLM/network.
4. Completion: aggregate is a real function of the five dimensions; range-bounded; weights sum to 1.0.
5. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.

### Task 2 - Export the new estimator
1. In `helios_v2/src/helios_v2/appraisal/__init__.py`, export `WeightedAggregateEstimator`.
2. Completion: importable from `helios_v2.appraisal`.
3. Validation: import succeeds in the composition assembly module.

### Task 3 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, when `semantic_memory_enabled`, build the appraisal engine with `aggregate_estimator=WeightedAggregateEstimator()`; keep `FirstVersionAggregateEstimator()` otherwise. The dimension-estimator selection (R35-R40) is unchanged.
2. No new public assembly flag; reuse the existing `semantic_memory_enabled` opt-in.
3. Completion: the semantic-memory assembly grounds the aggregate; default/recency/offline keep constant `0.4`.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Tests
1. `test_rapid_salience_engine.py` (extend): aggregate equals the weighted sum for a known dimension vector; weights sum to 1.0; monotonic; high-salience vector > low-salience vector; range `[0,1]` for extreme dimensions; determinism; through the engine the `RapidSalienceVector.aggregate` reflects the combination (not `0.4`).
2. `test_runtime_composition.py` (extend): semantic assembly yields a dimension-driven aggregate (not `0.4`) that differs across two ticks with different dimensions; default assembly keeps constant `0.4`.
3. Completion: all new/extended tests pass and assert real differences, not just presence.
4. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 5 - Documentation sync
1. `index.md`: add the R41 row (depends on `03, 35, 39, 40`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add migration-state item 22 — `03` aggregate is now a dimension-grounded convex combination under the semantic assembly, closing the `03` owner P3 de-shim (all five dimensions + aggregate real); weights are an owner-owned first-version placeholder allocation (P5-learnable), the aggregate inherits its inputs' grounding (threat/reward still R40 `C_engineering_hypothesis`); default keeps constant `0.4`.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row to note the `03` owner is fully de-shimmed (five dimensions + aggregate real); the aggregate inherits input grounding tiers; add `41` to links.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `03` entry — add the aggregate de-shim (R41) as a shipped step; flip completeness note to "all `03` outputs real under the semantic assembly"; record the weight placeholder + P5/model-assisted replacement and the inherited-grounding caveat.
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): update the `03` node label (aggregate now real too), last-synced to R41, test baseline count, status-summary bullet.
6. Completion: no doc/code drift.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `03` appraisal owner (`AggregateJudgmentEstimator` protocol, `RapidDimensionEstimate`, `RapidSalienceVector`) — shipped.
2. Depends on the R35/R39/R40 real dimensions (the aggregate only carries real signal once the dimensions are real) — shipped.
3. Reuses the composition semantic-memory opt-in from R34-R40 — shipped.
4. No dependency on any injected fact source (the aggregate is a pure function of the dimensions); stateless.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (Task 1)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (Task 2)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 3)
4. `helios_v2/tests/test_rapid_salience_engine.py` (Task 4)
5. `helios_v2/tests/test_runtime_composition.py` (Task 4)
6. `helios_v2/docs/requirements/index.md` (Task 5)
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 5)
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 5)
9. `helios_v2/docs/OWNER_GUIDE.md` (Task 5)
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 5)
11. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 5)
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 5)

## 4. Implementation Order

1. Task 1 (owner estimator) — foundation; testable in isolation.
2. Task 2 (export) — makes it available to composition.
3. Task 3 (assembly wiring) — selects it under the opt-in.
4. Task 4 (tests) — alongside Tasks 1-3, finalized with the composition dimension-driven aggregate test.
5. Task 5 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.
2. After Task 3: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 4: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `03` computes `aggregate` as a bounded convex combination of the five real dimensions via an owner-owned estimator when the semantic-memory assembly is enabled; composition only selects it.
2. The aggregate is dimension-driven (differs with dimensions, monotonic, deterministic), within `[0,1]`; weights are explicit owner constants summing to `1.0`, recorded as a first-version placeholder (P5-learnable) and not over-claimed.
3. With R41 all `03` outputs (five dimensions + aggregate) are real under the semantic assembly; the default, recency-only, and offline assemblies keep constant `0.4`.
4. The five dimension behaviors are unchanged from R35/R39/R40.
5. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
6. The single-logging-mechanism guard and the full test suite remain green and network-free.
