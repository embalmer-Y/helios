# Requirement 13 - Planner executor feedback bridge task plan

## 1. Task Breakdown

1. Completed: defined the planner-bridge API and ops contracts.
2. Completed: defined the explicit bridge-request contract that carries externalization-result provenance, normalized proposal presence, and bounded bridge context into `13` without owner reach-through.
3. Completed: encoded the confirmed first-version boundaries that `13` owns planner evaluation, action decision publication, execution-consistency-failure publication, and normalized execution-feedback publication.
4. Completed: encoded the confirmed owner separation that feedback recorder remains a downstream collaborator rather than part of the bridge owner.
5. Completed: encoded the confirmed boundary that rejected and failed paths must still produce formal bridge results.
6. Completed: implemented the public contracts for bridge request, bridge-status taxonomy, rejection taxonomy, execution-consistency failure, bridge result, normalized execution feedback, API, and ops contracts.
7. Completed: implemented the owner skeleton for input validation, bridge-evaluation op construction, private bridge-path invocation, explicit accepted decision publication, explicit rejected bridge-result publication, explicit normalized execution-feedback publication, and no-fallback capability checks.
8. Completed: implemented the runtime-owned bridge-request provider contract and `13` runtime stage adapter.
9. Completed: exported the public planner-bridge contract surface.
10. Completed: added focused contract, owner-skeleton, and runtime-stage tests for immutability, explicit rejected-result publication, explicit consistency-failure publication, normalized execution-feedback publication, no-fallback behavior, and `12 -> 13` stage wiring.

## 2. Dependencies

1. `12-action-proposal-externalization-contract` for upstream normalized proposal ownership.
2. `01-runtime-kernel` for runtime-stage registration and immutable frame passing.
3. Existing behavior-spec, channel-descriptor, and channel-status owners provide bounded bridge inputs, but `13` must define the bridge result and decision contracts now without requiring later persistence slices first.

## 3. Files and Modules

### 3.1 New modules
1. `helios_v2/src/helios_v2/planner_bridge/contracts.py`
2. `helios_v2/src/helios_v2/planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/planner_bridge/__init__.py`
4. `helios_v2/tests/test_planner_bridge_contracts.py`
5. `helios_v2/tests/test_planner_bridge_engine.py`

### 3.2 Existing modules to extend
1. `helios_v2/src/helios_v2/runtime/stages.py`
2. `helios_v2/src/helios_v2/runtime/__init__.py`
3. `helios_v2/src/helios_v2/__init__.py`
4. `helios_v2/tests/test_runtime_stage_chain.py`

### 3.3 Requirement package files
1. `helios_v2/docs/requirements/13-planner-executor-feedback-bridge/requirement.md`
2. `helios_v2/docs/requirements/13-planner-executor-feedback-bridge/design.md`
3. `helios_v2/docs/requirements/13-planner-executor-feedback-bridge/task.md`

## 4. Implementation Order

1. Requirement and design confirmation.
2. Confirmed boundary encoding for unified bridge ownership, downstream recorder collaboration, and formal rejected-result publication.
3. Public planner-bridge contracts.
4. Runtime-owned bridge-request provider contract.
5. Owner skeleton.
6. Runtime stage adapter and stage-result wiring.
7. Export surface.
8. Focused tests.
9. Adjacent runtime-chain validation.
10. Full `helios_v2/tests` regression validation.

## 5. Validation Plan

1. `Set-Location "d:/Software/project/helios"`
2. `Set-Item -Path Env:PYTHONPATH -Value "d:/Software/project/helios/helios_v2/src"`
3. Focused contract, owner, and stage validation: `pytest helios_v2/tests/test_planner_bridge_contracts.py helios_v2/tests/test_planner_bridge_engine.py helios_v2/tests/test_runtime_stage_chain.py -q`
4. Full regression validation: `pytest helios_v2/tests -q`

## 6. Completion Criteria

1. A documented API from normalized externalization results into formal bridge results and accepted action decisions exists.
2. Bridge evaluation, action decision, rejection, and execution-feedback ops are defined and documented.
3. The contract surface publishes formal bridge results for accepted, rejected, and execution-consistency-failure paths.
4. The contract surface publishes normalized execution feedback when execution occurs.
5. Feedback recorder remains explicitly downstream collaboration rather than the bridge owner itself.
6. Rejected and failed paths produce formal bridge results rather than logs or recorder events alone.
7. The owner skeleton enforces fail-fast malformed-input handling and no-fallback behavior.
8. Focused contract, owner-skeleton, and runtime-stage tests pass.
9. Full `helios_v2/tests` regression passes.

## 7. Completion Snapshot

Status on 2026-06-01: complete for the current `baseline_implementation` target.

Validated results:

1. `pytest helios_v2/tests/test_planner_bridge_contracts.py helios_v2/tests/test_planner_bridge_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `151 passed`

Delivered files:

1. `helios_v2/src/helios_v2/planner_bridge/contracts.py`
2. `helios_v2/src/helios_v2/planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/planner_bridge/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/__init__.py`
7. `helios_v2/tests/test_planner_bridge_contracts.py`
8. `helios_v2/tests/test_planner_bridge_engine.py`
9. `helios_v2/tests/test_runtime_stage_chain.py`