# Requirement 96 - Real Semantic Embedding as Default (B2 closure)

> **Status**: drafted, awaiting owner review (2026-06-15)
> **Owner**: `helios_v2.composition` (assembly-side wiring) + `helios_v2.embedding` (capability-side provider)
> **Wave**: W3, the first slice in the new owner-confirmed order (R96 → R97 → R98 → R99+ → P4)
> **Renumbering history**: R98 → R96 (after W2.5 R94 / W2.6 R95 inserted, the originally-planned R98 was shifted to R96 to keep the W3/W4 stack consecutive); the work content is unchanged from the ROADMAP §10 W3 R98 description.
> **Embedding model decision (owner-confirmed 2026-06-15)**: option **A — OpenAI-compatible cloud** (走 R34 已就位的 `OpenAICompatibleEmbeddingProvider`，与 `.env` 现有 `HELIOS_EMBEDDING_API_KEY` / `HELIOS_EMBEDDING_BASE_URL` 凭证同套；本地小模型 / 自训方案留作 P5 学习循环立起后的降级或增强路径，**不**进入本切片）。
> **Model default**: `text-embedding-3-small` (1536 维, OpenAI, 性价比高，中英文均支持)。R97 中文 grounding 接入时可换 `bge-m3` (1024 维多语)。

## 1. Background and Problem

R69 made the semantic-memory assembly the default behavior of `assemble_runtime()`: every no-argument call now boots a runtime where `03`–`10` are driven by real signals, and `semantic_memory_enabled == True`. R34 (the `P2` second slice) already shipped the full embedding capability owner, the OpenAI-compatible provider, the deterministic hash fallback provider, the store-side vector storage and bounded cosine similarity search, and the `embedding_profile_ready` critical dependency.

The 2026-06 real-LLM Chinese-emotion long-run (ROADMAP §9) captured and verified a decisive fact that the current default assembly still gets wrong: **`03` appraisal, `04`–`05` affect, and `06`–`10` recall are all driven by a 16-dimension deterministic character-hash vector that has no semantic structure** (R69 auto-provisions `DeterministicHashEmbeddingProvider` with `model="deterministic-hash"`). The captured evaluation:

1. The seven appraisal-responsive affect channels (DA/NE/5-HT/ACh/Cort/Oxy/Opioid) produced *mean|Δ| ≈ 0.09* on real Chinese emotional input, with a *cortisol positive/negative emotion separation of -0.0095* (i.e. essentially zero and slightly inverted). The R36 appraisal-derived neuromodulator drive and the R38/R44 derived-feeling chain therefore cannot distinguish joy from grief in Chinese, because the input cosine against the stored experience cosine is a hash-cosine noise signal, not a semantic-similarity signal.
2. The R40 prototype-anchored `threat` / `reward` is `B_functional_inspiration` / `C_engineering_hypothesis` and uses an English-only prototype set, so on Chinese input the two dimensions are equally non-semantic.
3. The R52 recalled-replay path surfaces prior affect memories by binding-context content cosine, but when both binding-context content and stored experience summary are hash vectors, the cosine ranking is a noise ranking and the "most similar" memory is effectively a random pick. The R40 prototypes' cosine is similarly noise.
4. Memory-recall in the R83 long-run benchmark returned only "count of items in each layer" and the "first hit summary truncated to 80 characters"; even when the recall machinery works, the recalled item is the hash-closest, not the semantically-closest, so the system "remembers it talked" but cannot remember "what was talked about".

The ROADMAP §9.1 root-cause verdict is unambiguous: **hash embedding cannot provide the causal signal `03`/`04`/`05`/`09` need for the FG-2 emotion-appropriateness standard**. R90's memory-fidelity probe measures recall mechanics; the recall *content* is meaningless until the embedding itself is semantic. R91's present-field already brought the operator's words into the `11` prompt, so the cognitive chain now has the right *content* on the input side and the right *appraisal dimensions* on the salience side — the only piece still fabricated is the embedding that joins them.

R34 already exposed everything R96 needs:

1. `OpenAICompatibleEmbeddingProvider` in `helios_v2.embedding.engine` (lazy `openai` SDK import inside the call path; fail-fast on empty api key / empty input / provider error; never fabricates a vector).
2. `DeterministicHashEmbeddingProvider` (R69-promoted) as the network-free no-fabrication default.
3. `EmbeddingGateway.embed` fail-fast + `EmbeddingGateway.check_static_readiness` network-free + `EmbeddingGateway.probe_live_readiness` opt-in.
4. `embedding_profile_ready` critical dependency already wired into the R82 production-assembly dependency gate.

R96 is therefore **not** a new capability owner. It is the **first narrow switch from the placeholder provider to the real OpenAI-compatible cloud provider** at the composition layer, with a hard-rule on when the switch happens and a hard-fallback (not silent degradation) when the conditions for the real switch are not met. The cognitive owners are not touched; the embedding owner is not touched; the persistence owner is not touched. Only `composition.runtime_assembly` and the `RuntimeProfile` capability bundle change.

## 2. Goal

Make **real OpenAI-compatible cloud embedding** the *active* default of `assemble_runtime()` whenever the runtime environment declares the necessary credentials, so that `03` novelty-from-memory, `03` threat/reward prototype cosine, `06` binding-context content cosine, `06`/`10` semantic recall, and any future `05`/`09` consumer of the `34` embedding substrate all run on a real semantic vector. When the credentials are absent or the live probe fails at startup, the assembly must **hard-fall back** to `DeterministicHashEmbeddingProvider` so the existing 1110-test green baseline is preserved byte-for-byte; this fallback is explicit (recorded in the resolved profile), not silent, and the embedding-profile-readiness critical dependency still fails fast on an explicitly-enabled-but-unready profile. The B2 root-cause (ROADMAP §9.1) must be closed: re-running the 2026-06 emotion long-run with real embedding must produce a measurable positive-vs-negative emotion separation in the `04`/R36 appraisal-derived channels (and the B2 §3.2 acceptance criteria below are sized to that).

## 3. Functional Requirements

### 3.1 Capability wiring (no owner change)

1. The new behavior must be expressed **purely at the composition layer** — `helios_v2.composition` and `helios_v2.embedding` (provider selection only) — and must not change any cognitive owner's code, any cognitive owner's contract, the `34` embedding owner's public API, the `33` persistence owner's API, the canonical stage chain, the `21` observability seam, or the `22` composition's own boundary rules.
2. The new behavior must be triggered by a real-environment signal, **never by a hard-coded "use real embedding" boolean in code**. The trigger is the presence (and validity) of the OpenAI-compatible credential at the moment `assemble_runtime` resolves the profile.
3. The selected provider must be exposed on the resolved `RuntimeProfile` (as `embedding_provider_kind: Literal["openai_compatible", "deterministic_hash"]` and `embedding_provider_model: str`) so the test / probe / runtime surface can verify which provider is active without re-deriving it.

### 3.2 Credential resolution (no new dependency)

1. The runtime must read **exactly three** environment variables to decide the active embedding provider, with the names and the precedence as follows:
   1. `HELIOS_EMBEDDING_API_KEY` — the bearer key. **Non-empty after `str.strip()`** is the gate; a whitespace-only value counts as absent.
   2. `HELIOS_EMBEDDING_BASE_URL` — the endpoint base URL. **Defaults to `https://api.openai.com/v1`** when unset or empty.
   3. `HELIOS_EMBEDDING_MODEL` — the model name. **Defaults to `text-embedding-3-small`** when unset or empty. A `bge-m3` (1024-dim) or other OpenAI-compatible embedding model is acceptable when the operator sets this explicitly.
2. The credential resolution must be done by a new `composition.embedding_provider_resolution` owner-neutral helper, with the resolved decision exposed as a frozen `EmbeddingProviderResolution` dataclass carrying `kind`, `model`, `base_url`, `dimensions: int | None` (resolved from a small static `EMBEDDING_MODEL_DIMENSIONS` map for the well-known models; `None` if unknown), and `api_key_env_var: str`. Composition is the only place that reads the env directly; the embedding owner receives a constructed `EmbeddingProfile` and an already-resolved `OpenAICompatibleEmbeddingProvider`.
3. The resolution must be deterministic given an injected `env` mapping (default `os.environ`); tests must not need to mutate the real environment. The existing `EmbeddingGateway(env=...)` injection seam is reused for the env mapping.

### 3.3 Auto-provisioning seam (in `runtime_assembly`)

1. The R69 auto-provisioning block in `assemble_runtime` (the `if resolved_profile.default_signal_mode == "semantic":` branch around `runtime_assembly.py` L1207–L1245) must be extended: the current path always builds a `DeterministicHashEmbeddingProvider` with `model="deterministic-hash"`. The new path must:
   1. First call the new `resolve_embedding_provider(env)` helper.
   2. If `kind == "openai_compatible"`: build an `OpenAICompatibleEmbeddingProvider` (already in `helios_v2.embedding`) and an `EmbeddingProfile` carrying `model=resolved.model`, `api_key_env="HELIOS_EMBEDDING_API_KEY"`, `base_url=resolved.base_url`, `dimensions=resolved.dimensions`. Use the existing `EmbeddingGateway(provider=..., registry=...)` with `env=injected_env_mapping` (so the gateway reads the same key the resolver saw).
   3. If `kind == "deterministic_hash"`: build the same R69 `DeterministicHashEmbeddingProvider` + `EmbeddingProfile(model="deterministic-hash", ...)` exactly as today. The fallback profile's `api_key_env` is `"HELIOS_AUTO_EMBEDDING_KEY"` with a non-empty stub value in the injected env mapping (the same trick R69 already uses, byte-for-byte preserved).
2. The provider selection must be made **before** the resolved profile is frozen, so `semantic_memory_enabled` and the new `embedding_provider_kind` / `embedding_provider_model` reflect the actual selection.
3. The explicit caller-provided `embedding_gateway` path (caller injects a fully-built gateway) must still take precedence: the resolver must be **skipped** entirely when the caller supplied `embedding_gateway is not None` (preserve R69's "explicit caller-provided capabilities always take precedence" rule, byte-for-byte).
4. The `default_signal_mode == "legacy_constant"` path must be untouched: it does not auto-provision any store or gateway; the new resolver is also skipped on that path.

### 3.4 Fail-fast and readiness

1. The `embedding_profile_ready` critical dependency (`EmbeddingReadinessDependencyProvider`, R34 §3.4 + R82) must be exercised against the *new* resolved profile (real cloud or hash fallback) exactly as it is today. Its `check_static_readiness` must report:
   - For the real-cloud profile: `static_ready=True` iff `HELIOS_EMBEDDING_API_KEY` was non-empty at the moment of resolution.
   - For the hash fallback profile: `static_ready=True` iff the `HELIOS_AUTO_EMBEDDING_KEY` stub env entry the resolver injected into the gateway's `env` mapping is non-empty. (This is a *non-runtime* `True` from the perspective of the dependency gate, because the hash provider does not need a key; the value is set to `"auto-provisioned"` for self-documenting purposes.)
2. When the resolver chose `openai_compatible` but the key is later removed (env mutation between resolution and startup), the dependency gate's `static_ready=False` must still fail fast at startup — the same `CompositionError`/dependency-missing hard stop as R34.
3. The optional live probe (`EmbeddingGateway.probe_live_readiness`) must be **off by default** for the assembled runtime (preserves "live probe is never part of the mandatory startup gate" from R34). The R82 production assembly's startup gate must remain network-free.
4. The new resolver must never silently upgrade a hash-fallback to a real embedding: if `HELIOS_EMBEDDING_API_KEY` is absent at resolution time, the hash fallback is the *one and only* default; no env mutation between resolution and the first tick can change that without a fresh `assemble_runtime()` call.

### 3.5 B2 root-cause closure (verifiable)

1. The B2 closure criterion is the ROADMAP §9.1 verdict: "similar emotional inputs produce a measurable and directionally appropriate affect separation" (the R36 appraisal-derived `04` chain's response to positive vs negative input must not be ~0). For R96, the requirement-level acceptance is:
   1. The R35 novelty-from-memory signal must change measurably when the active embedding provider switches from `DeterministicHashEmbeddingProvider` to `OpenAICompatibleEmbeddingProvider`, for the same input batch and the same `PersistedExperienceRecord` corpus.
   2. The R40 `threat` / `reward` prototype-cosine signal must change measurably across the same provider switch.
   3. The R52 recalled-replay path must rank the semantically-most-similar prior affect-memory above a less-similar more-recent memory in at least one of the new-emotion-test fixtures (the semantic-ranking-over-recency test that R34 §7 acceptance introduced, replayed under the real provider).
2. These are the **3 must-measure shifts** that close B2. A focused test suite (`tests/r96_b2_closure.py`, see design §10 / task §1.5) drives the same fixture corpus through both providers and asserts the directional shift, with a recorded `B2ClosureReport` per provider and a falsifiable `b2_closed: bool` verdict.
3. The B2 acceptance runs in **two paths**:
   1. **Network-free path** (CI / no real LLM): uses a deterministic `FakeOpenAICompatibleEmbeddingProvider` (registered in tests) that returns synthetic-but-coherent 1536-dim vectors. CI must pass on this path; no real API key is required.
   2. **Real-LLM path** (opt-in, post-merge): runs the emotion-test corpus against the real provider when `HELIOS_EMBEDDING_API_KEY` is set, and asserts the same shifts. The 2026-06-15 emotion test (ROADMAP §9.1) is the reference. This path is documented in `scripts/r96_b2_real_llm_probes/` and is *not* in CI.

### 3.6 Honest "fallback is a placeholder" record

1. The runtime surface must expose, on the resolved `RuntimeProfile` and via the `embedding_provider_kind` field, *which* provider is active in this assembled runtime. The `b2_closed: bool` in the B2 closure report must be `True` iff `embedding_provider_kind == "openai_compatible"` *and* the live probe succeeds; otherwise it must be `False` and the report must carry an explicit `fallback_reason` string. This is the R59 "honest absence" rule (no fabricated signal labeled as real), extended to the embedding layer: a runtime that boots with the hash fallback is not silently "semantic" — it is explicitly "semantic-with-hash-fallback", and the next-token report will say so.
2. The R95 followup "channel driver is the sole source of truth for op names" rule is mirrored here: **the embedding provider is the sole source of truth for vector quality**; the cognitive owners receive vectors and never know which provider produced them. There is no `embedding_provider_kind` field on any `PersistedExperienceRecord`, on any `Stimulus`, on any `MemoryRetrievalCandidate`, or on any `13`/`11` prompt — the *fact* of "hash vs cloud" is a composition-level observability fact, not a cognition-level one. The test/probe surface can read it from the resolved profile.

## 4. Non-Functional Requirements

1. **Performance**: the resolver adds no measurable startup cost (it is a single `os.environ` lookup and a dict construction, < 100 µs typical). The real-cloud embed cost is on the existing R34 path; the hash-fallback cost is unchanged from R69.
2. **Reliability**: identical input text must produce identical vectors under each provider (deterministic within provider). The new resolver must never raise for valid env inputs; the gateway's existing `EmbeddingError` rules (R34 §3.1) remain the hard-stop on provider failure. **No silent degradation** at any layer: missing key → resolver picks hash → profile reports `kind="deterministic_hash"` → `embedding_profile_ready` reports `static_ready=True` for the hash stub key → the assembled runtime boots with the same 1110-test-green baseline; the consumer (probe / test / CI) can see the kind and the B2 verdict.
3. **Observability**: the new behavior must not introduce a second logging mechanism. The `embedding_provider_kind` / `embedding_provider_model` fields on the resolved profile are the *only* new observability fact; everything else flows through the existing R34 readiness report, the R21 `LogEvent` stream (used only by the 21 owner), and the R90 memory-fidelity probe / R88 drift / R89 Turing harness as before. The R95 followup no-adhoc-logging guard test must keep passing.
4. **Compatibility and migration**:
   1. The pre-R96 default assembly (R69 + R82) is byte-for-byte preserved when `HELIOS_EMBEDDING_API_KEY` is absent (i.e. the R69 hash-fallback path runs exactly as today; the existing 1110 tests stay green with zero modification). The `legacy_constant` mode is also unchanged.
   2. When `HELIOS_EMBEDDING_API_KEY` is present, the active provider changes from hash to real cloud; the 1110 tests' network-free guarantees are preserved by the network-free CI path using the `FakeOpenAICompatibleEmbeddingProvider`. **No existing test gets modified** to pass — they pass as-is, and the new tests live in a new file.
   3. The R34 durable experience store (SQLite + memory) already supports per-record optional embedding vectors; no schema change is needed. Existing R82 store files load correctly (rows without embeddings are excluded from semantic results, exactly as today). The B2 closure's recalled-replay path uses the R52 surface, which is also unchanged.
5. **Dependency hygiene**: no new heavy dependency. R34 already lazy-imports the `openai` SDK inside `OpenAICompatibleEmbeddingProvider.embed`; the R96 change reuses that. No new `pip` requirement.

## 5. Code Behavior Constraints

1. The embedding owner is a capability owner, not a cognitive owner (R34 §5.1 — preserved verbatim). R96 must not import or call any cognitive owner; it must not add a new cognition-owner import surface.
2. The persistence owner must remain free of any embedding-owner import (R34 §5.2 — preserved). R96 does not touch the persistence owner.
3. The composition glue must remain owner-neutral: the new resolver and the new profile field are plain data + provider construction, no cognitive policy.
4. **No new logging mechanism**: `print` and `logging` remain forbidden under `helios_v2/src/`. The R95 followup no-adhoc-logging guard must keep passing.
5. **No owner-boundary violation**: the R56 / R57 owner-boundary guards must keep passing. The new resolver does not introduce any sensitivity coefficient, autonomy pressure constant, or feeling-coupling coefficient. The only thing composition now does is *pick a provider* — the same composition responsibility R34 already exercises.
6. **No degraded path on the real-provider branch**: when the resolver picks `openai_compatible` but a tick-time `embed()` call fails, the existing R34 hard-stop (`EmbeddingError`) propagates; there is no recency fallback, no hash fallback mid-runtime, no retry. A failed tick is a failed tick. The hash fallback is a *startup-time* decision, not a per-tick fall-back.
7. **No embedding-provider kind leak into prompts or persisted records**: the new `embedding_provider_kind` field exists on the *resolved profile* (composition-level), never on cognitive contracts, never on `PersistedExperienceRecord`, never on `Stimulus.metadata`, never on `InternalThoughtRequest`. The R95 "channel driver is the sole source of truth" rule is mirrored.
8. **No mutation of `_embed_text` / `_embed_record` closures' shape**: the composition-side closure that wraps `embedding_gateway.embed` is unchanged. The only new behavior is *which gateway* it is wrapped around, decided once at resolve time.
9. **The `openai` SDK is not a hard runtime dependency for the default assembly** (R34 §4.5 — preserved). The resolver only picks the cloud provider when the credential is set; the network-free path remains the lazy-import path.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py` (new) — `resolve_embedding_provider(env) -> EmbeddingProviderResolution`, the static `EMBEDDING_MODEL_DIMENSIONS` map, and the `EmbeddingProviderKind` literal.
2. `helios_v2/src/helios_v2/composition/embedding_provider_resolution.py` exports added to `composition/__init__.py`.
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` — extend the R69 auto-provisioning block; add `embedding_provider_kind` and `embedding_provider_model` fields to `RuntimeProfile` (frozen dataclass) and to `_resolve_profile`; wire the resolver into the `semantic` default-signal-mode branch.
4. `helios_v2/src/helios_v2/composition/bridges.py` — no new bridge; the existing `_embed_text` / `_embed_record` closures already wrap the gateway.
5. `helios_v2/src/helios_v2/embedding/engine.py` — no change. The `OpenAICompatibleEmbeddingProvider` and `DeterministicHashEmbeddingProvider` are reused as-is.
6. `helios_v2/src/helios_v2/embedding/contracts.py` — no change. The `EmbeddingProfile` dataclass already accepts `dimensions` and `api_key_env` and `base_url`.
7. `helios_v2/src/helios_v2/composition/dependencies.py` — no change. The existing `EmbeddingReadinessDependencyProvider` consumes the resolved profile.
8. `helios_v2/src/helios_v2/tests/test_embedding_provider_resolution.py` (new) — unit tests for the resolver; tests for the `EMBEDDING_MODEL_DIMENSIONS` map; tests for the env-missing / whitespace-only / explicit-set / explicit-bge-m3 paths.
9. `helios_v2/src/helios_v2/tests/test_runtime_composition.py` (extend) — assertion that `assemble_runtime()` with `HELIOS_EMBEDDING_API_KEY` set in the injected env produces `embedding_provider_kind == "openai_compatible"`; assertion that the resolved profile records the right model; assertion that explicit `embedding_gateway=` still wins; assertion that `legacy_constant` mode skips the resolver.
10. `helios_v2/src/helios_v2/tests/r96_b2_closure.py` (new) — B2 closure focused tests; `FakeOpenAICompatibleEmbeddingProvider` plus a corpus; per-provider `B2ClosureReport` with `b2_closed: bool`; the three must-measure shifts (R35 novelty, R40 threat/reward, R52 recall-over-recency).
11. `helios_v2/scripts/r96_b2_real_llm_probes/` (new, opt-in) — real-cloud re-run of the 2026-06 emotion test corpus against the real provider. Documented in `scripts/r96_b2_real_llm_probes/README.md`.
12. `helios_v2/tests/test_no_adhoc_logging_guard.py` (no change, must keep passing).
13. `helios_v2/tests/test_composition_owner_boundary_guard.py` (no change, must keep passing).
14. `helios_v2/docs/requirements/index.md` (Task 6) — add the R96 row, maturity per evidence.
15. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` (Task 6) — add a §4.X owner-snapshot note recording the composition-side change and that the embedding owner is unchanged.
16. `helios_v2/docs/ROADMAP.zh-CN.md` (Task 6) — flip R96 from "next slice" to "delivered" once tests are green; the W3 / W4 ordering does not change.
17. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` + `PROGRESS_FLOW.en.md` (Task 6) — note that the default semantic assembly is now real-embedding-aware (when credentials present) while the existing coloring stays.

## 7. Acceptance Criteria

1. **Credential-driven switch**: a fresh `assemble_runtime()` call with `HELIOS_EMBEDDING_API_KEY="sk-..."` in the (injected) env produces a resolved `RuntimeProfile` whose `embedding_provider_kind == "openai_compatible"` and `embedding_provider_model == "text-embedding-3-small"` (or the explicitly-set model). With the key absent, the same call produces `embedding_provider_kind == "deterministic_hash"`. Both are verified in `test_runtime_composition.py` extend and `test_embedding_provider_resolution.py`.
2. **Byte-for-byte preservation of the 1110 baseline**: with `HELIOS_EMBEDDING_API_KEY` absent, `assemble_runtime()` runs and all 1110 existing tests + 4 skipped + 5 pre-existing wall-clock-profile + lt1 failures are **unchanged** (no test file modified, no expected output modified). The `legacy_constant` mode is also unchanged.
3. **Explicit caller-provided gateway still wins**: `assemble_runtime(embedding_gateway=FakeEmbeddingGateway(), ...)` produces the resolved profile's `embedding_provider_kind == "openai_compatible"` (because the caller's gateway is openai-compatible) *or* the equivalent for the fake; the resolver is not consulted.
4. **No owner-boundary drift**: the R56 (`<salience>_to_<channel>`) and R57 (autonomy drive pressure) guards pass; the new resolver introduces no sensitivity coefficient, no pressure constant, no threshold. The R95 followup no-adhoc-logging guard passes.
5. **`embedding_profile_ready` fail-fast unchanged**: when the resolver chose `openai_compatible` but the env no longer has `HELIOS_EMBEDDING_API_KEY` (mutated between resolution and startup), `assemble_runtime()` raises `CompositionError` exactly as R34; the runtime does not boot. The dependency-gate behavior is preserved byte-for-byte.
6. **B2 closure, network-free path**: `tests/r96_b2_closure.py` runs the same emotion-corpus fixtures under both providers (real-cloud simulated by `FakeOpenAICompatibleEmbeddingProvider`, and `DeterministicHashEmbeddingProvider`) and reports a per-provider `B2ClosureReport`. The report must show:
   1. R35 novelty signal: real-cloud case differs from the hash case on at least 8 of 10 fixtures (per-fixture sign of the change, recorded).
   2. R40 threat / reward prototype-cosine: real-cloud case differs from the hash case on at least 8 of 10 fixtures.
   3. R52 recalled-replay path: the real-cloud case ranks a known semantically-similar prior affect-memory above a less-similar more-recent memory; the hash case does not (recorded as a passing *and* failing witness of the B2 verdict).
   4. `b2_closed: bool` is `True` for the real-cloud case and `False` for the hash case; the report records `fallback_reason="hash_placeholder"` for the hash case.
7. **B2 closure, real-LLM path (opt-in)**: `scripts/r96_b2_real_llm_probes/run.py` runs the 2026-06 emotion corpus (the 89-utterance / 16-visitor set) against the real provider, with the same recording discipline (per-tick `04`/R36 levels + LLM I/O log). The probe result JSON, committed under `docs/requirements/96-real-semantic-embedding/probe_results.md` (gitignored artifacts under `logs/r96_b2_real_llm_probes/`), records the post-R96 `cortisol` positive-vs-negative emotion separation. The acceptance is **directional**: a measurable increase over the pre-R96 -0.0095 (i.e. an absolute separation ≥ +0.05 in either direction, with the expected direction being positive for cortisol-under-negative-input). The exact numerical target is recorded and not over-claimed; the acceptance is the directional shift + a recorded `b2_closed_real_llm: bool`.
8. **No schema change in the persistence owner**: the SQLite migration path is unchanged; existing R82 store files load correctly; the `embedding` column's nullable behavior is preserved.
9. **No public-API change in the `34` embedding owner**: the public `EmbeddingGatewayAPI` protocol surface is unchanged; the public `EmbeddingProfile` / `EmbeddingRequest` / `EmbeddingResult` contracts are unchanged.
10. **Documentation consistency**: `index.md`, `ARCHITECTURE_BOUNDARIES.md`, `BRAIN_ARCHITECTURE_COMPARISON.md`, `PROGRESS_FLOW.en.md` / `zh-CN.md` reflect the same boundary truth as the code; the W2.6 / R95 + R95-followup test baseline is preserved.

## 8. Future Extension Scope (recorded, not in this slice)

The following are explicitly out of scope for R96 and must each be its own requirement package, preserving the owner boundaries:

1. **R97 — Chinese-appraisal grounding**: once the real provider is in place, the `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` set is replaced with a multilingual / Chinese-anchored set (or a learned / weakly-supervised set), and the model choice in `HELIOS_EMBEDDING_MODEL` may move to `bge-m3` for tighter cross-cultural alignment. R97 is the natural follow-up; R96 only ships the *infrastructure switch*.
2. **Real-LLM emotion-test re-run as CI gate**: a CI-tier test that runs the B2 closure corpus under the real provider is currently opt-in; promoting it to CI requires either a CI-side credential (security/secret-management concern, out of scope for R96) or a stub provider that is empirically calibrated to the real provider's responses (out of scope, R110+ concern).
3. **Self-trained embedding (option C in the ROADMAP §8 decision)**: deferred to P5 learning-cycle setup. R96 only ships option A.
4. **Bounded-window / ANN retrieval (R102-equivalent)**: not a real blocker per the R83 long-run finding (per-tick cost is dominated by per-tick fixed costs, not the cosine scan over the current 1k-record store); deferred to the P5 dual-track memory slice.
5. **Multi-provider fan-out** (one runtime uses two different embedding models for two different purposes): not in scope. R96 picks one provider per runtime.

## 9. Cross-References

- ROADMAP §1.0 (new-order table), §3 (near-term queue), §8 item 5 (embedding model decision recorded), §10 W3 R96 description, §11.2 (probe-validation discipline).
- `ARCHITECTURE_BOUNDARIES.md` §4 core owner map (composition owner) and the `34` embedding owner snapshot.
- `BRAIN_ARCHITECTURE_COMPARISON.md` `gap_persistence_and_learning` (recall is now semantic) and the `gap_external_afferent_source` extension (the embedding substrate is the second causal chain of FG-2 alongside R51 interoception and R59 external afferent).
- `OWNER_GUIDE.md` §3.2 (composition owner) and the §3.5 (embedding capability owner) — composition-side update.
- R34 (semantic experience retrieval), R69 (semantic assembly as default runtime), R82 (standard production assembly), R95 + R95 followup (behavior-neutral schema, channel driver as sole source of truth), R97 (next slice).
