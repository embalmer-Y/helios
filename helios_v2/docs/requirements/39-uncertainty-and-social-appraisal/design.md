# Requirement 39 - Memory-grounded uncertainty and transport-grounded social appraisal (design)

## 1. Design Overview

R39 de-shims two of the four remaining constant `03` dimensions — `uncertainty` and `social` — by generalizing the R35 boundary pattern: composition supplies raw facts, the `03` owner owns the fact→salience mapping. It introduces no LLM into the fast pre-attentive path and adds no heavyweight dependency.

The design has three parts:

1. The `03` owner gains two narrow injected fact-source protocols (retrieval ambiguity, social presence) alongside the existing `MemorySimilaritySource`, and a generalized owner-owned estimator that grounds `novelty` (R35), `uncertainty`, and `social` while keeping `threat`/`reward` constant.
2. Composition gains two owner-neutral fact sources: one returns the top-N cosine similarities (reaching the embedding callable + store), one returns the social-presence transport fact (reaching the stimulus provenance / channel wiring it owns).
3. Assembly selects the generalized estimator only under the existing semantic-memory opt-in.

## 2. Current State and Gap

`MemoryGroundedDimensionEstimator` (R35) computes `novelty = clamp(1 - max_similarity)` via the injected `MemorySimilaritySource` (which returns the top-1 cosine or `None`), and holds the other four dimensions as constants: `threat=0.2, reward=0.1, social=0.0, uncertainty=0.3`. The `RapidSalienceVector` and aggregate estimator are unchanged and need no change here.

Gap: `uncertainty` and `social` are constant, so the `04` norepinephrine channel (driven by novelty+uncertainty) sees only the novelty half, and `social` never moves. R39 closes both.

## 3. Target Architecture

### 3.1 Fact sources (composition-owned, raw facts only)

```
MemorySimilaritySource         (R35) -> top-1 cosine or None         -> novelty
RetrievalAmbiguitySource       (R39) -> top-N cosines desc (tuple)   -> uncertainty
SocialContextSource            (R39) -> social_presence in [0,1]     -> social
```

Each source returns a raw fact, never a salience value. The `03` owner maps facts to dimensions.

To avoid a second embedding pass, the `RetrievalAmbiguitySource` and the existing novelty `MemorySimilaritySource` can share one composition implementation that embeds the stimulus once and runs one `search_similar(limit>=2)`; novelty reads hit[0], uncertainty reads hit[0]/hit[1]. The `03` owner still sees two narrow protocols (it does not know they share a backing object).

### 3.2 Ownership

- novelty/uncertainty/social salience mappings: owned by the `03` owner (the generalized estimator).
- top-N cosine retrieval, social-presence classification: owned by composition glue (raw facts).
- `03` imports neither embedding, persistence, nor channel owners; it reaches them only through injected sources, exactly as R35.

### 3.3 The mappings (owner-private)

Uncertainty (retrieval ambiguity):
- source returns the top-N normalized-able cosines descending, or an empty tuple when there is no comparable memory.
- empty tuple (cold/all-non-embedded store, or empty stimulus content) -> `uncertainty = 1.0` (no basis to resolve).
- otherwise normalize each cosine `c` from `[-1,1]` to `[0,1]` via `(c+1)/2`; `n1 = norm(hit[0])`, `n2 = norm(hit[1])` (or `0.0` if only one hit); `uncertainty = clamp(1 - (n1 - n2), 0, 1)`.
- intuition: one strong unique match (`n1` high, `n2` low) -> small `1 - margin` -> low uncertainty; several near-equal matches (`n1 ≈ n2`) -> `margin ≈ 0` -> uncertainty ≈ 1; a single hit (`n2 = 0`) gives `1 - n1`, i.e. a weak match is ambiguous.

Novelty (unchanged, R35): from the top-1 cosine, `novelty = clamp(1 - n1_raw)` using the existing `MemorySimilaritySource` semantics. (Novelty keeps reading the raw cosine as in R35; uncertainty reads the normalized margin. They are deliberately different reads of the retrieval result.)

Social (transport presence):
- source returns `social_presence` in `[0,1]` (composition classifies the stimulus's channel: external interactive-agent channel -> high, internal body/background -> low/zero).
- `social = clamp(social_floor + social_gain * social_presence, 0, 1)`, first-version `social_floor = 0.0`, `social_gain = 1.0` (so social tracks presence directly this version; the floor/gain are the P5-learnable surface).

Threat/reward: unchanged first-version constants `threat=0.2, reward=0.1`.

Determinism: pure arithmetic on the facts + config. Statelessness: no prior-tick read.

## 4. Data Structures

No contract change. `RapidSalienceVector`/`RapidDimensionEstimate` are unchanged; the new behavior lives in a new estimator + two new injected source protocols.

### 4.1 New owner-side protocols (in `appraisal/engine.py`)

```python
@runtime_checkable
class RetrievalAmbiguitySource(Protocol):
    def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
        """Top-N cosine similarities to stored experience, descending; empty when no comparable memory."""

@runtime_checkable
class SocialContextSource(Protocol):
    def social_presence_for(self, stimulus: Stimulus) -> float:
        """Raw transport fact in [0,1]: external interactive-agent presence for this stimulus."""
```

### 4.2 Generalized estimator (in `appraisal/engine.py`)

```python
@dataclass
class GroundedDimensionEstimator(RapidDimensionEstimator):
    similarity_source: MemorySimilaritySource        # novelty (R35)
    ambiguity_source: RetrievalAmbiguitySource       # uncertainty (R39)
    social_source: SocialContextSource               # social (R39)
    threat: float = 0.2                              # constant this slice
    reward: float = 0.1                              # constant this slice
    social_floor: float = 0.0
    social_gain: float = 1.0
    def estimate_dimensions(self, stimulus) -> RapidDimensionEstimate: ...
```

`MemoryGroundedDimensionEstimator` (R35, novelty-only) is kept for backward compatibility / smaller assemblies, or `GroundedDimensionEstimator` subsumes it; the design keeps R35's class to avoid breaking its tests and adds the new one. (Implementation may share a helper.)

## 5. Module Changes

1. `appraisal/engine.py`: add `RetrievalAmbiguitySource`, `SocialContextSource`, and `GroundedDimensionEstimator`. Keep `MemorySimilaritySource` and `MemoryGroundedDimensionEstimator` unchanged.
2. `appraisal/__init__.py`: export the new protocols + estimator.
3. `composition/bridges.py`: add `RetrievalAmbiguitySource` impl (top-N cosines via the embed callable + store `search_similar(limit=N)`) and `SocialContextSource` impl (presence from the stimulus channel/source provenance). The existing `MemoryGroundedSimilaritySource` stays (novelty). Optionally share one embed+search call.
4. `composition/runtime_assembly.py`: when `semantic_memory_enabled`, build the appraisal engine with `GroundedDimensionEstimator(similarity_source=..., ambiguity_source=..., social_source=...)`; otherwise keep `FirstVersionDimensionEstimator()`.

## 6. Migration Plan

1. Add the protocols + estimator (inert until selected).
2. Add the composition fact sources.
3. Switch the assembly selection behind `semantic_memory_enabled` (existing opt-in; no new flag). R35's `MemoryGroundedDimensionEstimator` path is replaced by `GroundedDimensionEstimator` in the semantic assembly, but novelty behavior is preserved identically (same `MemorySimilaritySource` semantics), so R35 composition tests still pass.
4. The default assembly keeps `FirstVersionDimensionEstimator`, unchanged.

No contract rewrite; the salience vector, the aggregate estimator, and the appraisal batch are untouched.

## 7. Failure Modes and Constraints

1. Embedding/store failure while fetching the ambiguity fact: hard stop, no constant fallback (consistent with R35 novelty).
2. Empty stimulus content: the ambiguity source returns an empty tuple without an embedding call -> uncertainty `1.0` (mirrors R35 novelty cold path).
3. Out-of-range dimension: structurally impossible (clamped to `[0,1]`).
4. Stateless: no prior-tick read.
5. No LLM in the fast path; no NN; no hidden branch keyed on content; deterministic.
6. Social presence is a transport fact; `03` does not hardcode channel names — composition classifies presence.

## 8. Observability and Logging

No new logging mechanism. Dimensions travel only through the existing `RapidSalienceVector`/`RapidAppraisalBatch`. No `logging`/`print` under `src`; guard test stays green.

## 9. Validation Strategy

1. Engine tests (`test_rapid_salience_engine.py`), with deterministic fake sources:
   - one strong unique match -> low uncertainty; several near-equal matches -> high uncertainty; the novelty-vs-uncertainty discrimination case (familiar but ambiguous -> low novelty, high uncertainty);
   - empty similarities -> uncertainty `1.0`;
   - high social_presence -> higher social than low presence; social within `[0,1]`;
   - determinism; threat/reward still the constants; novelty unchanged.
2. Composition tests (`test_runtime_composition.py`):
   - the semantic assembly produces an ambiguity-driven uncertainty that differs between a uniquely-matching and an ambiguously-matching stimulus (read from the `03` stage result);
   - an external interactive-agent stimulus yields higher social than an internal one;
   - the default assembly keeps constant uncertainty `0.3` / social `0.0`.
3. Guard + full gate: `test_no_adhoc_logging_guard.py` plus `pytest helios_v2/tests -q` green and network-free.
