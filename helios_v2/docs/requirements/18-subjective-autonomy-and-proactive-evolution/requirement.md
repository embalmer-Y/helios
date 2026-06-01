# Requirement 18 - Subjective autonomy and proactive evolution

## 1. Background and Problem

Even with thought, action, governance, writeback, and prompt assembly owners specified, Helios v2 still needs one owner for how internal pressure becomes sustained self-directed activity across ticks. The final project goal is not satisfied by passive reaction plus isolated thought bursts. It requires a runtime that can preserve unresolved internal tendency, choose between reflection and outward action, and evolve through controlled proactive behavior.

## 2. Goal

Create an autonomy owner that integrates proactive drive, continuation pressure, unresolved tendencies, and continuity feedback into multi-tick self-directed activity, while still routing any externalization through the formal planner/channel/governance path.

## 3. Functional Requirements

### 3.1 Owner boundary
1. `18` must be the sole owner of proactive-drive integration and multi-tick self-directed continuity in v2.
2. `18` must remain separate from prompt assembly, planner authority, channel ownership, and governance judgment.

### 3.2 Proactive-drive integration
1. `18` must integrate internal pressure, continuation carry, memory pull, temporal pressure, and identity-relevant unresolved state into one formal proactive-drive surface.
2. The owner must support at least reflective, exploratory, outward, and deferential dispositions.
3. The owner must allow self-directed thought in weak-input or no-input windows.

### 3.3 Controlled proactive externalization
1. When proactive pressure warrants outward action, `18` may request formal externalization through the existing action path.
2. `18` must not directly trigger channel output.
3. When outward action is blocked, the owner must preserve deferred continuity rather than dropping it silently.

### 3.4 Self-evolution continuity
1. `18` must preserve continuity of unresolved intentions and partially blocked tendencies across ticks.
2. The owner must collaborate with `15` and `14` rather than bypassing continuity writeback or governance.

### 3.5 Observability
1. The owner must publish structured proactive-drive snapshots and deferred-continuity states.
2. The owner must distinguish outward proactive activity from inward reflective activity.

### 3.6 No fallback behavior
1. Missing required continuity inputs must fail explicitly.
2. `18` must not fake proactive behavior with timer-only text emission.

## 4. Non-Functional Requirements

1. Proactive behavior must remain auditable and deterministic for identical state and policy.
2. The owner boundary must remain separate from planner/channel/governance owners.

## 5. Code Behavior Constraints
1. `18` must not bypass planner/channel ops.
2. `18` must not let blocked proactive tendencies vanish without trace.
3. `18` must not equate any single scalar with guaranteed outward action.

## 6. Impacted Modules
1. `helios_v2/src/helios_v2/autonomy/contracts.py`
2. `helios_v2/src/helios_v2/autonomy/engine.py`
3. `helios_v2/src/helios_v2/autonomy/__init__.py`
4. `helios_v2/src/helios_v2/runtime/stages.py`
5. `helios_v2/src/helios_v2/runtime/__init__.py`
6. `helios_v2/src/helios_v2/evaluation/contracts.py`
7. `helios_v2/src/helios_v2/evaluation/engine.py`
8. `helios_v2/src/helios_v2/__init__.py`
9. `helios_v2/tests/test_autonomy_contracts.py`
10. `helios_v2/tests/test_autonomy_engine.py`
11. `helios_v2/tests/test_evaluation_contracts.py`
12. `helios_v2/tests/test_evaluation_engine.py`
13. `helios_v2/tests/test_runtime_stage_chain.py`

## 7. Acceptance Criteria
1. The package defines a documented API for proactive-drive integration and continuity carry.
2. Outward proactive behavior still routes through formal action/planner owners.
3. Deferred or blocked proactive tendencies remain continuity-visible.
4. Structured proactive observability is defined.

## 8. Implementation Status Snapshot

1. `helios_v2/src/helios_v2/autonomy/` now defines immutable autonomy contracts, a first-version deterministic autonomy path, and a public `AutonomyEngine`.
2. `runtime/stages.py` now wires `AutonomyRuntimeStage` after experience writeback and before evaluation, and the stage preserves owner-private deferred continuity records across ticks.
3. `evaluation/` now formally consumes `autonomy_evidence` in addition to the existing thought/action/writeback and outward-expression artifact chain.
4. Deferred continuity is no longer tick-local only: prior deferred records now re-enter the autonomy owner through explicit request carry, long-horizon decay, same-key merge, explicit resolved-or-expired accounting, and bounded expiration semantics.

## 9. Validated Outcomes

1. `pytest helios_v2/tests/test_autonomy_contracts.py helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `26 passed`
2. `pytest helios_v2/tests -q` -> `204 passed`
