# Requirement 02 - Sensory ingress design

## 1. Design Overview

Sensory ingress is the sole owner of signal collection and normalization for the first runtime layer after source adapters. It exposes a narrow API for collecting normalized stimuli and two ops contracts: one for source submission semantics and one for runtime-facing batch publication semantics.

It does not own salience estimation, context interpretation, memory lookup, or routing policy.

## 2. Current State and Gap

Helios v1 blended input adaptation with runtime wiring and partial stimulus interpretation. Helios v2 needs a clean owner boundary before rapid appraisal is introduced.

The gap is a typed, documented, fail-explicit ingress layer that can normalize raw signals without embedding downstream logic.

## 3. Target Architecture

The initial sensory ingress slice contains five runtime concepts:

1. `RawSignal`: immutable raw input emitted by one source owner.
2. `Stimulus`: immutable normalized record owned by sensory ingress.
3. `StimulusBatch`: immutable collection published to downstream runtime owners.
4. `IngestSignalOp`: source-to-owner op describing one raw signal submission event.
5. `PublishStimulusBatchOp`: owner-to-runtime op describing one normalized batch publication.

The owner-facing API is `SensorySource` plus `SensoryIngressAPI`.

Lifecycle:

1. Sources are registered by stable owner name.
2. The ingress owner requests raw signals from each source.
3. Raw signals are normalized into `Stimulus` objects.
4. The owner can expose a corresponding `IngestSignalOp` for each raw signal submission.
5. Invalid required signals raise a hard-stop ingress error.
6. The owner returns a `StimulusBatch` with deterministic content-derived identity and can expose a corresponding publication op.

## 4. Data Structures

### 4.1 RawSignal
- `signal_id: str`
- `source_name: str`
- `signal_type: str`
- `content: str`
- `channel: str | None`
- `metadata: Mapping[str, object]`
- `required: bool`

### 4.2 Stimulus
- `stimulus_id: str`
- `source_name: str`
- `modality: str`
- `content: str`
- `channel: str | None`
- `metadata: Mapping[str, object]`
- `provenance_signal_id: str`

### 4.3 StimulusBatch
- `batch_id: str`
- `stimuli: tuple[Stimulus, ...]`

### 4.4 IngestSignalOp
- `op_name: str`
- `owner: str`
- `source_name: str`
- `signal_id: str`
- `required: bool`

### 4.5 PublishStimulusBatchOp
- `op_name: str`
- `owner: str`
- `batch_id: str`
- `stimulus_count: int`
- `source_names: tuple[str, ...]`

## 5. Module Changes

1. `sensory/contracts.py` defines the owner declaration, typed data contracts, source and ingress protocols, ops contracts, and ingress errors.
2. `sensory/ingress.py` implements source registration and normalization.
3. `sensory/ingress.py` builds source-ingest ops and deterministic content-derived batch identifiers.
4. `sensory/__init__.py` exports the public sensory ingress surface.
5. `tests/test_sensory_ingress.py` validates registration, normalization, deterministic provenance, and fail-explicit behavior.

## 6. Migration Plan

This slice does not port Helios v1 channel gateway behavior directly.

It only establishes the v2 ingress owner and contract language. Channel-specific adapters can plug into the `SensorySource` protocol in later slices.

## 7. Failure Modes and Constraints

1. Duplicate source registration raises `ValueError`.
2. Missing or invalid required signal content raises `SensoryIngressError`.
3. Optional invalid signals may be skipped only when the source marks them as non-required.
4. No fallback or inferred replacement stimulus is allowed.

## 8. Observability and Logging

This initial slice keeps observability structural rather than verbose:

1. stimulus batches preserve source provenance,
2. ingestion ops expose source submission identity,
3. publication ops expose batch and source summary fields,
4. errors name the failing source and signal.

## 9. Validation Strategy

1. Unit test duplicate source rejection.
2. Unit test normalization into immutable stimulus batch.
3. Unit test batch identity changes when content changes.
4. Unit test invalid required signal failure.
5. Unit test ingestion and publication op summary fields.