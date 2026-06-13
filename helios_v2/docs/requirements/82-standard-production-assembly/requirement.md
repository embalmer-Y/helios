# Requirement 82 - Standard Production Assembly and Persistence-by-Default

## 1. Background and Problem

`assemble_runtime()` is the single composition entry point. Under R69 its default
`default_signal_mode="semantic"` auto-provisions an **in-memory** experience store and a
deterministic-hash embedding gateway, and it leaves the R42 continuity checkpoint **off** unless a
caller explicitly injects one. The consequence is that the default runtime is a blank slate on every
process start: experience and the genuinely cross-tick continuity state (`09` continuation pressure,
`18`/`24` long-horizon continuity, `04`/`05` affect) are lost on exit.

`ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13.3.1 makes durable memory the single hard, still-open gate for
the P0-P3 "foundation-stability" phase (G2): "标准生产装配必须使用真实持久化后端（SQLite）而非内存白板
——记忆必须跨进程存活" (G2.2) and "checkpoint + SQLite 须为标准装配默认开启" (G2.4). The capabilities
to satisfy this all exist and are validated — the SQLite experience store (R33), the embedding
gateway (R34), and the SQLite continuity checkpoint (R42) — but they are opt-in, so no standard entry
point turns them on by default. The remaining gap is purely an assembly/default gap, not a missing
capability.

`assemble_runtime()` must stay exactly as it is: the test/embedded entry point used by the entire
suite, network-free and in-memory by default. The fix is a new, separate standard production entry
point that defaults the durable infrastructure on.

## 2. Goal

Add a standard production assembly entry point `assemble_production_runtime()` that, by default,
wires a SQLite-backed durable experience store, a SQLite-backed R42 continuity checkpoint, and an
embedding gateway under a single git-ignored data directory, so a runtime assembled through it
persists its experience and resumes its cross-tick `09`/`18`/`04`/`05` state across a process
restart — closing the G2 hard gate — while `assemble_runtime()` and the whole test suite stay
byte-for-byte unchanged.

## 3. Functional Requirements

### 3.1 Standard production entry point

1. Composition must expose `assemble_production_runtime()` that returns a `RuntimeHandle` assembled
   through the existing `assemble_runtime()` seam (it adds no new assembly path and holds no
   cognitive policy).
2. By default it must enable, without the caller passing anything:
   - a durable experience store backed by `SqliteExperienceStoreBackend` at a file under the data
     directory,
   - a durable R42 continuity checkpoint backed by `SqliteCheckpointBackend` at a file under the data
     directory,
   - an embedding gateway bound to the same `experience-embedding` profile name the retrieval path
     uses.
3. It must accept an optional `data_dir`; when absent it must default to a git-ignored project data
   directory (`data/`). The two SQLite files live under that directory.
4. It must accept optional overrides for `config`, the LLM `gateway`, the `recorder`, and the
   `embedding_gateway`, forwarding them to `assemble_runtime()` so production callers (and the test)
   can inject a ready LLM gateway and recorder.
5. The assembled runtime must register the existing `experience_store_ready`,
   `embedding_profile_ready`, and `continuity_checkpoint_ready` critical dependencies (through the
   existing `assemble_runtime` wiring) and fail fast at startup if any backend is not ready; there is
   no degraded non-persistent production path.

### 3.2 Embedding gateway: real-capable, offline-safe

1. The default production embedding gateway must be real-capable: when a configured embedding
   credential environment variable (`HELIOS_EMBEDDING_API_KEY`) is present, it must use the
   OpenAI-compatible embedding provider (model/base-url from `HELIOS_EMBEDDING_MODEL` /
   `HELIOS_EMBEDDING_BASE_URL`, with documented defaults).
2. When that credential is absent (offline / CI), it must fall back to the network-free
   `DeterministicHashEmbeddingProvider` so the production assembly still starts and runs offline.
   This requirement does not introduce a real embedding model as a hard dependency (real embedding
   quality is deferred to P5); the hash fallback is an explicit, documented placeholder.

### 3.3 Cross-restart continuity

1. A runtime assembled through `assemble_production_runtime()` against a given data directory, run
   for some ticks and dropped, must — when a fresh runtime is assembled through the same entry point
   against the same data directory — read back the prior session's persisted experience (store
   count > 0 and prior records retrievable) and resume the prior cross-tick `09`/`18` continuity and
   `04`/`05` affect state from the checkpoint.

## 4. Non-Functional Requirements

1. Performance: no new per-tick cost beyond the already-validated SQLite append / checkpoint save
   (R33/R42); the entry point only constructs backends and delegates.
2. Reliability: missing critical infrastructure fails fast at startup (no degraded path); SQLite
   parent directories are created as needed (existing backend behavior).
3. Observability and logging: no new logging mechanism; `21` stays the single logging mechanism.
4. Compatibility and migration: `assemble_runtime()` and its defaults are unchanged; the full
   network-free suite stays green; the data directory and `*.sqlite3` files are already git-ignored.

## 5. Code Behavior Constraints

1. Forbidden: changing `assemble_runtime()`'s default behavior or its in-memory auto-provisioning;
   the production defaults live only in the new entry point.
2. Forbidden: a degraded production path that silently runs non-persistent when a backend is
   unavailable (it must fail fast through the existing critical-dependency gate).
3. Forbidden: introducing a real embedding model as a hard/startup dependency; the offline hash
   fallback must keep the assembly network-free when no embedding credential is present.
4. The production entry point holds no cognitive policy; it only constructs durable backends + the
   embedding gateway and delegates to `assemble_runtime()`.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/runtime_assembly.py` - add `assemble_production_runtime()`
   and a `_production_embedding_gateway()` helper; the `DEFAULT_PRODUCTION_DATA_DIR` constant.
2. `helios_v2/src/helios_v2/composition/__init__.py` - export `assemble_production_runtime`.
3. `helios_v2/.env.example` - document the optional `HELIOS_EMBEDDING_*` variables.
4. Tests: `helios_v2/tests/test_production_assembly.py` (new) - defaults-on wiring + cross-restart
   continuity (offline, injected ready LLM gateway, tmp data dir).
5. Docs: `requirements/index.md` (row 82), `OWNER_GUIDE.*` (`22` composition root), `PROGRESS_FLOW.*`
   only if a maturity color changes (it does not).

## 7. Acceptance Criteria

1. `assemble_production_runtime(data_dir=<tmp>, gateway=<ready fake>)` assembles and starts up; its
   handle has a non-`None` durable experience store and continuity checkpoint, and the registered
   critical dependencies include `experience_store_ready`, `embedding_profile_ready`, and
   `continuity_checkpoint_ready`.
2. After session A runs N ticks against a tmp data directory and is dropped, session B assembled
   through the same entry point against the same directory sees store count > 0 (prior experience
   survived) and resumes a non-empty prior continuity/affect checkpoint (the checkpoint loads a
   prior snapshot at startup).
3. With no `HELIOS_EMBEDDING_API_KEY` in the environment, the production embedding gateway uses the
   deterministic-hash provider and the assembly is network-free; with the credential set it builds
   the OpenAI-compatible provider (verified without a network call, e.g. by inspecting the bound
   profile/provider).
4. `assemble_runtime()` defaults and the full network-free suite are unchanged; `index.md` has a row
   82 and the `22` `OWNER_GUIDE` entry records the standard production assembly with persistence
   defaulted on.
