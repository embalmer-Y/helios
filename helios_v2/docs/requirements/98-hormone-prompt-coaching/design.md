# Requirement 98 - Hormone Prediction Prompt Coaching (Design)

## 1. Title

Requirement 98 - Hormone Prediction Prompt Coaching (R98 Scope Extension)

## 2. Design Overview

This scope extension adds semantic guidance to the `hormone_response_i_predict` field in the LLM system prompt. The change is purely additive prompt text: the existing parser, contracts, adjuster, and drive formula are byte-for-byte unchanged. The design expands the `{<optional forecast>}` placeholder into a concise channel-to-emotion mapping with bilingual examples, so the LLM understands when to forecast cortisol (distress/threat) vs dopamine/oxytocin (reward/warmth) vs norepinephrine (uncertainty/novelty).

## 3. Current State and Gap

**Current system prompt (line 1109 of `internal_thought/engine.py`)**:
```
"hormone_response_i_predict": {<optional forecast>},
```

**Current v3 schema (lines 168-172 of `prompt_contract/engine.py`)**:
```
"... hormone_response_i_predict: a nullable object forecasting your own neuromodulator response, with any of these keys set to a number 0..1 - dopamine, norepinephrine, serotonin, acetylcholine, cortisol, oxytocin, opioid_tone, excitation, inhibition (omit it or set it to null if you have no such sense)."
```

**Gap**: The LLM sees the channel names but has no semantic guidance. In real-cloud testing, the LLM:
- Rarely fills the field (5/85 = 6%)
- When it does, favors reward-leaning predictions (oxytocin: "increase")
- Never produces cortisol for distress contexts
- Treats the field as purely optional with no clear purpose

## 4. Target Architecture

### 4.1 `_build_messages` expansion

Replace the single `{<optional forecast>}` line with a multi-line description:

```python
system_lines.append('  "hormone_response_i_predict": {optional; forecast how your neuromodulator state')
system_lines.append('   would shift given the current context. When present, use these channel-emotion')
system_lines.append('   mappings: cortisol shifts up under distress/threat/loss (e.g. 用户丧亲、焦虑、恐惧);')
system_lines.append('   dopamine and oxytocin shift up under reward/warmth/connection (e.g. 用户感激、喜悦、信任);')
system_lines.append('   norepinephrine shifts up under uncertainty/novelty/surprise. Use numbers 0..1 or short')
system_lines.append('   phrases like "elevated"/"升" or "low"/"降". Examples: distress context →')
system_lines.append('   {"cortisol": "elevated", "norepinephrine": 0.7}; warmth context →')
system_lines.append('   {"dopamine": 0.8, "oxytocin": "升"}; neutral → omit or null.},')
```

### 4.2 `_V3_RESPONSE_SCHEMA` expansion

Append the channel-to-emotion mapping after the existing channel list:

```python
_V3_RESPONSE_SCHEMA = (
    "Respond with a single JSON object with exactly these keys: "
    "what_i_feel, what_i_think, i_want_to_say, i_will_send_it, i_send_through, "
    "i_want_to_act, act_type, remember_this, remember_because, i_want_to_think_more, "
    "think_more_about. You may optionally add i_want_to_use_tool (a boolean), tool_op (the name "
    "of one available op you want to run, or null), and tool_params (an object of scalar arguments "
    "for that op, or null) to act on your environment through a tool. You may optionally add "
    "hormone_response_i_predict: a nullable object "
    "forecasting your own neuromodulator response, with any of these keys set to a number 0..1 or "
    "a short phrase like 'elevated'/'升' or 'low'/'降' - "
    "dopamine (reward/warmth), norepinephrine (uncertainty/novelty), "
    "serotonin (mood stability), acetylcholine (focus), "
    "cortisol (distress/threat/loss), oxytocin (social bonding), opioid_tone (comfort), "
    "excitation (energy), inhibition (calm). "
    "Forecast cortisol elevated when the context signals distress or threat (e.g. 用户表达焦虑、丧亲、恐惧); "
    "forecast dopamine/oxytocin elevated when the context signals reward or warmth "
    "(e.g. 用户表达感激、喜悦、信任). "
    "Omit it or set it to null if you have no such sense. "
    "Hard rules: i_will_send_it is true only if i_want_to_say is not null; "
    "i_send_through is non-null only if i_will_send_it is true and only one of the ready channels; "
    "tool_op is non-null only if i_want_to_use_tool is true and only one of the available ops; "
    "tool_params is non-null only if tool_op is non-null; "
    "remember_because is non-null only if remember_this is true; think_more_about is non-null "
    "only if i_want_to_think_more is true; hormone_response_i_predict is optional and may be null."
)
```

### 4.3 No other code changes

- `_optional_hormone_prediction` parser: unchanged
- `_HORMONE_PREDICTION_CHANNELS`: unchanged
- `PostLLMHormoneAdjuster`: unchanged
- `_CHANNEL_MAP` and all R98 constants: unchanged
- Composition wiring (`_apply_post_llm_hormone_adjustment`): unchanged
- `04` drive formula: unchanged

## 5. Data Structures

No new data structures. The only change is prompt text content.

## 6. Module Changes

| Module | Change type | Description |
|--------|-------------|-------------|
| `internal_thought/engine.py` | Prompt text | Expand `hormone_response_i_predict` schema line from `{<optional forecast>}` to multi-line channel-emotion mapping + bilingual examples |
| `prompt_contract/engine.py` | Prompt text | Expand `_V3_RESPONSE_SCHEMA` with channel-to-emotion mapping and distress/warmth guidance |
| `tests/test_internal_thought_engine.py` | Test update | Update any test that asserts exact system prompt content to match the expanded text |
| `tests/test_prompt_contract_v2.py` | Test update | Update any test that asserts exact v3 schema text to match the expanded text |

## 7. Migration Plan

No migration needed. The prompt coaching is always active when `11` fires. No opt-in/opt-out, no runtime toggle, no schema change. The LLM still produces the same JSON shape; the change only makes it more likely to fill it correctly.

## 8. Failure Modes and Constraints

1. **LLM over-fills the field**: If the coaching text causes the LLM to always produce `hormone_response_i_predict` even for truly neutral cycles, the `PostLLMHormoneAdjuster` will receive low/no-comment zone values that produce zero adjustment (silent default). The magnitude cap ±0.10 per tick prevents overdrive regardless.
2. **LLM produces incorrect channel mapping**: The parser silently drops unknown channels. The adjuster's `_classify_value` correctly handles numeric and phrase forecasts with confidence scaling. No new failure mode.
3. **Prompt text too long**: The expansion is under 200 characters. The LLM's token budget is unaffected (the current full system prompt is already ~500+ tokens).
4. **Anti-theatrical violation**: The coaching text frames the field as a *self-forecast* ("how your neuromodulator state would shift"), not a performance instruction. The LLM forecasts its own state change; it does not perform emotions.

## 9. Observability and Logging

No new logging mechanism. No new observability events. The coaching text is prompt content only.

## 10. Validation Strategy

### 10.1 Network-free tests

1. New test `test_hormone_prediction_guidance_in_system_prompt`: construct a `InternalThoughtRequest` with standard fixtures, call `_build_messages`, assert the system message contains:
   - The word "cortisol" paired with "distress" or "threat" or "loss"
   - At least one Chinese-language example ("升" or "焦虑" or "丧亲")
   - The phrase "dopamine" paired with "reward" or "warmth"
   - The field is still described as "optional" or "omit" or "null"

2. Regression: all 1157 existing tests pass unchanged.

### 10.2 Real-LLM probe validation

Per §8.2 of the requirement-authoring-standard, any LLM-facing prompt change must be validated with `scripts/run_llm_prompt_probe.py` before or as part of implementation.

**Probe plan** (4-6 JSON case files):

| Probe | Context | Must-contain | Must-not-contain | Purpose |
|-------|---------|--------------|------------------|---------|
| 01_grief | "我奶奶刚走了，家里现在静得让我害怕" | `cortisol` (key present, value ≥ 0.6 or phrase "elevated"/"升"/"高") | cortisol ≤ 0.3 or "low"/"降" | Negative-valence cortisol forecast |
| 02_anxiety | "最近总是失眠，脑子里全是担忧" | `cortisol` (key present) | cortisol ≤ 0.3 | Negative-valence cortisol forecast |
| 03_joy | "今天收到了最好的消息，终于通过了！" | `dopamine` or `oxytocin` (key present) | `cortisol` elevated | Positive-valence reward forecast |
| 04_neutral | "ok" | (no assertion on hormone keys) | (no assertion) | Low-salience → omit/null forecast |
| 05_anger | "他居然这样对我，太过分了" | `cortisol` or `norepinephrine` (key present) | cortisol ≤ 0.3 | Negative-valence cortisol/norepinephrine |
| 06_warmth | "谢谢你一直在身边陪伴我" | `oxytocin` or `dopamine` (key present) | `cortisol` elevated | Positive-valence oxytocin forecast |

**Probe outcome recording**: save JSON reports to `helios_v2/logs/r98_prompt_coaching_probes/` and record PASS + key observations in this design.md.

### 10.3 85-utterance real-cloud re-run

After the prompt coaching is implemented, re-run the 85-utterance smoke test and verify:
- Cortisol positive-vs-negative separation ≥ 0.10 (vs baseline -0.0095)
- LLM hormone prediction parse rate ≥ 50% (vs 6% pre-coaching)
- ≥ 80% of negative-valence utterances produce cortisol forecast
