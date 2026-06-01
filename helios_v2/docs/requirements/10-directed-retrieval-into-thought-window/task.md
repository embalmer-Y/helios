# Requirement 10 - Directed retrieval into thought window task plan

## 1. Task Breakdown

1. Define the directed-retrieval API and ops contracts.
2. Define the explicit retrieval-request contract that carries gate result, continuation state, compact stimuli, recall intent, selected-memory refs, and tier targets into `10` without owner reach-through.
3. Encode the confirmed first-version boundaries: `10` owns retrieval-query planning, tiered selection or reranking, and final bounded thought-window bundle assembly.
4. Encode the confirmed owner separation that public memory-owner interfaces supply candidates, but selection policy remains with `10`.
5. Encode the confirmed boundary that short-term context is part of the bundle but remains tiny and bounded.
6. Implement the public contracts for retrieval request, query plan, bounded thought-window hits, thought-window bundle, selection trace, SEC trace, config, API, and ops contracts.
7. Implement the owner skeleton for input validation, retrieval-planning op construction, private retrieval-path invocation, explicit query-plan publication, explicit bounded bundle publication, and no-fallback capability checks.
8. Implement the runtime-owned retrieval-request provider contract and `10` runtime stage adapter.
9. Export the public directed-retrieval contract surface.
10. Add focused contract, owner-skeleton, and runtime-stage tests for immutability, bounded bundle shape, explicit tier selection trace, structured SEC trace, no-fallback behavior, and `09 -> 10` stage wiring.

## 2. Dependencies

1. `09-thought-gating-and-continuation-pressure` for upstream `ThoughtGateResult` and `ContinuationPressureState`.
2. `06-memory-affect-and-replay` for the public memory-owner boundary that later retrieval calls will consume rather than bypass.
3. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
4. A future internal-thought slice may provide prior-thought retrieval-request handoff, but `10` must define that public contract now without requiring `11` implementation first.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/directed_retrieval/contracts.py`
2. `helios_v2/src/helios_v2/directed_retrieval/engine.py`
3. `helios_v2/src/helios_v2/directed_retrieval/__init__.py`
4. `helios_v2/tests/test_directed_retrieval_contracts.py`
5. `helios_v2/tests/test_directed_retrieval_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/dependencies.py`
3. `helios_v2/tests/test_runtime_stage_chain.py`
4. `helios_v2/tests/test_runtime_dependencies.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/10-directed-retrieval-into-thought-window/requirement.md`
2. `helios_v2/docs/requirements/10-directed-retrieval-into-thought-window/design.md`
3. `helios_v2/docs/requirements/10-directed-retrieval-into-thought-window/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for explicit retrieval request, tiered selection ownership, and bounded short-term context.
3. Public directed-retrieval contracts.
4. Runtime-owned retrieval-request provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain and dependency validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract and owner validation: `pytest helios_v2/tests/test_directed_retrieval_contracts.py helios_v2/tests/test_directed_retrieval_engine.py -q`
4. Stage-chain validation: `pytest helios_v2/tests/test_runtime_stage_chain.py -q -k "thought_gate or retrieval"`
5. Dependency validation: `pytest helios_v2/tests/test_runtime_dependencies.py -q`

## 6. Completion Criteria

1. A documented API from `ThoughtGateResult + ContinuationPressureState + RetrievalRequest` into `RetrievalQueryPlan` and `ThoughtWindowBundle` exists.
2. Retrieval-planning and thought-window-bundle publication ops are defined and documented.
3. The contract surface publishes one formal query plan and one bounded thought-window bundle every valid fired-gate cycle.
4. The contract surface publishes structured selection trace and candidate-level SEC trace.
5. Tiered selection or reranking ownership is explicit in `10` rather than hidden inside the memory owner.
6. Optional prior-thought `recall_intent` and selected-memory refs enter only through the explicit retrieval-request handoff contract.
7. Short-term context remains part of the thought-window bundle but is explicitly tiny and bounded.
8. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
9. Focused contract, owner-skeleton, runtime-stage, and dependency tests pass.