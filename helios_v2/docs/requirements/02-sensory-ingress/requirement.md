# Requirement 02 - Sensory ingress

## 1. Background and Problem

Helios v2 needs a dedicated owner for incoming signals before any salience scoring, memory lookup, or deliberation occurs. In Helios v1, stimulus construction was spread across gateway logic, channel adapters, and runtime orchestration. That shape blurred boundaries between collection, normalization, and downstream interpretation.

Sensory ingress in Helios v2 must become a narrow owner that accepts raw source signals, normalizes them into a stable stimulus contract, and exposes those normalized stimuli through explicit APIs and ops. It must not own salience scoring, memory retrieval, appraisal, or action routing.

## 2. Goal

Create a sensory ingress owner that registers signal sources, collects source-owned raw signal batches, normalizes them into immutable stimulus records, and exposes those records through documented API and ops contracts without fallback behavior or downstream policy leakage.

## 3. Functional Requirements

### 3.1 Source registration
1. Sensory ingress must support explicit registration of source owners.
2. Each registered source must have a stable owner name.
3. Duplicate source owner names must be rejected explicitly.

### 3.2 Stimulus normalization
1. Sensory ingress must transform raw source signals into a stable normalized stimulus contract.
2. The normalized contract must preserve source provenance.
3. Sensory ingress must reject invalid or incomplete source signals explicitly.
4. Sensory ingress must not assign salience, value, or action intent during normalization.

### 3.3 Public API and ops exposure
1. Sensory ingress must expose a public API for collecting the current normalized stimulus batch.
2. Sensory ingress must define ops contracts for source-to-owner ingestion requests and owner-to-runtime batch publication.
3. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.4 No fallback behavior
1. Sensory ingress must not synthesize placeholder stimuli when a required source emits invalid data.
2. Sensory ingress must not silently drop invalid required signals.
3. Sensory ingress must not perform downstream reinterpretation to compensate for source defects.

## 4. Non-Functional Requirements

1. Stimulus normalization must be deterministic for the same raw signal input.
2. Stimulus contracts must be immutable after publication.
3. Error reporting must be explicit enough for test assertions and diagnostics.

## 5. Code Behavior Constraints

1. Sensory ingress code must not import appraisal, memory, or action-routing owners.
2. Sensory ingress must expose only documented API and ops contracts across module boundaries.
3. Sensory ingress must not hide invalid input handling behind defaults or fallback values.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/sensory/contracts.py`
2. `helios_v2/src/helios_v2/sensory/ingress.py`
3. `helios_v2/src/helios_v2/sensory/__init__.py`
4. `helios_v2/tests/test_sensory_ingress.py`

## 7. Acceptance Criteria

1. Registering duplicate source owner names raises an explicit configuration error.
2. Collecting valid raw signals returns an immutable normalized stimulus batch with preserved provenance.
3. Invalid required signals raise an explicit ingress error instead of being replaced or silently dropped.
4. The sensory ingress API and ops contracts are documented and reference no salience or action semantics.