# Requirement 39 - Memory-grounded uncertainty and transport-grounded social appraisal (tasks)

## 1. Task Breakdown

### Task 1 - Owner-side fact-source protocols and generalized estimator
1. In `helios_v2/src/helios_v2/appraisal/engine.py`, add two `@runtime_checkable` protocols: `RetrievalAmbiguitySource.top_similarities_for(stimulus) -> tuple[float, ...]` (top-N cosines descending; empty when no comparable memory) and `SocialContextSource.social_presence_for(stimulus) -> float` (raw transport presence fact in `[0,1]`).
2. Add `GroundedDimensionEstimator(RapidDimensionEstimator)` taking `similarity_source` (novelty, R35 semantics), `ambiguity_source` (uncertainty), `social_source` (social), plus `threat=0.2`, `reward=0.1`, `social_floor=0.0`, `social_gain=1.0` constants.
3. `estimate_dimensions`: novelty = R35 mapping from `similarity_source` (unchanged); uncertainty: empty tuple -> `1.0`, else normalize cosines via `(c+1)/2`, `uncertainty = clamp(1 - (n1 - n2), 0, 1)` with `n2=0.0` for a single hit; social = `clamp(social_floor + social_gain * social_presence, 0, 1)`; threat/reward = the constants. Keep `MemorySimilaritySource`/`MemoryGroundedDimensionEstimator` (R35) unchanged.
4. Completion: deterministic, range-bounded dimensions; uncertainty distinct from novelty; stateless; no LLM/network.
5. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.

### Task 2 - Export the new protocols and estimator
1. In `helios_v2/src/helios_v2/appraisal/__init__.py`, export `RetrievalAmbiguitySource`, `SocialContextSource`, `GroundedDimensionEstimator`.
2. Completion: importable from `helios_v2.appraisal`.
3. Validation: import succeeds in the composition assembly module.

### Task 3 - Composition fact sources
1. In `helios_v2/src/helios_v2/composition/bridges.py`, add a `RetrievalAmbiguitySource` impl that embeds `stimulus.content` via the existing embed callable and runs the store `search_similar(limit>=2)`, returning the top-N cosines descending (empty tuple for empty content or a cold/all-non-embedded store), and a `SocialContextSource` impl that returns a bounded social-presence fact from the stimulus transport provenance (external interactive-agent channel -> high; internal body/background -> low/zero). Optionally share one embed+search with the existing novelty source to avoid a second embedding pass.
2. Both are owner-neutral glue: raw facts only, no salience mapping. `03` imports neither embedding, persistence, nor channel owners.
3. Completion: facts are produced from the real store/transport; composition computes no salience.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 4 - Composition opt-in wiring
1. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, when `semantic_memory_enabled`, build the appraisal engine with `GroundedDimensionEstimator(similarity_source=..., ambiguity_source=..., social_source=...)`; keep `FirstVersionDimensionEstimator()` otherwise.
2. No new public assembly flag; reuse the existing `semantic_memory_enabled` opt-in (same trigger as R35/R36/R37/R38). Novelty behavior must remain identical to R35.
3. Completion: the semantic-memory assembly grounds novelty + uncertainty + social; default/recency/offline assemblies are unchanged.
4. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 5 - Tests
1. `test_rapid_salience_engine.py` (extend): one strong unique match -> low uncertainty; several near-equal matches -> high uncertainty; familiar-but-ambiguous discrimination (low novelty + high uncertainty); empty similarities -> uncertainty `1.0`; high vs low social_presence -> higher vs lower social; range; determinism; threat/reward unchanged constants; novelty unchanged.
2. `test_runtime_composition.py` (extend): semantic assembly yields ambiguity-driven uncertainty differing between unique vs ambiguous match; external interactive-agent stimulus yields higher social than internal; default assembly keeps constant uncertainty `0.3` / social `0.0`.
3. Completion: all new/extended tests pass and assert real differences, not just presence.
4. Validation: `pytest helios_v2/tests/test_rapid_salience_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 6 - Documentation sync
1. `index.md`: add the R39 row (depends on `03, 33, 34, 35`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: add migration-state item 20 — `03` uncertainty now memory-grounded (retrieval ambiguity, B_functional_inspiration) and social transport-grounded; mappings owned by `03`, facts supplied by composition; threat/reward still constant (R40 next); social bundled under the semantic opt-in incidentally (documented).
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: update the `03-07` row to note three of five `03` dimensions are now real (novelty, uncertainty, social) with honest grounding levels; threat/reward remain constant pending R40; add `39` to links.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: update the `03` entry (uncertainty + social shipped; honest grounding caveats; threat/reward next via prototype-embedding R40).
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): update the `03` node label, last-synced to R39, the test baseline count, and a status-summary bullet.
6. Completion: no doc/code drift across index, boundaries, comparison, both owner guides, both flow maps.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `03` appraisal owner (`RapidDimensionEstimator`, `RapidDimensionEstimate`, `RapidSalienceVector`, the R35 `MemorySimilaritySource`) — shipped.
2. Depends on the R34 embedding substrate and R33 store (`search_similar`) for the ambiguity fact — shipped.
3. Reuses the composition semantic-memory opt-in from R34/R35/R36/R37/R38 — shipped.
4. No dependency on threat/reward grounding (R40) or any appraisal-state carry (stateless).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (Task 1)
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

1. Task 1 (protocols + generalized estimator) — foundation; testable in isolation with fake sources.
2. Task 2 (export) — makes them available to composition.
3. Task 3 (composition fact sources) — produce real facts from store/transport.
4. Task 4 (assembly opt-in wiring) — binds the estimator under the semantic-memory flag.
5. Task 5 (tests) — alongside Tasks 1-4, finalized with the composition ambiguity/social tests.
6. Task 6 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_rapid_salience_engine.py -q`.
2. After Tasks 3-4: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 5: the suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `03` computes `uncertainty` from retrieval ambiguity (top-two cosine margin) and `social` from transport presence via owner-owned mappings when the semantic-memory assembly is enabled; composition supplies only raw facts.
2. Ambiguous match -> higher uncertainty than unique match, and uncertainty is distinct from novelty (the discrimination test passes); external interactive-agent stimulus -> higher social than internal.
3. Cold store / empty content -> uncertainty `1.0`; every dimension within `[0,1]`, deterministic; novelty unchanged from R35; threat/reward still constant; fast path network-free with no LLM.
4. The mappings live in the `03` owner; `03` imports neither embedding, persistence, nor channel owners.
5. The default, recency-only, and offline assemblies keep the constant estimator and current `03` behavior.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
