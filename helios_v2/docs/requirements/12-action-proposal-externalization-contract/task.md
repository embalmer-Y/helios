# Requirement 12 - Action proposal and externalization contract task plan

## 1. Task Breakdown

1. Define the action-externalization API and ops contracts.
2. Define the explicit externalization-request contract that carries thought-cycle provenance, optional proposal carrier, and bounded normalization context into `12` without owner reach-through.
3. Encode the confirmed first-version boundaries: `12` owns proposal normalization, formal externalization-contract publication, bridge-level rejection publication, and equivalent-evidence publication.
4. Encode the confirmed owner separation that planner acceptance and executor dispatch remain outside `12`.
5. Encode the confirmed boundary that user-visible external behaviors must carry final outbound text in the normalized contract.
6. Implement the public contracts for externalization request, normalized proposal, bridge outcome status, rejection taxonomy, equivalent evidence, API, and ops contracts.
7. Implement the owner skeleton for input validation, externalization-request op construction, private bridge-path invocation, explicit successful contract publication, explicit bridge rejection publication, and no-fallback capability checks.
8. Implement the runtime-owned externalization-request provider contract and `12` runtime stage adapter.
9. Export the public action-externalization contract surface.
10. Add focused contract, owner-skeleton, and runtime-stage tests for immutability, explicit bridge rejection publication, equivalent-evidence publication, outbound-text requirements, no-fallback behavior, and `11 -> 12` stage wiring.

## 2. Dependencies

1. `11-internal-thought-loop-owner` for upstream thought-cycle results and optional proposal-carrier semantics.
2. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
3. Later planner and executor slices may consume normalized externalization contracts, but `12` must define those outputs now without requiring downstream implementation first.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/action_externalization/contracts.py`
2. `helios_v2/src/helios_v2/action_externalization/engine.py`
3. `helios_v2/src/helios_v2/action_externalization/__init__.py`
4. `helios_v2/tests/test_action_externalization_contracts.py`
5. `helios_v2/tests/test_action_externalization_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/dependencies.py`
3. `helios_v2/tests/test_runtime_stage_chain.py`
4. `helios_v2/tests/test_runtime_dependencies.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/12-action-proposal-externalization-contract/requirement.md`
2. `helios_v2/docs/requirements/12-action-proposal-externalization-contract/design.md`
3. `helios_v2/docs/requirements/12-action-proposal-externalization-contract/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for proposal normalization ownership, equivalent-evidence preservation, and outbound-text requirements.
3. Public action-externalization contracts.
4. Runtime-owned externalization-request provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain and dependency validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract and owner validation: `pytest helios_v2/tests/test_action_externalization_contracts.py helios_v2/tests/test_action_externalization_engine.py -q`
4. Stage-chain validation: `pytest helios_v2/tests/test_runtime_stage_chain.py -q -k "internal_thought or externalization"`
5. Dependency validation: `pytest helios_v2/tests/test_runtime_dependencies.py -q`

## 6. Completion Criteria

1. A documented API from `ThoughtCycleResult` into one formal externalization result exists.
2. Externalization request, successful publication, and bridge rejection ops are defined and documented.
3. The contract surface publishes explicit bridge outcomes for success, rejection, and equivalent-evidence-only paths.
4. The contract surface preserves origin thought id, owner path, behavior name, preferred op, channel constraints, outbound intensity, and reason trace.
5. Equivalent bridge evidence remains explicit and distinct from normalized explicit proposals.
6. User-visible external behaviors require final outbound text inside the normalized contract.
7. Planner acceptance and executor dispatch remain explicitly outside `12`.
8. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
9. Focused contract, owner-skeleton, runtime-stage, and dependency tests pass.