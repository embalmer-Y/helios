# Requirement 03 - Rapid salience appraisal design

## 1. Design Overview

Rapid salience appraisal is the sole owner of fast-path coarse appraisal immediately after sensory ingress. It consumes `StimulusBatch`, computes coarse salience summaries, and publishes `RapidAppraisalBatch` for downstream gating layers.

This slice now moves from contract-only definition into owner skeleton implementation. The first implementation must establish the owner boundary, batch assessment flow, pluggable estimator interfaces, and fail-fast malformed-input handling without committing to a permanent scoring strategy.

## 2. Current State and Gap

Helios v2 now has a sensory ingress owner but no formally separated early-appraisal layer. Without that separation, later cognition or routing owners would have to read raw stimuli directly or sensory ingress would be pressured to absorb appraisal semantics.

The gap is a typed, documented contract layer for early coarse salience assessment.

The next gap after that contract layer is a concrete owner skeleton that can:

1. accept `StimulusBatch`,
2. validate batch invariants,
3. build per-stimulus rapid appraisal records,
4. expose request and publication ops,
5. delegate dimension and aggregate estimation to replaceable appraisal components.

## 3. Target Architecture

The initial rapid appraisal slice contains five runtime concepts:

1. `RapidSalienceVector`: immutable coarse salience dimensions.
2. `RapidAppraisal`: immutable appraisal result for one stimulus.
3. `RapidAppraisalBatch`: immutable batch of coarse appraisal results.
4. `AssessStimulusBatchOp`: runtime-visible request op describing one appraisal request.
5. `PublishRapidAppraisalBatchOp`: runtime-visible publication op describing one appraisal result batch.

The owner-facing API is `RapidSalienceAppraisalAPI`.

Implementation boundary confirmation:

1. Rapid appraisal owns only coarse early salience estimation.
2. It does not own semantic parsing, memory retrieval, action intent generation, or policy ranking.
3. It may expose replaceable estimator interfaces, but those interfaces remain private to the appraisal owner until promoted by a later requirement slice.
4. The `StimulusBatch -> RapidAppraisalBatch` transformation is the only public owner-facing batch API in this slice.

Lifecycle:

1. Sensory ingress publishes a `StimulusBatch`.
2. Rapid appraisal validates batch provenance and summary invariants.
3. The owner builds an assessment request op for orchestration visibility.
4. Each stimulus is mapped to a coarse salience vector by an owner-controlled estimator path.
5. The owner returns a `RapidAppraisalBatch`.
6. The owner can expose a corresponding publication op.

## 4. Data Structures

### 4.1 RapidSalienceVector
- `threat: float`
- `reward: float`
- `novelty: float`
- `social: float`
- `uncertainty: float`
- `aggregate: float`

### 4.2 RapidAppraisal
- `appraisal_id: str`
- `stimulus_id: str`
- `source_name: str`
- `salience: RapidSalienceVector`
- `provenance_signal_id: str`

### 4.3 RapidAppraisalBatch
- `batch_id: str`
- `appraisals: tuple[RapidAppraisal, ...]`

### 4.4 AssessStimulusBatchOp
- `op_name: str`
- `owner: str`
- `stimulus_batch_id: str`
- `stimulus_count: int`
- `source_names: tuple[str, ...]`

### 4.5 PublishRapidAppraisalBatchOp
- `op_name: str`
- `owner: str`
- `appraisal_batch_id: str`
- `appraisal_count: int`
- `source_names: tuple[str, ...]`

## 5. Module Changes

1. `appraisal/contracts.py` defines owner declaration, typed appraisal contracts, API protocol, ops contracts, and appraisal error type.
2. `appraisal/__init__.py` exports the public appraisal contract surface.
3. `appraisal/engine.py` implements the first owner skeleton for batch assessment and op construction.
4. `tests/test_rapid_salience_contracts.py` validates the contract layer.
5. `tests/test_rapid_salience_engine.py` validates owner-skeleton behavior and boundary-safe fail-fast semantics.

Aggregate semantics for this slice are intentionally hybrid:

1. `aggregate` remains an explicit owner-produced field.
2. Early implementations may let dimension combination contribute part of the aggregate value.
3. The aggregate field must not be reduced to a fixed alias of dimension arithmetic as a permanent architecture rule.
4. Later implementations may use learned models or LLM-assisted appraisal to produce the overall judgment, provided the owner boundary remains intact.

Implementation strategy for aggregate in this slice:

1. The appraisal owner exposes a replaceable aggregate estimator interface internally.
2. The first skeleton may combine dimension-derived signal with a separately supplied owner judgment path.
3. The skeleton must not hardcode a permanent weighted formula as the architecture contract.
4. The first executable slice may use a minimal deterministic estimator only as a bootstrap implementation surface, not as the declared long-term semantics.

## 6. Migration Plan

This slice does not port Helios v1 appraisal logic directly.

It defines the v2 contract boundary so later scoring implementations can land without reopening owner semantics.

## 7. Failure Modes and Constraints

1. Missing stimulus provenance must raise `RapidAppraisalError`.
2. Salience values outside the allowed range must raise `RapidAppraisalError`.
3. Publication must not occur for malformed appraisal batches.
4. No fallback scoring path is allowed.
5. A fully low-salience but valid appraisal result is not a failure mode and must remain publishable.
6. The owner skeleton must reject malformed input before estimator invocation.
7. Estimator interfaces must not pull in memory, planning, or routing dependencies in this slice.

## 8. Observability and Logging

This initial slice keeps observability structural:

1. appraisal results preserve source and stimulus provenance,
2. request and publication ops summarize batch identity and coverage,
3. error types define malformed contract conditions explicitly,
4. owner-skeleton outputs are testable without introducing verbose runtime logging.

## 9. Validation Strategy

1. Unit test immutable appraisal contracts.
2. Unit test provenance preservation from `Stimulus` into `RapidAppraisal`.
3. Unit test range validation for salience values.
4. Unit test request and publication op summary fields.
5. Unit test that low-salience appraisals remain valid contract outputs.
6. Unit test that the owner skeleton rejects malformed batches before estimator execution.
7. Unit test that the owner skeleton can produce a `RapidAppraisalBatch` from a valid `StimulusBatch` using replaceable estimators.