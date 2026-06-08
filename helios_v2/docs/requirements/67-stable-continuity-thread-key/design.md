# Requirement 67 - Stable Continuity Thread Key: Design

## 1. Title
Design: Stable Continuity Thread Key for Long-Horizon Thread Reinforcement

## 2. Design Overview
The fix targets a single method — `FirstVersionAutonomyPath._continuity_key` — and its two call sites. The key derivation drops the tick-specific `origin_ref` parameter and derives the key solely from the `carry_reason` via the existing `_base_reason` stripping helper. All other record/thread/carry/merge/expiry logic is unchanged.

## 3. Current State and Gap
**Current key derivation:**
```python
@classmethod
def _continuity_key(cls, origin_ref: str, carry_reason: str) -> str:
    return f"{origin_ref}:{cls._base_reason(carry_reason)}"
```

**Call sites in `assemble_result`:**
1. Blocked-outward path: `_continuity_key(request.source_planner_bridge_result_id, "blocked_outward_externalization")`
2. Carry-forward path: `_continuity_key(request.source_thought_cycle_result_id, "insufficient_outward_readiness")`

Both `source_*_result_id` values embed the tick id, making the key tick-specific.

**Carry-forward preserves old keys** (line 314: `continuity_key=record.continuity_key`), so consecutive ticks reinforce. But when the original record expires (2-tick `expires_after_ticks`) and a fresh record is created on a later tick, the fresh key differs from the expired thread's key, breaking reinforcement.

## 4. Target Architecture
**Target key derivation:**
```python
@classmethod
def _continuity_key(cls, carry_reason: str) -> str:
    return cls._base_reason(carry_reason)
```

The key is the bare carry reason string (e.g., `"insufficient_outward_readiness"` or `"blocked_outward_externalization"`), stable across all ticks.

**Call sites updated:**
1. Blocked-outward: `self._continuity_key("blocked_outward_externalization")`
2. Carry-forward: `self._continuity_key("insufficient_outward_readiness")`

The `origin_ref` parameter is removed from `_continuity_key` but continues to be passed separately to `_build_deferred_record` for provenance.

## 5. Data Structures
No new data structures. No field additions or removals on existing contracts:

- `DeferredContinuityRecord`: unchanged (continuity_key, origin_ref, record_id, carry_reason, carry_count, decayed_pressure, expires_after_ticks)
- `ContinuityThread`: unchanged
- `LongHorizonContinuityState`: unchanged
- `ProactiveDriveRequest`: unchanged

## 6. Module Changes

### 6.1 `helios_v2/src/helios_v2/autonomy/engine.py`
- `_continuity_key` signature: drop `origin_ref` parameter, return `cls._base_reason(carry_reason)`
- Two call sites in `assemble_result` (lines ~486, ~520): drop the `origin_ref` argument
- `_build_deferred_record` call sites: unchanged (still pass `origin_ref` separately)
- `_carry_forward_records`: unchanged (already uses `record.continuity_key`)
- `_merge_active_records`: unchanged (already groups by `continuity_key`)
- `_build_long_horizon_state`: unchanged (already matches prior threads by `continuity_key`)

### 6.2 `helios_v2/tests/test_autonomy_engine.py`
- Check for any unit test that asserts specific continuity-key string patterns containing tick-specific ids; update to match the stable key format.

### 6.3 `helios_v2/tests/test_runtime_composition.py`
- Add `test_consecutive_deferring_ticks_reinforce_single_thread`: 5 ticks, assert `reinforcement_count >= 2`
- Add `test_reinforcement_survives_carry_forward_gap`: 4 ticks with a gap at tick 3, assert thread reinforces on tick 4

## 7. Migration Plan
This is a behavior-preserving key-scheme change for the in-memory thread layer. No persisted state migration is required because:

1. `DeferredContinuityRecord` is in-memory only (not persisted to disk between ticks except via the `42` checkpoint).
2. `ContinuityThread` is in-memory only.
3. The `42` checkpoint stores these as opaque tuples; the key string is read back as-is and used only for matching, so an in-flight checkpoint from the old key scheme would produce one last tick of non-matching keys (the old thread would retire, the new stable-key thread would form fresh). This is acceptable: a one-tick thread reset on upgrade, not a data corruption.

**Rollout:** default-on (not opt-in). The key scheme is an internal implementation detail of the `18` owner; there is no assembly-level toggle.

## 8. Failure Modes and Constraints
1. **No failure mode introduced**: the key derivation is a pure string function; it cannot fail.
2. **Thread explosion risk**: with stable keys, the number of distinct threads per tick is bounded by the number of distinct `carry_reason` values (currently 2: `insufficient_outward_readiness` and `blocked_outward_externalization`). This is strictly fewer threads than before (where each tick could add one).
3. **Key collision between motives**: not applicable — each motive currently maps to exactly one carry_reason. If future requirements add new carry reasons, they naturally produce distinct keys.

## 9. Observability and Logging
No new logging mechanism. The existing `LongHorizonContinuityState.threads` tuple, published via `AutonomyResult.long_horizon_state`, exposes each thread's `continuity_key`, `age_ticks`, `reinforcement_count`, and `thread_strength`. The stable key makes these fields more meaningful (they now accumulate across the full lifetime of a recurring motive, not just consecutive windows).

## 10. Validation Strategy
1. **Unit test**: call `_continuity_key("insufficient_outward_readiness")` from two different mock requests with different `origin_ref` values and assert identical key output.
2. **Integration test (consecutive)**: run 5 ticks with concluded+no-action; assert single thread with `reinforcement_count >= 2`, `age_ticks >= 3`.
3. **Integration test (gap)**: run 4 ticks where tick 3 breaks the carry chain; assert tick 4 reinforces the original thread (not a fresh one).
4. **Regression**: full test suite (744+) passes.
