# Requirement 26 - LLM-backed internal thought task plan

## 1. Title

Requirement 26 - LLM-backed internal thought

## 2. Task Breakdown

1. Extract the deterministic judgment logic from `FirstVersionInternalThoughtPath` into an owner-private `_derive_thought_judgment` helper plus shared result/trace assembly helpers in `internal_thought/engine.py`, preserving current behavior.
2. Refactor `FirstVersionInternalThoughtPath` to use the shared helpers; confirm existing tests stay green with no test changes.
3. Implement `LlmBackedInternalThoughtPath` in `internal_thought/engine.py`: build neutral `LlmRequest` messages from the request, retrieval window, continuation state, and prompt-contract summary; call the `25` gateway; turn completion text into `ThoughtContent` (`llm_used=True`); run owner judgment; assemble result and trace; handle empty completion as explicit `insufficient_generation`; let `LlmError` propagate.
4. Export `LlmBackedInternalThoughtPath` from `internal_thought/__init__.py`.
5. Add an `llm` section to `CompositionConfig` (registry profiles + `thought_profile_name`) and supply a default profile bound to the `.env` LLM vars in `default_composition_config()`.
6. Wire the LLM-backed path as the default thought path in `assemble_runtime`, construct the gateway and registry, and register the bound thought profile as a critical dependency through the `25` readiness provider.
7. Provide an explicit deterministic-path / fake-gateway assembly seam so composition tests stay network-free.
8. Extend `tests/test_internal_thought_engine.py` with LLM-backed path cases (fake gateway success, raising gateway, empty completion, judgment-in-owner reproducibility).
9. Extend `tests/test_runtime_composition.py` with default LLM-backed assembly (injected fake gateway), the LLM critical-dependency fail-fast/pass cases, and the deterministic-path assembly seam.
10. Update `docs/requirements/index.md`, `docs/ARCHITECTURE_BOUNDARIES.md`, and `docs/BRAIN_ARCHITECTURE_COMPARISON.md` to record the first real cognition consumer and the narrowed shim gap.

## 3. Dependencies

1. `25-llm-inference-gateway` provides the `LlmGateway`, neutral contracts, profile registry, and static-readiness dependency plumbing.
2. `11-internal-thought-loop-owner` provides the `InternalThoughtPath` protocol and the result/trace contracts the new path implements.
3. `22-runtime-composition-root-and-runnable-runtime` provides the assembly surface for binding the path and the dependency.
4. No real network or api key is required for any test; a deterministic fake gateway covers all cases.

## 4. Files and Modules

1. `helios_v2/src/helios_v2/internal_thought/engine.py`
2. `helios_v2/src/helios_v2/internal_thought/__init__.py`
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py`
4. `helios_v2/src/helios_v2/composition/dependencies.py`
5. `helios_v2/tests/test_internal_thought_engine.py`
6. `helios_v2/tests/test_runtime_composition.py`
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

## 5. Implementation Order

1. Refactor judgment into the shared owner-private helper; keep the deterministic path green.
2. Implement and unit-test `LlmBackedInternalThoughtPath` with a deterministic fake gateway.
3. Add the composition `llm` config section, gateway/registry construction, and the default LLM-backed wiring.
4. Register the LLM critical dependency and add the fail-fast/pass composition tests plus the network-free assembly seam.
5. Update boundary, grounding, and index docs.

## 6. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `$env:PYTHONPATH = "d:/Software/project/helios/helios_v2/src"`
3. `pytest helios_v2/tests/test_internal_thought_engine.py -q`
4. `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_runtime_dependencies.py -q`
5. `pytest helios_v2/tests/test_no_adhoc_logging_guard.py -q`
6. `pytest helios_v2/tests -q`

## 7. Completion Criteria

1. `LlmBackedInternalThoughtPath` implements the existing `InternalThoughtPath` protocol and produces `completed` results with `llm_used=True`, `fallback_used=False`, an LLM-distinct `source_path`, and completion-derived content, with owner-held reproducible judgment.
2. Gateway failure raises a hard stop with no fabricated content; empty completion yields an explicit `insufficient_generation` status with no `ThoughtContent`.
3. The default assembled runtime is LLM-backed and registers the bound thought profile as a critical dependency that fails startup fast when unready; an explicit deterministic/fake-gateway assembly keeps the suite network-free.
4. Existing internal-thought validation invariants and deterministic-path tests remain green.
5. No `11` result contract changed; the logging-guard test passes and `pytest helios_v2/tests -q` is green and network-free.

## 8. Completion Snapshot

Status on 2026-06-03: implemented and validated as `baseline_implementation`.

Delivered files:

1. `helios_v2/src/helios_v2/internal_thought/engine.py` (`_derive_thought_judgment` shared owner-private judgment helper, `_assemble_completed_result`/`_assemble_trace`/`_assemble_insufficient_result` helpers, refactored `FirstVersionInternalThoughtPath`, new `LlmBackedInternalThoughtPath`)
2. `helios_v2/src/helios_v2/internal_thought/__init__.py` (`LlmBackedInternalThoughtPath` export)
3. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (`LlmCompositionConfig`, default LLM profile bound to `.env` vars, gateway construction, default LLM-backed thought wiring, injectable `gateway` param, LLM critical-dependency registration)
4. `helios_v2/tests/test_internal_thought_engine.py` (LLM-backed path cases), `helios_v2/tests/test_runtime_composition.py` (default LLM-backed assembly, fail-fast/pass dependency cases, hard-stop on inference failure, network-free fake-gateway seam)
5. `helios_v2/docs/requirements/index.md`, `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`, `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`

Validated outcomes:

1. `pytest helios_v2/tests/test_internal_thought_engine.py helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_runtime_dependencies.py -q` -> 33 passed
2. `pytest helios_v2/tests -q` -> 306 passed, network-free

Implementation notes:

1. Judgment (sufficiency, continuation, recall intent, memory handoff, action/self-revision proposal) is extracted into the owner-private `_derive_thought_judgment` helper shared by both paths, so judgment provably stays in the `11` owner and is reproducible for fixed content. The model supplies content only.
2. The default assembled runtime is LLM-backed and carries `llm_profiles_ready` as a critical dependency; a real `startup()` requires a statically-ready bound profile. Tests inject a deterministic fake-provider gateway via the new `assemble_runtime(gateway=...)` seam to stay network-free.
3. Gateway failure (`LlmError`) propagates as a hard stop with no deterministic fallback; an empty completion yields an explicit `insufficient_generation` result with no `ThoughtContent`. No `11` result contract changed.
