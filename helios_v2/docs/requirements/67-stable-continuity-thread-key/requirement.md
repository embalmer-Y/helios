# Requirement 67 - Stable Continuity Thread Key

## 1. Background and Problem
The autonomy owner (`18`) produces deferred-continuity records when proactive activity cannot close externally. Each record carries a `continuity_key` that identifies which long-horizon continuity thread it belongs to. Threads are reinforced (age increases, strength grows) only when the same `continuity_key` recurs across ticks.

The current `_continuity_key` derivation embeds tick-specific `origin_ref` values (`source_thought_cycle_result_id` or `source_planner_bridge_result_id`):

```python
def _continuity_key(cls, origin_ref: str, carry_reason: str) -> str:
    return f"{origin_ref}:{cls._base_reason(carry_reason)}"
```

This produces keys like `thought-cycle-result:tick-1:insufficient_outward_readiness` and `thought-cycle-result:tick-3:insufficient_outward_readiness` — different keys for the same semantic motive ("not ready to act yet") on different ticks.

**Consequence:** Reinforcement works only when the carry-forward chain is unbroken (the carried record preserves the old key). When a deferred record expires (2-tick `expires_after_ticks`) and a later tick creates a new deferral for the same motive, the new key differs from all prior-thread keys, and the thread resets to age 1 with `reinforcement_count=0`. A motive that recurs every 3 ticks (e.g., tick 1, tick 4, tick 7) is never reinforced — it is treated as a fresh tendency each time.

This defeats the long-horizon subjective-continuity design intent of R24: threads should accumulate evidence of recurrence, not only of consecutive recurrence.

## 2. Goal
Make the `continuity_key` derivation stable across ticks so that the same deferral motive always maps to the same thread, enabling reinforcement regardless of whether the carry-forward chain was unbroken or interrupted by record expiry. A thread representing "insufficient outward readiness" persists and strengthens whenever that motive recurs, even across gaps.

## 3. Functional Requirements

### 3.1 Key Derivation
1. The `continuity_key` must be derived solely from the `carry_reason`, not from any tick-specific identifier such as `source_thought_cycle_result_id` or `source_planner_bridge_result_id`.
2. The key must be stable: two deferrals with the same `carry_reason` on different ticks must produce the same `continuity_key`.
3. The `origin_ref` field on `DeferredContinuityRecord` must continue to store the tick-specific provenance reference for audit and traceability; it must not be removed or conflated with the key.

### 3.2 Thread Reinforcement
1. When a deferred record with a stable key recurs on a later tick (either via carry-forward or as a newly created record after expiry), the corresponding `ContinuityThread` must be reinforced (age incremented, `reinforcement_count` incremented, `thread_strength` increased).
2. The existing decay, merge, and expiry semantics on `DeferredContinuityRecord` must remain unchanged.

### 3.3 Key Collision
1. Two deferrals with different `carry_reason` values (e.g., `blocked_outward_externalization` vs `insufficient_outward_readiness`) must produce different keys and separate threads.

## 4. Non-Functional Requirements
1. The key derivation must be O(1) — no new I/O, no lookup, no embedding computation.
2. All existing deferred-continuity tests and long-horizon-thread tests must continue to pass without modification to their pass/fail assertions.
3. No contract shape change: `DeferredContinuityRecord`, `ContinuityThread`, `LongHorizonContinuityState`, and `ProactiveDriveRequest` must not change their field set.

## 5. Code Behavior Constraints
1. The `_continuity_key` method must not accept or use `origin_ref` in its key derivation.
2. No other code path may construct a `continuity_key` value outside the `_continuity_key` classmethod.
3. The `origin_ref` field on `DeferredContinuityRecord` remains mandatory and non-empty for provenance.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/autonomy/engine.py` — `_continuity_key` method and its two call sites in `assemble_result`
2. `helios_v2/tests/test_runtime_composition.py` — add reinforcement-gap test (non-consecutive deferral proves reinforcement survives record expiry)
3. `helios_v2/tests/test_autonomy_engine.py` — update any unit test that asserts specific key string values

## 7. Acceptance Criteria
1. A new integration test runs 5 consecutive ticks with identical cognitive conditions (concluded + no-action) and asserts that the resulting `ContinuityThread` for `insufficient_outward_readiness` has `reinforcement_count >= 2`, proving the thread was reinforced across multiple ticks beyond the 2-tick record expiry.
2. A new integration test runs 4 ticks where ticks 1-2 produce a deferral, tick 3 does not (e.g., exploratory disposition), and tick 4 produces the same deferral; asserts that the tick-4 thread has `age_ticks >= 2` and `reinforcement_count >= 1`, proving reinforcement survives a carry-forward gap.
3. All existing 744+ tests continue to pass.
4. Two deferrals with different `carry_reason` values produce separate threads in the same tick (verified by existing multi-thread arbitration tests).
