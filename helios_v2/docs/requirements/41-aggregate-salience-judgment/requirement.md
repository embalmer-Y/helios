# Requirement 41 - Dimension-grounded aggregate salience judgment (P3 03-owner closeout)

## 1. Background and Problem

R35/R39/R40 de-shimmed all five of the `03` appraisal owner's coarse salience dimensions (novelty, uncertainty, social, threat, reward) into real signals under the semantic-memory assembly. But the `03` owner's sixth output — the aggregate salience judgment (`RapidSalienceVector.aggregate`) — is still a constant shim: `FirstVersionAggregateEstimator.estimate_aggregate` does `del stimulus, dimensions` and returns `0.4` every tick, in every assembly. So even when all five dimensions are real, the overall coarse-salience judgment that summarizes them is a fixed number, ignoring the very dimensions it is supposed to summarize.

The `RapidSalienceVector.aggregate` contract already anticipates this: its docstring states `aggregate` is "an owner-produced overall coarse judgment. Early implementations may allow partial contribution from dimension combination, but the contract leaves room for later learned or model-assisted overall appraisal." R41 takes the "dimension combination" step: the aggregate becomes a deterministic bounded combination of the five now-real dimensions, owned by the `03` owner.

This is the natural closeout of the `03` owner's P3 de-shim: with R41 every output of `03` (all five dimensions plus the aggregate) is a real signal under the semantic-memory assembly, none remaining a constant. It is intentionally the smallest, lowest-risk slice in the series — a pure function of the dimensions already computed, requiring no new injected fact source and no new embedding/store/transport access. It only matters once the dimensions are real (R40), which is why it is sequenced here.

## 2. Goal

Replace the constant aggregate-salience shim with a deterministic dimension-grounded aggregate judgment owned by the `03` owner: when the semantic-memory assembly is enabled (where all five dimensions are real), the aggregate is a bounded convex combination of the five real dimensions with explicit first-version weights, so that the overall coarse-salience judgment measurably and traceably reflects the real dimensions it summarizes, while `03` keeps sole ownership of the aggregate semantic, the combination stays deterministic and bounded (no NN, no divergence), reads no prior-tick state, and the default assembly stays unchanged (constant `0.4`).

## 3. Functional Requirements

### 3.1 Dimension-grounded aggregate combination
1. A new aggregate judgment estimator owned by the `03` owner must compute `aggregate` from the five dimensions of the `RapidDimensionEstimate` it is given. It must consume the dimensions; it must not ignore them.
2. The combination must be a convex combination: `aggregate = clamp(sum(weight_k * dimension_k), 0, 1)` where the per-dimension weights are explicit bounded first-version constants that sum to `1.0` (so the result is inherently within `[0,1]` for in-range dimensions). At minimum the documented first-version weights must cover all five dimensions (threat, reward, novelty, uncertainty, social), each contributing non-negatively (higher dimension salience yields a not-lower aggregate).
3. The aggregate must be deterministic given the same dimensions and must read no prior-tick state.
4. The combination must be monotonic non-decreasing in each dimension (a higher value on any single dimension, others fixed, yields an aggregate no lower than before).

### 3.2 Bounded, future-learnable weights
1. The per-dimension weights must be explicit first-version bounded constants summing to `1.0`. They are deterministic now and are the surface a later P5 learning slice or a model-assisted overall appraisal replaces; they must not be a black-box model.
2. The weights are a first-version placeholder allocation, not a calibrated importance model. This must be recorded as an honest caveat (the relative weighting of threat vs reward vs novelty etc. is an engineering choice, not a measured salience prior) and not over-claimed.
3. The estimator must not introduce any runtime strategy branch keyed on hardcoded content; the combination is a fixed bounded linear combination plus clamping.

### 3.3 Real downstream effect
1. The derived aggregate must flow through the existing `RapidSalienceVector.aggregate` field unchanged, so any downstream consumer of the aggregate receives it through the existing boundary with no contract change.
2. The change must be observable: two stimuli whose real dimensions differ (for example a high-threat/high-novelty stimulus vs a low-salience stimulus) must produce measurably different aggregate values, attributable to the real dimensions rather than a constant.

### 3.4 Opt-in rollout and statelessness
1. The dimension-grounded aggregate must be enabled in the same semantic-memory assembly as R35/R39/R40 (where the five dimensions are real). The default and recency-only assemblies must keep the constant aggregate estimator (`0.4`) and behave exactly as today, because aggregating still-constant first-version dimensions carries no real signal.
2. This slice is stateless: the estimator must not read or carry prior-tick appraisal state.
3. There is no fallback path: when enabled, the aggregate is computed from the dimensions every tick. The dimensions are already validated by the `RapidSalienceVector` construction; the estimator runs before that construction and its output is range-validated by the contract.
4. The five dimension behaviors are unchanged from R35/R39/R40.

## 4. Non-Functional Requirements

1. Performance: the aggregate is one bounded linear combination per stimulus per tick; no new I/O, no embedding/store access, no LLM. It does not change the runtime stage structure.
2. Reliability and fault tolerance: for identical dimensions the aggregate must be deterministic and independent of wall-clock time, and must stay within `[0,1]` (a convex combination of in-range values plus a defensive clamp).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. The aggregate travels only through the existing `RapidSalienceVector` contract.
4. Compatibility and migration: the new aggregate estimator is additive. The default, recency-only, and offline assemblies keep the constant estimator and their current `03` behavior (constant `0.4`).

## 5. Code Behavior Constraints

1. The appraisal owner stays the sole owner of the aggregate-salience semantic. The dimension-combination must live in an owner-owned `03` aggregate estimator, not in composition glue. Composition only selects the owner-provided estimator under the opt-in; it computes no aggregate value itself.
2. The estimator must consume only the `RapidDimensionEstimate` it is given (and the stimulus for signature compatibility, which it may ignore). It must not import or reach into other owners' state, must not read prior-tick state, and must not produce downstream (gating/feeling/memory) semantics.
3. The combination must be a deterministic bounded equation (convex combination + clamp). No black-box NN, no hidden runtime strategy branch, no prior-tick state read, and no divergence outside `[0,1]`.
4. No degraded or fallback path: when enabled the aggregate is dimension-grounded every tick. When disabled, the constant first-version estimator runs unchanged.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (a new owner-owned `WeightedAggregateEstimator` implementing the existing `AggregateJudgmentEstimator` protocol; the dimension estimators and contracts are unchanged)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (export the new estimator if public to composition)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (select the weighted aggregate estimator in the semantic-memory assembly; keep `FirstVersionAggregateEstimator` otherwise)
4. `helios_v2/tests/test_rapid_salience_engine.py` (extend: aggregate from dimensions, monotonicity, range, determinism, weights sum to 1.0)
5. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly produces a dimension-driven aggregate that differs across two ticks with different dimensions; default assembly keeps constant `0.4`)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
9. `helios_v2/docs/OWNER_GUIDE.md`
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, `03` computes `aggregate` as a bounded convex combination of the five real dimensions via an owner-owned estimator; with R41 every `03` output (five dimensions + aggregate) is real, none constant.
2. Two stimuli whose real dimensions differ yield measurably different aggregate values; a higher value on any single dimension (others fixed) yields an aggregate no lower (monotonic, deterministic).
3. The aggregate stays within `[0,1]` for in-range dimensions; the first-version weights are explicit owner-owned constants summing to `1.0`; the combination is a convex combination plus clamp with no NN and no prior-tick read.
4. The first-version weights are recorded as an honest placeholder allocation (an engineering choice, not a calibrated importance prior) and not over-claimed; the P5/model-assisted replacement is recorded as explicit future scope.
5. The default, recency-only, and offline assemblies keep the constant aggregate estimator (`0.4`) and their current `03` behavior; their existing tests pass.
6. The five dimension behaviors are unchanged from R35/R39/R40.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R41 closes the `03` owner's P3 de-shim with a convex-combination aggregate. The following are explicitly anticipated future work, each via its own requirement, preserving the owner boundaries established here:

1. **P5 learning of the aggregate weights** via outcome feedback, replacing the first-version convex weights without changing the combination shape (the weights are the learnable surface).
2. **Model-assisted / non-linear overall appraisal**: a richer aggregate (e.g. interaction terms, a learned small model, or a slow `11`-LLM second-stage salience judgment feeding a secondary appraisal) replacing the first-version linear convex combination, per the `RapidSalienceVector` contract's "later learned or model-assisted overall appraisal" allowance. A slow LLM judgment is a distinct second-stage owner concern, not the fast `03` path.
3. **Affect/recency weighting**: once `04`/`05` and a memory-recency signal are richer, weight the dimensions by current affect or recency rather than fixed constants.
4. **Caveat carried forward**: the aggregate inherits the grounding strength of its inputs. While threat/reward remain the R40 `C_engineering_hypothesis` prototype anchor, the aggregate's threat/reward contribution is only as strong as that anchor; this must not be over-claimed. The aggregate strengthens automatically as its input dimensions are upgraded (e.g. R40 threat/reward replaced by memory-affect grounding).

None of these may be smuggled into this slice. R41 introduces no prior-tick state, no NN, no LLM, no new logging mechanism, and changes no owner's contract; it only makes `03`'s `aggregate` a real deterministic function of the five real dimensions.
