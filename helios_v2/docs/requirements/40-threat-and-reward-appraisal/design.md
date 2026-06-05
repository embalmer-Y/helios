# Requirement 40 - Prototype-grounded threat and reward appraisal (design)

## 1. Design Overview

R40 de-shims the last two constant `03` dimensions — `threat` and `reward` — with a network-free prototype-embedding scorer, completing the `03` de-shim so all five dimensions are real. It generalizes the R35/R39 boundary pattern once more: the `03` owner owns the semantic (the prototype phrase sets and the cosine→salience mapping); composition supplies only the mechanical fact (embed these owner-provided phrases, return the stimulus's max cosine to a set). No LLM enters the fast path; the grounding is honestly `C_engineering_hypothesis` and annotated as such everywhere.

Three parts:

1. The `03` owner gains fixed first-version threat/reward prototype phrase sets (owner constants) and a new injected `PrototypeSimilaritySource` protocol, and extends `GroundedDimensionEstimator` to map prototype similarity to the `threat`/`reward` dimensions.
2. Composition gains a `PrototypeSimilaritySource` implementation that embeds the owner-provided phrases (once, cached) through the existing embed callable and returns the stimulus's max cosine to a phrase set.
3. Assembly wires that source into the grounded estimator under the existing semantic-memory opt-in.

## 2. Current State and Gap

After R39, `GroundedDimensionEstimator` computes `novelty` (similarity_source), `uncertainty` (ambiguity_source), `social` (social_source) and holds `threat=0.2`, `reward=0.1` as constants. The `RapidSalienceVector` and aggregate estimator are unchanged and need no change here.

Gap: `threat`/`reward` are constant, so the `04` cortisol channel (driven by threat) and dopamine channel (driven by reward) move only by the fixed constants. R40 makes both real.

## 3. Target Architecture

### 3.1 Fact source (composition-owned, mechanical fact only)

```
PrototypeSimilaritySource.max_similarity_to(stimulus, prototypes) -> float | None
```

Given a stimulus and an owner-provided tuple of prototype phrases, returns the maximum cosine similarity of the embedded stimulus content to any embedded prototype phrase, or `None` for empty stimulus content. The source caches each prototype set's embeddings (embedded once, keyed by the phrase tuple) so per-tick cost is one stimulus embedding (shared with novelty/uncertainty) plus a bounded number of cosines.

The source is purely mechanical: it embeds phrases and computes cosines. It does not know that one set means "threat" and another means "reward" — the owner passes the sets and owns their meaning.

### 3.2 Ownership

- the prototype phrase sets (the first-version definition of "what counts as threat/reward") and the cosine→salience mapping: owned by the `03` owner.
- embedding phrases + computing cosine: owned by composition glue (mechanical fact).
- `03` imports neither the embedding nor persistence owner; it reaches the embedding capability only through the injected source, exactly as R35/R39.

### 3.3 The mapping (owner-private)

The owner holds first-version prototype sets and gains:

```
THREAT_PROTOTYPES = (
    "a dangerous threat",
    "I am under attack",
    "this will cause harm",
    "an urgent emergency",
    "something is broken or failing",
)
REWARD_PROTOTYPES = (
    "a valuable reward",
    "this is helpful and good",
    "a successful achievement",
    "a positive useful outcome",
    "something beneficial and worthwhile",
)
threat_gain = 1.0   # first-version, P5-learnable
reward_gain = 1.0
```

For each dimension:
- `fact = source.max_similarity_to(stimulus, prototypes)` (max cosine, or `None`).
- `None` (empty content) -> `0.0` (no comparable input -> no prototype evidence).
- else `dimension = clamp(gain * max(0.0, fact), 0, 1)` — positive correlation, only positive similarity contributes (a stimulus dissimilar or anti-similar to the prototypes scores 0), bounded by clamp.

This differs from novelty's `1 - cosine` (novelty is *distance*; threat/reward are *proximity* to a semantic anchor). Determinism: pure arithmetic on the facts + constants. Statelessness: no prior-tick read. No cold-start: prototype vectors are fixed at assembly time.

`novelty`/`uncertainty`/`social` mappings are unchanged from R35/R39.

## 4. Data Structures

No contract change. `RapidSalienceVector`/`RapidDimensionEstimate` unchanged. New: one injected protocol + owner constants + two estimator fields.

### 4.1 New owner-side protocol (in `appraisal/engine.py`)

```python
@runtime_checkable
class PrototypeSimilaritySource(Protocol):
    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        """Max cosine similarity of the stimulus to any prototype phrase; None for no comparable input."""
```

### 4.2 Estimator extension (in `appraisal/engine.py`)

`GroundedDimensionEstimator` gains:
- `prototype_source: PrototypeSimilaritySource`
- `threat_prototypes: tuple[str, ...] = THREAT_PROTOTYPES`
- `reward_prototypes: tuple[str, ...] = REWARD_PROTOTYPES`
- `threat_gain: float = 1.0`, `reward_gain: float = 1.0`

and removes the constant `threat`/`reward` fields, computing them from the source instead. (The default constant estimator `FirstVersionDimensionEstimator` in composition keeps `threat=0.2`, `reward=0.1` for non-semantic assemblies.)

## 5. Module Changes

1. `appraisal/engine.py`: add `PrototypeSimilaritySource`, the `THREAT_PROTOTYPES`/`REWARD_PROTOTYPES` owner constants, and the threat/reward mapping in `GroundedDimensionEstimator`. `MemorySimilaritySource`/`RetrievalAmbiguitySource`/`SocialContextSource` and the R35 `MemoryGroundedDimensionEstimator` are unchanged.
2. `appraisal/__init__.py`: export `PrototypeSimilaritySource` (and the prototype constants if convenient for tests).
3. `composition/bridges.py`: add a `PrototypeSimilaritySource` impl (`EmbeddingPrototypeSimilaritySource`) that embeds phrase sets once (cached by phrase tuple) via the injected embed callable and returns the stimulus's max cosine to a set; empty stimulus content -> `None`. Reuses `cosine_similarity` from the persistence module (already used for the store). Owner-neutral: mechanical fact only.
4. `composition/runtime_assembly.py`: when `semantic_memory_enabled`, construct `GroundedDimensionEstimator(..., prototype_source=EmbeddingPrototypeSimilaritySource(embed_text=_embed_text))`; keep `FirstVersionDimensionEstimator()` otherwise.

## 6. Migration Plan

1. Add the protocol + owner constants + estimator extension (the estimator now requires a `prototype_source`).
2. Add the composition source.
3. Update the assembly's `GroundedDimensionEstimator` construction to inject the prototype source (it already constructs the estimator for R39).
4. The default assembly keeps `FirstVersionDimensionEstimator`, unchanged.

No contract rewrite; the salience vector, aggregate estimator, and appraisal batch are untouched. Because `GroundedDimensionEstimator` is only constructed in the semantic assembly, adding a required `prototype_source` field affects only that construction path plus the engine tests that build it directly.

## 7. Failure Modes and Constraints

1. Embedding failure while embedding the stimulus or prototypes: hard stop, no constant fallback (consistent with R35/R39).
2. Empty stimulus content: the source returns `None` -> threat/reward `0.0` (no stimulus embedding call).
3. Out-of-range dimension: structurally impossible (clamped to `[0,1]`).
4. Stateless: no prior-tick read. No cold-start: prototypes embedded at assembly time.
5. No LLM in the fast path; no NN; no hidden branch beyond the declared prototype sets; deterministic.
6. The prototype sets are owner constants; composition never defines what counts as threat/reward.

## 8. Observability and Logging

No new logging mechanism. Dimensions travel only through the existing `RapidSalienceVector`/`RapidAppraisalBatch`. No `logging`/`print` under `src`; guard test stays green.

## 9. Validation Strategy

1. Engine tests (`test_rapid_salience_engine.py`), with a deterministic fake `PrototypeSimilaritySource`:
   - high prototype similarity -> high threat/reward; low/negative similarity -> 0; positive-correlation and bounded;
   - `None` fact -> 0.0; determinism; range; gain scaling;
   - novelty/uncertainty/social unchanged.
2. Composition tests (`test_runtime_composition.py`):
   - the semantic assembly produces `threat`/`reward` that are prototype-derived (not the constant `0.2`/`0.1`) and within `[0,1]`, flowing through `04` unchanged (read threat/reward from the `03` stage result and confirm `04` consumed the same batch);
   - the default assembly keeps constant threat `0.2` / reward `0.1`.
3. Guard + full gate: `test_no_adhoc_logging_guard.py` plus `pytest helios_v2/tests -q` green and network-free.

Note on the deterministic fake embedding: it is a bag-of-characters bucket vector, so cosine similarity tracks character-distribution overlap, not meaning. The engine-level tests (with a fake `PrototypeSimilaritySource` returning controlled similarities) own the precise positive-correlation, gain, range, and `None`->0 assertions. The composition tests own the wiring truth (threat/reward are prototype-derived under the semantic assembly, constant under default) and the downstream `04` flow; they do not assert that a "scary-sounding" sentence scores high, because the fake embedding has no semantics.
