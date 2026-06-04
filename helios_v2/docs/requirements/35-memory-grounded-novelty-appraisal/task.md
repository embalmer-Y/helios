# Requirement 35 - Memory-grounded novelty appraisal (tasks)

## 1. Task Breakdown

### Task 1 - Appraisal owner: similarity source protocol + memory-grounded estimator
1. In `helios_v2/src/helios_v2/appraisal/engine.py`, add the owner-defined `MemorySimilaritySource` protocol (`max_similarity_for(stimulus) -> float | None`, a retrieval fact in `[-1, 1]` or `None`) and `MemoryGroundedDimensionEstimator` (implements `RapidDimensionEstimator`; owns the novelty salience mapping `novelty = 1 - similarity`, `None -> 1.0`, clamped/rounded into `[0, 1]`; threat/reward/social/uncertainty kept at first-version constants).
2. Export `MemorySimilaritySource` and `MemoryGroundedDimensionEstimator` from `helios_v2/src/helios_v2/appraisal/__init__.py`.
3. The estimator must not import embedding/persistence; it only calls the injected `MemorySimilaritySource`. The `1 - similarity` salience semantic lives in `03`, not in the source. The aggregate estimator is untouched.
4. Completion: the estimator returns the four constants unchanged and a novelty in `[0, 1]` derived from the injected similarity fact (`None -> 1.0`).
5. Validation: `pytest helios_v2/tests/test_appraisal_engine.py -q`.

### Task 2 - Composition: memory-grounded similarity source + opt-in wiring
1. In `helios_v2/src/helios_v2/composition/bridges.py`, add `MemoryGroundedSimilaritySource` (owner-neutral glue): `embed stimulus.content -> store.search_similar(limit=1) -> return top cosine similarity`, with empty content -> `None` (no embed call) and zero hits -> `None`. It returns a raw cosine fact (or `None`), never a novelty value. It receives `embed_text` (callable) and `store`; it imports the `ExperienceStore` type only, never the embedding owner.
2. In `helios_v2/src/helios_v2/composition/runtime_assembly.py`, select `MemoryGroundedDimensionEstimator(similarity_source=MemoryGroundedSimilaritySource(embed_text=_embed_text, store=experience_store))` for the `03` engine when both `experience_store` and `embedding_gateway` are present; otherwise keep `FirstVersionDimensionEstimator`. Reuse the existing `_embed_text` callable (same embedding profile as the store writes).
3. No new public assembly flag: the trigger is the existing `embedding_gateway` (which R34 already requires to come with `experience_store`).
4. Completion: a semantic-memory assembly runs a tick whose `03` novelty is real; default/recency assemblies unchanged.
5. Validation: `pytest helios_v2/tests/test_runtime_composition.py -q`.

### Task 3 - Tests
1. `test_appraisal_engine.py` (extend): four constants unchanged; near vs far novelty via a `MemorySimilaritySource` double (high similarity -> low novelty; low/negative similarity -> high novelty); `None` similarity -> novelty `1.0`; the salience mapping (`1 - sim`) is exercised in `03`, not the double; determinism; range `[0, 1]`.
2. `test_runtime_composition.py` (extend): semantic-memory assembly yields lower novelty for a stimulus near a seeded record than for a far one (read from the `03` stage result); novelty flows through `RapidSalienceVector` unchanged; default + recency-only assemblies keep novelty `0.6`; embedding-failure provider hard-stops a grounding-enabled tick (no constant fallback); empty stimulus content yields novelty `1.0` without an embed call.
3. Completion: all new/extended tests pass; the near-vs-far test asserts a real similarity-driven difference, not just presence.
4. Validation: `pytest helios_v2/tests/test_appraisal_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_no_adhoc_logging_guard.py -q`.

### Task 4 - Documentation sync
1. `index.md`: add the R35 row (depends on `03, 33, 34`), maturity per evidence.
2. `ARCHITECTURE_BOUNDARIES.md`: record the `03` novelty de-shim and the owner-neutral novelty-source binding (composition injects `embed_text` + store into `03`; `03` imports neither embedding nor persistence); note the cross-register first-version caveat.
3. `BRAIN_ARCHITECTURE_COMPARISON.md`: note `03` novelty is now memory-grounded (the first cognitive consumer of the R34 embedding substrate); keep the remaining `03` dimensions and other shim owners as open P3 gaps.
4. `OWNER_GUIDE.md` + `OWNER_GUIDE.zh-CN.md`: flip `03` novelty in the staged plan from "in progress" to "shipped (R35)"; keep the remaining staged items (method B, other four dimensions, aggregate, downstream coupling).
5. `PROGRESS_FLOW.en.md` + `PROGRESS_FLOW.zh-CN.md` (same change set): note `03` novelty is real under the semantic-memory assembly; update last-synced to R35 and the test baseline count.
6. Completion: no doc/code drift across index, boundaries, comparison, both owner guides, both flow maps.
7. Validation: manual review + `getDiagnostics` on changed spec docs.

## 2. Dependencies

1. Depends on `03` appraisal (`RapidDimensionEstimator` protocol, `RapidSalienceVector`) — shipped.
2. Depends on `34` embedding gateway (`embed_text` callable) and `33` store (`search_similar`) — shipped.
3. Reuses the composition `_embed_text` callable and the `embedding_gateway`/`experience_store` opt-in from R34 — shipped.
4. No dependency on `04`/`09` (downstream coupling is a later slice).

## 3. Files and Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (Task 1)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (Task 1)
3. `helios_v2/src/helios_v2/composition/bridges.py` (Task 2)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (Task 2)
5. `helios_v2/tests/test_appraisal_engine.py` (Task 3)
6. `helios_v2/tests/test_runtime_composition.py` (Task 3)
7. `helios_v2/docs/requirements/index.md` (Task 4)
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 4)
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md` (Task 4)
10. `helios_v2/docs/OWNER_GUIDE.md` (Task 4)
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` (Task 4)
12. `helios_v2/docs/PROGRESS_FLOW.en.md` (Task 4)
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` (Task 4)

## 4. Implementation Order

1. Task 1 (appraisal owner protocol + estimator) — foundation; testable in isolation with a `NoveltySource` double.
2. Task 2 (composition novelty source + opt-in wiring) — binds the real capability.
3. Task 3 (tests) — alongside Tasks 1-2, finalized with the near-vs-far composition test.
4. Task 4 (docs) — last, once behavior is evidenced.

## 5. Validation Plan

1. After Task 1: `pytest helios_v2/tests/test_appraisal_engine.py -q`.
2. After Task 2: `pytest helios_v2/tests/test_runtime_composition.py -q`.
3. After Task 3: the two suites above plus `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`.
4. Full gate: `pytest helios_v2/tests -q` (must stay green and network-free).

## 6. Completion Criteria

1. `03` computes novelty from real memory similarity when the semantic-memory assembly is enabled, without importing the embedding or persistence owners (capability injected through `NoveltySource`).
2. A stimulus near a stored experience yields a measurably lower novelty than a distant one; the difference is similarity-driven, not constant.
3. Empty content and a cold store both yield the defined maximum novelty `1.0`; empty content does not call the embed capability; a runtime embedding/store failure is a hard stop with no constant fallback.
4. Novelty stays in `[0, 1]`, is deterministic for identical inputs, and flows through the unchanged `RapidSalienceVector`/`RapidAppraisalBatch` contracts.
5. The other four dimensions and the aggregate estimator are unchanged; default and recency-only assemblies keep constant novelty.
6. `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, both `OWNER_GUIDE` files, and both `PROGRESS_FLOW` maps are updated in the same change set.
7. The single-logging-mechanism guard and the full test suite remain green and network-free.
