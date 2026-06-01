# Requirement 14 - Identity governance and self revision integration task plan

## 1. Task Breakdown

1. Completed: defined the identity-governance API and ops contracts.
2. Completed: defined the explicit governance-request contract that carries normalized self-revision proposals, identity-state snapshot, and bounded governance-trace state into `14` without owner reach-through.
3. Completed: encoded the confirmed first-version boundaries that `14` owns proposal validation, pressure evaluation, revision acceptance or rejection, identity mutation, and formal governance-result publication.
4. Completed: encoded the confirmed owner separation that proactive governance pressure belongs inside `14` while personality synchronization remains downstream collaboration.
5. Completed: encoded the confirmed boundary that rejected and invalid paths must still produce formal governance results.
6. Completed: implemented the public contracts for governance request, revision-status taxonomy, pressure-state, rejection taxonomy, revision decision, applied identity state, API, and ops contracts.
7. Completed: implemented the owner skeleton for input validation, governance-evaluation op construction, private governance-path invocation, explicit accepted revision publication, explicit rejected governance-result publication, explicit applied-identity-state publication, and no-fallback capability checks.
8. Completed: implemented the runtime-owned governance-request provider contract and `14` runtime stage adapter.
9. Completed: exported the public identity-governance contract surface.
10. Completed: added focused contract, owner-skeleton, and runtime-stage tests for immutability, explicit rejected-result publication, explicit backpressure publication, applied identity-state publication, no-fallback behavior, and governance-boundary preservation.

## 2. Dependencies

1. `11-internal-thought-loop-owner` for upstream self-revision proposal ownership.
2. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
3. `13-planner-executor-feedback-bridge` provides a parallel publication pattern for formal rejected or accepted bridge results, but `14` must define governance-native contracts and outcomes now rather than reusing transport semantics.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/identity_governance/contracts.py`
2. `helios_v2/src/helios_v2/identity_governance/engine.py`
3. `helios_v2/src/helios_v2/identity_governance/__init__.py`
4. `helios_v2/tests/test_identity_governance_contracts.py`
5. `helios_v2/tests/test_identity_governance_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/__init__.py`
3. `helios_v2/src/helios_v2/__init__.py`
4. `helios_v2/tests/test_runtime_stage_chain.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/14-identity-governance-self-revision-integration/requirement.md`
2. `helios_v2/docs/requirements/14-identity-governance-self-revision-integration/design.md`
3. `helios_v2/docs/requirements/14-identity-governance-self-revision-integration/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for unified governance ownership, internal pressure ownership, downstream personality synchronization, and formal rejected-result publication.
3. Public identity-governance contracts.
4. Runtime-owned governance-request provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain validation.
10. Full `helios_v2/tests` regression validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract, owner, and stage validation: `pytest helios_v2/tests/test_identity_governance_contracts.py helios_v2/tests/test_identity_governance_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`
4. Full regression validation: `pytest helios_v2/tests -q`

## 6. Completion Criteria

1. A documented API from normalized self-revision proposals into formal governance results and accepted applied identity-state publication exists.
2. Governance evaluation, revision decision, pressure-state, and applied-identity-state ops are defined and documented.
3. The contract surface publishes formal governance results for accepted, monitored-accepted, rejected, and invalid-proposal paths.
4. The contract surface publishes applied identity state when a revision is accepted.
5. Proactive governance pressure remains explicitly inside the governance owner rather than as passive observability only.
6. Personality synchronization remains explicitly downstream collaboration rather than part of the governance owner itself.
7. Audit persistence remains explicitly downstream collaboration rather than part of the governance owner itself.
8. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
9. Focused contract, owner-skeleton, and runtime-stage tests pass.
10. Full `helios_v2/tests` regression passes.

## 7. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_identity_governance_contracts.py helios_v2/tests/test_identity_governance_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `159 passed`

Delivered files:

1. `helios_v2/src/helios_v2/identity_governance/contracts.py`
2. `helios_v2/src/helios_v2/identity_governance/engine.py`
3. `helios_v2/src/helios_v2/identity_governance/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_identity_governance_contracts.py`
8. `helios_v2/tests/test_identity_governance_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`