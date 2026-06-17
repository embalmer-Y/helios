# Requirement 98 - Hormone Prediction Prompt Coaching (R98 Scope Extension)

## 1. Background and Problem

R98 (post-LLM appraisal adjustment) delivered a bounded architecture that translates the LLM's `hormone_response_i_predict` field into a per-tick appraisal Δ adjustment via `PostLLMHormoneAdjuster`. The network-free closure tests pass (4/4), confirming the architecture is correctly wired.

However, the honest real-cloud 85-utterance verdict (2026-06-16) reveals that the LLM rarely produces actionable hormone predictions:

- Only 5/85 (6%) of LLM responses include a parseable `hormone_response_i_predict` field
- Of those 5, only 1 contains `cortisol` (the threat channel)
- The LLM is biased toward reward-leaning predictions: warm empathy contexts produce `oxytocin: "increase"` but never `cortisol: "elevated"` for distress/threat contexts
- Cortisol positive-vs-negative separation is -0.0118 vs baseline -0.0095 (directional shift -0.0023, slight regression, not a headline closure)

Root cause: the system prompt's description of `hormone_response_i_predict` is `{<optional forecast>}` (line 1109 of `internal_thought/engine.py`). This tells the LLM nothing about:
- What each neuromodulator channel represents emotionally
- When to fill specific channels for specific emotional contexts
- That `cortisol` should be elevated when the present field contains distress/threat signals

The `PostLLMHormoneAdjuster` architecture is correct; the upstream LLM behavior is the bottleneck. This scope extension addresses the LLM behavior gap through prompt coaching — adding semantic guidance to the `hormone_response_i_predict` field description so the LLM understands what to forecast and when.

## 2. Goal

Make the LLM reliably produce `cortisol: "elevated"` (or `cortisol: ≥0.7`) for negative-valence contexts and `dopamine: "elevated"` / `oxytocin: "elevated"` for positive-valence contexts, by expanding the `hormone_response_i_predict` field description in the system prompt with emotional-context-to-channel mapping guidance and bilingual examples. Target: ≥80% of negative-valence probe utterances produce a cortisol forecast, and 85-utterance real-cloud cortisol separation ≥ 0.10.

## 3. Functional Requirements

### 3.1 Hormone prediction semantic guidance
1. The `hormone_response_i_predict` schema line in `_build_messages` must expand from `{<optional forecast>}` to a description that explains each channel's emotional meaning and when the LLM should forecast it.
2. The expanded description must include a concise mapping: distress/threat → cortisol elevated; social warmth/reward → oxytocin/dopamine elevated; uncertainty/novelty → norepinephrine elevated.
3. The expanded description must provide 2-3 bilingual (Chinese + English) example predictions covering negative-valence, positive-valence, and neutral contexts.
4. The expanded description must preserve the anti-theatrical constraint: it guides the LLM's *forecast accuracy*, not its *emotional performance*. The LLM should forecast what its neuromodulator state *would* be, not perform emotions.

### 3.2 v3 embodied prompt schema alignment
1. The `_V3_RESPONSE_SCHEMA` in `prompt_contract/engine.py` must be updated with the same channel-to-emotion mapping, keeping the existing field list and hard rules intact. The addition is additive: the current "omit it or set it to null if you have no such sense" clause remains, but is supplemented with "when you do forecast, map the context to the appropriate channels as follows".

### 3.3 No architecture or owner boundary changes
1. `PostLLMHormoneAdjuster` translation rules, magnitude caps, confidence weights, and channel map must remain byte-for-byte unchanged.
2. `04` drive formula and composition wiring must remain unchanged.
3. No new owner, no new carry holder, no new stage, no new contract field.
4. The `_optional_hormone_prediction` parser and `_HORMONE_PREDICTION_CHANNELS` list must remain unchanged — the LLM still produces the same JSON shape; the change only affects how often and how accurately it fills it.

## 4. Non-Functional Requirements

1. **Performance**: prompt text addition is under 200 characters (measured by counting new system_lines entries). The LLM's token budget must not be materially affected.
2. **Reliability**: the expanded description must not cause the LLM to always fill `hormone_response_i_predict` (it must remain optional — the LLM may still omit it for truly neutral cycles).
3. **Compatibility**: all 1157 existing network-free tests must pass unchanged. The parser, contracts, and engine code paths are byte-for-byte identical except for the prompt text content.
4. **Migration**: default-off is not applicable — the prompt coaching is always active when `11` fires (it is prompt text, not a runtime toggle). No opt-in or opt-out needed.

## 5. Code Behavior Constraints

1. **Forbidden**: hardcoding specific cortisol values in the prompt (e.g., "always set cortisol to 0.8") — this would violate the anti-theatrical principle by telling the LLM what value to produce regardless of context.
2. **Forbidden**: adding a runtime toggle or opt-in for the coaching text — it is always part of the system prompt when `11` fires.
3. **Boundary**: `11` internal_thought owner owns the prompt text; `03` appraisal owner owns the translation rules; composition is owner-neutral wiring. This scope extension only changes prompt text content in `11`; it does not change `03` translation rules or `04` drive formulas.
4. **Anti-theatrical**: the coaching text must frame `hormone_response_i_predict` as a *self-forecast* ("what your neuromodulator state would shift toward"), not as a *performance instruction* ("show that you feel anxious"). The LLM forecasts its own state; it does not perform emotions for the user.

## 6. Impacted Modules

1. `helios_v2/internal_thought/engine.py` — `_build_messages` method, `hormone_response_i_predict` schema line expansion
2. `helios_v2/prompt_contract/engine.py` — `_V3_RESPONSE_SCHEMA` string, hormone channel-to-emotion mapping addition
3. `helios_v2/tests/test_internal_thought_engine.py` — update test fixtures that assert system prompt content
4. `helios_v2/tests/test_prompt_contract_v2.py` — update tests that assert v3 schema text
5. `docs/requirements/index.md` — R98 entry update
6. `docs/PROGRESS_FLOW.zh-CN.md` and `docs/PROGRESS_FLOW.en.md` — sync

## 7. Acceptance Criteria

1. The system prompt produced by `_build_messages` contains a `hormone_response_i_predict` description that mentions at least cortisol, dopamine, oxytocin, and norepinephrine with their emotional context mappings.
2. The system prompt contains at least one Chinese-language example prediction showing `cortisol` elevated for a distress context.
3. The `_V3_RESPONSE_SCHEMA` in `prompt_contract/engine.py` contains the same channel-to-emotion mapping.
4. All 1157 existing network-free tests pass unchanged (0 regression).
5. New network-free test: `test_hormone_prediction_guidance_in_system_prompt` asserts the system prompt contains the coaching text and at least one bilingual example.
6. Real-LLM probe: ≥80% of negative-valence probe utterances (anxiety/grief/anger) produce a `hormone_response_i_predict` containing `cortisol ≥ 0.6` or `cortisol: "elevated"` (verified by `scripts/run_llm_prompt_probe.py`).
7. Real-LLM probe: positive-valence utterances produce reward-leaning forecasts (dopamine/oxytocin elevated) and not cortisol elevated.
8. Real-LLM probe: neutral/low-salience utterances produce null or omitted `hormone_response_i_predict` (the field remains optional, not mandatory).
