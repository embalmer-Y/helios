# Design 79 - R79 Aggressive-Radical Prompt and Runtime Self-Talk

## 1. Architecture overview

R79 re-architects the v1 anti-theatrical structured-thought path into a layered
stack that lets the LLM be a person, the channel driver be the world, and the
hormone system be the body. The change is composed of 7 sub-requirements
(R79-A through R82), each of which is a small opt-in addition to an existing
owner package. There is no rewrite.

```
        v1 baseline (R70/R78)                          R79 stack
        ─────────────────────                          ─────────
16  prompt_contract   ─► FirstVersionEmbodied  ──────►  + AggressiveRadicalEmbodied
    (default)              PromptPath                    PromptPath (opt-in)
    ───────────────────────────────────────────────   ──────────────────────
22  composition        ─► assemble_runtime     ──────►  + AggressiveRadicalPromptProfile
    (default)              (v1)                          (opt-in capability bundle)
    ───────────────────────────────────────────────   ──────────────────────
25  llm_gateway        ─► OpenAICompatible      ──────►  + AggressiveRadicalRequestBuilder
    (default)              (v1)                          (opt-in)
    ───────────────────────────────────────────────   ──────────────────────
30  channel_driver     ─► ChannelDriver        ──────►  + ready_channels exposed
    (default)              (1 stub)                      (snapshot API)
    ───────────────────────────────────────────────   ──────────────────────
04  neuromodulation    ─► AppraisalDerived     ──────►  + 5-HT/Oxy/Opioid updaters
    (default)              (DA/NE/ACh/Cort only)        + HormonePredictCorroborator
    ───────────────────────────────────────────────   ──────────────────────
02  sensory_ingress    ─► external sources     ──────►  + internal_monologue
    (default)                                        (rumination source)
    ───────────────────────────────────────────────   ──────────────────────
03  appraisal          ─► external estimators  ──────►  + InternalMonologueEstimator
    (default)                                        (rumination salience)
    ───────────────────────────────────────────────   ──────────────────────
09  thought_gating     ─► v1 input             ──────►  + self_continuation_signal
    (default)                                        (rumination gate input)
    ───────────────────────────────────────────────   ──────────────────────
42  continuity         ─► v3 snapshot          ──────►  v4 snapshot
    (default)                                        (rumination carry)
    ───────────────────────────────────────────────   ──────────────────────
17  evaluation         ─► v1 dimensions        ──────►  + 17-dim BehaviorDriftDimension
    (default)                                        + AggressiveRadicalDriftEvaluator
    ───────────────────────────────────────────────   ──────────────────────
21  observability      (no change; reads new state)    (no change)
R21  ad-hoc-logging-guard  (no change; _io wrapper)    (no change)
```

The rollout sequence is R79-A → R79-B → R79-C → R79-D → R80 → R81 → R82, with
R79-A and R79-D delivered (this change set) and R79-B / R79-C / R80 / R81 / R82
tracked as future work in the same requirement package.

## 2. R79-A: aggressive-radical-no-theater prompt path (delivered)

### 2.1 The 6-layer `EmbodiedPromptContract`

`AggressiveRadicalEmbodiedPromptPath` builds a 6-layer contract in fixed order
(earlier layers are read first by the LLM, so order matters):

| # | Layer name         | Content                                                           | Source field                         |
|---|--------------------|-------------------------------------------------------------------|--------------------------------------|
| 1 | `present_field`    | Focused stimulus text (concatenation of `RawSignal.text` filtered to `focused` attention tier) | `EmbodiedPromptRequest.focused_stimuli` |
| 2 | `embodied_state`   | Body state text (hormone / feeling snapshot)                       | `request.hormone_snapshot` + `request.feeling_snapshot` |
| 3 | `attention_breakdown` | 3-tier per-stimulus attention breakdown (focused/peripheral/filtered) | `request.attention_field`            |
| 4 | `channel_catalog`  | Available + ready channel list (free-form text listing)           | `request.ready_channels` + `request.available_channels` |
| 5 | `response_schema`  | 11-field natural-language JSON schema description                  | static (in code)                     |
| 6 | `v3_system_prompt` | Full v3 system prompt with all placeholders filled                | static template (in code)            |

The order is the **only** contract: the existing `EmbodiedPromptEngine` reads
layers 1-4 in order to build the user message, layer 5 as the user message tail
(schema instructions), and layer 6 as the system message.

### 2.2 The 11-field natural-language JSON schema

The v3 schema uses natural-language field names (no cognitive-owner vocabulary):

| Field | Type | Meaning | Hard rule |
|---|---|---|---|
| `what_i_feel` | string (>= 4 chars) | What am I feeling in my body right now? | required |
| `what_i_think` | string (>= 4 chars) | What am I thinking about? | required |
| `i_want_to_say` | string or null | Do I want to say something? If so, what? | required iff `i_will_send_it=true` |
| `i_will_send_it` | bool | Will I say it (vs swallow it)? | required |
| `i_send_through` | string (channel name) or null | Which channel? | required iff `i_will_send_it=true`; must be in `ready_channels` |
| `i_want_to_act` | bool | Do I want to do something other than speak? | required |
| `act_type` | string or null | What kind of act? (one of `move`, `touch`, `remember`, `forget`, `nothing`) | required iff `i_want_to_act=true` |
| `remember_this` | string or null | Is there something I want to remember? | required iff `remember_because != null` |
| `remember_because` | string or null | Why? | optional |
| `i_want_to_think_more` | bool | Do I want to keep thinking about this? | required |
| `think_more_about` | string or null | What? | required iff `i_want_to_think_more=true` |

The schema is enforced both as **schema-layer instructions** (the LLM is told
"if X then Y must be present") and as **hard rules** in the contract builder
(cross-field invariants are verified after LLM output is parsed, so a
misbehaving LLM doesn't crash the runtime).

### 2.3 The v3 system prompt template

The v3 system prompt has 5 fixed sections in this order:

1. **Identity block**: "You are a person. Not an AI, not a role, not a
   runtime. You have a body, you have a name, you have a past. You are here
   because you are having a moment right now."
2. **The 3 attention tiers**: a 3-paragraph explanation of `focused /
   peripheral / filtered`, with the rule "I only act on what reaches me
   focused, but I'm aware the rest is there".
3. **The channel catalog intro**: "The channels I have are: {catalog}. Of
   these, I can actually use right now: {ready}. The rest are like hands I
   can't move."
4. **The 11-field schema instruction**: a 1-paragraph description of each
   field with examples.
5. **The 7 hard rules**: the cross-field invariants as bulleted "if-then"
   rules.

The system prompt never says "anti-theatrical" or "theater" as a rule. The
identity block absorbs the anti-theatrical directive into the lived
experience: "I am a person, so I don't have to perform being one."

### 2.4 Why this works

The 7-scenario v3 manual probe (2026-06-11) shows the v3 prompt:

- produces `what_i_feel` in first-person ("I feel warmth in my chest, like
  when someone I trust tells me something good") instead of v1's third-person
  ("the system has registered a moderate salience").
- produces `i_send_through` non-null in scenarios where channels are ready
  (4/7 scenarios have non-zero `i_send_through` in v3 vs 0/7 in v1).
- produces `i_want_to_think_more = true` in 5/7 scenarios vs 0/7 in v1.

These are not measurable in the 11 unit tests (the tests verify the contract
shape, not the LLM's prose quality); they are measurable in the R79-D
framework's `i_want_to_say_freq` / `i_send_through_freq` /
`i_want_to_think_more_freq` assertions, which are the
`BehaviorDriftDimension` 5-family.

## 3. R79-B: channel catalog runtime injection

### 3.1 The `AggressiveRadicalPromptProfile` capability bundle

`composition.profile.AggressiveRadicalPromptProfile` is a frozen dataclass with 2 fields:

```python
@dataclass(frozen=True)
class AggressiveRadicalPromptProfile:
    prompt_path_mode: Literal["aggressive-radical-v3"] = "aggressive-radical-v3"
    ready_channels: tuple[str, ...] = ()
```

It is consumed by `assemble_runtime` via the existing capability-bundle
mechanism (R50). The default is `prompt_path_mode="aggressive-radical-v3"`
and `ready_channels=()` (i.e., no channels are ready until the channel driver
subsystem is asked).

### 3.2 The `AggressiveRadicalChannelArbitrationPostProcessor` bridge

`composition.bridges.AggressiveRadicalChannelArbitrationPostProcessor` consumes the LLM
JSON envelope after it returns and dispatches to the correct `ChannelDriver`
if and only if the chosen channel is in the `ready_channels` snapshot.

The post-processor is owner-neutral glue: it imports `composition.contracts`
and `channel_driver.dispatcher` only; it does not import the LLM owner or the
prompt contract owner. This keeps the composition owner-boundary guard green.

### 3.3 The channel-state snapshot API

`channel_driver.dispatcher.ChannelSubsystem.channel_state_snapshot()` returns
a `frozenset[ChannelState]` where `ChannelState.channel_id` is the channel
name and `ChannelState.is_ready` is the boolean. The snapshot is computed
fresh on every prompt-contract build (no caching) so a channel that becomes
ready mid-session shows up in the next tick.

## 4. R79-C: 5-HT / Oxy / Opioid updater + LLM hormone predict signal

### 4.1 The 3 new updater entries

`neuromodulation.engine.AppraisalDerivedNeuromodulatorUpdatePath` gains 3 new
methods (kept as separate `def` so P5 can mutate them individually):

```python
def _serotonin_drive(self, appraisal: Salience, sensitivity: float) -> float:
    threat = max(appraisal.threat or 0.0, appraisal.uncertainty or 0.0)
    social = appraisal.social or 0.0
    return clamp(self.serotonin_baseline + sensitivity * (1.0 - threat) * social)

def _oxytocin_drive(self, appraisal: Salience, comfort: float, sensitivity: float) -> float:
    social = appraisal.social or 0.0
    return clamp(self.oxytocin_baseline + sensitivity * social * comfort)

def _opioid_drive(self, appraisal: Salience, feeling: InteroceptiveFeeling, sensitivity: float) -> float:
    pain = feeling.pain_like or 0.0
    threat = max(appraisal.threat or 0.0, appraisal.uncertainty or 0.0)
    return clamp(self.opioid_baseline + sensitivity * (1.0 - pain) * (1.0 - threat))
```

All 3 sensitivities sit under a new learned-parameter category
`neuromodulator_serotonin_oxytocin_opioid` (5-HT and Oxy and Opioid share a
category because their dynamics are tightly coupled: 5-HT modulates the
threshold at which Oxy is released; Opioid reinforces the experience of
comfort that Oxy enabled).

### 4.2 The LLM `hormone_response_i_predict` signal

The LLM JSON schema gains an optional 12th field `hormone_response_i_predict`
which is a 9-key dict (DA / NE / 5-HT / ACh / Cort / Oxy / Opioid / Excitation
/ Inhibition) each in `[-1, +1]`. The LLM's prediction is **not** a drive
override; it is a corroboration signal.

`HormonePredictCorroborator` reads both the LLM's prediction and the
formula-derived drive and produces a per-channel verdict:

- `corroborate`: `sign(predict) == sign(drive) and abs(predict - drive) < 0.3`
- `conflict`: `sign(predict) != sign(drive) and abs(predict) > 0.2 and abs(drive) > 0.2`
- `silent`: anything else

The verdict is added to the next tick's drive as a bounded bonus
`+bonus * predict` (corroborate) or `+penalty * predict` (conflict) or `0`
(silent). `bonus` and `penalty` are first-version constants
(`bonus=0.05, penalty=0.05`) under a new learned-parameter category
`hormone_predict_coupling`.

### 4.3 Why "LLM signal as addition, not override"

The fail-fast principle (R70 §3.1.8) requires that the formula's drive is
authoritative; the LLM signal is corroborative. This prevents the LLM from
hallucinating extreme drives ("I'm so angry I want to kill the user") and
overriding the formula. The LLM has a say, but not a veto.

## 5. R79-D: extendable baseline framework (delivered)

### 5.1 The 4-package structure

```
src/helios_v2/tests/r79d/
├── __init__.py
├── framework.py       (Scenario, ExperimentConfig, run_experiment)
├── assertions.py      (9 built-in assertions + @register_assertion)
├── cli.py             (list / run / report / diff / assertions subcommands)
├── _io.py             (write_line wrapper for sys.stdout.write)
├── scenarios/
│   ├── A_praise.json
│   ├── B_neglect.json
│   ├── C_bipolar.json
│   └── D_repeat_stimulus.json
└── reports/
    └── generator.py   (aggregate + diff report generators)
```

### 5.2 The 9 built-in assertions

| Name | Verifies |
|---|---|
| `hormone_drift_in_range` | A given hormone's max-min drift over N ticks is in `[lo, hi]` |
| `hormone_series_not_constant` | A given hormone's stddev > epsilon |
| `llm_field_count_nonzero` | A given LLM JSON field is non-zero in >= k% of ticks |
| `llm_field_count_zero` | A given LLM JSON field is zero in >= k% of ticks |
| `sign_of_delta_differs` | A_praise minus B_neglect's hormone delta has the expected sign |
| `magnitude_of_delta_at_least` | A_praise minus B_neglect's hormone delta has magnitude >= threshold |
| `alpha_tonic_plateau` | A repeated stimulus's hormone series plateau in last 5 ticks (stddev < epsilon) |
| `i_want_to_say_freq_at_least` | A scenario's `i_want_to_say` non-null rate >= threshold |
| `valence_arousal_correlate` | A scenario's `valence` series correlates with `i_want_to_think_more` rate |

The `@register_assertion("name")` decorator lets new assertions be added
without modifying the framework.

### 5.3 Why a sub-package under `tests/` and not `helios_v2/`

R21 forbids the framework from being a product dependency, and the R21
ad-hoc logging guard covers `src/helios_v2/` recursively. Putting the
framework under `tests/` puts it inside the guard but makes it explicitly
a test infrastructure (the v1 unit tests are also under `tests/`). It is
**invocable as a CLI** (`python -m helios_v2.tests.r79d ...`) for ad-hoc
validation, not just for pytest.

## 6. R80: internal_monologue source owner

### 6.1 The new source under `02` sensory_ingress

`helios_v2.sensory.internal_monologue.InternalMonologueSource` implements the
existing `SensorySource` Protocol. It is registered via the same
`handle.ingress.register_source(src)` mechanism used by other R70+ sources.

The source's `poll()` method reads the runtime's
`RuntimeHandle._carry_internal_monologue` field (set by R81) and emits a
`RawSignal(signal_type="internal_monologue", text=...)` per LLM envelope.

### 6.2 Why under `02` and not a new top-level

The `02` sensory ingress package is the canonical owner of
`RawSignal.signal_type` discriminators. Adding a new top-level package would
duplicate the normalization logic. R79's contract is **"new signal_type lives
under `02`"**, and the rest of the chain learns it organically.

## 7. R81: multi-tick feedback carry

### 7.1 The `_carry_internal_monologue` field

`RuntimeHandle._carry_internal_monologue` is a versioned `dict` field added
to the existing `_carry_recall_directive` seam (R49). The field is set
post-tick from the LLM's `what_i_think` + `i_want_to_think_more` + etc.
envelope; it is read pre-tick by the `internal_monologue` source owner (R80).

The field is a soft carry, not a hard carry: if the runtime restarts, the
field is restored from the `42` continuity checkpoint v4 snapshot.

### 7.2 The `42` continuity checkpoint v4

`RuntimeContinuitySnapshot` gains a `version: Literal[3, 4]` discriminator.
v3 is the existing R49 snapshot; v4 adds `internal_monologue: dict | None`.
A v3 snapshot can be restored as v4 with `internal_monologue=None`; a v4
snapshot cannot be restored as v3 (fail-fast, R70 §3.1.8).

## 8. R82: 17-dim behavior drift evaluation

### 8.1 The 17 dimensions

| Family | Dimensions | Source |
|---|---|---|
| hormone | DA / NE / 5-HT / Cort | `NeuromodulatorLevels.levels.{da,ne,5ht,cort}` |
| feeling | valence / arousal / tension / comfort | `InteroceptiveFeelingVector.{valence,arousal,tension,comfort}` |
| cognition | novelty / uncertainty / social / aggregate | `Salience.{novelty,uncertainty,social,aggregate}` |
| behavior | i_want_to_say_freq / i_send_through_freq / i_want_to_think_more_freq / remember_this_freq / act_type_distribution | LLM JSON output aggregated per scenario |

The 4-cognition + 5-behavior = 9 dimensions of the P5 launch gate; the 8
hormone/feeling dimensions are the "inner state drift" the LLM signal is
supposed to influence.

### 8.2 Why a separate evaluator and not just `17` evaluation extending

The 17-dim drift evaluator is specific to the R79 prompt path; v1's
structured JSON (`sufficiency` / `continuation` / etc.) doesn't have an
`i_want_to_think_more` field to count. Keeping the v3 evaluator separate
preserves the v1 evaluator's signature.

## 9. Owner boundaries and the composition guard

| R79 piece | Owner | Cross-owner import? |
|---|---|---|
| R79-A prompt path | `16` prompt_contract | no (only the existing Protocol) |
| R79-B prompt profile | `22` composition | no (owner's own bundle) |
| R79-B channel arbitration bridge | `22` composition | yes, imports `channel_driver` only |
| R79-B LLM request builder | `25` llm_gateway | no (owner's own builder) |
| R79-C hormone updaters | `04` neuromodulation | no (owner's own paths) |
| R79-C hormone predict corroborator | `04` neuromodulation | no (consumes LLM JSON, but does not import LLM owner) |
| R79-D framework | `tests/r79d` | yes, but tests are allowed cross-owner imports |
| R80 internal_monologue source | `02` sensory_ingress | no (owner's own source) |
| R80 internal_monologue estimator | `03` appraisal | no (owner's own estimator) |
| R81 carry extension | `42` continuity + `09` thought_gating | no (owner's own extension) |
| R82 drift evaluator | `17` evaluation | no (consumes R79-D JSONL output, but does not import R79-D module) |

The composition owner-boundary guard test
(`test_composition_owner_boundary_guard.py`) is extended in R79-C to also
forbid `<salience>_to_<channel>` sensitivity strategies in composition glue
(those belong in `04`).

## 10. Backwards compatibility

| Change | Backwards-compat strategy |
|---|---|
| R79-A new prompt path | v1 path is untouched; new path is opt-in via `prompt_path_mode` |
| R79-B ready_channels API | `channel_state_snapshot()` is additive; v1 doesn't read it |
| R79-C 3 new updaters | v1's `AppraisalDerivedNeuromodulatorUpdatePath` is untouched; new updaters are additive |
| R79-C LLM predict signal | v3 schema's 12th field is optional; v1 LLM output (no `hormone_response_i_predict`) parses as `silent` |
| R79-D framework | lives under `tests/`, not a product dependency |
| R80 internal_monologue source | opt-in via the R79 prompt path switch |
| R81 carry extension | `_carry_internal_monologue` is a new field; v3 snapshot is unchanged |
| R82 drift evaluator | new module; v1 evaluation owner is unchanged |

## 11. Migration and rollback

- **Rollout**: `AggressiveRadicalPromptProfile(prompt_path_mode="aggressive-radical-v3")`
  in the runtime profile. No code change required.
- **Rollback**: flip the flag back to `v1_first_version`. The v3 path is never
  invoked. v1 contract is byte-for-byte unchanged.
- **Migration safety**: R79-A and R79-D are delivered together; the rest is
  sequential opt-in. Each sub-requirement is independent.

## 12. Open questions

1. **Should the LLM predict field be required or optional?** Currently
   optional (LLM can omit it; the corroborator returns `silent` for missing
   fields). Required forces the LLM to engage with its body; optional is
   easier on small-context LLMs. Decision deferred to R79-C
   implementation.
2. **Should rumination be enabled by default under R79, or opt-in?** Currently
   opt-in via the same `prompt_path_mode` flag. Default-off is the
   fail-safe position; rumination can amplify negative stimuli and needs
   a separate evaluation.
3. **Should R82's drift evaluator be a blocking gate (P5 cannot start
   without it) or a soft signal?** Decision deferred to R82.
