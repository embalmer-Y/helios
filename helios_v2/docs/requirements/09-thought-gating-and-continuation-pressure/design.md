# Requirement 09 - Thought gating and continuation pressure design

## 1. Design Overview

Thought gating and continuation pressure are the sole owner-controlled transition between `08` reportable conscious content and the later thought-window pipeline. This slice consumes explicit current-cycle gate inputs, computes one formal `fire` versus `no_fire` decision, publishes compact gate observability, and owns the structured multi-tick continuation-pressure state for later retrieval and internal-thought owners.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, explicit gate-input contract, compact stimulus-summary contract, formal continuation-pressure contract, and owner-controlled gate path before later retrieval and internal-thought slices are implemented.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, neuromodulator, interoceptive feeling, memory affect and replay, workspace competition, and reportable consciousness owners, but it still lacks a formal owner that decides whether the thought window opens and how unfinished thought pressure persists across cycles.

The legacy implementation already demonstrates that these are distinct runtime concepts:

1. `ThoughtGateResult` records whether internal thought should fire, why, and which signals contributed.
2. `ContinuationPressureState` carries multi-tick pressure with origin thought, expiry, and carry count.
3. The current path mixes those concepts with thought-type cooldown, directed retrieval, thought generation, action derivation, and self-revision extraction.

The gap is therefore twofold:

1. a typed, documented, fail-fast owner for current-cycle gate decisions,
2. a typed, documented, fail-fast owner for continuation-pressure carry that remains separate from retrieval and thought generation.

## 3. Target Architecture

The initial thought-gating slice contains eight runtime concepts:

1. `ThoughtGateSignalSnapshot`: immutable explicit normalized gate inputs for one cycle.
2. `SelectedStimulusSummary`: immutable compact stimulus observability item used only for gate provenance.
3. `ThoughtGateDecision`: explicit per-cycle gate outcome taxonomy for `fire` and `no_fire`.
4. `NoFireReason`: explicit no-fire taxonomy for the current cycle.
5. `ThoughtGateResult`: immutable published gate snapshot for one cycle.
6. `ContinuationPressureState`: immutable published continuation-pressure snapshot.
7. `EvaluateThoughtGateOp`: runtime-visible request op for one gate-evaluation cycle.
8. `PublishThoughtGateResultOp` and `PublishContinuationPressureOp`: runtime-visible publication ops for the gate result and continuation carry.

The initial owner also contains one private owner-controlled collaborator surface:

1. `ThoughtGatePath`: private owner interface responsible for turning explicit gate inputs plus prior continuation state into one gate result and one next continuation state.

Implementation boundary confirmation:

1. Thought-gating owner owns only current-cycle gate evaluation and continuation-pressure publication.
2. It does not own thought-type cooldown, directed retrieval, internal-thought content generation, action externalization, planner routing, executor dispatch, or identity writeback.
3. It may expose a replaceable internal gate path, but that path remains private to the owner until promoted by a later requirement slice.
4. `ConsciousState + ContinuationPressureState + ThoughtGateSignalSnapshot -> ThoughtGateResult + ContinuationPressureState` is the first required public owner-facing transformation in this slice.

### 3.1 Explicit gate-input boundary

The gate owner must read one explicit normalized input surface rather than reach through upstream owners.

`ThoughtGateSignalSnapshot` is expected to carry at least:

1. workload pressure,
2. ICRI or equivalent global activation level,
3. temporal-dynamics signal,
4. drive-urgency signal,
5. DMN-availability flag or score,
6. current-cycle compact stimulus summaries.

The gate owner must not:

1. read full raw channel payloads,
2. inspect retrieval-window content,
3. inspect thought text or structured decisions,
4. pull private state from planner, executor, or identity owners.

### 3.2 Lifecycle

1. `08` publishes one `ConsciousState` for the current cycle.
2. Runtime provides one explicit `ThoughtGateSignalSnapshot` plus the prior-cycle `ContinuationPressureState`.
3. Thought-gating owner validates conscious-state, signal-snapshot, and carry-state invariants.
4. The owner builds one `EvaluateThoughtGateOp` for orchestration visibility.
5. An owner-controlled gate path computes one `ThoughtGateResult` and one next `ContinuationPressureState`.
6. The owner publishes one immutable `ThoughtGateResult` every valid cycle.
7. The owner publishes one immutable `ContinuationPressureState` every valid cycle, including clear or decayed carry states.
8. Later retrieval and internal-thought owners consume the published gate result and continuation state without transferring ownership back into this slice.

### 3.3 Confirmed design constraints for this slice

1. Required upstream inputs are `ConsciousState`, `ThoughtGateSignalSnapshot`, and prior `ContinuationPressureState`.
2. Current-cycle stimulus observability inside `09` is compact summary only and must not expose full payload dictionaries.
3. `09` publishes one formal gate result every valid cycle.
4. `ThoughtGateResult.decision` is explicit and supports at least `fire` and `no_fire`.
5. `NoFireReason` is explicit and supports a fixed first-version taxonomy rather than open-ended free text.
6. `09` publishes one structured continuation state every valid cycle rather than a scalar mirror only.
7. Thought-type cooldown remains outside this slice and is deferred to the later internal-thought owner.
8. Gate scoring, no-fire policy, and continuation decay may use one owner-controlled deterministic first-version path, but that path remains private to `09` and does not become permanent architecture truth.

## 4. Data Structures

### 4.1 SelectedStimulusSummary
- `stimulus_id: str`
- `source_kind: str`
- `source_channel_id: str | None`
- `stimulus_intensity: float`
- `novelty_signal: float | None`
- `sensitization_signal: float | None`

Purpose:

1. preserve compact trigger observability for the gate owner,
2. avoid carrying raw upstream payloads across the `09` public boundary,
3. give later diagnostics enough evidence to explain why the gate opened or remained closed.

### 4.2 ThoughtGateSignalSnapshot
- `snapshot_id: str`
- `source_conscious_state_id: str`
- `workload_pressure: float`
- `global_activation_level: float`
- `temporal_signal: float`
- `drive_urgency_signal: float`
- `dmn_available: bool`
- `selected_stimuli: tuple[SelectedStimulusSummary, ...]`
- `tick_id: int | None`

Purpose:

1. define the explicit normalized input boundary for `09`,
2. prevent owner reach-through into unrelated upstream modules,
3. give the gate path one bounded signal surface per cycle.

### 4.3 ThoughtGateDecision
- `fire`
- `no_fire`

Purpose:

1. make current-cycle gate outcome explicit,
2. prevent silent omission of no-fire cycles,
3. support deterministic downstream handling.

### 4.4 NoFireReason
- `gate_score_too_low`
- `resource_pressure_too_high`
- `continuation_absent_and_no_stimulus`
- `conscious_content_not_eligible`
- `capability_rejected_cycle`

Purpose:

1. make no-fire causes explicit and testable,
2. avoid open-ended free-text drift in the first version,
3. support downstream diagnostics without reopening owner boundaries.

### 4.5 ThoughtGateResult
- `result_id: str`
- `source_conscious_state_id: str`
- `source_signal_snapshot_id: str`
- `decision: ThoughtGateDecision`
- `gate_score: float`
- `trigger_reason: str | None`
- `dominant_reason: str | None`
- `blocked_reasons: tuple[str, ...]`
- `contributing_signals: dict[str, float]`
- `selected_stimuli: tuple[SelectedStimulusSummary, ...]`
- `no_fire_reason: NoFireReason | None`
- `tick_id: int | None`

Purpose:

1. represent one immutable formal gate result for one cycle,
2. make trigger observability explicit,
3. remain bounded and compact enough for later diagnostic consumption.

### 4.6 ContinuationPressureState
- `active: bool`
- `level: float`
- `origin_thought_id: str`
- `reason: str`
- `expires_at_tick: int`
- `carry_count: int`

Purpose:

1. preserve the formal multi-tick carry owner,
2. make continuation pressure auditable beyond a scalar mirror,
3. keep carry semantics explicit for later retrieval and internal-thought slices.

### 4.7 EvaluateThoughtGateOp
- `op_name: str`
- `owner: str`
- `conscious_state_id: str`
- `signal_snapshot_id: str`
- `prior_continuation_active: bool`

### 4.8 PublishThoughtGateResultOp
- `op_name: str`
- `owner: str`
- `result_id: str`
- `decision: str`
- `no_fire_reason: str | None`

### 4.9 PublishContinuationPressureOp
- `op_name: str`
- `owner: str`
- `active: bool`
- `level: float`
- `origin_thought_id: str`

## 5. Module Changes

1. `thought_gating/contracts.py` defines owner declaration, typed gate contracts, public API protocol, ops contracts, fixed first-version decision taxonomies, and gate-owner error type.
2. `thought_gating/engine.py` will implement the first owner skeleton for gate evaluation and continuation publication.
3. `thought_gating/__init__.py` will export the public gate surface.
4. `runtime/stages.py` will add one `09` runtime stage result and one explicit runtime-owned gate-signal provider contract.
5. `tests/test_thought_gating_contracts.py` will validate contract immutability, bounded observability, provenance preservation, and fixed decision taxonomies.
6. `tests/test_thought_gating_engine.py` will validate owner-skeleton behavior, fail-fast input handling, explicit no-fire publication, and continuation carry behavior.
7. `tests/test_runtime_stage_chain.py` will validate the `08 -> 09` stage boundary and explicit immutable frame passing.

## 6. Migration Plan

This slice does not port the legacy mixed thought-integration path directly.

It extracts only the gate and continuation concepts first so later retrieval and internal-thought slices can attach to a stable `09` contract.

First-version migration direction:

1. preserve the existing legacy semantics that gate decisions can depend on stimulus pressure, continuation pressure, drive urgency, global activation, temporal dynamics, and workload pressure,
2. remove legacy thought-type cooldown from the gate owner and defer it to the later internal-thought owner,
3. reduce legacy selected-stimulus observability to compact summaries instead of full payload dictionaries,
4. preserve structured continuation carry with origin thought, expiry, and carry count as a first-class public contract.

## 7. Failure Modes and Constraints

1. Missing conscious-state provenance must raise an explicit gate-owner error.
2. Missing required normalized gate signals must raise an explicit gate-owner error.
3. Publication must not occur for malformed gate results or malformed continuation states.
4. No fallback fire-decision path is allowed.
5. Missing required gate capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent weighted formulas, permanent threshold heuristics, and permanent continuation-decay branches are prohibited as architecture truth.
7. The owner skeleton must reject malformed input before invoking its private gate path.
8. Compact stimulus summaries must be validated so that raw payload dictionaries cannot cross the `09` public boundary.

## 8. Observability and Logging

This initial slice keeps observability structural and bounded:

1. gate result preserves source conscious-state provenance and signal-snapshot provenance,
2. compact selected-stimulus summaries expose only bounded gate-relevant fields,
3. contributing-signal summaries preserve normalized numeric evidence for later diagnostics,
4. continuation-pressure publication preserves origin thought, expiry, and carry count,
5. error types define malformed gate-contract conditions explicitly.

## 9. Validation Strategy

1. Unit test immutable gate-result and continuation contracts.
2. Unit test fixed decision and no-fire taxonomies in the public contract surface.
3. Unit test that compact selected-stimulus observability rejects full payload dictionaries.
4. Unit test provenance preservation from `ConsciousState` and `ThoughtGateSignalSnapshot` into `ThoughtGateResult`.
5. Unit test explicit publication of `fire` and `no_fire` cycles.
6. Unit test explicit continuation decay, carry preservation, and carry clearing.
7. Unit test that thought-type cooldown is not represented as a `09` public contract responsibility.
8. Unit test explicit failure for malformed conscious-state or malformed signal-snapshot input.
9. Unit test explicit failure when required gate capability is unavailable.
10. Unit test runtime-stage wiring from `08` into `09` through immutable frame inputs only.