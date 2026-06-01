# Requirement 05 - Interoceptive feeling layer design

## 1. Design Overview

Interoceptive feeling layer is the sole owner of subjective body-feeling state immediately after neuromodulator update and before memory affect tagging, conscious workspace use, or inhibitory gating. It consumes neuromodulator state plus normalized internal body signals, constructs an immutable feeling-state snapshot, and publishes that snapshot for downstream owners.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, and confirmed feeling-schema constraints before any permanent feeling-construction implementation is written.

## 2. Current State and Gap

Helios v2 now has runtime kernel, sensory ingress, rapid salience appraisal, and neuromodulator owners, but no formal owner that turns embodied internal state into a subjective body-feeling representation. Without this layer, downstream domains would either inspect neuromodulator levels directly or invent private feeling semantics, which would destroy embodied-state traceability.

The gap is a typed, documented, fail-fast owner for subjective body-feeling state.

The next gap after that contract layer is a concrete owner skeleton that can:

1. accept `NeuromodulatorState`,
2. optionally accept normalized internal body signals through reused `sensory.Stimulus` contracts limited to `body` or `interoceptive` modality,
3. build a feeling update request op,
4. invoke an owner-controlled feeling-construction path,
5. publish an immutable feeling-state snapshot,
6. reject malformed input or unavailable required construction capability explicitly.

## 3. Target Architecture

The initial interoceptive feeling slice contains five runtime concepts:

1. `InteroceptiveFeelingVector`: immutable dimensional feeling representation.
2. `InteroceptiveFeelingState`: immutable owner snapshot with provenance and cycle identity.
3. `UpdateInteroceptiveFeelingOp`: runtime-visible request op describing one feeling update request.
4. `PublishInteroceptiveFeelingStateOp`: runtime-visible publication op describing one feeling-state snapshot.
5. `InteroceptiveFeelingAPI`: public owner-facing API for update and publication.

Implementation boundary confirmation:

1. Interoceptive feeling layer owns only subjective body-feeling construction and publication.
2. It does not own neuromodulator mutation, memory affect tagging, conscious content selection, or inhibitory gate execution.
3. It may expose replaceable internal construction interfaces, but those interfaces remain private to the owner until promoted by a later requirement slice.
4. `NeuromodulatorState -> InteroceptiveFeelingState` is the first required public owner-facing transformation in this slice.

Lifecycle:

1. Neuromodulator system publishes a `NeuromodulatorState`.
2. Interoceptive feeling layer validates neuromodulator provenance and optional internal-signal invariants.
3. The owner builds a feeling update request op for orchestration visibility.
4. An owner-controlled feeling-construction path computes the next feeling vector.
5. The owner publishes one immutable `InteroceptiveFeelingState` snapshot and one corresponding publication op.

Confirmed design constraints for this slice:

1. Required upstream input is `NeuromodulatorState`.
2. Optional additional input may come from normalized internal body signals only, represented in this slice by `sensory.Stimulus` values limited to `body` or `interoceptive` modality; this slice does not read `RapidAppraisalBatch` directly.
3. The minimum public feeling schema is a dimensional vector containing `valence`, `arousal`, `tension`, `comfort`, `fatigue`, `pain_like`, and `social_safety`.
4. The owner publishes only feeling-state snapshots and update/publication ops in this slice.
5. The owner may contribute soft modulation only; hard-gate execution remains outside this owner.
6. The only allowed initialization priors are baseline feeling values and legal min/max bounds.
7. Mapping strength and coupling semantics remain learning-driven rather than permanently fixed.

## 4. Data Structures

### 4.1 InteroceptiveFeelingVector
- `valence: float`
- `arousal: float`
- `tension: float`
- `comfort: float`
- `fatigue: float`
- `pain_like: float`
- `social_safety: float`

### 4.2 InteroceptiveFeelingState
- `state_id: str`
- `source_neuromodulator_state_id: str`
- `feeling: InteroceptiveFeelingVector`
- `tick_id: int | None`

### 4.3 UpdateInteroceptiveFeelingOp
- `op_name: str`
- `owner: str`
- `neuromodulator_state_id: str`
- `internal_signal_count: int`

### 4.4 PublishInteroceptiveFeelingStateOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `source_neuromodulator_state_id: str`
- `dominant_dimensions: tuple[str, ...]`

## 5. Module Changes

1. `feeling/contracts.py` defines owner declaration, typed feeling contracts, public API protocol, ops contracts, and feeling error type.
2. `feeling/engine.py` will implement the first owner skeleton for feeling update and publication.
3. `feeling/__init__.py` will export the public feeling surface.
4. `tests/test_interoceptive_feeling_contracts.py` will validate contract immutability, provenance, and dimensional schema.
5. `tests/test_interoceptive_feeling_engine.py` will validate owner-skeleton behavior and fail-fast input handling.

## 6. Confirmation Gates

This requirement package must not guess the following unresolved semantics:

1. whether feeling-construction coupling is globally sparse, pair-specific, or family-constrained,
2. the exact runtime semantics of soft modulation payloads consumed by downstream owners,
3. whether dominant-dimension reporting should be rank-based, threshold-based, or another learned reporting scheme,
4. whether some feeling dimensions require asymmetric persistence rules beyond the shared learning-driven policy.

These remain explicit design gates that require user confirmation before implementation of the permanent construction path.

## 7. Migration Plan

This slice does not port Helios v1 mood or affect logic directly.

It defines the v2 owner boundary first so later memory, workspace, and arbitration slices can attach to a stable feeling contract.

## 8. Failure Modes and Constraints

1. Missing neuromodulator provenance must raise an explicit feeling-owner error.
2. Published feeling values outside the allowed contract range must raise an explicit feeling-owner error.
3. Publication must not occur for malformed feeling states.
4. No fallback feeling-vector path is allowed.
5. Missing required construction capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent weighted formulas, permanent routing branches, and permanent threshold heuristics are prohibited.
7. The owner skeleton must reject malformed input before invoking its internal construction path.

## 9. Observability and Logging

This initial slice keeps observability structural:

1. feeling state preserves source neuromodulator provenance,
2. update and publication ops summarize owner activity,
3. dominant-dimension reporting supports downstream diagnostics without transferring gate or memory ownership,
4. error types define malformed contract conditions explicitly.

## 10. Validation Strategy

1. Unit test immutable feeling-state contracts.
2. Unit test dimensional schema coverage in the public contract surface.
3. Unit test provenance preservation from `NeuromodulatorState` into `InteroceptiveFeelingState`.
4. Unit test validation of optional internal signals restricted to `body` or `interoceptive` modality.
5. Unit test that only baseline values and legal bounds are accepted as initialization priors.
6. Unit test that learned construction semantics are represented explicitly in the owner configuration surface.
7. Unit test request and publication op summary fields.
8. Unit test explicit failure for malformed neuromodulator input.
9. Unit test explicit failure when required construction capability is unavailable.