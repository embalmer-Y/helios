# Requirement 36 - Appraisal-derived neuromodulation (tasks)

## 1. Task Breakdown

### Task 1 - Appraisal-derived update path (composition glue)
1. In `helios_v2/src/helios_v2/composition/bridges.py`, add `AppraisalDerivedNeuromodulatorUpdatePath` (implements the `04` `NeuromodulatorUpdatePath` protocol) plus the module-private `_AggregatedSalience`, `_aggregate_salience` (per-dimension max across the batch; empty batch -> all-zero), and `_clamp` helpers.
2. The derivation is `clamp(tonic_baseline_channel + sum(sensitivity_k * salience_k), legal_min, legal_max)` per channel, with the documented mapping (reward/novelty -> dopamine; novelty/uncertainty -> norepinephrine; threat -> cortisol; other channels -> clamped tonic baseline). Coefficients are explicit bounded first-version constants.
3. The path reads only the batch + config; it imports/reaches no other owner's state and reads no prior-tick levels (stateless).
4. Completion: deterministic, range-bounded levels derived from a batch; empty batch -> tonic baseline.
5. Validation: `pytest helios_v2/tests/test_neuromodulator_engine.py -q`.

### Task 2 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, select `AppraisalDerivedNeuromodulatorUpdatePath()` for the `NeuromodulatorEngine` when both `experience_store` and `embedding_gateway` are present (the semantic-memory assembly, where R35 novelty is real); keep `FirstVersionNeuromodulatorUpdatePath()` otherwise.
2. No new public assembly flag; reuse the existing semantic-memory opt-in (same trigger as R35).
3. Completion: a semantic-memory assembly runs a tick whose `04` levels are appraisal-derived; default/recency/offline assemblies unchanged.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 3 - Tests
1. `test_neuromodulator_engine.py` (extend): high-novelty vs low-novelty batch -> higher NE; high-reward -> higher DA; high-threat -> higher cortisol; empty batch -> tonic baseline; all levels in legal range; determinism; non-driven channels equal clamped tonic baseline.
2. `test_runtime_composition.py` (extend): semantic-memory assembly produces different NE across two ticks differing in novelty (read from the `04` stage result); default assembly keeps constant levels.
3. Completion: all new/extended tests pass; the salience-driven tests assert a real difference, not just presence.
4. Validation: `pytest helios_v2/tests/test_neuromodulator_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 4 - Documentation sync
1. `index.md`: add the R36 row (depends on `03, 04, 35`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add a migration-state note that `04` levels are now appraisal-derived (stateless deterministic equation) under the semantic-memory assembly, via an owner-protocol-conforming composition-provided update path; the `04` engine is unchanged; dual-timescale decay (prior-tick carry) is deferred.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row to note `04` neuromodulation now derives from real appraisal (DA/NE/cortisol driven by reward/novelty-uncertainty/threat); keep `05-07` and dual-timescale decay as open.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `04` entry completeness/next-step (stateless appraisal-derived levels shipped; dual-timescale decay + P5 coefficient learning + downstream coupling remain).
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): note `04` levels are appraisal-derived under the semantic-memory assembly; update last-synced to R36 and the test baseline count.
6. Completion: no doc/code drift across index, boundaries, comparison, both owner guides, both flow maps.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `04` neuromodulator owner (`NeuromodulatorUpdatePath` protocol, `NeuromodulatorLevels`/`NeuromodulatorConfig`) — shipped.
2. Depends on `03` appraisal (`RapidAppraisalBatch`, `RapidSalienceVector`) and `35` real novelty — shipped.
3. Reuses the composition semantic-memory opt-in from R34/R35 — shipped.
4. No dependency on a neuromodulator-state carry/checkpoint (dual-timescale decay is a later slice).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` (Task 1)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
3. `helios_v2/tests/test_neuromodulator_engine.py` (Task 3)
4. `helios_v2/tests/test_runtime_composition.py` (Task 3)
5. `helios_v2/docs/requirements/index.md` (Task 4)
6. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 4)
7. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 4)
8. `helios_v2/docs/OWNER_GUIDE.md` (Task 4)
9. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 4)
10. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 4)
11. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 4)

## 4. Implementation Order

1. Task 1 (appraisal-derived update path + helpers) — foundation; testable in isolation against the `04` engine.
2. Task 2 (composition opt-in wiring) — binds the path in the semantic-memory assembly.
3. Task 3 (tests) — alongside Tasks 1-2, finalized with the composition novelty-driven NE test.
4. Task 4 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_neuromodulator_engine.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 3: the two suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `04` computes neuromodulator levels from the real appraisal batch when the semantic-memory assembly is enabled, via an injected `NeuromodulatorUpdatePath` that consumes the batch; the `04` engine is unchanged.
2. Higher novelty -> higher norepinephrine; higher reward -> higher dopamine; higher threat -> higher cortisol; the differences are salience-driven, not constant.
3. Every level is within its legal range, deterministic for identical inputs, and flows through the unchanged `NeuromodulatorState`/`NeuromodulatorLevels` contracts; an empty batch yields the tonic baseline.
4. The sensitivity coefficients are explicit bounded first-version constants (P5-learnable later); the derivation is a linear combination plus clamp with no NN and no prior-tick state read.
5. The default, recency-only, and offline assemblies keep the constant update path and their current `04` behavior.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
