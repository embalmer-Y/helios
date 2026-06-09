# Requirement 69 - Semantic Assembly as Default Runtime

## 1. Background and Problem

The Helios v2 cognitive chain (`03`-`10`) has been fully de-shimmed through requirements `R35`-`R65`:
every owner from rapid salience appraisal through directed retrieval now consumes real,
non-constant signals under the **semantic-memory assembly**. However, this assembly is an
**opt-in** configuration: callers must explicitly inject an `experience_store` and an
`embedding_gateway` into `assemble_runtime()`. The default (no-argument) assembly still
registers `FirstVersion*` constant shim paths — fixed salience vectors, fixed neuromodulator
levels, fixed feeling states, fixed memory formation, fixed workspace scores, and fixed
gate signals — so every tick of the default runtime processes fabricated constants rather
than real signals.

This violates `ARCHITECTURE_PHILOSOPHY` §4.3 (unacceptable pseudo-completion state #1:
"the main path is essentially reply-first, only adding decorative steps before and after
the reply") and §7.4 (dependency constraint: "critical dependency absence must fail-fast;
compatibility/reduced-mode/temporary-fallback paths that hide critical capability absence
are not allowed"). The system's "real brain-like working mode" is currently an optional
experiment configuration rather than the default behavior.

Evidence:

1. `assemble_runtime()` with no arguments produces `semantic_memory_enabled = False`.
2. All `FirstVersion*` estimators, paths, and providers remain the default wiring.
3. A consumer or integrator calling the public assembly API sees constant shim outputs
   unless they independently discover and configure the semantic-memory opt-in.

## 2. Goal

Make the semantic-memory assembly (real signal processing through the `03`-`10` owner
chain) the **default** behavior of `assemble_runtime()`. When called with no arguments,
the runtime must use an in-memory experience store and a deterministic, network-free
hash-based embedding provider so the full de-shimmed cognitive chain runs without
external service dependencies. The prior constant-shim assembly must remain available
through an explicit, named escape hatch (`default_signal_mode="legacy_constant"`) but
must no longer be the silent default.

## 3. Functional Requirements

### 3.1 Default semantic assembly

1. `assemble_runtime()` called with no arguments must produce a runtime where
   `semantic_memory_enabled` is `True`.
2. The default assembly must auto-provision an in-memory `ExperienceStore` (using the
   existing `InMemoryExperienceStoreBackend`) and a deterministic, network-free
   `EmbeddingGateway` (using a shipped `DeterministicHashEmbeddingProvider`).
3. Under the default assembly, `03` appraisal must compute real novelty, uncertainty,
   social, threat, and reward dimensions; `04` neuromodulation must derive from real
   appraisal; `05` feeling must derive from real neuromodulation; `06` memory must form
   from real feeling with salience-gated consolidation; `07` workspace must run real
   competition; `08` consciousness must ignite a real focal winner; `09` gate must
   consume real arousal, activation, and selected-stimuli signals; `10` retrieval must
   use real candidate providers.
4. The default assembly must not require any network access, API key, or external
   service.

### 3.2 Legacy constant escape hatch

1. A new `RuntimeProfile.default_signal_mode` field must accept `"semantic"` (the new
   default) or `"legacy_constant"`.
2. When `default_signal_mode` is `"legacy_constant"`, the assembly must reproduce the
   pre-R69 default behavior byte-for-byte: all `FirstVersion*` constant shim paths,
   no auto-provisioned store or embedding, and `semantic_memory_enabled = False`.
3. The `default_signal_mode` must be validated at construction: any value outside the
   allowed set must raise `CompositionError`.

### 3.3 Explicit caller-provided capabilities take precedence

1. When the caller explicitly provides `experience_store` or `embedding_gateway`, those
   must be used regardless of `default_signal_mode`.
2. Auto-provisioning of in-memory backends must only occur when `default_signal_mode`
   is `"semantic"` AND the corresponding capability was not explicitly provided.
3. The existing mutual-exclusion rules (`embedding requires store`, `channel_cli vs
   external_signal_source`) must remain enforced.

### 3.4 Deterministic hash embedding provider

1. A `DeterministicHashEmbeddingProvider` must be shipped in the `helios_v2.embedding`
   package (not in tests).
2. It must conform to the existing `EmbeddingProvider` protocol.
3. It must produce deterministic, fixed-dimension vectors from input text using a
   character-hash-to-bucket algorithm (no network, no model, no randomness).
4. Similar texts must produce similar vectors (cosine similarity is meaningful for
   nearest-neighbor retrieval).
5. It must never raise for valid inputs; it must never fabricate a vector to mask a
   failure (the protocol's existing failure-semantics rule).

## 4. Non-Functional Requirements

1. **Performance**: the deterministic hash embedding must complete in under 1 ms per
   call on typical input text (< 500 characters). The in-memory store operations must
   complete in under 5 ms per append or retrieval.
2. **Reliability**: auto-provisioned backends must never introduce a failure mode that
   the explicit opt-in assembly does not already have. The in-memory backend has no
   durability (data lost on process exit), which is an acceptable trade-off for the
   default assembly; restart continuity requires the caller to inject a durable backend.
3. **Observability**: the `semantic_memory_enabled` property must reflect the true
   assembly state. No new logging mechanism is introduced.
4. **Compatibility**: the `legacy_constant` mode must reproduce the pre-R69 default
   assembly byte-for-byte. Existing callers that explicitly inject store/embedding
   must see no behavior change.

## 5. Code Behavior Constraints

1. `DeterministicHashEmbeddingProvider` must live in `helios_v2.embedding.engine` and
   be re-exported from `helios_v2.embedding.__init__`. It must not import any network
   library or external SDK.
2. `RuntimeProfile.default_signal_mode` validation must occur in `__post_init__`, not
   deferred to `assemble_runtime`. Invalid values must raise `CompositionError`.
3. Auto-provisioned in-memory store and embedding must be created inside
   `assemble_runtime` (or the profile resolver), not as module-level singletons. Each
   `assemble_runtime` call must get a fresh instance.
4. The composition owner must not hold any cognitive policy for the auto-provisioned
   backends. The in-memory store and hash embedding are infrastructure, not cognition.
5. No `FirstVersion*` constant shim path may be the default wiring when
   `default_signal_mode` is `"semantic"`.

## 6. Impacted Modules

1. `helios_v2/embedding/engine.py` — new `DeterministicHashEmbeddingProvider` class.
2. `helios_v2/embedding/__init__.py` — re-export new provider.
3. `helios_v2/composition/runtime_assembly.py` — `RuntimeProfile` new field,
   `assemble_runtime` auto-provisioning logic, `_resolve_profile` reconciliation.
4. `helios_v2/composition/dependencies.py` — no structural change, but the auto-
   provisioned store/embedding must wire the existing readiness dependency specs.
5. `tests/test_runtime_composition.py` — tests using default assembly must be migrated.
6. `tests/test_runtime_stage_chain.py` — tests using default assembly must be migrated.
7. `helios_v2/docs/requirements/index.md` — new R69 row.
8. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` / `PROGRESS_FLOW.en.md` — sync line update.
9. `helios_v2/docs/OWNER_GUIDE.zh-CN.md` / `OWNER_GUIDE.md` — composition root update.

## 7. Acceptance Criteria

1. `assemble_runtime()` with no arguments produces `semantic_memory_enabled == True`
   and the `03` appraisal engine uses `GroundedDimensionEstimator` (not
   `FirstVersionDimensionEstimator`).
2. `assemble_runtime()` with no arguments and no external signal source produces a
   tick where `03` novelty is computed from the real embedding distance to stored
   experience (not the constant `0.6`).
3. `RuntimeProfile(default_signal_mode="legacy_constant")` produces
   `semantic_memory_enabled == False` and all `FirstVersion*` paths, byte-for-byte
   identical to the pre-R69 default.
4. `RuntimeProfile(default_signal_mode="invalid")` raises `CompositionError` at
   construction time.
5. `DeterministicHashEmbeddingProvider` is importable from `helios_v2.embedding`,
   conforms to `EmbeddingProvider`, and produces deterministic 16-dimension vectors
   with no network access.
6. Existing tests that explicitly use `default_signal_mode="legacy_constant"` or
   `deterministic_thought=True` pass with no behavior change.
7. A new integration test validates the default assembly runs the full de-shimmed
   `03`-`10` chain with real signals and produces measurably different outputs for
   different stimuli across ticks.
8. Full test suite passes (`pytest helios_v2/tests/`).
