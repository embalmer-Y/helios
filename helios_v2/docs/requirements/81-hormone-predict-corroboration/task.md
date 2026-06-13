# Requirement 81 - Hormone-Predict Corroboration

## 1. Task Breakdown

### T1 - New learned-parameter category (`04` contract)
In `neuromodulation/contracts.py`, add `"hormone_predict_coupling"` to the `LearnedParameterCategory`
`Literal` and to the `expected_learned_parameters` set in `NeuromodulatorConfig.__post_init__`.

### T2 - `04` corroborator
Add `neuromodulation/corroborator.py` with `HormonePredictionSource` (protocol),
`HormoneCorroborationOutcome` (frozen), `HormonePredictCorroborator` (verdict + bounded bias), and
`CorroborationBiasedNeuromodulatorUpdatePath` (wraps the drive path + prediction source +
corroborator). Export all four from `neuromodulation/__init__.py`.

### T3 - `11` parse + publish
In `internal_thought/contracts.py` add `_HORMONE_PREDICTION_CHANNELS` and the additive optional
`hormone_response_i_predict` field (+ validation) on `ThoughtCycleResult`. In
`internal_thought/engine.py` add `_optional_hormone_prediction`, parse it in
`_parse_structured_thought` into `StructuredThoughtEvidence.hormone_prediction`, thread it through
`_derive_thought_judgment`/`_ThoughtJudgment`/`_assemble_completed_result`, and document the optional
field in the LLM envelope (`_build_messages`).

### T4 - `16` schema text
In `prompt_contract/engine.py` add the twelfth `hormone_response_i_predict` field (nullable
9-channel object) to `_V3_RESPONSE_SCHEMA`.

### T5 - composition carry + wiring
In `composition/bridges.py` add `PriorHormonePredictionHolder` (owner-neutral, with
`current_prediction`). In `composition/runtime_assembly.py`: add the new category to the default
`NeuromodulatorConfig`; build the holder under the semantic assembly; nest
`CorroborationBiasedNeuromodulatorUpdatePath` inside the dual-timescale wrapper; add the
RuntimeHandle field and the post-tick `_carry_hormone_prediction` seam (call it in `tick()`).

### T6 - Tests
Add `tests/test_neuromodulator_corroborator.py` (verdicts, bounded bias, null=drive, in-range,
path-with-source). Add `11` parse + publish tests and the no-judgment-change assertion. Add the v3
schema-field assertion. Add a composition test: forecast on tick N biases tick N+1's `04`; no
forecast leaves `04` unchanged.

### T7 - Migrate existing assertions
Add `"hormone_predict_coupling"` to the neuromodulator config tuples in
`test_neuromodulator_contracts.py` (3) and `test_runtime_stage_chain.py` (1). Update any exact v3
schema field-list assertion in `test_prompt_contract_v2.py`.

### T8 - Documentation sync
Update `index.md` (row 81), `OWNER_GUIDE.*` (`04` corroborator, `11` forecast field, `16` twelfth
field), `BRAIN_ARCHITECTURE_COMPARISON.md` (`03-07` row: corroboration/prediction-error seed with
`C_engineering_hypothesis`). `PROGRESS_FLOW.*` only if a maturity color changes (it does not; note
the R81 sync line).

## 2. Dependencies

1. T1 -> T2; T3 (contract) -> T3 (engine); T2 + T3 + T5 -> T6; T1 -> T7.
2. External: `04` (R36 drive, R43 wrapper), `11` (R27 structured parse, R79 v3), `16` (R79 v3), the
   R49/R62 carry pattern. No new owner; the only contract changes are additive (`ThoughtCycleResult`
   field, one learned-parameter category).

## 3. Files and Modules

1. `src/helios_v2/neuromodulation/contracts.py` (T1), `corroborator.py` (T2), `__init__.py` (T2)
2. `src/helios_v2/internal_thought/contracts.py`, `engine.py` (T3)
3. `src/helios_v2/prompt_contract/engine.py` (T4)
4. `src/helios_v2/composition/bridges.py`, `runtime_assembly.py` (T5)
5. `tests/test_neuromodulator_corroborator.py` (new), `test_internal_thought_engine.py`,
   `test_prompt_contract_v2.py`, `test_runtime_composition.py` (T6); `test_neuromodulator_contracts.py`,
   `test_runtime_stage_chain.py` (T7)
6. `docs/requirements/index.md`, `docs/OWNER_GUIDE.md`/`.zh-CN.md`,
   `docs/BRAIN_ARCHITECTURE_COMPARISON.md`, `docs/PROGRESS_FLOW.*` (T8)

## 4. Implementation Order

T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8.

## 5. Validation Plan

1. After T1-T2: `pytest helios_v2/tests/test_neuromodulator_corroborator.py helios_v2/tests/test_neuromodulator_contracts.py helios_v2/tests/test_neuromodulator_engine.py -q`.
2. After T3-T4: `pytest helios_v2/tests/test_internal_thought_engine.py helios_v2/tests/test_prompt_contract_v2.py -q`.
3. After T5-T7: `pytest helios_v2/tests/test_runtime_composition.py helios_v2/tests/test_runtime_stage_chain.py helios_v2/tests/test_composition_owner_boundary_guard.py -q`.
4. Full: `pytest helios_v2/tests -q` green and network-free.

## 6. Completion Criteria

1. The model can assert a nullable 9-channel hormone forecast; `11` parses it as optional content and
   publishes it without changing any judgment; `16` declares the twelfth field.
2. The carried prior-tick forecast is corroborated per channel against the R80 drive into
   corroborate/conflict/silent; only corroborate applies a bounded clamped bias toward the forecast;
   the model can never override the formula.
3. The biased drive is smoothed by the R43 dual-timescale wrapper; the corroborator reads no
   `05`/same-tick `11`/other-owner state; all channels stay in range; a null forecast is the drive
   unchanged.
4. The coupling gain is under the declared `hormone_predict_coupling` category; the mapping lives in
   the `04` owner; the owner-boundary guard is green.
5. Default/offline assemblies and all existing semantic-assembly level assertions are byte-for-byte
   unchanged (fake providers emit no forecast); the full network-free suite is green.
6. `index.md` row 81; the `04`/`11`/`16` `OWNER_GUIDE` entries + `BRAIN_ARCHITECTURE_COMPARISON` note
   record the corroboration with the honest `C_engineering_hypothesis` caveat.
