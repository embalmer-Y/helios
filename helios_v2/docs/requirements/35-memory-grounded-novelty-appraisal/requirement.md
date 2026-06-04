# Requirement 35 - Memory-grounded novelty appraisal (P3 first de-shim)

## 1. Background and Problem

The cognition main chain runs end to end, but the `03` rapid salience appraisal owner is `baseline_real` with composition-injected shim inputs: `FirstVersionDimensionEstimator.estimate_dimensions` returns a fixed constant vector (`threat=0.2, reward=0.1, novelty=0.6, social=0.0, uncertainty=0.3`) for every stimulus, regardless of what the stimulus actually is. The owner, its `RapidSalienceVector` contract, its validation, and its tests are all real; the values flowing into it are not.

This is exactly the kind of shim phase `P3` exists to remove. Of the five salience dimensions, **novelty** is the one with the clearest, most defensible real signal available today: in `brain.mmd`, novelty is a core fast-path appraisal signal, and the standard functional definition of novelty is "how unlike anything I already remember this is". With R33 (durable experience store) and R34 (embedding gateway + cosine similarity search) shipped, the substrate to compute that real signal now exists: embed the current stimulus, find the most similar stored experience, and derive `novelty = 1 - max_similarity`.

Today no cognitive owner consumes the R34 embedding substrate; it only powers `10` retrieval candidate ranking. Making `03` novelty real is the first cognitive-owner de-shim, the highest-leverage P3 first slice, and the proof that the embedding base built in R34 is usable by the cognition chain, advancing the locked final-goal standard `FG-1` (the chain is driven by real signals).

The other four dimensions (threat/reward/social/uncertainty) require different real signals (classifiers or LLM scoring) and are deliberately left as shim here; each is its own later P3 slice.

## 2. Goal

Replace the constant novelty value in the `03` appraisal owner with a real signal derived from memory: when memory-grounded novelty is enabled, the appraisal owner computes each stimulus's novelty as one minus the cosine similarity of the stimulus to its most similar stored experience (via the R34 embedding gateway and the R33 store's similarity search), so a stimulus resembling prior experience scores low novelty and a genuinely new stimulus scores high, while the appraisal owner keeps sole ownership of salience, never imports the embedding or persistence owners (the novelty capability is injected), and the default and shim assemblies stay unchanged.

## 3. Functional Requirements

### 3.1 Owner-injected novelty estimation
1. The `03` appraisal owner must continue to own salience and the `RapidSalienceVector`. It must not import the `34` embedding owner or the `33` persistence owner. The memory-grounded novelty capability must be injected behind a narrow owner-defined protocol (a novelty estimator the owner calls), exactly as the dimension estimator is already injected.
2. A new memory-grounded dimension estimator must compute novelty for one stimulus as `novelty = clamp(1 - max_similarity, 0, 1)`, where `max_similarity` is the highest cosine similarity between the stimulus embedding and any stored experience embedding within the bounded similarity search; the other four dimensions (threat/reward/social/uncertainty) must keep their first-version constant values in this slice.
3. When the store holds no embedded experience that can be compared (cold store, or a stimulus that cannot be embedded into a comparable vector), novelty must resolve to the explicit maximum-novelty value (`1.0`): an experience unlike anything remembered is maximally novel. This is a defined semantic, not a fallback to the old constant.
4. The novelty value must remain within the `RapidSalienceVector` `[0.0, 1.0]` contract range and must be deterministic given the same stimulus text and the same stored embeddings.

### 3.2 Real downstream effect
1. The computed novelty must flow through the existing `RapidSalienceVector` and `RapidAppraisalBatch` contracts unchanged, so downstream owners (gating, modulation) consume it through the existing boundary with no contract change.
2. The change must be observable: for two stimuli processed against the same store, a stimulus semantically close to a stored experience must yield a measurably lower novelty than a semantically distant stimulus. The difference must be attributable to real similarity, not to a constant.

### 3.3 Opt-in rollout and fail-fast
1. Memory-grounded novelty must be an explicit opt-in assembly choice, enabled only when both the R33 experience store and the R34 embedding gateway are present. When either is absent, the appraisal owner keeps the first-version constant estimator and behaves exactly as today.
2. Enabling memory-grounded novelty requires durable persistence and the embedding gateway; requesting it without both must be a composition error, consistent with the R34 semantic-memory rule.
3. An embedding failure or a store read failure while memory-grounded novelty is enabled must propagate as a hard stop. There is no silent fallback to the constant novelty value when the capability is enabled (the cold-store maximum-novelty semantic in 3.1.3 is a defined result, not a failure fallback).

## 4. Non-Functional Requirements

1. Performance: novelty computation is one embedding call plus one bounded similarity search per stimulus per tick, reusing the R34 bounded scan. It must not change runtime stage execution structure.
2. Reliability and fault tolerance: for identical stimulus text and identical stored embeddings, the novelty value must be deterministic and independent of wall-clock time.
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Novelty travels only through the existing salience contracts.
4. Compatibility and migration: the memory-grounded estimator and its wiring are additive and opt-in. The default assembly, the recency-persistent assembly, and the semantic-memory assembly (without novelty opt-in) all keep their current `03` behavior.

## 5. Code Behavior Constraints

1. The appraisal owner must stay free of any embedding/persistence import. The novelty capability is injected through an owner-defined protocol; composition binds it to the embedding gateway and the store.
2. The injected novelty estimator must compute only the novelty dimension. It must not recompute or override threat/reward/social/uncertainty, and it must not assume ownership of aggregate salience (the aggregate estimator stays owned by `03`).
3. The store and embedding owners are unchanged: the store still does not embed text, the embedding owner still holds no cognitive policy. The novelty estimator orchestrates them through their existing public surfaces only.
4. No degraded or fallback path when the capability is enabled: a missing store/embedding at assembly is a composition error; a runtime embedding/store failure is a hard stop; a cold store yields the defined maximum-novelty result.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (a memory-grounded dimension estimator implementing the existing `RapidDimensionEstimator` protocol, or a thin owner-defined novelty-estimator protocol the dimension estimator consumes)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (export the new estimator if it is public to composition)
3. `helios_v2/src/helios_v2/composition/bridges.py` (owner-neutral binding of the embedding gateway + store into the injected novelty capability)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (opt-in selection of the memory-grounded estimator when store + embedding are present; composition error otherwise)
5. `helios_v2/tests/test_appraisal_engine.py` (extend: novelty-from-similarity behavior, cold-store max novelty, deterministic)
6. `helios_v2/tests/test_runtime_composition.py` (extend: opt-in novelty assembly; near vs far stimulus novelty difference; composition error without store/embedding; default unchanged)
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
10. `helios_v2/docs/OWNER_GUIDE.md`
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The `03` appraisal owner computes novelty from real memory similarity when memory-grounded novelty is enabled, without importing the embedding or persistence owners; the capability is injected through an owner-defined protocol.
2. A stimulus semantically close to a stored experience yields a measurably lower novelty than a semantically distant stimulus, processed against the same store; the difference is attributable to cosine similarity, not a constant.
3. A cold store (no embedded experience) yields the defined maximum novelty (`1.0`) explicitly, not the old constant and not a failure.
4. The novelty value stays within `[0.0, 1.0]`, is deterministic for identical inputs, and flows through the unchanged `RapidSalienceVector`/`RapidAppraisalBatch` contracts to downstream owners.
5. Enabling memory-grounded novelty without both the store and the embedding gateway raises a composition error; a runtime embedding/store failure is a hard stop with no constant fallback.
6. The default assembly, the recency-persistent assembly, and the semantic-memory assembly without the novelty opt-in keep their current `03` constant-novelty behavior; their existing tests pass unmodified.
7. The other four salience dimensions (threat/reward/social/uncertainty) keep their first-version constant values in this slice (explicitly out of scope).
8. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R35 de-shims the novelty dimension only. The following are explicitly anticipated future P3 work, each via its own requirement, and must preserve the owner boundaries established here:

1. Real threat/reward/social/uncertainty dimensions from their own appropriate signals (classifier or LLM scoring), each a separate de-shim slice.
2. A learned or model-assisted aggregate salience judgment, replacing the constant aggregate estimator.
3. Feeding novelty (and later the other real dimensions) into a de-shimmed `04` neuromodulator dynamics model and `09` gating, so real salience measurably shapes gating thresholds.
4. Affect-weighted or recency-weighted novelty once `04`/`05` produce real signals.

None of these may be smuggled into this slice. R35 changes only the novelty dimension of `03`, introduces no cognitive ownership into the embedding/persistence owners, and adds no default-on behavior.
