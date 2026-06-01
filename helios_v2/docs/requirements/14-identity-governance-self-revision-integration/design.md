# Requirement 14 - Identity governance and self revision integration design

## 1. Design Overview

Identity governance is the sole owner-controlled transition between optional normalized self-revision proposals and later consumers of updated identity state. This slice consumes normalized self-revision proposals, evaluates them under explicit governance policy and proactive-governance pressure, publishes one formal governance result for accepted and rejected paths, mutates identity state when accepted, and collaborates with downstream personality synchronization and audit persistence without taking ownership of either.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, explicit governance-result taxonomy, pressure-state contract, applied-identity-state contract, and owner-controlled governance path before later personality read models or long-term autobiographical synthesis are refined.

## 2. Current State and Gap

Helios v2 now has runtime kernel, thought gating, directed retrieval, internal thought, action externalization, and planner bridge owners specified, but it still lacks a formal owner that closes the loop from thought-origin self reflection into durable identity continuity.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `self_revision_proposal` is derived in thought execution but only as an optional payload.
2. `SelfRevisionProposal` and `IdentityRevisionRecord` encode proposal and result semantics.
3. `IdentityGovernance.apply_self_revision()` owns acceptance or rejection, identity-boundary checks, mutation, and reason trace.
4. `build_proactive_governance_signal()` and deferred-trace summaries directly influence revision judgment.
5. `helios_main.py` still mixes governance invocation, identity-store persistence, personality sync, and audit publication.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for proposal validation, pressure evaluation, and governance-result publication,
2. a typed, documented, fail-fast owner for identity mutation and applied-state publication that remains separate from personality sync and audit persistence.

## 3. Target Architecture

The initial identity-governance slice contains eleven runtime concepts:

1. `IdentityGovernanceRequest`: immutable explicit governance input contract for one cycle.
2. `RevisionStatus`: explicit identity-governance outcome taxonomy.
3. `GovernancePressureState`: immutable pressure-state contract.
4. `GovernanceRejectionReason`: explicit governance rejection taxonomy.
5. `RevisionDecision`: immutable accepted or rejected governance decision contract.
6. `AppliedIdentityState`: immutable publication of post-governance identity state.
7. `IdentityGovernanceResult`: immutable published governance result for one cycle.
8. `EvaluateIdentityGovernanceOp`: runtime-visible request op for one governance evaluation cycle.
9. `PublishRevisionDecisionOp`: runtime-visible publication op for one accepted or rejected governance decision.
10. `PublishAppliedIdentityStateOp`: runtime-visible publication op for one accepted identity mutation result.
11. `IdentityGovernanceAPI`: public owner-facing API for proposal evaluation and state publication.

The initial owner also contains one private owner-controlled collaborator surface:

1. `IdentityGovernancePath`: private owner interface responsible for turning a normalized proposal into one governance result and optional applied identity state.

Implementation boundary confirmation:

1. Identity-governance owner owns only proposal validation, pressure evaluation, revision decision, identity mutation, and formal result publication.
2. It does not own thought generation, personality projection rendering, personality sync application, or audit persistence.
3. It may expose a replaceable internal governance path, but that path remains private to the owner until promoted by a later requirement slice.
4. `NormalizedSelfRevisionProposal + IdentityGovernanceRequest -> IdentityGovernanceResult (+ AppliedIdentityState when accepted)` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit governance input boundary

The governance owner must read one explicit normalized input surface rather than reach through unrelated owners.

`IdentityGovernanceRequest` is expected to carry at least:

1. source self-revision proposal id,
2. normalized self-revision proposal payload,
3. current identity-state snapshot,
4. bounded governance-trace summary and recent deferred-trace history,
5. tick or cycle metadata,
6. owner-provided mutation capability surface.

The governance owner must not:

1. inspect raw internal-thought private state,
2. inspect personality renderer internals,
3. inspect audit-storage internals,
4. mutate unrelated persistence stores directly.

### 3.2 Lifecycle

1. `11` publishes one optional self-revision proposal in thought-cycle output.
2. Runtime provides one explicit `IdentityGovernanceRequest` for the same cycle when a normalized proposal exists.
3. Identity-governance owner validates the request, proposal, and identity invariants.
4. The owner builds one `EvaluateIdentityGovernanceOp` for orchestration visibility.
5. An owner-controlled governance path computes one `GovernancePressureState` and one `IdentityGovernanceResult`.
6. If the proposal is accepted, the owner mutates identity state, publishes one immutable `RevisionDecision`, and publishes one immutable `AppliedIdentityState`.
7. If the proposal is rejected or invalid, the owner publishes one immutable rejected governance result.
8. Downstream personality sync may consume the applied identity state, but synchronization does not replace the governance result.
9. Downstream audit persistence may persist the same outcome, but persistence does not replace the governance result.

### 3.3 Confirmed design constraints for this slice

1. Required upstream input is normalized self-revision proposal plus explicit governance request.
2. Proposal validation, pressure evaluation, revision acceptance or rejection, and identity mutation belong to `14` rather than being scattered across `helios_main.py` and helper modules.
3. Proactive governance pressure belongs to `14` rather than to a future passive observability slice.
4. Personality synchronization remains downstream collaboration rather than part of the governance owner.
5. Rejected or invalid governance paths must still produce formal governance results.
6. Deterministic first-version revision handling or confidence thresholds may exist as an owner-private path, but do not become permanent architecture truth.

## 4. Data Structures

### 4.1 IdentityGovernanceRequest
- `request_id: str`
- `source_proposal_id: str`
- `proposal_snapshot: dict[str, object]`
- `identity_state_snapshot: dict[str, object]`
- `governance_trace_summary: dict[str, object]`
- `recent_governance_trace_history: tuple[dict[str, object], ...]`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `14`,
2. prevent owner reach-through into thought, projection, and audit internals,
3. give the governance path one bounded evaluation surface per cycle.

### 4.2 RevisionStatus
- `accepted`
- `accepted_with_monitoring`
- `rejected`
- `invalid_proposal`

Purpose:

1. make governance outcomes explicit,
2. distinguish monitored acceptance from hard rejection,
3. prevent invalid and rejected paths from disappearing.

### 4.3 GovernancePressureState
- `active: bool`
- `pressure_score: float`
- `pressure_level: str`
- `review_hint: str`
- `recent_trace_count: int`
- `source_consistency_ratio: float`
- `recent_trigger_sources: tuple[str, ...]`

Purpose:

1. preserve explicit proactive-governance pressure as decision input,
2. distinguish monitoring and stabilizing backpressure,
3. support later audit and evaluation.

### 4.4 GovernanceRejectionReason
- `invalid_self_revision_payload`
- `unsupported_revision_type`
- `identity_boundary_violation`
- `missing_self_definition`
- `missing_personality_adjustment`
- `missing_identity_narrative`
- `governance_backpressure`

Purpose:

1. make governance-level rejections explicit and testable,
2. distinguish structural invalidity from policy rejection,
3. support later fidelity analysis.

### 4.5 RevisionDecision
- `revision_id: str`
- `origin_thought_id: str`
- `status: RevisionStatus`
- `requested_change: dict[str, object]`
- `applied_change: dict[str, object]`
- `reason_trace: tuple[str, ...]`

Purpose:

1. represent one immutable governance decision,
2. preserve requested and applied semantics distinctly,
3. decouple governance truth from direct store mutation side effects.

### 4.6 AppliedIdentityState
- `revision_id: str`
- `current_revision: str`
- `identity_state_snapshot: dict[str, object]`
- `changed_fields: tuple[str, ...]`

Purpose:

1. carry one immutable post-acceptance identity-state publication,
2. support downstream personality synchronization without owning it,
3. prevent consumers from scraping mutable owner internals.

### 4.7 IdentityGovernanceResult
- `result_id: str`
- `source_request_id: str`
- `pressure_state: GovernancePressureState`
- `revision_decision: RevisionDecision`
- `applied_identity_state: AppliedIdentityState | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable governance outcome for one evaluated proposal path,
2. preserve accepted and rejected semantics in one formal owner contract,
3. decouple governance truth from logs and persistence.

### 4.8 EvaluateIdentityGovernanceOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `source_proposal_id: str`

### 4.9 PublishRevisionDecisionOp
- `op_name: str`
- `owner: str`
- `revision_id: str`
- `status: str`
- `origin_thought_id: str`

### 4.10 PublishAppliedIdentityStateOp
- `op_name: str`
- `owner: str`
- `revision_id: str`
- `current_revision: str`
- `changed_fields: tuple[str, ...]`

## 5. Module Changes

1. `identity_governance/contracts.py` defines owner declaration, typed governance contracts, public API protocol, ops contracts, and governance-owner error type.
2. `identity_governance/engine.py` implements the first owner skeleton for proposal validation, pressure evaluation, revision decision, and applied-state publication.
3. `identity_governance/__init__.py` exports the public governance surface.
4. `runtime/stages.py` adds one `14` runtime stage result and one explicit runtime-owned governance-request provider contract.
5. `tests/test_identity_governance_contracts.py` validates contract immutability, pressure-state preservation, and revision-status taxonomy.
6. `tests/test_identity_governance_engine.py` validates owner-skeleton behavior, fail-fast input handling, accepted mutation publication, rejected result publication, and downstream-boundary preservation.
7. `tests/test_runtime_stage_chain.py` validates the `11 -> 14` governance handoff and immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy mixed governance path directly.

It extracts only proposal validation, pressure evaluation, revision decision, mutation, and applied-state publication first so later personality or autobiographical synthesis slices can attach to a stable `14` contract.

First-version migration direction:

1. preserve the legacy semantics that accepted revisions publish requested change, applied change, reason trace, and new current revision,
2. preserve proactive governance monitoring and stabilizing backpressure as distinct first-class decision inputs,
3. keep personality synchronization as a downstream collaborator rather than folding projection ownership into governance,
4. keep audit persistence as a downstream collaborator rather than folding journal persistence into governance,
5. require formal governance results for rejected and invalid paths rather than allowing runtime-local trace dictionaries alone.

## 7. Failure Modes and Constraints

1. Missing proposal provenance must raise an explicit governance-owner error.
2. Missing required governance-request fields must raise an explicit governance-owner error.
3. Publication must not occur for malformed governance results, malformed revision decisions, or malformed applied identity state.
4. No fallback accepted-mutation path is allowed.
5. Missing required governance capability must abort execution rather than substituting direct store mutation.
6. Permanent revision formulas, permanent confidence thresholds, and permanent personality ideals are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private governance path.
8. The governance owner must not let personality sync or audit persistence stand in for formal governance-result publication.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. governance result preserves proposal provenance and revision outcome status,
2. pressure state preserves active, score, level, review hint, and recent-trigger visibility,
3. revision decision preserves requested change, applied change, and explicit reason trace,
4. applied identity state preserves changed fields and current revision before downstream sync,
5. error types define malformed governance-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable governance request, governance result, revision decision, and applied identity state contracts.
2. Unit test explicit revision-status taxonomy and governance-rejection taxonomy.
3. Unit test that monitoring acceptance and stabilizing backpressure remain distinct outcomes.
4. Unit test that rejected or invalid proposal paths still publish formal governance results.
5. Unit test provenance preservation from self-revision proposal into governance result and revision decision.
6. Unit test explicit applied identity-state publication when a revision is accepted.
7. Unit test explicit failure for malformed proposal or malformed governance request.
8. Unit test explicit failure when required governance capability is unavailable.
9. Unit test runtime-stage wiring for immutable governance-request input and downstream consumption of applied identity state.

## 10. Completion Snapshot

Status on 2026-06-01: this design has been implemented and validated as the current `baseline_implementation` for `14`.

Delivered boundary:

1. The owner publishes `IdentityGovernanceResult` for `accepted`, `accepted_with_monitoring`, `rejected`, and `invalid_proposal` paths.
2. The owner publishes deterministic proactive-governance pressure as a formal `GovernancePressureState`, not only as passive observability.
3. The owner publishes `AppliedIdentityState` only for accepted and monitored-accepted mutations.
4. The runtime stage handoff is `11 internal_thought_loop_owner -> 14 identity_governance_self_revision_integration`.
5. Personality synchronization and audit persistence remain outside `14`.

Validated commands:

1. `pytest helios_v2/tests/test_identity_governance_contracts.py helios_v2/tests/test_identity_governance_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `15 passed`
2. `pytest helios_v2/tests -q` -> `159 passed`