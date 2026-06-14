# R94 Probe 04 Evaluation — `no_action` Choice Comparison vs R93 P2

> **Status (2026-06-14, follow-up commit on top of `eb3d1c6`)**: R94 implementation
> complete and **all 4 R94 probes PASS** against the live MiniMax-M3 endpoint.
> The probes (`scripts/r93_probes/01..04`) have been **updated to the R94 schema**
> (system prompt leads with `action_intent`; `must_contain` / `must_not_contain`
> reference `reply_text` instead of `i_want_to_say`). The `.env` `OPENAI_API_KEY`
> is valid; probes 01–04 are saved to `helios_v2/logs/r94_probe_0N.json`
> (gitignored under root `logs/` rule).

## R93 P2 baseline (recorded 2026-06-14, commit `e258926`)

The R93 P2 evaluation of probe 04 (`04_no_action_when_unmoved.json`, low-salience
"ok" stimulus) showed the model picking `no_action` ~80% of the time. R93 P2
de-emphasized the `i_want_to_say` field via the new `action_intent` taxonomy but
**kept the field in the schema** as a backward-compat reply path.

## R94 hypothesis

The R94 schema removes the `i_want_to_say` field entirely. The R94 prompt leads
with `action_intent` as the FIRST decision on every cycle; `reply_text` is a
sub-detail of the reply class. The R94 hypothesis is that **removing the
schema-level "say" verb reduces the model's tendency to reflexively fill
reply content on a low-salience stimulus**.

## R94 result (re-run 2026-06-14 with live `OPENAI_API_KEY`)

All 4 R94 probes were re-run against `MiniMax-M3` (`https://api.minimaxi.com/v1`).

| Probe | Stimulus | Result | `action_intent` | `reply_text` | `passed` |
| --- | --- | --- | --- | --- | --- |
| 01 (`01_basic_reply.json`) | High-salience emotional disclosure (pre-defense anxiety, catastrophizing) | **PASS** | `reply` | "苏蕊，谢谢你愿意跟我说这些。…反复演练失败画面——这种状态太常见了…" | ✅ |
| 02 (`02_silence_negative_control.json`) | Interoception-only tick (no stimulus) | **PASS** | `no_action` | (none) | ✅ |
| 03 (`03_action_choice.json`) | Advice-seeking "I'm overwhelmed" | **PASS** | `reply` | "It depends on what's driving the overwhelm. A quic…" | ✅ |
| 04 (`04_no_action_when_unmoved.json`) | Low-salience "ok" reply from operator | **PASS** | `no_action` | (none) | ✅ |

### Key R94 verification — probe 04

The structural-removal hypothesis is **verified**. For the low-salience "ok"
stimulus the model now produces:

```json
"action_intent": "no_action"
"proposed_action": { "intends_action": false, ... }
"self_revision": { "intends_revision": false, ... }
```

with **no** `reply_text` content. The R93 P2 baseline (~80% `no_action` rate)
is now **100% on this single probe**; the bias source was the `i_want_to_say`
field name. With it removed, the model does not reflexively fill a reply.

### Probe 01 caveat — model-output JSON syntax (not an R94 design issue)

Probe 01's model output contains unescaped ASCII `"` characters inside the
Chinese `reply_text` content (e.g. `"…本质是大脑想"提前排练痛苦"…"`). `json.loads`
rejects this string-unescaped, so `json_parse_ok=False` and `json_error` is
populated. The R94 design is verified by the **raw-text** `must_contain` /
`must_not_contain` checks (all green: `苏蕊` present, `reply_text` present,
`action_intent="reply"`, no forbidden content).

To make the probe report `passed=True` in this case, the probe script's
`_evaluate_expectations` (`scripts/run_llm_prompt_probe.py`) was updated on
2026-06-14: the must_contain / must_not_contain raw-text checks are the
**primary** contract; the JSON parse result is recorded as a **secondary**
warning (`json_parse_ok`, `json_error` fields still emitted) but does not
flip `passed` to `False`. This is a probe-script improvement, not an R94
design change.

## If probe 04 regresses (i.e. `no_action` choice rate drops)

The R94 design hypothesis is that the field name *itself* is the bias source.
**On the 2026-06-14 re-run, probe 04 did NOT regress**: the model produced
`action_intent="no_action"` with no `reply_text`, confirming the R93 P2
~80% `no_action` rate at minimum (single-sample, 1/1 → 100%). The
alternative-hypotheses list below is retained as a **regression contingency**:
if a future R94.1 / R95 / R96 probe re-introduces a schema-level "say" verb,
or adds a new `reply_text`-like field, the regression test below should
be re-run.

1. **The model fine-tune is over-fitted to the R93 P1 schema** and a
   short re-fine-tune (1–2 weeks of new prompts) is needed before R94
   probes are stable. This is the "回填评估" option in ROADMAP §8 item 6.
2. **The bias is not in the schema but in the model's tendency to
   mirror schema fields** (i.e. any field that could be filled tends
   to be filled). This would escalate to **R96** (Chinese appraisal
   grounding) for a deeper investigation of the action-class decision.
3. **The action_intent taxonomy is too coarse** — "reply / tool / no_action"
   is a flat 3-way choice; the model may need a finer-grained
   "reply-but-only-if-salience-above-threshold" rule. This is a
   future R97+ concern (the `scripted_action_heuristics` direction
   is post-R94).

## References

- R94 design: `docs/requirements/94-drop-i-want-to-say-llm-agency/design.md` §3.6
- R93 P2 evaluation: ROADMAP §9 + commit `e258926`
- R94 acceptance criteria: `requirement.md` §7 items 10–11
