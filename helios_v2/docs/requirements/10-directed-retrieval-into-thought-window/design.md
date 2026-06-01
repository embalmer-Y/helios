# Requirement 10 - Directed retrieval into thought window design

## 1. Design Overview

Directed retrieval into the thought window is the sole owner-controlled transition between `09` thought gating and the later internal-thought owner. This slice consumes explicit retrieval demand, builds one retrieval query plan, queries public memory-owner surfaces, applies owner-controlled tiered selection to the returned candidates, and publishes one bounded retrieval bundle for the thought window.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, explicit retrieval-input contract, optional prior-thought retrieval-request handoff, bounded thought-window bundle contract, and owner-controlled selection path before the internal-thought slice is implemented.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect and replay, workspace competition, reportable consciousness, and thought-gating owners, but it still lacks a formal owner that decides what bounded memory material enters the thought window after a fired gate.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `RetrievalQueryPlan` records retrieval demand built from current stimuli and recall intent.
2. `DirectedMemoryBundle` groups short-term, mid-term, long-term, and autobiographical hits into one bounded context surface.
3. `RetrievalSelectionTrace` and retrieval SEC trace record why candidates were selected.
4. The current path mixes query planning, tier selection, and bundle shaping inside the memory owner, then lets the thought owner consume the result ad hoc.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for retrieval-query planning and tiered selection,
2. a typed, documented, fail-fast owner for bounded thought-window bundle assembly that remains separate from memory persistence and thought generation.

## 3. Target Architecture

The initial directed-retrieval slice contains nine runtime concepts:

1. `RetrievalRequest`: immutable explicit retrieval-demand contract for one cycle.
2. `RetrievalQueryPlan`: immutable owner-built query plan for one cycle.
3. `ThoughtWindowHit`: immutable bounded projection of one selected memory hit for the thought window.
4. `ThoughtWindowBundle`: immutable selected bundle grouped by public memory tier.
5. `RetrievalSelectionTrace`: immutable tier-level selection summary.
6. `RetrievalSECTraceItem`: immutable candidate-level selection evidence item.
7. `PlanDirectedRetrievalOp`: runtime-visible request op for one retrieval-planning cycle.
8. `PublishThoughtWindowBundleOp`: runtime-visible publication op for one thought-window retrieval bundle.
9. `DirectedRetrievalAPI`: public owner-facing API for retrieval planning and bundle publication.

The initial owner also contains one private owner-controlled collaborator surface:

1. `DirectedRetrievalPath`: private owner interface responsible for turning a retrieval request into one query plan and one bounded bundle.

Implementation boundary confirmation:

1. Directed-retrieval owner owns only retrieval-query planning, tiered selection or reranking, and thought-window bundle publication.
2. It does not own memory persistence, memory-family mutation, thought-window firing, thought generation, action externalization, planner routing, executor dispatch, or identity writeback.
3. It may expose a replaceable internal retrieval path, but that path remains private to the owner until promoted by a later requirement slice.
4. `ThoughtGateResult + ContinuationPressureState + RetrievalRequest -> RetrievalQueryPlan + ThoughtWindowBundle` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit retrieval-input boundary

The retrieval owner must read one explicit normalized input surface rather than reach through memory or thought owners.

`RetrievalRequest` is expected to carry at least:

1. source gate-result id,
2. source continuation state,
3. current-cycle compact stimulus summaries,
4. optional `recall_intent`,
5. optional `selected_memory_refs`,
6. public tier targets and bound limits.

The retrieval owner must not:

1. read raw channel payloads,
2. inspect private memory storage internals,
3. inspect thought text or action proposals,
4. pull private state from planner, executor, or identity owners.

### 3.2 Lifecycle

1. `09` publishes one `ThoughtGateResult` and one current `ContinuationPressureState`.
2. Runtime provides one explicit `RetrievalRequest` for the current cycle, including compact stimuli and any formal prior-thought retrieval handoff when available.
3. Directed-retrieval owner validates gate-result, continuation, and retrieval-request invariants.
4. The owner builds one `PlanDirectedRetrievalOp` for orchestration visibility.
5. An owner-controlled retrieval path computes one `RetrievalQueryPlan` and one `ThoughtWindowBundle`.
6. The owner queries public memory-owner interfaces only.
7. The owner publishes one immutable `ThoughtWindowBundle` every valid fired-gate cycle.
8. The owner publishes selection trace and candidate-level SEC trace for the same cycle.
9. The later internal-thought owner consumes the published bundle without transferring retrieval ownership back into this slice.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `ThoughtGateResult`, `ContinuationPressureState`, and `RetrievalRequest`.
2. Tiered selection or reranking belongs to `10` rather than the memory owner.
3. Current-cycle short-term context is part of the formal thought-window bundle, but remains tiny and bounded.
4. Optional prior-thought `recall_intent` and selected-memory refs may be used, but only through an explicit retrieval-request handoff contract.
5. `10` publishes one formal query plan and one formal thought-window bundle every valid fired-gate cycle.
6. The retrieval bundle preserves per-tier selection trace and candidate-level selection evidence in the first version.
7. Deterministic first-version planning or SEC scoring may exist as an owner-private path, but does not become permanent architecture truth.

## 4. Data Structures

### 4.1 RetrievalRequest
- `request_id: str`
- `source_gate_result_id: str`
- `source_continuation_active: bool`
- `compact_stimuli: tuple[dict[str, object], ...]`
- `recall_intent: str`
- `selected_memory_refs: tuple[str, ...]`
- `target_tiers: tuple[str, ...]`
- `limit: int`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `10`,
2. prevent owner reach-through into memory and thought internals,
3. give the retrieval path one bounded demand surface per cycle.

### 4.2 RetrievalQueryPlan
- `plan_id: str`
- `source_request_id: str`
- `query_text: str`
- `query_source: str`
- `target_tiers: tuple[str, ...]`
- `limit: int`
- `retrieval_strategy: str`
- `tick_id: int | None`

Purpose:

1. make retrieval planning explicit and observable,
2. preserve query provenance before public memory search executes,
3. prevent hidden query building inside memory or thought owners.

### 4.3 ThoughtWindowHit
- `memory_id: str`
- `memory_type: str`
- `summary: str`
- `score: float`
- `source: str`
- `tags: tuple[str, ...]`

Purpose:

1. carry a bounded selected memory projection into the thought window,
2. avoid leaking full storage internals across the `10` public boundary,
3. preserve enough semantic detail for internal-thought consumption.

### 4.4 ThoughtWindowBundle
- `bundle_id: str`
- `source_plan_id: str`
- `short_term_context: tuple[ThoughtWindowHit, ...]`
- `mid_term_hits: tuple[ThoughtWindowHit, ...]`
- `long_term_hits: tuple[ThoughtWindowHit, ...]`
- `autobiographical_hits: tuple[ThoughtWindowHit, ...]`
- `selection_trace: tuple[RetrievalSelectionTrace, ...]`
- `retrieval_sec_trace: tuple[RetrievalSECTraceItem, ...]`
- `tick_id: int | None`

Purpose:

1. represent one immutable bounded thought-window retrieval bundle,
2. make per-tier retrieval outcomes explicit,
3. keep later internal-thought consumption within a controlled context surface.

### 4.5 RetrievalSelectionTrace
- `tier_name: str`
- `candidate_count: int`
- `selected_count: int`
- `query_source: str`

### 4.6 RetrievalSECTraceItem
- `candidate_id: str`
- `candidate_type: str`
- `score: float`
- `reason: str`
- `selected: bool`

### 4.7 PlanDirectedRetrievalOp
- `op_name: str`
- `owner: str`
- `request_id: str`
- `gate_result_id: str`
- `target_tier_count: int`

### 4.8 PublishThoughtWindowBundleOp
- `op_name: str`
- `owner: str`
- `bundle_id: str`
- `short_term_count: int`
- `mid_term_count: int`
- `long_term_count: int`
- `autobiographical_count: int`

## 5. Module Changes

1. `directed_retrieval/contracts.py` defines owner declaration, typed retrieval contracts, public API protocol, ops contracts, and retrieval-owner error type.
2. `directed_retrieval/engine.py` will implement the first owner skeleton for retrieval planning and bounded bundle publication.
3. `directed_retrieval/__init__.py` will export the public retrieval surface.
4. `runtime/stages.py` will add one `10` runtime stage result and one explicit runtime-owned retrieval-request provider contract.
5. `tests/test_directed_retrieval_contracts.py` will validate contract immutability, bounded bundle shape, and selection-trace preservation.
6. `tests/test_directed_retrieval_engine.py` will validate owner-skeleton behavior, fail-fast input handling, bounded tier outputs, and no-fallback behavior.
7. `tests/test_runtime_stage_chain.py` will validate the `09 -> 10` stage boundary and immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy memory-system-directed retrieval path directly.

It extracts only the query-planning, tier-selection, and thought-window bundle concepts first so the later internal-thought slice can attach to a stable `10` contract.

First-version migration direction:

1. preserve the existing legacy semantics that retrieval demand can depend on current stimuli, recall intent, and selected memory refs,
2. move tiered selection or reranking ownership out of the memory owner and into `10`,
3. preserve short-term context in the bundle but keep it explicitly tiny and bounded,
4. preserve structured selection trace and SEC trace as first-class public observability.

## 7. Failure Modes and Constraints

1. Missing gate-result provenance must raise an explicit retrieval-owner error.
2. Missing required retrieval-request fields must raise an explicit retrieval-owner error.
3. Publication must not occur for malformed query plans or malformed thought-window bundles.
4. No fallback retrieval-bundle path is allowed.
5. Missing required public memory capability must abort execution rather than substituting an unrestricted heuristic path.
6. Permanent query formulas, permanent tier-priority heuristics, and permanent SEC thresholds are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private retrieval path.
8. The thought-window bundle must be validated so that raw storage payloads cannot cross the `10` public boundary.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. retrieval plan preserves request provenance and query-source provenance,
2. thought-window bundle preserves per-tier selected-hit counts and bounded hit projections,
3. selection trace preserves candidate and selected counts for each queried tier,
4. retrieval SEC trace preserves candidate-level selection evidence for diagnostics,
5. error types define malformed retrieval-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable retrieval-request, query-plan, and thought-window-bundle contracts.
2. Unit test that bounded short-term context is preserved and remains tiny.
3. Unit test that optional selected-memory refs influence selection only through explicit retrieval-request input.
4. Unit test provenance preservation from `ThoughtGateResult` and `RetrievalRequest` into `RetrievalQueryPlan` and `ThoughtWindowBundle`.
5. Unit test explicit per-tier empty-selection visibility through selection trace.
6. Unit test that tiered selection belongs to `10` and does not require private memory-owner reach-through.
7. Unit test explicit failure for malformed gate result or malformed retrieval-request input.
8. Unit test explicit failure when required public memory capability is unavailable.
9. Unit test runtime-stage wiring from `09` into `10` through immutable frame inputs only.