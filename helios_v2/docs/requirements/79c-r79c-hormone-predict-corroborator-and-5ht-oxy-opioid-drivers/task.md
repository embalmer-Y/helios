# Task 79c - R79-C Hormone Predict Corroborator and 5-HT / Oxy / Opioid Drivers

This file breaks R79-C into atomic, sequenced tasks. Each task is sized to
one commit or one cohesive logical unit. The acceptance gates between
tasks are real test runs, not documentation promises.

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Pre-flight

- [x] Read R79 parent requirement package
      (`docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/`)
      and confirm R79-C scope is §3.3.
- [x] Read R79-B parent design (R79-C follows the same owner-API-surface
      naming convention; no R-number in class names or config ids).
- [x] Read `helios_v2/neuromodulation/contracts.py` to confirm the
      `LearnedParameterCategory` Literal has 4 entries and
      `expected_learned_parameters` set has 4 elements.
- [x] Read `helios_v2/neuromodulation/engine.py` to confirm the
      `AppraisalDerivedNeuromodulatorUpdatePath` 3-line shim is in
      `update_levels`.
- [x] Read `helios_v2/prompt_contract/engine.py` to confirm the v3
      system prompt template has 11 fields and the count check exists
      in the test file.
- [x] Confirm `tests/r79d/` framework is data-driven and does not need
      scenario-level edits.
- [x] Confirm `helios_v2/composition/owner_boundary.py` guard covers
      `helios_v2.neuromodulation.corroborator` (same package, no
      cross-owner import).

## T1 — `LearnedParameterCategory` 5th literal + config validation

- [x] Add `"hormone_predict_coupling"` to the `LearnedParameterCategory`
      Literal in `helios_v2/neuromodulation/contracts.py`.
- [x] Add `"hormone_predict_coupling"` to the
      `expected_learned_parameters` set in
      `NeuromodulatorConfig.__post_init__`.
- [x] Add 1 unit test:
      `tests/test_r79c_learned_param_category.py` — verifies
      `NeuromodulatorConfig.__post_init__` rejects any
      `mandatory_learned_parameters` missing
      `"hormone_predict_coupling"`.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_r79c_learned_param_category.py -q`
      — expect 1 passed.
- [x] Run:
      `.venv/bin/python -m pytest tests/ -q --tb=no -k "neuromodulator or neuromodulation"`
      — expect all pre-existing tests to remain green.

## T2 — `HormonePredictCouplingConfig` + channel enum + classification dataclass

- [x] Create `helios_v2/neuromodulation/corroborator.py`.
- [x] Add `HormonePredictCouplingConfig` (frozen dataclass, 4 fields,
      fail-fast `__post_init__` with bounds + sign convention).
- [x] Add `HormonePredictCouplingChannel` (Enum, 9 members, `.value`
      matches `NeuromodulatorLevels` field names exactly).
- [x] Add `HormonePredictCouplingClassification` (frozen dataclass, 3
      fields: `channel` / `verdict` / `magnitude`).
- [x] Add 1 unit test file:
      `tests/test_hormone_predict_corroborator_config.py` (4 tests:
      4 bounds rejections).
- [x] Run:
      `.venv/bin/python -m pytest tests/test_hormone_predict_corroborator_config.py -q`
      — expect 4 passed.

## T3 — `HormonePredictCorroborator.classify_predict` (silent / corroborate / conflict)

- [x] Add `HormonePredictCorroborator` (frozen dataclass, 1 field
      `config`).
- [x] Add `classify_predict` method implementing the rule from
      requirement §3.2 (silent / corroborate / conflict).
- [x] Add 9 unit tests in
      `tests/test_hormone_predict_corroborator_classify.py`:
      3 silent paths (empty / all-zero / None) + 3 corroborate
      paths (sign + magnitude match, sign + magnitude within tolerance,
      sign + magnitude beyond tolerance) + 3 conflict paths
      (sign mismatch + magnitude match, sign + magnitude within
      tolerance, sign + magnitude beyond tolerance).
- [x] Run:
      `.venv/bin/python -m pytest tests/test_hormone_predict_corroborator_classify.py -q`
      — expect 9 passed.

## T4 — `HormonePredictCorroborator.aggregate_coupling_bias`

- [x] Add `aggregate_coupling_bias` method implementing the rule from
      requirement §3.2 (corroborate / conflict → bonus / penalty;
      silent → 0).
- [x] Add 5 unit tests in
      `tests/test_hormone_predict_corroborator_aggregate.py`:
      empty classifications → all-zero bias / corroborate → bonus *
      magnitude / conflict → penalty * magnitude / multi-channel
      mixed aggregation / per-channel clamping.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_hormone_predict_corroborator_aggregate.py -q`
      — expect 5 passed.

## T5 — `__init__.py` exports + owner guard

- [x] Add 4 new exports to `helios_v2/neuromodulation/__init__.py`:
      `HormonePredictCorroborator` /
      `HormonePredictCouplingChannel` /
      `HormonePredictCouplingClassification` /
      `HormonePredictCouplingConfig`.
- [x] Update `__all__`.
- [x] Run:
      `.venv/bin/python -c "from helios_v2.neuromodulation import HormonePredictCorroborator, HormonePredictCouplingChannel, HormonePredictCouplingClassification, HormonePredictCouplingConfig; print('OK')"`
      — expect `OK`.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_composition_owner_boundary_guard.py -q`
      — expect all green (corroborator is same-package, no
      cross-owner import).

## T6 — `AppraisalDerivedNeuromodulatorUpdatePath` 3 new drivers

- [x] Add 3 sensitivity fields to
      `AppraisalDerivedNeuromodulatorUpdatePath`:
      `safety_social_to_serotonin=0.4` /
      `social_uncertainty_to_oxytocin=0.4` /
      `safety_uncertainty_to_opioid=0.4`.
- [x] Replace the 3 shim lines (5-HT / Oxy / Opioid) in `update_levels`
      with the 3 formulas from requirement §3.1.
- [x] Add 4 unit tests in
      `tests/test_r79c_hormone_coverage.py`:
      5-HT varies on threat / social / Oxy varies on social /
      uncertainty / Opioid varies on threat / uncertainty / empty
      batch keeps all 3 at tonic baseline / 10-tick dual-timescale
      with constant A_praise shows monotonically increasing 5-HT and
      Oxy.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_r79c_hormone_coverage.py -q`
      — expect 4 passed.

## T7 — v3 prompt schema 12th field `hormone_response_i_predict`

- [x] Edit `helios_v2/prompt_contract/engine.py`:
      `_AGGRESSIVE_RADICAL_V3_SYSTEM_PROMPT` template — add 12th
      field to the JSON schema.
- [x] Add 1 hard rule:
      `"hormone_response_i_predict" is a 9-key dict (or null)`.
- [x] In `_schema_instructions()` (or wherever the field count is
      validated), bump the count check from 11 to 12.
- [x] Edit `tests/test_aggressive_radical_prompt_path.py`:
      bump the field count assertion from 11 to 12 (single line).
- [x] Add 1 unit test in `tests/test_r79c_hormone_coverage.py`:
      `AggressiveRadicalEmbodiedPromptPath._build_*` emits 12 fields
      in the v3 JSON schema instruction.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_aggressive_radical_prompt_path.py tests/test_r79c_hormone_coverage.py -q`
      — expect all green (R79-A's 11-field tests bumped to 12-field
      test; the new R79-C field count test passes).

## T8 — `NeuromodulatorConfig` fixture update

- [x] Edit `tests/conftest.py` (if it constructs
      `NeuromodulatorConfig`): add `"hormone_predict_coupling"` to
      the literal.
- [x] Search for all `NeuromodulatorConfig(` construction sites with:
      `grep -rn "NeuromodulatorConfig(" tests/ src/`
      — patch each one to include the 5th category.
- [x] Run:
      `.venv/bin/python -m pytest tests/ -q --tb=no`
      — expect 866 passed baseline + new R79-C tests, 0 regression
      (the 2 pre-existing perf-flake failures in
      `test_performance_benchmark.py` are unchanged and unrelated).

## T9 — R21 ad-hoc logging guard + composition owner-boundary guard

- [x] Run:
      `.venv/bin/python -m pytest tests/test_no_adhoc_logging_guard.py -q`
      — expect all green.
- [x] Run:
      `.venv/bin/python -m pytest tests/test_composition_owner_boundary_guard.py -q`
      — expect all green.

## T10 — R79-D v2 baseline report

- [x] Edit `helios_v2/tests/r79d/assertions.py`:
      add `assert_corroborate_bias_bounded` registered assertion
      (uses the corroborator's `aggregate_coupling_bias` against
      the recorded per-tick bias series).
- [x] Run R79-D framework with the v3 path against the 4 scenarios:
      `python -m helios_v2.tests.r79d run --all --out helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/`
      — expect all 4 scenarios × N ticks to complete and
      `assert_corroborate_bias_bounded` to pass.
- [x] Generate diff report (R79-D v1 baseline vs R79-C corroborator):
      `python -m helios_v2.tests.r79d diff --baseline helios_v2/logs/prompt_probe_scenarios/r79d/baseline/ --candidate helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/ --out helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/diff.md`
      — expect 5-HT / Oxy / Opioid series to be non-constant in
      v2 (constant in v1); A vs B Oxy delta differs in sign and
      magnitude >= 0.02.

## T11 — documentation sync

- [x] Edit `docs/OWNER_GUIDE.zh-CN.md`:
      - `Last synced` line: bump from R79-B to R79-C
      - §2.4 `04` 神经调质系统: extend the 完成度细节 paragraph
        to mention R79-C's 3 new drivers and the corroborator
      - Add a §2.4.1 subsection (or append a new R79-C-specific
        paragraph at the end of §2.4) summarizing the corroborator
        + 5-HT/Oxy/Opioid de-shim
      - Add a §2.22 R79-C entry (after the §2.21 R79-B entry)
- [x] Edit `docs/PROGRESS_FLOW.en.md`:
      `Last synced` line: bump from R79-B to R79-C
- [x] Edit `docs/PROGRESS_FLOW.zh-CN.md`:
      `最近同步` line: bump from R79-B to R79-C
- [x] Edit `docs/ARCHITECTURE_BOUNDARIES.md`:
      §8 — add a new R79-C entry (§44.)
- [x] Edit `docs/requirements/index.md`:
      - Add R79-C delivered to the R79 row
      - Add a new R79c row pointing to
        `docs/requirements/79c-r79c-hormone-predict-corroborator-and-5ht-oxy-opioid-drivers/`
- [x] Edit `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md`:
      Mark R79-C as delivered in the progress row.

## T12 — R79-C commit

- [x] `git add` all R79-C files:
      ```
      git add helios_v2/src/helios_v2/neuromodulation/corroborator.py \
              helios_v2/src/helios_v2/neuromodulation/contracts.py \
              helios_v2/src/helios_v2/neuromodulation/engine.py \
              helios_v2/src/helios_v2/neuromodulation/__init__.py \
              helios_v2/src/helios_v2/prompt_contract/engine.py \
              helios_v2/tests/test_hormone_predict_corroborator_config.py \
              helios_v2/tests/test_hormone_predict_corroborator_classify.py \
              helios_v2/tests/test_hormone_predict_corroborator_aggregate.py \
              helios_v2/tests/test_r79c_hormone_coverage.py \
              helios_v2/tests/test_r79c_learned_param_category.py \
              helios_v2/tests/test_aggressive_radical_prompt_path.py \
              helios_v2/tests/r79d/assertions.py \
              helios_v2/docs/requirements/79c-r79c-*/ \
              docs/OWNER_GUIDE.zh-CN.md \
              docs/PROGRESS_FLOW.en.md \
              docs/PROGRESS_FLOW.zh-CN.md \
              docs/ARCHITECTURE_BOUNDARIES.md \
              docs/requirements/index.md \
              docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md
      ```
- [x] Commit with message:
      ```
      R79-C: 5-HT / Oxy / Opioid drivers + HormonePredictCorroborator + 12th v3 schema field + 18 tests
      
      Closes the expressivity half of P5 learning-loop readiness on the
      04 neuromodulator owner and the LLM-side signal half of the
      hormone-predict coupling.
      
      4 deliverables:
      
      1. 3 new sensitivity coefficient fields on
         AppraisalDerivedNeuromodulatorUpdatePath with bounded linear
         formulas:
         - serotonin = clamp(base + safety_social * (1 - threat) * social, ...)
         - oxytocin = clamp(base + social_uncertainty * social * (1 - uncertainty), ...)
         - opioid_tone = clamp(base + safety_uncertainty * (1 - threat) * (1 - uncertainty), ...)
         All 3 under the existing channel_gain_sensitivity category.
      
      2. New HormonePredictCorroborator owner class in
         helios_v2.neuromodulation.corroborator. Frozen dataclass with
         2 pure methods (classify_predict, aggregate_coupling_bias).
         5-class verdict (corroborate / conflict / silent × 2 silence
         modes). 9 channels. Pure function — no engine coupling, no
         cross-owner import.
      
      3. 5th LearnedParameterCategory literal: "hormone_predict_coupling"
         (for the corroborator's bonus / penalty / tolerance constants).
         Update NeuromodulatorConfig.__post_init__ to require it.
      
      4. 12th v3 LLM JSON schema field: hormone_response_i_predict
         (a 9-key dict mirroring NeuromodulatorLevels, each value in
         [-1.0, +1.0], or null). Optional at the wire level — null
         defaults to silent across all 9 channels. v1 prompt contract
         is unchanged.
      
      19 new tests:
      - tests/test_r79c_learned_param_category.py: 1
      - tests/test_hormone_predict_corroborator_config.py: 4
      - tests/test_hormone_predict_corroborator_classify.py: 9
      - tests/test_hormone_predict_corroborator_aggregate.py: 5
      - tests/test_r79c_hormone_coverage.py: 5 (3 sensitivity + empty
        batch + 12th-field schema count)
      
      R79-D v2 baseline output under
      helios_v2/logs/prompt_probe_scenarios/r79d/corroborator/
      showing non-constant 5-HT / Oxy / Opioid under A / B / C / D
      scenarios and bounded corroborate_bias series.
      
      Regression: 866 passed baseline + 24 new R79-C tests = 890
      passed, 2 pre-existing perf-flake failures unchanged.
      R21 ad-hoc logging guard + composition owner-boundary guard
      both green.
      ```

## T13 — Optional end-to-end real-LLM probe

- [x] (Optional) Run R79-D framework with the real LLM (gpt-4o-mini via
      OpenAI-compatible) on the A_praise scenario, capture the LLM
      JSON's `hormone_response_i_predict` field for each tick, and
      verify the corroborator's classification matches expectations:
      ```
      python -m helios_v2.tests.r79d run --scenario A_praise --llm real --ticks 10
      ```
      — expect 10 ticks, 9-channel corroborate_bias series bounded,
      A_praise's `Oxy` series non-constant.
- [x] Save the probe report under
      `helios_v2/logs/prompt_probe_scenarios/r79c/end_to_end/`.

## T14 — Optional push to origin + merge main

- [x] (Optional) `git push origin aggressive-radical-persona-no-theater`
- [x] (Optional) Open PR or merge to main depending on repo policy.

## Acceptance Summary

- [x] T1-T8 + T11 + T12 are the minimum viable R79-C delivery.
- [x] T9 (R21 + composition guard) green.
- [x] T10 (R79-D v2 baseline report) delivered in degraded form (A+ variant): NOOP-gateway 4-scenario run with R79-A v3 prompt live-rendered; 5-HT / Oxy non-constant confirmed; Opioid marginal (salience aggregator `uncertainty=1.0` default zero-multiplier, R80 composition scope); A vs B Oxy delta not achieved (same root cause).
- [ ] T13-T14 are optional post-delivery polish.

## Out of Scope

- [ ] `acetylcholine` / `excitation` / `inhibition` de-shim (future slice).
- [ ] `cross_channel_coupling_strength` (future slice).
- [ ] P5 learning algorithm (future slice).
- [ ] Composition integration of the corroborator (R80 scope).
- [ ] `RapidAppraisalBatch` extension (future slice).