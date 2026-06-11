# Requirement 79c - R79-C Hormone Predict Corroborator and 5-HT / Oxy / Opioid Drivers

## 1. Background and Problem

R79-A (delivered) built the v3 aggressive-radical-no-theater embodied-prompt path.
R79-B (delivered) wired the v3 path's `channel_catalog` layer to the real channel
subsystem and added a `AggressiveRadicalChannelArbitrationPostProcessor` that
dispatches the LLM's `i_send_through` JSON output.

Both are prompt-side and dispatch-side. The hormone-side remains a hole.

The `04` neuromodulator owner's `AppraisalDerivedNeuromodulatorUpdatePath` (R36,
owner-recovered in R56) drives 3 of 9 channels from rapid-appraisal salience
(dopamine, norepinephrine, cortisol), and explicitly **shims** the other 6 to
the tonic baseline:

```python
# Remaining channels regress to the tonic baseline (clamped) in this slice; their
# real drivers are later de-shim slices.
serotonin=_clamp(base.serotonin, low.serotonin, high.serotonin),
acetylcholine=_clamp(base.acetylcholine, low.acetylcholine, high.acetylcholine),
oxytocin=_clamp(base.oxytocin, low.oxytocin, high.oxytocin),
opioid_tone=_clamp(base.opioid_tone, low.opioid_tone, high.opioid_tone),
excitation=_clamp(base.excitation, low.excitation, high.excitation),
inhibition=_clamp(base.inhibition, low.inhibition, high.inhibition),
```

R79-D baseline framework (delivered 2026-06-11) confirms the shim: under the
`A_praise`, `B_neglect`, `C_bipolar`, `D_repeat` scenarios, `5-HT`, `oxytocin`,
and `opioid_tone` series are **constant 0.30 in every tick** because the update
path has no entry for them. R79 §3.3 also points out that the A vs B dopamine
delta is symmetric (A: +0.064, B: +0.063) because both praise and neglect map to
`social=1.0, reward=0`; this is a separate bug not in R79-C scope.

Even if we add 5-HT / Oxy / Opioid drivers, the v1 prompt contract does not ask
the LLM to predict how the body *should* change — so the loop "LLM predicts
hormone shift → next tick reflects prediction" cannot exist. R79 §3.3 requirement
4 calls for an LLM `hormone_response_i_predict` field and a
`HormonePredictCorroborator` that compares the LLM's prediction against the
formula-derived drive.

This violates P5 learning-loop readiness (R79 §1, requirement 5): the hormone
system must be expressive enough that feedback modifies it, **and** the LLM
must be able to act on its decisions, **and** the LLM output must be a
faithful first-person report. R79-C delivers the expressivity half (drivers)
and the LLM-side signal half (predict field + corroborator).

## 2. Goal

Close the `04` neuromodulator owner's expressivity gap on the three social /
homeostatic channels (5-HT / Oxy / Opioid), and close the v3 prompt contract's
missing predict field, by delivering 4 owned pieces:

1. **3 new sensitivity coefficient families** on
   `AppraisalDerivedNeuromodulatorUpdatePath` (5-HT from `(1 - threat) * social`,
   Oxy from `social * (1 - uncertainty)`, Opioid from `(1 - threat) * (1 - uncertainty)`),
   all under the existing `channel_gain_sensitivity` learned-parameter category.
2. **A new `HormonePredictCorroborator` owner class** in
   `helios_v2.neuromodulation.corroborator` that takes the LLM's
   `hormone_response_i_predict` (a 9-key dict mirroring `NeuromodulatorLevels`)
   and the formula-derived `drive` (a `NeuromodulatorLevels`), and emits a
   per-channel `corroborate` / `conflict` / `silent` verdict with a bounded
   bonus / penalty magnitude.
3. **A 5th `LearnedParameterCategory` literal**: `"hormone_predict_coupling"`,
   for the bonus / penalty magnitudes — the predict-coupling is a separately
   learnable coefficient family (per-channel sign, per-channel magnitude) so
   P5 can later tune corroboration strength without touching the channel
   sensitivity coefficients.
4. **A 12th v3 LLM JSON field `hormone_response_i_predict`**: a 9-key dict
   (`dopamine` / `norepinephrine` / `serotonin` / `acetylcholine` / `cortisol` /
   `oxytocin` / `opioid_tone` / `excitation` / `inhibition`), each value in
   `[-1.0, +1.0]`, representing the LLM's subjective prediction of how the
   current stimulus should move the body. The default (no predict) is
   `null` — the corroborator treats null-predict as silent and emits zero
   bonus / penalty.

The dual-timescale dynamics (R43, `DualTimescaleNeuromodulatorUpdatePath`) is
**not** changed. The 3 new channels continue to flow through it.

The R79-D baseline framework must now show `5-HT / Oxy / Opioid` series
non-constant under the A_praise / B_neglect / C_bipolar / D_repeat scenarios
(7.3 acceptance criterion 1).

## 3. Detailed Requirements

### 3.1 `04` `AppraisalDerivedNeuromodulatorUpdatePath` drivers

The path gains 3 new sensitivity coefficient fields and replaces the 3 shim
lines with bounded linear formulas:

```
serotonin = clamp(base.serotonin
                  + self.safety_social_to_serotonin * (1 - threat) * social,
                  low.serotonin, high.serotonin)
oxytocin  = clamp(base.oxytocin
                  + self.social_uncertainty_to_oxytocin * social * (1 - uncertainty),
                  low.oxytocin, high.oxytocin)
opioid_tone = clamp(base.opioid_tone
                    + self.safety_uncertainty_to_opioid
                    * (1 - threat) * (1 - uncertainty) * social,
                    low.opioid_tone, high.opioid_tone)
```

**Note on the `social` factor in the opioid formula**: requirement
§3.1 originally proposed `opioid_tone = sensitivity * (1 - pain_like)
* (1 - threat)`. `pain_like` is a feeling-layer field that requires
prior_feeling to read; R79-C does not extend `update_levels` to take
prior_feeling. Instead, the implementation uses `social` from the
appraisal salience as the "signal-present" gate (a stimulus without
any social signal does not engage the opioid / pain-relief channel).
This keeps the 3 formulas uniformly gated on `social` so an empty
appraisal batch keeps all 3 channels at the tonic baseline.

Coefficient defaults (first-version constants, all bounded in `[0.0, 1.0]`):

| coefficient | default | meaning |
|---|---|---|
| `safety_social_to_serotonin` | `0.4` | how much safety + social signal raises 5-HT |
| `social_uncertainty_to_oxytocin` | `0.4` | how much social + non-uncertainty raises Oxy |
| `safety_uncertainty_to_opioid` | `0.4` | how much safety + non-uncertainty raises Opioid |

All three sit under the existing `channel_gain_sensitivity` learned-parameter
category — no new category for these.

The other 3 shimmed channels (`acetylcholine` / `excitation` / `inhibition`)
remain at the tonic baseline. R79-C does not de-shim them; that is a future
slice's scope (ACh from selective-attention signal, excitation/inhibition from
the `thought_gating` owner's `competition_threshold`).

### 3.2 `04` `HormonePredictCorroborator` owner class

New file `helios_v2/neuromodulation/corroborator.py`. New public classes:

- `HormonePredictCouplingChannel` (frozen enum, members:
  `DOPAMINE` / `NOREPINEPHRINE` / `SEROTONIN` / `ACETYLCHOLINE` / `CORTISOL` /
  `OXYTOCIN` / `OPIOID_TONE` / `EXCITATION` / `INHIBITION`)
- `HormonePredictCouplingVerdict` (Literal: `"corroborate"` / `"conflict"` / `"silent"`)
- `HormonePredictCouplingClassification` (frozen dataclass, 3 fields:
  `channel: HormonePredictCouplingChannel` / `verdict: HormonePredictCouplingVerdict` /
  `magnitude: float` — magnitude is the LLM-side predict value, in `[-1.0, +1.0]`)
- `HormonePredictCouplingConfig` (frozen dataclass, 4 fields:
  `corroborate_bonus: float` (default `+0.05`, bounded `0.0 ≤ ≤ 0.2`),
  `conflict_penalty: float` (default `-0.05`, bounded `-0.2 ≤ ≤ 0.0`),
  `sign_match_tolerance: float` (default `0.1`, bounded `0.0 < ≤ 0.5`),
  `magnitude_match_tolerance: float` (default `0.2`, bounded `0.0 < ≤ 0.5`))
  — fail-fast `__post_init__` raises `NeuromodulatorError` on any out-of-bound field
  or `corroborate_bonus < 0.0` or `conflict_penalty > 0.0` (sign convention).
- `HormonePredictCorroborator` (frozen dataclass, 1 field:
  `config: HormonePredictCouplingConfig`)

  Methods:
  - `classify_predict(formula_drive: NeuromodulatorLevels, predict: Mapping[str, float]) -> tuple[HormonePredictCouplingClassification, ...]` —
    classifies each of the 9 channels; returns an empty tuple if `predict` is
    empty / `None` (silent across the board).
  - `aggregate_coupling_bias(classifications: tuple[HormonePredictCouplingClassification, ...]) -> dict[str, float]` —
    converts classifications into a 9-channel bias vector (one key per
    channel name); the bias is added to the formula-derived drive on the
    **next** tick (the bias is not a self-feedback on the same tick — it
    must travel through the `DualTimescaleNeuromodulatorUpdatePath`
    integrator). Output is a `dict[str, float]` (not `NeuromodulatorLevels`)
    because the bias can be negative on a conflict verdict, and
    `NeuromodulatorLevels` enforces `[0.0, 1.0]`.

The corroborator's classification rule (per channel):

```
predict_value = predict.get(channel.name, 0.0)
drive_value = formula_drive.<channel> - tonic_baseline.<channel>   # signed drive
drive_sign = sign(drive_value)        # -1 / 0 / +1
predict_sign = sign(predict_value)    # -1 / 0 / +1
if predict_value == 0.0 or predict is None:
    verdict = "silent", magnitude = 0.0
elif drive_sign == 0 or predict_sign == 0:
    verdict = "silent", magnitude = 0.0
elif drive_sign == predict_sign and abs(drive_value - predict_value) <= magnitude_match_tolerance:
    verdict = "corroborate", magnitude = predict_value
elif drive_sign != predict_sign and abs(drive_value + predict_value) <= magnitude_match_tolerance:
    verdict = "conflict", magnitude = predict_value
else:
    verdict = "silent", magnitude = 0.0
```

`aggregate_coupling_bias` rule:

```
for classification in classifications:
    if classification.verdict == "corroborate":
        bias.<channel> = config.corroborate_bonus * classification.magnitude
    elif classification.verdict == "conflict":
        bias.<channel> = config.conflict_penalty * classification.magnitude
    else:
        bias.<channel> = 0.0
return clamp(bias, legal_min - tonic_baseline, legal_max - tonic_baseline)
```

**Output type note**: the bias is a `dict[str, float]` (not
`NeuromodulatorLevels`) because the bias can be **negative** (a conflict
verdict produces a negative penalty), and `NeuromodulatorLevels` enforces
`[0.0, 1.0]` per channel. The caller consumes the dict and adds it as
a per-channel offset to the next-tick `RapidAppraisalBatch`. The
channel names in the dict are the same as `NeuromodulatorLevels`
field names (`dopamine` / `norepinephrine` / etc.).

**Why a separate bias (not direct drive mutation)?** The corroborator must
not influence the same tick's drive; the bias is fed into the next tick's
`RapidAppraisalBatch` as a small per-channel offset. This is a future slice
(R80 or R81) to wire the bias back into the rapid-appraisal path. R79-C
delivers the corroborator + bias calculation, but does not modify
`AppraisalDerivedNeuromodulatorUpdatePath.update_levels` to consume the bias.
The bias is returned and **may be ignored** by the caller; that is the v1
behavior (default assembly). The R79-D baseline framework (R79-D)
**does** feed the bias into the next tick — that is the integration test.

### 3.3 `04` `NeuromodulatorConfig` `mandatory_learned_parameters`

Add a 5th literal `"hormone_predict_coupling"` to the
`LearnedParameterCategory` Literal type. Add it to the
`expected_learned_parameters` set in `NeuromodulatorConfig.__post_init__`. The
existing 4 categories are unchanged.

The 3 new sensitivity coefficients (3.1) are under
`channel_gain_sensitivity` (existing category, expanded). The corroborator's
bonus / penalty / tolerances (3.2) are under the new
`hormone_predict_coupling` category.

### 3.4 `16` v3 prompt schema — 12th field `hormone_response_i_predict`

The `AggressiveRadicalEmbodiedPromptPath._schema_instructions()` (in
`helios_v2/prompt_contract/engine.py`) gains a 12th field in the
`_AGGRESSIVE_RADICAL_V3_SYSTEM_PROMPT` template:

```
"hormone_response_i_predict": "<a 9-key dict mirroring your body's neuromodulators
 (dopamine / norepinephrine / serotonin / acetylcholine / cortisol / oxytocin /
 opioid_tone / excitation / inhibition), each value in [-1.0, +1.0]. -1 means
 'this should fall', +1 means 'this should rise', 0 means 'no opinion'.
 null if you do not want to predict.>"
```

The hard rules block is extended:

```
- "hormone_response_i_predict" is a 9-key dict (or null). Each key is a channel
  name, each value is a number in [-1.0, +1.0]. No other keys allowed.
```

The `_build_*` method validates the rendered schema still has exactly 12
fields (i.e., the existing
`test_aggressive_radical_prompt_path.py` schema count test gets bumped from
11 to 12 — the test is part of R79-C's edit set, not R79-A's).

The field is **optional** at the v3 wire level: the LLM may return
`hormone_response_i_predict: null` and the corroborator treats it as
silent across the board. The v1 prompt contract is unchanged (it does not
ask for this field at all).

### 3.5 v1 byte-level preservation

- `FirstVersionEmbodiedPromptPath` — not touched.
- `FirstVersionEmbodiedPromptRequestBridge` — not touched.
- `DualTimescaleNeuromodulatorUpdatePath` — not touched.
- `RapidSalienceVector` / `RapidAppraisalBatch` — not touched.
- The 3 sensitivity fields (3.1) on `AppraisalDerivedNeuromodulatorUpdatePath`
  are added with `default=0.4` so an existing v1 assembly with the v1
  constants gets them at `0.4` — but **the v1 assembly uses
  `FirstVersionConstantNeuromodulatorUpdatePath`, not
  `AppraisalDerivedNeuromodulatorUpdatePath`**, so the default has no effect
  on the v1 path. R79-C only runs when the v3 path is wired in (R79-A's
  `RuntimeProfile.aggressive_radical_prompt_profile` is set).

### 3.6 `NeuromodulatorConfig` constant update

The default `NeuromodulatorConfig` in `helios_v2/neuromodulation/contracts.py`
(the one in `tests/conftest.py` and any other canonical fixture) must include
`"hormone_predict_coupling"` in `mandatory_learned_parameters`. The R79-A
profile bundle does not reference `NeuromodulatorConfig` directly, so R79-C
only needs to update fixtures and any test that constructs a
`NeuromodulatorConfig` literal.

## 4. Non-Goals

1. **No `acetylcholine` / `excitation` / `inhibition` de-shim.** These three
   channels stay at the tonic baseline. R79-C's scope is `5-HT / Oxy /
   Opioid` only.
2. **No `cross_channel_coupling_strength` work.** Cross-channel coupling
   (e.g., cortisol suppressing 5-HT) is a future slice.
3. **No P5 learning.** R79-C fixes the expressivity and the signal, not the
   learning algorithm. The corroborator's bonus / penalty magnitudes are
   first-version constants under the new
   `hormone_predict_coupling` category; P5 will tune them later.
4. **No composition integration of the corroborator.** The corroborator is
   imported by tests and by the R79-D baseline framework's bias-passthrough.
   The composition layer (`helios_v2.composition.bridges`) does not gain a
   `HormonePredictCouplingBridge` in R79-C; that is R80's scope.
5. **No `RapidAppraisalBatch` extension.** The bias is returned to the
   caller; the caller (R79-D framework, future composition bridge) decides
   how to feed it back.
6. **No retrospective reprocessing.** R79-C does not re-run the R79-D v1
   baseline reports. It produces a v2 baseline report
   (R79-D v2 output) under
   `helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/`, showing the
   `5-HT / Oxy / Opioid` series non-constant under A / B / C / D scenarios
   and the bias series under A (which has a coherent predict) vs B (which
   has a low-magnitude predict) vs C (mixed) vs D (constant).

## 5. Owner Boundaries

R79-C adds 2 things to the `04` owner package `helios_v2.neuromodulation`:

- 3 new sensitivity coefficient fields on
  `AppraisalDerivedNeuromodulatorUpdatePath` (3.1).
- 1 new module `helios_v2.neuromodulation.corroborator` exporting the
  corroborator public API (3.2).
- 1 new entry in the `LearnedParameterCategory` Literal (3.3) and 1 new
  entry in the `expected_learned_parameters` set.

R79-C adds 1 thing to the `16` prompt contract owner
`helios_v2.prompt_contract`:

- 1 new field `hormone_response_i_predict` in the v3 system prompt template
  (3.4).
- 1 new hard rule.
- The `_schema_instructions` method's 12-field check.

R79-C does **not** add to:

- `helios_v2.composition` (no new bridge, no new post-processor).
- `helios_v2.runtime.stages` (no new stage, no stage signature change).
- `helios_v2.appraisal` (`RapidSalienceVector` / `RapidAppraisalBatch` are
  frozen).
- `helios_v2.feeling` (no new feeling field).
- `helios_v2.channel` (no new channel behavior).
- `helios_v2.llm.contracts` (no new wire field — the v3 schema is a prompt
  field, not a wire field; the existing JSON envelope is unchanged at the
  protocol level).

R21 ad-hoc logging guard (`tests/test_no_adhoc_logging_guard.py`) must
remain green: no `print(` or `import logging` in any new file or
modification.

`helios_v2/composition/owner_boundary.py` guard must remain green: no
new cross-owner import in the new corroborator file beyond `contracts.py`
inside the same `04` owner package.

## 6. Files to Add / Modify

### New
- `helios_v2/src/helios_v2/neuromodulation/corroborator.py` — corroborator
  owner class + config + classification + bias.
- `helios_v2/tests/test_hormone_predict_corroborator.py` — unit tests
  covering the 3 sensitivity coefficient fields, 9 channel classifications,
  silent-default, sign-mismatch (conflict), sign-match + magnitude-match
  (corroborate), sign-match + magnitude-mismatch (silent), bonus/penalty
  bounds, config out-of-bounds rejection.
- `helios_v2/tests/test_r79c_hormone_coverage.py` — coverage tests for
  `5-HT / Oxy / Opioid` non-constant behavior under the R79-D baseline
  scenarios, plus the 12th-field schema count test for the v3 prompt path.

### Modify
- `helios_v2/src/helios_v2/neuromodulation/contracts.py` — add
  `"hormone_predict_coupling"` to `LearnedParameterCategory` Literal and
  to the `expected_learned_parameters` set.
- `helios_v2/src/helios_v2/neuromodulation/engine.py` — add 3 new
  sensitivity fields to `AppraisalDerivedNeuromodulatorUpdatePath` and
  replace the 3 shim lines.
- `helios_v2/src/helios_v2/neuromodulation/__init__.py` — export the
  corroborator public API.
- `helios_v2/src/helios_v2/prompt_contract/engine.py` — add 12th field to
  `_AGGRESSIVE_RADICAL_V3_SYSTEM_PROMPT` template, add 1 hard rule, and
  bump the v3 schema count check from 11 to 12.
- `helios_v2/tests/test_aggressive_radical_prompt_path.py` — bump the
  schema count assertion from 11 to 12 (this test is owned by R79-A's
  file but the assertion target is shared with R79-C; R79-C edits the
  one specific count assertion, no other lines).
- `helios_v2/tests/conftest.py` (if it constructs `NeuromodulatorConfig`)
  — add `"hormone_predict_coupling"` to the literal.
- `helios_v2/tests/r79d/scenarios/*.py` — none expected to need edits
  (the R79-D framework is data-driven; the new fields are read by the
  default `assert_all_salience_series_non_constant` assertion, which
  iterates over `NeuromodulatorLevels` channels generically).
- `helios_v2/tests/r79d/assertions.py` — extend
  `assert_all_salience_series_non_constant` to also assert the
  `corroborate_bias` series is bounded.

## 7. Acceptance Criteria

### 7.1 Unit / integration tests (R79-C)

1. `AppraisalDerivedNeuromodulatorUpdatePath` produces non-constant
   `5-HT / Oxy / Opioid` under any non-empty rapid-appraisal batch where
   `threat != 0.0` or `social != 0.0` or `uncertainty != 0.0`.
2. `AppraisalDerivedNeuromodulatorUpdatePath` produces constant
   `5-HT / Oxy / Opioid == tonic_baseline` when the appraisal batch is
   empty (no salience signal).
3. `HormonePredictCorroborator.config` raises `NeuromodulatorError` on
   out-of-bounds `corroborate_bonus` / `conflict_penalty` /
   `sign_match_tolerance` / `magnitude_match_tolerance`.
4. `classify_predict` with empty `predict` returns an empty tuple (silent
   across the board).
5. `classify_predict` with `predict_value == 0.0` for all channels returns
   an empty tuple (silent across the board).
6. `classify_predict` with sign match + magnitude match emits
   `"corroborate"` with magnitude = `predict_value`.
7. `classify_predict` with sign mismatch + magnitude match emits
   `"conflict"` with magnitude = `predict_value`.
8. `classify_predict` with sign mismatch + magnitude beyond tolerance
   emits `"silent"` (LLM was confidently wrong; do not punish).
9. `aggregate_coupling_bias` returns a `dict[str, float]` with each
   channel clamped to the legal range around the tonic baseline (the
   bias can be negative on a conflict verdict, so a dict is used
   instead of `NeuromodulatorLevels`).
10. `NeuromodulatorConfig.__post_init__` rejects any
    `mandatory_learned_parameters` that is missing
    `"hormone_predict_coupling"`.

### 7.2 v3 prompt schema (R79-C)

11. `AggressiveRadicalEmbodiedPromptPath._build_*` emits 12 fields in
    the schema instruction (bumped from 11).
12. The 12th field's prompt description matches §3.4 exactly (no
    abbreviation, no field-name rephrasing).

### 7.3 R79-D baseline output (R79-C)

13. R79-D framework, when run with the v3 path, shows non-constant
    `5-HT / Oxy / Opioid` series under the A_praise / B_neglect /
    C_bipolar / D_repeat scenarios.
14. R79-D framework's A vs B `Oxy` delta is non-zero and differs in
    sign (A > B, magnitude >= 0.02) — confirming the social ×
    non-uncertainty signal is being picked up.
15. R79-D framework's `corroborate_bias` series is bounded within
    `[legal_min - tonic_baseline, legal_max - tonic_baseline]` for all
    9 channels across all 4 scenarios × N ticks.

### 7.4 Regression

16. All pre-R79-C tests must continue to pass (current baseline: 866
    passed, 2 pre-existing perf-flake).
17. R21 ad-hoc logging guard must remain green.
18. `helios_v2/composition/owner_boundary.py` guard must remain green.
19. The `tests/test_performance_benchmark.py` failures remain unchanged
    (pre-existing perf-flake, unrelated to R79-C).
