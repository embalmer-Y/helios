# Requirement 11 - Internal thought loop owner design

## 1. Design Overview

Internal thought loop is the sole owner-controlled transition between `10` directed retrieval and later action externalization or identity-governance slices. This slice consumes a fired thought-window context, executes one bounded thought cycle, decides sufficiency and continuation for the current cycle, emits memory-handoff directives for later retrieval, and may emit optional action or self-revision proposals without owning downstream acceptance or persistence.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, fired-path thought-cycle contract, fired-path non-success outcome contract, memory-handoff contract, optional proposal-carrier contract, and owner-controlled thought path before externalization and governance slices are implemented.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect and replay, workspace competition, reportable consciousness, thought gating, and directed retrieval owners, but it still lacks a formal owner that executes one internal thought cycle after the thought window has been prepared.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `ThoughtCycleResult` records the current thought outcome, sufficiency, continuation, recall intent, and optional downstream proposals.
2. `InternalThoughtTrace` records fired-path observability.
3. `MemoryHandoffDirective` records the retrieval-relevant carry material for the next cycle.
4. The current path mixes thought execution with gate ownership, retrieval ownership, direct persistence, and downstream proposal wiring.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for fired-path thought execution,
2. a typed, documented, fail-fast owner for sufficiency judgment and proposal emission that remains separate from persistence and downstream acceptance.

## 3. Target Architecture

The initial internal-thought slice contains ten runtime concepts:

1. `InternalThoughtRequest`: immutable explicit fired-path input contract for one cycle.
2. `ThoughtContent`: immutable successful internal-thought payload.
3. `ThoughtExecutionStatus`: explicit fired-path execution outcome taxonomy.
4. `ThoughtCycleResult`: immutable published thought-cycle snapshot for one cycle.
5. `MemoryHandoffDirective`: immutable retrieval-facing carry contract for later cycles.
6. `InternalThoughtTrace`: immutable observability contract for the thought owner.
7. `ThoughtActionProposalCarrier`: optional action-proposal carrier surface emitted by `11` only as a proposal.
8. `SelfRevisionProposalCarrier`: optional self-revision-proposal carrier surface emitted by `11` only as a proposal.
9. `RunInternalThoughtOp`: runtime-visible request op for one fired thought cycle.
10. `PublishThoughtCycleResultOp`: runtime-visible publication op for one thought-cycle result.

The initial owner also contains one private owner-controlled collaborator surface:

1. `InternalThoughtPath`: private owner interface responsible for turning a fired-path request into one thought-cycle result and one observability trace.

Implementation boundary confirmation:

1. Internal-thought owner owns only fired-path thought execution, sufficiency judgment, continuation emission, retrieval handoff emission, and optional proposal emission.
2. It does not own gate scoring, retrieval-window assembly, memory persistence, planner routing, executor dispatch, or governance acceptance.
3. It may expose a replaceable internal thought path, but that path remains private to the owner until promoted by a later requirement slice.
4. `ThoughtGateResult + ThoughtWindowBundle + ContinuationPressureState + InternalThoughtRequest -> ThoughtCycleResult` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit fired-path input boundary

The thought owner must read one explicit normalized input surface rather than reach through unrelated owners.

`InternalThoughtRequest` is expected to carry at least:

1. source gate-result id,
2. source retrieval-bundle id,
3. source continuation state,
4. current-cycle internal-state summary,
5. prompt-contract snapshot or equivalent public prompt inputs,
6. current-cycle thought-type candidate surface if later needed.

The thought owner must not:

1. read raw memory storage internals,
2. inspect planner or executor private state,
3. mutate persistence stores directly,
4. pull private state from identity-governance owners.

### 3.2 Lifecycle

1. `10` publishes one bounded thought-window bundle.
2. Runtime provides one explicit `InternalThoughtRequest` for the current cycle.
3. Internal-thought owner validates gate-result, retrieval-bundle, continuation, and request invariants.
4. The owner builds one `RunInternalThoughtOp` for orchestration visibility.
5. An owner-controlled thought path computes one `ThoughtCycleResult` and one `InternalThoughtTrace`.
6. The owner publishes one immutable `ThoughtCycleResult` for every valid fired-thought cycle.
7. The owner publishes explicit fired-path non-success outcomes when execution cannot produce a valid successful thought.
8. The owner may publish memory handoff, optional action proposal, and optional self-revision proposal as part of the same result.
9. Later externalization, feedback, and governance owners consume those outputs without transferring ownership back into `11`.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `ThoughtGateResult`, `ThoughtWindowBundle`, `ContinuationPressureState`, and `InternalThoughtRequest`.
2. `11` owns fired-path thought execution only; `09` remains the sole owner of no-fire cycles.
3. `11` may emit optional action and self-revision proposals, but downstream acceptance remains outside this slice.
4. Thought persistence remains outside `11`; this slice publishes memory handoff and observability only.
5. `11` publishes one formal thought-cycle result every valid fired-thought cycle.
6. Fired-path non-success outcomes are explicit and auditable rather than silent drops.
7. Deterministic first-version thought shaping or fallback parsing may exist as an owner-private path, but does not become permanent architecture truth.

## 4. Data Structures

### 4.1 InternalThoughtRequest
- `request_id: str`
- `source_gate_result_id: str`
- `source_retrieval_bundle_id: str`
- `source_continuation_active: bool`
- `internal_state_summary: str`
- `prompt_contract_summary: dict[str, object]`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `11`,
2. prevent owner reach-through into unrelated runtime state,
3. give the thought path one bounded fired-path request surface per cycle.

### 4.2 ThoughtContent
- `thought_id: str`
- `thought_type: str`
- `content: str`
- `source_path: str`
- `llm_used: bool`
- `fallback_used: bool`

Purpose:

1. carry one successful thought payload for the current cycle,
2. preserve content provenance and source-path visibility,
3. separate successful content from the broader cycle result contract.

### 4.3 ThoughtExecutionStatus
- `completed`
- `insufficient_generation`
- `capability_rejected_cycle`
- `request_invalid`

Purpose:

1. make fired-path execution outcomes explicit,
2. prevent silent loss of fired-path thought failures,
3. support deterministic downstream handling.

### 4.4 ThoughtCycleResult
- `result_id: str`
- `source_request_id: str`
- `execution_status: ThoughtExecutionStatus`
- `thought: ThoughtContent | None`
- `trigger_reason: str`
- `sufficiency_level: float`
- `continuation_requested: bool`
- `continuation_reason: str`
- `continuation_pressure_delta: float`
- `recall_intent: str`
- `memory_handoff: MemoryHandoffDirective | None`
- `action_proposal: dict[str, object] | None`
- `self_revision_proposal: dict[str, object] | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable formal thought-cycle result for one fired-thought cycle,
2. preserve sufficiency and continuation semantics,
3. carry optional downstream proposals without taking downstream acceptance ownership.

### 4.5 MemoryHandoffDirective
- `recall_intent: str`
- `selected_memory_refs: tuple[str, ...]`
- `saved_for_next_tick: bool`
- `source_thought_id: str`

### 4.6 InternalThoughtTrace
- `triggered: bool`
- `trigger_reason: str`
- `llm_used: bool`
- `fallback_used: bool`
- `execution_status: str`
- `sufficiency_level: float`
- `continuation_requested: bool`
- `continuation_reason: str`
- `recall_intent: str`
- `action_explicit: bool`
- `action_parse_status: str`

### 4.7 RunInternalThoughtOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `gate_result_id: str`
- `retrieval_bundle_id: str`

### 4.8 PublishThoughtCycleResultOp
- `op_name: str`
- `owner: str`
- `result_id: str`
- `execution_status: str`
- `continuation_requested: bool`
- `has_action_proposal: bool`
- `has_self_revision_proposal: bool`

## 5. Module Changes

1. `internal_thought/contracts.py` defines owner declaration, typed thought contracts, public API protocol, ops contracts, and thought-owner error type.
2. `internal_thought/engine.py` will implement the first owner skeleton for fired-path thought execution and result publication.
3. `internal_thought/__init__.py` will export the public internal-thought surface.
4. `runtime/stages.py` will add one `11` runtime stage result and one explicit runtime-owned internal-thought request provider contract.
5. `tests/test_internal_thought_contracts.py` will validate contract immutability, fired-path outcome taxonomy, and memory-handoff preservation.
6. `tests/test_internal_thought_engine.py` will validate owner-skeleton behavior, fail-fast input handling, explicit fired-path non-success publication, and optional proposal emission.
7. `tests/test_runtime_stage_chain.py` will validate the `10 -> 11` stage boundary and immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy mixed `thinking_integration.py` path directly.

It extracts only the thought execution, sufficiency, continuation, and optional proposal-emission concepts first so later externalization, feedback, and governance slices can attach to a stable `11` contract.

First-version migration direction:

1. preserve the existing legacy semantics that a thought cycle can emit sufficiency, continuation request, recall intent, selected-memory refs, optional action proposal, and optional self-revision proposal,
2. remove no-fire ownership from the internal-thought owner and keep that boundary in `09`,
3. remove direct persistence side effects from `11` and defer formal writes to later owners,
4. preserve structured fired-path observability as a first-class public contract.

## 7. Failure Modes and Constraints

1. Missing gate-result or retrieval-bundle provenance must raise an explicit thought-owner error.
2. Missing required internal-thought request fields must raise an explicit thought-owner error.
3. Publication must not occur for malformed thought-cycle results or malformed memory-handoff directives.
4. No fallback successful-thought path is allowed.
5. Missing required thought capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent thought formulas, permanent sufficiency thresholds, and permanent continuation heuristics are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private thought path.
8. The thought owner must not directly persist thought output or identity changes in this slice.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. thought-cycle result preserves request provenance and fired-path execution status,
2. internal-thought trace preserves sufficiency, continuation, and parse visibility,
3. memory handoff preserves retrieval-relevant carry material for later cycles,
4. optional proposal presence is explicit without implying downstream acceptance,
5. error types define malformed thought-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable internal-thought request, thought-cycle result, and memory-handoff contracts.
2. Unit test explicit fired-path execution-status taxonomy.
3. Unit test that optional action and self-revision proposals can be emitted without transferring downstream ownership.
4. Unit test that persistence side effects are not part of the `11` public contract.
5. Unit test provenance preservation from fired-path inputs into `ThoughtCycleResult`.
6. Unit test explicit fired-path non-success publication rather than silent drops.
7. Unit test explicit failure for malformed gate result, malformed retrieval bundle, or malformed internal-thought request.
8. Unit test explicit failure when required thought capability is unavailable.
9. Unit test runtime-stage wiring from `10` into `11` through immutable frame inputs only.