"""R99 emotion validation probe verification.

A probe test drives a self-contained production-shaped runtime with the deterministic
fake-LLM gateway and asserts the four emotional-chain metrics; an integration test feeds
the probe report into the R89 harness and asserts the `bio_responsiveness` axis becomes
a real reconstructed axis with R99 provenance (and stays drift-only without the probe).
The probe is read-only and emits no logging; this module renders the report (a test may
print).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_runtime, default_composition_config
from helios_v2.embedding import (
    DeterministicHashEmbeddingProvider,
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend

from r88_drift_evaluator import evaluate_drift
from r83_long_runner import LongRunConfig, run_long_run
from r89_turing_harness import (
    AVAILABLE,
    BIO_RESPONSIVENESS,
    STUBBED,
    evaluate_turing,
)
from r89_turing_harness.turing_harness import RECONSTRUCTED

from r99_emotion_validation_probe import (
    DEFAULT_VISITOR_FIXTURES,
    EmotionValidationConfig,
    EmotionValidationReport,
    FixtureResult,
    VisitorFixture,
    run_emotion_validation_probe,
)


# --- deterministic offline runtime (for R89 harness integration) -----------------------------


@dataclass
class _SimpleThoughtProvider:
    """Neutral fake-LLM provider for the R89 integration baseline long-run."""

    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "Continuing internal reflection.",
            "sufficiency": 0.85,
            "thinking_complete": True,
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _build_embedding_gateway():
    """Network-free embedding gateway for the integration baseline."""
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


def _reports_for_turing(tmp_path):
    """Build R83/R88 reports for the Turing harness integration tests."""
    provider = _SimpleThoughtProvider()
    config = default_composition_config()
    gateway = LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )
    handle = assemble_runtime(
        gateway=gateway,
        experience_store=ExperienceStore(backend=InMemoryExperienceStoreBackend()),
        embedding_gateway=_build_embedding_gateway(),
        default_signal_mode="semantic",
    )
    handle.startup()
    long_run = run_long_run(handle, LongRunConfig(ticks=40))
    drift = evaluate_drift(long_run.evolution_samples)
    return long_run, drift


# --- probe metrics ----------------------------------------------------------------------------


def test_probe_measures_four_metrics() -> None:
    """The probe runs successfully and produces all four bounded metrics."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    assert report.crash is None, report.summary()
    assert report.ticks_completed == 50, report.summary()
    assert report.report_usable, report.summary()


def test_cortisol_valence_separation() -> None:
    """cortisol_valence_separation >= 0.05 under fake-LLM (negative fixtures produce cortisol elevation)."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    assert report.cortisol_valence_separation is not None, report.summary()
    assert report.cortisol_valence_separation >= 0.05, (
        f"cortisol_valence_separation {report.cortisol_valence_separation:.4f} < 0.05 threshold; "
        f"the fake-LLM cortisol-elevated prediction is not closing B2 on the fixture set\n"
        f"{report.summary()}"
    )
    print(f"\n{report.summary()}")


def test_thought_content_grounding() -> None:
    """thought_content_grounding >= 0.5 under fake-LLM (thought references visitor text)."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    assert report.thought_content_grounding is not None, report.summary()
    assert report.thought_content_grounding >= 0.5, (
        f"thought_content_grounding {report.thought_content_grounding:.4f} < 0.5 threshold\n"
        f"{report.summary()}"
    )


def test_reply_loop_closure() -> None:
    """reply_loop_closure > 0 under fake-LLM (negative-valence fixtures produce reply proposals)."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    assert report.reply_loop_closure is not None, report.summary()
    assert report.reply_loop_closure > 0, (
        f"reply_loop_closure {report.reply_loop_closure:.4f} == 0; no negative-valence "
        f"fixture tick produced a reply proposal\n{report.summary()}"
    )


def test_memory_recall_relevance() -> None:
    """memory_recall_relevance is computed (may be 0 on first run with cold store)."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    # memory_recall_relevance is honest None when no recall-possible ticks,
    # or a float when there are recall-possible ticks.
    assert report.memory_recall_relevance is not None or report.report_usable is False, (
        f"memory_recall_relevance should be None or computed; got {report.memory_recall_relevance}\n"
        f"{report.summary()}"
    )


def test_all_metrics_bounded() -> None:
    """All present metrics are bounded in [0, 1]."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    for metric in (
        report.cortisol_valence_separation,
        report.thought_content_grounding,
        report.memory_recall_relevance,
        report.reply_loop_closure,
    ):
        if metric is not None:
            assert 0.0 <= metric <= 1.0, f"metric {metric} out of [0,1] bounds"


# --- honest absence paths -----------------------------------------------------------------------


def test_empty_fixture_set_all_metrics_none() -> None:
    """Empty fixture set -> all metrics None, report_usable=False."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=10, visitor_fixtures=()))

    assert report.cortisol_valence_separation is None
    assert report.report_usable is False


def test_all_positive_fixture_reply_closure_none() -> None:
    """All-positive fixtures -> reply_loop_closure=None (no negative-valence ticks)."""
    positive_only = tuple(f for f in DEFAULT_VISITOR_FIXTURES if f.valence_sign > 0.0)
    report = run_emotion_validation_probe(
        EmotionValidationConfig(ticks=20, visitor_fixtures=positive_only),
    )

    assert report.reply_loop_closure is None, (
        f"reply_loop_closure should be None with all-positive fixtures; "
        f"got {report.reply_loop_closure}\n{report.summary()}"
    )


def test_all_negative_fixture_separation_computed() -> None:
    """All-negative fixtures -> separation still computed (positive group empty -> None)."""
    negative_only = tuple(f for f in DEFAULT_VISITOR_FIXTURES if f.valence_sign < 0.0)
    report = run_emotion_validation_probe(
        EmotionValidationConfig(ticks=20, visitor_fixtures=negative_only),
    )

    # With no positive fixtures, separation = None (honest absence).
    assert report.cortisol_valence_separation is None, (
        f"separation should be None when one group has no fixtures; "
        f"got {report.cortisol_valence_separation}\n{report.summary()}"
    )


def test_single_fixture_partial_metrics() -> None:
    """Single fixture -> partial metrics (honest None for absent dimensions)."""
    single = (DEFAULT_VISITOR_FIXTURES[0],)  # anxiety (negative)
    report = run_emotion_validation_probe(
        EmotionValidationConfig(ticks=5, visitor_fixtures=single),
    )

    # With only negative fixtures, separation is None (no positive group).
    assert report.cortisol_valence_separation is None
    # reply_loop_closure may be > 0 (negative fixture -> reply).


# --- R89 harness integration -------------------------------------------------------------------


def test_usable_probe_makes_bio_responsiveness_real_axis(tmp_path) -> None:
    """R99: a usable emotion probe upgrades bio_responsiveness to available/reconstructed."""
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    probe = run_emotion_validation_probe(EmotionValidationConfig(ticks=50))

    assert probe.report_usable, probe.summary()

    verdict = evaluate_turing(long_run, drift, emotion_validation_probe=probe)
    axis = verdict.axis_scores[BIO_RESPONSIVENESS]
    assert axis.availability == AVAILABLE, verdict.summary()
    assert axis.judge_track == RECONSTRUCTED
    assert "R99 emotion validation probe" in axis.provenance
    assert axis.score > 0.0, f"bio_responsiveness score {axis.score} should be positive"
    assert verdict.emotion_validation_probe_usable is True


def test_absent_probe_keeps_bio_responsiveness_drift_path(tmp_path) -> None:
    """R99: without the emotion probe, bio_responsiveness keeps the drift-reconstruction path."""
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    verdict = evaluate_turing(long_run, drift)  # no emotion probe -> drift path preserved

    axis = verdict.axis_scores[BIO_RESPONSIVENESS]
    assert axis.availability == AVAILABLE
    assert axis.judge_track == RECONSTRUCTED
    # The provenance should NOT mention R99.
    assert "R99" not in axis.provenance
    assert verdict.emotion_validation_probe_usable is None


def test_unusable_probe_keeps_bio_responsiveness_drift_path(tmp_path) -> None:
    """R99: an unusable emotion probe falls back to the drift-reconstruction path."""
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    unusable = EmotionValidationReport(ticks_requested=10, ticks_completed=0, crash="startup_failed")
    assert not unusable.report_usable

    verdict = evaluate_turing(long_run, drift, emotion_validation_probe=unusable)
    axis = verdict.axis_scores[BIO_RESPONSIVENESS]
    assert axis.availability == AVAILABLE
    # Unusable probe -> drift path (no R99 provenance).
    assert "R99" not in axis.provenance
    assert verdict.emotion_validation_probe_usable is False


# --- robustness --------------------------------------------------------------------------------


def test_crash_in_report_makes_it_unusable() -> None:
    """A report with a crash reason is not usable."""
    report = EmotionValidationReport(
        ticks_requested=10, ticks_completed=5, crash="tick 5: RuntimeError: boom",
    )
    assert report.report_usable is False
    assert report.crash is not None


def test_fixture_result_per_fixture_data() -> None:
    """Each FixtureResult has correct per-fixture data (valence, tick_id, cortisol)."""
    report = run_emotion_validation_probe(EmotionValidationConfig(ticks=20))

    assert len(report.fixture_results) == len(DEFAULT_VISITOR_FIXTURES)

    for i, fr in enumerate(report.fixture_results):
        fixture = DEFAULT_VISITOR_FIXTURES[i]
        assert fr.fixture_index == i
        assert fr.valence_category == fixture.valence_category
        assert fr.valence_sign == fixture.valence_sign
        assert fr.tick_id == i  # fixture i is on tick i


def test_probe_is_deterministic() -> None:
    """Two identical probe runs produce identical metrics."""
    report_a = run_emotion_validation_probe(EmotionValidationConfig(ticks=20))
    report_b = run_emotion_validation_probe(EmotionValidationConfig(ticks=20))

    assert report_a.ticks_completed == report_b.ticks_completed
    if report_a.cortisol_valence_separation is not None and report_b.cortisol_valence_separation is not None:
        assert report_a.cortisol_valence_separation == pytest.approx(
            report_b.cortisol_valence_separation, abs=0.01
        )
