# Requirement 37 - Neuromodulatory gating coupling (P3 third de-shim)

## 1. Background and Problem

R36 made the `04` neuromodulator owner's levels a real deterministic function of the `03` appraisal batch (under the semantic-memory assembly): higher novelty/uncertainty raises norepinephrine, higher reward raises dopamine, higher threat raises cortisol. But that real `04` state currently dies one stage later, exactly the same way the real `03` novelty signal died at the `04` boundary before R36.

The `09` thought-gating owner's `FirstVersionThoughtGatePath` computes its gate score from a normalized `ThoughtGateSignalSnapshot`. One of its terms is `global_activation_level * 0.20` — a real, owned input slot that already represents "how globally activated is the system this tick". The problem is upstream: composition's `FirstVersionThoughtGateSignalBridge` fills `global_activation_level` with a hardcoded constant `0.9` every tick. So no matter what `04` produces, the gating owner sees the same activation, and the real norepinephrine signal has no causal downstream effect.

This is the open half of `gap_behavioral_consequence_binding` and the modulation-weakness note in `BRAIN_ARCHITECTURE_COMPARISON.md` (the `03-07` row, post-R36): "`04` is now appraisal-derived but ... its levels are not yet coupled into a de-shimmed `05` feeling or `09` gating, so modulation still influences later owners more weakly than a strong biological analog would imply". `brain.mmd` models norepinephrine as a primary arousal/alerting driver of selective ignition: higher locus-coeruleus norepinephrine tone biases the system toward engaging rather than idling. The substrate to make this real already exists — `04`'s `NeuromodulatorStageResult` (with its `levels.norepinephrine`) is in `frame.stage_results` before `09` runs, because the canonical stage order is `02→03→04→05→06→07→08→09`. No stage reordering is needed.

R37 is the third P3 cognitive-owner de-shim. It couples the real `04` norepinephrine level into the `09` gate decision so that, under the semantic-memory assembly, a tick with elevated neuromodulatory arousal is measurably more likely to fire (and a low-arousal tick less likely), while keeping the gating policy semantic firmly inside the `09` owner. Per the locked selection principle in `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 14, `09` couples through a deterministic, explainable, bounded rule rather than a black-box NN.

This slice is intentionally narrow. It couples one channel (norepinephrine, the canonical arousal driver) into one consumer (`09` gating) through one bounded rule. The cortisol/inhibition hard-gate-eligibility channels that `04` already reserves (`hard_gate_eligibility_channels=("cortisol","inhibition")`) are a separate later slice; coupling `04` into `05` feeling is a separate later slice; the other four `03` dimensions remain first-version constants as in R36.

## 2. Goal

Couple the real `04` neuromodulator state into the `09` thought-gating decision: when neuromodulatory gating coupling is enabled, composition forwards the `04` norepinephrine level into the gate-signal snapshot as a raw bounded arousal fact, and the `09` owner maps that fact into its gate evaluation through an owner-owned bounded rule, so that elevated neuromodulatory arousal measurably and traceably raises the tick's fire propensity while `09` keeps sole ownership of gating policy, the coupling stays deterministic and bounded (no NN, never single-handedly forcing or suppressing a fire), the rule reads no prior-tick state, and the default assembly stays unchanged.

## 3. Functional Requirements

### 3.1 Owner-owned arousal fact on the gate-signal contract
1. The `09` `ThoughtGateSignalSnapshot` must gain one additive, optional raw input field `neuromodulatory_arousal: float | None` (default `None`), validated to `[0.0, 1.0]` when present. It is a raw fact (the forwarded neuromodulator arousal level), not a gate score and not a salience value.
2. The field must be optional so that an assembly which does not provide it (the default, recency-only, and offline assemblies) produces a snapshot byte-for-byte equivalent to today's behavior, and the existing gate path must treat `None` exactly as today (no arousal coupling).
3. Composition must forward only the raw `04` norepinephrine level into this field. Composition must not pre-map it into an activation score or a fire propensity; the mapping from arousal fact to gate influence is the `09` owner's decision.

### 3.2 Owner-owned bounded coupling rule
1. The `09` owner must gain a gate path (an `arousal`-aware path) that, when `neuromodulatory_arousal` is present, adds a distinct bounded arousal contribution to the gate score. The arousal contribution must be a separate term with its own bounded weight; it must not replace, overwrite, or reinterpret the existing `global_activation_level` input (which remains its own, separately-owned, still-first-version input in this slice). The mapping (arousal fact -> gate-score contribution) must live in the `09` owner, not in composition glue.
2. The coupling must be bounded and monotonic: a higher `neuromodulatory_arousal` must not decrease the gate score, and the arousal contribution must be a non-negative term whose weight is small enough that it can never by itself force a fire (it cannot push a sub-threshold tick over the threshold when every other signal is absent) nor, being additive and non-negative, ever suppress a fire that all other signals already justify. The coupling adjusts propensity within bounds; it is not a hard gate.
3. When `neuromodulatory_arousal` is `None`, the path must behave exactly as the first-version path does today (the arousal term is absent), so non-coupled assemblies are unchanged.
4. The gate result's `contributing_signals` must record the raw arousal fact as an explicit named signal when coupling is active, so the influence is observable through the existing contract (no new logging mechanism).

### 3.3 Real downstream effect
1. The coupling must be observable end to end: under the coupled assembly, two ticks whose `04` norepinephrine differs (driven by differing `03` novelty/uncertainty, as established by R35/R36) must produce a measurably different gate score on the arousal-contributing signal, attributable to the real neuromodulator level rather than a constant.
2. The gate result and continuation-pressure contracts must be otherwise unchanged; the coupling flows through the existing `ThoughtGateResult`/`ContinuationPressureState` shapes with no contract break for downstream owners.

### 3.4 Opt-in rollout and statelessness
1. Neuromodulatory gating coupling must be enabled in the assembly variant where `04` already produces real levels (the semantic-memory assembly, the same opt-in as R35/R36). The default and recency-only assemblies must keep the constant `global_activation_level` and behave exactly as today.
2. This slice is stateless: the coupling rule must not read or carry prior-tick gate or neuromodulator state. It derives the arousal contribution from the current snapshot only.
3. There is no fallback path: when coupling is enabled the arousal fact is forwarded every tick from the real `04` result. A missing or malformed `04` stage result is the existing runtime stage error (fail-fast), not a degraded uncoupled mode.

## 4. Non-Functional Requirements

1. Performance: the coupling is one bounded arithmetic mapping per tick; it adds no stage and does not change the stage chain structure or order.
2. Reliability and fault tolerance: for an identical snapshot the gate score must be deterministic and independent of wall-clock time, and the arousal contribution must never push the gate score outside `[0.0, 1.0]` (clamped consistent with the existing contract).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. The arousal contribution travels only through the existing `ThoughtGateResult.contributing_signals` map.
4. Compatibility and migration: the new `ThoughtGateSignalSnapshot` field is additive and optional. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant activation input and their current `09` behavior.

## 5. Code Behavior Constraints

1. The thought-gating owner stays the sole owner of gating policy. The arousal-to-gate mapping must live in an owner-private `09` gate path, not in composition glue. Composition may only forward the raw `04` norepinephrine level as a bounded fact.
2. Composition must read the `04` `NeuromodulatorStageResult` from the already-available stage results for the current tick; it must not reorder stages, must not reach into neuromodulator owner internals beyond the public `NeuromodulatorState.levels`, and must not import the gate path's policy.
3. The coupling must be a deterministic bounded rule (clamped linear/blended contribution). No black-box NN, no hidden runtime strategy branch, no prior-tick state read, and no divergence outside `[0.0, 1.0]`.
4. The arousal coupling must never act as a hard gate by itself: it cannot solely force a fire on an otherwise sub-threshold tick, nor solely suppress a fire that other signals justify. Hard-gate eligibility (cortisol/inhibition) remains out of scope.
5. No degraded or fallback path: when enabled, the arousal fact is forwarded every tick. When disabled, the field is absent and the path is unchanged.
6. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/thought_gating/contracts.py` (add the optional `neuromodulatory_arousal` field to `ThoughtGateSignalSnapshot` with `[0,1]` validation)
2. `helios_v2/src/helios_v2/thought_gating/engine.py` (an arousal-aware gate path that owns the arousal-to-gate-score mapping; the first-version path's `None` behavior is preserved)
3. `helios_v2/src/helios_v2/thought_gating/__init__.py` (export the new gate path if public to composition)
4. `helios_v2/src/helios_v2/composition/bridges.py` (a neuromodulator-arousal-aware gate-signal bridge that reads the `04` `NeuromodulatorStageResult` from the frame and forwards `levels.norepinephrine` as the raw arousal fact; the first-version bridge is unchanged)
5. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (select the arousal-aware gate path and the arousal-forwarding signal bridge in the semantic-memory assembly; keep the constant bridge and first-version path otherwise)
6. `helios_v2/tests/test_thought_gating_engine.py` (extend: arousal raises gate score monotonically; bounded so it cannot solely force/suppress a fire; `None` behaves as today; determinism)
7. `helios_v2/tests/test_thought_gating_contracts.py` (extend: optional field validation and default `None`)
8. `helios_v2/tests/test_runtime_composition.py` (extend: coupled assembly produces a different arousal-contributing gate signal across two ticks differing in novelty; default assembly unchanged)
9. `helios_v2/docs/requirements/index.md`
10. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
11. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
12. `helios_v2/docs/OWNER_GUIDE.md`
13. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
14. `helios_v2/docs/PROGRESS_FLOW.en.md`
15. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. The `09` `ThoughtGateSignalSnapshot` carries an optional `neuromodulatory_arousal` raw fact validated to `[0,1]`; when absent the snapshot and the gate decision are byte-for-byte equivalent to today's first-version behavior.
2. Under the coupled (semantic-memory) assembly, composition forwards the real `04` norepinephrine level into that field every tick; it does not pre-map it into a score, and `09` owns the arousal-to-gate mapping.
3. A higher `neuromodulatory_arousal` yields a gate score no lower than a lower one (monotonic, deterministic for identical inputs), and the arousal contribution is a distinct bounded non-negative term (it does not overwrite `global_activation_level`) so it can neither solely force a fire on an otherwise sub-threshold tick nor solely suppress a fire that other signals justify.
4. The gate result records the arousal contribution as a named entry in `contributing_signals` when coupling is active, so the influence is observable through the existing contract without any new logging mechanism.
5. Under the coupled assembly, two ticks whose `04` norepinephrine differs (via differing `03` novelty/uncertainty) produce a measurably different arousal-contributing gate signal, attributable to the real level rather than a constant.
6. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant activation input and their current `09` behavior; their existing tests pass unmodified.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R37 couples one channel (norepinephrine) into one consumer (`09` gating) through one bounded stateless rule. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Cortisol/inhibition hard-gate-eligibility coupling: the `04` config already reserves `hard_gate_eligibility_channels=("cortisol","inhibition")`; wiring a real stress/inhibition gate into `09` (which may legitimately suppress a fire) is a separate slice with its own safety semantics.
2. Coupling the real `04` state into a de-shimmed `05` feeling layer (the sibling de-shim of `04`'s other downstream consumer).
3. Coupling additional `04` channels (dopamine into retrieval/exploration drive, acetylcholine into precision) into their appropriate consumers.
4. Dual-timescale `04` dynamics (prior-tick carry) so the arousal feeding `09` reflects tonic/phasic history, not just the current tick.
5. P5 learning of the `09` coupling coefficient and the gate policy thresholds (the `gate_policy` learned-parameter category the config already declares), replacing the first-version constant without changing the rule shape.
6. De-shimming the remaining four `03` dimensions so all neuromodulator drivers feeding the coupling are real.
7. De-shimming the `09` gate-signal snapshot's other still-constant composition-provided inputs (`global_activation_level`, `workload_pressure`, `temporal_signal`, `drive_urgency_signal`, `dmn_available`) from their real owners (for example `global_activation_level` from a de-shimmed `07` workspace), each as its own slice; R37 deliberately leaves them untouched and only adds the new arousal term.

None of these may be smuggled into this slice. R37 introduces no prior-tick state, no NN, no new logging mechanism, no hard gate, and changes no owner's contract beyond one additive optional input field; it only makes the `09` gate decision a real bounded function of the `04` arousal level.
