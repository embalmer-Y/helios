# Requirement 09 - Thought gating and continuation pressure task plan

## 1. Task Breakdown

1. Define the thought-gating API and ops contracts.
2. Define the explicit gate-input contract that carries `ConsciousState`, prior continuation state, normalized gate signals, and compact selected-stimulus summaries into `09` without owner reach-through.
3. Encode the confirmed first-version boundaries: `09` owns only `fire` versus `no_fire` decisions, compact gate observability, and continuation-pressure publication.
4. Encode the confirmed owner separation that thought-type cooldown remains outside `09` and belongs to the later internal-thought owner.
5. Keep the remaining unresolved gate-policy semantics as owner-private implementation details rather than public architecture truth.
6. Implement the public contracts for gate signals, compact stimulus summaries, gate result, continuation-pressure publication, config, API, and ops contracts.
7. Implement the owner skeleton for input validation, gate-evaluation op construction, private gate-path invocation, explicit `fire` versus `no_fire` publication, and continuation-pressure publication.
8. Implement the runtime-owned gate-signal provider contract and `09` runtime stage adapter.
9. Export the public thought-gating contract surface.
10. Add focused contract, owner-skeleton, and runtime-stage tests for immutability, bounded observability, explicit no-fire publication, structured continuation carry, no-fallback behavior, and `08 -> 09` stage wiring.

## 2. Dependencies

1. `08-reportable-conscious-content` for upstream `ConsciousState`.
2. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
3. Existing runtime state exports for normalized activation, workload, temporal, and drive signals, provided only through an explicit `09` gate-input contract rather than direct owner reach-through.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/thought_gating/contracts.py`
2. `helios_v2/src/helios_v2/thought_gating/engine.py`
3. `helios_v2/src/helios_v2/thought_gating/__init__.py`
4. `helios_v2/tests/test_thought_gating_contracts.py`
5. `helios_v2/tests/test_thought_gating_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/dependencies.py`
3. `helios_v2/tests/test_runtime_stage_chain.py`
4. `helios_v2/tests/test_runtime_dependencies.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/09-thought-gating-and-continuation-pressure/requirement.md`
2. `helios_v2/docs/requirements/09-thought-gating-and-continuation-pressure/design.md`
3. `helios_v2/docs/requirements/09-thought-gating-and-continuation-pressure/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for explicit gate inputs, compact stimulus summaries, and continuation-pressure ownership.
3. Public thought-gating contracts.
4. Runtime-owned gate-signal provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain and dependency validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract and owner validation: `pytest helios_v2/tests/test_thought_gating_contracts.py helios_v2/tests/test_thought_gating_engine.py -q`
4. Stage-chain validation: `pytest helios_v2/tests/test_runtime_stage_chain.py -q -k "conscious or thought_gate"`
5. Dependency validation: `pytest helios_v2/tests/test_runtime_dependencies.py -q`

## 6. Completion Criteria

1. A documented API from `ConsciousState + prior ContinuationPressureState + ThoughtGateSignalSnapshot` into `ThoughtGateResult` exists.
2. Gate-evaluation, gate-result publication, and continuation-pressure publication ops are defined and documented.
3. The contract surface publishes one formal gate result every valid cycle, including explicit `no_fire` cycles.
4. The contract surface publishes structured continuation pressure with origin thought, reason, expiry, and carry count.
5. Compact selected-stimulus summaries remain bounded and exclude full raw payload dictionaries.
6. The package explicitly records that thought-type cooldown remains outside `09` and belongs to the later internal-thought owner.
7. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
8. Focused contract, owner-skeleton, runtime-stage, and dependency tests pass.