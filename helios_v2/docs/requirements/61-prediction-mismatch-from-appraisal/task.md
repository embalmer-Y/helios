# Requirement 61 - Prediction-Mismatch Evidence Grounded in Real Appraisal Novelty

## 1. Task Breakdown

### T1 - Add the low-novelty threshold constant
In `composition/bridges.py`, add a module-level `_MISMATCH_NOVELTY_THRESHOLD = 0.5` (the
first-version cut-point below which a percept is familiar/expected and yields no surprise
evidence). Reuse the existing `_clamp`.

### T2 - Derive mismatch from the real `03` appraisal
Rewrite `FirstVersionPredictionMismatchEvidenceBridge.build_mismatch_evidence(frame, feeling_result)`
to read the real `rapid_salience_appraisal` `RapidSalienceAppraisalStageResult` from the frame,
compute the batch-max `novelty` and `uncertainty`, return `None` when there is no appraisal/empty
batch or `novelty < _MISMATCH_NOVELTY_THRESHOLD`, and otherwise project
`mismatch_score=clamp(novelty)`, `anomaly_score=clamp(novelty)`, `confidence=clamp(1 - uncertainty)`
into `PredictionMismatchEvidence` (preserving the real feeling-state `source_reference_id`). Remove
the `0.8/0.85/0.9` constant. Lazily import `RapidSalienceAppraisalStageResult`.

### T3 - Update existing tests asserting the old constant / always-autobiographical
Find and update stage-chain/composition tests asserting the old mismatch scores
(`0.8`/`0.85`/`0.9`) or an always-`autobiographical` formed-memory family to assert the real
novelty-grounded behavior.

### T4 - Add focused tests
In `test_runtime_composition.py`: a novel (cold/dissimilar) percept yields a high mismatch and an
`autobiographical` memory; a familiar (similar) percept yields `None` mismatch and an `episodic`
memory; the mismatch tracks real novelty (different novelty → different score, not `0.8`); the
default assembly's constant novelty `0.6` yields a `0.6`-derived mismatch (no `0.8` constant).

### T5 - Documentation
Update `index.md` (row 61), both `OWNER_GUIDE` files (`06`/`03` entries: mismatch now grounded in
real appraisal novelty, honest `B_functional_inspiration` caveat), both `PROGRESS_FLOW` maps
(status note + sync line), and `BRAIN_ARCHITECTURE_COMPARISON.md` (FG-1 mismatch/surprise
grounding + caveat).

## 2. Dependencies

1. T1 -> T2 (the bridge uses the constant).
2. T3 + T4 after T2. T5 after T1-T4.
3. External requirement dependencies: 06 (memory owner: salience gate + family mapping), 45
   (affect-grounded formation/salience gate), 03 (`RapidSalienceVector` novelty/uncertainty), 35
   (memory-grounded novelty), 59/60 (real percept feeding `03`/`06`). No new owner, no contract
   change.

## 3. Files and Modules

1. `src/helios_v2/composition/bridges.py` (T1, T2)
2. `tests/test_runtime_stage_chain.py` and/or `tests/test_runtime_composition.py` (T3, T4)
3. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`, `docs/OWNER_GUIDE.zh-CN.md`,
   `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md` (T5)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5. Constant, derivation, fix existing tests, add focused tests, document.

## 5. Validation Plan

1. After T2 (no stale constant + chain runs):
   `pytest helios_v2/tests/test_runtime_stage_chain.py helios_v2/tests/test_runtime_composition.py -q`
   green (existing tests updated for the real novelty-grounded mismatch).
2. After T4 (new behavior):
   `pytest helios_v2/tests/test_runtime_composition.py -q` green, including novel→autobiographical,
   familiar→episodic, novelty-tracking, and default-assembly tests.
3. `06` mechanism regression:
   `pytest helios_v2/tests/test_memory_engine.py helios_v2/tests/test_memory_contracts.py -q`
   green (salience gate / family mapping / recall unchanged).
4. Guards + full suite:
   `pytest helios_v2/tests/test_composition_owner_boundary_guard.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`
   and `pytest helios_v2/tests -q` green; count = prior baseline (732) + added tests (minus any
   updated-in-place).

## 6. Completion Criteria

1. The mismatch evidence is derived from the real `03` novelty/uncertainty (different novelty →
   different score; familiar percept → `None`); no hardcoded `0.8/0.85/0.9` mismatch constant
   remains in composition.
2. A novel percept yields high mismatch + `autobiographical` family; a familiar percept yields
   `None` + `episodic` family; a `None`-mismatch tick completes the chain.
3. The `06` salience gate, family mapping, durability, and recalled replay are unchanged in
   mechanism (their tests stay green).
4. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
5. `index.md`, both `OWNER_GUIDE` files, both `PROGRESS_FLOW` maps, and
   `BRAIN_ARCHITECTURE_COMPARISON.md` record that mismatch is grounded in real appraisal novelty
   (with the honest novelty-as-surprise caveat), with sync lines naming R61.
