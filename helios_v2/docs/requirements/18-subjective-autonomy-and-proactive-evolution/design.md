# Requirement 18 - Subjective autonomy and proactive evolution design

## 1. Design Overview

The autonomy owner integrates unresolved internal tendencies into durable multi-tick self-directed activity. It publishes proactive-drive state, deferred continuity, and formal requests into the thought/action path while keeping channel and governance truth outside its boundary.

## 2. Current State and Gap

Without `18`, v2 can specify reaction and thought slices but cannot explain how a subject remains active between salient external stimuli. This is a direct gap against the final project goal.

## 3. Target Architecture

The initial slice contains seven runtime concepts:

1. `ProactiveDriveRequest`
2. `ProactiveDisposition`
3. `ProactiveDriveState`
4. `DeferredContinuityRecord`
5. `AutonomyResult`
6. `PublishProactiveDriveOp`
7. `AutonomyAPI`

Implementation boundary confirmation:

1. `18` owns proactive integration and deferred continuity.
2. `18` does not own channel execution or governance decisions.
3. `ProactiveDriveRequest -> AutonomyResult` is the required public transformation.

## 4. Data Structures

### 4.1 ProactiveDriveRequest
- `request_id: str`
- `continuation_summary: dict[str, object]`
- `retrieval_pull_summary: dict[str, object]`
- `temporal_pressure_summary: dict[str, object]`

### 4.2 ProactiveDisposition
- `reflect`
- `explore`
- `externalize`
- `defer`

### 4.3 ProactiveDriveState
- `state_id: str`
- `dominant_disposition: str`
- `pressure_components: dict[str, float]`
- `deferred_active: bool`

### 4.4 DeferredContinuityRecord
- `record_id: str`
- `continuity_key: str`
- `origin_ref: str`
- `carry_reason: str`
- `carry_count: int`
- `decayed_pressure: float`
- `expires_after_ticks: int | None`

### 4.5 AutonomyResult
- `result_id: str`
- `drive_state: ProactiveDriveState`
- `deferred_records: tuple[DeferredContinuityRecord, ...]`

## 5. Module Changes

1. `autonomy/contracts.py` defines typed autonomy contracts.
2. `autonomy/engine.py` implements the first-version deterministic autonomy path.
3. `runtime/stages.py` adds `AutonomyRuntimeStage`, `AutonomyRequestProvider`, and `AutonomyStageResult`.
4. `evaluation/` consumes `autonomy_evidence` so deferred continuity remains visible to the diagnostic owner.
5. Tests validate deferred continuity and formal boundary preservation.

## 6. Failure Modes and Constraints

1. Missing required continuity inputs raise explicit owner errors.
2. No direct channel triggering is allowed.

## 7. Validation Strategy

1. Unit test proactive-drive state publication.
2. Unit test blocked outward tendency becomes deferred continuity.
3. Unit test long-horizon decay, same-key merge, and resolved-or-expired continuity accounting.
4. Unit test runtime-stage wiring.

## 8. Implemented Baseline

1. `ProactiveDriveRequest` now carries explicit provenance ids from thought gating, retrieval, internal thought, planner bridge, governance, writeback, and the two-layer outward-expression artifact chain.
2. `ProactiveDriveRequest` also carries explicit `prior_deferred_records`, allowing the owner to preserve deferred continuity across ticks without reaching through private runtime state.
3. `FirstVersionAutonomyPath` deterministically chooses between `reflect`, `explore`, `externalize`, and `defer`, emits `DeferredContinuityRecord` when outward proactive pressure is blocked or must be carried forward, decays carried pressure across ticks, merges matching continuity keys, and publishes explicit generated/merged/resolved/expired counts inside the drive-state pressure snapshot.
4. `AutonomyRuntimeStage` owns the prior-record carry state privately and re-injects it into each new request, keeping the multi-tick carry policy inside the autonomy slice rather than distributing it across unrelated owners.
5. `EvaluationEvidenceBundle` now includes `autonomy_evidence`, allowing R17 diagnostics to distinguish missing autonomy evidence from preserved deferred continuity.

## 9. Validated Results

1. `pytest helios_v2/tests/test_autonomy_contracts.py helios_v2/tests/test_autonomy_engine.py helios_v2/tests/test_evaluation_contracts.py helios_v2/tests/test_evaluation_engine.py helios_v2/tests/test_runtime_stage_chain.py -q` -> `26 passed`
2. `pytest helios_v2/tests -q` -> `204 passed`
