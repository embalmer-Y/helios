# Requirement 79 - R79 Aggressive-Radical Prompt and Runtime Self-Talk

## 1. Background and Problem

R70 (`70-prompt-to-thought-real-state-bridge`) shipped semantic bridges
(`SemanticEmbodiedPromptRequestBridge` / `SemanticInternalThoughtRequestBridge`) that
project real `04` `NeuromodulatorLevels` and `05` `InteroceptiveFeelingVector` from the
tick frame into the LLM user-message context, plus R27's structured json_object envelope
parsing in `11` (sufficiency / continuation / action / self-revision). R70 + R27 are the
v1 baseline of the embodied prompt + structured-thought path.

End-to-end capture (2026-06-10, fixed in R78) and 7-scenario manual prompt tests (2026-06-11)
show three persistent limitations that block P5 learning-loop readiness:

1. **Anti-theatrical framing is a top-down rule**, not a lived experience. R70's
   `anti_theatrical_constraints` layer says "Do not perform empty self-consciousness
   theater. Use first-person phrasing only when grounded..." — the LLM is told it must
   not perform; the prompt teaches the model to police itself. The LLM still talks about
   itself in the third person or as "the runtime" because the prompt never tells it what
   it is.
2. **JSON field names leak the framework**. v1 uses `sufficiency` / `continuation` /
   `action_proposal` / `self_revision_proposal`. These are cognitive-owner vocabulary
   the LLM has no business knowing; the LLM reverse-engineers the schema and starts
   performing for it ("I should signal self-revision here").
3. **The LLM is told it is not a person**. v1 is silent on the LLM's identity; the
   absence of "you are a person" in the prompt lets the LLM default to "I am a
   runtime module" framing in its JSON field commentary.

The 7-scenario v1 manual tests (S01-S07, 2026-06-11) show all 7 scenarios PASS the
`llm_field_count_zero` assertion (LLM never picks a channel), but the free-form
`what_i_feel` / `what_i_think` fields are written in clinical third-person: "the
system has registered a moderate salience in the novelty dimension", "feeling at
baseline, no computed feeling state", "I am a runtime executing the
internal-thought-loop owner's first-version path".

A 10-tick multi-tick probe (2026-06-11) and a 3-baseline comparison (A=praise, B=neglect,
C=bipolar, 32 ticks, 2026-06-11) further show three algorithmic gaps that block the
stimulus -> hormone -> feeling -> LLM feedback loop:

4. **A vs B DA delta is symmetric** (A: +0.064, B: +0.063) because the v1
   `AppraisalDerivedNeuromodulatorUpdatePath` maps both praise and neglect to
   `social=1.0, reward=0`, so the dopamine drive is identical.
5. **5-HT / Oxy / Opioid stay at constant 0.30** in every tick because the v1 update
   path has no entry for these three channels; they regress to tonic baseline
   permanently.
6. **LLM `i_want_to_say` and `i_send_through` are 0 in all 3 baselines** because the
   channel catalog is not in the prompt at all, and the LLM has no way to know which
   channels exist; it defaults to "internal-only monolog".

P5 learning-loop readiness (`P5` self-training first step) requires: (a) the LLM
output to be a faithful first-person report (so a learning signal can read it as
ground truth), (b) the hormone system to be expressive enough that feedback
modifies it (so a learning signal has a gradient to push), (c) the LLM to be able
to act on its decisions (so learned behavior propagates back into the world).

## 2. Goal

Replace the v1 anti-theatrical structured-thought prompt path with a v3
aggressive-radical-no-theater prompt path that:

1. Tells the LLM it IS a person (not an AI, runtime, role, or person-who-thinks-they-are-a-runtime).
2. Asks for free-form first-person inner experience, with JSON field names that
   reflect how a person naturally frames their own inner experience.
3. Injects the channel catalog (available + ready) and the attention field
   (focused / peripheral / filtered) into the prompt at runtime.
4. Adds the missing `5-HT / Oxy / Opioid` updater paths to the neuromodulator
   owner and a mechanism for the LLM to influence hormone levels (LLM
   `hormone_response_i_predict` subjective prediction, compared to the
   `04` formula in a corroborate / conflict loop).
5. Adds a new internal-monologue `internal_monologue` source owner that lets
   the system feed its own previous-tick LLM output back as a new stimulus
   (rumination / self-talk / 反刍), closing the feedback loop.
6. Adds an evaluation framework (`17` evaluation owner) that quantifies 17
   behavior-drift metrics, to measure P5 learning progress.

The v1 path remains as a baseline (`FirstVersionEmbodiedPromptPath`); R79 adds a
sibling v3 path (`R79AggressiveEmbodiedPromptPath`) and never modifies v1 in place.
The change is backwards-compatible: default assembly still uses v1 unless the
runtime profile opts in to `prompt_path_mode="r79_aggressive_radical_v3"`.

## 3. Functional Requirements

### 3.1 R79-A: aggressive-radical-no-theater embodied prompt path (delivered)

1. The `16` `prompt_contract` owner gains a new owner module
   `R79AggressiveEmbodiedPromptPath` (sibling to `FirstVersionEmbodiedPromptPath`).
2. The new path implements the existing `EmbodiedPromptPath` Protocol and is
   wired into the existing `EmbodiedPromptEngine` via composition opt-in.
3. The new path emits a 6-layer `EmbodiedPromptContract`:
   - `present_field` — focused stimulus text
   - `embodied_state` — body state text (hormone / feeling snapshot)
   - `attention_breakdown` — focused / peripheral / filtered 3-tier breakdown
   - `channel_catalog` — available + ready channel list
   - `response_schema` — 11-field natural-language JSON instructions
   - `v3_system_prompt` — full v3 system prompt with all placeholders filled
4. The v3 system prompt's identity block MUST say "You are a person. Not an AI, not
   a role, not a runtime." and MUST NOT mention "anti-theatrical" or "theater"
   phrased as a rule.
5. The v3 JSON schema MUST use natural-language field names:
   `what_i_feel`, `what_i_think`, `i_want_to_say`, `i_will_send_it`, `i_send_through`,
   `i_want_to_act`, `act_type`, `remember_this`, `remember_because`,
   `i_want_to_think_more`, `think_more_about`. The v1 names (`sufficiency` etc.) are
   forbidden in v3 output.
6. The v3 schema MUST enforce hard cross-field invariants as schema-layer
   instructions: `i_will_send_it => i_want_to_say != null`,
   `i_send_through => i_will_send_it && i_send_through in ready_channels`,
   `remember_because => remember_this`, `think_more_about => i_want_to_think_more`.
7. The new path requires `EmbodiedPromptConfig.prompt_bootstrap_id ==
   "R79-aggressive-radical-v3"`; a different bootstrap id is a hard-stop
   `PromptContractError`.
8. The action boundary MUST distinguish `thought` vs `outward_expression` consumers
   (mirroring v1 boundary rules).
9. No cognitive-owner code is modified; the v3 path lives entirely under
   `helios_v2.prompt_contract.r79`.

### 3.2 R79-B: channel catalog runtime injection + LLM channel arbitration

1. The `22` composition root owner gains an opt-in capability bundle
   `R79PromptProfile(prompt_path_mode="r79_aggressive_radical_v3", ready_channels=...)`.
2. The `25` LLM gateway owner adds the `R79AggressiveEmbodiedPromptPath` as a
   registered `LlmRequest` builder when the profile is active.
3. The `30` channel driver subsystem exposes its per-driver `ChannelStateSnapshot`
   to the prompt-contract builder, so `ready_channels` is computed from real
   per-driver availability (replacing the v1 hardcoded shim).
4. A new post-processor (`R79ChannelArbitrationPostProcessor`) interprets the
   LLM JSON's `i_will_send_it` + `i_send_through` + `act_type` triple and
   dispatches to the appropriate `ChannelDriver` if and only if the chosen
   channel is in the `ready_channels` set. LLM output that names a non-ready
   channel is treated as "internal-only", same as if `i_will_send_it` were
   false.
5. The post-processor is owner-neutral glue under `helios_v2.composition`;
   it does not import the LLM owner or the channel driver owner.
6. The composition owner-boundary guard test
   (`test_composition_owner_boundary_guard.py`) must remain green.

### 3.3 R79-C: 5-HT / Oxy / Opioid updater + LLM hormone predict signal

1. The `04` neuromodulator owner gains three new entry functions in
   `AppraisalDerivedNeuromodulatorUpdatePath`:
   - `serotonin = clamp(baseline + sensitivity * (1 - max(threat)) * social)`
   - `oxytocin = clamp(baseline + sensitivity * social * comfort_signal)`
   - `opioid_tone = clamp(baseline + sensitivity * (1 - pain_like) * (1 - threat))`
2. The sensitivity coefficients sit under the existing learned-parameter
   categories and are P5-learnable later.
3. The LLM JSON schema gains an optional 12th field
   `hormone_response_i_predict` — the LLM's subjective prediction of how the
   current stimulus should move the body. Format: a 9-key dict mirroring the
   `NeuromodulatorLevels` schema, each value in `[-1, +1]` representing
   "should rise / should fall" intent.
4. A new `HormonePredictCorroborator` (in `04`) reads the LLM's
   `hormone_response_i_predict` and computes per-channel `corroborate` /
   `conflict` / `silent` verdicts against the formula-derived drive.
5. A corroborate verdict adds a small bounded bonus `+bonus * predict` to the
   next tick's drive; a conflict verdict adds a small bounded penalty
   `-penalty * predict`; a silent verdict adds zero. Bonus / penalty are
   first-version constants under a new learned-parameter category
   `hormone_predict_coupling`.
6. The 3 new hormone channels' tonic baseline and dual-timescale alpha remain
   in the existing `DualTimescaleNeuromodulatorUpdatePath` (no new dynamics).
7. The R79-D baseline framework must now show `5-HT / Oxy / Opioid` series
   non-constant under the A_praise / B_neglect scenarios.

### 3.4 R79-D: extendable baseline framework (delivered)

1. New `helios_v2.tests.r79d` package: `framework.py` (Scenario dataclass,
   `ExperimentConfig`, `run_experiment`), `assertions.py` (9 built-in
   assertion functions + `@register_assertion("name")` decorator), `cli.py`
   (`list / run / report / diff / assertions` subcommands), `scenarios/`
   (4 v1 baseline scenarios), `reports/` (aggregate + diff report generators).
2. All CLI output routed through a `_io` helper that wraps `sys.stdout.write`
   to comply with the R21 ad-hoc logging guard.
3. The framework runs each scenario for N ticks (default 10) against either
   a real LLM (`.env` loaded) or a `NoopLlmGateway`, captures every
   per-tick state (hormones / feelings / salience / LLM JSON output / delta),
   and evaluates the scenario's assertion list.
4. The 4 v1 scenarios cover: A=continuous praise, B=continuous neglect,
   C=alternating praise/criticism (bipolar), D=repeated same stimulus
   (20 ticks, verifies alpha_tonic plateau).
5. Each scenario ships as a JSON file with `id / description /
   stimulus_script / assertions / repeat`. A new scenario is "drop a JSON
   in scenarios/"; a new assertion is `@register_assertion("name")` in any
   module imported before `run`.
6. The R79-D framework is the standard baseline harness for R79-A/B/C
   validation and the eventual P5 learning-curve assessment.

### 3.5 R80: internal_monologue source owner (anti-rumination carry)

1. New sensory source owner `helios_v2.sensory.internal_monologue` (under
   the existing `02` sensory ingress package, not a new top-level package).
2. The source feeds the previous tick's LLM JSON output
   (`what_i_think` + `i_want_to_think_more` + `think_more_about`) back into
   the next tick's stimulus batch as a synthetic `RawSignal` with
   `signal_type="internal_monologue"`.
3. The 02 sensory normalization preserves the `internal_monologue` signal
   type as a first-class `Stimulus.signal_type` discriminator (no special
   casing in `02`; the owner stays purely normalizational).
4. The 03 appraisal owner gains an owner-defined
   `InternalMonologueAppraisalEstimator` that maps `internal_monologue`
   stimuli to a `novelty = 0.3 / uncertainty = 0.7 / social = 0.0` salience
   profile (low novelty because it's self-referential, high uncertainty
   because it's the system's own thought). This estimator is opt-in under
   the same R79 prompt-path switch.
5. The 04 / 05 / 06 / 09 / 11 chain receives the `internal_monologue`
   signal normally, so the LLM's own previous-tick output is a real driver
   of the next tick's hormone / feeling / memory / gate / thought chain.

### 3.6 R81: multi-tick feedback carry enhancements

1. The `RuntimeHandle._carry_recall_directive` seam (R49) extends to also
   carry the previous tick's LLM JSON envelope verbatim
   (`what_i_think` + `i_want_to_say` + `i_send_through` + etc.) as a
   `_carry_internal_monologue` field.
2. The `09` thought gating owner reads
   `_carry_internal_monologue` as a new optional gate input
   `self_continuation_signal` — a `0..1` value derived from
   `i_want_to_think_more` boolean + `think_more_about` non-empty boolean.
3. The `18` autonomy owner's deferred-continuity records gain a new
   `source_kind="internal_monologue"` variant for rumination continuity
   (vs `source_kind="external_stimulus"` and `source_kind="retrieval"`).
4. The `42` continuity checkpoint gains a versioned
   `_carry_internal_monologue` field in the snapshot, so cross-restart
   continuation includes the last LLM envelope.

### 3.7 R82: 17-behavior-drift evaluation harness

1. The `17` evaluation owner gains a new `BehaviorDriftDimension` enum
   covering 17 dimensions across 4 families: hormone (4: DA / NE / 5-HT /
   Cort), feeling (4: valence / arousal / tension / comfort), cognition
   (4: novelty / uncertainty / social / aggregate), behavior (5:
   i_want_to_say_freq / i_send_through_freq / i_want_to_think_more_freq /
   remember_this_freq / act_type_distribution).
2. The `R79DriftEvaluator` (under `17` evaluation) consumes the
   `R79-D` framework's per-scenario JSONL output and computes per-tick
   drift for each dimension.
3. The P5 launch gate requires the drift evaluator to be wired before
   any P5 learning loop can mutate the `04` sensitivity coefficients.

## 4. Non-Functional Requirements

1. **Performance**: R79-A path adds at most 1 extra `str.format` call per
   tick (the v3 system prompt stitch). No new I/O. No new owner import.
2. **Reliability**: R79-A's fail-fast on wrong `prompt_bootstrap_id`
   guarantees that a config drift is caught at contract-build time, never
   at LLM-call time. R79-B's channel arbitration fail-fast guarantees that
   a `i_send_through` to a non-ready channel is an internal-only tick
   (no external dispatch), not a silent drop.
3. **Observability**: R79 does not add new observability mechanisms; the
   existing `21` observability owner + per-tick timeline capture the new
   paths unchanged.
4. **Compatibility**: Default assembly and the v1 path remain byte-for-byte
   unchanged when `prompt_path_mode` is not `r79_aggressive_radical_v3`.
   R78 (real-state bridge) remains unchanged. R26 (LLM-backed default
   cognition) remains unchanged.
5. **Migration safety**: R79 is opt-in; rollout is one profile flag flip.
   No rollback required; flipping the flag back to `v1_first_version` is
   the rollback.

## 5. Code Behavior Constraints

1. No v1 code is modified. R79 adds sibling paths / new owners; v1
   `FirstVersionEmbodiedPromptPath` / `FirstVersionNeuromodulatorUpdatePath` /
   v1 sensory source remain untouched.
2. The composition owner-boundary guard test
   (`test_composition_owner_boundary_guard.py`) must remain green: R79
   additions either live in owner packages (preferred) or are
   owner-neutral bridge glue in composition.
3. The R21 ad-hoc logging guard test
   (`test_no_adhoc_logging_guard.py`) must remain green: R79 framework
   CLI output routes through a `_io` helper, not `print`.
4. The composition owner-boundary guard must be extended to also forbid
   `<salience>_to_<channel>` sensitivity strategies in composition
   glue (a guard extension in R79-C).
5. No new logging mechanism; no new observability owner code.

## 6. Impacted Modules

### R79-A (delivered)

- `helios_v2/src/helios_v2/prompt_contract/r79.py` — new
  `R79AggressiveEmbodiedPromptPath` + 6-layer v3 contract builder.
- `helios_v2/src/helios_v2/prompt_contract/__init__.py` — export additions.
- `helios_v2/tests/test_r79a_prompt_contract.py` — 11 unit tests.

### R79-B (next)

- `helios_v2/src/helios_v2/composition/profile.py` — `R79PromptProfile`
  capability bundle.
- `helios_v2/src/helios_v2/composition/bridges.py` — new
  `R79ChannelArbitrationPostProcessor` bridge.
- `helios_v2/tests/test_r79b_channel_arbitration.py` — arbitration tests.

### R79-C (next)

- `helios_v2/src/helios_v2/neuromodulation/engine.py` — add 5-HT / Oxy /
  Opioid entries to `AppraisalDerivedNeuromodulatorUpdatePath` + new
  `HormonePredictCorroborator`.
- `helios_v2/src/helios_v2/neuromodulation/contracts.py` — extend
  `NeuromodulatorLevels` learned-parameter categories with
  `hormone_predict_coupling`.
- `helios_v2/tests/test_r79c_hormone_coverage.py` — coverage tests.

### R79-D (delivered)

- `helios_v2/src/helios_v2/tests/r79d/` — full framework package
  (`framework.py`, `assertions.py`, `cli.py`, `scenarios/`, `reports/`).
- `helios_v2/logs/prompt_probe_scenarios/r79d/baseline/` — v1 baseline
  output (4 scenarios, 52 ticks, 28 assertions).

### R80 (next)

- `helios_v2/src/helios_v2/sensory/internal_monologue.py` — new source.
- `helios_v2/src/helios_v2/appraisal/r79_internal_monologue.py` — new
  dimension estimator.
- `helios_v2/tests/test_r80_internal_monologue.py` — feedback-loop tests.

### R81 (next)

- `helios_v2/src/helios_v2/runtime/kernel.py` — extend
  `_carry_recall_directive` with `_carry_internal_monologue`.
- `helios_v2/src/helios_v2/thought_gating/engine.py` — add
  `self_continuation_signal` input.
- `helios_v2/src/helios_v2/continuity_checkpoint/contracts.py` — extend
  `RuntimeContinuitySnapshot` to v4 with `internal_monologue` field.

### R82 (next)

- `helios_v2/src/helios_v2/evaluation/r79_drift.py` — new
  `BehaviorDriftDimension` + `R79DriftEvaluator`.
- `helios_v2/tests/test_r82_drift_evaluator.py` — 17-dim tests.

### Documentation sync (R79-A baseline, this change set)

- `helios_v2/docs/requirements/index.md` — add R79 row, maturity
  `baseline_implementation` (R79-A path + R79-D framework delivered;
  R79-B / R79-C / R80 / R81 / R82 still pure_skeleton / not_started).
- `helios_v2/docs/PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md` — sync
  line naming R79-A.
- `helios_v2/docs/OWNER_GUIDE.en.md` / `OWNER_GUIDE.zh-CN.md` — top
  "Last synced" line, and §2.11 (`16` prompt contract) update with v3
  path entry.
- `helios_v2/docs/ARCHITECTURE_BOUNDARIES.md` — §8 migration-state
  recording: append R79 entry.

## 7. Acceptance Criteria

### 7.1 R79-A acceptance (delivered)

1. `R79AggressiveEmbodiedPromptPath.build()` returns a 6-layer
   `EmbodiedPromptContract` for any valid
   `EmbodiedPromptRequest + EmbodiedPromptConfig(prompt_bootstrap_id=
   "R79-aggressive-radical-v3")`.
2. The v3 system prompt layer contains: "You are a person", "Not an AI",
   "focused / peripheral / filtered" (3 attention tiers), the 11 natural
   field names, and the 7 hard-rule cross-field invariants.
3. `prompt_bootstrap_id != "R79-aggressive-radical-v3"` raises
   `PromptContractError`.
4. `i_send_through` in the response schema is bounded to the
   `ready_channels` set, not the `available_channels` set.
5. Action boundary switches correctly between `thought` and
   `outward_expression` consumers.
6. 11 unit tests pass; full suite `842 passed` (831 baseline + 11 R79-A);
   R21 ad-hoc logging guard green; composition owner-boundary guard green.

### 7.2 R79-B acceptance (pending)

1. `assemble_runtime(profile=R79PromptProfile(
   prompt_path_mode="r79_aggressive_radical_v3"))` builds a runtime with
   the v3 path wired and `ready_channels` sourced from real
   `ChannelSubsystem.channel_state_snapshot()`.
2. LLM output naming a non-ready channel results in an internal-only tick
   (no dispatch, `no_actionable_proposal` published by `13`).
3. LLM output naming a ready channel and `i_will_send_it=true` results in
   a dispatch to the correct driver.
4. Composition owner-boundary guard green (no LLM / channel driver
   imports in the new bridge).

### 7.3 R79-C acceptance (pending)

1. `5-HT / Oxy / Opioid` series non-constant under A_praise and B_neglect
   scenarios in the R79-D framework.
2. A vs B `Oxy` delta differ in sign (A > B) and magnitude (>= 0.02).
3. `HormonePredictCorroborator` adds bounded `corroborate` bonus when the
   LLM `hormone_response_i_predict` matches the formula-derived drive sign
   and magnitude within tolerance; bounded `conflict` penalty when it
   doesn't.
4. R79-D baseline under R79-C shows A vs B distinguishable on
   `i_want_to_think_more_freq` (LLM reflection rate).

### 7.4 R79-D acceptance (delivered)

1. CLI: `python -m helios_v2.tests.r79d list` lists 4 scenarios.
2. CLI: `python -m helios_v2.tests.r79d run --all` runs 52 ticks (10+10
   +12+20) against the real LLM via `.env`.
3. CLI: `python -m helios_v2.tests.r79d assertions` lists 9 built-in
   assertions + the `@register_assertion` registration seam.
4. CLI: `python -m helios_v2.tests.r79d report --output <dir>` produces
   an aggregate.md; `diff --baseline <a> --current <b>` produces a
   diff.md.
5. R21 ad-hoc logging guard green (no `print(` in the framework).
6. R79-D baseline run completes in <5 minutes with `.env` real LLM; 28
   assertions evaluated; 16 PASS / 12 FAIL (FAILs document the gaps that
   R79-B / R79-C must close).

### 7.5 R80 acceptance (pending)

1. `internal_monologue` source owner registers as a
   `SensorySource` and feeds a `RawSignal(signal_type="internal_monologue")`
   per tick when the previous tick's LLM emitted `i_want_to_think_more`.
2. `02` sensory normalization preserves `signal_type` as
   `Stimulus.signal_type` (no special casing).
3. `03` appraisal under the R79 profile maps `internal_monologue`
   stimuli to `novelty=0.3, uncertainty=0.7, social=0.0`.
4. A 20-tick A_praise scenario with rumination enabled shows
   `i_want_to_think_more_freq > 0.3` and `5-HT / Cort` series with
   cumulative drift `>= 0.10` (rumination amplifies the inner-state
   feedback loop).

### 7.6 R81 acceptance (pending)

1. `_carry_internal_monologue` is preserved across ticks; cross-restart
   via `42` checkpoint v4 retains the last LLM envelope.
2. `self_continuation_signal` in `09` gate signal correlates with
   `i_want_to_think_more_freq` in the R79-D framework.

### 7.7 R82 acceptance (pending)

1. `R79DriftEvaluator` produces 17-dim drift verdicts for the R79-D
   baseline output.
2. The P5 launch gate uses the drift evaluator; no P5 learning loop can
   mutate `04` sensitivities until the drift evaluator is green.
