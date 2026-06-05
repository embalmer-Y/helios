# Requirement 38 - Neuromodulator-derived feeling (tasks)

## 1. Task Breakdown

### Task 1 - Owner-private neuromodulator-derived construction path
1. In `helios_v2/src/helios_v2/feeling/engine.py`, add `NeuromodulatorDerivedFeelingConstructionPath` implementing the existing `FeelingConstructionPath` protocol, plus a module-private `_clamp(value, low, high)`.
2. `construct_feeling` derives each dimension as `clamp(baseline_dim + sum(+coeff * level) - sum(-coeff * level), legal_min_dim, legal_max_dim)` using the documented first-version coupling table (valence: +DA/opioid/5-HT, -cortisol; arousal: +NE/excitation; tension: +cortisol/NE; comfort: +opioid/oxytocin/5-HT, -cortisol; pain_like: +cortisol, -opioid; social_safety: +oxytocin/5-HT, -cortisol; fatigue: +inhibition, -excitation). Reference level is `0.0` per channel this slice.
3. The path reads only `neuromodulator_state.levels` + `config`; it ignores `internal_signals`/`tick_id` (contract compatibility) and reads no prior-tick feeling (stateless).
4. Completion: deterministic, range-bounded feeling derived from a real neuromodulator state; the engine, protocol, and the constant path are unchanged.
5. Validation: `pytest helios_v2/tests/test_interoceptive_feeling_engine.py -q`.

### Task 2 - Export the new path
1. In `helios_v2/src/helios_v2/feeling/__init__.py`, export `NeuromodulatorDerivedFeelingConstructionPath` so composition can select it.
2. Completion: `from helios_v2.feeling import NeuromodulatorDerivedFeelingConstructionPath` works.
3. Validation: import succeeds in the composition assembly module.

### Task 3 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, when `semantic_memory_enabled`, build the `InteroceptiveFeelingEngine` with `construction_path=NeuromodulatorDerivedFeelingConstructionPath()`; keep `FirstVersionFeelingConstructionPath()` otherwise.
2. No new public assembly flag; reuse the existing `semantic_memory_enabled` opt-in (same trigger as R35/R36/R37).
3. Completion: a semantic-memory assembly runs a tick whose `05` feeling is neuromodulator-derived; default/recency/offline assemblies are unchanged.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Tests
1. `test_interoceptive_feeling_engine.py` (extend): high-cortisol vs low-cortisol -> higher tension/pain_like, lower valence/comfort; high-dopamine -> higher valence; high-norepinephrine -> higher arousal; high-oxytocin -> higher social_safety; all dimensions within legal range for extreme states; determinism; the derived path differs from the constant for a non-baseline state.
2. `test_runtime_composition.py` (extend): the semantic-memory assembly produces different feeling (tension/pain_like) across two ticks whose `04` cortisol differs (read from the `05` stage result); the default assembly keeps the constant feeling vector.
3. Completion: all new/extended tests pass; the salience-driven tests assert a real difference, not just presence.
4. Validation: `pytest helios_v2/tests/test_interoceptive_feeling_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 5 - Documentation sync
1. `index.md`: add the R38 row (depends on `04, 05, 36`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add migration-state item 19 — `05` feeling now neuromodulator-derived (owner-private bounded equation) under the semantic-memory assembly; `04`'s two downstream consumers (`09`, `05`) are now both real; the `05` engine/contracts are unchanged; dual-timescale feeling persistence and real interoceptive-signal integration deferred.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row to note `05` feeling now derives from real `04` state (valence/tension/pain_like/etc. from DA/cortisol/NE/oxytocin); both `04` consumers real; keep `06-07`, dual-timescale, and the remaining `03` dimensions open.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `05` entry (neuromodulator-derived feeling shipped under semantic assembly; stateless) and the `04` entry next-step (downstream coupling now fully shipped for both `09` and `05`; cortisol/inhibition hard gate and dual-timescale remain).
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): update the `05` node label, last-synced to R38, the test baseline count, and a status-summary bullet.
6. Completion: no doc/code drift across index, boundaries, comparison, both owner guides, both flow maps.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `05` feeling owner (`FeelingConstructionPath` protocol, `InteroceptiveFeelingVector`/`InteroceptiveFeelingConfig`, `InteroceptiveFeelingEngine`) — shipped.
2. Depends on `04` neuromodulator owner real levels (`NeuromodulatorState.levels`) and R36's appraisal-derived path — shipped.
3. Reuses the composition semantic-memory opt-in from R34/R35/R36/R37 — shipped.
4. No dependency on a feeling-state carry/checkpoint (stateless; dual-timescale persistence is a later slice).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/feeling/engine.py` (Task 1)
2. `helios_v2/src/helios_v2/feeling/__init__.py` (Task 2)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 3)
4. `helios_v2/tests/test_interoceptive_feeling_engine.py` (Task 4)
5. `helios_v2/tests/test_runtime_composition.py` (Task 4)
6. `helios_v2/docs/requirements/index.md` (Task 5)
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 5)
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 5)
9. `helios_v2/docs/OWNER_GUIDE.md` (Task 5)
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 5)
11. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 5)
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 5)

## 4. Implementation Order

1. Task 1 (owner-private construction path + `_clamp`) — foundation; testable in isolation against the `05` engine.
2. Task 2 (export) — makes the path available to composition.
3. Task 3 (composition opt-in wiring) — binds the path in the semantic-memory assembly.
4. Task 4 (tests) — alongside Tasks 1-3, finalized with the composition cortisol-driven feeling test.
5. Task 5 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_interoceptive_feeling_engine.py -q`.
2. After Task 3: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 4: the two suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `05` computes feeling from the real `04` neuromodulator state when the semantic-memory assembly is enabled, via an owner-private construction path that consumes the state; the `05` engine and contracts are unchanged.
2. Higher cortisol -> higher tension/pain_like and lower valence/comfort; higher dopamine -> higher valence; higher norepinephrine -> higher arousal; the differences are state-driven, not constant.
3. Every feeling dimension is within its legal range, deterministic for identical inputs, and flows through the unchanged `InteroceptiveFeelingState`/`InteroceptiveFeelingVector` contracts.
4. The coupling coefficients are explicit bounded first-version constants under the config's declared learned-parameter categories; the derivation is a linear combination plus clamp with no NN and no prior-tick feeling read.
5. The default, recency-only, and offline assemblies keep the constant construction path and their current `05` behavior.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
