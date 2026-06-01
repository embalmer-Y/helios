# Requirement 04 - Neuromodulator system

## 1. Background and Problem

After rapid salience appraisal, Helios v2 needs a dedicated owner for internal neuromodulatory state transitions. Without this owner, appraisal outputs would either leak directly into downstream gates as raw scalar values or later layers would have to invent hidden modulation state for themselves. Both outcomes would blur boundaries and make it impossible to verify whether internal state changes actually influence later behavior.

Helios v2 also explicitly rejects a single fused "mood vector". The neuromodulator layer must model independent modulation channels rather than collapsing them into one opaque score.

## 2. Goal

Create a neuromodulator system owner that consumes upstream appraisal and later qualifying internal signals, maintains independently modeled neuromodulator state, and exposes documented API and ops contracts for modulation updates and publication without hardcoded strategy branches or fallback behavior.

## 3. Functional Requirements

### 3.1 Independent neuromodulator ownership
1. The neuromodulator system must be the sole owner of runtime neuromodulator state.
2. The owner must model neuromodulators independently rather than as one fused scalar.
3. The initial contract must support at least dopamine, norepinephrine, serotonin, acetylcholine, cortisol, oxytocin, opioid tone, excitation, and inhibition as distinct channels.
4. The owner must not delegate core neuromodulator state mutation to downstream feeling, memory, deliberation, or action-routing owners.

### 3.2 Upstream input boundary
1. The neuromodulator system must accept `RapidAppraisalBatch` as an initial upstream input contract.
2. The confirmed baseline appraisal-to-modulator input mapping is:
	- dopamine <- reward, novelty, positive prediction shift signals available to the owner
	- norepinephrine <- threat, uncertainty, novelty
	- serotonin <- aversive persistence, social stability, control-context signals available to the owner
	- acetylcholine <- uncertainty, attention demand, novelty
	- cortisol <- sustained threat, uncontrollable load
	- oxytocin <- positive social salience, affiliation cues
	- opioid tone <- relief, satisfaction, soothing
	- excitation <- external intensity, novelty, approach activation
	- inhibition <- conflict, threat, control demand
2. The owner may later accept additional internal regulatory inputs, but those inputs must be introduced through documented API or ops contracts rather than hidden shared state.
3. The owner must expose a public API for updating neuromodulator state from one upstream modulation request.
4. The owner must expose a publication API or ops contract for the resulting neuromodulator state snapshot.

### 3.3 Learned or runtime-provided modulation semantics
1. The owner must not hardcode permanent update formulas, threshold branches, or routing semantics into the architecture contract.
2. Any modulation update policy must be learned, runtime-provided, or initialized from explicit owner-controlled state rather than fixed strategy branches.
3. The only allowed initialization priors in this slice are tonic baseline values and legal min/max bounds for each channel.
4. Channel gain or sensitivity, cross-channel coupling strength, decay speed or persistence, and gate influence strength must be treated as online-learned parameters rather than permanent fixed priors.
5. The confirmed default decay family is per-channel dual-timescale tonic/phasic dynamics, while the concrete learned parameters remain owner-controlled runtime state.
6. The owner must surface any remaining unresolved parameter-model decisions as explicit confirmation gates rather than encoding guessed behavior.

### 3.4 Public API and ops exposure
1. The neuromodulator system must expose documented public API contracts for modulation updates and state reads.
2. The owner must define an op for neuromodulator update requests.
3. The owner must define an op for neuromodulator state publication.
4. Public APIs and ops contracts must be documented with owner, purpose, inputs, outputs, and failure semantics.

### 3.5 No fallback behavior
1. The neuromodulator system must not substitute a fused fallback vector when independent channels are unavailable or malformed.
2. The owner must not downgrade to permanent weighted formulas, permanent routing branches, or permanent threshold heuristics when the configured modulation update path is unavailable.
3. The owner must fail explicitly when required modulation input invariants or required update capabilities are missing.

## 4. Non-Functional Requirements

1. Neuromodulator state contracts must be immutable after publication.
2. Identical upstream inputs and identical neuromodulator owner state must produce deterministic outputs for the same configured update path.
3. The owner boundary must remain separate from interoceptive feeling, memory, deliberation, and action arbitration owners.
4. Published state must preserve enough provenance to support later diagnostics and evaluation.

## 5. Code Behavior Constraints

1. Neuromodulator code must not import feeling, memory retrieval, deliberation, or action-routing owners.
2. Neuromodulator code must expose only documented APIs and ops contracts across module boundaries.
3. Neuromodulator code must not encode permanent hardcoded thresholds, weighted routing formulas, or fallback default branches as architecture truth.
4. Only tonic baseline and legal bounds may be initialized as priors; learned parameters must not be frozen into architecture defaults.
5. `inhibition` and `cortisol` may contribute hard-gate eligibility signals only; all other channels are limited to soft modulation in this slice.
6. Unconfirmed parameter semantics must be represented as explicit design gates, not silent implementation choices.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/contracts.py`
2. `helios_v2/src/helios_v2/neuromodulation/engine.py`
3. `helios_v2/src/helios_v2/neuromodulation/__init__.py`
4. `helios_v2/tests/test_neuromodulator_contracts.py`
5. `helios_v2/tests/test_neuromodulator_engine.py`

## 7. Acceptance Criteria

1. The requirement package defines a documented API from rapid salience appraisal into neuromodulator state update.
2. The package defines documented ops contracts for modulation update requests and neuromodulator state publication.
3. The contract surface models independent neuromodulator channels instead of a fused vector.
4. The requirement package records the confirmed baseline input mapping, allowed initialization priors, learned-parameter categories, default decay family, and hard/soft gate scope.
5. The requirement package records only truly unresolved parameter-model semantics as explicit confirmation gates rather than fixed implementation assumptions.
6. No test or implementation path demonstrates fallback fusion or degraded heuristic substitution.