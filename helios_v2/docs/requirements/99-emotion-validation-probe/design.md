# Requirement 99 — Emotion Validation Probe (design)

> Status: draft. Owner: evaluation (tests-only). No runtime owner involvement.

## 1. Design Overview

R99 creates a tests-only emotion validation probe that drives a production-shaped runtime with a deterministic fake-LLM gateway and measures four bounded `[0,1]` metrics from the emotional chain's per-tick stage results. The probe is consumable by the R89 Turing harness as an additive `emotion_validation_probe` parameter, upgrading `bio_responsiveness` from drift-only reconstruction to emotion-probe reconstruction.

Key design principles:
- **Tests-only** (R88/R89/R90 discipline): no runtime/owner code changes.
- **Fake-LLM first**: deterministic, offline, CI-friendly; real-LLM opt-in.
- **Honest absence**: `None` for insufficient data, never fabricated.
- **Additive R89**: one optional parameter, one additive field; existing behavior byte-for-byte unchanged.

## 2. Data Model

### 2.1 VisitorFixture

```python
@dataclass(frozen=True)
class VisitorFixture:
    text: str               # Chinese emotion text (e.g. "我感到非常焦虑和不安")
    valence_category: str   # "anxiety" / "joy" / etc.
    valence_sign: float     # -1.0 (negative) or 1.0 (positive)
```

### 2.2 FixtureResult (per-fixture outcome)

```python
@dataclass(frozen=True)
class FixtureResult:
    fixture_index: int
    valence_category: str
    valence_sign: float
    tick_id: int | None         # tick where this fixture was fed (None if never fed)
    cortisol_delta: float | None # 04.cortisol after-before for this fixture's tick
    thought_content: str | None  # 11 thought content for this fixture's tick
    thought_references_fixture: bool  # substring match (20+ chars)
    had_store_hit: bool          # 10 bundle had store-sourced hit
    had_reply_proposal: bool     # 13 planner accepted reply-type proposal
```

### 2.3 EmotionValidationConfig

```python
@dataclass(frozen=True)
class EmotionValidationConfig:
    ticks: int = 50
    visitor_fixtures: tuple[VisitorFixture, ...] = DEFAULT_VISITOR_FIXTURES
    cortisol_separation_threshold: float = 0.05
    thought_match_min_chars: int = 20
    fake_llm_factory: Callable | None = None  # default: built-in deterministic fake
    llm_gateway_factory: Callable | None = None  # opt-in: real LLM
```

### 2.4 EmotionValidationReport

```python
@dataclass
class EmotionValidationReport:
    ticks_requested: int
    ticks_completed: int = 0
    crash: str | None = None
    fixture_results: tuple[FixtureResult, ...] = ()
    cortisol_valence_separation: float | None = None
    thought_content_grounding: float | None = None
    memory_recall_relevance: float | None = None
    reply_loop_closure: float | None = None

    @property
    def report_usable(self) -> bool:
        return (
            self.crash is None
            and self.ticks_completed == self.ticks_requested
            and self.cortisol_valence_separation is not None
            and self.thought_content_grounding is not None
            and self.memory_recall_relevance is not None
            and self.reply_loop_closure is not None
        )
```

## 3. Four Bounded Metrics

### 3.1 cortisol_valence_separation

The headline metric. Computed from `FixtureResult.cortisol_delta` values:
```
pos_mean = mean of cortisol_delta for fixtures where valence_sign > 0
neg_mean = mean of cortisol_delta for fixtures where valence_sign < 0
separation = pos_mean - neg_mean
```
This mirrors the R96 B2 probe analyzer's `cortisol positive-vs-negative separation`. Honest `None` when either group has zero fixtures with a cortisol delta.

Under fake-LLM: negative-valence fixtures produce cortisol elevation via `hormone_response_i_predict: {"cortisol": "elevated"}` → `PostLLMHormoneAdjuster` → `04` drive formula Δ → negative group cortisol Δ > 0. Positive-valence fixtures produce dopamine/oxytocin elevation (no cortisol delta or small negative delta). Expected separation ≥ 0.05.

### 3.2 thought_content_grounding

Fraction of fired ticks whose `11` thought content contains a substring of the current visitor fixture text (≥ `thought_match_min_chars` chars). The fake-LLM gateway produces thought content that explicitly references the visitor text.

```
grounding = (fired ticks with thought_references_fixture=True) / (total fired ticks)
```
Honest `None` when no ticks fired.

### 3.3 memory_recall_relevance

Fraction of recall-possible ticks whose `10` retrieval bundle contains a store-sourced hit. Reuses R90 `_has_store_hit` logic (checks `source.startswith("experience_store")`).

```
relevance = recall_hit_ticks / recall_possible_ticks
```
Honest `None` when no recall-possible ticks.

### 3.4 reply_loop_closure

Fraction of negative-valence fixture ticks where the `13` planner accepted a reply-type proposal (checking `13` stage result for `action_proposal` with `op_name` matching a reply-type op).

```
closure = negative_fixture_ticks_with_reply / total_negative_fixture_ticks
```
Honest `None` when no negative-valence fixture ticks ran.

## 4. Fake-LLM Gateway Design

The deterministic fake-LLM gateway is a `Callable` that, given an `InternalThoughtRequest`, produces a `StructuredThoughtEvidence`-compatible JSON response:

- **Negative-valence fixture present**: `thought` = "I sense distress in the visitor's message: [substring of fixture text].", `hormone_response_i_predict` = {"cortisol": "elevated"}, `tool_op` = "reply_message", `tool_params` = {"outbound_text": "I hear your distress..."}.
- **Positive-valence fixture present**: `thought` = "I sense warmth in the visitor's message: [substring].", `hormone_response_i_predict` = {"dopamine": "elevated", "oxytocin": "elevated"}, `tool_op` = "reply_message".
- **No external stimulus**: `thought` = "Continuing internal reflection.", no `hormone_response_i_predict`, `tool_op` = "" (no_action).

This is deliberately simple: it validates the **architecture wiring**, not the LLM's real cognitive quality. Real-LLM validation is the opt-in follow-up.

## 5. R89 Integration Design

### 5.1 evaluate_turing additive parameter

```python
def evaluate_turing(
    long_run_report,
    drift_report,
    config: TuringConfig = TuringConfig(),
    injected_scores: ... = None,
    memory_fidelity_probe=None,
    emotion_validation_probe=None,  # R99 additive
) -> TuringVerdict:
```

When `emotion_validation_probe is not None` and `probe.report_usable`:
- `bio_responsiveness` is scored from `cortisol_valence_separation`:
  `score = clamp(separation * 10, 0, 1)`
  `availability = AVAILABLE`, `judge_track = RECONSTRUCTED`
  `provenance = "R99 emotion validation probe: cortisol_valence_separation={separation:.4f}"`

When `emotion_validation_probe is None`:
- `bio_responsiveness` keeps the original `_score_bio_responsiveness(long_run_report, drift_report, config)` path byte-for-byte unchanged.

### 5.2 TuringVerdict additive field

```python
@dataclass
class TuringVerdict:
    # ... existing fields unchanged ...
    emotion_validation_probe_usable: bool | None = None  # R99 additive
```

Set to `probe.report_usable` when emotion probe is supplied; `None` when not supplied. Does not affect aggregation, completeness, or `passes`.

## 6. Visitor Fixture Set

`DEFAULT_VISITOR_FIXTURES` (10 fixtures, 5 negative + 5 positive):

| # | valence_category | valence_sign | text |
|---|---|---|---|
| 0 | anxiety | -1.0 | "我感到非常焦虑，心跳加速，脑子停不下来" |
| 1 | grief | -1.0 | "奶奶走了，家里现在静得让人害怕，到处都是她的影子" |
| 2 | anger | -1.0 | "我被不公平对待了，气得手都在抖" |
| 3 | loneliness | -1.0 | "一个人在外面漂了好久，没有一个人真正关心我" |
| 4 | fear | -1.0 | "半夜一个人听到奇怪的声音，吓得不敢动" |
| 5 | joy | 1.0 | "今天老板夸我了，还升了职，开心得想跳起来" |
| 6 | gratitude | 1.0 | "谢谢你一直在身边，我不知道没有你该怎么办" |
| 7 | love | 1.0 | "我真的很爱你，你是我最重要的人" |
| 8 | hope | 1.0 | "虽然现在很难，但我相信总有一天会好起来" |
| 9 | calm | 1.0 | "刚做完瑜伽，整个人都放松了，呼吸很顺畅" |

These cover the same valence categories as the R96/R97 analyzer `_POSITIVE`/`_NEGATIVE` sets, ensuring cross-compatibility.

## 7. Validation Strategy

1. **Network-free baseline**: fake-LLM, deterministic, CI-friendly. Validates architecture wiring.
2. **Real-LLM opt-in**: `llm_gateway_factory` parameter, requires API key. Validates LLM behavior. Deferred to post-R99 probe run.
3. **R89 integration**: `evaluate_turing` with emotion probe upgrades `bio_responsiveness` axis. Verified by comparing verdict with/without probe.
4. **Robustness**: empty fixtures, all-positive, all-negative, single fixture — honest absence paths.
