# Requirement 98 - Hormone Prediction Prompt Coaching (Task Breakdown)

## 1. Title

Requirement 98 - Hormone Prediction Prompt Coaching (R98 Scope Extension)

## 2. Task Breakdown

### T1: Expand `hormone_response_i_predict` schema in `_build_messages`
- **What**: Replace the single line `"hormone_response_i_predict": {<optional forecast>},` (line 1109 of `internal_thought/engine.py`) with a multi-line description that includes channel-to-emotion mappings and bilingual examples.
- **Dependency**: None
- **Touched modules**: `helios_v2/internal_thought/engine.py`
- **Completion definition**: The `_build_messages` method produces a system prompt where the `hormone_response_i_predict` field description contains at least cortisol→distress, dopamine→reward, oxytocin→warmth mappings, at least one Chinese example, and still marks the field as optional.
- **Validation**: Run `test_internal_thought_engine.py` tests that check system prompt content; manually inspect the output of `_build_messages` with standard fixtures.

### T2: Expand `_V3_RESPONSE_SCHEMA` in prompt_contract engine
- **What**: Update the `_V3_RESPONSE_SCHEMA` string constant in `prompt_contract/engine.py` (lines 162-179) to add channel-to-emotion mapping ("dopamine (reward/warmth)", "cortisol (distress/threat/loss)", etc.) and bilingual distress/warmth guidance phrases, keeping all existing hard rules intact.
- **Dependency**: None (parallel with T1)
- **Touched modules**: `helios_v2/prompt_contract/engine.py`
- **Completion definition**: The `_V3_RESPONSE_SCHEMA` contains channel-to-emotion mapping and bilingual guidance while preserving all existing `Hard rules` text byte-for-byte.
- **Validation**: Run `test_prompt_contract_v2.py` tests; manually inspect `_V3_RESPONSE_SCHEMA` content.

### T3: Add network-free regression test for hormone guidance
- **What**: Add `test_hormone_prediction_guidance_in_system_prompt` in `tests/test_internal_thought_engine.py` that constructs a standard `InternalThoughtRequest`, calls `_build_messages`, and asserts:
  - System message contains "cortisol" paired with "distress" or "threat" or "loss"
  - System message contains at least one Chinese example substring ("焦虑" or "丧亲" or "恐惧" or "升")
  - System message contains "dopamine" paired with "reward" or "warmth"
  - System message still contains "optional" or "omit" or "null" (field remains optional)
  - System message does NOT contain performance instructions ("show", "perform", "act anxious")
- **Dependency**: T1
- **Touched modules**: `helios_v2/tests/test_internal_thought_engine.py`
- **Completion definition**: New test passes; existing 1157 tests all pass unchanged.
- **Validation**: Run `pytest tests/test_internal_thought_engine.py -k hormone_prediction_guidance`

### T4: Run full test suite regression check
- **What**: Run the complete network-free test suite to confirm 0 regression from T1+T2+T3 changes.
- **Dependency**: T1, T2, T3
- **Touched modules**: None (validation only)
- **Completion definition**: 1157+ passed / 4 skipped / 0 regression.
- **Validation**: `pytest helios_v2/tests/ -x --timeout=60`

### T5: Create and run real-LLM probe validation
- **What**: Create 6 JSON probe case files under `helios_v2/scripts/r98_prompt_coaching_probes/` covering grief, anxiety, joy, neutral, anger, and warmth contexts. Run them against the real configured LLM using `scripts/run_llm_prompt_probe.py`. Record outcomes.
- **Dependency**: T1, T2 (prompt text must be in place for probe)
- **Touched modules**: `helios_v2/scripts/r98_prompt_coaching_probes/` (new directory)
- **Completion definition**: ≥80% of negative-valence probes (01_grief, 02_anxiety, 05_anger) produce `hormone_response_i_predict` with cortisol ≥ 0.6 or phrase "elevated"/"升"/"高". Positive-valence probes (03_joy, 06_warmth) produce reward forecasts. Neutral probe (04_neutral) omits or nulls the field.
- **Validation**: `python helios_v2/scripts/run_llm_prompt_probe.py` with each case file; inspect JSON reports.

### T6: Update documentation sync
- **What**: Update `docs/requirements/index.md` with R98 scope extension note. Update `docs/PROGRESS_FLOW.zh-CN.md` and `docs/PROGRESS_FLOW.en.md` top-line sync note. Update `docs/ROADMAP.zh-CN.md` §1 top-line pointer. Update `docs/OWNER_GUIDE.zh-CN.md` and `docs/OWNER_GUIDE.md` `11` section note about prompt coaching. Update `docs/ARCHITECTURE_BOUNDARIES.md` top-line sync note.
- **Dependency**: T4 (tests must pass first)
- **Touched modules**: Multiple docs files
- **Completion definition**: All 6 docs files updated with R98 prompt coaching scope extension reference.
- **Validation**: Manual review of each doc file's top-line sync note referencing R98 prompt coaching.

## 3. Dependencies

- T1 and T2 are independent (parallel)
- T3 depends on T1
- T4 depends on T1, T2, T3
- T5 depends on T1, T2 (prompt text must be in place)
- T6 depends on T4 (tests must pass first)

## 4. Files and Modules

| File | Role |
|------|------|
| `helios_v2/src/helios_v2/internal_thought/engine.py` | T1: expand `_build_messages` hormone schema |
| `helios_v2/src/helios_v2/prompt_contract/engine.py` | T2: expand `_V3_RESPONSE_SCHEMA` |
| `helios_v2/tests/test_internal_thought_engine.py` | T3: new regression test |
| `helios_v2/scripts/r98_prompt_coaching_probes/` | T5: real-LLM probe cases |
| `docs/requirements/index.md` | T6: index update |
| `docs/PROGRESS_FLOW.zh-CN.md` | T6: progress flow sync |
| `docs/PROGRESS_FLOW.en.md` | T6: progress flow sync |
| `docs/ROADMAP.zh-CN.md` | T6: roadmap pointer |
| `docs/OWNER_GUIDE.zh-CN.md` | T6: owner guide note |
| `docs/OWNER_GUIDE.md` | T6: owner guide note |
| `docs/ARCHITECTURE_BOUNDARIES.md` | T6: boundary sync |

## 5. Implementation Order

```
T1 (build_messages expansion) ──┐
                                 ├── T3 (regression test) ── T4 (full suite) ── T6 (docs sync)
T2 (v3 schema expansion) ───────┘                                 │
                                                                 T5 (real-LLM probes, after T4)
```

T1 and T2 can be done in parallel. T3 follows T1. T4 requires T1+T2+T3. T5 requires T1+T2 but can run after T4. T6 requires T4.

## 6. Validation Plan

1. T3 test: `pytest helios_v2/tests/test_internal_thought_engine.py -k hormone_prediction_guidance -v`
2. T4 full suite: `pytest helios_v2/tests/ -x --timeout=60`
3. T5 real-LLM probes: manual execution with `scripts/run_llm_prompt_probe.py`

## 7. Completion Criteria

1. T1-T3 produce code changes with 0 regression (1157+ passed / 4 skipped).
2. T4 confirms full suite green.
3. T5 real-LLM probes show ≥80% cortisol forecast rate for negative-valence contexts.
4. T6 documentation is synced across all 6 files.
5. Single git commit with message: "R98 scope extension: hormone prediction prompt coaching (cortisol guidance + bilingual examples)"
