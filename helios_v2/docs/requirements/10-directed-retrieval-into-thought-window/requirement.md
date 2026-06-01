# Requirement 10 - Directed retrieval into thought window

## 1. Background and Problem

After `09` publishes a formal gate result and continuation-pressure state, Helios v2 still lacks a dedicated owner that turns explicit thought-window demand into a bounded retrieval bundle for later internal thought. Without this owner, the internal-thought layer would either query memory directly and invent private retrieval policy, or the memory owner would silently absorb query planning, tiered reranking, and thought-window assembly into one mixed retrieval controller.

The current legacy implementation proves that directed retrieval is a real runtime concept rather than incidental prompt text. It already carries `RetrievalQueryPlan`, `DirectedMemoryBundle`, `RetrievalSelectionTrace`, and retrieval SEC trace semantics, but these responsibilities remain embedded inside the general memory system and then consumed ad hoc by thought generation. Helios v2 must separate directed retrieval into its own owner before the internal-thought owner is defined.

This slice corresponds to the transition from a fired thought gate into a bounded memory bundle for the thought window, not to gate ownership, internal thought generation, action externalization, planner routing, or identity-governance execution.

## 2. Goal

Create a directed-retrieval owner that consumes explicit retrieval demand after `09`, builds one retrieval query plan, selects bounded tiered memory hits through public memory-owner interfaces, assembles an immutable thought-window retrieval bundle, and exposes documented API and ops contracts without fallback behavior, private reach-through, or ownership collapse into memory storage, internal-thought generation, or downstream action modules.

## 3. Functional Requirements

### 3.1 Directed-retrieval owner boundary
1. The directed-retrieval layer must be the sole owner of retrieval-query planning, tiered selection or reranking, and final thought-window bundle assembly in this slice.
2. The owner must remain separate from memory persistence, memory-family storage mutation, thought gating, internal thought generation, action externalization, planner routing, and identity-governance ownership.
3. The owner must not reinterpret itself as the owner of memory write policy, thought rendering, or outward behavior selection.

### 3.2 Upstream input boundary
1. The directed-retrieval layer must accept `ThoughtGateResult` as a required upstream input contract.
2. The directed-retrieval layer must accept the current `ContinuationPressureState` as a required upstream carry input.
3. The directed-retrieval layer must accept current-cycle compact stimulus summaries through an explicit retrieval-input contract rather than reading raw stimulus payloads or channel internals directly.
4. The directed-retrieval layer may accept an explicit optional retrieval-request handoff carrying `recall_intent` and selected memory refs from prior thought activity, but only through a documented public contract.
5. The owner must obtain memory candidates only through documented public memory-owner interfaces rather than private reach-through into memory storage internals.
6. The owner must not require direct imports into internal-thought, planner, executor, or identity-governance owners in this slice.

### 3.3 Retrieval-plan ownership
1. The first public output of this slice must include a formal retrieval-query plan rather than leaving query construction implicit inside memory or thought owners.
2. The retrieval-query plan must preserve the upstream trigger basis used to build the query, including compact stimulus-derived text, recall intent, and tier targets.
3. The retrieval owner must decide which public memory tiers are queried in the current cycle.
4. The retrieval owner must decide how candidate hits are selected into the thought window from each queried tier.
5. The retrieval owner must not delegate tiered selection or reranking policy implicitly back into the memory owner under the name of a generic search call.

### 3.4 Thought-window bundle output
1. The first public output of this slice must be a bounded thought-window retrieval bundle rather than raw unbounded search hits.
2. The bundle must support at least bounded short-term context, bounded mid-term hits, bounded long-term hits, and bounded autobiographical hits in the first version.
3. Short-term context may be included in the bundle, but it must remain tiny and explicitly bounded.
4. The bundle must preserve selection trace and retrieval SEC trace or equivalent first-version selection observability.
5. The bundle must not expose full storage internals or unlimited raw payload transfer into the thought window.
6. If no retrieval candidate is selected from a tier, the bundle must publish that outcome explicitly through trace fields rather than silently omitting tier visibility.

### 3.5 Separation from later owners
1. The directed-retrieval owner may assemble the thought-window memory bundle, but it must not generate internal thought text in this slice.
2. The directed-retrieval owner must not decide whether the thought window fires; that remains with `09`.
3. The directed-retrieval owner must not normalize final external action proposals in this slice.
4. The directed-retrieval owner must not write identity revisions or planner-facing behavior proposals in this slice.
5. The directed-retrieval owner must not call planner, executor, channel, or identity-governance owners directly as part of retrieval.

### 3.6 Learned or runtime-provided retrieval semantics
1. The owner must not hardcode permanent query-construction formulas, tier-priority formulas, or permanent reranking thresholds into the architecture contract.
2. Retrieval planning policy, tier-selection policy, selection or reranking policy, and bounded thought-window shaping policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty-bundle defaults, and explicit owner-controlled bootstrap metadata.
4. If the first-version implementation uses deterministic selection or SEC scoring, that path must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic retrieval semantics must remain learning-driven rather than frozen into architecture defaults.

### 3.7 No fallback behavior
1. The directed-retrieval layer must not synthesize a fallback thought-window bundle when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic retrieval path when the configured directed-retrieval capability is unavailable.
3. The owner must fail explicitly when required retrieval-input invariants or required public memory capability are missing.
4. The owner must not silently treat missing selected-memory refs, missing recall intent, or empty query text as permission to bypass explicit retrieval-plan publication.
5. The owner must not silently expand into unrestricted full-memory prompt stuffing when bounded tiered retrieval fails.

## 4. Non-Functional Requirements

1. Retrieval-plan, retrieval-bundle, and publication contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured retrieval policy.
3. The owner boundary must remain separate from memory storage mutation, thought generation, action-externalization, planning, execution, and identity-governance owners.
4. Published state must preserve enough provenance and selection detail to support later diagnostics of why specific memory hits entered or did not enter the thought window.
5. The thought-window retrieval bundle must remain bounded and must not become an unrestricted long-history replay surface.

## 5. Code Behavior Constraints

1. Directed-retrieval code must not import planner, executor, channel, or identity-governance owners directly.
2. Directed-retrieval code must use only documented public memory-owner interfaces across module boundaries.
3. Directed-retrieval code must expose only documented APIs and ops contracts across module boundaries.
4. Directed-retrieval code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
5. Directed-retrieval code must not blur owner boundaries by taking ownership of thought-window firing, thought rendering, action proposal normalization, or memory persistence.
6. The thought-window bundle must not carry unlimited raw storage payloads across the `10` public boundary.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/directed_retrieval/contracts.py`
2. `helios_v2/src/helios_v2/directed_retrieval/engine.py`
3. `helios_v2/src/helios_v2/directed_retrieval/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_directed_retrieval_contracts.py`
6. `helios_v2/tests/test_directed_retrieval_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from `ThoughtGateResult + ContinuationPressureState + explicit retrieval input` into a formal retrieval-query plan and bounded thought-window retrieval bundle.
2. The package defines documented ops contracts for retrieval planning request, retrieval-bundle publication, and retrieval-selection observability publication.
3. The contract surface publishes one formal retrieval plan and one bounded retrieval bundle every valid fired-gate cycle.
4. The contract surface publishes bounded short-term, mid-term, long-term, and autobiographical thought-window retrieval outputs without collapsing back into raw search results.
5. The package records that tiered selection or reranking belongs to `10` rather than remaining hidden inside the memory owner.
6. The package records that optional prior-thought `recall_intent` and selected-memory refs enter only through an explicit retrieval-request handoff contract.
7. The package does not claim gate, internal-thought generation, action-externalization, planner, executor, or identity-governance ownership.
8. No test or implementation path demonstrates fallback retrieval bundling, degraded unrestricted prompt stuffing, or private reach-through into memory storage internals.