# Requirement 09 - Thought gating and continuation pressure

## 1. Background and Problem

After `08` publishes one formal `ConsciousState` per valid cycle, Helios v2 still lacks a dedicated owner that decides whether the internal thought window should open in the current cycle and whether unfinished thought pressure should carry into later cycles. Without this owner, later modules would either read `ConsciousState` directly and invent private trigger logic, or the internal-thought owner would silently absorb gate policy, continuation carry, and trigger observability into one mixed controller.

The current legacy implementation proves that thought gating and continuation pressure are real runtime concepts rather than incidental metadata. It already records `ThoughtGateResult`, selected trigger stimuli, and a multi-tick `ContinuationPressureState`, but these semantics remain mixed inside a broader thought-generation path. Helios v2 must separate the gate owner from retrieval, thought generation, action proposal, and identity revision before those later slices are implemented.

This slice corresponds to the transition from reportable conscious content into a formal `should_fire` versus `no_fire` thought-window decision plus explicit continuation carry, not to directed retrieval, internal thought generation, action externalization, planner routing, or identity-governance execution.

## 2. Goal

Create a thought-gating owner that consumes explicit current-cycle gate inputs after `08`, decides whether the thought window should fire in the current cycle, publishes an immutable gate result plus compact trigger observability, and owns the formal multi-tick continuation-pressure state without hardcoded architecture truth, fallback behavior, or ownership collapse into retrieval, internal-thought generation, or downstream action modules.

## 3. Functional Requirements

### 3.1 Thought-gating owner boundary
1. The thought-gating layer must be the sole owner of current-cycle thought-window firing decisions and continuation-pressure publication in this slice.
2. The owner must remain separate from directed retrieval, internal thought generation, thought-type selection, action externalization, planner routing, executor dispatch, and identity-governance ownership.
3. The owner must not reinterpret itself as the owner of retrieval-content assembly, thought rendering, or outward behavior selection.

### 3.2 Upstream input boundary
1. The thought-gating layer must accept `ConsciousState` as a required upstream input contract.
2. The thought-gating layer must accept the prior-cycle `ContinuationPressureState` as a required upstream carry input.
3. The thought-gating layer must accept current-cycle stimulus summaries as an explicit upstream contract rather than reading source-channel payloads or downstream routing state directly.
4. The thought-gating layer must accept runtime-normalized gate signals for at least workload pressure, ICRI or equivalent global activation level, temporal dynamics, drive urgency, and DMN-availability state through an explicit gate-input contract.
5. The thought-gating layer must not require direct imports into retrieval-owner internals, internal-thought owner internals, channel owners, or identity owners in this slice.
6. The owner must not reach through arbitrary upstream state fields when the same information can be carried through one explicit gate-input contract.

### 3.3 Gate decision output
1. The first public output of this slice must be a formal per-cycle gate result rather than an implicit boolean hidden inside later owner state.
2. Every valid cycle in this slice must publish one formal gate result, including cycles where the thought window does not fire.
3. The gate result must explicitly record whether the owner decided `fire` or `no_fire` for the current cycle.
4. If the gate result is `no_fire`, the owner must publish an explicit no-fire reason rather than silently omitting a gate record.
5. The gate result must preserve the dominant trigger reason, blocked reasons, and normalized contributing signals needed for later diagnostics.
6. The gate result may include a compact selected-stimulus summary, but it must not publish full raw upstream payloads in this slice.

### 3.4 Continuation-pressure ownership
1. The thought-gating layer must be the sole owner of formal continuation-pressure carry across cycles in this slice.
2. The continuation-pressure contract must preserve at least active state, pressure level, origin thought id, carry reason, expiry boundary, and carry count.
3. The thought-gating owner must be able to publish continuation pressure for both `fire` and `no_fire` cycles.
4. The thought-gating owner must be able to decay or clear prior continuation pressure explicitly when the configured carry policy no longer sustains it.
5. The thought-gating owner must not infer new continuation pressure from retrieval output, thought text, or planner feedback in this slice.
6. The owner may preserve a compact downstream-facing carry reason taxonomy, but it must not collapse continuation pressure into an unstructured float alone.

### 3.5 Separation from later owners
1. The thought-gating owner may decide whether the thought window should open, but it must not select a thought type in this slice.
2. Thought-type cooldown ownership must remain outside `09` and be handled by the later internal-thought owner rather than by the gate owner.
3. The thought-gating owner must not perform directed retrieval into the thought window in this slice.
4. The thought-gating owner must not generate internal thought text, structured thought decisions, external action proposals, or self-revision proposals in this slice.
5. The thought-gating owner must not call planner, executor, channel, or identity-governance owners directly as part of gate evaluation.

### 3.6 Learned or runtime-provided gate semantics
1. The owner must not hardcode permanent trigger formulas, fixed threshold heuristics, or permanent continuation policies into the architecture contract.
2. Gate scoring policy, no-fire policy, continuation decay policy, and compact trigger-selection policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are legal bounds, explicit empty continuation defaults, and explicit owner-controlled bootstrap metadata.
4. If the first-version implementation uses a deterministic score composition, that composition must remain an owner-private implementation note rather than permanent architecture truth.
5. Dynamic gate semantics and continuation semantics must remain learning-driven rather than frozen into architecture defaults.

### 3.7 No fallback behavior
1. The thought-gating layer must not synthesize a fallback fire decision when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic trigger path when the configured gate capability is unavailable.
3. The owner must fail explicitly when required gate-input invariants or required continuation capability are missing.
4. The owner must not silently treat missing contributing signals as permission to bypass explicit gate-input validation.
5. The owner must not silently drop malformed continuation state and continue as if no carry existed unless the configured owner policy explicitly clears it through a valid gate cycle.

## 4. Non-Functional Requirements

1. Gate-result and continuation-pressure contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured gate policy.
3. The owner boundary must remain separate from retrieval, internal-thought generation, action-externalization, planning, execution, and identity-governance owners.
4. Published state must preserve enough provenance and signal detail to support later diagnostics of why the thought window fired or remained closed.
5. Compact selected-stimulus observability must remain bounded and must not expose raw payload growth across module boundaries.

## 5. Code Behavior Constraints

1. Thought-gating code must not import retrieval, planner, executor, channel, or identity-governance owners directly.
2. Thought-gating code must expose only documented APIs and ops contracts across module boundaries.
3. Thought-gating code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Thought-gating code must not blur owner boundaries by taking ownership of thought-type cooldown, retrieval-window population, thought rendering, or action proposal normalization.
5. Compact selected-stimulus observability must not carry full upstream payload dictionaries across the `09` public boundary.
6. Retrieval-window construction, thought generation, and planner/executor integration remain outside this owner.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/thought_gating/contracts.py`
2. `helios_v2/src/helios_v2/thought_gating/engine.py`
3. `helios_v2/src/helios_v2/thought_gating/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/tests/test_thought_gating_contracts.py`
6. `helios_v2/tests/test_thought_gating_engine.py`
7. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from `ConsciousState + prior ContinuationPressureState + explicit gate inputs` into a formal thought-gate result.
2. The package defines documented ops contracts for gate evaluation request, gate-result publication, and continuation-pressure publication.
3. The contract surface publishes one formal gate result every valid cycle, including explicit `no_fire` cycles.
4. The contract surface publishes continuation pressure as a structured contract containing level, reason, origin thought id, expiry boundary, and carry count rather than a float alone.
5. The package records that thought-type cooldown remains outside `09` and belongs to the later internal-thought owner.
6. The package records that selected-stimulus observability is compact and does not expose full raw stimulus payloads.
7. The package does not claim retrieval, internal-thought generation, action-externalization, planner, executor, or identity-governance ownership.
8. No test or implementation path demonstrates fallback thought firing, degraded heuristic substitution, or silent continuation-state loss.