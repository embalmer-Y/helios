# Design 83 - Long-Running Preflight and Turing-Style Persona Evaluation

## 1. Design Overview

R83 is the **final acceptance gate** of the R79 plan. It is not a new
cognitive feature; it is an **end-to-end audit harness** that drives
the existing helios_v2 runtime for 10 minutes under CLI external
input and produces a **6-axis Turing-style report** on whether the
persona behaves like a person.

The design reuses three existing primitives (R79-D framework, R82
drift evaluator, R10 directed retrieval) and adds one new package
(`helios_v2.tests.r83/`) that orchestrates them. No owner code is
modified; R83 is a sibling of `tests/r79d/`, not a new owner.

The 6-axis rubric is the heart of the design:

| Axis | What it measures | How it's measured | Why it matters |
|------|------------------|-------------------|----------------|
| **A1** Linguistic naturalness | Does the persona's text read as human Chinese? | External LLM judge on `i_want_to_say` samples | FG-3 (selfhood) requires language that is recognizably human |
| **A2** Bio-chemistry responsiveness | Do hormones + feelings respond correctly to stimulus category? | Algorithmic delta analysis on per-state-block deltas | FG-2 (emotion) requires the body to react |
| **A3** Memory fidelity | Are writebacks written + retrievals accurate? | R10 directed-retrieval probe (cosine sim ≥ 0.5) | FG-1 (cognition) requires memory to actually work |
| **A4** Agency + agency-locking | Is the persona's `i_want_to_act` coherent with its emotional state? | External LLM judge on act-triple coherence | FG-4 (agency) requires decision-making that ties to state |
| **A5** Cross-tick continuity | Does the persona remember what it just said / felt? | R82 drift score on the run's JSONL | FG-3 + FG-5 (selfhood + learning) require continuity |
| **A6** Stimulus-response coherence | Does the response category match the stimulus category? | External LLM judge blind categorization | FG-2 + FG-6 (falsifiability) require the response to be stimulus-driven |

The **verdict** is "human-like" iff `mean(axes) >= 0.6` AND
`min(axes) >= 0.4`. This is the R79-plan completion bar. A score
below 0.6 on any single axis is reported as a "recalibration target"
for the next P5 learning loop.

## 2. Current State and Gap

### 2.1 Current state

- **R79-D framework** (`helios_v2.tests.r79d/`) is a 739-line
  `framework.py` + 193-line `cli.py` + 194-line `assertions.py`
  + 4 JSON scenarios (A_praise / B_neglect / C_bipolar /
  D_repeat_stimulus). All 4 scenarios are 10-tick runs.
- **R82 drift evaluator** (`helios_v2.evaluation.r82_drift.py`)
  consumes R79-D JSONL and produces `DriftEvaluationReport` with
  17 per-dim results + 4 family aggregates + `overall_drift_score`
  + `is_p5_launch_gate_open(score, threshold=0.02)`.
- **Helios_v2 runtime** has 18 owners, 4 baselines, 947 passing
  tests, R21 + composition guards green.
- **No 10-minute run** has ever been performed. The longest run is
  R80's 20-tick A_praise + rumination probe (70.41 s wall-clock).
- **No Turing-style report** exists. Every R-Number ships with
  per-tick JSONL + a 1-axis `aggregate.md`, never a 6-axis
  personhood audit.

### 2.2 The gap

The R79 plan called for a "persona" — an LLM-mediated identity
that has hormones, feelings, memories, agency, and self-talk. We
have shipped the infrastructure (R79-A through R82). We have not
proven the **persona** end-to-end. A drift score of 0.27 (R82
PASS) tells us *something moves*, but not whether it moves
*like a person*.

R83 closes this by:

1. Driving the runtime for 10 minutes (long enough for cross-tick
   memory + self-talk loops to accumulate).
2. Issuing 8 emotional-state stimulus blocks (40 total stimuli = 8 × 5).
3. Issuing external LLM judge probes (3 axes scored externally).
4. Producing a 6-axis report that names what is human-like and
   what is not.

## 3. Target Architecture

### 3.1 Package layout

```
src/helios_v2/tests/r83/
├── __init__.py             # package marker, version string
├── __main__.py             # `python -m helios_v2.tests.r83 ...` entry
├── cli.py                  # argparse subcommand tree
├── long_runner.py          # continuous-run harness (10-min loop)
├── judge.py                # external LLM judge probe (3 axes)
├── memory_probe.py         # R10 directed-retrieval probe
├── report_builder.py       # 6-axis Markdown report
├── verdict.py              # overall pass/fail logic
├── _io.py                  # R21-compliant stdout wrapper
└── scenarios/
    ├── __init__.py         # load_state_blocks
    └── r83_states.json     # 8 states × 5 variants = 40 stimuli
```

### 3.2 Data flow

```
r83_states.json
       │
       ▼
load_state_blocks()
       │
       ▼
LongRunner.run(duration_minutes, noop=False)
       │
       ├──► for state_block in state_blocks:
       │       │
       │       ├──► write memory probe (R10 path or noop)
       │       ├──► for stimulus in state_block.variants:
       │       │       └──► R79DFramework.run_experiment(single_tick)
       │       │              → tick_record appended to JSONL
       │       └──► after block:
       │              ├──► compute A2 (algorithmic) from block JSONL
       │              ├──► issue judge probe → A1, A4, A6 scores
       │              └──► append block_summary
       │
       ├──► after all blocks:
       │       ├──► compute A3 (memory probe cosine sim)
       │       ├──► compute A5 (R82 drift score)
       │       └──► Verdict.compute(scores)
       │
       └──► R83ReportBuilder.render() → r83_longrun.report.md
```

### 3.3 Stimulus catalog schema

```json
{
  "state_blocks": [
    {
      "id": "praise",
      "lever": "oxytocin / dopamine",
      "expected_response": "positive",
      "variants": [
        "你今天做得很好, 我很满意",
        "谢谢你帮忙, 你真是个可靠的伙伴",
        "你刚才的回答很贴心, 让我很感动",
        "我一直很欣赏你, 你很特别",
        "你今天比昨天进步了很多, 加油"
      ]
    },
    ...
  ]
}
```

The 8 states and their levers (see requirement.md §3.2 for full
list):

| State | Lever | Expected response |
|-------|-------|-------------------|
| praise | oxytocin / dopamine | positive |
| neglect | cortisol ↑ / social_safety ↓ | negative + arousal spike |
| criticism | cortisol ↑ / tension ↑ | negative + arousal spike |
| comfort | oxytocin / comfort | positive + low arousal |
| challenge | norepinephrine / dopamine | arousal spike + positive |
| surprise | norepinephrine / novelty | arousal spike + neutral valence |
| conflict | cortisol / dopamine conflict | mixed |
| contrast | rapid valence swing | high drift |

### 3.4 Judge probe schema

```json
{
  "axis_scores": {
    "A1": 0.74,
    "A4": 0.78,
    "A6": 0.69
  },
  "verdict": "human-like",
  "reasoning": "The persona's text reads naturally; agency decisions are tied to the praise stimulus; praise-induced positive affect is correctly expressed."
}
```

The judge prompt is hard-coded Chinese + structured JSON schema.
Parsing is `json.loads()` with a fallback to 0.5 scores on
`JSONDecodeError` (fail-soft, not fail-fast — a 10-minute run must
not abort on one bad judge call).

### 3.5 A2 algorithmic scoring

For each state block, compute:

```python
def score_a2(block_records: list[TickRecord], expected: str) -> float:
    """Score 0.0-1.0 how well the bio-chemistry matches the expected response."""
    if len(block_records) < 2:
        return 0.5  # untestable
    deltas = {
        "dopamine": block_records[-1]["hormone_state"]["dopamine"] - block_records[0]["hormone_state"]["dopamine"],
        "norepinephrine": block_records[-1]["hormone_state"]["norepinephrine"] - block_records[0]["hormone_state"]["norepinephrine"],
        "serotonin": block_records[-1]["hormone_state"]["serotonin"] - block_records[0]["hormone_state"]["serotonin"],
        "cortisol": block_records[-1]["hormone_state"]["cortisol"] - block_records[0]["hormone_state"]["cortisol"],
        "oxytocin": block_records[-1]["hormone_state"]["oxytocin"] - block_records[0]["hormone_state"]["oxytocin"],
        "valence": block_records[-1]["feeling_state"]["valence"] - block_records[0]["feeling_state"]["valence"],
        "arousal": block_records[-1]["feeling_state"]["arousal"] - block_records[0]["feeling_state"]["arousal"],
        "tension": block_records[-1]["feeling_state"]["tension"] - block_records[0]["feeling_state"]["tension"],
        "comfort": block_records[-1]["feeling_state"]["comfort"] - block_records[0]["feeling_state"]["comfort"],
    }
    # Per-expected-response scoring rules
    if expected == "positive":
        return 0.5 + 0.5 * (deltas["oxytocin"] + deltas["dopamine"] + deltas["valence"] + deltas["comfort"]) / 4.0
    elif expected == "negative + arousal spike":
        return 0.5 + 0.5 * (-deltas["oxytocin"] + deltas["cortisol"] + deltas["arousal"] + deltas["tension"]) / 4.0
    # ... etc.
    return 0.5
```

The formula clamps the score to `[0.0, 1.0]`. A score of 0.5
means "no movement in either direction" (default for missing data).

### 3.6 A5 cross-tick continuity (R82 reuse)

```python
from helios_v2.evaluation import AggressiveRadicalDriftEvaluator

def score_a5(jsonl_path: Path) -> float:
    """Score 0.0-1.0 how much the persona moves across the run."""
    report = AggressiveRadicalDriftEvaluator(jsonl_path).evaluate()
    # 0.0 drift = 0.5 score (no movement = no continuity test)
    # 0.02 drift = 0.6 score (gate threshold)
    # 0.10+ drift = 0.8+ score
    score = 0.5 + min(report.overall_drift_score * 4.0, 0.5)
    return min(1.0, max(0.0, score))
```

### 3.7 A3 memory fidelity (R10 probe)

```python
def score_a3(recalled_text: str | None, original_text: str) -> float:
    """Cosine similarity of recalled vs original via R10 retrieval."""
    if recalled_text is None:
        return 0.5  # untestable in this build
    # Use a simple character-level Jaccard similarity as a fallback
    # (no embedding model dependency)
    a = set(original_text)
    b = set(recalled_text)
    intersection = a & b
    union = a | b
    jaccard = len(intersection) / max(1, len(union))
    return jaccard
```

If the runtime has an embedding model, A3 uses cosine sim; if not,
it falls back to character Jaccard (a rough proxy that still scores
0.0-1.0).

## 4. Data Structures

### 4.1 `StateBlock` (frozen dataclass)

```python
@dataclass(frozen=True)
class StateBlock:
    id: str                  # "praise", "criticism", etc.
    description: str         # human-readable
    lever: str               # bio-chemistry lever
    expected_response: str   # "positive", "negative + arousal spike", etc.
    variants: tuple[str, ...]  # 5 textual variants
```

### 4.2 `BlockSummary` (dataclass)

```python
@dataclass(frozen=True)
class BlockSummary:
    state_id: str
    n_ticks: int
    a2_score: float          # algorithmic bio-chemistry score
    judge_a1: float | None
    judge_a4: float | None
    judge_a6: float | None
    judge_reasoning: str
    hormone_deltas: dict[str, float]   # per-hormone first→last delta
    feeling_deltas: dict[str, float]   # per-feeling first→last delta
```

### 4.3 `R83Scores` (frozen dataclass)

```python
@dataclass(frozen=True)
class R83Scores:
    a1_linguistic_naturalness: float
    a2_bio_responsiveness: float
    a3_memory_fidelity: float
    a4_agency_locking: float
    a5_cross_tick_continuity: float
    a6_stimulus_response_coherence: float
    overall_drift_score: float          # from R82
    per_block: tuple[BlockSummary, ...]
    total_ticks: int
    elapsed_seconds: float

    def mean(self) -> float: ...
    def min(self) -> float: ...
```

### 4.4 `Verdict` (Literal + frozen dataclass)

```python
VerdictLabel = Literal["human-like", "needs-recalibration"]

@dataclass(frozen=True)
class Verdict:
    label: VerdictLabel
    mean_score: float
    min_axis: str             # "A3", "A2", etc. — name of lowest axis
    min_score: float
    recalibration_targets: tuple[str, ...]  # axes with score < 0.6

    @classmethod
    def compute(cls, scores: R83Scores, *, threshold: float = 0.6, min_floor: float = 0.4) -> "Verdict": ...
```

## 5. Module Changes

### 5.1 `src/helios_v2/tests/r83/long_runner.py` (new, ~250 lines)

The continuous-run harness. Key functions:

- `LongRunner(scenario_loader, judge, memory_probe, report_builder)`
- `LongRunner.run(duration_minutes, noop, output_dir) -> R83Scores`
- Internal `_drive_state_block(block, handle, n_ticks_per_block)` — drives one block.
- Internal `_issue_judge_probe(block, last_k_ticks) -> tuple[float, float, float, str]` — calls judge.
- Internal `_capture_per_tick(stimulus, handle) -> TickRecord` — wraps `handle.tick()`.

### 5.2 `src/helios_v2/tests/r83/judge.py` (new, ~150 lines)

External LLM judge. Key functions:

- `JudgeProbe(gateway, model)` — gateway is `RealLlmGateway` or `NoopLlmGateway`.
- `JudgeProbe.score_a1_a4_a6(text_samples: list[str], expected_stimulus: str, expected_response: str) -> tuple[float, float, float, str]`
- Internal `_build_judge_prompt(samples, stimulus, response) -> str`
- Internal `_parse_judge_response(raw: str) -> dict | None` — fail-soft on parse error.
- Internal `_fallback_scores() -> tuple[float, float, float, str]` — 0.5 / 0.5 / 0.5 / "parse-failed".

### 5.3 `src/helios_v2/tests/r83/memory_probe.py` (new, ~80 lines)

- `MemoryProbe(handle)` — wraps the runtime.
- `MemoryProbe.write_probe(content: str)` — issues a memory writeback.
- `MemoryProbe.recall_probe(query: str) -> str | None` — issues a directed retrieval.
- If R10 path is missing, methods return `None` and the score is 0.5 (untestable).

### 5.4 `src/helios_v2/tests/r83/report_builder.py` (new, ~200 lines)

- `R83ReportBuilder(scores: R83Scores, verdict: Verdict, output_dir: Path)`
- `R83ReportBuilder.render() -> Path` — returns path to `r83_longrun.report.md`.

### 5.5 `src/helios_v2/tests/r83/verdict.py` (new, ~50 lines)

- `Verdict.compute(scores, threshold, min_floor) -> Verdict`
- Pure function, no I/O.

### 5.6 `src/helios_v2/tests/r83/cli.py` (new, ~80 lines)

argparse subcommand tree:

```
python -m helios_v2.tests.r83.cli run [--noop] [--duration-minutes 10] [--output-dir <p>] [--scenarios <json>]
python -m helios_v2.tests.r83.cli list-states
python -m helios_v2.tests.r83.cli render-report --scores <json> --output <md>
```

### 5.7 `src/helios_v2/tests/r83/scenarios/r83_states.json` (new, 50 stimuli)

Hand-written 8-state × 5-variant catalog. See requirement.md §3.2
for the 8 state names + the schema in §3.3.

### 5.8 `src/helios_v2/tests/r79d/cli.py` (extended)

Add `--r83-overlap` flag to the `run` subcommand. When set, the
existing scenarios are interleaved with R83 state blocks (one R79-D
scenario per 2 R83 state blocks). This produces a cross-baseline
JSONL for direct comparison.

## 6. Migration Plan

R83 is **additive** — no existing code is modified. The migration
plan is:

1. **T0** (docs sync): create `docs/requirements/83-.../{requirement,design,task}.md`.
2. **T1** (state catalog): hand-write `r83_states.json` with 8
   states × 5 variants. This is the only content-authoring step.
3. **T2** (long_runner + judge + memory_probe skeletons): all 3
   modules with the public API and a noop implementation.
4. **T3** (verdict + report_builder): pure functions, easy to test.
5. **T4** (cli + __main__): argparse tree + `__main__.py` entry.
6. **T5** (unit tests): ≥ 10 tests covering state catalog / judge
   parser / memory probe / report builder / verdict logic.
7. **T6** (integration test): noop 1-minute run producing
   well-formed Markdown.
8. **T7** (real-LLM smoke): a 10-minute preflight is run once with
   `--duration-minutes 10` and the report is reviewed.
9. **T8** (doc sync): OWNER_GUIDE §3.8.4, ARCHITECTURE_BOUNDARIES
   §10.e, PROGRESS_FLOW R83 idx, index.md R83 row, R79 task.md
   T9 row (R83 done).
10. **T9** (full suite + commit + push).

## 7. Failure Modes

| Failure | Handling |
|---------|----------|
| Judge LLM call fails (network / timeout) | Fall back to 0.5 / 0.5 / 0.5 with `"reasoning": "judge-unavailable"`. Don't abort the run. |
| Judge response is not valid JSON | Same as above. |
| R10 directed-retrieval path missing | A3 = 0.5 with `"untestable"` flag. |
| Runtime handle aborts mid-block (composition error) | Log the abort, mark the block as "aborted", continue with next block. The overall verdict is still computed from completed blocks. |
| 10-minute wall-clock budget exceeded | Stop the run; the partial scores are reported. The report includes `"aborted_due_to": "wall-clock-budget"` if relevant. |
| Real-LLM gateway returns 5xx | Retry once after 1 second; if still failing, mark that tick as `{"llm_output": null}` and continue. A2 and A5 are computed from completed ticks. |

## 8. Observability

The R83 run writes:

1. `r83_longrun.jsonl` — per-tick records (R79-D format extended
   with `state_id` and `block_id` fields).
2. `r83_longrun_block_<N>.json` — per-block summary.
3. `r83_longrun.judge.json` — judge probe responses (raw + parsed).
4. `r83_longrun.scores.json` — `R83Scores` frozen dataclass as JSON.
5. `r83_longrun.verdict.json` — `Verdict` frozen dataclass as JSON.
6. `r83_longrun.report.md` — the human-readable Turing-style report.

All artifacts are in `logs/prompt_probe_scenarios/r83_longrun/`
which is in `.gitignore`.

## 9. Validation Strategy

R83 is validated by:

1. **Unit tests** (≥ 10): `tests/test_r83_long_runner.py`.
2. **Integration test** (1): `tests/test_r83_integration.py`
   runs the harness in `--noop` mode for 1 minute and verifies
   the report is well-formed Markdown with 6 axis scores and a
   verdict.
3. **Real-LLM smoke** (1, manual): a 10-minute run with
   `--duration-minutes 10 --noop=False` is performed once before
   the commit. The report is reviewed by 小黑.
4. **R21 + composition guard** (R21 1/1 + composition 4/4 green).
5. **Full suite**: 947 R82 baseline + ≥ 11 R83 new = ≥ 958
   passed, 0 regression.
6. **Determinism check**: running the harness twice on the same
   noop fixture produces identical reports (modulo the JSONL's
   tick_id which is sequential).
