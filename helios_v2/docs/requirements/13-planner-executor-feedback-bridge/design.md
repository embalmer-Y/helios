# Requirement 13 - Planner executor feedback bridge design

## 1. Design Overview

Planner-executor-feedback bridge is the sole owner-controlled transition between `12` action externalization contracts and later persistence or governance consumers of action outcomes. This slice consumes normalized proposals, evaluates them under bridge policy, publishes one formal bridge result for accepted and rejected paths, normalizes execution outcomes into one explicit feedback contract, and collaborates with downstream audit persistence without taking transport or recorder ownership.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, explicit bridge-result taxonomy, action-decision contract, execution-consistency-failure contract, execution-feedback contract, and owner-controlled bridge path before identity-governance integration is implemented.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect and replay, workspace competition, reportable consciousness, thought gating, directed retrieval, internal thought, and action-externalization owners, but it still lacks a formal owner that closes the loop from normalized proposal into decision and execution outcome.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `PolicyEvaluation` captures accepted state, allowed channels, violations, and trace.
2. `ActionDecision` captures selected channel, selected op, validated params, and rejection reason.
3. `ExecutionFeedback` captures post-execution success or failure.
4. `policy_rejection` and `execution_consistency_failure` already exist as structured journal events, but not as one formal bridge-owner contract.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for proposal-to-decision evaluation and bridge-result publication,
2. a typed, documented, fail-fast owner for normalized execution-outcome publication that remains separate from transport and persistence.

## 3. Target Architecture

The initial planner-bridge slice contains eleven runtime concepts:

1. `PlannerBridgeRequest`: immutable explicit bridge input contract for one cycle.
2. `BridgeStatus`: explicit planner-bridge outcome taxonomy.
3. `BridgeRejectionReason`: explicit bridge rejection taxonomy.
4. `ExecutionConsistencyFailure`: immutable pre-execution failure contract.
5. `PlannerBridgeResult`: immutable published bridge result for one cycle.
6. `ActionDecision`: immutable decision contract for accepted proposals.
7. `NormalizedExecutionFeedback`: immutable execution-feedback contract.
8. `EvaluatePlannerBridgeOp`: runtime-visible request op for one bridge evaluation cycle.
9. `PublishActionDecisionOp`: runtime-visible publication op for one accepted decision.
10. `PublishPlannerBridgeRejectionOp`: runtime-visible publication op for one rejected or failed bridge outcome.
11. `PlannerBridgeAPI`: public owner-facing API for bridge evaluation and outcome publication.

The initial owner also contains one private owner-controlled collaborator surface:

1. `PlannerBridgePath`: private owner interface responsible for turning a normalized proposal into one bridge result and optional execution feedback.

Implementation boundary confirmation:

1. Planner bridge owner owns only proposal-to-decision evaluation, bridge-result publication, and execution-outcome normalization.
2. It does not own raw channel transport, feedback-journal persistence, memory persistence, or governance acceptance.
3. It may expose a replaceable internal bridge path, but that path remains private to the owner until promoted by a later requirement slice.
4. `ThoughtExternalizationResult + PlannerBridgeRequest -> PlannerBridgeResult (+ NormalizedExecutionFeedback when executed)` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit bridge input boundary

The bridge owner must read one explicit normalized input surface rather than reach through unrelated owners.

`PlannerBridgeRequest` is expected to carry at least:

1. source externalization-result id,
2. normalized externalization proposal when available,
3. current behavior-spec snapshot,
4. current channel-descriptor snapshot,
5. current channel-status snapshot,
6. executor callback or handoff capability surface.

The bridge owner must not:

1. inspect raw channel-transport internals,
2. inspect feedback-recorder storage internals,
3. mutate persistence stores directly,
4. pull private state from governance owners.

### 3.2 Lifecycle

1. `12` publishes one formal externalization result.
2. Runtime provides one explicit `PlannerBridgeRequest` for the same cycle.
3. Planner bridge owner validates the request, behavior, and channel invariants.
4. The owner builds one `EvaluatePlannerBridgeOp` for orchestration visibility.
5. An owner-controlled bridge path computes one `PlannerBridgeResult` and, if execution occurs, one `NormalizedExecutionFeedback`.
6. If the proposal is accepted, the owner publishes one immutable `ActionDecision` and one accepted bridge result.
7. If the proposal is policy-rejected or fails pre-execution consistency checks, the owner publishes one immutable rejected bridge result.
8. If execution occurs, the owner publishes one immutable normalized execution-feedback contract.
9. A downstream feedback recorder may persist the same outcome, but persistence does not replace the bridge result.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `ThoughtExternalizationResult` and `PlannerBridgeRequest`.
2. Planner evaluation, accepted decisions, policy rejection, and execution-consistency-failure semantics belong to `13` rather than being scattered across downstream logs.
3. Feedback recorder remains a downstream collaborator rather than the bridge owner itself.
4. Rejected or failed bridge paths must still produce formal bridge results.
5. Channel transport remains outside this slice.
6. `13` publishes one formal bridge result for every evaluated normalized proposal path.
7. Deterministic first-version rejection taxonomies or channel ranking may exist as an owner-private path, but do not become permanent architecture truth.

## 4. Data Structures

### 4.1 PlannerBridgeRequest
- `request_id: str`
- `source_externalization_result_id: str`
- `normalized_proposal_present: bool`
- `behavior_snapshot: dict[str, object]`
- `channel_descriptor_snapshot: dict[str, object]`
- `channel_status_snapshot: dict[str, object]`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `13`,
2. prevent owner reach-through into transport and recorder internals,
3. give the bridge path one bounded evaluation surface per cycle.

### 4.2 BridgeStatus
- `accepted`
- `policy_rejected`
- `execution_consistency_failed`
- `executed`
- `execution_failed`

Purpose:

1. make bridge outcomes explicit,
2. distinguish planning and execution phases,
3. prevent rejected and failed paths from disappearing.

### 4.3 BridgeRejectionReason
- `behavior_not_registered`
- `behavior_unreviewed`
- `score_below_threshold`
- `no_channel_available`
- `requested_op_unavailable`
- `missing_requested_op`
- `missing_channel_binding`
- `missing_output_op`
- `missing_op_inputs`

Purpose:

1. make bridge-level failures explicit and testable,
2. distinguish policy rejection from pre-execution consistency failure,
3. support later fidelity and routing diagnostics.

### 4.4 ExecutionConsistencyFailure
- `decision_id: str`
- `proposal_id: str`
- `behavior_name: str`
- `rejection_reason: str`
- `selected_channel_id: str`
- `selected_op: str`
- `policy_trace: dict[str, object]`

Purpose:

1. preserve explicit pre-execution bridge breakage,
2. distinguish executor-readiness failures from policy rejection,
3. support downstream audit and evaluation.

### 4.5 PlannerBridgeResult
- `result_id: str`
- `source_request_id: str`
- `status: BridgeStatus`
- `action_decision: ActionDecision | None`
- `rejection_reason: BridgeRejectionReason | None`
- `execution_consistency_failure: ExecutionConsistencyFailure | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable bridge outcome for one evaluated proposal path,
2. preserve accepted and rejected semantics in one formal owner contract,
3. decouple bridge truth from logs and recorder persistence.

### 4.6 NormalizedExecutionFeedback
- `proposal_id: str`
- `decision_id: str`
- `behavior_name: str`
- `success: bool`
- `channel_id: str`
- `op_name: str`
- `normalized_intensity: float`
- `result_details: dict[str, object]`
- `state_effects: dict[str, object]`

Purpose:

1. carry one immutable post-execution outcome,
2. preserve explicit execution success or failure semantics,
3. support downstream audit persistence without becoming persistence itself.

### 4.7 EvaluatePlannerBridgeOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `externalization_result_id: str`
- `normalized_proposal_present: bool`

### 4.8 PublishActionDecisionOp
- `op_name: str`
- `owner: str`
- `decision_id: str`
- `proposal_id: str`
- `selected_channel_id: str`
- `selected_op: str`

### 4.9 PublishPlannerBridgeRejectionOp
- `op_name: str`
- `owner: str`
- `result_id: str`
- `status: str`
- `rejection_reason: str`

## 5. Module Changes

1. `planner_bridge/contracts.py` defines owner declaration, typed bridge contracts, public API protocol, ops contracts, and bridge-owner error type.
2. `planner_bridge/engine.py` implements the first owner skeleton for bridge evaluation and outcome publication.
3. `planner_bridge/__init__.py` exports the public planner-bridge surface.
4. `runtime/stages.py` adds one `13` runtime stage result and one explicit runtime-owned bridge-request provider contract.
5. `tests/test_planner_bridge_contracts.py` validates contract immutability, bridge-status taxonomy, and execution-consistency-failure preservation.
6. `tests/test_planner_bridge_engine.py` validates owner-skeleton behavior, fail-fast input handling, accepted decision publication, rejected bridge-result publication, and normalized execution-feedback publication.
7. `tests/test_runtime_stage_chain.py` validates the `12 -> 13` stage boundary and immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy mixed planner and feedback path directly.

It extracts only the evaluation, decision, rejection, consistency-failure, and execution-feedback normalization concepts first so later persistence and governance slices can attach to a stable `13` contract.

First-version migration direction:

1. preserve the existing legacy semantics that accepted decisions include selected channel, selected op, normalized intensity, validated params, and policy trace,
2. preserve policy rejection and execution-consistency-failure as distinct first-class outcomes,
3. keep feedback recorder as a downstream collaborator rather than folding persistence into the bridge owner,
4. require formal bridge results for rejected and failed paths rather than allowing logs alone.

## 7. Failure Modes and Constraints

1. Missing externalization-result provenance must raise an explicit bridge-owner error.
2. Missing required bridge-request fields must raise an explicit bridge-owner error.
3. Publication must not occur for malformed bridge results, malformed action decisions, or malformed normalized execution feedback.
4. No fallback successful-decision path is allowed.
5. Missing required bridge capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent rejection taxonomies, permanent routing heuristics, and permanent channel-ranking formulas are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private bridge path.
8. The bridge owner must not let recorder persistence stand in for formal bridge-result publication.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. bridge result preserves externalization-result provenance and bridge outcome status,
2. action decisions preserve selected channel, selected op, normalized intensity, and policy trace visibility,
3. rejected and consistency-failure outcomes preserve explicit rejection reasons,
4. normalized execution feedback preserves explicit execution result semantics before downstream persistence,
5. error types define malformed bridge-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable bridge request, bridge result, action decision, and normalized execution-feedback contracts.
2. Unit test explicit bridge-status taxonomy and rejection taxonomy.
3. Unit test that policy rejection and execution-consistency failure remain distinct outcomes.
4. Unit test that rejected bridge paths still publish formal bridge results.
5. Unit test provenance preservation from `ThoughtExternalizationResult` into `PlannerBridgeResult` and `ActionDecision`.
6. Unit test explicit normalized execution-feedback publication when execution occurs.
7. Unit test explicit failure for malformed externalization result or malformed bridge request.
8. Unit test explicit failure when required bridge capability is unavailable.
9. Unit test runtime-stage wiring from `12` into `13` through immutable frame inputs only.

## 10. Completion Snapshot

Status on 2026-06-01: this design has been implemented and validated as the current `baseline_implementation` for `13`.

Delivered boundary:

1. The owner publishes `PlannerBridgeResult` for accepted, policy-rejected, execution-consistency-failed, executed, and execution-failed paths.
2. The owner publishes `ActionDecision` for accepted and executed paths and preserves it across execution-consistency-failure results.
3. The owner publishes `NormalizedExecutionFeedback` only when execution occurs.
4. The runtime stage handoff is `12 action_proposal_externalization_contract -> 13 planner_executor_feedback_bridge`.
5. Feedback persistence, raw transport, and governance acceptance remain outside `13`.

Validated commands:

1. `pytest helios_v2/tests/test_planner_bridge_contracts.py helios_v2/tests/test_planner_bridge_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `151 passed`