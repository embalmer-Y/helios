# Requirement 38 - Neuromodulator-derived feeling (P3 fourth de-shim)

## 1. Background and Problem

R36 made the `04` neuromodulator owner's levels a real deterministic function of the `03` appraisal batch (under the semantic-memory assembly), and R37 coupled the real `04` norepinephrine level into the `09` gate decision. The `04` owner has two immediate downstream consumers in the canonical chain: `09` thought gating (now real, R37) and `05` interoceptive feeling. The `05` consumer is still a constant shim, so half of `04`'s real downstream effect is still missing.

The `05` feeling owner is fully built: its `update_state(neuromodulator_state, internal_signals, tick_id)` already receives the complete `04` `NeuromodulatorState` every tick (the `InteroceptiveFeelingRuntimeStage` passes the `neuromodulator_system` stage result's `state` in directly). Its contracts, validation, ops, and tests are all real. The only shim is the injected construction path: `FirstVersionFeelingConstructionPath.construct_feeling` does `del neuromodulator_state, internal_signals, config, tick_id` and returns a fixed 7-dimensional `InteroceptiveFeelingVector` (valence=0.4, arousal=0.7, tension=0.5, comfort=0.2, fatigue=0.3, pain_like=0.1, social_safety=0.4) every tick. So no matter what `04` produces, the body-feeling vector is constant, and the real neuromodulator state dies at the `05` boundary exactly the way the real novelty signal died at `04` before R36 and the real `04` arousal died at `09` before R37.

This is the `05` half of the modulation-weakness note in `BRAIN_ARCHITECTURE_COMPARISON.md` (the `03-07` row, post-R37): "`04` is now appraisal-derived ... only its norepinephrine->`09` arousal coupling is real (the `05` feeling layer ... is not yet coupled)". `brain.mmd` models interoceptive feeling as the subjective read-out of body/neuromodulatory state: dopamine/opioid/serotonin tone reads as positive valence and comfort, cortisol as tension and pain-like stress, norepinephrine as arousal, oxytocin as social safety. The standard functional reading is that the affective body-feeling vector is a bounded transformation of the modulatory state. With `04` now producing a real state, the substrate to derive a real `05` feeling already exists in the contract `05` already consumes (`NeuromodulatorState.levels`).

R38 is the fourth P3 cognitive-owner de-shim, and it brings `04`'s second downstream consumer to real. Per the locked selection principle in `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 14, `05` uses a deterministic, explainable, bounded equation (a clamped linear mapping from neuromodulator channels to feeling dimensions around the configured baseline) rather than a black-box NN. Because `05`'s entire reason to exist is subjectivizing neuromodulator state into feeling, the mapping is owned by the `05` owner itself (an owner-private construction path), not by composition glue.

This slice is intentionally stateless: it derives the feeling vector from the current neuromodulator state plus the configured baseline, without carrying prior-tick feeling across ticks. True dual-timescale feeling persistence (the declared `feeling_persistence` category, carrying prior feeling) requires a carried feeling-state checkpoint (the same family as the `18`/`09`/`14`/`04` state-checkpoint problem) and is a separate later slice. Integrating real internal body/interoceptive signals (the `internal_signals` argument) is also a separate later slice; no real interoceptive signal flows yet.

## 2. Goal

Replace the constant feeling construction path with a deterministic neuromodulator-derived one owned by the `05` feeling owner: when neuromodulator-derived feeling is enabled, `05` computes each tick's interoceptive feeling vector from the real `04` `NeuromodulatorState.levels` around the configured baseline feeling, using explicit bounded per-dimension coupling coefficients and clamping every dimension into its legal range, so that the real `04` state (dopamine, norepinephrine, cortisol, serotonin, oxytocin, opioid tone, etc.) measurably and traceably shapes the subjective body-feeling vector, while `05` keeps sole ownership of feeling subjectivation, the derivation stays deterministic and bounded (no NN, no divergence), reads no prior-tick feeling, and the default assembly stays unchanged.

## 3. Functional Requirements

### 3.1 Deterministic neuromodulator-derived construction path
1. A new neuromodulator-derived `FeelingConstructionPath` must compute the `InteroceptiveFeelingVector` from the validated `NeuromodulatorState.levels` and the owner `InteroceptiveFeelingConfig`, replacing the constant shim. It must consume the real neuromodulator levels; it must not ignore them.
2. Each feeling dimension's value must be `clamp(baseline_dimension + sum(coupling_k * (level_k - level_reference_k)), legal_min_dimension, legal_max_dimension)`, where the channel inputs and their per-dimension coupling coefficients are explicit and bounded, and the result is clamped into the configured legal range for that dimension. At minimum the documented mapping must include:
   - valence driven up by dopamine, opioid tone, and serotonin, and down by cortisol;
   - arousal driven up by norepinephrine and excitation;
   - tension driven up by cortisol and norepinephrine;
   - comfort driven up by opioid tone, oxytocin, and serotonin, and down by cortisol;
   - pain_like driven up by cortisol and down by opioid tone;
   - social_safety driven up by oxytocin and serotonin, and down by cortisol;
   - fatigue driven up by inhibition and down by excitation (a weak first-version coupling; real fatigue needs cross-tick accumulation and is deferred).
3. Every produced dimension must lie within `[legal_min, legal_max]` for that dimension (enforced by clamping, consistent with the `InteroceptiveFeelingVector` and config contracts), and must be deterministic given the same neuromodulator state and config.
4. The derivation must read only the neuromodulator levels and the owner config; it must not read prior-tick feeling state in this slice.

### 3.2 Bounded, future-learnable coefficients
1. The per-dimension coupling coefficients must be explicit first-version bounded constants, organized under the learned-parameter categories the `InteroceptiveFeelingConfig` already declares (`feeling_mapping_strength`, `feeling_coupling_strength`, `feeling_persistence`). They are deterministic now and are the surface a later P5 learning slice tunes; they must not be a black-box model.
2. The construction path must not introduce any new runtime strategy branch keyed on hardcoded content; the mapping is a fixed bounded linear combination plus clamping.

### 3.3 Real downstream effect
1. The derived feeling must flow through the existing `InteroceptiveFeelingState`/`InteroceptiveFeelingVector` contracts unchanged, so `06` memory-affect and any later consumer receive it through the existing boundary with no contract change.
2. The change must be observable: two ticks whose `04` neuromodulator states differ in a driving channel (for example a high-cortisol state vs a low-cortisol state) must produce measurably different feeling on the corresponding dimension (tension/pain_like for cortisol, arousal for norepinephrine, valence for dopamine). The difference must be attributable to the real neuromodulator state, not a constant.

### 3.4 Opt-in rollout and statelessness
1. Neuromodulator-derived feeling must be enabled in the assembly variant where `04` already produces real levels (the semantic-memory assembly, the same opt-in as R35/R36/R37); the default and recency-only assemblies keep the constant construction path and behave exactly as today.
2. This slice is stateless: the construction path must not read or carry prior-tick feeling. It derives from the current neuromodulator state plus the configured baseline only. True dual-timescale feeling persistence (carrying prior feeling) is explicitly out of scope and is a later slice.
3. There is no fallback path: the derivation is a total deterministic function of the neuromodulator levels and config. A malformed neuromodulator state fails before the construction path (existing `05` validation); the construction path itself does not branch into a degraded mode.
4. Real internal body/interoceptive signal integration (the `internal_signals` argument) is out of scope; the path may accept the argument for contract compatibility but must base this slice's derivation on the neuromodulator state.

## 4. Non-Functional Requirements

1. Performance: derivation is one bounded linear combination per dimension per tick; it does not change runtime stage structure.
2. Reliability and fault tolerance: for an identical neuromodulator state and config, the produced feeling must be deterministic and independent of wall-clock time, and must never exceed the legal range (no divergence).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Feeling travels only through the existing feeling contracts.
4. Compatibility and migration: the neuromodulator-derived construction path and its wiring are additive. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant construction path and their current `05` behavior.

## 5. Code Behavior Constraints

1. The interoceptive feeling owner stays the sole owner of feeling subjectivation. The neuromodulator-derived construction path is an owner-private `FeelingConstructionPath` implementation inside `helios_v2.feeling`; the owner engine, contracts, and the constant path are unchanged. Composition selects the owner-provided path under the opt-in; it does not compute feeling values itself.
2. The construction path must consume only the `NeuromodulatorState` it is given plus the owner config. It must not import or reach into other owners' state, must not read prior-tick feeling in this slice, and must not produce memory or action semantics (those are `06`/later owners).
3. The derivation must be a deterministic bounded equation (linear combination + clamp). No black-box NN, no hidden runtime strategy branch, no divergence outside the legal range.
4. No degraded or fallback path: the construction path is total over valid neuromodulator states; a malformed state is rejected by the existing owner validation before the path runs.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/feeling/engine.py` (a neuromodulator-derived `FeelingConstructionPath` implementation owned by the `05` owner; the engine and protocols are unchanged) and `helios_v2/src/helios_v2/feeling/__init__.py` (export the new path for composition)
2. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (select the neuromodulator-derived construction path in the semantic-memory assembly; keep the constant path otherwise)
3. `helios_v2/src/helios_v2/composition/bridges.py` (only if a thin selection import is needed; the `FirstVersionFeelingConstructionPath` constant shim stays for the default assembly)
4. `helios_v2/tests/test_interoceptive_feeling_engine.py` (extend: channel-driven feeling, determinism, range, baseline at reference levels)
5. `helios_v2/tests/test_runtime_composition.py` (extend: high-cortisol vs low-cortisol tick produces different tension/pain_like; default assembly unchanged)
6. `helios_v2/docs/requirements/index.md`
7. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
8. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
9. `helios_v2/docs/OWNER_GUIDE.md`
10. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
11. `helios_v2/docs/PROGRESS_FLOW.en.md`
12. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. `05` computes the interoceptive feeling vector from the real `04` neuromodulator state when neuromodulator-derived feeling is enabled, via an owner-private `FeelingConstructionPath` that consumes the state (it does not ignore it); the owner engine and contracts are unchanged.
2. A high-cortisol neuromodulator state yields measurably higher tension and pain_like (and lower valence/comfort) than a low-cortisol state; a high-dopamine state yields higher valence; a high-norepinephrine state yields higher arousal; the differences are attributable to the real neuromodulator state, not a constant.
3. Every produced feeling dimension lies within its `[legal_min, legal_max]` range, is deterministic for identical inputs, and flows through the unchanged `InteroceptiveFeelingState`/`InteroceptiveFeelingVector` contracts.
4. The per-dimension coupling coefficients are explicit bounded first-version constants under the config's declared learned-parameter categories; the derivation is a linear combination plus clamp, with no black-box model and no prior-tick feeling read.
5. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant construction path and their current `05` behavior; their existing tests pass unmodified.
6. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R38 de-shims `05` to a stateless deterministic neuromodulator-derived model. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Dual-timescale feeling persistence that carries prior-tick feeling across ticks (the declared `feeling_persistence` category; depends on a feeling-state carry/checkpoint, the same family as the `18`/`09`/`14`/`04` state-checkpoint slice).
2. Integrating real internal body/interoceptive signals (the `internal_signals` argument) into feeling construction once a real interoceptive signal source exists.
3. P5 learning of the bounded coupling coefficients via outcome feedback, replacing the first-version constants without changing the equation shape.
4. Feeding the real `05` feeling state into downstream consumers so feeling measurably shapes `06` memory-affect tagging, conscious content, and behavior (FG-2), beyond the existing structural flow.
5. De-shimming the remaining four `03` dimensions and `04`'s dual-timescale dynamics so all upstream drivers of feeling are real, not just novelty.

None of these may be smuggled into this slice. R38 introduces no prior-tick state, no NN, no new logging mechanism, and changes no owner's contract; it only makes the `05` feeling a real deterministic function of the `04` neuromodulator state.
