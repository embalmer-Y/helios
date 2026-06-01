# Requirement 03 - Rapid salience appraisal

## 1. Background and Problem

After sensory ingress publishes normalized stimuli, Helios v2 needs a separate owner for fast-path coarse appraisal. This layer corresponds to the early threat/reward/novelty/social-salience estimation stage in the brain-inspired model. Without a dedicated owner, sensory collection risks absorbing interpretation logic and downstream systems risk reading raw stimuli without a stable early-appraisal contract.

Rapid salience appraisal must stay narrow. It should perform a coarse, early estimate that can guide later gating and routing, but it must not own fine semantic interpretation, memory retrieval, value integration, or action selection.

## 2. Goal

Create a rapid salience appraisal owner that consumes normalized stimulus batches, produces immutable coarse salience assessments for each stimulus, and exposes those assessments through documented APIs and ops contracts without mixing in fine semantic or decision-layer logic.

## 3. Functional Requirements

### 3.1 Early appraisal ownership
1. Rapid salience appraisal must consume `StimulusBatch` as its upstream input contract.
2. Rapid salience appraisal must produce a stable per-stimulus coarse appraisal contract.
3. The owner must preserve stimulus provenance in every appraisal record.

### 3.2 Coarse salience dimensions
1. The rapid appraisal contract must represent coarse early salience dimensions only.
2. The initial contract must support at least threat, reward, novelty, social salience, and uncertainty dimensions.
3. The contract must expose an aggregate coarse salience magnitude for runtime gating.
4. Rapid appraisal must not embed fine semantic interpretation or action intent.
5. The aggregate coarse salience magnitude may coexist with dimension scores and must remain an owner-produced overall judgment rather than a pure alias of one individual dimension.
6. Low-salience appraisal results with valid provenance must remain valid runtime outputs and must not be treated as contract errors.

### 3.3 Public API and ops exposure
1. Rapid salience appraisal must expose a public API for assessing one `StimulusBatch`.
2. Rapid salience appraisal must define an op for batch assessment requests.
3. Rapid salience appraisal must define an op for publication of coarse appraisal batches.
4. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.4 No fallback behavior
1. Rapid appraisal must not synthesize appraisal results for malformed required stimuli.
2. Rapid appraisal must not downgrade to a simpler rule path when the appraisal owner cannot evaluate the batch.
3. Rapid appraisal must fail explicitly when required input invariants are violated.

## 4. Non-Functional Requirements

1. Appraisal results must be deterministic for identical input and identical appraisal state.
2. Appraisal contracts must be immutable after publication.
3. The owner boundary must remain separate from sensory ingress and later reappraisal layers.
4. The contract must allow early implementations where aggregate salience is partially informed by dimension combination while preserving space for later learned or model-assisted overall judgment.

## 5. Code Behavior Constraints

1. Rapid appraisal code must not import memory, deliberation, or action-routing owners.
2. Rapid appraisal must not mutate the incoming `StimulusBatch`.
3. Rapid appraisal must expose only documented APIs and ops contracts across module boundaries.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/appraisal/contracts.py`
2. `helios_v2/src/helios_v2/appraisal/engine.py`
3. `helios_v2/src/helios_v2/appraisal/__init__.py`
4. `helios_v2/tests/test_rapid_salience_contracts.py`
5. `helios_v2/tests/test_rapid_salience_engine.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from sensory ingress into rapid appraisal.
2. The requirement package defines documented ops contracts for batch assessment and appraisal publication.
3. The coarse appraisal contract preserves stimulus provenance, includes uncertainty, and excludes fine semantic or action semantics.
4. The owner skeleton validates required batch invariants before estimator invocation and remains separate from downstream domains.
5. Contract-layer and owner-skeleton tests verify immutability, provenance preservation, stable exported interface names, and validity of low-salience appraisal results.