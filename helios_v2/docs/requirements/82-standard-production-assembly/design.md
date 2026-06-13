# Requirement 82 - Standard Production Assembly and Persistence-by-Default

## 1. Design Overview

Add a thin `assemble_production_runtime()` entry point that constructs SQLite-backed durable
backends (experience store + R42 continuity checkpoint) under a git-ignored data directory and a
real-capable, offline-safe embedding gateway, then delegates to the unchanged `assemble_runtime()`
seam with those capabilities injected. `assemble_runtime()` already wires the checkpoint bridge,
the `_ready` critical dependencies, and the startup restore for any injected store/checkpoint, so
the new entry point adds only construction + delegation. No assembly path, default, or cognitive
policy changes; `assemble_runtime()` stays byte-for-byte.

## 2. Current State and Gap

1. `assemble_runtime(default_signal_mode="semantic")` (the default) auto-provisions an
   `InMemoryExperienceStoreBackend` + `DeterministicHashEmbeddingProvider` and leaves
   `continuity_checkpoint=None`. Nothing durable is on by default.
2. The durable backends exist and are validated: `SqliteExperienceStoreBackend(db_path=...)` (R33),
   `SqliteCheckpointBackend(db_path=...)` (R42), `EmbeddingGateway` + `OpenAICompatibleEmbeddingProvider`
   / `DeterministicHashEmbeddingProvider` (R34). When `continuity_checkpoint` is injected,
   `assemble_runtime` builds the `ContinuityCheckpointBridge`, registers
   `continuity_checkpoint_ready`, and restores the snapshot at startup; when `experience_store` +
   `embedding_gateway` are injected, it registers `experience_store_ready` / `embedding_profile_ready`
   and runs the semantic chain.
3. There is no standard entry point that defaults these on, so G2.2/G2.4 stay open.

## 3. Target Architecture

### 3.1 `assemble_production_runtime`

```
DEFAULT_PRODUCTION_DATA_DIR = "data"

def assemble_production_runtime(
    *,
    data_dir: str | os.PathLike[str] | None = None,
    config: CompositionConfig | None = None,
    gateway: LlmGatewayAPI | None = None,
    recorder: RuntimeObservabilityRecorder | None = None,
    embedding_gateway: EmbeddingGatewayAPI | None = None,
) -> RuntimeHandle:
```

Steps:
1. `base = Path(data_dir or DEFAULT_PRODUCTION_DATA_DIR)`.
2. Build and initialize the durable experience store:
   `ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=str(base / "experience_store.sqlite3")))`,
   then `.initialize()` (idempotent; backend creates parent dirs).
3. Build and initialize the durable checkpoint:
   `ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=str(base / "continuity_checkpoint.sqlite3")))`,
   then `.initialize()`.
4. `emb = embedding_gateway or _production_embedding_gateway()`.
5. `return assemble_runtime(config=config, gateway=gateway, recorder=recorder,
   experience_store=store, embedding_gateway=emb, continuity_checkpoint=checkpoint,
   default_signal_mode="semantic")`.

Only the keyword overrides that production/tests need are exposed; everything else uses the
`assemble_runtime` default. Because both `experience_store` and `embedding_gateway` are injected,
the R69 auto-provisioning block is bypassed and the `RuntimeProfile` cross-capability validation
(embedding requires a store) is satisfied.

### 3.2 `_production_embedding_gateway`

```
_EMBEDDING_API_KEY_ENV = "HELIOS_EMBEDDING_API_KEY"
_EMBEDDING_BASE_URL_ENV = "HELIOS_EMBEDDING_BASE_URL"
_EMBEDDING_MODEL_ENV = "HELIOS_EMBEDDING_MODEL"
_DEFAULT_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

def _production_embedding_gateway(
    profile_name: str = "experience-embedding",
    env: Mapping[str, str] | None = None,
) -> EmbeddingGateway:
```

- `env = env if env is not None else os.environ`.
- If `env.get(_EMBEDDING_API_KEY_ENV)` is non-empty: build an `EmbeddingProfile` (model/base-url
  from env with documented defaults, `api_key_env=_EMBEDDING_API_KEY_ENV`) with
  `OpenAICompatibleEmbeddingProvider()` (the SDK is lazy-imported inside the provider call path, so
  construction is import-safe and network-free).
- Else: build the offline `EmbeddingProfile(model="deterministic-hash",
  api_key_env="HELIOS_AUTO_EMBEDDING_KEY", base_url="http://localhost")` with
  `DeterministicHashEmbeddingProvider()` and `env={"HELIOS_AUTO_EMBEDDING_KEY": "production-offline"}`
  so static readiness passes offline.

Both branches register the profile under `profile_name == "experience-embedding"` (the name
`assemble_runtime`'s `_embed_text` uses), so the retrieval path resolves it.

## 4. Data Structures

No new contracts. Reuses `ExperienceStore`, `SqliteExperienceStoreBackend`,
`ContinuityCheckpointStore`, `SqliteCheckpointBackend`, `EmbeddingGateway`, `EmbeddingProfile`,
`EmbeddingProfileRegistry`, the embedding providers, and `RuntimeHandle`. One module constant
`DEFAULT_PRODUCTION_DATA_DIR` and the four `_EMBEDDING_*` env-name constants.

## 5. Module Changes

1. `composition/runtime_assembly.py` - add `DEFAULT_PRODUCTION_DATA_DIR`, `_production_embedding_gateway`,
   `assemble_production_runtime`; import `Path`/`os` as needed (already imported `replace`,
   embedding/persistence/checkpoint symbols).
2. `composition/__init__.py` - export `assemble_production_runtime` (and `DEFAULT_PRODUCTION_DATA_DIR`).
3. `.env.example` - add an optional `HELIOS_EMBEDDING_*` section documenting the production embedding
   credential and its offline-hash fallback.

## 6. Migration Plan

1. Additive only: a new entry point + helper. `assemble_runtime()` and every existing test are
   untouched.
2. The data directory (`data/`) and `*.sqlite3` are already git-ignored, so durable files never
   enter version control.
3. The production assembly is offline-safe by default (hash embedding when no credential), so the
   new test runs network-free in CI; a real production deployment sets `OPENAI_API_KEY` (LLM) and
   optionally `HELIOS_EMBEDDING_API_KEY` (embedding).

## 7. Failure Modes and Constraints

1. An unwritable data directory / SQLite path raises `PersistenceError` / `CheckpointError` at
   `initialize()` or first use (existing backend behavior); fail-fast, no degraded path.
2. A missing LLM credential makes `llm_profiles_ready` fail at startup (existing gate) - correct for
   production; the test injects a ready fake gateway.
3. The embedding gateway is always statically ready (real credential present, or the offline-hash
   env key set), so `embedding_profile_ready` passes; an unready real profile would fail fast.
4. The entry point holds no cognitive policy and adds no new assembly branch; it only constructs and
   delegates.

## 8. Observability and Logging

No new logging mechanism. The durable backends and checkpoint flow through the existing `21`
surfaces unchanged. The assembly emits nothing itself.

## 9. Validation Strategy

1. Wiring: `assemble_production_runtime(data_dir=tmp, gateway=<ready fake>)` produces a handle whose
   `experience_store` and `continuity_checkpoint` are non-`None`, and whose kernel dependency specs
   include `experience_store_ready`, `embedding_profile_ready`, `continuity_checkpoint_ready`; it
   starts up and runs ticks offline.
2. Cross-restart: session A runs ticks against a tmp data dir then is dropped; session B through the
   same entry point against the same dir sees store count > 0 and a loadable prior checkpoint
   snapshot (continuity/affect resumed).
3. Embedding selection: with no `HELIOS_EMBEDDING_API_KEY`, `_production_embedding_gateway(env={})`
   binds the hash provider (network-free); with the key set in a passed `env`, it binds the
   OpenAI-compatible provider and the `experience-embedding` profile (asserted without a network
   call).
4. Regression: `assemble_runtime()` defaults unchanged; full network-free suite green; the data
   directory stays git-ignored.
