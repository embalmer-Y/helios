# Requirement 80 - Appraisal-Derived Serotonin / Oxytocin / Opioid / Acetylcholine Channels

## 1. Design Overview

Extend `AppraisalDerivedNeuromodulatorUpdatePath` (the `04` owner's R36 drive path) so serotonin,
oxytocin, opioid_tone, and acetylcholine are bounded linear combinations of the aggregated `03`
salience around the tonic baseline, replacing their regress-to-baseline behavior. The R43
dual-timescale wrapper is unchanged and now also carries these four channels across ticks. The
mapping stays owner-owned, deterministic, and clamped.

## 2. Current State and Gap

`AppraisalDerivedNeuromodulatorUpdatePath` drives dopamine/norepinephrine/cortisol from salience
and sets serotonin/acetylcholine/oxytocin/opioid_tone/excitation/inhibition to the clamped tonic
baseline (constants). The four affective channels never respond to appraisal, so `05` feeling
loses breadth and praise vs neglect is indistinguishable on the social/satisfaction/stability axes.

## 3. Target Architecture

Per channel, around the tonic baseline (all inputs are aggregated `03` salience; all clamped to
the legal range):

- `serotonin = clamp(base + serotonin_social_safety * social * (1 - threat))` — mood stability
  rises with social safety in a low-threat context; threat suppresses the rise.
- `oxytocin = clamp(base + oxytocin_social * social)` — social bonding rises with social presence.
- `opioid_tone = clamp(base + opioid_reward * reward + opioid_social * social)` — reward
  satisfaction + social comfort.
- `acetylcholine = clamp(base + acetylcholine_novelty * novelty)` — attention/encoding gain for
  novel input.

excitation and inhibition remain `clamp(base)` (unchanged this slice). dopamine/norepinephrine/
cortisol are unchanged. The drive path stays stateless (prior-tick carry is the R43 wrapper).

Grounding is `C_engineering_hypothesis`: a cautious functional analogy to `brain.mmd`
neuromodulator roles, not a calibrated neuroendocrine model.

## 4. Data Structures

Four additive bounded first-version coefficient fields on `AppraisalDerivedNeuromodulatorUpdatePath`
(defaults below), conceptually under the config's existing `channel_gain_sensitivity`
learned-parameter category (P5-learnable):

- `serotonin_social_safety: float = 0.4`
- `oxytocin_social: float = 0.4`
- `opioid_reward: float = 0.3`
- `opioid_social: float = 0.2`
- `acetylcholine_novelty: float = 0.4`

No contract change; `NeuromodulatorLevels` / `NeuromodulatorConfig` are unchanged.

## 5. Module Changes

1. `neuromodulation/engine.py` — add the four coefficient fields and replace the four
   regress-to-baseline channel lines in `AppraisalDerivedNeuromodulatorUpdatePath.update_levels`
   with the bounded drives; update the class docstring.

## 6. Migration Plan

1. Under the semantic assembly the four channels now evolve with appraisal (intended P3
   deepening). Tests asserting these channels equal the constant baseline under the
   appraisal-derived path are migrated to assert the new bounded drive behavior.
2. Default `legacy_constant`/offline assemblies use `FirstVersionNeuromodulatorUpdatePath`
   (unchanged constants), so they are byte-for-byte unchanged.
3. The R43 dual-timescale wrapper already integrates all nine channels, so cross-tick carry of the
   four channels needs no change.

## 7. Failure Modes and Constraints

1. An empty appraisal batch yields all-zero salience, so each channel reduces to `clamp(base)`
   (unchanged).
2. Every channel is clamped to `[legal_min, legal_max]`; no value can leave the legal range.
3. The drive path reads only the batch + config; reading `05`/prior-tick state is forbidden.

## 8. Observability and Logging

No new logging mechanism; the `04` state flows through existing `21`/checkpoint surfaces unchanged.

## 9. Validation Strategy

1. Unit: a high-social/low-threat batch yields serotonin > baseline; a high-threat batch yields
   serotonin lower than the low-threat one.
2. Unit: oxytocin rises with social; opioid_tone rises with reward and with social; acetylcholine
   rises with novelty — each verified against a contrasting batch.
3. Unit: an empty batch yields each channel at `clamp(base)`; all channels stay in range.
4. Regression: migrate constant-baseline assertions for these channels under the appraisal-derived
   path; `legacy_constant` path unchanged; full network-free suite green.
