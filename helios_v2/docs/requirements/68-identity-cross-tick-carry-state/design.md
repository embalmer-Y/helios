# Requirement 68 - Identity Cross-Tick Governance Carry State: Design

## 1. Title
Design: Identity Cross-Tick Governance Carry State

## 2. Design Overview
Introduce a `GovernanceCarryState` frozen dataclass in the `14` owner's contracts, giving the identity governance owner a first-class cross-tick state container. The runtime stage (`IdentityGovernanceRuntimeStage`) holds and advances this state post-tick. The composition bridge reads it through an owner-neutral seam and injects it into the next request. The owner engine consumes it to produce richer governance decisions and pressure assessments.

## 3. Current State and Gap
- `IdentityGovernanceRuntimeStage` has zero cross-tick state fields.
- `FirstVersionIdentityGovernanceRequestBridge.build_request()` hardcodes `identity_state_snapshot` to a bootstrap constant, `governance_trace_summary={}`, and `recent_governance_trace_history=()`.
- `FirstVersionIdentityGovernancePath._build_pressure_state()` computes pressure from trace history — always empty → always `pressure_level="none"`.
- `_evaluate_proposal()` reads `identity_state_snapshot` from the request — always the bootstrap constant → revisions are applied to a throwaway copy every tick.

## 4. Target Architecture

### 4.1 New Contract: `GovernanceCarryState`
A frozen dataclass in `identity_governance/contracts.py`:

```python
@dataclass(frozen=True)
class GovernanceCarryState:
    identity_state_snapshot: Mapping[str, object]
    recent_governance_trace_history: tuple[Mapping[str, object], ...]
    accepted_revision_count: int
    rejected_revision_count: int
```

Validation in `__post_init__`:
- `accepted_revision_count >= 0`
- `rejected_revision_count >= 0`
- `recent_governance_trace_history` entries have no empty keys

### 4.2 Runtime Stage: Carry and Advance
`IdentityGovernanceRuntimeStage` gains two private mutable fields:
- `_prior_carry_state: GovernanceCarryState | None` (initially `None` for cold start)
- Post-tick: after evaluating governance, compute the next carry state:
  - If `applied_identity_state` is not `None`, carry its `identity_state_snapshot`
  - Otherwise, carry the prior `identity_state_snapshot` (or bootstrap on cold start)
  - Append a trace entry `{pressure_level, revision_status, tick_id}` to the bounded history

### 4.3 Composition Bridge: Owner-Neutral Injection
`FirstVersionIdentityGovernanceRequestBridge` gains an optional `carry_state: GovernanceCarryState | None` parameter:
- When `carry_state` is not `None`: use `carry_state.identity_state_snapshot` and `carry_state.recent_governance_trace_history`; derive a `governance_trace_summary` from the history (count-based).
- When `carry_state` is `None`: use the current bootstrap constant (backward-compatible cold start).

### 4.4 Owner Engine: Consume Carry
`FirstVersionIdentityGovernancePath`:
- `_build_pressure_state()`: unchanged logic (already reads `recent_governance_trace_history`) — now receives non-empty history when governance has been active.
- `_evaluate_proposal()`: unchanged logic (already reads `identity_state_snapshot` from request) — now receives the evolved snapshot when revisions have been applied.

## 5. Data Structures

### GovernanceCarryState (new)
```
GovernanceCarryState:
    identity_state_snapshot: Mapping[str, object]  # evolved identity dict
    recent_governance_trace_history: tuple[Mapping[str, object], ...]  # bounded trace
    accepted_revision_count: int
    rejected_revision_count: int
```

Trace entry format (added each tick):
```python
{
    "pressure_level": str,          # from GovernancePressureState.pressure_level
    "revision_status": str,         # from RevisionDecision.status
    "tick_id": int | None,
}
```

## 6. Module Changes

### 6.1 `identity_governance/contracts.py`
- Add `GovernanceCarryState` frozen dataclass with `__post_init__` validation.

### 6.2 `identity_governance/engine.py`
- No engine change required. The owner already reads `identity_state_snapshot` and `recent_governance_trace_history` from the request; the carry state flows through the request.

### 6.3 `runtime/stages.py`
- `IdentityGovernanceRuntimeStage`: add `_prior_carry_state: GovernanceCarryState | None` field (default `None`), add `seed_prior_carry_state(state)` method.
- Post-evaluation in `run()`: build next carry state from result + prior.

### 6.4 `composition/bridges.py`
- `FirstVersionIdentityGovernanceRequestBridge`: add optional `carry_state` attribute.
- `build_request()`: when carry state present, use its snapshot and trace history.

### 6.5 `composition/runtime_assembly.py`
- Wire `carry_state` from the runtime stage into the bridge during assembly.

## 7. Migration Plan
- Cold start (`carry_state=None`): the bridge uses the current bootstrap constant → byte-for-byte identical to current behavior.
- The carry state is purely in-memory; no persistence migration needed.
- The `42` checkpoint integration is out of scope for R68 (future requirement).

**Rollout:** default-on. Every assembled runtime gains cross-tick identity carry.

## 8. Failure Modes and Constraints
1. **No failure mode introduced**: the carry state is a pure data container; `None` falls back to current behavior.
2. **Identity state grows unbounded**: mitigated by the trace history window cap (10 entries). The `identity_state_snapshot` dict size is bounded by the governance revision types (currently 3: self_definition, personality_baseline, identity_metadata).
3. **Composition reads owner state**: mitigated by the owner-neutral contract — composition reads the published `GovernanceCarryState` (an owner-exported type) without interpreting its contents.

## 9. Observability and Logging
No new logging mechanism. The `GovernancePressureState` now produces non-trivial `pressure_score` and `pressure_level` values when trace history accumulates — visible through the existing `IdentityGovernanceStageResult` and evaluation pipeline.

## 10. Validation Strategy
1. **Unit test**: construct `GovernanceCarryState` with a non-bootstrap identity snapshot; verify governance preserves it.
2. **Integration test (revision persistence)**: 3 ticks — tick 2 applies a revision; tick 3 sees the evolved identity state.
3. **Integration test (trace accumulation)**: 5+ ticks; verify trace history grows.
4. **Cold-start test**: first tick with no carry state → byte-for-byte identical to current.
5. **Regression**: full test suite passes.
