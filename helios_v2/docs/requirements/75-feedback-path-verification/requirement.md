# Requirement 75 - Feedback Path Verification

## 1. Background and Problem

The Helios v2 cognitive chain is a 19-stage pipeline (`02`–`24`) with feedback loops:
gate fire → thought → action → planner → writeback → autonomy → next tick's drive urgency.
R54 established the no-fire closure path, R62 grounded gate drive urgency in real `18`
carry, and R70 connected the prompt bridges to real owner state.

However, no single test module validates the end-to-end feedback paths: that gate
decisions propagate through the full chain and back, that writeback feeds memory
which feeds retrieval, that `04`→`05`→`07`→`09` causal chains hold, and that
checkpoint save/restore preserves continuity state across restarts.

## 2. Goal

Provide a read-only verification module that validates the five critical feedback
paths in the cognitive chain, ensuring that upstream owner state causally influences
downstream behavior and that cross-tick carry mechanisms function correctly.

## 3. Functional Requirements

### 3.1 FP-1: Fire path autonomy carry

1. A test must verify that when `09` gate fires, the `18` autonomy carry propagates
   `drive_urgency` to the next tick's gate signal across ≥ 3 consecutive ticks.

### 3.2 FP-2: No-fire closure continuation

1. A test must verify that when `09` gate does not fire (high load via pressure
   sampler), stages `18` and `17` still execute and `continuation_state` carries
   forward.

### 3.3 FP-3: Writeback to memory to retrieval

1. A test must verify that `15` experience writeback writes records to `06` memory
   store, and that subsequent `10` directed retrieval reads them back. Validated
   over ≥ 5 ticks with store count ≥ 5.

### 3.4 FP-4: Neuromodulator-feeling-workspace-gate causal chain

1. A test must verify the `04`→`05`→`07`→`09` causal chain: dopamine and valence
   evolve across ticks, demonstrating that neuromodulator changes propagate through
   feeling to workspace competition to gate decisions.

### 3.5 FP-5: Checkpoint round-trip

1. A test must verify that `ContinuityCheckpointStore` v3 save → new handle → restore
   preserves `thought_gating` continuation state and `autonomy` carry state.

### 3.6 Composite verdict

1. Aggregate all feedback path checks into a single verdict.

## 4. Non-Functional Requirements

1. **Offline**: all tests run without network access.
2. **Read-only**: no owner code modification.
3. **Tick-based**: validation uses multi-tick runs, not direct owner calls.

## 5. Code Behavior Constraints

1. Tests must use `assemble_runtime()` and `handle.run_ticks()`.
2. High-load scenarios use `_HighPressureSampler` (real `RuntimePressureSample`),
   not mock objects.
3. Checkpoint tests use `ContinuityCheckpointStore` API only.

## 6. Impacted Modules

1. `helios_v2/tests/test_feedback_path_verification.py` — new verification module.
2. `helios_v2/docs/requirements/index.md` — new R75 row.

## 7. Acceptance Criteria

1. `pytest helios_v2/tests/test_feedback_path_verification.py -v` passes all 6 tests.
2. Composite verdict covers FP-1 through FP-5.
3. Full suite still passes.
