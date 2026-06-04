# Requirement 34 - Semantic experience retrieval (design)

## 1. Design Overview

R34 adds semantic recall on top of the R33 durable experience store, without changing any cognitive owner. It has three additive parts:

1. A new backend-neutral embedding capability owner, `helios_v2.embedding`, modeled directly on the `25` LLM gateway: neutral request/result contracts, a named-profile registry, an injected provider protocol (lazy OpenAI-compatible provider + deterministic fake), a fail-fast gateway, network-free static readiness, and an opt-in live probe.
2. Vector storage and a bounded, deterministic cosine similarity search added additively to the R33 persistence owner: `PersistedExperienceRecord` gains an optional embedding vector, both backends persist/read it, and the backend gains a `search_similar` method plus a `SemanticStoreBackedDirectedMemoryCandidateProvider`.
3. Composition glue that, when semantic memory is opt-in enabled, embeds each tick's `15` record at write and wires the semantic candidate provider into `10`, plus an `embedding_profile_ready` critical dependency.

The persistence owner never imports the embedding owner: it stores and ranks vectors it is given. The semantic candidate provider receives a query-embedding callable by injection. Composition is the only place that knows both owners. `03` appraisal is untouched (novelty-from-memory is the first `P3` slice).

## 2. Current State and Gap

Current state (post-R33):

1. `helios_v2.persistence` durably stores `PersistedExperienceRecord`s and exposes `read_recent`. The `StoreBackedDirectedMemoryCandidateProvider` returns the most-recent N records as candidates.
2. No embedding capability exists anywhere in `helios_v2/src`. Records store no vector. The store cannot rank by similarity.
3. `RuntimeHandle._persist_experience` appends the tick's `15` records via `ExperienceRecordBridge`. `assemble_runtime(experience_store=...)` selects the recency provider for `10`.

Gap:

1. Recall is recency-only; it ignores relevance to the current cycle.
2. There is no text-to-vector capability and no vector field, so similarity is impossible.

## 3. Target Architecture

### 3.1 Embedding owner (capability, not cognition)

```
EmbeddingRequest(request_id, target_profile, input_text, metadata)
  -> EmbeddingGateway.embed(request)
       -> registry.resolve(target_profile) -> EmbeddingProfile
       -> resolve api key from injected env mapping (fail-fast if empty)
       -> provider.embed(profile, request, api_key) -> ProviderEmbedding(vector, dimensions, usage)
  -> EmbeddingResult(result_id, source_request_id, profile_name, model, vector, dimensions, usage, latency_ms)
```

Mirrors `25` exactly: keys only on `target_profile`; provider injected behind a protocol; first-version `OpenAICompatibleEmbeddingProvider` imports the `openai` SDK lazily inside `embed`; tests inject a deterministic fake provider. Static readiness = profile registered and api-key env non-empty (network-free); live probe is opt-in and never in the startup gate.

### 3.2 Vector storage + similarity search (in the persistence owner)

`PersistedExperienceRecord` gains `embedding: tuple[float, ...] | None = None` (additive; a record without it remains valid).

The backend protocol gains:

```
search_similar(query_vector, limit, max_scan) -> SimilaritySearchResult
```

`SimilaritySearchResult` carries the ranked hits (record + similarity score) and `skipped_non_embedded_count`. Ranking is cosine similarity, descending; the explicit tie-break is descending similarity then descending sequence (more-recent wins ties). Only the most-recent `max_scan` embedded records are considered (bounded brute force; no external index). Records without an embedding are excluded and counted.

Both backends implement it:
- in-memory: iterate the most-recent `max_scan` records, compute cosine over embedded ones.
- SQLite: select the most-recent `max_scan` rows, decode the JSON vector column, compute cosine in Python (standard-library math; no numpy).

The vector is persisted as a JSON-encoded column (nullable) so a prior non-semantic DB stays readable (its rows decode to `embedding=None`).

### 3.3 Semantic candidate provider

```
SemanticStoreBackedDirectedMemoryCandidateProvider(store, embed_query, limit, max_scan)
  collect_candidates(plan):
    query_vector = embed_query(plan.query_text)        # injected callable; no embedding-owner import
    result = store.search_similar(query_vector, limit, max_scan)
    map each hit -> MemoryRetrievalCandidate(score=similarity, source="experience_store_semantic", tier by continuity_kind)
```

`embed_query` is an injected `Callable[[str], tuple[float, ...]]`, so the persistence owner stays free of any embedding dependency. Composition supplies a callable that calls the embedding gateway.

### 3.4 Composition wiring (opt-in, default-off)

`assemble_runtime` gains an optional `embedding_gateway` parameter, used only together with the R33 `experience_store`:

1. Enabling `embedding_gateway` without `experience_store` raises `CompositionError` (semantic memory requires durable persistence).
2. When both are present:
   - the `10` candidate provider becomes `SemanticStoreBackedDirectedMemoryCandidateProvider` with an injected `embed_query` bound to the gateway + a composition-owned embedding profile name;
   - `RuntimeHandle._persist_experience` embeds each record's summary and stores the vector with the record (the embed-at-write seam);
   - `embedding_profile_ready` is registered as a critical dependency via `EmbeddingReadinessDependencyProvider`, wrapping the existing provider chain.
3. When `embedding_gateway` is absent, everything is exactly R33 (recency or non-persistent) or the default assembly.

### 3.5 Embed-at-write seam

`RuntimeHandle` gains an optional `embed_record` callable. In `_persist_experience`, after building records via `ExperienceRecordBridge`, if `embed_record` is present each record is re-created with its embedding (`record_with_embedding`) before `append_records`. An embedding failure propagates as a hard stop (no recency fallback, no fabricated vector).

### 3.6 Default rollout

Default-off. No `embedding_gateway` -> no embedding owner touched, no vector stored, no new dependency, recency/default behavior intact.

## 4. Data Structures

### 4.1 Embedding contracts (`helios_v2/embedding/contracts.py`)

```
class EmbeddingError(RuntimeError): ...

@dataclass(frozen=True)
class EmbeddingProfile:
    profile_name: str
    model: str
    api_key_env: str
    base_url: str
    dimensions: int | None = None     # optional expected dimensions (documented, not enforced on provider)
    timeout: float = 30.0

@dataclass(frozen=True)
class EmbeddingRequest:
    request_id: str
    target_profile: str
    input_text: str
    metadata: Mapping[str, object] = {}
    # validates: non-empty request_id, target_profile, input_text

@dataclass(frozen=True)
class EmbeddingUsage:
    prompt_tokens: int | None
    total_tokens: int | None

@dataclass(frozen=True)
class ProviderEmbedding:
    vector: tuple[float, ...]
    dimensions: int
    usage: EmbeddingUsage | None

@dataclass(frozen=True)
class EmbeddingResult:
    result_id: str
    source_request_id: str
    profile_name: str
    model: str
    vector: tuple[float, ...]
    dimensions: int
    usage: EmbeddingUsage | None
    latency_ms: float

@dataclass(frozen=True)
class EmbeddingProfileReadiness / EmbeddingReadinessReport: ...   # mirrors 25 readiness shape

@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed(self, profile, request, api_key) -> ProviderEmbedding: ...
```

### 4.2 Engine (`helios_v2/embedding/engine.py`)

`EmbeddingProfileRegistry` (unique names), `EmbeddingGateway` (resolve profile, resolve key fail-fast, dispatch, measure latency, validate provider output is a non-empty vector), `OpenAICompatibleEmbeddingProvider` (lazy `from openai import OpenAI`), `FakeEmbeddingProvider` is defined in tests (a deterministic hashing embedder), plus `check_static_readiness` / `probe_live_readiness`.

### 4.3 Persistence additions

```
@dataclass(frozen=True)
class PersistedExperienceRecord:
    ... (R33 fields)
    embedding: tuple[float, ...] | None = None
    # with_embedding(vector) returns a copy carrying the vector

@dataclass(frozen=True)
class SimilarityHit:
    record: PersistedExperienceRecord
    similarity: float

@dataclass(frozen=True)
class SimilaritySearchResult:
    hits: tuple[SimilarityHit, ...]
    scanned_count: int
    skipped_non_embedded_count: int
```

Backend protocol gains `search_similar(query_vector, limit, max_scan) -> SimilaritySearchResult`. A module-level `cosine_similarity(a, b)` helper (standard-library, raises `PersistenceError` on dimension mismatch or zero-norm) is the single ranking primitive.

### 4.4 Composition / dependencies

`EMBEDDING_PROFILE_READY` name, `embedding_profile_critical_dependency_spec()`, `EmbeddingReadinessDependencyProvider(gateway, bound_profile_names, baseline_provider)` (mirrors `LlmReadinessDependencyProvider`).

## 5. Module Changes

1. `helios_v2/embedding/{__init__,contracts,engine}.py`: new owner (sections 4.1-4.2).
2. `helios_v2/persistence/contracts.py`: add `embedding` to the record + `with_embedding`; add `SimilarityHit`, `SimilaritySearchResult`, `cosine_similarity`, and `search_similar` to the backend protocol.
3. `helios_v2/persistence/engine.py`: persist/read vectors in both backends; implement bounded deterministic `search_similar` in both; add `SemanticStoreBackedDirectedMemoryCandidateProvider`.
4. `helios_v2/composition/bridges.py`: an embed-at-write helper/callable factory and the semantic provider wiring stay owner-neutral (composition supplies `embed_query`/`embed_record` bound to the gateway).
5. `helios_v2/composition/runtime_assembly.py`: `embedding_gateway` param; composition error if set without `experience_store`; semantic provider selection; `RuntimeHandle.embed_record` + embed-at-write in `_persist_experience`; register the dependency.
6. `helios_v2/composition/dependencies.py`: embedding readiness name/spec/provider.

## 6. Migration Plan

1. The embedding owner is a new package; importing it never requires the SDK.
2. The record vector field is additive and defaulted `None`; existing R33 records and tests stay valid. A prior recency DB reopens cleanly (its rows decode `embedding=None` and are excluded from semantic results).
3. `embedding_gateway` defaults to `None`; the default, recency-persistent, and channel-bound assemblies are byte-for-byte unchanged. Existing tests pass unmodified.
4. No stage-order change. The embed-at-write seam runs inside the existing `_persist_experience` post-tick call.

## 7. Failure Modes and Constraints

1. `embedding_gateway` set without `experience_store`: `CompositionError` at assembly (semantic memory requires durable persistence).
2. Embedding profile statically unready while semantic memory enabled: `embedding_profile_ready` reports unavailable, startup fails fast. No recency fallback.
3. Embedding failure at write or query time: `EmbeddingError` propagates as a hard stop; no fabricated vector, no recency fallback.
4. Similarity over a cold or all-non-embedded store: `search_similar` returns zero hits with `skipped_non_embedded_count` set; the tick completes; the semantic provider returns `()`.
5. Dimension mismatch between query and a stored vector: `cosine_similarity` raises `PersistenceError` (a corrupt/mixed-model store is a hard stop, not a silent skip).
6. Read-only/append-only store semantics from R33 are unchanged; vectors are written only at append time.
7. No new heavyweight dependency; no `logging`/`print`; guard test stays green.

## 8. Observability and Logging

No new logging mechanism. Embedding facts (model, dimensions, usage, latency) ride the `EmbeddingResult` contract; similarity scores ride `SimilaritySearchResult` and the candidate `score`. Neither travels through the log channel, and neither owner emits log events itself.

## 9. Validation Strategy

Network-free, deterministic. Tests use a `FakeEmbeddingProvider` that maps text to a small fixed-dimension vector deterministically (e.g. bag-of-chars / hashed buckets) so similarity ordering is predictable.

1. `test_embedding_contracts.py`: profile registry uniqueness; request validation (empty id/profile/text); readiness report shape.
2. `test_embedding_engine.py`: gateway resolves profile and returns a vector via fake provider; unknown profile / missing key / empty text / provider failure all raise `EmbeddingError`; static readiness true/false network-free; live probe opt-in via fake.
3. `test_persistence_engine.py` (extend): record `with_embedding` round-trips; SQLite persists/reads the vector across re-open; `cosine_similarity` correctness + dimension-mismatch raise; `search_similar` ranks a near vector above a far one, excludes and counts non-embedded records, honors `max_scan` bound and the documented tie-break; `SemanticStoreBackedDirectedMemoryCandidateProvider` maps hits with `source="experience_store_semantic"` and similarity scores, and returns `()` on a cold store.
4. `test_runtime_composition.py` (extend):
   - semantic assembly: each tick embeds and stores a vector; a query close to one stored record ranks it above a more-recent but less-similar record.
   - semantic restart recall (headline): session A on a tmp_path SQLite store with semantic memory; reopen in session B; a query semantically close to a prior-session record recalls it by similarity (hit `source="experience_store_semantic"`), not merely the most recent.
   - `embedding_gateway` without `experience_store` -> `CompositionError`.
   - unready embedding profile -> `RuntimeStartupError` naming `embedding_profile_ready`.
   - embedding failure -> hard stop (no recency fallback).
   - default + recency-only + channel-bound assemblies unchanged when semantic memory off.
5. Guard test green; full suite green and network-free.

First narrow validation command:

```
$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"
pytest helios_v2/tests/test_embedding_contracts.py helios_v2/tests/test_embedding_engine.py -q
```
