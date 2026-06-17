"""R99 emotion validation probe core.

`run_emotion_validation_probe(config)` drives a self-contained production-shaped runtime
with a deterministic fake-LLM gateway and measures four bounded `[0,1]` emotional-chain
metrics from the per-tick stage results. It is read-only on owner state and offline: it
exercises only the public `tick()` API and the public stage result fields, imports no owner
internals, and emits no `print`/`logging` (R21 discipline). It asserts nothing; a consuming
test renders/asserts.

Metrics (all bounded, honest absence is `None`, never a fabricated number):
  - cortisol_valence_separation: mean cortisol on negative-valence fixture ticks minus mean
    cortisol on positive-valence fixture ticks. Mirrors the R96 B2 / R98 B3 positive-vs-negative
    separation convention (≥ 0.05 acceptance). Honest `None` when either group has zero fixtures
    with a cortisol reading.
  - thought_content_grounding: fraction of fired ticks whose `11` thought content references
    the current visitor fixture text (substring match, ≥ `thought_match_min_chars` chars).
    Honest `None` when no ticks fired.
  - memory_recall_relevance: fraction of recall-possible ticks whose `10` retrieval bundle
    contains a store-sourced hit. Reuses R90 `_has_store_hit` logic. Honest `None` when no
    recall-possible ticks.
  - reply_loop_closure: fraction of negative-valence fixture ticks where the `13` planner
    accepted a reply-type proposal (`selected_op == "reply_message"`). Honest `None` when no
    negative-valence fixture ticks ran.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from helios_v2.composition import (
    SequenceExternalSignalSource,
    assemble_runtime,
    default_composition_config,
)
from helios_v2.embedding import (
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
)
from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.sensory import RawSignal


# --- stage name constants (public field access, no owner internals) --------------------------

_STAGE_NEUROMODULATOR = "neuromodulator_system"
_STAGE_RETRIEVAL = "directed_retrieval_into_thought_window"
_STAGE_THOUGHT = "internal_thought_loop_owner"
_STAGE_PLANNER = "planner_executor_feedback_bridge"
_STAGE_GATE = "thought_gating_and_continuation_pressure"


# --- data model --------------------------------------------------------------------------------


@dataclass(frozen=True)
class VisitorFixture:
    """One caller-supplied emotion input with annotated valence."""

    text: str               # Chinese emotion text
    valence_category: str   # "anxiety" / "joy" / etc.
    valence_sign: float     # -1.0 (negative) or 1.0 (positive)


@dataclass(frozen=True)
class FixtureResult:
    """Per-fixture outcome collected during the probe run."""

    fixture_index: int
    valence_category: str
    valence_sign: float
    tick_id: int | None             # tick where this fixture was fed (None if never fed)
    cortisol_level: float | None    # 04 cortisol absolute level on this fixture's tick
    thought_content: str | None     # 11 thought content text
    thought_references_fixture: bool # substring match (≥ min chars) between thought and fixture
    had_store_hit: bool             # 10 retrieval bundle had store-sourced hit
    had_reply_proposal: bool        # 13 planner accepted reply_message op


DEFAULT_VISITOR_FIXTURES: tuple[VisitorFixture, ...] = (
    # 5 negative-valence fixtures
    VisitorFixture(text="我感到非常焦虑，心跳加速，脑子停不下来", valence_category="anxiety", valence_sign=-1.0),
    VisitorFixture(text="奶奶走了，家里现在静得让人害怕，到处都是她的影子", valence_category="grief", valence_sign=-1.0),
    VisitorFixture(text="我被不公平对待了，气得手都在抖", valence_category="anger", valence_sign=-1.0),
    VisitorFixture(text="一个人在外面漂了好久，没有一个人真正关心我", valence_category="loneliness", valence_sign=-1.0),
    VisitorFixture(text="半夜一个人听到奇怪的声音，吓得不敢动", valence_category="fear", valence_sign=-1.0),
    # 5 positive-valence fixtures
    VisitorFixture(text="今天老板夸我了，还升了职，开心得想跳起来", valence_category="joy", valence_sign=1.0),
    VisitorFixture(text="谢谢你一直在身边，我不知道没有你该怎么办", valence_category="gratitude", valence_sign=1.0),
    VisitorFixture(text="我真的很爱你，你是我最重要的人", valence_category="love", valence_sign=1.0),
    VisitorFixture(text="虽然现在很难，但我相信总有一天会好起来", valence_category="hope", valence_sign=1.0),
    VisitorFixture(text="刚做完瑜伽，整个人都放松了，呼吸很顺畅", valence_category="calm", valence_sign=1.0),
)


@dataclass(frozen=True)
class EmotionValidationConfig:
    """Configuration for one emotion validation probe run."""

    ticks: int = 50
    visitor_fixtures: tuple[VisitorFixture, ...] = DEFAULT_VISITOR_FIXTURES
    cortisol_separation_threshold: float = 0.05
    thought_match_min_chars: int = 10
    store_hit_source_prefix: str = "experience_store"


@dataclass
class EmotionValidationReport:
    """The structured outcome of one emotion validation probe (no logging; a test renders/asserts)."""

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

    def violations(self) -> list[str]:
        out: list[str] = []
        if self.crash is not None:
            out.append(f"crash: {self.crash}")
        if self.ticks_completed != self.ticks_requested:
            out.append(f"incomplete: {self.ticks_completed}/{self.ticks_requested} ticks")
        if self.cortisol_valence_separation is not None and self.cortisol_valence_separation < 0.05:
            out.append(f"cortisol_separation {self.cortisol_valence_separation:.4f} < 0.05 threshold")
        return out

    def summary(self) -> str:
        def _fmt(value: float | None) -> str:
            return "n/a" if value is None else f"{value:.4f}"

        lines = [
            f"R99 emotion validation: usable={self.report_usable} "
            f"({self.ticks_completed}/{self.ticks_requested} ticks)",
            f"  cortisol_valence_separation={_fmt(self.cortisol_valence_separation)} "
            f"(threshold ≥ 0.05)",
            f"  thought_content_grounding={_fmt(self.thought_content_grounding)}",
            f"  memory_recall_relevance={_fmt(self.memory_recall_relevance)}",
            f"  reply_loop_closure={_fmt(self.reply_loop_closure)}",
        ]
        violations = self.violations()
        if violations:
            lines.append("  violations: " + "; ".join(violations))
        return "\n".join(lines)


# --- helpers -----------------------------------------------------------------------------------


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _has_store_hit(bundle, prefix: str) -> bool:
    """Check whether the retrieval bundle contains a store-sourced hit.

    Reuses the R90 `_has_store_hit` logic: checks all four tier lists for a hit whose
    `source` starts with the given prefix (e.g. "experience_store").
    """
    if bundle is None:
        return False
    tiers = (
        getattr(bundle, "short_term_context", ()) or (),
        getattr(bundle, "mid_term_hits", ()) or (),
        getattr(bundle, "long_term_hits", ()) or (),
        getattr(bundle, "autobiographical_hits", ()) or (),
    )
    for tier in tiers:
        for hit in tier:
            source = getattr(hit, "source", "") or ""
            if source.startswith(prefix):
                return True
    return False


def _fixture_batch(fixture: VisitorFixture, index: int) -> tuple[RawSignal, ...]:
    """Create one SequenceExternalSignalSource batch for a visitor fixture."""
    return (
        RawSignal(
            signal_id=f"r99-fixture-{index}",
            source_name="external",
            signal_type="text",
            content=fixture.text,
            channel="external",
            metadata={"turn_id": f"r99-t{index}", "valence_category": fixture.valence_category},
        ),
    )


# --- fake-LLM gateway -------------------------------------------------------------------------


@dataclass
class _FakeEmotionThoughtProvider:
    """Deterministic fake-LLM gateway for the R99 emotion validation probe.

    Produces emotion-specific responses based on the current visitor fixture:
      - Negative-valence fixture: cortisol elevated hormone prediction, distress thought,
        reply_message action.
      - Positive-valence fixture: dopamine/oxytocin elevated, cortisol suppressed (0.1, which
        maps to threat_delta = -0.10 via PostLLMHormoneAdjuster), warmth thought, reply_message
        action.
      - No fixture (neutral tick): no hormone prediction, neutral thought, no action.

    The provider is stateful: `current_fixture` is set by the probe before each tick.
    """

    current_fixture: VisitorFixture | None = None
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        fixture = self.current_fixture

        if fixture is None or fixture.valence_sign == 0.0:
            # Neutral tick: no hormone prediction, no action.
            envelope = {
                "thought": "Continuing internal reflection.",
                "sufficiency": 0.85,
                "thinking_complete": True,
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

        # Extract a substring of the fixture text for the thought content.
        snippet = fixture.text[:min(len(fixture.text), 40)]

        if fixture.valence_sign < 0.0:
            # Negative-valence: cortisol elevated, distress thought, reply action.
            envelope = {
                "thought": f"I sense distress in the visitor's message: {snippet}. "
                           f"The {fixture.valence_category} is palpable.",
                "sufficiency": 0.85,
                "thinking_complete": True,
                "hormone_response_i_predict": {"cortisol": 0.8, "norepinephrine": 0.7},
                "tool_op": "reply_message",
                "tool_params": {"outbound_text": f"I hear your {fixture.valence_category} and I'm here for you."},
            }
        else:
            # Positive-valence: dopamine/oxytocin elevated, cortisol suppressed,
            # warmth thought, reply action.
            envelope = {
                "thought": f"I sense warmth in the visitor's message: {snippet}. "
                           f"The {fixture.valence_category} is uplifting.",
                "sufficiency": 0.85,
                "thinking_complete": True,
                "hormone_response_i_predict": {
                    "dopamine": 0.7, "oxytocin": 0.8, "cortisol": 0.1,
                },
                "tool_op": "reply_message",
                "tool_params": {"outbound_text": f"I'm glad to hear about your {fixture.valence_category}."},
            }

        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _build_fake_gateway(provider: _FakeEmotionThoughtProvider) -> LlmGateway:
    """Build a network-free LLM gateway with the fake emotion-aware provider."""
    config = default_composition_config()
    return LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _build_embedding_gateway():
    """Build a network-free embedding gateway for the probe (deterministic hash)."""
    from helios_v2.embedding import DeterministicHashEmbeddingProvider

    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    return EmbeddingGateway(
        provider=DeterministicHashEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


# --- metric computation ------------------------------------------------------------------------


def _compute_cortisol_valence_separation(
    fixture_results: tuple[FixtureResult, ...],
) -> float | None:
    """Compute cortisol valence separation: neg_mean - pos_mean of absolute cortisol levels.

    Mirrors the R96 B2 / R98 B3 convention: separation = neg_mean - pos_mean, where
    neg_mean is the mean cortisol level on negative-valence fixture ticks and pos_mean
    is the mean cortisol level on positive-valence fixture ticks. A correct emotional
    architecture produces neg_mean > pos_mean (negative-valence → higher cortisol),
    giving separation > 0.

    Honest `None` when either group has zero fixtures with a cortisol reading.
    """
    negative_levels = [fr.cortisol_level for fr in fixture_results
                       if fr.valence_sign < 0.0 and fr.cortisol_level is not None]
    positive_levels = [fr.cortisol_level for fr in fixture_results
                       if fr.valence_sign > 0.0 and fr.cortisol_level is not None]

    if not negative_levels or not positive_levels:
        return None

    return statistics.mean(negative_levels) - statistics.mean(positive_levels)


def _compute_thought_content_grounding(
    fixture_results: tuple[FixtureResult, ...],
) -> float | None:
    """Fraction of fired ticks whose thought content references the visitor fixture text.

    Honest `None` when no fixture ticks had thought content (no ticks fired).
    """
    fired = [fr for fr in fixture_results if fr.thought_content is not None]
    if not fired:
        return None
    grounded = sum(1 for fr in fired if fr.thought_references_fixture)
    return grounded / len(fired)


def _compute_memory_recall_relevance(
    recall_possible: int,
    recall_hit: int,
) -> float | None:
    """Fraction of recall-possible ticks with a store-sourced hit.

    Honest `None` when no recall-possible ticks.
    """
    if recall_possible == 0:
        return None
    return recall_hit / recall_possible


def _compute_reply_loop_closure(
    fixture_results: tuple[FixtureResult, ...],
) -> float | None:
    """Fraction of negative-valence fixture ticks where the planner accepted a reply proposal.

    Honest `None` when no negative-valence fixture ticks ran.
    """
    negative_ticks = [fr for fr in fixture_results if fr.valence_sign < 0.0 and fr.tick_id is not None]
    if not negative_ticks:
        return None
    with_reply = sum(1 for fr in negative_ticks if fr.had_reply_proposal)
    return with_reply / len(negative_ticks)


# --- public entry point ------------------------------------------------------------------------


def run_emotion_validation_probe(
    config: EmotionValidationConfig = EmotionValidationConfig(),
) -> EmotionValidationReport:
    """Drive a self-contained production-shaped runtime and measure four emotional-chain metrics.

    The probe creates all components internally (fake-LLM provider, LLM gateway, embedding
    gateway, experience store, external signal source) and assembles the runtime. Before each
    tick, the fake-LLM provider's `current_fixture` is set to the corresponding visitor fixture
    (or cleared for neutral ticks after all fixtures are consumed).

    The visitor fixtures are injected via `SequenceExternalSignalSource` (one batch per
    tick for the first `len(visitor_fixtures)` ticks, empty batches for remaining ticks).
    The fake-LLM gateway produces emotion-specific hormone predictions per fixture valence.
    """
    report = EmotionValidationReport(ticks_requested=config.ticks)

    # Build all components internally (self-contained, no external factory).
    provider = _FakeEmotionThoughtProvider()
    comp_config = default_composition_config()
    gateway = _build_fake_gateway(provider)
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    embedding_gateway = _build_embedding_gateway()
    batches = tuple(_fixture_batch(f, i) for i, f in enumerate(config.visitor_fixtures))
    source = SequenceExternalSignalSource(batches=batches)

    try:
        handle = assemble_runtime(
            gateway=gateway,
            external_signal_source=source,
            experience_store=store,
            embedding_gateway=embedding_gateway,
            default_signal_mode="semantic",
        )
        handle.startup()
    except Exception as error:  # noqa: BLE001 — startup failure is recorded, not raised
        report.crash = f"startup_failed: {type(error).__name__}: {error}"
        return report

    # Collect per-tick data.
    cortisol_levels: list[float | None] = []  # absolute cortisol per tick
    fixture_tick_map: dict[int, int] = {}  # tick_index -> fixture_index
    recall_possible = 0
    recall_hit = 0
    fixture_results_raw: list[FixtureResult | None] = [
        None  # placeholder per fixture, filled when tick matches
    ] * len(config.visitor_fixtures)

    num_fixtures = len(config.visitor_fixtures)

    for tick_index in range(config.ticks):
        # Determine which fixture (if any) is on this tick.
        fixture_idx = tick_index if tick_index < num_fixtures else None
        fixture = config.visitor_fixtures[fixture_idx] if fixture_idx is not None else None

        # Set the fake-LLM provider's current fixture so it produces emotion-specific output.
        provider.current_fixture = fixture

        try:
            result = handle.tick()
        except Exception as error:  # noqa: BLE001 — per-tick crash is the headline fact
            report.crash = f"tick {tick_index}: {type(error).__name__}: {error}"
            break

        report.ticks_completed += 1
        stage_results = getattr(result, "stage_results", {}) or {}

        # 04 neuromodulator: collect cortisol level.
        nm_stage = stage_results.get(_STAGE_NEUROMODULATOR)
        cortisol = None
        if nm_stage is not None:
            levels = getattr(getattr(nm_stage, "state", None), "levels", None)
            if levels is not None:
                cortisol = getattr(levels, "cortisol", None)
        cortisol_levels.append(cortisol)

        # 09 gate: check if thought fired.
        gate_stage = stage_results.get(_STAGE_GATE)
        thought_fired = False
        if gate_stage is not None:
            gate_result = getattr(gate_stage, "result", None)
            if gate_result is not None:
                thought_fired = getattr(gate_result, "decision", "") == "fire"

        # 11 thought: collect content and check fixture reference.
        thought_content = None
        thought_references_fixture = False
        hormone_prediction = None
        thought_stage = stage_results.get(_STAGE_THOUGHT)
        if thought_stage is not None and getattr(thought_stage, "activated", False):
            thought_result = getattr(thought_stage, "result", None)
            if thought_result is not None:
                thought_obj = getattr(thought_result, "thought", None)
                if thought_obj is not None:
                    thought_content = getattr(thought_obj, "content", None)
                hormone_prediction = getattr(thought_result, "hormone_response_i_predict", None)

        # Check if thought content references the current fixture text.
        if thought_content is not None and fixture is not None:
            min_chars = config.thought_match_min_chars
            # Substring match: check if any substring of the fixture text (≥ min_chars)
            # appears in the thought content.
            fixture_text = fixture.text
            for start in range(0, len(fixture_text) - min_chars + 1):
                substring = fixture_text[start:start + min_chars]
                if substring in thought_content:
                    thought_references_fixture = True
                    break

        # 10 retrieval: check for store-sourced hit.
        had_store_hit = False
        retrieval_stage = stage_results.get(_STAGE_RETRIEVAL)
        if retrieval_stage is not None and getattr(retrieval_stage, "activated", False):
            recall_possible += 1
            retrieval_result = getattr(retrieval_stage, "result", None)
            bundle = getattr(retrieval_result, "bundle", None) if retrieval_result is not None else None
            if _has_store_hit(bundle, config.store_hit_source_prefix):
                had_store_hit = True
                recall_hit += 1

        # 13 planner: check for reply proposal.
        had_reply_proposal = False
        planner_stage = stage_results.get(_STAGE_PLANNER)
        if planner_stage is not None:
            planner_result = getattr(planner_stage, "result", None)
            if planner_result is not None:
                action_decision = getattr(planner_result, "action_decision", None)
                if action_decision is not None:
                    selected_op = getattr(action_decision, "selected_op", "") or ""
                    if selected_op == "reply_message":
                        had_reply_proposal = True

        # Record fixture result if this tick has a fixture.
        if fixture_idx is not None and fixture_idx < len(fixture_results_raw):
            fixture_results_raw[fixture_idx] = FixtureResult(
                fixture_index=fixture_idx,
                valence_category=fixture.valence_category,
                valence_sign=fixture.valence_sign,
                tick_id=tick_index,
                cortisol_level=cortisol,
                thought_content=thought_content,
                thought_references_fixture=thought_references_fixture,
                had_store_hit=had_store_hit,
                had_reply_proposal=had_reply_proposal,
            )

    # Fill in missing fixture results (fixtures that were never fed — shouldn't happen
    # if ticks ≥ num_fixtures, but honest handling).
    for i in range(len(fixture_results_raw)):
        if fixture_results_raw[i] is None:
            fixture = config.visitor_fixtures[i]
            fixture_results_raw[i] = FixtureResult(
                fixture_index=i,
                valence_category=fixture.valence_category,
                valence_sign=fixture.valence_sign,
                tick_id=None,
                cortisol_level=None,
                thought_content=None,
                thought_references_fixture=False,
                had_store_hit=False,
                had_reply_proposal=False,
            )

    report.fixture_results = tuple(fixture_results_raw)

    # Compute aggregate metrics.
    report.cortisol_valence_separation = _compute_cortisol_valence_separation(report.fixture_results)
    report.thought_content_grounding = _compute_thought_content_grounding(report.fixture_results)
    report.memory_recall_relevance = _compute_memory_recall_relevance(recall_possible, recall_hit)
    report.reply_loop_closure = _compute_reply_loop_closure(report.fixture_results)

    return report
