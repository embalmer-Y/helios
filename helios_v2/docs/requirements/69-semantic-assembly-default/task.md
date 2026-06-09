# Requirement 69 - Semantic Assembly as Default Runtime — Task

## 1. Task Breakdown

### Task A: Ship `DeterministicHashEmbeddingProvider`

**Scope**: Add the deterministic hash embedding provider to the embedding package.
**Dependency**: None (additive, no existing code affected).
**Touched modules**:
- `helios_v2/src/helios_v2/embedding/engine.py` — new class.
- `helios_v2/src/helios_v2/embedding/__init__.py` — re-export.
- `helios_v2/tests/test_embedding_engine.py` — add focused unit tests.

**Completion definition**:
- `DeterministicHashEmbeddingProvider` is importable from `helios_v2.embedding`.
- Conforms to `EmbeddingProvider` protocol.
- Produces deterministic 16-dimension vectors; same text → same vector; similar text →
  higher cosine similarity than dissimilar text.
- No network import, no external SDK import.
- Unit tests pass: `pytest helios_v2/tests/test_embedding_engine.py -x`.

**Validation step**:
```
pytest helios_v2/tests/test_embedding_engine.py -x -k "deterministic_hash"
```

### Task B: Add `default_signal_mode` to `RuntimeProfile`

**Scope**: Add the new field with validation, update profile machinery.
**Dependency**: None (additive; default value `"semantic"` not yet wired to auto-provision).
**Touched modules**:
- `helios_v2/src/helios_v2/composition/runtime_assembly.py` — `RuntimeProfile` field,
  `__post_init__` validation, `_PROFILE_FIELDS` tuple, `_resolve_profile` reconciliation.

**Completion definition**:
- `RuntimeProfile()` has `default_signal_mode == "semantic"`.
- `RuntimeProfile(default_signal_mode="legacy_constant")` is accepted.
- `RuntimeProfile(default_signal_mode="invalid")` raises `CompositionError`.
- `_PROFILE_FIELDS` includes `"default_signal_mode"`.
- `_resolve_profile` handles the loose-kwarg form.
- Existing tests still pass (auto-provisioning not yet active).
- Unit test: `pytest helios_v2/tests/test_runtime_composition.py -x -k "signal_mode"`.

**Validation step**:
```
pytest helios_v2/tests/test_runtime_composition.py -x -k "signal_mode or profile"
```

### Task C: Implement auto-provisioning in `assemble_runtime`

**Scope**: When `default_signal_mode == "semantic"` and store/embedding are not provided,
auto-create in-memory backends and wire the dependency specs/providers.
**Dependency**: Task A (provider exists), Task B (field exists).
**Touched modules**:
- `helios_v2/src/helios_v2/composition/runtime_assembly.py` — auto-provisioning block
  in `assemble_runtime` after profile resolution.

**Completion definition**:
- `assemble_runtime()` with no arguments produces `semantic_memory_enabled == True`.
- The `03` appraisal engine uses `GroundedDimensionEstimator`.
- A tick with the default `FirstVersionSensorySource` produces real novelty (computed
  from embedding distance, not the constant `0.6`).
- `assemble_runtime(default_signal_mode="legacy_constant")` produces
  `semantic_memory_enabled == False` and all `FirstVersion*` paths.
- Integration test: `pytest helios_v2/tests/test_runtime_composition.py -x -k "semantic_default"`.

**Validation step**:
```
pytest helios_v2/tests/test_runtime_composition.py -x -k "semantic_default or legacy_constant"
```

### Task D: Migrate existing tests

**Scope**: Update tests that depend on constant shim values to use the legacy escape hatch
or update assertions for real-signal behavior.
**Dependency**: Task C (auto-provisioning active).
**Touched modules**:
- `helios_v2/tests/test_runtime_composition.py` — add `default_signal_mode="legacy_constant"`
  to tests that assert on constant values; leave semantic-assembly tests unchanged.
- `helios_v2/tests/test_runtime_stage_chain.py` — same pattern.
- Any other test file that calls `assemble_runtime()` without explicit store/embedding
  and asserts on constant shim outputs.

**Completion definition**:
- Full suite passes: `pytest helios_v2/tests/ -x`.
- No test silently relies on the old default-assembly constant values.
- Tests that need legacy behavior explicitly declare `default_signal_mode="legacy_constant"`.

**Validation step**:
```
pytest helios_v2/tests/ -x
```

### Task E: Add default-assembly integration test

**Scope**: A new test that validates the default assembly runs the full de-shimmed chain.
**Dependency**: Task C.
**Touched modules**:
- `helios_v2/tests/test_runtime_composition.py` — new test class.

**Completion definition**:
- Test creates `assemble_runtime()` with no arguments.
- Asserts `semantic_memory_enabled == True`.
- Runs two ticks with different stimuli (via `SequenceExternalSignalSource` or direct
  sensory injection).
- Asserts `03` novelty differs between ticks (real signal, not constant).
- Asserts `04` neuromodulator levels differ between ticks.

**Validation step**:
```
pytest helios_v2/tests/test_runtime_composition.py -x -k "default_semantic_assembly"
```

### Task F: Update documentation

**Scope**: Sync all living documents with the new default.
**Dependency**: Task D (full suite green).
**Touched modules**:
- `helios_v2/docs/requirements/index.md` — add R69 row.
- `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` — update sync line.
- `helios_v2/docs/PROGRESS_FLOW.en.md` — update sync line.
- `helios_v2/docs/OWNER_GUIDE.zh-CN.md` — update composition root section.
- `helios_v2/docs/OWNER_GUIDE.md` — update composition root section.

**Completion definition**:
- `index.md` contains R69 row with `baseline_implementation` maturity.
- Both progress flow maps reference R69 in their sync line.
- Both owner guides describe the new default in the composition root section.

**Validation step**: visual inspection; no automated check.

## 2. Dependencies

```
Task A (embedding provider)  ─┐
                               ├─> Task C (auto-provisioning) ─> Task D (test migration)
Task B (profile field)       ─┘                                     │
                                                                     ├─> Task F (docs)
                                               Task E (integration) ─┘
```

Tasks A and B are independent and may be done in either order or in parallel.
Task C depends on both A and B.
Tasks D and E depend on C and may be done in parallel.
Task F depends on D (full suite green) and E.

## 3. Files and Modules

| File | Change type | Description |
|------|-------------|-------------|
| `helios_v2/src/helios_v2/embedding/engine.py` | Add class | `DeterministicHashEmbeddingProvider` |
| `helios_v2/src/helios_v2/embedding/__init__.py` | Add export | Re-export new provider |
| `helios_v2/src/helios_v2/composition/runtime_assembly.py` | Modify | `RuntimeProfile` field + auto-provisioning |
| `helios_v2/tests/test_embedding_engine.py` | Add tests | Deterministic hash provider tests |
| `helios_v2/tests/test_runtime_composition.py` | Modify + add | Migrate legacy tests + add semantic default tests |
| `helios_v2/tests/test_runtime_stage_chain.py` | Modify | Migrate tests that assert on constant values |
| `helios_v2/docs/requirements/index.md` | Add row | R69 entry |
| `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` | Update sync line | R69 reference |
| `helios_v2/docs/PROGRESS_FLOW.en.md` | Update sync line | R69 reference |
| `helios_v2/docs/OWNER_GUIDE.zh-CN.md` | Update section | Composition root description |
| `helios_v2/docs/OWNER_GUIDE.md` | Update section | Composition root description |

## 4. Implementation Order

1. Task A: `DeterministicHashEmbeddingProvider` (no dependencies, no breakage).
2. Task B: `RuntimeProfile.default_signal_mode` (no dependencies, no breakage with
   `"semantic"` as default since auto-provisioning is not yet active).
3. Task C: Auto-provisioning logic (depends on A + B; this is the breaking change).
4. Task D: Test migration (depends on C; restores full suite green).
5. Task E: Integration test (depends on C; validates new default behavior).
6. Task F: Documentation (depends on D + E).

## 5. Validation Plan

After each task:

| Task | Validation command |
|------|-------------------|
| A | `pytest helios_v2/tests/test_embedding_engine.py -x` |
| B | `pytest helios_v2/tests/test_runtime_composition.py -x -k "profile"` |
| C | `pytest helios_v2/tests/test_runtime_composition.py -x -k "semantic_default"` |
| D | `pytest helios_v2/tests/ -x` |
| E | `pytest helios_v2/tests/test_runtime_composition.py -x -k "default_semantic"` |
| F | Visual inspection of updated documents |

Final validation: `pytest helios_v2/tests/ -x` (full suite green).

## 6. Completion Criteria

1. `DeterministicHashEmbeddingProvider` is shipped and tested in `helios_v2.embedding`.
2. `RuntimeProfile.default_signal_mode` is validated and tested.
3. `assemble_runtime()` with no arguments produces a semantic-memory-enabled runtime
   with real signal processing through the `03`-`10` chain.
4. `assemble_runtime(default_signal_mode="legacy_constant")` reproduces the pre-R69
   default byte-for-byte.
5. All existing tests pass after migration.
6. A new integration test validates the default assembly's real-signal behavior.
7. All living documents are updated to reference R69.
8. `requirements/index.md` contains the R69 row with correct maturity.
