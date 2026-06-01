# Requirement 04 - Neuromodulator system design

## 1. Design Overview

Neuromodulator system is the sole owner of runtime neuromodulator state immediately after rapid salience appraisal and before interoceptive feeling or later cognitive integration. It consumes upstream modulation requests, updates independently modeled neuromodulator channels, and publishes immutable state snapshots for downstream owners.

This slice is intentionally contract-first. It establishes the owner boundary, public API, ops contracts, and confirmation gates for unresolved parameter semantics before any permanent modulation update implementation is written.

## 2. Current State and Gap

Helios v2 now has a runtime kernel, sensory ingress, and rapid salience appraisal chain, but no formal owner that converts coarse appraisal outputs into internal neuromodulatory state. Without this layer, later owners would either duplicate modulation logic or read appraisal results as if they were already embodied internal state.

The gap is a typed, documented, fail-fast owner for independently modeled neuromodulator state.

The next gap after that contract layer is a concrete owner skeleton that can:

1. accept `RapidAppraisalBatch`,
2. build a modulation update request op,
3. invoke an owner-controlled modulation update path,
4. publish an immutable neuromodulator state snapshot,
5. reject malformed input or unavailable required update capability explicitly.

## 3. Target Architecture

The initial neuromodulator slice contains five runtime concepts:

1. `NeuromodulatorLevels`: immutable independently modeled neuromodulator channel values.
2. `NeuromodulatorState`: immutable owner snapshot with provenance and cycle identity.
3. `UpdateNeuromodulatorsOp`: runtime-visible request op describing one modulation update request.
4. `PublishNeuromodulatorStateOp`: runtime-visible publication op describing one neuromodulator state snapshot.
5. `NeuromodulatorSystemAPI`: public owner-facing API for update and publication.

Implementation boundary confirmation:

1. Neuromodulator system owns only neuromodulator state transitions and publication.
2. It does not own subjective feeling construction, memory tagging, deliberative reasoning, or action selection.
3. It may expose replaceable internal update-path interfaces, but those interfaces remain private to the owner until promoted by a later requirement slice.
4. `RapidAppraisalBatch -> NeuromodulatorState` is the first public owner-facing batch transformation in this slice.

Lifecycle:

1. Rapid salience appraisal publishes a `RapidAppraisalBatch`.
2. Neuromodulator system validates required appraisal provenance and update-request invariants.
3. The owner builds an update request op for orchestration visibility.
4. An owner-controlled modulation update path computes the next independently modeled neuromodulator levels.
5. The owner publishes one immutable `NeuromodulatorState` snapshot and one corresponding publication op.

Confirmed design constraints for this slice:

1. The baseline appraisal-to-modulator input mapping is fixed at the requirement level:
	- dopamine <- reward, novelty, positive prediction shift signals available to the owner
	- norepinephrine <- threat, uncertainty, novelty
	- serotonin <- aversive persistence, social stability, control-context signals available to the owner
	- acetylcholine <- uncertainty, attention demand, novelty
	- cortisol <- sustained threat, uncontrollable load
	- oxytocin <- positive social salience, affiliation cues
	- opioid tone <- relief, satisfaction, soothing
	- excitation <- external intensity, novelty, approach activation
	- inhibition <- conflict, threat, control demand
2. The only allowed initialization priors are tonic baseline values and legal min/max bounds.
3. Channel gain or sensitivity, cross-channel coupling strength, decay speed or persistence, and gate influence strength are mandatory learned parameters.
4. The default decay family is per-channel dual-timescale tonic/phasic dynamics.
5. `inhibition` and `cortisol` may emit hard-gate eligibility signals, but final hard-gate execution still belongs to the later inhibitory-gates owner.
6. All other channels are limited to soft modulation in this slice.

## 4. Data Structures

### 4.1 NeuromodulatorLevels
- `dopamine: float`
- `norepinephrine: float`
- `serotonin: float`
- `acetylcholine: float`
- `cortisol: float`
- `oxytocin: float`
- `opioid_tone: float`
- `excitation: float`
- `inhibition: float`

### 4.2 NeuromodulatorState
- `state_id: str`
- `source_appraisal_batch_id: str`
- `levels: NeuromodulatorLevels`
- `tick_id: int | None`

### 4.3 UpdateNeuromodulatorsOp
- `op_name: str`
- `owner: str`
- `appraisal_batch_id: str`
- `appraisal_count: int`
- `source_names: tuple[str, ...]`

### 4.4 PublishNeuromodulatorStateOp
- `op_name: str`
- `owner: str`
- `state_id: str`
- `source_appraisal_batch_id: str`
- `active_channels: tuple[str, ...]`

## 5. Module Changes

1. `neuromodulation/contracts.py` defines owner declaration, typed state contracts, public API protocol, ops contracts, and neuromodulator error type.
2. `neuromodulation/engine.py` will implement the first owner skeleton for modulation update and publication.
3. `neuromodulation/__init__.py` will export the public neuromodulator surface.
4. `tests/test_neuromodulator_contracts.py` will validate contract immutability, provenance, and channel independence.
5. `tests/test_neuromodulator_engine.py` will validate owner-skeleton behavior and fail-fast input handling.

## 6. Confirmation Gates

This requirement package must not guess the following unresolved semantics:

1. the exact owner-visible representation for "positive prediction shift", "aversive persistence", "control-context", and "uncontrollable load" before those upstream concepts receive their own requirement slices,
2. whether cross-channel coupling is globally sparse, pair-specific, or family-constrained,
3. whether any channels require asymmetric tonic/phasic learning rules rather than a shared dual-timescale interface,
4. the exact magnitude semantics of hard-gate eligibility signals passed from `inhibition` and `cortisol` into the later inhibitory-gates owner,
5. whether any channels share coupled constraints beyond publication-time validation.

These remain explicit design gates that require user confirmation before implementation of the permanent update path.

## 7. Migration Plan

This slice does not port Helios v1 affect or mood logic directly.

It defines the v2 owner boundary first so later embodied regulation and feeling slices can attach to a stable modulation contract.

## 8. Failure Modes and Constraints

1. Missing appraisal provenance must raise an explicit neuromodulator owner error.
2. Published neuromodulator values outside the allowed contract range must raise an explicit neuromodulator owner error.
3. Publication must not occur for malformed neuromodulator states.
4. No fallback fused-vector path is allowed.
5. Missing required update capability must abort execution rather than substituting a simpler heuristic path.
6. Permanent weighted formulas, permanent routing branches, and permanent threshold heuristics are prohibited.
7. The owner skeleton must reject malformed input before invoking its internal update path.

## 9. Observability and Logging

This initial slice keeps observability structural:

1. neuromodulator state preserves source appraisal batch provenance,
2. update and publication ops summarize owner activity,
3. active channel reporting supports downstream diagnostics,
4. hard-gate eligibility signals from `inhibition` and `cortisol` remain visible without transferring gate ownership,
5. error types define malformed contract conditions explicitly.

## 10. Validation Strategy

1. Unit test immutable neuromodulator state contracts.
2. Unit test channel independence in the contract surface.
3. Unit test provenance preservation from `RapidAppraisalBatch` into `NeuromodulatorState`.
4. Unit test request and publication op summary fields.
5. Unit test that only tonic baseline and legal bounds are accepted as initialization priors.
6. Unit test that learned-parameter categories are represented explicitly in the owner configuration surface.
7. Unit test explicit failure for malformed appraisal input.
8. Unit test explicit failure when required update capability is unavailable.