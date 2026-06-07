# Requirement 63 - Real Selected-Stimuli Projection and Default-Assembly Ignition Source

## 1. Background and Problem

The `09` thought-gate score is a weighted sum of normalized signals. After R37/R48/R53/R55/R62, all
gate inputs except `selected_stimuli` are real (arousal, workspace activation, workload pressure,
temporal/DMN, prior-tick drive urgency). `selected_stimuli` is the gate's last constant input:
both `FirstVersionThoughtGateSignalBridge` and `NeuromodulatorAwareThoughtGateSignalBridge`
hardcode `stimulus_intensity=0.9`, `novelty_signal=0.6`, `sensitization_signal=0.2` every tick.

`stimulus_signal` (the max `stimulus_intensity` across `selected_stimuli`) carries the largest
positive weight in the gate formula (`* 0.30`, tied with continuation). The real source exists:
the `03` rapid salience appraisal runs before `09` and publishes a `RapidSalienceAppraisalBatch`
whose per-stimulus `RapidSalienceVector` includes an `aggregate` (overall coarse salience judgment),
`novelty`, and `uncertainty`. The R61 mismatch bridge already reads this batch from
`frame.stage_results["rapid_salience_appraisal"]` — the pattern and data path are established.

However, projecting the real `03` aggregate into `stimulus_intensity` surfaces a deeper problem
(first identified during R62 and explicitly deferred here): under the default (non-semantic)
assembly, the `03` `FirstVersionAggregateEstimator` returns a constant `0.4` (a deliberately low
first-version coarse judgment). Projecting that real `0.4` as `stimulus_intensity` drops the gate
score from the current `~0.925` to `~0.475`, below the `0.55` fire threshold, flipping the default
runtime to no-fire — breaking approximately 17 fired-path tests that depend on the default assembly
firing. That flip is architecturally honest (a weak constant-`0.4` appraisal should not fire every
tick), but it exposes the real problem: the default assembly has no genuine high-salience ignition
source. In a brain, even at rest, the reticular activating system and the default-mode network
provide a baseline activation that keeps the system responsive. The default assembly's appraisal
chain has no equivalent — its aggregate judgment is too low to cross the gate threshold the owner
set.

The `09` owner's fire threshold (`0.55`) and weights are correct and must not be patched to
accommodate a shim removal (that would violate owner-boundary discipline). The fix belongs in the
default assembly's appraisal: raising `FirstVersionAggregateEstimator` from `0.4` to a moderate
baseline that honestly represents "a first-version system with no real salience grounding still
attributes moderate significance to its percept" — enough to cross the gate threshold when the
other real signals contribute, but not so high as to fire on appraisal alone.

## 2. Goal

Ground the `09` gate's `selected_stimuli` projection in the real same-tick `03` appraisal (batch-max
`aggregate` → `stimulus_intensity`, batch-max `novelty` → `novelty_signal`, batch-max `uncertainty`
→ `sensitization_signal`), and raise the default assembly's `FirstVersionAggregateEstimator` from
`0.4` to a moderate baseline (`0.7`) that provides an honest first-version ignition source — so
the default gate still fires under real appraisal while the `09` owner's threshold and weights stay
untouched. After R63, every `09` gate input is real; no constant shim remains in the gate signal.

## 3. Functional Requirements

### 3.1 Selected-stimuli projection from the real `03` appraisal

1. Both gate-signal bridges (`FirstVersionThoughtGateSignalBridge` and
   `NeuromodulatorAwareThoughtGateSignalBridge`) must read the `03`
   `RapidSalienceAppraisalStageResult` from `frame.stage_results` (the same path the R61 mismatch
   bridge already uses) and project the batch-max salience into `SelectedStimulusSummary`:
   `stimulus_intensity` = batch-max `aggregate`, `novelty_signal` = batch-max `novelty`,
   `sensitization_signal` = batch-max `uncertainty`.
2. The projection must be a raw bounded fact: each value is clamped to `[0,1]` and rounded for
   determinism. Composition forwards the published `03` values; it does not compute a gate score
   or re-derive the appraisal.
3. If the `03` appraisal result is absent from the frame (e.g. an assembly that does not run the
   appraisal stage), the bridge must fall back to documented cold-start constants — not crash and
   not fabricate a high stimulus.

### 3.2 Default-assembly honest ignition source

1. `FirstVersionAggregateEstimator.estimate_aggregate` must return `0.7` (raised from `0.4`), a
   moderate baseline that honestly represents "a first-version system attributes moderate
   significance to its percept" — enough to contribute to gate firing alongside the other real
   signals (global activation, temporal, drive urgency, DMN), but not enough to fire on appraisal
   alone (`0.7 * 0.30 = 0.21 < 0.55`). The default-assembly cold-start gate score with the
   raised aggregate is `~0.555`, just above the `0.55` fire threshold.
2. The change must affect only the default/recency assemblies (which use
   `FirstVersionAggregateEstimator`). The semantic assembly uses `WeightedAggregateEstimator`
   (R41) and is unaffected.

### 3.3 Behavioral scope

1. The change must affect only the `selected_stimuli` projection and the
   `FirstVersionAggregateEstimator` constant. The `09` gate decision policy, weights, thresholds,
   and the other inputs (all real after R37/R48/R53/R55/R62) are unchanged.
2. Under the default assembly with the raised aggregate, the gate score on a cold-start tick must
   remain above the `0.55` fire threshold, preserving the existing fired-path behavior.

## 4. Non-Functional Requirements

1. Performance: no measurable per-tick overhead beyond reading one stage result from the frame and
   computing three max operations over the appraisal batch.
2. Reliability: an absent `03` appraisal result falls back to documented constants; no new failure
   branch, no fabricated high stimulus.
3. Observability and logging: no new logging mechanism; the `21` owner stays the single logging
   mechanism and the ad-hoc-logging guard stays green.
4. Compatibility and migration: the `09` `ThoughtGateSignalSnapshot` contract is unchanged in shape.
   The `selected_stimuli` projection source changes from a composition-injected constant to a
   composition-projected real value. The default assembly's gate still fires on tick 1 (the raised
   aggregate plus the other real signals exceed the threshold).

## 5. Code Behavior Constraints

1. Forbidden: the hardcoded `stimulus_intensity=0.9` / `novelty_signal=0.6` /
   `sensitization_signal=0.2` constants in the gate-signal bridges once the projection lands,
   except as the documented fallback when no `03` appraisal result is present.
2. Forbidden: fabricating a stimulus intensity not derived from the real `03` appraisal
   (`ARCHITECTURE_PHILOSOPHY` §4.3/§8); the documented cold-start fallback is the only non-real
   value.
3. Forbidden: changing the `09` gate's fire threshold or weights to accommodate the shim removal
   (owner-boundary discipline — the threshold belongs to the `09` owner).
4. Boundary rule: composition projects the batch-max `03` salience values (clamped) into the gate
   signal snapshot; the `09` owner keeps the gate weights and decision policy.
5. Failure mode: absent `03` appraisal result → documented fallback constants; empty appraisal
   batch → documented fallback constants.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/composition/bridges.py` — add `_selected_stimuli_from_appraisal(frame,
   tick_id)` helper; both gate-signal bridges call it for `selected_stimuli` (replacing the
   hardcoded constants); raise `FirstVersionAggregateEstimator` from `0.4` to `0.7`.
2. `helios_v2/tests/test_runtime_composition.py` — tests for real appraisal projection, absent
   appraisal fallback, and default-assembly gate firing with the raised aggregate.
3. `helios_v2/tests/test_appraisal_engine.py` — update any tests asserting the old `0.4` aggregate
   constant.
4. Documentation: `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`,
   `docs/OWNER_GUIDE.zh-CN.md`, `docs/PROGRESS_FLOW.en.md`, `docs/PROGRESS_FLOW.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md`.

## 7. Acceptance Criteria

1. `selected_stimuli` `stimulus_intensity` on each tick equals the batch-max `03` appraisal
   `aggregate` (clamped), not the constant `0.9`; `novelty_signal` equals the batch-max `novelty`;
   `sensitization_signal` equals the batch-max `uncertainty`.
2. Under the default assembly, the gate score on a cold-start tick exceeds the `0.55` fire
   threshold and the gate decides `fire` (the raised `FirstVersionAggregateEstimator` `0.7`
   provides sufficient ignition alongside the other signals).
3. The `09` gate decision policy, weights, and thresholds are unchanged (their tests stay green).
4. The semantic assembly's `WeightedAggregateEstimator` is unaffected (its tests stay green).
5. The full network-free suite is green; owner-boundary and ad-hoc-logging guards stay green.
6. `index.md` has a row 63; the `09` `OWNER_GUIDE` entries record that all gate inputs are now
   real (no constant shim remains); the `BRAIN_ARCHITECTURE_COMPARISON` note records the
   completion; sync lines name R63.
