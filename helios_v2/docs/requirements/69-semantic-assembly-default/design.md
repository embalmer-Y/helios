# Requirement 69 - Semantic Assembly as Default Runtime — Design

## 1. Design Overview

This design makes the semantic-memory assembly (the de-shimmed `03`-`10` cognitive chain)
the default behavior of `assemble_runtime()`. It introduces three coordinated changes:

1. A **shipped deterministic hash embedding provider** in the `helios_v2.embedding`
   package, promoted from the test-only `_FakeEmbeddingProvider` pattern already proven
   in `test_embedding_engine.py` and `test_p3_exit_evaluation.py`.
2. A **`default_signal_mode` field** on `RuntimeProfile` that selects between
   `"semantic"` (new default) and `"legacy_constant"` (explicit escape hatch).
3. **Auto-provisioning logic** in `assemble_runtime` that creates fresh in-memory
   store and embedding backends when `default_signal_mode` is `"semantic"` and the
   caller did not explicitly inject those capabilities.

The design preserves every existing invariant: the composition owner holds no cognitive
policy, the `FirstVersion*` paths remain available for the legacy mode, explicit
caller-provided capabilities always take precedence, and the `legacy_constant` mode
reproduces the pre-R69 default byte-for-byte.

## 2. Current State and Gap

### 2.1 Current state

`assemble_runtime()` with no arguments:

1. Registers `FirstVersionSensorySource` (constant `"hello runtime"` per tick).
2. Wires `FirstVersionDimensionEstimator` (constant novelty `0.6`, uncertainty `0.3`,
   social `0.0`, threat `0.2`, reward `0.1`).
3. Wires `FirstVersionAggregateEstimator` (constant `0.7`).
4. Wires `FirstVersionNeuromodulatorUpdatePath` (constant levels).
5. Wires `FirstVersionFeelingConstructionPath` (constant feeling vector).
6. Wires `FirstVersionMemoryFormationPath` (constant binding context).
7. Wires `FirstVersionWorkspaceCompetitionPath` (constant score `0.95`).
8. Wires `FirstVersionWorkingStateRetentionPath` (retain all).
9. Wires `FirstVersionConsciousCommitmentPath` (count-based).
10. `semantic_memory_enabled` is `False`; the `03`-`10` de-shim branches are not taken.

### 2.2 Gap

The semantic-memory assembly (which replaces every `FirstVersion*` path above with a
real-signal path) requires `experience_store` and `embedding_gateway` to be explicitly
injected. No default provisioning exists. The real cognitive chain is opt-in.

## 3. Target Architecture

### 3.1 New runtime data flow (default assembly)

```
assemble_runtime()
  └─ RuntimeProfile(default_signal_mode="semantic")
       ├─ experience_store is None → auto-create InMemoryExperienceStoreBackend → ExperienceStore
       ├─ embedding_gateway is None → auto-create DeterministicHashEmbeddingProvider → EmbeddingGateway
       └─ semantic_memory_enabled = True
            ├─ 03: GroundedDimensionEstimator (real novelty/uncertainty/social/threat/reward)
            ├─ 04: AppraisalDerivedNeuromodulatorUpdatePath (real appraisal → real levels)
            ├─ 05: NeuromodulatorDerivedFeelingConstructionPath (real levels → real feeling)
            ├─ 06: AffectGroundedMemoryFormationPath + SalienceGatedReplayCandidateSelector
            ├─ 07: SalienceWeightedWorkspaceCompetitionPath + BoundedAttentionRetentionPath
            ├─ 08: IgnitionFocalSelectionPolicy (real winner-take-all)
            ├─ 09: NeuromodulatorAwareThoughtGateSignalBridge (real arousal/activation/stimuli)
            └─ 10: SemanticStoreBackedDirectedMemoryCandidateProvider (real semantic recall)
```

### 3.2 Legacy mode data flow (escape hatch)

```
assemble_runtime(default_signal_mode="legacy_constant")
  └─ RuntimeProfile(default_signal_mode="legacy_constant")
       ├─ No auto-provisioning
       └─ semantic_memory_enabled = False
            └─ All FirstVersion* paths (byte-for-byte identical to pre-R69 default)
```

## 4. Data Structures

### 4.1 `DeterministicHashEmbeddingProvider`

```python
@dataclass(frozen=True)
class DeterministicHashEmbeddingProvider:
    """Owner: embedding inference gateway (default no-network provider).

    Purpose:
        Produce deterministic, fixed-dimension embedding vectors from input text using a
        character-hash-to-bucket algorithm. No network, no model, no randomness.

    Failure semantics:
        Never raises for valid inputs. Never fabricates a vector to mask a failure (the
        protocol rule applies to provider-level failures; this provider has none).

    Notes:
        Similar texts produce similar vectors because shared characters at shared positions
        contribute to the same buckets. The embedding quality is intentionally minimal — it
        provides a meaningful cosine-similarity ordering for the default assembly's novelty
        and retrieval computations, but is not a substitute for a real embedding model.
        Callers who need higher-quality embeddings inject an `OpenAICompatibleProvider` or
        a custom `EmbeddingProvider` through the existing `embedding_gateway` seam.
    """

    dimensions: int = 16

    def embed(
        self,
        profile: EmbeddingProfile,
        request: EmbeddingRequest,
        api_key: str,
    ) -> ProviderEmbedding:
        ...
```

### 4.2 `RuntimeProfile.default_signal_mode`

New field on the existing frozen `RuntimeProfile` dataclass:

```python
default_signal_mode: str = "semantic"
```

Allowed values: `"semantic"`, `"legacy_constant"`. Validated in `__post_init__`.

When `default_signal_mode` is `"semantic"`:
- `semantic_memory_enabled` returns `True` if either the caller provided both
  `experience_store` and `embedding_gateway`, OR the auto-provisioning created them.
- Auto-provisioning only fills in capabilities the caller did not explicitly provide.

When `default_signal_mode` is `"legacy_constant"`:
- `semantic_memory_enabled` returns `False` unless the caller explicitly provided both
  `experience_store` and `embedding_gateway` (in which case the explicit opt-in wins).
- No auto-provisioning occurs.

## 5. Module Changes

### 5.1 `helios_v2/embedding/engine.py`

Add `DeterministicHashEmbeddingProvider` class after `OpenAICompatibleProvider`.
Frozen dataclass, implements `EmbeddingProvider` protocol, 16-dimension hash buckets.

### 5.2 `helios_v2/embedding/__init__.py`

Re-export `DeterministicHashEmbeddingProvider`.

### 5.3 `helios_v2/composition/runtime_assembly.py`

1. Add `default_signal_mode` field to `RuntimeProfile` with `__post_init__` validation.
2. Update `_PROFILE_FIELDS` tuple to include the new field name.
3. Update `_resolve_profile` to handle the new field in loose-kwarg reconciliation.
4. In `assemble_runtime`, after profile resolution, when
   `default_signal_mode == "semantic"`:
   a. If `experience_store is None`: create
      `ExperienceStore(backend=InMemoryExperienceStoreBackend())`, call `.initialize()`,
      and assign to the local `experience_store` variable.
   b. If `embedding_gateway is None`: create `EmbeddingGateway` with
      `DeterministicHashEmbeddingProvider()`, a default profile, and a synthetic API key;
      assign to the local `embedding_gateway` variable.
   c. Add `experience_store_critical_dependency_spec()` and
      `embedding_profile_critical_dependency_spec()` to `resolved_specs`.
   d. Wire `ExperienceStoreReadinessDependencyProvider` and
      `EmbeddingReadinessDependencyProvider` into `resolved_provider`.
5. The existing `semantic_memory_enabled` property on `RuntimeProfile` already computes
   from `experience_store is not None and embedding_gateway is not None`. After
   auto-provisioning, the resolved profile will have both set, so the property returns
   `True` without modification.

### 5.4 `helios_v2/composition/dependencies.py`

No structural changes. The existing `experience_store_critical_dependency_spec()`,
`embedding_profile_critical_dependency_spec()`, `ExperienceStoreReadinessDependencyProvider`,
and `EmbeddingReadinessDependencyProvider` are reused as-is.

## 6. Migration Plan

### 6.1 Phase 1: Ship the new embedding provider (no behavior change)

Add `DeterministicHashEmbeddingProvider` to `helios_v2.embedding`. Export it. Add a
focused unit test. No existing assembly or test is affected.

### 6.2 Phase 2: Add `default_signal_mode` with `"legacy_constant"` as temporary default

Add the field to `RuntimeProfile` with `"legacy_constant"` as the initial default value.
Validate in `__post_init__`. Update `_PROFILE_FIELDS` and `_resolve_profile`. No existing
test breaks because the default behavior is unchanged.

### 6.3 Phase 3: Flip the default to `"semantic"` and add auto-provisioning

Change `default_signal_mode` default from `"legacy_constant"` to `"semantic"`. Add the
auto-provisioning logic in `assemble_runtime`. This is the breaking change for tests that
rely on constant shim values.

### 6.4 Phase 4: Migrate tests

Tests that depend on constant shim values must explicitly pass
`default_signal_mode="legacy_constant"` (or `deterministic_thought=True` which already
bypasses the semantic chain). Tests that should validate real-signal behavior are updated
to assert on real outputs.

### 6.5 Phase 5: Update documentation

Update `index.md`, `PROGRESS_FLOW.*`, and `OWNER_GUIDE.*` to reflect the new default.

## 7. Failure Modes and Constraints

1. **Auto-provisioned store initialization failure**: `InMemoryExperienceStoreBackend.initialize()`
   is total (no I/O); it cannot fail. If a future backend is substituted, the existing
   `experience_store_critical_dependency_spec` and fail-fast startup gate apply.
2. **Auto-provisioned embedding profile missing**: the auto-provisioned `EmbeddingGateway`
   must register a default profile. If the profile is not registered, the
   `embedding_profile_critical_dependency_spec` fails fast at startup.
3. **Caller provides store but not embedding (or vice versa)**: the existing
   `RuntimeProfile.__post_init__` validation (`embedding requires store`) rejects this
   before auto-provisioning runs. Auto-provisioning only fills both-None or respects the
   explicit value when one is provided.
4. **`legacy_constant` mode with explicit store+embedding**: the caller's explicit
   capabilities win. `semantic_memory_enabled` is `True` and the de-shim paths are used.
   This is the existing opt-in behavior and is not affected by `default_signal_mode`.

## 8. Observability and Logging

No new logging mechanism. The `semantic_memory_enabled` property on `RuntimeProfile`
already reflects the true assembly state. The existing `21` observability owner and
kernel instrumentation are unchanged.

## 9. Validation Strategy

1. **Unit tests** for `DeterministicHashEmbeddingProvider`: determinism, dimension,
   non-zero norm, similarity ordering for similar vs dissimilar texts.
2. **Unit tests** for `RuntimeProfile.default_signal_mode`: valid values accepted,
   invalid value raises `CompositionError`, default is `"semantic"`.
3. **Integration test** for default assembly: `assemble_runtime()` produces
   `semantic_memory_enabled == True`; a tick with varying stimuli produces varying
   `03` novelty (not the constant `0.6`).
4. **Regression test** for legacy mode: `assemble_runtime(default_signal_mode="legacy_constant")`
   produces the same tick output as the pre-R69 default assembly.
5. **Full suite**: all 762+ existing tests pass after migration.
