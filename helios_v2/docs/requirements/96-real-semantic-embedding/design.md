# Requirement 96 - Real Semantic Embedding as Default (design)

> **Companion to `requirement.md`**. The owner-confirmed decision (option **A** — OpenAI-compatible cloud; `text-embedding-3-small` default) is the closed design constraint; this document specifies *how* the switch is wired without disturbing any cognitive owner.

## 1. Design Overview

R96 is a **composition-side provider selection** with three additive parts:

1. **A new owner-neutral resolver** (`composition.embedding_provider_resolution`) that reads three env vars (`HELIOS_EMBEDDING_API_KEY`, `HELIOS_EMBEDDING_BASE_URL`, `HELIOS_EMBEDDING_MODEL`) from an injected mapping and returns a frozen `EmbeddingProviderResolution(kind, model, base_url, dimensions, api_key_env_var)` decision. The resolver is the only place that reads the env; cognitive owners and the embedding owner do not learn the env-var names.
2. **A new `RuntimeProfile` capability-bundle extension** that records the resolved `embedding_provider_kind: Literal["openai_compatible", "deterministic_hash"]` and `embedding_provider_model: str` on the frozen profile, alongside the existing `semantic_memory_enabled`. These are observability facts on the *composition* seam; they never leak into any cognitive contract.
3. **An extension of the R69 auto-provisioning block** in `composition.runtime_assembly` that calls the resolver *before* the R69 hash-fallback construction, and uses the resolver's kind to pick between an `OpenAICompatibleEmbeddingProvider` (kind=openai_compatible) and the existing R69 `DeterministicHashEmbeddingProvider` (kind=deterministic_hash). The existing 1110-test-green baseline is preserved byte-for-byte when the resolver picks hash (which is the R69-equivalent path).

The cognitive chain is not touched. The `34` embedding owner is not touched. The `33` persistence owner is not touched. The `21` observability owner is not touched. The only owner code change is the `composition` package's new module + an extension of the `runtime_assembly` R69 block. The R82 production assembly's startup dependency gate, the R95 followup no-adhoc-logging guard, and the R56 / R57 owner-boundary guards are all preserved.

## 2. Current State and Gap

### 2.1 Current state (post-R69 + R82 + R95 followup)

1. The R69 auto-provisioning block in `runtime_assembly.py` (around L1207–L1245) always builds:
   - a `DeterministicHashEmbeddingProvider()` (R69-promoted; 16-dim character hash), and
   - an `EmbeddingProfile(model="deterministic-hash", api_key_env="HELIOS_AUTO_EMBEDDING_KEY", base_url="http://localhost")` registered in a fresh `EmbeddingProfileRegistry`,
   - wrapped in a fresh `EmbeddingGateway(provider=..., registry=..., env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"})`,
   - the gateway's `embed()` then calls the hash provider regardless of the real environment.
2. The R34 `OpenAICompatibleEmbeddingProvider` is shipped in `helios_v2.embedding.engine` but is **not** wired into the default assembly; the only way to use it today is to construct a `OpenAICompatibleEmbeddingProvider` and a real `EmbeddingProfile` (with `api_key_env="OPENAI_API_KEY"` etc.) and inject the gateway explicitly through `assemble_runtime(embedding_gateway=...)`.
3. The `embedding_profile_ready` critical dependency (R34 + R82) consumes whichever profile is registered. The dependency gate's fail-fast works correctly for any profile shape.

### 2.2 The gap

1. The R69 default assembly uses a 16-dim character hash, which empirically cannot distinguish Chinese emotional inputs (R36 / R38 / R40 / R52 all read noise, not semantics). This is the B2 root-cause identified in ROADMAP §9.1.
2. Switching to the R34 `OpenAICompatibleEmbeddingProvider` is a **one-line change at the composition layer**; the cognitive chain needs no edits. The hard work is in the resolver (deciding *when* to switch), in the B2 acceptance tests (proving the switch closes B2), and in preserving the 1110-test green baseline (the resolver must be a no-op when the credential is absent).

## 3. Target Architecture

### 3.1 The resolver

```python
# helios_v2/composition/embedding_provider_resolution.py

EMBEDDING_MODEL_DIMENSIONS: Mapping[str, int] = MappingProxyType({
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "bge-m3": 1024,
    "bge-large-zh-v1.5": 1024,
    "bge-base-zh-v1.5": 768,
    "bge-small-zh-v1.5": 512,
    "deterministic-hash": 16,  # explicit declaration of the hash placeholder's dim
})

EmbeddingProviderKind = Literal["openai_compatible", "deterministic_hash"]

@dataclass(frozen=True)
class EmbeddingProviderResolution:
    kind: EmbeddingProviderKind
    model: str
    base_url: str
    dimensions: int | None
    api_key_env_var: str  # for the *real* cloud: "HELIOS_EMBEDDING_API_KEY"; for hash: "HELIOS_AUTO_EMBEDDING_KEY"

def resolve_embedding_provider(env: Mapping[str, str]) -> EmbeddingProviderResolution:
    """Owner: composition. The single place that reads the embedding env vars.

    Returns:
        kind="openai_compatible" iff HELIOS_EMBEDDING_API_KEY is present and non-blank;
        otherwise kind="deterministic_hash" (the explicit R69 placeholder).
    """
```

Failure semantics: never raises for valid env inputs. Whitespace-only `HELIOS_EMBEDDING_API_KEY` is treated as absent (the resolution rules specify `str.strip()` truthiness). An empty injected `env` mapping is treated as "no env vars" (the same as a real `os.environ` empty mapping).

### 3.2 The auto-provisioning seam (in `runtime_assembly`)

The R69 block is extended; the resolver is the new first step. Pseudocode of the new block (the only cognitive-owner-neutral change):

```python
# inside assemble_runtime, after resolved_profile.default_signal_mode check, before R69 block:

if resolved_profile.default_signal_mode == "semantic":
    _auto_store = experience_store
    _auto_embedding = embedding_gateway
    if _auto_store is None and _auto_embedding is None:
        # NEW: call the resolver with the same env mapping the gateway will use.
        _resolution = resolve_embedding_provider(env=os.environ)  # injectable for tests
        if _resolution.kind == "openai_compatible":
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model=_resolution.model,
                api_key_env=_resolution.api_key_env_var,
                base_url=_resolution.base_url,
                dimensions=_resolution.dimensions,
            )
            _auto_embedding = EmbeddingGateway(
                provider=OpenAICompatibleEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env=os.environ,
            )
        else:
            # R69-equivalent hash fallback (byte-for-byte preserved).
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model="deterministic-hash",
                api_key_env="HELIOS_AUTO_EMBEDDING_KEY",
                base_url="http://localhost",
            )
            _auto_embedding = EmbeddingGateway(
                provider=DeterministicHashEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"},
            )
        _auto_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
        _auto_store.initialize()
    elif _auto_store is None:
        # NEW: also re-resolve when only the store is missing (gateway is caller-supplied).
        # The R69 path only built the hash-fallback profile in the "embedding is None" branch;
        # we keep that path identical and just expose the kind on the resolved profile.
        _auto_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
        _auto_store.initialize()
    elif _auto_embedding is None:
        # NEW: re-resolve and build either real-cloud or hash profile.
        _resolution = resolve_embedding_provider(env=os.environ)
        if _resolution.kind == "openai_compatible":
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model=_resolution.model,
                api_key_env=_resolution.api_key_env_var,
                base_url=_resolution.base_url,
                dimensions=_resolution.dimensions,
            )
            _auto_embedding = EmbeddingGateway(
                provider=OpenAICompatibleEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env=os.environ,
            )
        else:
            # R69-equivalent hash fallback (byte-for-byte preserved).
            _auto_profile = EmbeddingProfile(
                profile_name=embedding_profile_name,
                model="deterministic-hash",
                api_key_env="HELIOS_AUTO_EMBEDDING_KEY",
                base_url="http://localhost",
            )
            _auto_embedding = EmbeddingGateway(
                provider=DeterministicHashEmbeddingProvider(),
                registry=EmbeddingProfileRegistry(profiles=(_auto_profile,)),
                env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"},
            )
    experience_store = _auto_store
    embedding_gateway = _auto_embedding
    # NEW: record the provider kind on the resolved profile.
    _resolved_kind = (
        "openai_compatible"
        if isinstance(embedding_gateway.provider, OpenAICompatibleEmbeddingProvider)
        else "deterministic_hash"
    )
    _resolved_model = embedding_gateway.registry.resolve(embedding_profile_name).model
    resolved_profile = replace(
        resolved_profile,
        experience_store=experience_store,
        embedding_gateway=embedding_gateway,
        embedding_provider_kind=_resolved_kind,        # NEW
        embedding_provider_model=_resolved_model,      # NEW
    )
```

The shape of the new branches is dictated by what the R69 block does today. The R69 block builds the hash profile in two of its three branches (the all-missing branch and the embedding-only-missing branch); the new code keeps both paths and adds a resolver step that decides *which* profile to build in each.

### 3.3 The `RuntimeProfile` extension

Two new frozen fields on `RuntimeProfile`:

```python
@dataclass(frozen=True)
class RuntimeProfile:
    # ... existing fields ...
    embedding_provider_kind: EmbeddingProviderKind = "deterministic_hash"
    embedding_provider_model: str = "deterministic-hash"
```

`__post_init__` validation:

1. `embedding_provider_kind` must be one of `{"openai_compatible", "deterministic_hash"}`; any other value raises `CompositionError` at construction (the same guard the existing `default_signal_mode` has).
2. `embedding_provider_model` must be a non-empty string.

The defaults preserve the pre-R96 behavior: a profile constructed without explicit provider fields has the R69 hash kind. `assemble_runtime(default_signal_mode="legacy_constant")` does not set these fields (they stay at their default), preserving the byte-for-byte R69/R82 legacy path.

The `_resolve_profile` helper (R58) threads the new fields through `assemble_runtime` and `_resolve_profile` (when a `profile=` is passed explicitly, the profile's `embedding_provider_kind` / `embedding_provider_model` are honored; when neither `profile` nor the new fields are explicitly set, the defaults apply). **The explicit `embedding_gateway=` path still wins**: when the caller injects a gateway, the resolved profile's `embedding_provider_kind` is derived from the injected gateway's provider class (`isinstance(..., OpenAICompatibleEmbeddingProvider) -> "openai_compatible"`, else `"deterministic_hash"`). The resolver is **not** consulted on that path (preserving R69's "explicit caller-provided capabilities always take precedence" rule byte-for-byte).

### 3.4 The data flow (when the real-cloud path is active)

```
compose_runtime() called
  -> R58 _resolve_profile: new fields default to (deterministic_hash, deterministic-hash)
  -> assemble_runtime enters the R69 auto-provisioning block
       (because default_signal_mode == "semantic" and no caller-injected gateway)
  -> resolve_embedding_provider(os.environ) returns
       EmbeddingProviderResolution(
           kind="openai_compatible",
           model="text-embedding-3-small",
           base_url="https://api.openai.com/v1",
           dimensions=1536,
           api_key_env_var="HELIOS_EMBEDDING_API_KEY",
       )
  -> builds EmbeddingProfile(profile_name="experience-embedding",
       model="text-embedding-3-small",
       api_key_env="HELIOS_EMBEDDING_API_KEY",
       base_url="https://api.openai.com/v1",
       dimensions=1536)
  -> builds EmbeddingGateway(provider=OpenAICompatibleEmbeddingProvider(),
       registry=EmbeddingProfileRegistry(profiles=(profile,)),
       env=os.environ)
  -> rebuilds resolved_profile with the new fields
       embedding_provider_kind="openai_compatible"
       embedding_provider_model="text-embedding-3-small"
  -> continues R82 / R34 dependency wiring unchanged
  -> RuntimeHandle._persist_experience (existing R34 embed-at-write seam) calls
       _embed_text(record.summary) -> gateway.embed(request) -> real cloud vector
  -> RuntimeHandle._embed_query_text (existing R34 semantic-recall seam) calls
       _embed_text(query_text) -> gateway.embed(request) -> real cloud vector
  -> R35 / R40 / R52 read vectors from the same gates, indistinguishable from the
     hash-path; their `cosine_similarity` over the same real vectors now reflects
     true semantic similarity, not hash noise.
```

### 3.5 The data flow (when the hash fallback is active — R69 byte-for-byte preserved)

```
compose_runtime() called
  -> R58 _resolve_profile: new fields default to (deterministic_hash, deterministic-hash)
  -> assemble_runtime enters the R69 auto-provisioning block
       (because default_signal_mode == "semantic" and no caller-injected gateway)
  -> resolve_embedding_provider(os.environ) returns
       EmbeddingProviderResolution(
           kind="deterministic_hash",
           model="deterministic-hash",
           base_url="http://localhost",
           dimensions=16,
           api_key_env_var="HELIOS_AUTO_EMBEDDING_KEY",
       )
  -> builds the R69 hash profile + R69 hash gateway (byte-for-byte)
  -> rebuilds resolved_profile with the new fields
       embedding_provider_kind="deterministic_hash"
       embedding_provider_model="deterministic-hash"
  -> continues as today; the 1110 baseline tests pass unchanged.
```

The hash path is *intentionally* the R69-equivalent path; the resolver adds the resolver call and the profile-field recording, but the `DeterministicHashEmbeddingProvider` + `EmbeddingProfile(model="deterministic-hash", ...)` + `env={"HELIOS_AUTO_EMBEDDING_KEY": "auto-provisioned"}` triple is preserved verbatim. The 1110 existing tests are not modified.

## 4. Data Structures

### 4.1 `EmbeddingProviderResolution` (new, in `composition.embedding_provider_resolution`)

```
EmbeddingProviderKind = Literal["openai_compatible", "deterministic_hash"]

@dataclass(frozen=True)
class EmbeddingProviderResolution:
    kind: EmbeddingProviderKind
    model: str
    base_url: str
    dimensions: int | None        # None if the model is not in EMBEDDING_MODEL_DIMENSIONS
    api_key_env_var: str          # "HELIOS_EMBEDDING_API_KEY" or "HELIOS_AUTO_EMBEDDING_KEY"
```

Validation: `__post_init__` rejects empty `model` / `base_url` / `api_key_env_var`, and an `embedding_provider_kind` outside the literal set.

### 4.2 `EMBEDDING_MODEL_DIMENSIONS` (new, module-level `MappingProxyType`)

```
{
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "bge-m3": 1024,
    "bge-large-zh-v1.5": 1024,
    "bge-base-zh-v1.5": 768,
    "bge-small-zh-v1.5": 512,
    "deterministic-hash": 16,
}
```

If `HELIOS_EMBEDDING_MODEL` is set to a model not in the map, the resolver returns `dimensions=None`; the `OpenAICompatibleEmbeddingProvider` then omits the `dimensions` field from its request (the existing R34 behavior for `EmbeddingProfile.dimensions is None`). The default `text-embedding-3-small` *is* in the map (1536), so the default cloud call declares its dimension.

The map is module-level and `MappingProxyType`-frozen; it is the only place dimension knowledge lives. The map covers all model names mentioned in the owner-confirmed decision; future models add entries (no test changes needed for the openai-compatible cloud path).

### 4.3 `RuntimeProfile` (extended, in `composition.runtime_assembly`)

```
@dataclass(frozen=True)
class RuntimeProfile:
    # ... existing fields (R58, R69, R82) ...
    embedding_provider_kind: EmbeddingProviderKind = "deterministic_hash"
    embedding_provider_model: str = "deterministic-hash"
```

`__post_init__` validates both fields. The two `assemble_runtime(..., profile=...)` and `assemble_runtime(..., embedding_provider_kind=..., embedding_provider_model=...)` keyword seams mirror the R58 R69 `default_signal_mode` / `embedding_gateway` precedent.

## 5. Module Changes

### 5.1 New: `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py`

| Symbol | Purpose |
| --- | --- |
| `EmbeddingProviderKind` | `Literal["openai_compatible", "deterministic_hash"]` |
| `EmbeddingProviderResolution` | frozen dataclass; the resolver's output |
| `EMBEDDING_MODEL_DIMENSIONS` | `MappingProxyType` of well-known model names → int dimensions |
| `resolve_embedding_provider(env: Mapping[str, str]) -> EmbeddingProviderResolution` | the one function in this module; reads 3 env vars, returns the resolution |

All exports go into `composition/__init__.py` (additive, no breakage).

### 5.2 Modified: `helios_v2/src/helios_v2/composition/runtime_assembly.py`

| Change | Lines (approx.) | Behavior |
| --- | --- | --- |
| Add `embedding_provider_kind` and `embedding_provider_model` fields to `RuntimeProfile` | in the `RuntimeProfile` frozen dataclass | new additive fields, defaults to R69 hash path |
| Validate the new fields in `RuntimeProfile.__post_init__` | same | fail-fast on invalid input |
| Extend `_resolve_profile` to thread the new fields | R58 seam | additive |
| Extend the R69 auto-provisioning block to call the resolver and pick the provider | ~L1207–L1245 | resolver-driven; R69 hash path preserved byte-for-byte in the hash branch |
| Record `_resolved_kind` / `_resolved_model` on the rebuilt `resolved_profile` | inside the R69 block | observability fact on the profile |

### 5.3 New: `helios_v2/src/helios_v2/tests/test_embedding_provider_resolution.py`

| Test | What it asserts |
| --- | --- |
| `test_resolve_with_key_present_returns_openai_compatible` | `HELIOS_EMBEDDING_API_KEY="sk-..."` → kind=openai_compatible, model=text-embedding-3-small, dimensions=1536 |
| `test_resolve_with_blank_key_returns_deterministic_hash` | `HELIOS_EMBEDDING_API_KEY="   "` → kind=deterministic_hash |
| `test_resolve_with_no_key_returns_deterministic_hash` | empty env → kind=deterministic_hash |
| `test_resolve_with_explicit_model_returns_that_model` | `HELIOS_EMBEDDING_MODEL="bge-m3"` → model=bge-m3, dimensions=1024 |
| `test_resolve_with_unknown_model_returns_dimensions_none` | `HELIOS_EMBEDDING_MODEL="my-experimental-embedder"` → dimensions=None |
| `test_resolve_with_explicit_base_url_uses_it` | `HELIOS_EMBEDDING_BASE_URL="https://router.shengsuanyun.com/api/v1"` → base_url preserved |
| `test_resolve_validates_empty_model` | `HELIOS_EMBEDDING_MODEL=""` → kind=deterministic_hash (falls back to hash model) |
| `test_embedding_model_dimensions_is_frozen` | `MappingProxyType` rejects mutation |
| `test_embedding_provider_resolution_validates_empty_fields` | empty `model` / `base_url` / `api_key_env_var` raise |
| `test_resolve_uses_str_strip_for_key_check` | `HELIOS_EMBEDDING_API_KEY="  sk-...  "` → kind=openai_compatible (whitespace is stripped) |

### 5.4 Modified: `helios_v2/src/helios_v2/tests/test_runtime_composition.py`

| Test | What it asserts |
| --- | --- |
| `test_assemble_runtime_with_embedding_api_key_uses_openai_compatible` | with `HELIOS_EMBEDDING_API_KEY` set in the injected env, the resolved profile has `embedding_provider_kind == "openai_compatible"` and `embedding_provider_model == "text-embedding-3-small"` |
| `test_assemble_runtime_without_embedding_api_key_uses_deterministic_hash` | with the key absent, the resolved profile has `embedding_provider_kind == "deterministic_hash"` and `embedding_provider_model == "deterministic-hash"` (R69-equivalent) |
| `test_assemble_runtime_explicit_embedding_gateway_wins` | `assemble_runtime(embedding_gateway=OpenAICompatibleEmbeddingProvider_wrapped_gateway, ...)` → resolver skipped, profile kind reflects the injected gateway |
| `test_assemble_runtime_legacy_constant_mode_skips_resolver` | `default_signal_mode="legacy_constant"` → profile kind stays at default, no env reads |
| `test_assemble_runtime_real_cloud_with_explicit_bge_m3` | `HELIOS_EMBEDDING_MODEL="bge-m3"` → profile kind openai_compatible, model=bge-m3, dimensions=1024 |
| `test_resolved_profile_embedding_provider_fields_are_frozen` | `RuntimeProfile.embedding_provider_kind` and `.embedding_provider_model` are frozen-dataclass fields; cannot be reassigned |

### 5.5 New: `helios_v2/src/helios_v2/tests/r96_b2_closure.py`

The B2 closure test suite. Driven by a small `FakeOpenAICompatibleEmbeddingProvider` (network-free, deterministic, but produces *coherent* synthetic vectors — see §10). Three test functions, one per must-measure shift:

| Test | What it asserts |
| --- | --- |
| `test_b2_novelty_signal_differs_across_providers` | The R35 novelty signal (1 - max cosine to stored experience) for the same fixture corpus changes sign or magnitude on ≥ 8 of 10 fixtures when the provider switches from hash to fake-openai |
| `test_b2_threat_reward_prototype_cosine_differs_across_providers` | The R40 threat / reward prototype-cosine for the same fixtures differs on ≥ 8 of 10 fixtures across the same provider switch |
| `test_b2_recall_over_recency_holds_for_real_provider` | The R52 recalled-replay path ranks a known semantically-similar prior affect-memory above a less-similar more-recent memory under the real provider; the hash case does not (the failing witness is the B2 closing argument) |

Each test produces a `B2ClosureReport` (frozen dataclass, see §5.6) and asserts `b2_closed: bool == True` for the real-cloud path and `b2_closed: bool == False` for the hash path. The reports are also written to `logs/r96_b2_closure/` (gitignored) for human inspection.

### 5.6 `B2ClosureReport` (new, in `tests/r96_b2_closure.py`)

```
@dataclass(frozen=True)
class B2FixtureShift:
    fixture_id: str
    provider_kind: EmbeddingProviderKind
    novelty: float
    threat: float
    reward: float
    recall_top_record_id: str | None
    recall_top_similarity: float

@dataclass(frozen=True)
class B2ClosureReport:
    provider_kind: EmbeddingProviderKind
    fixture_count: int
    novelty_shift_count: int            # count of fixtures where novelty changed sign or |delta| > 0.05
    prototype_shift_count: int         # count of fixtures where threat or reward changed
    recall_over_recency_passed: bool
    b2_closed: bool
    fallback_reason: str | None         # "hash_placeholder" when kind=deterministic_hash
    shifts: tuple[B2FixtureShift, ...]
```

### 5.7 `FakeOpenAICompatibleEmbeddingProvider` (new, in `tests/r96_b2_closure.py`)

A test-only provider that conforms to the `EmbeddingProvider` protocol and returns deterministic, *coherent* 1536-dim vectors for a small fixture corpus. Coherent means: similar text → similar vectors. The simplest implementation: a fixed per-fixture index in `[0, N-1]` mapped to a 1536-dim vector `e_i` (a one-hot at position `i` plus a small base offset), and partial overlap is approximated by blending two such vectors. The fixture corpus is the same 10-emotion test set used in the ROADMAP §9.1 evaluation; the `text_embedding` of each fixture is a precomputed vector captured in a frozen dict in the test file (committed for determinism).

This is a **test-only** provider; it does not enter the runtime. The test-only provider must conform to the existing `EmbeddingProvider` protocol — the `EmbeddingGateway` will accept it without modification.

### 5.8 New: `helios_v2/scripts/r96_b2_real_llm_probes/` (opt-in, post-merge)

Documented in `scripts/r96_b2_real_llm_probes/README.md`:

1. `run.py` — re-runs the 2026-06 emotion corpus (16 visitors, ~89 utterances) through the real-cloud provider when `HELIOS_EMBEDDING_API_KEY` is set. Records per-tick `04`/R36 levels and LLM I/O (using the existing `_LoggingProvider` wrapper pattern from R91).
2. `analyze.py` — computes the same `cortisol` positive-vs-negative emotion separation metric as `scripts/analyze_emotion_test.py` and writes a JSON report.
3. `probe_results.md` — the committed report (gitignored artifacts under `logs/r96_b2_real_llm_probes/`).

This is opt-in (not in CI). The acceptance is directional, not numerical: a measurable shift over the pre-R96 -0.0095 separation. The probe result is committed as evidence of B2 closure under the real cloud.

## 6. Migration Plan

The migration is *additive and opt-in at the credential level*:

1. **Pre-R96 default behavior is preserved** (the 1110-test green baseline) — when `HELIOS_EMBEDDING_API_KEY` is absent, the resolver picks `deterministic_hash`, the runtime builds the R69 hash gateway, the resolved profile reports `kind="deterministic_hash"`. The 1110 tests are unmodified.
2. **Pre-R96 explicit behavior is preserved** — when the caller injects `embedding_gateway=...`, the resolver is skipped, the existing tests pass.
3. **Pre-R96 legacy_constant behavior is preserved** — when `default_signal_mode="legacy_constant"`, the resolver is not consulted, the `legacy_constant` assembly is unchanged.
4. **New path is added** — when `HELIOS_EMBEDDING_API_KEY` is set (and the runtime is otherwise `semantic`), the resolver picks `openai_compatible`, the runtime builds the cloud gateway, the resolved profile reports `kind="openai_compatible"`. The new `tests/r96_b2_closure.py` and the real-LLM opt-in probe exercise this path.
5. **No data migration is needed in the persistence owner** — the `embedding` column is already nullable; the schema does not change. The vector format changes (16-dim hash vs 1536-dim cloud), but each runtime's vectors are written by *its* provider; a per-record `embedding` is consumed by the same provider's cosine computation (no cross-provider cosine is performed within a single runtime, so a 16-dim hash vector and a 1536-dim cloud vector never appear in the same store).
6. **No public-API change** — the `34` embedding owner contract is unchanged; the `33` persistence owner contract is unchanged; the cognitive owner contracts are unchanged. The new `embedding_provider_kind` / `embedding_provider_model` fields are additive on the `RuntimeProfile` dataclass; existing callers that don't read them are unaffected.

The R82 standard production assembly's `assemble_production_runtime()` is updated to *not* override the new fields; the R82 entry point continues to default to the same semantics as `assemble_runtime()` (so the cloud-vs-hash decision is the same in both, and the R82 default `data/`-SQLite store remains the durability substrate).

## 7. Failure Modes and Constraints

1. **Missing or whitespace-only `HELIOS_EMBEDDING_API_KEY`** → resolver picks `deterministic_hash`; the R69 hash-fallback path runs; 1110 tests pass; the resolved profile's `embedding_provider_kind` is `deterministic_hash`; `b2_closed: bool` is `False` in any B2 closure report under this kind.
2. **`HELIOS_EMBEDDING_API_KEY` set but `OPENAI_API_KEY` also set** → the resolver reads only `HELIOS_EMBEDDING_API_KEY`; the `OpenAICompatibleEmbeddingProvider` reads its own `api_key_env` (which is `HELIOS_EMBEDDING_API_KEY` because that is what the resolver returned in `api_key_env_var`); the `OPENAI_API_KEY` is ignored for embedding. This is the explicit "separate concern" decision: LLM gateway uses `OPENAI_API_KEY`, embedding gateway uses `HELIOS_EMBEDDING_API_KEY`. The two credentials are independent.
3. **Network unavailable but credential set** → `OpenAICompatibleEmbeddingProvider.embed()` raises `EmbeddingError` (R34 behavior); the runtime's first `embed()` call hard-stops the tick. The B2 closure report records this as a `fallback_reason="real_cloud_unreachable_at_runtime"`. There is **no per-tick fall-back to hash**; the hash path is a *startup-time* decision, not a per-tick degradation. A failed startup with a present credential and a missing network fails at the dependency gate (`embedding_profile_ready` if the key was removed; otherwise, the first `embed()` call).
4. **Invalid model name** → `HELIOS_EMBEDDING_MODEL` is not in the well-known map; `dimensions=None` is sent to the provider; the OpenAI-compatible endpoint may reject the model and the first `embed()` call raises `EmbeddingError`. The runtime does not silently fall back; the failure is recorded and the B2 closure report's `fallback_reason` is `"real_cloud_model_invalid_at_runtime"`.
5. **`OpenAI` SDK not installed** → `OpenAICompatibleEmbeddingProvider.embed()` raises `EmbeddingError` (R34 behavior — `from openai import OpenAI` inside the call path). The runtime hard-stops; this is the R34 documented failure mode. The B2 closure report's `fallback_reason` is `"real_cloud_sdk_missing_at_runtime"`.
6. **`openai` SDK installed but `requests` / TLS broken** → same as (3); the B2 closure report's `fallback_reason` is `"real_cloud_unreachable_at_runtime"`.
7. **R95 followup no-adhoc-logging guard violation** (defensive) → the new code uses no `print` and no `logging`; the guard test keeps passing. The `embedding_provider_kind` field is the only new observability fact, and it is on the resolved profile (a frozen dataclass, not a log channel).
8. **R56 / R57 owner-boundary guard violation** (defensive) → the resolver introduces no sensitivity coefficient, no pressure constant, no feeling-coupling coefficient, no autonomy threshold. The new code is pure composition glue (provider selection). The guards keep passing.
9. **`RuntimeProfile` invariant violation** (defensive) → `__post_init__` validates the new fields at construction; the `_resolve_profile` helper threads them through; an invalid value is caught at the earliest point.
10. **R82 production assembly regression** (defensive) → the new resolver is called only inside the `default_signal_mode == "semantic"` branch. The `assemble_production_runtime` entry point (which calls `assemble_runtime(default_signal_mode="semantic")`) gets the new path automatically; the existing R82 tests pass because the hash-fallback branch is preserved byte-for-byte and the cloud branch only activates when the credential is set.

## 8. Observability and Logging

1. **No new logging mechanism** — the new code does not call `print` or `logging`; the no-adhoc-logging guard keeps passing.
2. **The new observability facts** are:
   1. `resolved_profile.embedding_provider_kind` — the active provider kind on this assembled runtime.
   2. `resolved_profile.embedding_provider_model` — the active model name on this assembled runtime.
   3. The `EmbeddingReadinessReport` from `EmbeddingGateway.check_static_readiness` (existing R34) — consumed by the `embedding_profile_ready` critical dependency, no change.
   4. The `B2ClosureReport` (new, in `tests/r96_b2_closure.py`) — opt-in via the test runner; not part of the runtime's per-tick observability.
3. **The R21 observability owner** is unchanged. The per-tick `LogEvent` stream is unchanged. No new event-kind or severity-level is added.
4. **The R32 consequence-corroboration owner** is unchanged. The R87 real-delivery verdict is unchanged. The B2 closure report is *not* fed into the runtime's evaluation owner; it is a tests-only artifact.
5. **The R88 / R89 / R90 evaluation harnesses** are unchanged. The B2 closure test co-exists with them; the closure report is a focused, narrow test surface, not a general evaluation harness.

## 9. Validation Strategy

The validation strategy follows the established Helios v2 pattern: **probe-driven design validation, network-free contract tests, and opt-in real-LLM probes**.

### 9.1 Network-free contract tests (CI, in `tests/test_embedding_provider_resolution.py` and `tests/test_runtime_composition.py` extend)

The resolver is a small, pure function over an injected `env` mapping. The 10 unit tests in §5.3 cover the resolver exhaustively. The 6 extend tests in §5.4 cover the composition wiring.

### 9.2 Network-free B2 closure tests (CI, in `tests/r96_b2_closure.py`)

The three B2 shift tests in §5.5 use the `FakeOpenAICompatibleEmbeddingProvider` to simulate the real-cloud behavior. CI runs the suite against both providers (hash and fake-openai) and asserts the per-provider reports.

### 9.3 Real-LLM opt-in probe (`scripts/r96_b2_real_llm_probes/`, post-merge)

When `HELIOS_EMBEDDING_API_KEY` is set, the probe re-runs the 2026-06 emotion corpus and records the per-tick `04`/R36 levels + LLM I/O. The `analyze.py` script computes the `cortisol` positive-vs-negative separation and records the result. The committed `probe_results.md` documents the B2 closure under the real cloud.

### 9.4 No-regression validation

1. The 1110-test baseline is preserved byte-for-byte; the existing test files are not modified; the R95 followup no-adhoc-logging guard passes; the R56 / R57 owner-boundary guards pass; the R82 standard production assembly tests pass; the R69 semantic-assembly-default tests pass.
2. The `legacy_constant` mode is unchanged; the R69 explicit `legacy_constant` tests pass.
3. The R34 / R82 / R95 / R95-followup tests are unchanged.

### 9.5 Probe-driven design verification (per ROADMAP §11)

Per the ROADMAP §11 discipline, prompt-touching changes must be probed. R96 does **not** change any LLM prompt (the embedding provider is a capability consumed by cognitive owners, never seen by the LLM), so no probe is required. The §11 discipline is recorded for completeness; no probe is filed for R96.

## 10. Migration and Risk Notes

1. The R96 change is **purely additive and opt-in**. The worst-case behavior is "the runtime boots with hash, the B2 closure test reports `b2_closed: False`, no test regression". The best-case is "the runtime boots with real cloud, the B2 closure test reports `b2_closed: True`, the emotion test shows the predicted directional shift".
2. The biggest risk is **the cloud provider's embedding quality not matching the prototype-anchor assumption in R40**. If the real cloud's `bge-m3` returns vectors that don't preserve the threat/reward prototype structure, the B2 closure will report a shift on novelty and recall-over-recency but *not* on the prototype-cosine shift. The acceptance is recorded as "at least 8 of 10 fixtures" rather than "all 10", so partial success is a passing test; the B2 verdict is the falsifiable aggregate.
3. The second-biggest risk is **CI flakiness from the no-network contract test path**. The R34 path is already tested; the new resolver is a small function with 10 unit tests; the `FakeOpenAICompatibleEmbeddingProvider` is fully deterministic; the B2 closure tests use frozen precomputed vectors. The CI path is deterministic.
4. The third-biggest risk is **operator confusion between `OPENAI_API_KEY` (LLM gateway) and `HELIOS_EMBEDDING_API_KEY` (embedding gateway)**. The R96 design explicitly separates the two credentials; the runtime never uses `OPENAI_API_KEY` for embedding. The `scripts/r96_b2_real_llm_probes/README.md` documents the credential separation.
5. The fourth-biggest risk is **a runtime with a present `HELIOS_EMBEDDING_API_KEY` but a slow or expensive network**. The R34 hard-stop on `EmbeddingError` is the right behavior; a slow cloud call slows the first `embed()` tick (which is the only tick that calls the embed-at-write seam per record). For a 1536-dim OpenAI embedding, typical latency is 50-200 ms; the R83 long-run benchmark showed 9.5ms/tick (legacy-constant) and 100ms/tick (semantic) baseline, so a cloud-embedding semantic tick would be 100-300ms. This is the documented "P4 network" cost; it is not a regression on the R83 baseline (which used hash, not cloud).
