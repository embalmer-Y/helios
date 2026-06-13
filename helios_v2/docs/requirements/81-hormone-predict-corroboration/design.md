# Requirement 81 - Hormone-Predict Corroboration

## 1. Design Overview

Add a twelfth nullable `hormone_response_i_predict` field to the model's structured thought output,
parse it in `11` as optional owner-private evidence, publish it on `ThoughtCycleResult`, carry it
forward one tick through an owner-neutral composition holder, and have the `04` owner corroborate
the carried prior-tick forecast per channel against the same tick's R80 formula drive into a
three-state verdict, applying a bounded owner-judged bias only on agreement. The biased drive is
the instantaneous target the existing R43 dual-timescale wrapper smooths. The change is split
across `11` (parse/publish), `16` (schema text), `04` (corroborator), and composition (carry +
wiring). It is byte-for-byte invariant unless the model actually returns a forecast.

## 2. Current State and Gap

1. `04`: `DualTimescaleNeuromodulatorUpdatePath(drive_path=AppraisalDerivedNeuromodulatorUpdatePath())`
   is the semantic-assembly update path. The drive is a pure formula of the `03` batch; nothing
   corroborates it.
2. `11`: `_parse_structured_thought` parses `thought`/`sufficiency`/`wants_to_continue`/
   `proposed_action`/`self_revision`. There is no hormone-forecast field and `ThoughtCycleResult`
   has no place to publish one.
3. `16`: `_V3_RESPONSE_SCHEMA` lists eleven natural-language fields; there is no hormone field.
4. composition: R49/R62 already show the owner-neutral cross-tick carry pattern (a holder set
   post-tick by `RuntimeHandle._carry_*`, read next tick). There is no hormone-forecast holder.
5. `NeuromodulatorConfig` declares exactly four learned-parameter categories; there is no category
   for a corroboration coupling.

## 3. Target Architecture

### 3.1 `11` parse + publish (model supplies content only)

`_parse_structured_thought` parses an optional `hormone_response_i_predict`:

1. Absent or JSON `null` -> `None` (no forecast).
2. Present -> must be an object; for each recognized channel key
   (`_HORMONE_PREDICTION_CHANNELS`, the nine names as an owner-local convention), the value must be
   numeric and in `[0, 1]` (else `StructuredThoughtParseError`); unrecognized keys are ignored; a
   partial subset is allowed; an empty/all-unrecognized object -> `None`.

The parsed mapping is added to `StructuredThoughtEvidence.hormone_prediction` and threaded through
`_derive_thought_judgment` -> `_ThoughtJudgment.hormone_prediction` -> `_assemble_completed_result`
onto `ThoughtCycleResult.hormone_response_i_predict`. It is content, not judgment: it is read by no
judgment branch. The deterministic path and non-success results publish `None`.

The `11` LLM envelope (`_build_messages` system text) documents the optional field so a real
reasoning model can emit it. The forecast does not appear in the user message.

### 3.2 `16` schema text

`_V3_RESPONSE_SCHEMA` gains the twelfth key `hormone_response_i_predict` documented as a nullable
object of the nine channel names to `[0, 1]`, plus a hard rule that it is optional. This is additive
schema text; no contract field changes.

### 3.3 Owner-neutral carry

`PriorHormonePredictionHolder` (composition, `bridges.py`) holds the carried forecast
(`Mapping[str, float] | None`) and exposes `current_prediction() -> Mapping[str, float] | None`, so
it structurally satisfies the `04`-owned `HormonePredictionSource` protocol (the holder is injected
directly; no separate adapter, mirroring how the `09` gate bridges forward raw facts).
`RuntimeHandle._carry_hormone_prediction(result)` runs after each tick: it reads the
`internal_thought_loop_owner` stage result's `ThoughtCycleResult.hormone_response_i_predict` and
`set_prediction(...)`s it, or `clear()`s when the gate did not fire / no forecast was published.

Because `04` runs before `11`, the holder read by tick N's `04` contains tick N-1's forecast - the
intended "prior-tick forecast corroborated against this tick's drive", and the only causal option
given stage order. This matches the predictive-coding direction (forecast, then check next tick).

### 3.4 `04` corroborator (owner policy)

New `neuromodulation/corroborator.py`:

1. `HormonePredictionSource` (runtime-checkable Protocol): `current_prediction() -> Mapping[str, float] | None`.
2. `HormoneCorroborationOutcome` (frozen): `biased_levels: NeuromodulatorLevels`,
   `verdicts: Mapping[str, str]` (channel -> `corroborate`/`conflict`/`silent`).
3. `HormonePredictCorroborator` (dataclass): `coupling_gain: float = 0.15`,
   `agreement_deadzone: float = 0.05`. `corroborate(prediction, drive, config) -> HormoneCorroborationOutcome`:
   per channel,
   - forecast value `p = prediction.get(channel)` (None -> `silent`, channel = drive value `d`);
   - `p_dir/d_dir = sign(value - tonic_baseline)` with the deadzone as zero;
   - `corroborate` if `p_dir == d_dir`, else `conflict`;
   - on `corroborate`: `biased = clamp(d + coupling_gain * (p - d), legal_min, legal_max)`;
   - on `conflict` / `silent`: `biased = d`.
4. `CorroborationBiasedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath)`: `drive_path`,
   `prediction_source`, `corroborator`. `update_levels(batch, config, tick_id, prior_levels=None)`
   ignores `prior_levels` (cross-tick carry is the dual-timescale wrapper's job), computes
   `drive = drive_path.update_levels(batch, config, tick_id, None)`, reads
   `prediction_source.current_prediction()`, and returns
   `corroborator.corroborate(prediction, drive, config).biased_levels`.

Nesting under the semantic assembly:
`DualTimescaleNeuromodulatorUpdatePath(drive_path=CorroborationBiasedNeuromodulatorUpdatePath(drive_path=AppraisalDerivedNeuromodulatorUpdatePath(), prediction_source=holder, corroborator=HormonePredictCorroborator()))`.

### 3.5 New learned-parameter category

`LearnedParameterCategory` gains `"hormone_predict_coupling"`, and the
`NeuromodulatorConfig.__post_init__` expected set adds it. The corroborator's `coupling_gain` /
`agreement_deadzone` are documented as belonging to this category (held on the corroborator, as R80
coefficients are held on the drive path).

## 4. Data Structures

1. `ThoughtCycleResult.hormone_response_i_predict: Mapping[str, float] | None = None` (additive,
   last field, default None; validated in `__post_init__`: if not None, a mapping of recognized
   channel names to floats in `[0, 1]`, stored as a `MappingProxyType`).
2. `StructuredThoughtEvidence.hormone_prediction: Mapping[str, float] | None` (owner-private).
3. `_ThoughtJudgment.hormone_prediction: Mapping[str, float] | None` (owner-private pass-through).
4. `HormoneCorroborationOutcome` (new, `04`): `biased_levels`, `verdicts`.
5. `HormonePredictCorroborator`, `CorroborationBiasedNeuromodulatorUpdatePath`,
   `HormonePredictionSource` (new, `04`).
6. `PriorHormonePredictionHolder` (new, composition): `prediction: Mapping[str, float] | None`,
   `set_prediction`, `clear`, `current_prediction`.
7. `LearnedParameterCategory` += `"hormone_predict_coupling"`.

## 5. Module Changes

1. `neuromodulation/contracts.py` - add the category to the `Literal` and the expected set.
2. `neuromodulation/corroborator.py` - new module (the four symbols above); reuses `_clamp` and the
   channel tuple from `engine.py`.
3. `neuromodulation/__init__.py` - export the four new symbols.
4. `internal_thought/contracts.py` - add `_HORMONE_PREDICTION_CHANNELS`; add the optional field +
   validation on `ThoughtCycleResult`.
5. `internal_thought/engine.py` - parse helper `_optional_hormone_prediction`; add to evidence;
   document in the LLM envelope; thread through judgment + completed-result assembly.
6. `prompt_contract/engine.py` - the twelfth field in `_V3_RESPONSE_SCHEMA`.
7. `composition/bridges.py` - `PriorHormonePredictionHolder`.
8. `composition/runtime_assembly.py` - import the corroborator path; build the holder under the
   semantic assembly; nest the corroboration path; add the RuntimeHandle field +
   `_carry_hormone_prediction`; add the new category to the default `NeuromodulatorConfig`.

## 6. Migration Plan

1. The new category is mandatory, so every `NeuromodulatorConfig` construction adds
   `"hormone_predict_coupling"`: the default config in `runtime_assembly.py` and the test configs in
   `test_neuromodulator_contracts.py` (3) and `test_runtime_stage_chain.py` (1). The negative-case
   test (wrong category set) stays failing.
2. `ThoughtCycleResult` gains an optional last field with a default, so all existing positional and
   keyword constructions are unchanged.
3. The corroboration path is wired only under the semantic assembly (same opt-in as R80/R43).
   Default `legacy_constant`/offline use `FirstVersionNeuromodulatorUpdatePath`, unchanged.
4. Runtime invariance: fake LLM providers emit no `hormone_response_i_predict`, so the parse yields
   `None`, the holder stays empty, and the corroborator returns the R80 drive byte-for-byte. Every
   existing semantic-assembly level assertion is therefore unchanged; only new tests that inject a
   forecast exercise the bias.
5. If a v3-schema assertion in `test_prompt_contract_v2.py` pins the exact field list, it is updated
   to include the twelfth field.

## 7. Failure Modes and Constraints

1. A present `hormone_response_i_predict` with a non-object value, or a recognized channel with a
   non-numeric or out-of-range value -> `StructuredThoughtParseError` -> `insufficient_generation`
   (existing fail-fast path); never silently coerced.
2. The corroborator never reads `05`, the same-tick `11`, or any other owner's state; it reads only
   the carried forecast, the R80 drive, and config. Cross-channel coupling stays out of scope.
3. Every biased channel is clamped to `[legal_min, legal_max]`; a null forecast or all-silent
   verdicts return the drive unchanged.
4. The bias only fires on directional agreement, so the model can never move a channel against the
   formula or veto it (content/judgment separation, §14; the owner keeps judgment).
5. `11` must not import `04`'s `NeuromodulatorLevels`; the forecast is an owner-neutral mapping.
6. Owner-boundary guard and ad-hoc-logging guard stay green; no new logging mechanism.

## 8. Observability and Logging

No new logging mechanism. The `04` state (with any corroboration bias applied) continues to flow
through the existing `21` timeline and the `42` checkpoint unchanged; the bias is reconstructable as
a difference between the published levels and the R80 drive. The three-state verdict is owner-private
this slice (computed and testable); surfacing it to `17`/`23` as explicit provenance is a future
slice.

## 9. Validation Strategy

1. Unit (`04` corroborator): a forecast above baseline on a channel whose drive is also above
   baseline biases that channel toward the forecast (within bound); a forecast below baseline with an
   above-baseline drive (conflict) leaves the channel at the drive; an absent channel (silent) leaves
   it at the drive; a null forecast returns the drive byte-for-byte; all channels stay in range;
   verdicts are `corroborate`/`conflict`/`silent` as expected.
2. Unit (`CorroborationBiasedNeuromodulatorUpdatePath`): with a fake prediction source it produces
   the biased levels; with a `None`-returning source it equals the inner drive.
3. Unit (`11`): `_parse_structured_thought` parses a present forecast into evidence, ignores
   unknown keys, raises on out-of-range/wrong-typed values, and yields `None` for absent/null; the
   forecast is published on `ThoughtCycleResult` and changes no judgment field (same judgment with
   and without it).
4. Unit (`16`): the v3 schema text includes `hormone_response_i_predict` and its nullable rule.
5. Composition: under the semantic assembly, a fake provider emitting a forecast on tick N changes
   tick N+1's `04` levels in the corroborated direction (and a non-fired/empty tick clears the
   carry); a fake provider emitting no forecast leaves `04` levels byte-for-byte unchanged.
6. Guards + regression: owner-boundary guard green (no salience/autonomy/corroboration policy in
   composition); ad-hoc-logging guard green; default/offline assemblies byte-for-byte unchanged;
   full network-free suite green.
7. Opt-in real-LLM smoke (not in CI): a reasoning model emits a forecast that parses and biases the
   next tick's `04`.
