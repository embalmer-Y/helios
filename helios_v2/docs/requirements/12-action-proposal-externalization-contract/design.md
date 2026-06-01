# Requirement 12 - Action proposal and externalization contract design

## 1. Design Overview

Action proposal and externalization contract is the sole owner-controlled transition between `11` internal thought loop results and the later planner-executor bridge. This slice consumes optional thought-origin proposal carriers, normalizes them into one formal externalization contract, emits explicit bridge-level rejection or drop outcomes when normalization fails, and preserves equivalent bridge evidence for fidelity diagnostics without taking planner acceptance or executor ownership.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, formal externalization contract, bridge-level rejection taxonomy, equivalent-bridge-evidence contract, and owner-controlled normalization path before the planner bridge slice is implemented.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect and replay, workspace competition, reportable consciousness, thought gating, directed retrieval, and internal-thought owners, but it still lacks a formal owner that turns optional thought-origin proposal carriers into a stable cross-domain externalization contract.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `ThoughtActionProposal` records origin thought id, behavior name, preferred op, channel constraints, outbound intensity, and governance hints.
2. Thought-origin bridge traces already record `owner_path=thought_action_bridge`, explicit drop reasons, and equivalent bridge evidence.
3. The current path mixes proposal normalization into `thinking_integration.py`, then lets planner-level code distinguish valid from invalid carriers.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for thought-origin proposal normalization and publication,
2. a typed, documented, fail-fast owner for bridge-level rejection and equivalent-evidence publication that remains separate from planner acceptance and executor dispatch.

## 3. Target Architecture

The initial action-externalization slice contains ten runtime concepts:

1. `ThoughtExternalizationRequest`: immutable explicit bridge input contract for one cycle.
2. `NormalizedThoughtActionProposal`: immutable formal thought-origin externalization contract.
3. `ExternalizationStatus`: explicit bridge outcome taxonomy.
4. `BridgeRejectionReason`: explicit bridge-level rejection taxonomy.
5. `EquivalentBridgeEvidence`: immutable distinct evidence contract for non-explicit but externally relevant thought-origin signal.
6. `ThoughtExternalizationResult`: immutable published bridge result for one cycle.
7. `RequestThoughtExternalizationOp`: runtime-visible request op for one bridge-normalization cycle.
8. `PublishThoughtExternalizationOp`: runtime-visible publication op for one normalized externalization contract.
9. `PublishThoughtExternalizationRejectionOp`: runtime-visible publication op for one bridge-level rejection.
10. `ThoughtExternalizationAPI`: public owner-facing API for bridge normalization and publication.

The initial owner also contains one private owner-controlled collaborator surface:

1. `ThoughtExternalizationPath`: private owner interface responsible for turning a thought-cycle result into one externalization result.

Implementation boundary confirmation:

1. Action-externalization owner owns only thought-origin proposal normalization, bridge-level rejection publication, and equivalent-evidence publication.
2. It does not own thought generation, planner acceptance, executor dispatch, or channel transport.
3. It may expose a replaceable internal externalization path, but that path remains private to the owner until promoted by a later requirement slice.
4. `ThoughtCycleResult + ThoughtExternalizationRequest -> ThoughtExternalizationResult` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit bridge input boundary

The bridge owner must read one explicit normalized input surface rather than reach through unrelated owners.

`ThoughtExternalizationRequest` is expected to carry at least:

1. source thought-cycle-result id,
2. optional thought-origin proposal carrier,
3. current-cycle target-binding context if available,
4. current-cycle channel-hint context if available,
5. thought-owner provenance needed for bridge diagnostics.

The bridge owner must not:

1. inspect planner private state,
2. inspect executor private state,
3. perform channel transport,
4. pull private state from governance owners.

### 3.2 Lifecycle

1. `11` publishes one `ThoughtCycleResult` for the current fired-thought cycle.
2. Runtime provides one explicit `ThoughtExternalizationRequest` for the same cycle.
3. Action-externalization owner validates thought-cycle result and request invariants.
4. The owner builds one `RequestThoughtExternalizationOp` for orchestration visibility.
5. An owner-controlled externalization path computes one `ThoughtExternalizationResult`.
6. If normalization succeeds, the owner publishes one immutable normalized externalization contract.
7. If normalization fails, the owner publishes one explicit bridge-level rejection or drop outcome.
8. If explicit proposal is absent but equivalent bridge evidence exists, the owner publishes one explicit equivalent-evidence outcome distinct from success.
9. Later planner and executor owners consume the result without transferring bridge ownership back into this slice.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `ThoughtCycleResult` and `ThoughtExternalizationRequest`.
2. Formal thought-origin proposal normalization belongs to `12` rather than remaining inside `11`.
3. Equivalent bridge evidence remains visible but explicitly distinct from a normalized explicit proposal.
4. User-visible external behaviors must carry final outbound text inside the normalized contract.
5. Planner acceptance and executor dispatch remain outside this slice.
6. `12` publishes one formal bridge result for every cycle where a thought-origin externalization path is evaluated.
7. Deterministic first-version normalization or evidence shaping may exist as an owner-private path, but does not become permanent architecture truth.

## 4. Data Structures

### 4.1 ThoughtExternalizationRequest
- `request_id: str`
- `source_thought_cycle_result_id: str`
- `proposal_carrier_present: bool`
- `target_binding_context: dict[str, object]`
- `channel_hint_context: dict[str, object]`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `12`,
2. prevent owner reach-through into planner and executor internals,
3. give the bridge path one bounded normalization surface per cycle.

### 4.2 NormalizedThoughtActionProposal
- `proposal_id: str`
- `origin_thought_id: str`
- `owner_path: str`
- `scope: str`
- `behavior_name: str`
- `preferred_op: str`
- `params: dict[str, object]`
- `channel_constraints: dict[str, object]`
- `outbound_intensity: float`
- `reason_trace: tuple[str, ...]`
- `governance_hints: dict[str, object]`

Purpose:

1. carry one immutable thought-origin externalization contract into later planner stages,
2. preserve thought-to-visible-behavior provenance,
3. prevent later modules from having to infer missing thought-origin semantics.

### 4.3 ExternalizationStatus
- `normalized`
- `bridge_rejected`
- `equivalent_evidence_only`
- `no_externalization`

Purpose:

1. make bridge outcomes explicit,
2. keep explicit proposal success separate from evidence-only outcomes,
3. prevent silent disappearance of bridge evaluation.

### 4.4 BridgeRejectionReason
- `schema_invalid`
- `missing_candidate_channels`
- `missing_target_user_id`
- `missing_outbound_text`
- `scope_conflict`

Purpose:

1. make bridge-level failures explicit and testable,
2. distinguish bridge rejection from planner rejection,
3. support later fidelity diagnostics.

### 4.5 EquivalentBridgeEvidence
- `origin_thought_id: str`
- `bridge_evidence_kind: str`
- `reason_trace: tuple[str, ...]`
- `candidate_summary: dict[str, object]`

Purpose:

1. preserve thought-origin externalization evidence even when no explicit normalized proposal exists,
2. keep that evidence distinct from normalized explicit contracts,
3. support evaluation and debugging of bridge completeness.

### 4.6 ThoughtExternalizationResult
- `result_id: str`
- `source_request_id: str`
- `status: ExternalizationStatus`
- `normalized_proposal: NormalizedThoughtActionProposal | None`
- `bridge_rejection_reason: BridgeRejectionReason | None`
- `equivalent_evidence: EquivalentBridgeEvidence | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable externalization-bridge outcome for one cycle,
2. preserve explicit success, rejection, and evidence-only outcomes,
3. keep downstream planner and executor work decoupled from bridge normalization.

### 4.7 RequestThoughtExternalizationOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `thought_cycle_result_id: str`
- `proposal_carrier_present: bool`

### 4.8 PublishThoughtExternalizationOp
- `op_name: str`
- `owner: str`
- `result_id: str`
- `proposal_id: str`
- `scope: str`
- `behavior_name: str`

### 4.9 PublishThoughtExternalizationRejectionOp
- `op_name: str`
- `owner: str`
- `result_id: str`
- `bridge_rejection_reason: str`

## 5. Module Changes

1. `action_externalization/contracts.py` defines owner declaration, typed externalization contracts, public API protocol, ops contracts, and bridge-owner error type.
2. `action_externalization/engine.py` will implement the first owner skeleton for proposal normalization and bridge-result publication.
3. `action_externalization/__init__.py` will export the public action-externalization surface.
4. `runtime/stages.py` will add one `12` runtime stage result and one explicit runtime-owned externalization-request provider contract.
5. `tests/test_action_externalization_contracts.py` will validate contract immutability, bridge-status taxonomy, and explicit outbound-text requirements.
6. `tests/test_action_externalization_engine.py` will validate owner-skeleton behavior, fail-fast input handling, explicit bridge rejection publication, and equivalent-evidence publication.
7. `tests/test_runtime_stage_chain.py` will validate the `11 -> 12` stage boundary and immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy mixed thought-action bridge path directly.

It extracts only the proposal-normalization, bridge-level rejection, and equivalent-evidence concepts first so the later planner bridge slice can attach to a stable `12` contract.

First-version migration direction:

1. preserve the existing legacy semantics that thought-origin proposals carry preferred op, candidate channels, outbound intensity, and governance hints,
2. move explicit normalization and drop-reason ownership out of `11` and into `12`,
3. preserve equivalent bridge evidence as a first-class explicit outcome for fidelity diagnostics,
4. require final outbound text for user-visible external behaviors inside the normalized contract.

## 7. Failure Modes and Constraints

1. Missing thought-cycle-result provenance must raise an explicit bridge-owner error.
2. Missing required externalization-request fields must raise an explicit bridge-owner error.
3. Publication must not occur for malformed normalized proposals or malformed equivalent-evidence contracts.
4. No fallback successful-externalization path is allowed.
5. Missing required bridge capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent normalization formulas, permanent evidence heuristics, and permanent bridge thresholds are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private externalization path.
8. The bridge owner must not let downstream planner or executor owners repair missing required outbound text.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. externalization result preserves thought-cycle provenance and bridge outcome status,
2. normalized proposals preserve owner path, behavior, op, and channel constraint visibility,
3. bridge-level rejection preserves explicit bridge rejection reasons,
4. equivalent bridge evidence preserves fidelity-diagnostic signal without pretending to be explicit success,
5. error types define malformed externalization-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable externalization request, normalized proposal, rejection, and evidence contracts.
2. Unit test explicit bridge-status taxonomy and bridge rejection taxonomy.
3. Unit test that user-visible external behaviors require final outbound text inside the normalized contract.
4. Unit test that equivalent bridge evidence remains distinct from normalized explicit proposals.
5. Unit test provenance preservation from `ThoughtCycleResult` into `ThoughtExternalizationResult`.
6. Unit test explicit bridge rejection publication rather than silent drops.
7. Unit test explicit failure for malformed thought-cycle result or malformed externalization request.
8. Unit test explicit failure when required bridge capability is unavailable.
9. Unit test runtime-stage wiring from `11` into `12` through immutable frame inputs only.