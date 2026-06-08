# Requirement 68 - Identity Cross-Tick Governance Carry State

## 1. Background and Problem
The identity governance owner (`14`) is completely stateless across ticks. The composition bridge (`FirstVersionIdentityGovernanceRequestBridge`) hardcodes the same `identity_state_snapshot`, an empty `governance_trace_summary`, and an empty `recent_governance_trace_history` on every tick:

```python
identity_state_snapshot={
    "self_definition": "runtime identity definition",
    "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
    "identity_metadata": {},
    "current_revision": "bootstrap",
    "revision_history_length": 0,
},
governance_trace_summary={},
recent_governance_trace_history=(),
```

This means:
1. An accepted self-revision on tick N is invisible to tick N+1 — the identity state resets to the hardcoded bootstrap snapshot.
2. `GovernancePressureState` is always `pressure_level="none"` because `recent_governance_trace_history` is always empty, making the entire proactive-governance backpressure system dormant.
3. `revision_history_length` never increments across ticks — every tick sees `0`.

This violates the wave_B design intent of a "persistent self": an identity that evolves and remembers its own revisions.

## 2. Goal
Give the identity governance owner a real cross-tick carry state so that accepted self-revisions persist into subsequent ticks, governance trace accumulates, and the pressure system can detect patterns and apply backpressure. The identity state becomes a genuine evolving artifact rather than a per-tick constant.

## 3. Functional Requirements

### 3.1 Cross-Tick Identity State Carry
1. When a tick produces an `AppliedIdentityState` (accepted revision), the resulting `identity_state_snapshot` must be carried forward and supplied to the next tick's governance request.
2. When a tick does NOT produce an applied state (rejected/invalid/no-proposal), the prior carried identity state must be preserved unchanged for the next tick.
3. On the first tick (cold start), the identity state must use the current bootstrap snapshot (backward-compatible default).

### 3.2 Governance Trace Accumulation
1. Each tick's governance result (pressure level, revision status, tick id) must be accumulated into a bounded `recent_governance_trace_history` supplied to the next tick's request.
2. The trace history must be bounded (capped at a fixed window, e.g., 10 entries) to prevent unbounded growth.
3. A `governance_trace_summary` must be derived from the trace history (at minimum: count of recent entries, count of accepted revisions, count of rejected revisions).

### 3.3 Owner-Neutral Composition Boundary
1. Composition must only inject the prior carry state into the request; it must not interpret, score, or apply policy to the carry data.
2. The identity state snapshot and trace history remain composition-owned transport; the governance policy (how to use them) stays in the `14` owner.

### 3.4 Owner-Owned Carry Contract
1. A new `GovernanceCarryState` frozen dataclass must be defined in the `14` owner's contracts module, encapsulating the identity state snapshot and bounded trace history.
2. The runtime stage must hold and update this carry state; the composition bridge must read it through an owner-neutral seam.

## 4. Non-Functional Requirements
1. The carry state update must be O(1) per tick — no new I/O, no database lookup.
2. The trace history window must be bounded (configurable, default 10) to prevent memory growth.
3. All existing identity governance tests must continue to pass without modification.
4. The cold-start behavior (no prior carry state) must be byte-for-byte identical to the current behavior.

## 5. Code Behavior Constraints
1. No cognitive policy may live in composition — composition forwards raw prior state only.
2. The `GovernanceCarryState` must be immutable (frozen dataclass).
3. The identity state snapshot carried forward must be the exact snapshot published by the prior tick's `AppliedIdentityState` (not a re-derived or re-interpreted version).
4. The `_prior_governance_result` field on the runtime stage must not be accessible to other stages or owners.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/identity_governance/contracts.py` — add `GovernanceCarryState` dataclass
2. `helios_v2/src/helios_v2/identity_governance/engine.py` — consume carry state in `_build_pressure_state` and `_evaluate_proposal`
3. `helios_v2/src/helios_v2/runtime/stages.py` — add `_prior_carry_state` to `IdentityGovernanceRuntimeStage`
4. `helios_v2/src/helios_v2/composition/bridges.py` — inject carry state into request
5. `helios_v2/tests/test_identity_governance.py` — add cross-tick carry tests
6. `helios_v2/tests/test_runtime_composition.py` — add integration test for identity state evolution

## 7. Acceptance Criteria
1. A unit test constructs a governance request with a non-bootstrap `identity_state_snapshot` (simulating a prior accepted revision) and verifies the governance result preserves the carried state when no new revision is applied.
2. An integration test runs 3 ticks where tick 1 produces no proposal, tick 2 produces an accepted self-revision, and tick 3 produces no proposal; asserts tick 3's identity state reflects the tick-2 revision.
3. An integration test runs 5+ ticks with governance activity and asserts that `recent_governance_trace_history` grows (bounded) across ticks.
4. The cold-start test (first tick, no prior carry) produces byte-for-byte identical results to the current behavior.
5. All existing 755+ tests continue to pass.
