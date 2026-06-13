# Requirement 81 - Hormone-Predict Corroboration

## 1. Background and Problem

R80 closed the `04` neuromodulator drive: seven channels are now appraisal-derived from the real
`03` salience. That drive is a pure formula. The model (`11`) never participates in the affective
loop except by consuming the resulting `05` feeling text downstream; it cannot express, and the
runtime never checks, the model's own subjective forecast of its affective response.

`brain.mmd` ties dopamine to a reward *prediction error* - the difference between a predicted and
an actual affective/value signal. Helios has no such corroboration anywhere: there is no path on
which a model assertion is checked against an owner computation and the agreement (or
disagreement) feeds back as a bounded signal. This is the missing seed for every later P5 learning
loop (§14 L2: bounded-parameter RL anchored on prediction error), and it is the first place the
philosophy's "model supplies content + self-assessment; owner keeps judgment" (§14 content/judgment
separation) is exercised on the affective state itself rather than only on sufficiency/continuation.

Today: the v3 thought envelope has no field for a hormone forecast; `11` does not parse one; `04`
has no corroborator; and there is no cross-tick seam carrying a model forecast into the next tick's
neuromodulation.

## 2. Goal

Let the model subjectively assert, in its structured thought output, a predicted neuromodulator
response (a nullable 9-channel mirror of `NeuromodulatorLevels`); carry that prior-tick assertion
into the next tick's `04`; have the `04` owner corroborate it per channel against the same tick's
R80 formula drive into a three-state verdict (corroborate / conflict / silent); and apply the
verdict only as a bounded, owner-judged bias on the drive that the R43 dual-timescale wrapper then
smooths - so the model can refine, but never override, the formula-derived affect, establishing the
project's first model-assertion-plus-owner-corroboration path.

## 3. Functional Requirements

### 3.1 Model hormone forecast field (`11` + `16`)

1. The `16` v3 embodied-prompt response schema must declare a twelfth field
   `hormone_response_i_predict`: a nullable object whose keys are the nine neuromodulator channel
   names (`dopamine`, `norepinephrine`, `serotonin`, `acetylcholine`, `cortisol`, `oxytocin`,
   `opioid_tone`, `excitation`, `inhibition`), each a number in `[0, 1]`. It is optional; the model
   may return `null` or omit it.
2. The `11` owner's structured-thought parse must accept the optional `hormone_response_i_predict`
   field: absent or `null` parses to no forecast; when present it must be an object, each provided
   channel value must be numeric and within `[0, 1]` (out-of-range or wrong-typed values are a parse
   error, consistent with the existing fail-fast parse), and unrecognized keys are ignored. A
   provided forecast may be partial (a subset of channels); omitted channels carry no forecast.
3. The parsed forecast must be published on the `ThoughtCycleResult` as an additive optional field
   so it can be carried; it is model-supplied content, never an owner judgment, and it must not
   change any sufficiency, continuation, recall, or proposal decision.

### 3.2 Cross-tick carry (owner-neutral composition seam)

1. Because `04` runs before `11` within a tick, a forecast made while thinking in tick N can only
   influence tick N+1's drive. The runtime must carry the just-completed tick's published
   `hormone_response_i_predict` forward to the next tick's `04`, mirroring the existing R49 recall /
   R62 drive-urgency carry seams.
2. The carry must be owner-neutral: it transports the `11`-owned forecast verbatim and computes no
   neuromodulation. When the gate did not fire, `11` published no forecast, or the forecast was
   null, the carry must clear so the next tick's `04` sees no forecast (silent).

### 3.3 Owner corroboration and bounded bias (`04`)

1. The `04` owner must own a `HormonePredictCorroborator` that, per channel, classifies the carried
   forecast against the same tick's R80 formula drive into exactly three verdicts:
   - `silent`: no forecast for the channel.
   - `corroborate`: the forecast and the drive are on the same side of the tonic baseline (within a
     bounded agreement deadzone), including both near baseline.
   - `conflict`: the forecast and the drive point to opposite sides of the baseline.
2. The corroborator must apply a bounded bias to the drive only on `corroborate`: the biased channel
   moves a bounded fraction (`hormone_predict_coupling` gain) of the way from the drive toward the
   forecast, then is clamped to the legal range. On `conflict` and `silent` the channel is the drive
   unchanged. A null forecast leaves every channel unchanged (byte-for-byte the R80 drive).
3. The bias must be structurally incapable of overriding the formula: it only fires when the model
   agrees with the formula's direction, so the model can refine magnitude within the agreed
   direction but can never move a channel against the formula or veto it.
4. The corroborated (biased) levels must be the instantaneous target the R43
   `DualTimescaleNeuromodulatorUpdatePath` smooths across ticks (bias and drive at the same layer,
   inside the dual-timescale wrapper), so a corroboration nudge is carried and decayed exactly like
   any drive.

### 3.4 Learnability and grounding

1. The corroboration coupling gain (and agreement deadzone) must be explicit bounded first-version
   constants under a new declared learned-parameter category `hormone_predict_coupling`
   (P5-learnable later), not free constants outside the scheme.
2. The corroboration is grounded as `C_engineering_hypothesis` (a cautious predictive-error analogy
   to `brain.mmd`, not a calibrated model); it must not be over-claimed.

## 4. Non-Functional Requirements

1. Performance: one extra linear combination per channel per tick when a forecast exists; no new
   I/O, no new heavyweight import, no network.
2. Reliability: the corroborator is a total deterministic function; every channel is clamped to the
   legal range; a null/absent forecast yields the R80 drive unchanged; it never diverges or NaNs.
3. Observability and logging: no new logging mechanism; `21` stays the single logging mechanism. The
   `04` state continues to flow through existing `21`/checkpoint surfaces; the bias is reconstructable
   as a difference in published levels.
4. Compatibility and migration: this is a new declared learned-parameter category, so every
   `NeuromodulatorConfig` construction migrates to include it. The runtime behavior is byte-for-byte
   unchanged unless the model actually returns a hormone forecast (fake providers do not), so default
   `legacy_constant`/offline assemblies and all existing semantic-assembly level assertions are
   unchanged. The wiring is on the same semantic-memory opt-in as the R80 drive / R43 wrapper.

## 5. Code Behavior Constraints

1. Forbidden: letting the model forecast override or veto the formula drive (bias fires only on
   directional agreement; conflict/silent never move the channel).
2. Forbidden: the corroborator or its bias reading `05` feeling, the same-tick `11` output, or any
   other owner's state; it reads only the carried prior-tick forecast, the R80 drive, and config.
3. Forbidden: `11` importing the `04` `NeuromodulatorLevels` contract to type the forecast; the
   forecast is an owner-neutral channel→value mapping in `11` (the nine channel names are a
   documented convention).
4. Forbidden: placing the corroboration mapping in composition glue; it is `04` owner policy (the
   owner-boundary guard must stay green). Composition only carries the forecast and injects it.
5. Forbidden: the forecast changing any `11` sufficiency/continuation/recall/proposal decision.

## 6. Impacted Modules

1. `helios_v2/src/helios_v2/neuromodulation/corroborator.py` (new) - `HormonePredictionSource`
   protocol, `HormonePredictCorroborator`, `HormoneCorroborationOutcome`,
   `CorroborationBiasedNeuromodulatorUpdatePath`.
2. `helios_v2/src/helios_v2/neuromodulation/contracts.py` - add the `hormone_predict_coupling`
   learned-parameter category.
3. `helios_v2/src/helios_v2/neuromodulation/__init__.py` - export the new corroborator symbols.
4. `helios_v2/src/helios_v2/internal_thought/engine.py` - parse the optional forecast; document it in
   the LLM envelope; thread it onto the result.
5. `helios_v2/src/helios_v2/internal_thought/contracts.py` - additive optional
   `hormone_response_i_predict` field on `ThoughtCycleResult`.
6. `helios_v2/src/helios_v2/prompt_contract/engine.py` - the twelfth v3 schema field.
7. `helios_v2/src/helios_v2/composition/bridges.py` - `PriorHormonePredictionHolder` (owner-neutral).
8. `helios_v2/src/helios_v2/composition/runtime_assembly.py` - the corroboration nesting under the
   semantic assembly, the holder field, and the post-tick `_carry_hormone_prediction` seam; the
   default config's new category.
9. Tests: `test_neuromodulator_corroborator.py` (new); migrations in `test_neuromodulator_contracts.py`,
   `test_runtime_stage_chain.py`, and any v3-schema assertion in `test_prompt_contract_v2.py`.
10. Docs: `requirements/index.md`, `OWNER_GUIDE.*` (`04`/`11`/`16`), `BRAIN_ARCHITECTURE_COMPARISON.md`,
    `PROGRESS_FLOW.*` (only if a maturity color changes - it does not).

## 7. Acceptance Criteria

1. The v3 schema declares the twelfth `hormone_response_i_predict` field; `11` parses a present
   forecast into bounded owner-private evidence and publishes it on `ThoughtCycleResult`; an absent
   or null forecast publishes none, and the forecast changes no sufficiency/continuation/proposal
   decision (verified by asserting identical judgment with and without the forecast field).
2. A present forecast that agrees in direction with the R80 drive on a channel moves that channel a
   bounded fraction toward the forecast (corroborate); a forecast on the opposite side of baseline
   leaves the channel at the drive (conflict); an absent channel leaves it at the drive (silent);
   verified with explicit forecast/drive pairs.
3. A null forecast yields the R80 drive byte-for-byte; the corroborated levels stay within the legal
   range for every channel; the corroborator reads no `05`/same-tick `11`/other-owner state.
4. The corroboration coupling gain is under the declared `hormone_predict_coupling` category; the
   mapping lives in the `04` owner; the composition owner-boundary guard stays green.
5. The carried prior-tick forecast reaches the next tick's `04` through an owner-neutral holder; a
   non-fired tick or null forecast clears the carry.
6. Default `legacy_constant`/offline assemblies are byte-for-byte unchanged; existing
   semantic-assembly level assertions are unchanged (fake providers emit no forecast → silent); the
   full network-free suite is green; `index.md` has a row 81 and the `04`/`11`/`16` `OWNER_GUIDE`
   entries + `BRAIN_ARCHITECTURE_COMPARISON` note record the corroboration with the honest
   `C_engineering_hypothesis` caveat.
