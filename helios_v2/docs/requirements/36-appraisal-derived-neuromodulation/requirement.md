# Requirement 36 - Appraisal-derived neuromodulation (P3 second de-shim)

## 1. Background and Problem

R35 made the `03` appraisal owner's `novelty` dimension a real signal. The immediate downstream consumer of `03` is the `04` neuromodulator owner, which is still `baseline_real` with a composition-injected shim: `FirstVersionNeuromodulatorUpdatePath.update_levels` ignores its `batch` argument entirely (`del batch, config, tick_id`) and returns a fixed constant `NeuromodulatorLevels` for every tick. The owner, its `NeuromodulatorState`/`NeuromodulatorLevels` contracts, its validation, and its tests are all real; the levels flowing out of it are not.

This means the real novelty signal R35 just produced dies at the `04` boundary: no matter what `03` appraises, `04` emits the same constant dopamine/norepinephrine/cortisol/etc. The `gap_persistence_and_learning` and the modulation gap in `BRAIN_ARCHITECTURE_COMPARISON.md` both note that modulation influences later owners more weakly than a biological analog implies, precisely because `04` is a constant.

`brain.mmd` models neuromodulators as fast-path appraisal-driven signals: dopamine tracks reward, norepinephrine tracks novelty/uncertainty/alertness, cortisol tracks threat/stress. The standard functional reading is that coarse salience drives the modulatory state. With `03` now producing a real novelty signal (and the other four dimensions present as bounded values), the substrate to derive a real `04` state from appraisal already exists in the contract `04` already consumes (`RapidAppraisalBatch`).

R36 is the second P3 cognitive-owner de-shim. It replaces the constant neuromodulator update path with a deterministic appraisal-derived dynamics model: the next neuromodulator levels are computed from the batch's coarse salience around the configured tonic baseline, with explicit bounded sensitivity coefficients (the learned-parameter categories the config already declares, learnable later in P5). Per the locked selection principle in `ARCHITECTURE_PHILOSOPHY.zh-CN.md` section 14, `04` uses a deterministic, explainable, non-diverging equation rather than a black-box NN.

This slice is intentionally stateless: it derives levels from the current appraisal plus the configured tonic baseline, without carrying prior-tick levels across ticks. True dual-timescale tonic/phasic decay requires a carried levels state (the same cross-tick state-checkpoint problem as `18`/`09`/`14`) and is a separate later slice.

## 2. Goal

Replace the constant neuromodulator update path with a deterministic appraisal-derived one: when appraisal-derived neuromodulation is enabled, `04` computes each tick's neuromodulator levels from the rapid-appraisal batch's coarse salience around the configured tonic baseline, using explicit bounded per-channel sensitivity coefficients and clamping every channel into its legal range, so that real `03` salience (especially the R35 novelty signal) measurably and traceably shapes the neuromodulator state, while `04` keeps sole ownership of modulation, the derivation stays deterministic and bounded (no NN, no divergence), and the default assembly stays unchanged.

## 3. Functional Requirements

### 3.1 Deterministic appraisal-derived update path
1. A new appraisal-derived `NeuromodulatorUpdatePath` must compute `NeuromodulatorLevels` from the validated `RapidAppraisalBatch` and the owner `NeuromodulatorConfig`, replacing the constant shim. It must consume the batch's real salience values; it must not ignore the batch.
2. The derivation must aggregate a multi-appraisal batch deterministically into one coarse salience vector before mapping to channels. The aggregation is the per-dimension maximum across the batch's appraisals (the most salient stimulus drives modulation); an empty batch uses the tonic baseline directly.
3. Each channel's next level must be `clamp(tonic_baseline_channel + sum(sensitivity_k * salience_k), legal_min_channel, legal_max_channel)`, where the salience inputs and their per-channel sensitivity coefficients are explicit and bounded. At minimum the documented mapping must include:
   - dopamine driven up by reward (and weakly by novelty as exploration drive);
   - norepinephrine driven up by novelty and uncertainty (alertness);
   - cortisol driven up by threat;
   - other channels regress toward their tonic baseline (zero or small bounded sensitivity in this slice).
4. Every produced level must lie within `[legal_min, legal_max]` for its channel (enforced by clamping, consistent with the `NeuromodulatorLevels` contract), and must be deterministic given the same batch and config.

### 3.2 Bounded, future-learnable coefficients
1. The per-channel sensitivity coefficients must be explicit first-version bounded constants, organized under the learned-parameter categories the `NeuromodulatorConfig` already declares (`channel_gain_sensitivity`, `cross_channel_coupling_strength`, `decay_speed_persistence`, `gate_influence_strength`). They are deterministic now and are the surface a later P5 learning slice tunes; they must not be a black-box model.
2. The update path must not introduce any new runtime strategy branch keyed on hardcoded content; the mapping is a fixed bounded linear combination plus clamping.

### 3.3 Real downstream effect
1. The derived levels must flow through the existing `NeuromodulatorState`/`NeuromodulatorLevels` contracts unchanged, so `05` feeling and any later consumer receive them through the existing boundary with no contract change.
2. The change must be observable: two ticks whose appraisal batches differ in a driving dimension (for example a high-novelty batch vs a low-novelty batch) must produce measurably different neuromodulator levels on the corresponding channel (norepinephrine for novelty). The difference must be attributable to real salience, not a constant.

### 3.4 Opt-in rollout and statelessness
1. Appraisal-derived neuromodulation must be enabled in the assembly variant where `03` already produces real signals (the semantic-memory assembly, where R35 novelty is real); the default and recency-only assemblies keep the constant update path and behave exactly as today.
2. This slice is stateless: the update path must not read or carry prior-tick levels. It derives from the current batch plus the configured tonic baseline only. True dual-timescale decay (carrying prior levels) is explicitly out of scope and is a later slice.
3. There is no fallback path: the derivation is a total deterministic function of the batch and config. A malformed batch fails before the update path (existing `04` validation); the update path itself does not branch into a degraded mode.

## 4. Non-Functional Requirements

1. Performance: derivation is one bounded linear combination per channel per tick; it does not change runtime stage structure.
2. Reliability and fault tolerance: for an identical appraisal batch and config, the produced levels must be deterministic and independent of wall-clock time, and must never exceed the legal range (no divergence).
3. Observability and logging: this requirement must not introduce a second logging mechanism and must not use `logging` or `print`. Levels travel only through the existing neuromodulator contracts.
4. Compatibility and migration: the appraisal-derived update path and its wiring are additive. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant update path and their current `04` behavior.

## 5. Code Behavior Constraints

1. The neuromodulator owner stays the sole owner of modulation. The appraisal-derived update path is injected through the existing `NeuromodulatorUpdatePath` protocol; the owner engine is unchanged.
2. The update path must consume only the `RapidAppraisalBatch` it is given plus the owner config. It must not import or reach into other owners' state, must not read prior-tick levels in this slice, and must not produce feeling or action semantics (those are `05`/later owners).
3. The derivation must be a deterministic bounded equation (linear combination + clamp). No black-box NN, no hidden runtime strategy branch, no divergence outside the legal range.
4. No degraded or fallback path: the update path is total over valid batches; a malformed batch is rejected by the existing owner validation before the path runs.
5. No `logging` or `print` may be introduced anywhere under `helios_v2/src`; the existing guard test must keep passing.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/engine.py` (an appraisal-derived `NeuromodulatorUpdatePath` implementation, or in composition if it is owner-neutral glue; see design) and any exported symbol.
2. `helios_v2/src/helios_v2/neuromodulation/__init__.py` (export the new update path if public to composition)
3. `helios_v2/src/helios_v2/composition/bridges.py` (the appraisal-derived update path as a first-version owner-provided estimator, mirroring how `FirstVersionNeuromodulatorUpdatePath` lives there today)
4. `helios_v2/src/helios_v2/composition/runtime_assembly.py` (select the appraisal-derived update path in the semantic-memory assembly; keep the constant path otherwise)
5. `helios_v2/tests/test_neuromodulator_engine.py` (extend: salience-driven levels, determinism, range, empty-batch baseline)
6. `helios_v2/tests/test_runtime_composition.py` (extend: high-novelty vs low-novelty tick produces different NE; default assembly unchanged)
7. `helios_v2/docs/requirements/index.md`
8. `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md`
9. `helios_v2/docs/BRAIN_ARCHITECTURE_COMPARISON.md`
10. `helios_v2/docs/OWNER_GUIDE.md`
11. `helios_v2/docs/OWNER_GUIDE.zh-CN.md`
12. `helios_v2/docs/PROGRESS_FLOW.en.md`
13. `helios_v2/docs/PROGRESS_FLOW.zh-CN.md`

## 7. Acceptance Criteria

1. `04` computes neuromodulator levels from the real appraisal batch when appraisal-derived neuromodulation is enabled, via an injected `NeuromodulatorUpdatePath` that consumes the batch (it does not ignore it); the owner engine is unchanged.
2. A high-novelty appraisal batch yields a measurably higher norepinephrine level than a low-novelty batch; a high-reward batch yields a higher dopamine level than a low-reward batch; the differences are attributable to real salience, not a constant.
3. Every produced level lies within its `[legal_min, legal_max]` range, is deterministic for identical inputs, and flows through the unchanged `NeuromodulatorState`/`NeuromodulatorLevels` contracts.
4. The per-channel sensitivity coefficients are explicit bounded first-version constants under the config's declared learned-parameter categories; the derivation is a linear combination plus clamp, with no black-box model and no prior-tick state read.
5. An empty appraisal batch yields the tonic-baseline levels (no divergence, no error).
6. The default assembly, the recency-only persistent assembly, and the deterministic offline assembly keep the constant update path and their current `04` behavior; their existing tests pass unmodified.
7. The single-logging-mechanism guard test still passes; the full `helios_v2/tests` suite remains green and network-free.

## 8. Future Extension Scope

R36 de-shims `04` to a stateless deterministic appraisal-derived model. The following are explicitly anticipated future work, each via its own requirement, and must preserve the owner boundaries established here:

1. Dual-timescale tonic/phasic dynamics that carry prior-tick levels across ticks (depends on a neuromodulator-state carry/checkpoint, the same family as the `18`/`09`/`14` state-checkpoint slice).
2. P5 learning of the bounded sensitivity coefficients via reward-prediction-error (dopamine) and outcome feedback, replacing the first-version constants without changing the equation shape.
3. Cross-channel coupling (the declared `cross_channel_coupling_strength` category) beyond the first-version independent linear mapping.
4. Feeding the real `04` state into a de-shimmed `05` feeling layer and `09` gating so modulation measurably shapes downstream subjective and gating behavior.
5. De-shimming the remaining `03` dimensions (threat/reward/social/uncertainty) so all neuromodulator drivers are real, not just novelty.

None of these may be smuggled into this slice. R36 introduces no prior-tick state, no NN, no new logging mechanism, and changes no owner's contract; it only makes the `04` levels a real deterministic function of appraisal.
