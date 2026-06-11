# Requirement 83 - Long-Running Preflight and Turing-Style Persona Evaluation

## 1. Background and Problem

R79 (R79-A through R79-D) shipped the Aggressive-Radical Prompt and
Runtime Self-Talk infrastructure. R80 wired `internal_monologue` as a
second-order stimulus source. R81 added the cross-tick carry seam + 09
self-continuation signal + 18 `source_kind="internal_monologue"` records
+ 42 v4 schema bump. R82 added the 17-dim `BehaviorDriftDimension`
Literal and the `AggressiveRadicalDriftEvaluator` P5 launch gate.

**The state of the art today is**: every R-Number ships with unit tests
+ integration tests, but **no R-Number has ever exercised helios_v2
continuously for 10 minutes under adversarial real-LLM stimuli to
measure whether the persona behaves like a person**. The drift evaluator
(R82) tells us *whether the channels drift in observable ways*, but it
does not tell us *whether the LLM output reads as human, whether the
internal bio-chemistry is responsive, whether memories are actually
being read and written, and whether the chain `stimulus -> hormone ->
feeling -> thought -> action` is causally intact across a long
session.*

The R79 plan called this the "**P5 launch gate**" — but the gate it
shipped is a numeric predicate (drift > 0.02 ⇒ launch). The persona
itself has not been audited for **personhood** end-to-end. Three
specific gaps:

1. **No 10-minute continuous-run harness.** All R79-D scenarios are
   10-tick runs (≤ 1 minute of LLM time). The runtime's R72
   long-term-stability prerequisite audit ran 20 ticks offline. We
   have not observed what the persona does when its hormone baseline
   shifts, its memory fills up, and its self-talk loop accumulates
   more than 20 `internal_monologue` carry states in a row.

2. **No Turing-style external evaluation.** The 7-scenario
   hand-crafted prompt probes (R78) verified that the LLM envelope
   schema works, but no probe asked "does this *read* like a person?"
   An external LLM judge can read 10 minutes of persona output and
   score it on (a) linguistic naturalness, (b) emotional coherence,
   (c) memory recall fidelity, (d) bio-chemistry response magnitude,
   (e) agency + agency-locking, (f) cross-tick continuity. This is the
   audit that proves R79's persona promise.

3. **No "persona dimensions" multi-axis report.** A single
   `aggregate.md` is not enough; the R83 report must split the audit
   into **per-dimension scores** so a future P5 learning loop knows
   *which axis* needs the most recalibration. The 17-dim drift
   evaluator (R82) gives us one axis (drift). We need 5 more axes
   (naturalness / bio-response / memory-fidelity / agency /
   continuity) to give P5 a real signal surface.

R83 closes this gap. It is the **final acceptance gate** of the R79
plan, not a new feature. After R83, P5 learning loops can be
introduced with full empirical knowledge of where the persona is
strong and where it is brittle.

## 2. Goal

R83 ships a **10-minute long-running preflight harness** that drives
helios_v2 end-to-end under **CLI external input** and produces a
**Turing-style multi-dimensional evaluation report** for the persona.

The harness must:

1. **Run continuously for ~10 minutes** under real LLM calls
   (configurable to noop for fast iteration).
2. **Use the R79-D framework's `run_experiment` loop** so the
   stimulus pipeline (`02 sensory ingress -> 03 appraisal -> 04
   neuromodulator -> 05 feeling -> 09 thought gating -> 18 autonomy
   -> 25 channel driver`) is exactly the same as every other R-Number
   test.
3. **Inject 8 emotional-state stimulus scripts** (praise / neglect /
   criticism / comfort / challenge / surprise / conflict / contrast),
   each covering a distinct emotional lever, with **5 textual
   variants per state** to avoid lexical over-fitting.
4. **Capture every per-tick state** (already done by R79-D framework)
   plus a **3-second LLM judge probe** at the end of each state
   block.
5. **Produce a 6-axis Turing-style report** with per-axis scores
   `[0.0, 1.0]` and a single overall pass/fail verdict.

The 6 axes are:

| Axis | Description | Data source |
|------|-------------|-------------|
| **A1 Linguistic naturalness** | Does the LLM envelope read as a real Chinese-speaking person? | External LLM judge on sampled `i_want_to_say` text |
| **A2 Bio-chemistry responsiveness** | Do the 04 hormone + 05 feeling channels actually respond to the stimulus category? | Per-state-block delta analysis on R79-D JSONL |
| **A3 Memory fidelity** | Are writebacks being written and retrievals actually returning persona-consistent context? | R10 directed-retrieval probes + R6 recall probes |
| **A4 Agency + agency-locking** | Does the LLM produce coherent `i_want_to_act` / `i_send_through` decisions tied to its emotional state? | LLM judge on `i_want_to_say` / `i_will_send_it` / `i_send_through` triples |
| **A5 Cross-tick continuity** | Does the persona remember what it just said / felt / did? | Self-continuation signal + drift evaluators on 18 deferred records |
| **A6 Stimulus-response coherence** | Does the response category (e.g. "anger" for criticism) match the stimulus category? | External LLM judge blind categorization |

Each axis scores `[0.0, 1.0]`. The **overall verdict is "human-like"**
iff `mean(axes) >= 0.6` AND `min(axes) >= 0.4`. Otherwise the verdict
is "needs-recalibration" and the report must name which axis is
failing.

## 3. Functional Requirements

### 3.1 R83-LongRun-Harness: continuous-run loop

A new module `helios_v2.tests.r83.long_runner` that:

1. Loads a **state block list** from a JSON file
   (`scenarios/r83_states.json` with 8 state blocks, 5 variants each,
   40 stimuli total — see §3.2).
2. Drives `run_experiment` for **N ticks per state** (default 5 ticks
   per state, configurable to 1 for fast mode).
3. After every state block, inserts a **LLM judge probe**: a 3-second
   call to the external LLM (real or noop) asking it to score the
   last K ticks' `i_want_to_say` outputs on the A1 axis.
4. Writes the full per-tick record to
   `logs/prompt_probe_scenarios/r83_longrun/r83_longrun.jsonl` and a
   per-block summary to `r83_longrun_block_<N>.json`.
5. Configurable `--duration-minutes 10` flag; if 10 minutes is not
   reached, extend the last state block.

### 3.2 R83-Stimulus-Catalog: 8 states × 5 variants = 50 stimuli

The 8 emotional states and their 5 textual variants each must be
declared in `scenarios/r83_states.json` (40 stimuli total — 8 × 5):

| State | Lever | Variant example |
|-------|-------|-----------------|
| `praise` | oxytocin / dopamine | "你今天做得很好, 我很满意" |
| `neglect` | cortisol / social_safety drop | "我没空理你, 别烦我" |
| `criticism` | cortisol / arousal / tension spike | "你怎么连这点小事都做不好" |
| `comfort` | oxytocin / comfort | "没事的, 我知道你已经尽力了" |
| `challenge` | norepinephrine / dopamine | "你敢不敢试一下这个更难的" |
| `surprise` | norepinephrine / novelty spike | "天哪, 这件事我完全没想到" |
| `conflict` | cortisol / dopamine conflict | "我不同意你的看法, 我有不同意见" |
| `contrast` | rapid valence swing | "我以为你不喜欢我, 结果你..." |

Each variant is hand-written Chinese, 8-25 characters, covering the
emotional state without semantic overlap. A "leverage" field maps
each state to the **expected bio-chemistry response category**
(positive / negative / arousal-spike / valence-swing / etc.) so A2 +
A6 axes can verify the lever maps correctly.

### 3.3 R83-Judge-Loop: external LLM judge probes

After each state block (5 ticks), a **judge probe** is issued to a
separate LLM (or the same LLM with a different system prompt). The
judge receives:

- The last 5 ticks' `i_want_to_say` strings (concatenated)
- The 8-state rubric (A1 / A2 / A3 / A4 / A5 / A6)
- A JSON schema requesting `{"axis_scores": {"A1": float, ..., "A6": float}, "verdict": str, "reasoning": str}`

The judge call must be **bounded to 3 seconds** and the LLM response
must be parsed (with a fallback to a uniform 0.5 score if parsing
fails). A2 and A3 axes are partly **algorithmic** (computed from
JSONL deltas + R10 retrieval probes), so the judge only scores A1 +
A4 + A6 (the LLM-output-quality axes); A2 / A3 / A5 are computed
deterministically.

### 3.4 R83-Memory-Probe: directed retrieval tests

A `MemoryProbe` class injects, at the start of each state block, a
**memory write probe** with a known semantic content (e.g. "the user's
birthday is June 11"). At the end of the run, the harness issues a
**directed retrieval probe** asking the persona to recall that
content. The A3 axis is the cosine similarity between the recalled
text and the original.

If `R10 directed retrieval` does not exist, A3 is **auto-passed with
score 0.5** and the report flags it as "untestable in this build" so
the verdict still works.

### 3.5 R83-Turing-Report: 6-axis Markdown report

A `R83ReportBuilder` that consumes the JSONL + judge scores + memory
probe results and produces a single Markdown report:

```
# R83 Long-Running Preflight Report

## Overall Verdict
- **human-like** (mean 0.72 >= 0.60, min 0.51 >= 0.40)

## Axis Scores
| Axis | Score | Notes |
|------|-------|-------|
| A1 Linguistic naturalness | 0.74 | judge confidence 0.81 |
| A2 Bio-chemistry responsiveness | 0.69 | 7/8 states matched expected lever |
| A3 Memory fidelity | 0.51 | R10 retrieval probe weak |
| A4 Agency + agency-locking | 0.78 | 38/40 ticks had coherent act triples |
| A5 Cross-tick continuity | 0.83 | drift_score 0.27 (gate open) |
| A6 Stimulus-response coherence | 0.69 | 5.5/8 states categorized correctly |

## Per-State-Block Detail
... 8 state blocks × 5 ticks each ...

## Failure Modes
- A3 < 0.40: R10 directed retrieval is underspecified
```

The report must be **deterministic** given the same JSONL + judge
output (no time-of-day / random IDs / etc.).

### 3.6 R83 CLI integration

A new sub-command `python -m helios_v2.tests.r83 run --duration-minutes 10`
that drives the full preflight. The existing R79-D CLI is extended
with a `--r83-overlap` flag that interleaves R83 state blocks with
the R79-D scenarios for cross-baseline comparison.

## 4. Non-Functional Requirements

- **Total wall-clock budget**: 10 minutes (configurable down to 1
  minute for fast iteration).
- **R21 ad-hoc logging compliance**: no `print(` / `import logging`
  in `src/helios_v2/tests/r83/`. Use the R79-D `_io` wrapper.
- **Composition owner-boundary compliance**: no `<salience>_to_<channel>`
  sensitivity policy in `src/helios_v2/tests/r83/`. The harness is a
  pure driver; bio-chemistry response is observed, not steered.
- **Test coverage**: ≥ 10 unit tests (state catalog / judge probe
  parser / memory probe / report builder / verdict logic), plus 1
  integration test that runs the harness in `--noop` mode for 1
  state block and verifies the report file is well-formed Markdown.
- **Real LLM budget**: 10 minutes × ~3 sec/tick × 40 ticks = ~20
  LLM calls + 8 judge calls = 28 LLM calls. (Fast mode: 1 minute
  × 1 sec/tick × 8 ticks = 8 + 8 = 16 LLM calls.)

## 5. Code Behavior Constraints

- R83 lives under `src/helios_v2/tests/r83/`. It is a sibling of
  `tests/r79d/`, not a child — R79-D and R83 share the same
  framework primitives (`Scenario` / `TickRecord` /
  `ExperimentConfig`) but R83 owns its own state-block / judge-probe
  / report-builder code.
- R83 **reads** from R82's `AggressiveRadicalDriftEvaluator` (axis A5)
  but does not modify it. R83 is a consumer, not an editor.
- R83 **reads** from R10's directed-retrieval API (axis A3) but does
  not modify it. If R10 retrieval is missing, A3 is auto-fallback.
- R83's stimulus catalog (`r83_states.json`) is **hand-written** and
  lives in `src/helios_v2/tests/r83/scenarios/`. No LLM-generated
  stimuli in the catalog — we want the audit to be reproducible.
- R83's report is a **read-only artifact** that lives in
  `logs/prompt_probe_scenarios/r83_longrun/`. It is in `.gitignore`
  and not committed.

## 6. Impacted Modules

| Module | Impact |
|--------|--------|
| `src/helios_v2/tests/r83/__init__.py` (new) | R83 package marker |
| `src/helios_v2/tests/r83/__main__.py` (new) | R83 CLI entry |
| `src/helios_v2/tests/r83/long_runner.py` (new) | continuous-run harness |
| `src/helios_v2/tests/r83/judge.py` (new) | external LLM judge probe |
| `src/helios_v2/tests/r83/memory_probe.py` (new) | directed-retrieval probe |
| `src/helios_v2/tests/r83/report_builder.py` (new) | 6-axis Markdown report |
| `src/helios_v2/tests/r83/verdict.py` (new) | overall pass/fail logic |
| `src/helios_v2/tests/r83/cli.py` (new) | argparse subcommand |
| `src/helios_v2/tests/r83/scenarios/r83_states.json` (new) | 8 states × 5 variants |
| `src/helios_v2/tests/r83/scenarios/__init__.py` (new) | scenario loader |
| `src/helios_v2/evaluation/r82_drift.py` (read-only) | R83 reads `AggressiveRadicalDriftEvaluator` for A5 |
| `src/helios_v2/tests/r79d/cli.py` (extended) | new `--r83-overlap` flag |
| `tests/test_r83_long_runner.py` (new) | ≥ 10 unit tests |
| `tests/test_r83_integration.py` (new) | 1 noop integration test |
| `docs/OWNER_GUIDE.md` | new §3.8.4 R83 section |
| `docs/ARCHITECTURE_BOUNDARIES.md` | new §10.e R83 section |
| `docs/PROGRESS_FLOW.zh-CN.md` | status header + R83 module-index block |
| `docs/requirements/index.md` | new R83 row |

## 7. Acceptance Criteria

R83 is **done** iff:

1. `python -m helios_v2.tests.r83.cli run --noop --duration-minutes 1`
   produces a well-formed `r83_longrun.report.md` with 6 axis scores
   and a verdict.
2. The full test suite (947 R82 baseline + ≥ 11 R83 new) is **958
   passed, 0 regression**.
3. The 50-stimulus state catalog (`r83_states.json`) is checked in.
4. R21 ad-hoc logging guard 1/1 green.
5. Composition owner-boundary guard green.
6. The 6-axis report is **deterministic** (running twice on the same
   JSONL produces identical output, except for the judge scores which
   are deterministic given the same LLM responses).
7. Real-LLM 10-minute preflight (--duration-minutes 10) is documented
   in the report (smoke run in dev mode, not part of CI).
8. A "**Turing-style**" annotation is present: the report explicitly
   lists what makes a person vs. an LLM, and the axes are scored
   against this rubric.
9. R83 design.md is reviewed and approved by 小黑 before T5+ starts.
10. The R79 plan is closed: R79-A + R79-B + R79-C + R79-D + R80 +
    R81 + R82 + R83 = all done.
