# Requirement 11 - Internal thought loop owner

## 1. Background and Problem

After `10` assembles a bounded thought-window retrieval bundle, Helios v2 still lacks a dedicated owner that executes one internal thought cycle and turns the current-cycle context into a formal thought outcome. Without this owner, later modules would either consume retrieval bundles and invent private thought semantics, or action and governance owners would silently absorb sufficiency judgment, continuation intent, and proposal emission into one mixed controller.

The current legacy implementation proves that the internal thought loop is a real runtime concept rather than incidental prompt text. It already carries `ThoughtCycleResult`, `InternalThoughtTrace`, `continuation_requested`, `recall_intent`, optional `action_proposal`, and optional `self_revision_proposal`, but these semantics remain mixed together with gate ownership, retrieval ownership, direct persistence, and downstream action wiring. Helios v2 must separate internal thought execution into its own owner before externalization and identity-governance slices are finalized.

This slice corresponds to the transition from a bounded thought-window bundle into one formal internal-thought cycle outcome, not to thought gating, directed retrieval, planner acceptance, executor dispatch, memory persistence, or identity-governance acceptance.

## 2. Goal

Create an internal-thought owner that consumes a fired thought-window context, executes one bounded internal thought cycle, publishes an immutable thought-cycle result with explicit sufficiency and continuation semantics, and may emit optional action and self-revision proposals without fallback behavior, private reach-through, or ownership collapse into persistence, planning, or governance acceptance.

## 3. Functional Requirements

### 3.1 Internal-thought owner boundary
1. The internal-thought layer must be the sole owner of fired-path internal thought execution in this slice.
2. The owner must remain separate from thought gating, directed retrieval, persistence, action externalization, planner routing, executor dispatch, and identity-governance acceptance.
3. The owner must not reinterpret itself as the owner of gate scoring, retrieval-window assembly, planner feasibility, or identity revision application.

### 3.2 Upstream input boundary
1. The internal-thought layer must accept `ThoughtGateResult` as a required upstream input contract.
2. The internal-thought layer must accept the bounded thought-window retrieval bundle as a required upstream input contract.
3. The internal-thought layer must accept the current `ContinuationPressureState` as a required upstream carry input.
4. The internal-thought layer must accept explicit current-cycle internal-state summaries and prompt-contract inputs through documented contracts rather than reaching through arbitrary runtime state.
5. The owner must not require direct imports into planner, executor, channel, or identity-governance owners in this slice.
6. The owner must not require direct persistence access in this slice.

### 3.3 Thought-cycle output
1. The first public output of this slice must be a formal thought-cycle result rather than raw LLM text alone.
2. Every valid fired-thought cycle in this slice must publish one formal thought-cycle result.
3. The thought-cycle result must preserve at least thought id, thought content or explicit non-content outcome, thought type, sufficiency level, continuation request, continuation reason, continuation-pressure delta, and recall intent.
4. The thought-cycle result must explicitly distinguish between a successful thought outcome and a fired-path non-success outcome such as capability rejection or insufficient generation.
5. The internal-thought owner must not silently swallow fired-path failures or return nothing for a cycle that entered `11`.

### 3.4 Continuation and recall ownership
1. The internal-thought layer must be the sole owner of current-cycle sufficiency judgment and continuation-request emission in this slice.
2. The owner must decide whether the current thought is sufficient or should continue into a later cycle.
3. The owner must emit `recall_intent` for later retrieval when the thought result requires future continuation or selective recall.
4. The owner may emit selected-memory refs for later retrieval, but only through a documented public handoff contract.
5. The internal-thought owner must not own the next-cycle gate carry state itself; that remains the published continuation-pressure contract handled across `09` and later runtime wiring.

### 3.5 Optional proposal emission boundary
1. The internal-thought owner may emit one optional structured action proposal for later externalization.
2. The internal-thought owner may emit one optional structured self-revision proposal for later identity governance.
3. Emitting these proposals does not transfer planner acceptance, executor normalization, governance acceptance, or writeback ownership into `11`.
4. The owner must not normalize final channel binding or governance approval inside this slice.
5. The owner must not assume that any emitted proposal will be accepted downstream.

### 3.6 Separation from persistence and downstream execution
1. The internal-thought owner may publish memory handoff directives and observability, but it must not directly persist thought memory in this slice.
2. Formal thought persistence must remain outside `11` and be handled by later feedback or memory owners.
3. The internal-thought owner must not call planner, executor, channel, or identity-governance owners directly as part of thought execution.
4. The owner must not directly mutate identity storage or memory storage in this slice.

### 3.7 Learned or runtime-provided thought semantics
1. The owner must not hardcode permanent thought-generation formulas, sufficiency thresholds, or continuation heuristics into the architecture contract.
2. Thought-generation policy, thought-type selection policy, sufficiency policy, continuation policy, and proposal-emission policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty-thought defaults, and explicit owner-controlled bootstrap metadata.
4. If the first-version implementation uses deterministic fallback shaping or deterministic thought-type selection, that path must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic internal-thought semantics must remain learning-driven rather than frozen into architecture defaults.

### 3.8 No fallback behavior
1. The internal-thought layer must not synthesize a fallback successful thought-cycle result when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic thought path when the configured thought capability is unavailable.
3. The owner must fail explicitly when required fired-path invariants or required thought capability are missing.
4. The owner must not silently reinterpret a fired-thought capability failure as if no thought cycle had occurred.
5. The owner must not silently persist or externalize thought output when the formal thought-cycle result is invalid.

## 4. Non-Functional Requirements

1. Thought-cycle result, memory-handoff, and proposal contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured thought policy.
3. The owner boundary must remain separate from gating, retrieval, persistence, externalization, planning, execution, and governance owners.
4. Published state must preserve enough observability to support later diagnostics of why a thought succeeded, failed, requested continuation, or emitted optional proposals.
5. Fired-path non-success outcomes must remain explicit and auditable.

## 5. Code Behavior Constraints

1. Internal-thought code must not import planner, executor, channel, or identity-governance owners directly.
2. Internal-thought code must not directly write memory or identity persistence in this slice.
3. Internal-thought code must expose only documented APIs and ops contracts across module boundaries.
4. Internal-thought code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
5. Internal-thought code must not blur owner boundaries by taking ownership of retrieval-window assembly, planner acceptance, or governance approval.
6. The fired-path result must not disappear simply because the owner could not produce a valid thought content string.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/internal_thought/contracts.py`
2. `helios_v2/src/helios_v2/internal_thought/engine.py`
3. `helios_v2/src/helios_v2/internal_thought/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_internal_thought_contracts.py`
6. `helios_v2/tests/test_internal_thought_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from fired-path thought inputs into a formal `ThoughtCycleResult`.
2. The package defines documented ops contracts for thought-cycle execution request, thought-cycle publication, and optional proposal publication or observability.
3. The contract surface publishes one formal thought-cycle result every valid fired-thought cycle, including explicit fired-path non-success outcomes.
4. The contract surface publishes sufficiency, continuation request, continuation reason, recall intent, and continuation-pressure delta as first-class fields rather than burying them in free text.
5. The package records that optional action proposals and self-revision proposals may be emitted by `11`, but downstream acceptance belongs to later owners.
6. The package records that direct thought persistence remains outside `11` and belongs to later feedback or memory owners.
7. The package does not claim gate, retrieval, externalization, planner, executor, persistence, or identity-governance acceptance ownership.
8. No test or implementation path demonstrates fallback successful-thought synthesis, silent fired-path failure loss, or direct persistence side effects from `11`.