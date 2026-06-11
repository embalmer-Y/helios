# Task 83 - Long-Running Preflight and Turing-Style Persona Evaluation

R83 is the **final acceptance gate** of the R79 plan. It is a 10-minute
end-to-end audit harness that drives helios_v2 under CLI external input
and produces a 6-axis Turing-style report.

Status legend: `[ ]` pending · `[~]` in flight · `[x]` done

## T0 - Documentation sync (requirement / design / task packages)

- [x] Create `docs/requirements/83-r83-long-running-preflight-and-turing-style-evaluation/requirement.md` (14300 bytes)
- [x] Create `docs/requirements/83-r83-long-running-preflight-and-turing-style-evaluation/design.md` (18000 bytes)
- [x] Create `docs/requirements/83-r83-long-running-preflight-and-turing-style-evaluation/task.md` (this file)
- [x] Update `docs/requirements/79-r79-aggressive-radical-prompt-and-runtime-self-talk/task.md` to add T9 row for R83

## T1 - Hand-write the 8-state stimulus catalog (`r83_states.json`)

- [x] 8 state blocks × 5 textual variants = 40 stimuli, all hand-written Chinese
- [x] Each block has `id` / `description` / `lever` / `expected_response` / `variants`
- [x] Verify the catalog loads with `r83.scenarios.load_state_blocks()`
- [x] 8 state blocks: `praise` / `neglect` / `criticism` / `comfort` / `challenge` / `surprise` / `conflict` / `contrast`
- [x] All 50 stimuli are 8-25 chars, no semantic overlap between blocks

## T2 - Long runner + judge probe + memory probe skeletons

- [x] `src/helios_v2/tests/r83/long_runner.py` (~250 lines): `LongRunner.run(duration_minutes, noop, output_dir) -> R83Scores`
- [x] `src/helios_v2/tests/r83/judge.py` (~150 lines): `JudgeProbe.score_a1_a4_a6(samples, stimulus, response)`
- [x] `src/helios_v2/tests/r83/memory_probe.py` (~80 lines): `MemoryProbe.write_probe` / `recall_probe`
- [x] All 3 modules use the R79-D `_io` wrapper for stdout (R21 compliance)
- [x] No `<salience>_to_<channel>` policy in any of the 3 modules (composition compliance)

## T3 - Verdict logic + report builder (pure functions)

- [x] `src/helios_v2/tests/r83/verdict.py` (~50 lines): `Verdict.compute(scores, threshold=0.6, min_floor=0.4)`
- [x] `src/helios_v2/tests/r83/report_builder.py` (~200 lines): `R83ReportBuilder.render() -> Path`
- [x] Report contains: overall verdict, 6-axis score table, per-block detail, failure modes section
- [x] Report is deterministic given the same JSONL + judge responses

## T4 - CLI + `__main__.py` entry

- [x] `src/helios_v2/tests/r83/cli.py` (~80 lines): argparse tree with `run` / `list-states` / `render-report` subcommands
- [x] `src/helios_v2/tests/r83/__main__.py` (~10 lines): `python -m helios_v2.tests.r83 ...` entry
- [x] `src/helios_v2/tests/r83/__init__.py` (~5 lines): package marker + version string
- [x] `python -m helios_v2.tests.r83.cli run --noop --duration-minutes 1` produces a Markdown report

## T5 - Unit tests (≥ 10)

- [x] `tests/test_r83_long_runner.py` with the following test cases:
  - [x] `test_state_catalog_loads` — 8 blocks, 5 variants each
  - [x] `test_state_catalog_no_semantic_overlap` — 8 levers are distinct
  - [x] `test_judge_probe_parse_valid_json` — happy path
  - [x] `test_judge_probe_parse_invalid_json` — fallback to 0.5
  - [x] `test_judge_probe_prompt_construction` — Chinese + JSON schema
  - [x] `test_memory_probe_no_r10` — auto-fallback to 0.5
  - [x] `test_memory_probe_with_r10` — cosine sim
  - [x] `test_verdict_human_like` — mean >= 0.6 AND min >= 0.4
  - [x] `test_verdict_needs_recalibration` — min < 0.4
  - [x] `test_verdict_recalibration_targets` — axes with score < 0.6
  - [x] `test_a2_algorithmic_positive_response` — praise → oxytocin / dopamine / valence / comfort ↑
  - [x] `test_a2_algorithmic_negative_response` — criticism → cortisol / tension ↑
  - [x] `test_a5_drift_score` — uses R82 evaluator
  - [x] `test_report_builder_deterministic` — same input → same output

## T6 - Integration test (noop 1-minute run)

- [x] `tests/test_r83_integration.py`:
  - [x] `test_noop_one_minute_run_produces_report` — drives harness in --noop mode for 1 state block, verifies the report file is well-formed Markdown
  - [x] `test_noop_one_minute_run_writes_jsonl` — verifies the per-tick JSONL is written
  - [x] `test_noop_one_minute_run_writes_scores_json` — verifies R83Scores JSON is written

## T7 - Real-LLM 10-minute smoke (manual)

- [x] `python -m helios_v2.tests.r83.cli run --duration-minutes 10 --output-dir logs/prompt_probe_scenarios/r83_longrun/`
- [x] The report is reviewed by 小黑 (manually)
- [x] The 6-axis scores are recorded in the report

## T8 - Doc sync (4 files)

- [x] `docs/OWNER_GUIDE.md` — new §3.8.4 R83 section + status header update
- [x] `docs/ARCHITECTURE_BOUNDARIES.md` — new §10.e R83 section
- [x] `docs/PROGRESS_FLOW.zh-CN.md` — status header update + R83 module-index block
- [x] `docs/requirements/index.md` — new R83 row

## T9 - Full suite validation

- [x] Full suite green: 947 R82 baseline + ≥ 17 R83 new = **≥ 964 passed, 0 regression**
- [x] R21 ad-hoc logging guard 1/1 green
- [x] Composition owner-boundary guard 4/4 green
- [x] The R79 plan is closed: R79-A + R79-B + R79-C + R79-D + R80 + R81 + R82 + R83 = all done

## T10 - Commit + push

- [x] Single atomic commit with all R83 code + tests + docs
- [x] `git add` the 17 R83 files (8 src / 2 tests / 4 docs / 1 catalog JSON / 2 markers)
- [x] `git commit` with a clear R83 summary message
- [x] `git push origin aggressive-radical-persona-no-theater` to the beta branch
- [x] Update HEARTBEAT.md to mark R83 done
- [x] Update MEMORY.md to add R83 overview
- [x] Update `memory/2026-06-11.md` with the R83 milestone

## Acceptance summary

R83 is **done** iff:

- [x] All T0-T10 are checked off.
- [x] The R83 report (`r83_longrun.report.md`) is well-formed and the verdict is `human-like` or `needs-recalibration` (both are valid; `human-like` is the R79-plan completion bar).
- [x] The stimulus catalog is reproducible (running the harness twice on the same noop fixture produces the same 40 stimuli).
- [x] The report includes a "Turing-style" annotation that names what makes a person vs. an LLM.
- [x] The R79 plan is closed in `docs/requirements/index.md` and `HEARTBEAT.md`.
