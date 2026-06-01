# Requirement 05 - Interoceptive feeling layer

## 1. Background and Problem

After neuromodulator state is updated, Helios v2 still needs a separate owner that turns body-state-related inputs into a subjective body-feeling representation. Without this layer, downstream memory, workspace, and arbitration owners would have to read raw neuromodulator levels or internal body signals directly, which would collapse embodied state and felt state into the same contract.

Helios v2 explicitly requires an interoceptive feeling layer as a separate owner. This layer should correspond to the body-state-subjectivization role, not to a generic emotion controller and not to an action gate owner.

## 2. Goal

Create an interoceptive feeling owner that consumes `NeuromodulatorState` plus normalized internal body signals, produces an immutable feeling-state snapshot with a stable dimensional schema, and exposes documented API and ops contracts without hardcoded heuristics, fallback behavior, or direct hard-gate ownership.

## 3. Functional Requirements

### 3.1 Feeling-layer ownership
1. The interoceptive feeling layer must be the sole owner of subjective body-feeling state.
2. The owner must remain separate from neuromodulator state mutation, memory tagging, workspace competition, and action gating.
3. The owner must not reinterpret itself as a generic emotion-policy or action-selection layer.

### 3.2 Upstream input boundary
1. The interoceptive feeling layer must accept `NeuromodulatorState` as a required upstream input contract.
2. The interoceptive feeling layer may consume normalized internal body signals, but only if those signals arrive as `sensory.Stimulus` values whose modality is restricted to `body` or `interoceptive`.
3. The owner must not require direct access to `RapidAppraisalBatch` in this slice.
4. The owner must expose a public API for updating feeling state from the upstream neuromodulator and internal-signal inputs.

### 3.3 Feeling-state schema
1. The public feeling contract must use a dimensional vector as its primary representation.
2. The initial feeling vector must support at least `valence`, `arousal`, `tension`, `comfort`, `fatigue`, `pain_like`, and `social_safety`.
3. The public contract must not require discrete feeling tags as the primary published representation in this slice.
4. The owner must preserve enough provenance to identify the upstream neuromodulator state used to construct the feeling snapshot.

### 3.4 Public API and ops exposure
1. The interoceptive feeling layer must expose documented public API contracts for feeling-state update and publication.
2. The owner must define an op for feeling update requests.
3. The owner must define an op for feeling-state publication.
4. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.5 Output boundary and downstream effects
1. The owner must publish only feeling-state snapshots and the corresponding update/publication ops in this slice.
2. The owner must not publish memory-specific affect hints or action-specific routing hints in this slice.
3. The owner may contribute soft modulation signals for downstream owners.
4. The owner must not emit hard-gate or hard-stop authority signals in this slice.

### 3.6 Learned or runtime-provided feeling construction semantics
1. The owner must not hardcode permanent weighted formulas, routing branches, or threshold heuristics into the architecture contract.
2. Feeling construction policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are baseline feeling values and legal min/max bounds.
4. Mapping strength, coupling, and other dynamic construction semantics must remain learning-driven rather than permanently fixed.

### 3.7 No fallback behavior
1. The interoceptive feeling layer must not synthesize a fallback feeling vector when required upstream inputs are malformed or unavailable.
2. The owner must not downgrade to a simpler heuristic feeling path when the configured construction path is unavailable.
3. The owner must fail explicitly when required input invariants or required construction capabilities are missing.

## 4. Non-Functional Requirements

1. Feeling-state contracts must be immutable after publication.
2. Identical upstream inputs and identical owner state must produce deterministic outputs for the same configured construction path.
3. The owner boundary must remain separate from neuromodulator, memory, workspace, and inhibitory-gating owners.
4. Published state must preserve enough provenance to support later diagnostics and evaluation.

## 5. Code Behavior Constraints

1. Interoceptive feeling code must not import memory, workspace, or action-routing owners.
2. Interoceptive feeling code must expose only documented APIs and ops contracts across module boundaries.
3. Interoceptive feeling code must not encode permanent hardcoded thresholds, weighted formulas, or fallback default branches as architecture truth.
4. Only baseline values and legal bounds may be initialized as priors; dynamic construction semantics must not be frozen into architecture defaults.
5. Hard-gate execution remains outside this owner.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/feeling/contracts.py`
2. `helios_v2/src/helios_v2/feeling/engine.py`
3. `helios_v2/src/helios_v2/feeling/__init__.py`
4. `helios_v2/tests/test_interoceptive_feeling_contracts.py`
5. `helios_v2/tests/test_interoceptive_feeling_engine.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from neuromodulator state into feeling-state update.
2. The package defines documented ops contracts for feeling update requests and feeling-state publication.
3. The contract surface publishes a dimensional feeling vector with the confirmed minimum dimensions.
4. The package encodes the confirmed input boundary, including reuse of `sensory.Stimulus` for optional body/interoceptive signals, publication boundary, and no-hard-gate rule for this owner.
5. No test or implementation path demonstrates fallback feeling synthesis or degraded heuristic substitution.