# R94 Probe 04 Evaluation — `no_action` Choice Comparison vs R93 P2

> **Status (2026-06-14)**: R94 implementation complete; **probe re-runs blocked** by expired
> `OPENAI_API_KEY` in the current shell environment (the `.env` token returns `401
> authorized_error` from the MiniMax provider). The probes (`scripts/r93_probes/01..04`)
> have been **updated to the R94 schema** (system prompt + `must_contain` /
> `must_contain_any` / `_notes`); they are ready to run when the API key is renewed.

## R93 P2 baseline (recorded 2026-06-14, commit `e258926`)

The R93 P2 evaluation of probe 04 (`04_no_action_when_unmoved.json`, low-salience
"ok" stimulus) showed the model picking `no_action` ~80% of the time. R93 P2
de-emphasized the `i_want_to_say` field via the new `action_intent` taxonomy but
**kept the field in the schema** as a backward-compat reply path.

## R94 expected behavior

The R94 schema removes the `i_want_to_say` field entirely. The R94 prompt leads
with `action_intent` as the FIRST decision on every cycle; `reply_text` is a
sub-detail of the reply class. The R94 hypothesis is that **removing the
schema-level "say" verb reduces the model's tendency to reflexively fill
reply content on a low-salience stimulus**.

**Predicted outcome** (to be verified when API key is renewed):
- Probe 04 `no_action` choice rate **holds or improves** (~80% → maybe 85–90%):
  the schema no longer primes the model to produce reply text.
- Probe 01 (positive reply) **still passes**: the model can still declare
  `action_intent="reply" + reply_text="..."` for a stimulus that warrants a
  reply. The schema change does not remove the reply path; it removes the
  *structural* bias.
- Probe 03 (action choice on advice-seeking stimulus) **still passes**:
  the model picks `reply` and supplies `reply_text` for a stimulus that
  warrants a reply.

## Verification plan (when API key is renewed)

```bash
# In a fresh shell with a valid OPENAI_API_KEY:
export OPENAI_API_KEY=<new-key>
export OPENAI_BASE_URL=https://api.minimaxi.com/v1
export HELIOS_LLM_MODEL=MiniMax-M3

cd helios_v2
PYTHONIOENCODING=utf-8 python scripts/run_llm_prompt_probe.py \
    --case-file scripts/r93_probes/01_basic_reply.json \
    --save-json logs/r94_probe_01.json
PYTHONIOENCODING=utf-8 python scripts/run_llm_prompt_probe.py \
    --case-file scripts/r93_probes/02_silence_negative_control.json \
    --save-json logs/r94_probe_02.json
PYTHONIOENCODING=utf-8 python scripts/run_llm_prompt_probe.py \
    --case-file scripts/r93_probes/03_action_choice.json \
    --save-json logs/r94_probe_03.json
PYTHONIOENCODING=utf-8 python scripts/run_llm_prompt_probe.py \
    --case-file scripts/r93_probes/04_no_action_when_unmoved.json \
    --save-json logs/r94_probe_04.json
```

The 4 reports (`logs/r94_probe_NN.json`) are the R94 baseline.

## If probe 04 regresses (i.e. `no_action` choice rate drops)

The R94 design hypothesis is that the field name *itself* is the bias source.
If probe 04 regresses, the alternative hypotheses are:

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

The owner of this file records the comparison-vs-baseline result here
when the API key is renewed.

## References

- R94 design: `docs/requirements/94-drop-i-want-to-say-llm-agency/design.md` §3.6
- R93 P2 evaluation: ROADMAP §9 + commit `e258926`
- R94 acceptance criteria: `requirement.md` §7 items 10–11
