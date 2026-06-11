# Task 79 - R79 Aggressive-Radical Prompt and Runtime Self-Talk

## Status legend

- `[ ]` pending
- `[~]` in progress
- `[x]` done
- `[!]` blocked (see note)

## Overview

R79 is decomposed into 7 sub-tasks (R79-A through R82) plus 1 documentation
sync sub-task. R79-A and R79-D are delivered (this change set); R79-B / R79-C
/ R80 / R81 / R82 are tracked here for future work in the same requirement
package.

## Sub-task T1: R79 requirements package (this change set)

- [x] Create `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/`
- [x] Write `requirement.md` (22927 bytes) — background, 7 sub-requirements,
      NFR, impacted modules, acceptance criteria
- [x] Write `design.md` (20518 bytes) — architecture, 6-layer contract,
      11-field schema, 9 assertions, owner boundaries, rollback
- [x] Write `task.md` (this file) — 7 sub-tasks + 1 doc-sync sub-task

## Sub-task T2: R79-A — aggressive-radical-no-theater prompt path

- [x] ~~Create `src/helios_v2/prompt_contract/r79.py`~~ — REMOVED in rename; v3 path is now `AggressiveRadicalEmbodiedPromptPath` inside `src/helios_v2/prompt_contract/engine.py` (follows the owner convention of "all paths live in engine.py")
- [x] Implement `AggressiveRadicalEmbodiedPromptPath` with 6-layer contract builder
- [x] Implement 11-field natural-language JSON schema
- [x] Implement 7 hard-rule cross-field invariants
- [x] Fail-fast on `prompt_bootstrap_id != "embodied-prompt-bootstrap:v3-aggressive-radical"`
- [x] Wire export in `prompt_contract/__init__.py`
- [x] Write `tests/test_aggressive_radical_prompt_path.py` with 11 unit tests
- [x] Run full suite, confirm 842 passed (831 baseline + 11 R79-A)
- [x] Confirm R21 ad-hoc logging guard green
- [x] Confirm composition owner-boundary guard green
- [x] Commit `5fcc80a` "R79-A: AggressiveRadicalEmbodiedPromptPath + 11 unit tests (842 passed)"

## Sub-task T3: R79-B — channel catalog runtime injection + LLM channel arbitration

- [x] Create `src/helios_v2/composition/profile.py` with `AggressiveRadicalPromptProfile`
      capability bundle (frozen dataclass, fail-fast `__post_init__`)
- [x] Wire `RuntimeProfile.aggressive_radical_prompt_profile` field +
      `assemble_runtime` integration (bootstrap id switch + path selection)
- [x] Add `ready_channels: tuple[str, ...] = ()` class field to
      `FirstVersionEmbodiedPromptRequestBridge` and `SemanticEmbodiedPromptRequestBridge`
      with `_resolved_channels` projection
- [x] Add `AggressiveRadicalChannelArbitrationPostProcessor` to
      `src/helios_v2/composition/bridges.py` (owner-neutral glue; parses
      v3 LLM JSON envelope; dispatches `OutboundPacket` via
      `ChannelSubsystem.dispatch_outbound`)
- [x] Add `AggressiveRadicalChannelArbitrationOutcome` (frozen dataclass,
      5 fixed-string fail-soft reasons)
- [x] Write `tests/test_aggressive_radical_channel_arbitration.py` with
      11 cases (13 test instances with parametrize) covering: ready
      channel / non-ready / not_sending / parse_error / multi-channel
      round-trip / empty_text / no_subsystem / null i_send_through /
      code-fence JSON tolerance / outcome construction validation
- [x] Write `tests/test_r79b_runtime_integration.py` with 6 cases
      covering: v1 default unchanged / v3 bundle wires v3 path + ready_channels /
      non-v1 baseline raises CompositionError / multi-channel round-trip /
      `RuntimeProfile()` field default is None / bundle round-trips profile field
- [x] Confirm `assemble_runtime(aggressive_radical_prompt_profile=...)` wires
      the v3 path end-to-end (T10 integration tests verify bootstrap id +
      path class + bridge field)
- [x] Full suite: 866 passed (847 baseline + 13 arbitration + 6 integration);
      2 pre-existing perf-flake failures in `test_performance_benchmark.py`
      (R71 SQLite throughput + semantic recall latency) — unrelated to R79-B.
- [x] R21 ad-hoc logging guard + composition owner-boundary guard: 5/5
      tests pass.
- [ ] R79-D baseline end-to-end probe with v3 bundle (deferred to T15+;
      current end-to-end is covered by the 6 integration tests + 11 arbitration
      tests which use the real `assemble_runtime` wiring)
- [ ] Commit on the `aggressive-radical-persona-no-theater` branch (T15)

## Sub-task T4: R79-C — 5-HT / Oxy / Opioid updater + LLM hormone predict signal

- [ ] Extend `AppraisalDerivedNeuromodulatorUpdatePath` with
      `_serotonin_drive` / `_oxytocin_drive` / `_opioid_drive` methods
- [ ] Add `neuromodulator_serotonin_oxytocin_opioid` learned-parameter
      category to `NeuromodulatorLevels.learned_parameter_categories`
- [ ] Add 12th `hormone_response_i_predict` field to the v3 LLM JSON
      schema in `prompt_contract.r79`
- [ ] Implement `HormonePredictCorroborator` in
      `src/helios_v2/neuromodulation/`
- [ ] Add `hormone_predict_coupling` learned-parameter category
- [ ] Extend `composition_owner_boundary_guard` to forbid
      `<salience>_to_<channel>` strategies in composition glue
- [ ] Write `tests/test_r79c_hormone_coverage.py` with at least 6 cases
      (each new updater, corroborate/conflict/silent, bounds, fallback)
- [ ] Run R79-D baseline: `5-HT / Oxy / Opioid` series non-constant
      under A_praise and B_neglect; `Oxy(A) > Oxy(B)` by `>= 0.02`
- [ ] Full suite green; R21 + composition guard green
- [ ] Commit on the `aggressive-radical-persona-no-theater` branch

## Sub-task T5: R79-D — extendable baseline framework

- [x] Create `src/helios_v2/tests/r79d/` package
- [x] Implement `framework.py` (Scenario dataclass, ExperimentConfig,
      run_experiment)
- [x] Implement `assertions.py` with 9 built-in assertions +
      `@register_assertion` decorator
- [x] Implement `cli.py` with `list / run / report / diff / assertions`
      subcommands
- [x] Implement `_io.py` wrapping `sys.stdout.write` to satisfy R21
- [x] Add 4 v1 baseline scenarios (A / B / C / D) as JSON files
- [x] Implement `reports/generator.py` for aggregate + diff
- [x] Smoke test: `python -m helios_v2.tests.r79d list` returns 4
      scenarios
- [x] Smoke test: `python -m helios_v2.tests.r79d assertions` returns 9
      assertions
- [x] Run baseline 4 scenarios × 52 ticks against real LLM
- [x] Generate `aggregate.md` with 16/28 assertions PASS
- [x] Commit `3827632` "R79-D: extendable baseline experiment framework + 4 v1 scenarios"
- [x] Commit `9597046` "R79-D: route all CLI output through _io module to satisfy R21 guard"
- [x] Cleanup: delete `scratch_r79d_*.py` (5 files)

## Sub-task T6: R80 — internal_monologue source owner

- [ ] Create `src/helios_v2/sensory/internal_monologue.py` with
      `InternalMonologueSource(SensorySource)` Protocol impl
- [ ] Source's `poll()` reads `RuntimeHandle._carry_internal_monologue`
      and emits `RawSignal(signal_type="internal_monologue")`
- [ ] Confirm `02` sensory normalization preserves `signal_type` as
      `Stimulus.signal_type` (no special casing in `02`)
- [ ] Add `appraisal/r79_internal_monologue.py` with
      `InternalMonologueAppraisalEstimator` mapping to
      `novelty=0.3, uncertainty=0.7, social=0.0`
- [ ] Wire into `assemble_runtime` under the R79 profile
- [ ] Write `tests/test_r80_internal_monologue.py` with at least 5
      cases (carry, normalization, appraisal, no-carry fallback, signal_type)
- [ ] Run R79-D baseline: 20-tick A_praise with rumination shows
      `i_want_to_think_more_freq > 0.3` and `5-HT / Cort` cumulative
      drift `>= 0.10`
- [ ] Full suite green; R21 + composition guard green
- [ ] Commit on the `aggressive-radical-persona-no-theater` branch

## Sub-task T7: R81 — multi-tick feedback carry

- [ ] Extend `RuntimeHandle._carry_recall_directive` seam (R49) with
      `_carry_internal_monologue: dict | None` field
- [ ] Extend `09` thought gating owner's input set with
      `self_continuation_signal: float` derived from
      `i_want_to_think_more` + `think_more_about` non-empty
- [ ] Extend `18` autonomy owner's deferred-continuity records with
      `source_kind="internal_monologue"` variant
- [ ] Bump `RuntimeContinuitySnapshot` to v4 with
      `internal_monologue: dict | None` field
- [ ] Confirm v3 → v4 cross-version restore works
      (v3 reads as v4 with `internal_monologue=None`; v4 cannot read as v3)
- [ ] Write `tests/test_r81_carry_enhancements.py` with at least 4 cases
      (intra-tick carry, cross-restart restore, gate signal correlation,
      autonomy source_kind)
- [ ] Run R79-D baseline: `self_continuation_signal` in `09` gate
      correlates with `i_want_to_think_more_freq` (Pearson `>= 0.5`)
- [ ] Full suite green; R21 + composition guard green
- [ ] Commit on the `aggressive-radical-persona-no-theater` branch

## Sub-task T8: R82 — 17-dim behavior drift evaluation

- [ ] Create `src/helios_v2/evaluation/r79_drift.py` with
      `BehaviorDriftDimension` enum (4 families × {1, 1, 4, 5} dimensions
      = 17 dims)
- [ ] Implement `AggressiveRadicalDriftEvaluator` consuming R79-D JSONL output
- [ ] Wire into the P5 launch gate: no P5 learning loop can mutate `04`
      sensitivities until the drift evaluator is green
- [ ] Write `tests/test_r82_drift_evaluator.py` with at least 17 cases
      (one per dim) + 4 family-aggregate cases
- [ ] Generate the R79-D baseline drift report (`drift_report.md`)
- [ ] Full suite green; R21 + composition guard green
- [ ] Commit on the `aggressive-radical-persona-no-theater` branch
- [ ] Push to `origin/aggressive-radical-persona-no-theater`
- [ ] Open PR for review before P5 launch

## Sub-task T9: R79 documentation sync (this change set)

### T9.1 `docs/requirements/index.md` — add R79 row

- [x] Add R79 row: `| 79 | Aggressive-Radical Persona No-Theater | baseline_implementation | 16, 22, 25, 30, 04, 02, 03, 09, 42, 17 | R79-A delivered (AggressiveRadicalEmbodiedPromptPath + 11 unit tests); R79-B delivered (AggressiveRadicalPromptProfile + RuntimeProfile integration + channel arbitration post-processor + 19 new tests, 866 passed); R79-D delivered (4-scenario baseline framework + 52-tick run); R79-C / R80 / R81 / R82 pending |`

### T9.2 `docs/PROGRESS_FLOW.en.md` / `PROGRESS_FLOW.zh-CN.md` — top "最近同步"

- [x] Update `PROGRESS_FLOW.zh-CN.md` "最近同步" from R78 → R79-A
      (AggressiveRadicalEmbodiedPromptPath 落代码, 11 单元测试, 842 passed 基线)
- [x] Update `PROGRESS_FLOW.en.md` "Last sync" same content in English

### T9.3 `docs/OWNER_GUIDE.en.md` / `OWNER_GUIDE.zh-CN.md` — top + §2.11

- [x] Update `OWNER_GUIDE.zh-CN.md` top "最近同步" from R69 → R79-A
- [x] Update `OWNER_GUIDE.en.md` top "Last synced" same content in English
- [x] Add `16` prompt contract §2.11 entry for R79:
      `AggressiveRadicalEmbodiedPromptPath` 是 v3 激进-激进-反戏剧化
      prompt path，与 `FirstVersionEmbodiedPromptPath`（v1）并列存在，
      通过 `prompt_path_mode="aggressive-radical-v3"` 选择。

### T9.4 `docs/ARCHITECTURE_BOUNDARIES.md` — §8 migration-state

- [x] Append R79 entry to §8:
      `R79-progress (2026-06-11): R79-A prompt path + R79-D baseline
      framework delivered. R79-B / R79-C / R80 / R81 / R82 in the same
      requirement package, not yet started.`

### T9.5 Re-commit (cleanup commit)

- [ ] Commit the R79 documentation package on the
      `aggressive-radical-persona-no-theater` branch
      `R79 docs: full requirement package + index/PROGRESS_FLOW/OWNER_GUIDE/ARCHITECTURE_BOUNDARIES sync`

## Open tasks summary

| Sub-task | Status | ETA | Notes |
|---|---|---|---|
| T1 R79 docs | done | — | this change set |
| T2 R79-A | done | — | commit `5fcc80a` |
| T3 R79-B | done | — | `AggressiveRadicalPromptProfile` + RuntimeProfile + assemble_runtime integration + 19 new tests, 866 passed |
| T4 R79-C | pending | after R79-B | needs 3 new updaters + corroborator |
| T5 R79-D | done | — | commits `3827632` + `9597046` |
| T6 R80 | pending | after R79-C | needs `internal_monologue` source + estimator |
| T7 R81 | pending | after R80 | needs carry + v4 snapshot |
| T8 R82 | pending | after R81 | needs 17-dim evaluator + P5 gate |
| T9 R79 doc sync | done | — | this change set |

## Pre-flight checks before each sub-task

1. `git status` clean
2. `git log --oneline -5` shows current branch state
3. `uv run pytest src/helios_v2/tests/ -x -q` last green
4. `python -m helios_v2.tests.r79d list` returns 4 scenarios
5. R21 ad-hoc logging guard green
6. Composition owner-boundary guard green

## Branch strategy

- All R79 work lives on the `aggressive-radical-persona-no-theater` branch
- `main` is untouched (R78 already merged in `a12bbb8`)
- Each sub-task (T2-T8) is one commit on the branch
- R79 documentation sync (T9) is the cleanup commit
- When R82 is done, the branch is pushed and a PR is opened for review
  before P5 launch
