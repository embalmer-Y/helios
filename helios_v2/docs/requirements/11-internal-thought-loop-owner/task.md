# Requirement 11 - Internal thought loop owner task plan

## 1. Task Breakdown

1. Define the internal-thought API and ops contracts.
2. Define the explicit internal-thought request contract that carries fired-path gate, retrieval, continuation, and prompt inputs into `11` without owner reach-through.
3. Encode the confirmed first-version boundaries: `11` owns fired-path thought execution, sufficiency judgment, continuation emission, memory handoff, and optional proposal emission.
4. Encode the confirmed owner separation that `11` may emit action or self-revision proposals, but downstream acceptance remains outside this slice.
5. Encode the confirmed boundary that direct thought persistence remains outside `11`.
6. Implement the public contracts for internal-thought request, thought content, execution-status taxonomy, thought-cycle result, memory handoff, internal-thought trace, API, and ops contracts.
7. Implement the owner skeleton for input validation, thought-execution op construction, private thought-path invocation, explicit successful-result publication, explicit fired-path non-success publication, and no-fallback capability checks.
8. Implement the runtime-owned internal-thought request provider contract and `11` runtime stage adapter.
9. Export the public internal-thought contract surface.
10. Add focused contract, owner-skeleton, and runtime-stage tests for immutability, explicit execution-status publication, memory-handoff preservation, optional proposal emission, no-fallback behavior, and `10 -> 11` stage wiring.

## 2. Dependencies

1. `10-directed-retrieval-into-thought-window` for upstream thought-window bundle ownership.
2. `09-thought-gating-and-continuation-pressure` for upstream fired-path gate result and continuation state.
3. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
4. Later externalization, feedback, and governance slices may consume optional proposals and memory handoff, but `11` must define those output contracts now without requiring downstream implementation first.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/internal_thought/contracts.py`
2. `helios_v2/src/helios_v2/internal_thought/engine.py`
3. `helios_v2/src/helios_v2/internal_thought/__init__.py`
4. `helios_v2/tests/test_internal_thought_contracts.py`
5. `helios_v2/tests/test_internal_thought_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/dependencies.py`
3. `helios_v2/tests/test_runtime_stage_chain.py`
4. `helios_v2/tests/test_runtime_dependencies.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/11-internal-thought-loop-owner/requirement.md`
2. `helios_v2/docs/requirements/11-internal-thought-loop-owner/design.md`
3. `helios_v2/docs/requirements/11-internal-thought-loop-owner/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for fired-path thought execution, optional proposal emission, and persistence-outside-11.
3. Public internal-thought contracts.
4. Runtime-owned internal-thought request provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain and dependency validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract and owner validation: `pytest helios_v2/tests/test_internal_thought_contracts.py helios_v2/tests/test_internal_thought_engine.py -q`
4. Stage-chain validation: `pytest helios_v2/tests/test_runtime_stage_chain.py -q -k "retrieval or internal_thought"`
5. Dependency validation: `pytest helios_v2/tests/test_runtime_dependencies.py -q`

## 6. Completion Criteria

1. A documented API from fired-path thought inputs into `ThoughtCycleResult` exists.
2. Thought-execution and thought-cycle publication ops are defined and documented.
3. The contract surface publishes one formal thought-cycle result every valid fired-thought cycle.
4. The contract surface publishes explicit fired-path execution status, sufficiency, continuation request, continuation reason, recall intent, and continuation-pressure delta.
5. Optional action and self-revision proposals are explicit output carriers of `11`, but downstream acceptance remains outside the slice.
6. Thought persistence remains explicitly outside `11` and is not encoded as a direct owner side effect.
7. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
8. Focused contract, owner-skeleton, runtime-stage, and dependency tests pass.