# Requirement 39 - Memory-grounded uncertainty and transport-grounded social appraisal (P3 fifth de-shim)

## 1. Background and Problem

R35 made the `03` appraisal owner's `novelty` dimension a real memory-grounded signal, and R36/R37/R38 made the whole `04` neuromodulator chain and both of `04`'s downstream consumers (`09` gating, `05` feeling) real. But the modulation chain still runs on only one real `03` driver: novelty. The other four `03` salience dimensions (`threat`, `reward`, `social`, `uncertainty`) are still the first-version constants hardcoded in `MemoryGroundedDimensionEstimator` (`threat=0.2, reward=0.1, social=0.0, uncertainty=0.3`). So although `04`→`05`/`09` is now real, most of what flows into `04` (reward→dopamine, threat→cortisol, uncertainty→norepinephrine) is still constant, which means those neuromodulator channels are wired but inert.

This slice de-shims the two `03` dimensions that can be grounded in real, cheap, network-free, deterministic facts today, without leaving the fast pre-attentive appraisal path:

1. `uncertainty` — grounded in retrieval ambiguity over the same embedding+store substrate R35 already uses for novelty. Novelty reads how far the stimulus is from the single best stored experience; uncertainty reads how ambiguous the match is (one dominant match vs several near-equal matches). These are distinct retrieval facts: a stimulus can be familiar (low novelty) yet ambiguous (high uncertainty) when several stored experiences match it about equally.
2. `social` — grounded in the transport provenance of the stimulus. A stimulus arriving from an external interactive-agent channel (a CLI operator, i.e. another subject) carries social salience; an internal body/background signal does not. This is a transport fact the composition root already knows (it wired the channels), not a semantic judgment.

`threat` and `reward` are intentionally NOT in this slice. Their honest grounding needs semantics ("is this dangerous / valuable"), which the fast pre-attentive `03` path must not obtain via an LLM call (the LLM is the slow `11` thought path, per `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 14). They are the next slice (R40), via a network-free prototype-embedding method whose weaker grounding will be annotated explicitly.

Per the locked selection principle, `03` must stay fast, deterministic, and network-free. Both new dimensions use only cheap facts (a bounded extra store query for the top-2 cosine similarities, and a transport-provenance lookup). No LLM, no new heavyweight dependency. As with R35, the salience semantic (the fact→dimension mapping) stays owned by the `03` owner; composition only supplies the raw facts.

## 2. Goal

De-shim the `03` appraisal owner's `uncertainty` and `social` dimensions into real deterministic signals under the semantic-memory assembly: `uncertainty` is computed from the retrieval ambiguity of the stimulus against stored experience (the margin between the top two cosine similarities) and `social` is computed from the stimulus's transport provenance (whether it originates from an external interactive-agent channel), each through an explicit bounded mapping owned by the `03` owner and fed by composition-supplied raw facts, so that real retrieval ambiguity and real social provenance measurably and traceably shape the appraisal batch (and therefore the `04`→`05`/`09` chain), while `03` keeps sole ownership of the salience mapping, stays fast/deterministic/network-free, reads no prior-tick state, and the default assembly stays unchanged. `threat` and `reward` remain first-version constants in this slice.

## 3. Functional Requirements

### 3.1 Memory-grounded uncertainty (retrieval ambiguity)
1. The `03` owner must compute `uncertainty` from a composition-supplied retrieval fact: the top-N (N>=2) cosine similarities of the stimulus to stored experience, descending. This reuses the R34 embedding substrate and the R33 store; it must remain network-free in tests (deterministic fake embedding) and must add at most one bounded store query per stimulus (a `search_similar` with a small limit).
2. The uncertainty salience mapping must live in the `03` owner (not composition). The first-version mapping must be: when there is no comparable memory (empty stimulus content, or a cold/all-non-embedded store, i.e. no hits) `uncertainty = 1.0` (a defined maximum: with no memory basis the stimulus cannot be resolved); when there is at least one hit, normalize each cosine from `[-1,1]` to `[0,1]`, let `n1`/`n2` be the top two normalized similarities (`n2 = 0.0` if only one hit), and `uncertainty = clamp(1 - (n1 - n2), 0, 1)`. A single dominant match yields low uncertainty; several near-equal matches yield high uncertainty.
3. `uncertainty` must be a distinct signal from `novelty`: for a stimulus that matches one stored experience strongly and uniquely, novelty is low and uncertainty is low; for a stimulus that matches several stored experiences about equally, uncertainty is high even though novelty may be low. A test must demonstrate this discrimination.
4. The derivation must be deterministic for the same stimulus and stored vectors and must read no prior-tick state.

### 3.2 Transport-grounded social salience
1. The `03` owner must compute `social` from a composition-supplied raw transport fact: a bounded `social_presence` value in `[0,1]` indicating whether the stimulus originates from an external interactive-agent channel (the composition root owns the channel-to-presence classification, since it wired the channels). `03` must not hardcode channel-name knowledge.
2. The social salience mapping must live in the `03` owner. The first-version mapping must be `social = clamp(social_floor + social_gain * social_presence, 0, 1)` with explicit bounded first-version constants. The mapping is owned by `03`; the raw presence fact is owned by composition.
3. `social` must be observably driven by the real presence fact: a stimulus from an external interactive-agent channel must yield measurably higher `social` than an internal body/background stimulus.
4. The derivation must be deterministic and read no prior-tick state.

### 3.3 Honest grounding scope
1. `uncertainty` grounding is `B_functional_inspiration`-level (retrieval ambiguity is a reasonable functional proxy for categorization uncertainty, not a calibrated confidence). This must be recorded explicitly and not over-claimed.
2. `social` grounding does NOT require the embedding/store substrate; it is a pure transport fact. This slice bundles it under the existing semantic-memory opt-in to keep a single rollout switch, but this coupling is incidental and must be documented as such. A future slice may enable social grounding in the channel-bound assembly independently of semantic memory.
3. `threat` and `reward` remain first-version constants in this slice; their de-shim (network-free prototype-embedding method, weaker `C_engineering_hypothesis` grounding) is the explicitly-scoped next slice (R40) and must be annotated thoroughly when it lands.

### 3.4 Opt-in rollout and statelessness
1. The de-shimmed `uncertainty` and `social` dimensions must be active in the assembly variant where `03` already grounds novelty (the semantic-memory assembly, the same opt-in as R35/R36/R37/R38). The default and recency-only assemblies must keep the first-version constant estimator and behave exactly as today.
2. This slice is stateless: the mappings must not read or carry prior-tick appraisal state.
3. There is no fallback path: when enabled, the facts are derived every tick. A runtime embedding/store failure (for the uncertainty fact) is a hard stop with no constant fallback, consistent with R35. Empty stimulus content yields the defined maxima without an embedding call (uncertainty `1.0`), consistent with R35 novelty.
4. `novelty` behavior is unchanged from R35; `threat`/`reward` remain the first-version constants.

## 4. Non-Functional Requirements

1. Performance: the fast appraisal path stays fast and network-free. Uncertainty reuses one bounded store query (raised to fetch the top two hits instead of one); social adds a constant-time transport lookup. No LLM, no new heavyweight dependency.
2. Reliability and fault tolerance: for identical inputs the produced dimensions must be deterministic and independent of wall-clock time, and must stay within `[0,1]` (clamped, consistent with `RapidSalienceVector`).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Dimensions travel only through the existing `RapidSalienceVector`/`RapidAppraisalBatch` contracts.
4. Compatibility and migration: the new estimator and its injected fact sources are additive. The default, recency-only, and offline assemblies keep the constant estimator and their current `03` behavior.

## 5. Code Behavior Constraints

1. The appraisal owner stays the sole owner of the salience mapping. The uncertainty and social mappings must live in an owner-owned `03` dimension estimator, not in composition glue. Composition may only supply the raw retrieval facts (top-N similarities) and the raw transport fact (social presence).
2. The fact sources must consume only what they are given (the stimulus, the store, the embedding callable, the transport provenance). `03` must not import the embedding, persistence, or channel owners; it reaches them solely through injected sources, exactly as R35.
3. The mappings must be deterministic bounded equations (clamp). No black-box NN, no LLM in the fast path, no hidden runtime strategy branch, no prior-tick state read, and no divergence outside `[0,1]`.
4. No degraded or fallback path: when enabled, the facts are derived every tick; an embedding/store failure is a hard stop. When disabled, the first-version constant estimator runs unchanged.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (a generalized owner-owned dimension estimator grounding novelty + uncertainty + social; new injected fact-source protocols for retrieval ambiguity and social presence; the aggregate estimator and contracts are unchanged)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (export the new estimator and source protocols if public to composition)
3. `helios_v2/src/helios_v2/composition/bridges.py` (a retrieval-fact source returning the top-N similarities and a social-context source returning the presence fact; both owner-neutral glue reaching the embedding/store and the transport provenance)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (select the generalized grounded estimator in the semantic-memory assembly; keep the constant estimator otherwise)
5. `helios_v2/tests/test_rapid_salience_engine.py` (extend: uncertainty from ambiguity, novelty-vs-uncertainty discrimination, social from presence, determinism, range, cold-store maxima)
6. `helios_v2/tests/test_runtime_composition.py` (extend: semantic assembly produces real uncertainty/social; ambiguous vs unique match differs in uncertainty; external vs internal stimulus differs in social; default assembly unchanged)
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
10. `helios_v2/docs/OWNER_GUIDE.md`
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, `03` computes `uncertainty` from the top-two cosine similarities of the stimulus to stored experience via an owner-owned mapping; a stimulus matching several stored experiences about equally yields measurably higher uncertainty than one matching a single experience uniquely, and this differs from the novelty signal (the discrimination test passes).
2. Under the semantic-memory assembly, `03` computes `social` from a composition-supplied transport presence fact via an owner-owned mapping; a stimulus from an external interactive-agent channel yields measurably higher `social` than an internal body/background stimulus.
3. A cold/all-non-embedded store or empty stimulus content yields the defined maximum `uncertainty = 1.0` (no embedding call for empty content), consistent with the R35 novelty cold-store semantics; every produced dimension stays within `[0,1]`, deterministic for identical inputs.
4. `novelty` behavior is unchanged from R35; `threat` and `reward` remain the first-version constants; the fast appraisal path makes no LLM call and stays network-free in tests.
5. The uncertainty and social mappings live in the `03` owner; composition supplies only raw facts and `03` imports neither the embedding, persistence, nor channel owners.
6. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant estimator and their current `03` behavior; their existing tests pass (R35 novelty behavior preserved).
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R39 de-shims `uncertainty` and `social`. The following are explicitly anticipated future work, each via its own requirement, preserving the owner boundaries established here:

1. `threat`/`reward` de-shim via a network-free prototype-embedding method (R40): embed a small assembled set of threat/reward prototype phrases and score each dimension by the stimulus's maximum cosine to the prototype set. This stays in the fast path but its grounding is `C_engineering_hypothesis` (the prototype set is a hand-authored, language-centric design choice); it must be annotated thoroughly and never over-claimed, with the prototype set as the surface a later learning slice or a memory-affect grounding replaces.
2. A slow re-appraisal path (second-stage appraisal) that may use the `11` LLM to refine threat/reward/social with real semantics, feeding a secondary appraisal rather than the fast `03` path. This is a distinct owner concern from the fast pre-attentive `03`.
3. Memory-affect grounding of `reward`/`threat` once `06` persists outcome valence, so the dimensions reflect the good/bad outcomes of similar past experience rather than prototype similarity.
4. P5 learning of the uncertainty/social/threat/reward mapping coefficients, replacing the first-version constants without changing the equation shape.
5. Enabling `social` grounding in the channel-bound assembly independently of semantic memory, since social is a transport fact and does not require the embedding/store substrate.
6. Calibrated uncertainty (a real predictive-model confidence/prediction-error) replacing the first-version retrieval-ambiguity proxy.

None of these may be smuggled into this slice. R39 introduces no prior-tick state, no NN, no LLM in the fast path, no new logging mechanism, and changes no owner's contract; it only makes `03`'s `uncertainty` and `social` real deterministic functions of retrieval ambiguity and transport provenance.
