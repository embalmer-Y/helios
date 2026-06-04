# Requirement 37 - Neuromodulatory gating coupling (tasks)

## 1. Task Breakdown

### Task 1 - Additive optional arousal fact on the gate-signal contract
1. In `helios_v2/src/helios_v2/thought_gating/contracts.py`, add `neuromodulatory_arousal: float | None = None` as the last field of `ThoughtGateSignalSnapshot`, validated to `[0.0, 1.0]` in `__post_init__` only when not `None` (reuse `_validate_unit_interval`).
2. The field is a raw input fact, not a score; no other contract changes.
3. Completion: an uncoupled snapshot (field omitted) is byte-for-byte equivalent to today; an out-of-range value raises `ThoughtGatingError`.
4. Validation: `pytest helios_v2/tests/test_thought_gating_contracts.py -q`.

### Task 2 - Owner-private arousal-aware gate path
1. In `helios_v2/src/helios_v2/thought_gating/engine.py`, add `ArousalAwareThoughtGatePath` implementing `ThoughtGatePath`. Share the first-version decision structure (extract a private helper or subclass) so only the activation-input derivation differs.
2. When `signal_snapshot.neuromodulatory_arousal is None`, behavior must be identical to `FirstVersionThoughtGatePath`. When present, add one non-negative term `arousal_gain * arousal` (explicit bounded first-version constant `arousal_gain = 0.15` under the `gate_policy` category) to the existing gate-score sum, then clamp. The existing `global_activation_level * 0.20` term and all other terms are untouched. Record `contributing_signals["neuromodulatory_arousal"] = arousal`.
3. The arousal term must be monotonic non-decreasing in arousal, with weight `0.15` below `fire_threshold` 0.55 so arousal alone cannot cross the threshold, and being additive non-negative it cannot suppress an otherwise-justified fire; deterministic; stateless (no prior-tick read).
4. Completion: arousal-aware path is identical to first-version for `None`; raises the gate score monotonically otherwise; never a hard gate by itself.
5. Validation: `pytest helios_v2/tests/test_thought_gating_engine.py -q`.

### Task 3 - Export the new gate path
1. In `helios_v2/src/helios_v2/thought_gating/__init__.py`, export `ArousalAwareThoughtGatePath` so composition can select it.
2. Completion: `from helios_v2.thought_gating import ArousalAwareThoughtGatePath` works.
3. Validation: import succeeds in the composition assembly module.

### Task 4 - Composition arousal-forwarding gate-signal bridge
1. In `helios_v2/src/helios_v2/composition/bridges.py`, add `NeuromodulatorAwareThoughtGateSignalBridge`. In `build_signal_snapshot(frame, conscious_result)`, read the current tick's `NeuromodulatorStageResult` from `frame.stage_results` (typed/`isinstance` read, mirroring `_require_stage_result`), take `state.levels.norepinephrine`, and build the same snapshot as the first-version bridge plus `neuromodulatory_arousal=that level`.
2. It forwards the raw value with no mapping (no activation/score computation in composition). A missing/wrong-typed neuromodulator result is a fail-fast error, not a degraded uncoupled snapshot.
3. The first-version bridge is unchanged.
4. Completion: under a coupled tick the snapshot carries the real norepinephrine level; composition computes no gate semantics.
5. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 5 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, when `semantic_memory_enabled`, construct the `ThoughtGatingEngine` with `gate_path=ArousalAwareThoughtGatePath()` and register the `ThoughtGatingRuntimeStage` with `signal_provider=NeuromodulatorAwareThoughtGateSignalBridge()`; otherwise keep `FirstVersionThoughtGatePath()` + `FirstVersionThoughtGateSignalBridge()`.
2. No new public assembly flag; reuse the existing `semantic_memory_enabled` opt-in (same trigger as R35/R36).
3. Completion: the semantic-memory assembly couples arousal into `09`; default/recency/offline assemblies are unchanged.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 6 - Tests
1. `test_thought_gating_contracts.py` (extend): default `None`; valid `[0,1]` accepted; out-of-range rejected.
2. `test_thought_gating_engine.py` (extend): `None` == first-version; monotonic increase; arousal-alone cannot fire; arousal cannot suppress an otherwise-justified fire; `contributing_signals` carries the arousal entry; determinism.
3. `test_runtime_composition.py` (extend): coupled assembly yields a different `contributing_signals["neuromodulatory_arousal"]` (and `>=` gate score) across two ticks differing in `03` novelty; default assembly snapshot has `neuromodulatory_arousal is None` and unchanged behavior.
4. Completion: all new/extended tests pass and assert real differences, not just presence.
5. Validation: `pytest helios_v2/tests/test_thought_gating_engine.py helios_v2/tests/test_thought_gating_contracts.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 7 - Documentation sync
1. `index.md`: add the R37 row (depends on `04, 09, 36`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add migration-state item 18 — `09` gate decision now couples the real `04` norepinephrine level under the semantic-memory assembly via an owner-private arousal-aware gate path; composition forwards the raw fact only; bounded, stateless, never a hard gate; default unchanged; cortisol/inhibition hard gate deferred.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row and `gap_behavioral_consequence_binding` to note the real `04` arousal now measurably shapes `09` gating; keep `05`, cortisol/inhibition hard gate, and dual-timescale as open; add `37` to the links.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `09` entry (real `04` arousal coupling shipped under semantic assembly) and the `04` entry next-step (downstream coupling into `09` now partially shipped — norepinephrine; cortisol/inhibition + `05` remain).
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): update the `09` node label, last-synced to R37, the test baseline count, and a status-summary bullet.
6. Completion: no doc/code drift across index, boundaries, comparison, both owner guides, both flow maps.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `09` thought-gating owner (`ThoughtGateSignalSnapshot`, `ThoughtGatePath`, `FirstVersionThoughtGatePath`, `ThoughtGatingEngine`) — shipped.
2. Depends on `04` neuromodulator owner real levels (`NeuromodulatorStageResult.state.levels.norepinephrine`) and R36's appraisal-derived path — shipped.
3. Reuses the composition semantic-memory opt-in from R34/R35/R36 — shipped.
4. No dependency on a gate/neuromodulator-state carry (stateless; dual-timescale is a later slice).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/thought_gating/contracts.py` (Task 1)
2. `helios_v2/src/helios_v2/thought_gating/engine.py` (Task 2)
3. `helios_v2/src/helios_v2/thought_gating/__init__.py` (Task 3)
4. `helios_v2/src/helios_v2/composition/bridges.py` (Task 4)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 5)
6. `helios_v2/tests/test_thought_gating_contracts.py` (Task 6)
7. `helios_v2/tests/test_thought_gating_engine.py` (Task 6)
8. `helios_v2/tests/test_runtime_composition.py` (Task 6)
9. `helios_v2/docs/requirements/index.md` (Task 7)
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 7)
11. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 7)
12. `helios_v2/docs/OWNER_GUIDE.md` (Task 7)
13. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 7)
14. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 7)
15. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 7)

## 4. Implementation Order

1. Task 1 (additive optional contract field) — foundation; suite stays green because it defaults to `None`.
2. Task 2 (arousal-aware gate path) — owns the mapping; unit-testable in isolation against the engine.
3. Task 3 (export) — makes the path available to composition.
4. Task 4 (forwarding bridge) — reads the `04` result, forwards the raw fact.
5. Task 5 (assembly opt-in wiring) — binds the path + bridge under the semantic-memory flag.
6. Task 6 (tests) — alongside Tasks 1-5, finalized with the composition novelty-driven arousal test.
7. Task 7 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_thought_gating_contracts.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_thought_gating_engine.py -q`.
3. After Tasks 4-5: `pytest helios_v2/tests/test_runtime_composition.py -q`.
4. After Task 6: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
5. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `09` couples the real `04` norepinephrine level into the gate decision when the semantic-memory assembly is enabled, via an owner-private arousal-aware gate path fed by an additive optional raw fact on `ThoughtGateSignalSnapshot`; composition forwards the raw level only.
2. Higher neuromodulatory arousal yields a gate score no lower (monotonic, deterministic); the arousal contribution is bounded so it can neither solely force nor solely suppress a fire.
3. The arousal contribution is observable through `ThoughtGateResult.contributing_signals` with no new logging mechanism; no contract break beyond the one additive optional field.
4. Under the coupled assembly, two ticks differing in `03` novelty produce a measurably different arousal-contributing gate signal; the default, recency-only, and offline assemblies keep the constant activation input and current behavior.
5. The coupling is stateless (no prior-tick read), uses no NN and no hidden branch, and never diverges outside `[0,1]`.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
