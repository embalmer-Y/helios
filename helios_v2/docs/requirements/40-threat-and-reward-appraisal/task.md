# Requirement 40 - Prototype-grounded threat and reward appraisal (tasks)

## 1. Task Breakdown

### Task 1 - Owner-side prototype constants, source protocol, and threat/reward mapping
1. In `helios_v2/src/helios_v2/appraisal/engine.py`, add the owner constants `THREAT_PROTOTYPES` and `REWARD_PROTOTYPES` (fixed first-version phrase tuples) and a `@runtime_checkable PrototypeSimilaritySource.max_similarity_to(stimulus, prototypes) -> float | None` protocol.
2. Extend `GroundedDimensionEstimator`: add `prototype_source: PrototypeSimilaritySource`, `threat_prototypes=THREAT_PROTOTYPES`, `reward_prototypes=REWARD_PROTOTYPES`, `threat_gain=1.0`, `reward_gain=1.0`; remove the constant `threat`/`reward` fields. Compute `threat`/`reward` as `clamp(gain * max(0.0, fact), 0, 1)` where `fact = prototype_source.max_similarity_to(stimulus, prototypes)`; a `None` fact -> `0.0`.
3. The mapping is positive-correlation, bounded, deterministic, stateless; no LLM/network in the path. novelty/uncertainty/social mappings are unchanged.
4. Completion: all five dimensions derived; threat/reward from prototype similarity; range-bounded; `None`->0.
5. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.

### Task 2 - Export the new protocol
1. In `helios_v2/src/helios_v2/appraisal/__init__.py`, export `PrototypeSimilaritySource` (and `THREAT_PROTOTYPES`/`REWARD_PROTOTYPES` if useful for tests).
2. Completion: importable from `helios_v2.appraisal`.
3. Validation: import succeeds in the composition assembly module.

### Task 3 - Composition prototype-similarity fact source
1. In `helios_v2/src/helios_v2/composition/bridges.py`, add `EmbeddingPrototypeSimilaritySource(PrototypeSimilaritySource)` taking the injected `embed_text` callable. `max_similarity_to(stimulus, prototypes)`: empty stimulus content -> `None`; otherwise embed the stimulus content once, embed each prototype phrase (cached per phrase tuple to embed once across ticks), and return the max `cosine_similarity` (reuse the persistence module's `cosine_similarity`) of the stimulus vector to any prototype vector.
2. Owner-neutral: mechanical embed+cosine only; it does not know which set means threat vs reward. `03` imports neither the embedding nor persistence owner.
3. Completion: returns the stimulus's max cosine to an owner-provided phrase set; prototypes embedded once.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, when `semantic_memory_enabled`, construct `GroundedDimensionEstimator(..., prototype_source=EmbeddingPrototypeSimilaritySource(embed_text=_embed_text))`; keep `FirstVersionDimensionEstimator()` (constant threat `0.2`/reward `0.1`) otherwise.
2. No new public assembly flag; reuse the existing `semantic_memory_enabled` opt-in (same trigger as R35/R39). novelty/uncertainty/social behavior unchanged.
3. Completion: the semantic-memory assembly grounds all five `03` dimensions; default/recency/offline unchanged.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 5 - Tests
1. `test_rapid_salience_engine.py` (extend, with a fake `PrototypeSimilaritySource`): high prototype similarity -> high threat/reward; low/negative -> 0; positive correlation; `None` -> 0.0; gain scaling; range; determinism; novelty/uncertainty/social unchanged.
2. `test_runtime_composition.py` (extend): semantic assembly yields prototype-derived threat/reward (not the `0.2`/`0.1` constants), within range, flowing through `04`; default assembly keeps constant threat `0.2`/reward `0.1`. (No "scary sentence" assertions — the fake embedding has no semantics.)
3. Completion: all new/extended tests pass and assert real differences, not just presence.
4. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 6 - Documentation sync
1. `index.md`: add the R40 row (depends on `03, 34, 39`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add migration-state item 21 — `03` threat/reward now prototype-embedding-grounded (`C_engineering_hypothesis`), so all five `03` dimensions are real and the `04` reward→DA / threat→cortisol channels are now driven by real signals; prototype sets + mapping owned by `03`, mechanical fact supplied by composition; honest grounding caveat; replacements (P5, `06` memory-affect, slow LLM re-appraisal) deferred.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row — all five `03` dimensions real, with explicit grounding tiers (novelty/uncertainty `B`, social transport-fact, threat/reward `C_engineering_hypothesis` placeholder); add `40` to links; record the honest caveat.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `03` entry (threat/reward shipped via prototype embedding; `C` grounding caveat; replacements as next steps) and flip the `03` completeness note to "all five dimensions real under the semantic assembly".
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): update the `03` node label (all five dims real), last-synced to R40, test baseline count, status-summary bullet.
6. Completion: no doc/code drift.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `03` appraisal owner (`GroundedDimensionEstimator`, `RapidDimensionEstimate`, `RapidSalienceVector`) and the R39 estimator — shipped.
2. Depends on the R34 embedding substrate (`_embed_text` callable) and the persistence `cosine_similarity` helper — shipped.
3. Reuses the composition semantic-memory opt-in from R34/R35/R36/R37/R38/R39 — shipped.
4. No dependency on `06` memory-affect grounding or P5 learning (explicit future scope); stateless, no cold-start.

## 3. Files and Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (Tasks 1)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (Task 2)
3. `helios_v2/src/helios_v2/composition/bridges.py` (Task 3)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 4)
5. `helios_v2/tests/test_rapid_salience_engine.py` (Task 5)
6. `helios_v2/tests/test_runtime_composition.py` (Task 5)
7. `helios_v2/docs/requirements/index.md` (Task 6)
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 6)
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 6)
10. `helios_v2/docs/OWNER_GUIDE.md` (Task 6)
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 6)
12. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 6)
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 6)

## 4. Implementation Order

1. Task 1 (protocol + constants + mapping) — foundation; testable in isolation with a fake source.
2. Task 2 (export) — makes them available to composition.
3. Task 3 (composition source) — embed+cosine fact from the real embedding callable.
4. Task 4 (assembly wiring) — injects the prototype source into the grounded estimator under the opt-in.
5. Task 5 (tests) — alongside Tasks 1-4, finalized with the composition wiring + downstream tests.
6. Task 6 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.
2. After Tasks 3-4: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 5: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `03` computes `threat`/`reward` from the stimulus's max cosine to owner-owned prototype phrase sets via an owner-owned positive-correlation bounded mapping when the semantic-memory assembly is enabled; composition supplies only the mechanical embed+cosine fact.
2. All five `03` dimensions are real; the `04` reward→dopamine and threat→cortisol channels are now driven by real signals (a composition test confirms the wiring + downstream flow).
3. Empty content -> threat/reward `0.0`; every dimension within `[0,1]`, deterministic; no cold-start; novelty/uncertainty/social unchanged.
4. The prototype sets + mapping live in the `03` owner; `03` imports neither the embedding nor persistence owner; no LLM in the fast path; grounding recorded as `C_engineering_hypothesis` and not over-claimed.
5. The default, recency-only, and offline assemblies keep the constant estimator and current `03` behavior.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
