# Requirement 13 - Planner executor feedback bridge

## 1. Background and Problem

After `12` publishes a formal thought-origin externalization contract, Helios v2 still lacks a dedicated owner that turns that contract into one formal planner decision and one formal execution outcome. Without this owner, proposal validation remains mixed across planner code, executor command wiring, `helios_main.py`, and feedback recorder calls, while rejected or pre-execution failures may survive only as logs or downstream persistence events.

The current legacy implementation proves that the planner-to-execution bridge is a real runtime concept rather than incidental orchestration. It already carries `PolicyEvaluation`, `ActionDecision`, executor readiness checks, `ExecutionFeedback`, `policy_rejection`, and `execution_consistency_failure`, but these semantics remain distributed across `planning.py`, `limb.py`, `feedback_recorder.py`, and main-loop wiring. Helios v2 must separate the bridge into its own owner before identity-governance integration is defined.

This slice corresponds to the transition from a normalized externalization contract into one formal bridge result covering planner acceptance, decision publication, execution-outcome normalization, and explicit rejection semantics, not to channel transport, memory persistence, or identity-governance acceptance.

## 2. Goal

Create a planner-executor-feedback bridge owner that consumes formal externalization contracts, evaluates them against behavior and channel constraints, publishes immutable bridge decisions and bridge outcomes for both accepted and rejected paths, normalizes execution outcomes into one explicit feedback contract, and collaborates with downstream audit persistence without fallback behavior, private reach-through, or ownership collapse into channel transport or feedback storage.

## 3. Functional Requirements

### 3.1 Bridge owner boundary
1. The planner-executor-feedback bridge must be the sole owner of proposal-to-decision evaluation, formal bridge-result publication, and execution-outcome normalization in this slice.
2. The owner must remain separate from thought generation, externalization-contract normalization, channel transport, memory persistence, and identity-governance acceptance.
3. The owner must not reinterpret itself as the owner of raw channel I/O or feedback-journal persistence.

### 3.2 Upstream input boundary
1. The bridge owner must accept the normalized externalization result from `12` as a required upstream input contract for thought-origin action paths.
2. The bridge owner may accept other normalized action-proposal sources later, but only through documented public contracts.
3. The bridge owner must consume behavior specs, channel descriptors, and channel statuses only through documented public contracts.
4. The owner must not require private reach-through into channel implementations, feedback storage internals, or governance internals in this slice.
5. The owner must not require direct memory-store mutation in this slice.

### 3.3 Planner and decision ownership
1. The first public output of this slice must be one formal bridge result rather than planner logs alone.
2. The bridge owner must evaluate whether a normalized proposal is acceptable under policy, behavior status, review status, channel capabilities, target binding, and op-input constraints.
3. If the proposal is acceptable, the bridge owner must publish one formal action decision containing selected channel, selected op, normalized intensity, validated params, execution priority, and policy trace.
4. If the proposal is rejected before execution, the bridge owner must still publish one formal bridge result with explicit rejection reason and rejection-phase metadata.
5. Rejected bridge results must not be represented only as downstream recorder events or logs.

### 3.4 Execution readiness and consistency failure semantics
1. The bridge owner must explicitly distinguish planner rejection from execution-consistency failure.
2. Missing channel binding, missing output op, missing required op inputs, or equivalent pre-execution invalid executor state must be modeled as explicit bridge outcomes.
3. The owner must not silently reinterpret execution-consistency failures as policy rejection.
4. The owner must not silently reinterpret execution-consistency failures as transport failures.
5. Execution-consistency failure results must preserve enough provenance to diagnose where the proposal path broke before transport execution.

### 3.5 Execution feedback normalization
1. If execution occurs, the bridge owner must normalize the outcome into one formal execution-feedback contract.
2. The execution-feedback contract must preserve at least proposal id, decision id, behavior name, success flag, selected channel, selected op, normalized intensity, result details, and state effects.
3. The owner must preserve whether the outcome corresponds to execution success, execution failure, policy rejection, or pre-execution consistency failure.
4. The owner must not let execution outcome semantics remain implicit in ad hoc callback payloads.

### 3.6 Separation from transport and persistence
1. The bridge owner may enqueue or hand off decisions to an executor abstraction, but it must not own raw channel transport in this slice.
2. The bridge owner may collaborate with a downstream audit or persistence recorder, but it must not own feedback-journal persistence in this slice.
3. The bridge owner must publish normalized bridge outcomes before or alongside downstream recorder collaboration rather than relying on recorder state as the primary contract.
4. The bridge owner must not directly persist memory or identity side effects in this slice.

### 3.7 Learned or runtime-provided bridge semantics
1. The owner must not hardcode permanent planner thresholds, routing rules, or rejection heuristics into the architecture contract.
2. Policy evaluation policy, channel selection policy, execution-readiness policy, and bridge feedback-normalization policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty-bridge defaults, and explicit owner-controlled bootstrap metadata.
4. If the first-version implementation uses deterministic channel ranking or deterministic rejection taxonomies, that path must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic bridge semantics must remain learning-driven rather than frozen into architecture defaults.

### 3.8 No fallback behavior
1. The bridge owner must not synthesize a successful decision or feedback result when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic execution path when the configured bridge capability is unavailable.
3. The owner must fail explicitly when required proposal, behavior, channel, or executor-readiness invariants are missing.
4. The owner must not silently let transport or recorder layers repair malformed decisions.
5. The owner must not silently drop rejected or failed bridge outcomes just because downstream recorder collaboration still occurs.

## 4. Non-Functional Requirements

1. Bridge result, action decision, and execution-feedback contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured bridge policy.
3. The owner boundary must remain separate from transport implementations, feedback persistence, and governance acceptance owners.
4. Published state must preserve enough provenance and rejection-phase detail to support later evaluation of where a thought-origin proposal was accepted, rejected, or failed.
5. Policy rejection, execution-consistency failure, and post-execution failure must remain explicitly distinguishable.

## 5. Code Behavior Constraints
1. Bridge code must not import raw channel implementations, memory persistence owners, or identity-governance owners directly.
2. Bridge code must expose only documented APIs and ops contracts across module boundaries.
3. Bridge code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Bridge code must not blur owner boundaries by taking ownership of channel transport or feedback-journal persistence.
5. Rejected or failed bridge results must not disappear into logs alone.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/planner_bridge/contracts.py`
2. `helios_v2/src/helios_v2/planner_bridge/engine.py`
3. `helios_v2/src/helios_v2/planner_bridge/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_planner_bridge_contracts.py`
6. `helios_v2/tests/test_planner_bridge_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The requirement package defines a documented API from normalized externalization contracts into one formal bridge result and, when accepted, one formal action decision.
2. The package defines documented ops contracts for bridge evaluation request, decision publication, rejection publication, and execution-feedback publication.
3. The contract surface publishes formal bridge results for accepted, policy-rejected, and execution-consistency-failure paths.
4. The contract surface publishes normalized execution feedback when execution occurs.
5. The package records that feedback persistence remains downstream collaboration rather than part of the bridge owner itself.
6. The package records that rejected cases must still produce formal bridge results rather than logs or recorder events alone.
7. The package does not claim channel transport, memory persistence, or governance acceptance ownership.
8. No test or implementation path demonstrates silent repair of malformed decisions by downstream layers or silent disappearance of rejected bridge outcomes.

## 8. Implementation Status

Status on 2026-06-01: implemented and validated as `baseline_implementation`.

Implemented scope:

1. `helios_v2/src/helios_v2/planner_bridge/contracts.py` defines immutable bridge contracts, taxonomies, ops contracts, and the public API surface.
2. `helios_v2/src/helios_v2/planner_bridge/engine.py` defines fail-fast validation, owner-private `FirstVersionPlannerBridgePath`, and formal bridge-result plus execution-feedback publication behavior.
3. `helios_v2/src/helios_v2/runtime/stages.py` wires `PlannerBridgeRuntimeStage` immediately after `12` through a runtime-owned `PlannerBridgeRequestProvider`.
4. `helios_v2/tests/test_planner_bridge_contracts.py`, `helios_v2/tests/test_planner_bridge_engine.py`, and `helios_v2/tests/test_runtime_stage_chain.py` cover contract immutability, accepted/rejected/consistency-failure paths, and `12 -> 13` runtime chaining.

Validated outcomes:

1. `pytest helios_v2/tests/test_planner_bridge_contracts.py helios_v2/tests/test_planner_bridge_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `151 passed`

Implementation note:

1. Focused validation caught one real adjacent-contract defect during implementation: `13` must consume `12` normalized proposals through `preferred_op`, not a nonexistent `requested_op`. The final validated implementation preserves the `12 -> 13` boundary accordingly.