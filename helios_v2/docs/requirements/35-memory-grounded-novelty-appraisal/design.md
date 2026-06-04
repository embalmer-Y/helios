# Requirement 35 - Memory-grounded novelty appraisal (design)

## 1. Design Overview

R35 makes the `03` appraisal owner's `novelty` dimension a real signal derived from memory, without changing any other dimension and without `03` importing the embedding or persistence owners. It is the first cognitive-owner de-shim of phase P3 and the first cognitive consumer of the R34 embedding substrate.

Three additive, opt-in pieces:

1. A narrow owner-defined novelty-source protocol in `helios_v2.appraisal`, and a memory-grounded dimension estimator that computes `novelty = clamp(1 - max_similarity, 0, 1)` while keeping the other four dimensions at their first-version constants.
2. An owner-neutral composition binding that wires the R34 embedding gateway + the R33 store's `search_similar` into one injected novelty source (`embed stimulus.content -> store.search_similar -> 1 - top similarity`), using the same embedding profile the store was written with so the vectors are comparable.
3. Opt-in selection in `assemble_runtime`: when both the experience store and the embedding gateway are present, `03` is assembled with the memory-grounded estimator; requesting novelty grounding without both is a `CompositionError`.

Everything stays within the existing `RapidSalienceVector`/`RapidAppraisalBatch` contracts. No downstream contract changes; novelty simply becomes real.

## 2. Current State and Gap

Current state:

1. `03` `RapidSalienceAppraisalEngine` calls an injected `RapidDimensionEstimator`. In composition that is `FirstVersionDimensionEstimator`, which returns a constant `RapidDimensionEstimate(threat=0.2, reward=0.1, novelty=0.6, social=0.0, uncertainty=0.3)` for every stimulus.
2. R34 ships `helios_v2.embedding.EmbeddingGateway` (text -> vector) and `ExperienceStore.search_similar(query_vector, limit, max_scan) -> SimilaritySearchResult` (cosine ranking with `hits[i].similarity`). Composition already builds an `_embed_text(text) -> vector` callable bound to the gateway + `embedding_profile_name` for semantic retrieval.
3. No cognitive owner consumes embeddings; `03` novelty is a constant.

Gap: novelty does not reflect the stimulus. The substrate to make it real exists but is unused by `03`.

## 3. Target Architecture

### 3.1 Owner-defined similarity source (in `helios_v2.appraisal`)

`03` stays the salience owner and never imports embedding/persistence. The salience semantic
(novelty = how unlike memory) stays inside `03`; the injected capability provides only a
memory-retrieval fact (max similarity to stored memory), not a salience judgment. `03` defines
a narrow protocol it calls:

```
@runtime_checkable
class MemorySimilaritySource(Protocol):
    def max_similarity_for(self, stimulus: Stimulus) -> float | None:
        """Return the max cosine similarity of the stimulus to stored memory, in [-1, 1],
        or None when there is no comparable memory (empty stimulus content or a cold/
        all-non-embedded store). This is a retrieval fact, not a salience judgment."""
```

A `MemoryGroundedDimensionEstimator` implements the existing `RapidDimensionEstimator` protocol;
it owns the novelty salience mapping and keeps the four non-novelty dimensions constant:

```
@dataclass
class MemoryGroundedDimensionEstimator(RapidDimensionEstimator):
    similarity_source: MemorySimilaritySource
    threat: float = 0.2
    reward: float = 0.1
    social: float = 0.0
    uncertainty: float = 0.3
    def estimate_dimensions(self, stimulus) -> RapidDimensionEstimate:
        similarity = self.similarity_source.max_similarity_for(stimulus)
        # Salience semantic owned by 03: unlike anything remembered -> maximally novel.
        novelty = 1.0 if similarity is None else round(min(1.0, max(0.0, 1.0 - similarity)), 4)
        return RapidDimensionEstimate(self.threat, self.reward, novelty, self.social, self.uncertainty)
```

The `1 - similarity` mapping and the `None -> 1.0` (cold/empty -> max novelty) decision are the
salience semantic and live in `03`. The four constants are explicit and unchanged from the
first-version shim (they are the next de-shim slices). The aggregate estimator
(`FirstVersionAggregateEstimator`) is untouched.

### 3.2 Composition-owned similarity source (owner-neutral glue)

The concrete `MemorySimilaritySource` lives in composition (it is glue that knows both the
embedding gateway and the store; it computes only a retrieval fact, never a salience value):

```
@dataclass
class MemoryGroundedSimilaritySource(MemorySimilaritySource):
    embed_text: Callable[[str], tuple[float, ...]]   # bound to the embedding gateway + profile
    store: ExperienceStore
    max_scan: int = _DEFAULT_MAX_SCAN
    def max_similarity_for(self, stimulus) -> float | None:
        text = stimulus.content.strip()
        if not text:
            return None                                 # empty input: no comparable signal, no gateway call
        query_vector = self.embed_text(text)            # same profile the store was written with
        result = self.store.search_similar(query_vector, limit=1, max_scan=self.max_scan)
        if not result.hits:
            return None                                 # cold/all-non-embedded store: no comparable memory
        return result.hits[0].similarity                # raw cosine retrieval fact; 03 maps it to novelty
```

`embed_text` is the exact same callable composition already builds for semantic retrieval (bound
to the gateway + `embedding_profile_name`), so the stimulus is embedded in the same vector space
as the stored records. This is the comparability guarantee. The glue returns a raw cosine fact
(or `None`); it never applies the `1 - x` salience mapping — that belongs to `03`.

### 3.3 Comparability and the cross-register caveat

The store currently holds only `15` result/continuity summaries, not raw stimulus text. R35 therefore compares the incoming stimulus input against past result summaries that share the same embedding profile. This is mathematically comparable (same vector space) and directionally correct (shared content shows up as higher cosine), but it is an input-vs-summary approximation, not strict input-vs-input. It must not be over-claimed. The follow-on "method B" (persist the raw stimulus stream) retires this caveat and is a separate requirement touching `15`/`33`, recorded in the `03` owner entry of `OWNER_GUIDE.md`.

### 3.4 Opt-in selection in assembly

`assemble_runtime` selects the appraisal estimator:

1. both `experience_store` and `embedding_gateway` present -> `MemoryGroundedDimensionEstimator(novelty_source=MemoryGroundedNoveltySource(embed_text=_embed_text, store=experience_store))`.
2. neither / only one present -> the existing `FirstVersionDimensionEstimator` (unchanged behavior).
3. an explicit novelty-grounding opt-in requested without both store and gateway -> `CompositionError`, consistent with the R34 semantic-memory rule (semantic capabilities require durable persistence + embedding).

Because R34 already requires `embedding_gateway` to come with `experience_store` (else `CompositionError`), the practical trigger is simply "embedding_gateway present": when semantic memory is on, novelty grounding is on too. No new public assembly parameter is strictly required; if a caller wants semantic retrieval without novelty grounding that is a future toggle, not this slice. (Design choice: reuse the existing `embedding_gateway`/`experience_store` opt-in; do not add a third flag.)

### 3.5 Default rollout

Default-off. The default assembly, the recency-persistent assembly (store only, no embedding), and any assembly without an embedding gateway keep `FirstVersionDimensionEstimator` and the constant novelty `0.6`. Only the semantic-memory assembly (store + embedding) gains real novelty.

## 4. Data Structures

No new cross-owner data contract. `RapidSalienceVector`, `RapidAppraisalBatch`, and `RapidDimensionEstimate` are unchanged. New types:

1. `MemorySimilaritySource` protocol (in `helios_v2.appraisal`) — owner-defined injection seam returning a retrieval fact (max cosine similarity or `None`), never a salience value.
2. `MemoryGroundedDimensionEstimator` (in `helios_v2.appraisal`) — implements `RapidDimensionEstimator`, owns the novelty salience mapping (`1 - similarity`, `None -> 1.0`), four constants otherwise.
3. `MemoryGroundedSimilaritySource` (in `helios_v2.composition.bridges`) — owner-neutral glue binding `embed_text` + `store.search_similar`, returning the raw cosine fact or `None`.

## 5. Module Changes

1. `helios_v2/src/helios_v2/appraisal/engine.py`: add the `MemorySimilaritySource` protocol and `MemoryGroundedDimensionEstimator` (the `1 - similarity` salience mapping lives here).
2. `helios_v2/src/helios_v2/appraisal/__init__.py`: export `MemorySimilaritySource` and `MemoryGroundedDimensionEstimator`.
3. `helios_v2/src/helios_v2/composition/bridges.py`: add `MemoryGroundedSimilaritySource` (imports the `ExperienceStore` type only; embedding is reached through the injected `embed_text` callable, not an import of the embedding owner; returns a raw cosine fact or `None`, never a novelty value).
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py`: select the memory-grounded estimator when `experience_store` and `embedding_gateway` are both present; otherwise keep `FirstVersionDimensionEstimator`. Reuse the existing `_embed_text` callable.

## 6. Migration Plan

1. All new code is additive. The default `FirstVersionDimensionEstimator` path is unchanged and remains the default.
2. No contract changes to `RapidSalienceVector`/`RapidAppraisalBatch`, so gating/modulation consume novelty exactly as before — only the value changes when grounding is enabled.
3. No stage-order change; `03` is the same stage with a different injected estimator.
4. The semantic-memory assembly automatically gains real novelty (the trigger is the same `embedding_gateway` opt-in), so no new caller flag is introduced.

## 7. Failure Modes and Constraints

1. Empty/whitespace `stimulus.content`: return `1.0` (defined max novelty), no gateway call. A predictable condition, not a transport failure.
2. Cold store or no embedded comparable record (`search_similar` returns zero hits): return `1.0` (defined max novelty). A defined semantic, not a fallback to the old constant.
3. Embedding call failure or store read failure while grounding is enabled: propagate as a hard stop (`EmbeddingError`/`PersistenceError`). No silent fallback to the constant novelty.
4. The cosine top similarity is clamped into `[0, 1]` before `1 - top`; negative cosine (an opposite vector) clamps to novelty `1.0`, consistent with "unlike anything remembered". The result is rounded for determinism and stays within the `RapidSalienceVector` range.
5. `03` must not import the embedding or persistence owners; the novelty capability is injected. The four non-novelty dimensions and the aggregate estimator are unchanged.
6. No `logging`/`print` under `src/`; the guard test stays green.

## 8. Observability and Logging

No new logging mechanism. Novelty travels only through the `RapidSalienceVector` in the appraisal batch. No log emission is added in `03` or the novelty source.

## 9. Validation Strategy

Network-free, deterministic, using a deterministic fake embedding (hashed-bucket) and an in-memory store seeded with known vectors.

1. `test_appraisal_engine.py` (extend):
   - `MemoryGroundedDimensionEstimator` returns the four constants unchanged and a novelty derived from the injected `NoveltySource`.
   - a `NoveltySource` double: a stimulus whose content embeds close to a stored vector yields low novelty; a distant one yields high novelty; the four other dimensions are unchanged; output stays in `[0, 1]`.
   - empty content -> `1.0` without invoking the embed callable (assert the callable was not called).
   - cold store -> `1.0`.
   - determinism: identical stimulus + identical stored vectors -> identical novelty.
2. `test_runtime_composition.py` (extend):
   - semantic-memory assembly (store + embedding): two stimuli, one semantically near a seeded record and one far, yield a measurably lower novelty for the near one, read from the `03` appraisal stage result.
   - the novelty difference flows unchanged through `RapidSalienceVector` (assert the appraisal batch carries the real values).
   - default assembly and recency-only persistent assembly keep novelty `0.6` at `03` (constant estimator).
   - an embedding-failure provider makes a grounding-enabled tick hard-stop (no constant fallback).
3. `test_no_adhoc_logging_guard.py` stays green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_appraisal_engine.py -q
```
