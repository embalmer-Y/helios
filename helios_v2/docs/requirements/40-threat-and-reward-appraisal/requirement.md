# Requirement 40 - Prototype-grounded threat and reward appraisal (P3 sixth de-shim)

## 1. Background and Problem

R35 de-shimmed the `03` appraisal owner's `novelty` dimension, and R39 de-shimmed `uncertainty` and `social`. Three of `03`'s five salience dimensions are now real. The last two — `threat` and `reward` — remain the first-version constants in `GroundedDimensionEstimator` (`threat=0.2`, `reward=0.1`).

This matters beyond `03`. R36 made the `04` neuromodulator levels derive from the appraisal batch (reward→dopamine, threat→cortisol, novelty/uncertainty→norepinephrine), and R37/R38 made `04`'s downstream consumers (`09` gating, `05` feeling) real. But the `reward→dopamine` and `threat→cortisol` channels are wired to constants: they move only by the fixed `threat=0.2`/`reward=0.1` every tick. So those two neuromodulator channels are structurally live but functionally inert. De-shimming `threat`/`reward` is the single change that makes the whole `03→04→05/09` chain driven by real signals on every channel.

Unlike novelty (distance from stored memory) or uncertainty (retrieval ambiguity), threat and reward are intrinsically semantic: they ask "is this dangerous?" / "is this valuable?". The fast pre-attentive `03` path must not obtain that judgment via an LLM call (the LLM is the slow `11` thought path, per `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 14). The chosen first-version method is therefore a network-free prototype-embedding scorer: a small assembled set of threat prototype phrases and reward prototype phrases is embedded once (through the same `34` embedding substrate the store uses), and each dimension is scored by the stimulus's maximum cosine similarity to its prototype set.

This method is honestly weak. The prototype phrase set is a hand-authored, English-centric design choice; it is a placeholder semantic anchor, not a calibrated affective model. Its grounding is `C_engineering_hypothesis`. This requirement must annotate that limitation thoroughly everywhere it is recorded and must never over-claim the result as real threat/reward understanding. The prototype set is explicitly the surface that a later P5 learning slice, or a `06` memory-affect grounding (scoring reward/threat from the good/bad outcomes of similar past experience), replaces.

Per the locked owner-boundary discipline established by R35/R39, the semantic of "what counts as threat/reward" (the prototype phrase set and the cosine→salience mapping) stays owned by the `03` owner; composition supplies only the mechanical fact (embed these phrases, return the stimulus's cosine to them). `03` imports neither the embedding nor the persistence owner.

## 2. Goal

De-shim the `03` appraisal owner's `threat` and `reward` dimensions into real deterministic signals under the semantic-memory assembly: each dimension is computed from the maximum cosine similarity of the stimulus to an owner-owned set of prototype phrases for that dimension (threat prototypes, reward prototypes), embedded through the existing `34` substrate, through an explicit bounded positive-correlation mapping owned by the `03` owner and fed by a composition-supplied mechanical similarity fact, so that all five `03` dimensions are now real and the `04` reward→dopamine and threat→cortisol channels become driven by real signals, while `03` keeps sole ownership of the prototype set and the salience mapping, stays fast/deterministic/network-free/LLM-free, reads no prior-tick state, and the default assembly stays unchanged. The grounding is honestly recorded as `C_engineering_hypothesis` (a placeholder prototype anchor, not a calibrated affective model).

## 3. Functional Requirements

### 3.1 Prototype-grounded threat and reward
1. The `03` owner must own a fixed first-version set of threat prototype phrases and reward prototype phrases (explicit owner constants). These phrases encode the owner's first-version definition of "what counts as threat / reward"; they must not live in composition glue.
2. The `03` owner must compute `threat` and `reward` from a composition-supplied mechanical fact: given a stimulus and a set of prototype phrases, the maximum cosine similarity of the stimulus to any phrase in that set (or `None` when there is no comparable input, e.g. empty stimulus content). This reuses the `34` embedding substrate; it must remain network-free in tests (deterministic fake embedding).
3. The cosine→salience mapping must live in the `03` owner and must be positive-correlation and bounded: `dimension = clamp(gain * max(0.0, max_cosine), 0, 1)` with an explicit bounded first-version `gain` per dimension (a stimulus more similar to the threat prototypes yields higher threat). A `None` fact (empty content) yields `0.0` (no comparable input → no prototype evidence), distinct from a present-but-dissimilar stimulus.
4. The derivation must be deterministic for the same stimulus and prototype embeddings and must read no prior-tick state.

### 3.2 Bounded, future-replaceable anchor
1. The prototype phrase sets and the per-dimension `gain` constants must be explicit first-version values. They are deterministic now and are the surface a later slice (P5 learning, or `06` memory-affect grounding) replaces; they must not be a black-box model.
2. The scorer must not introduce any new runtime strategy branch keyed on hardcoded content beyond the declared prototype sets; the mapping is a fixed bounded positive-correlation function plus clamping.

### 3.3 Real downstream effect
1. The derived `threat`/`reward` must flow through the existing `RapidSalienceVector`/`RapidAppraisalBatch` contracts unchanged, so `04` receives them through the existing boundary with no contract change.
2. The change must be observable end to end: a stimulus whose content is close to the threat prototypes must yield measurably higher `threat` (and through `04`, higher cortisol) than a neutral stimulus; a stimulus close to the reward prototypes must yield higher `reward` (and through `04`, higher dopamine). The difference must be attributable to real prototype similarity, not a constant.

### 3.4 Honest grounding scope
1. The prototype-embedding method is `C_engineering_hypothesis`-level grounding: the prototype phrase set is a hand-authored, English-centric placeholder anchor, not a calibrated affective model. This must be recorded explicitly in the requirement, design, `OWNER_GUIDE` (both languages), and `BRAIN_ARCHITECTURE_COMPARISON`, and must never be over-claimed as real threat/reward understanding.
2. The anticipated replacements (P5 learning of the gains/prototypes; `06` memory-affect grounding from past outcome valence; a slow LLM-based re-appraisal as a distinct second-stage owner concern, not the fast `03` path) must be recorded as explicit future scope.

### 3.5 Opt-in rollout and statelessness
1. The de-shimmed `threat` and `reward` dimensions must be active in the same semantic-memory assembly as R35/R39 (the only assembly with the embedding substrate). The default and recency-only assemblies must keep the first-version constant estimator and behave exactly as today.
2. There is no cold-start dependency: the prototype phrases are embedded once at assembly time and do not depend on accumulated experience, so threat/reward are real from the first tick (unlike novelty, which starts at the cold-store maximum).
3. This slice is stateless: the mapping must not read or carry prior-tick appraisal state.
4. There is no fallback path: when enabled, the fact is derived every tick. A runtime embedding failure is a hard stop with no constant fallback, consistent with R35/R39. Empty stimulus content yields `threat = reward = 0.0` without an embedding call for the stimulus.
5. `novelty`, `uncertainty`, and `social` behavior is unchanged from R35/R39.

## 4. Non-Functional Requirements

1. Performance: the fast appraisal path stays fast and network-free. Prototype phrases are embedded once at assembly time (not per tick); per tick the scorer embeds the stimulus once (shared with the novelty/uncertainty fact) and computes a bounded number of cosines against the cached prototype vectors. No LLM, no new heavyweight dependency.
2. Reliability and fault tolerance: for identical inputs the produced dimensions must be deterministic and independent of wall-clock time, and must stay within `[0,1]` (clamped, consistent with `RapidSalienceVector`).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Dimensions travel only through the existing appraisal contracts.
4. Compatibility and migration: the new prototype scorer and its injected fact source are additive. The default, recency-only, and offline assemblies keep the constant estimator and their current `03` behavior.

## 5. Code Behavior Constraints

1. The appraisal owner stays the sole owner of the threat/reward salience semantic. The prototype phrase sets and the cosine→salience mapping must live in the `03` owner, not in composition glue. Composition may only supply the mechanical fact (embed these owner-provided phrases, return the stimulus's max cosine to them).
2. The fact source must consume only the stimulus, the owner-provided prototype phrases, and the embedding callable. `03` must not import the embedding or persistence owners; it reaches the embedding capability solely through the injected source, exactly as R35/R39.
3. The mapping must be a deterministic bounded positive-correlation equation (clamp). No black-box NN, no LLM in the fast path, no hidden runtime strategy branch beyond the declared prototype sets, no prior-tick state read, and no divergence outside `[0,1]`.
4. No degraded or fallback path: when enabled, the fact is derived every tick; an embedding failure is a hard stop. When disabled, the first-version constant estimator runs unchanged.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/appraisal/engine.py` (the owner-owned prototype phrase sets, a new injected `PrototypeSimilaritySource` protocol, and the threat/reward mapping inside `GroundedDimensionEstimator`; the aggregate estimator and contracts are unchanged)
2. `helios_v2/src/helios_v2/appraisal/__init__.py` (export the new source protocol if public to composition)
3. `helios_v2/src/helios_v2/composition/bridges.py` (a prototype-similarity fact source that embeds the owner-provided phrases once and returns the stimulus's max cosine to a phrase set; owner-neutral glue reaching only the embedding callable)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (wire the prototype-similarity source into the grounded estimator in the semantic-memory assembly; keep the constant estimator otherwise)
5. `helios_v2/tests/test_rapid_salience_engine.py` (extend: threat/reward from prototype similarity, positive correlation, determinism, range, empty-content zero)
6. `helios_v2/tests/test_runtime_composition.py` (extend: threat-like vs neutral stimulus differs in threat and downstream cortisol; reward-like differs in reward and dopamine; default assembly unchanged)
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
10. `helios_v2/docs/OWNER_GUIDE.md`
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. Under the semantic-memory assembly, `03` computes `threat` and `reward` from the stimulus's maximum cosine similarity to owner-owned prototype phrase sets via an owner-owned positive-correlation bounded mapping; all five `03` dimensions are now real.
2. With a fake `PrototypeSimilaritySource` controlling similarity (engine level), higher prototype similarity yields measurably higher `threat`/`reward` (positive correlation), and through the existing `04` derivation a higher threat raises cortisol and a higher reward raises dopamine; a composition test confirms the wiring (threat/reward are prototype-derived, not the `0.2`/`0.1` constants) and the downstream `04` flow. (The deterministic fake embedding is a bag-of-characters function with no semantics, so the precise similarity-correlation assertion lives at the engine level, not on "scary-sounding" sentences.)
3. Empty stimulus content yields `threat = reward = 0.0` (no comparable input); every produced dimension stays within `[0,1]`, deterministic for identical inputs; there is no cold-start dependency (threat/reward are real from the first tick).
4. The prototype phrase sets and the per-dimension gains are explicit owner-owned first-version constants; the mapping is a bounded positive-correlation clamp with no NN and no LLM in the fast path; the grounding is recorded as `C_engineering_hypothesis` and not over-claimed.
5. The threat/reward semantic (prototype sets + mapping) lives in the `03` owner; composition supplies only the mechanical embed+cosine fact and `03` imports neither the embedding nor persistence owner.
6. `novelty`/`uncertainty`/`social` behavior is unchanged from R35/R39; the default, recency-only, and offline assemblies keep the constant estimator and their current `03` behavior; their existing tests pass.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R40 de-shims `threat`/`reward` via a placeholder prototype-embedding anchor. The following are explicitly anticipated future work, each via its own requirement, preserving the owner boundaries established here:

1. `06` memory-affect grounding: once `06` persists outcome valence, score `reward`/`threat` from the good/bad outcomes of similar past experience rather than prototype similarity, replacing the hand-authored anchor with experience-grounded affect.
2. P5 learning of the prototype gains and/or the prototype set, replacing the first-version constants without changing the equation shape.
3. A slow re-appraisal path (second-stage appraisal) that may use the `11` LLM to refine threat/reward with real semantics, feeding a secondary appraisal rather than the fast `03` path. This is a distinct owner concern from the fast pre-attentive `03`.
4. Multilingual / non-phrase prototype grounding to retire the English-centric limitation of the first-version phrase set.
5. The aggregate salience estimator de-shim (now that all five dimensions are real, the constant aggregate estimator can become a learned or model-assisted overall judgment).

None of these may be smuggled into this slice. R40 introduces no prior-tick state, no NN, no LLM in the fast path, no new logging mechanism, and changes no owner's contract; it only makes `03`'s `threat` and `reward` real deterministic functions of prototype similarity, with the honest `C_engineering_hypothesis` caveat recorded throughout.
