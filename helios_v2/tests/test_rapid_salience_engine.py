from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.appraisal import RapidAppraisalError, RapidSalienceAppraisalEngine
from helios_v2.appraisal.engine import AggregateJudgmentEstimator, RapidDimensionEstimate, RapidDimensionEstimator
from helios_v2.sensory import Stimulus, StimulusBatch


@dataclass
class CountingDimensionEstimator(RapidDimensionEstimator):
    calls: int = 0

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        self.calls += 1
        return RapidDimensionEstimate(
            threat=0.1,
            reward=0.2,
            novelty=0.3,
            social=0.0,
            uncertainty=0.4,
        )


@dataclass
class CountingAggregateEstimator(AggregateJudgmentEstimator):
    calls: int = 0

    def estimate_aggregate(self, stimulus: Stimulus, dimensions: RapidDimensionEstimate) -> float:
        self.calls += 1
        return 0.25


def _build_valid_batch() -> StimulusBatch:
    return StimulusBatch(
        batch_id="stimulus-batch:1:1",
        stimuli=(
            Stimulus(
                stimulus_id="stimulus:cli:001",
                source_name="cli",
                modality="text",
                content="hello",
                channel="cli",
                metadata={"user_id": "u1"},
                provenance_signal_id="001",
            ),
        ),
    )


def test_engine_rejects_malformed_batch_before_estimator_invocation() -> None:
    dimension_estimator = CountingDimensionEstimator()
    aggregate_estimator = CountingAggregateEstimator()
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=dimension_estimator,
        aggregate_estimator=aggregate_estimator,
    )
    malformed_batch = StimulusBatch(
        batch_id="stimulus-batch:broken",
        stimuli=(
            Stimulus(
                stimulus_id="",
                source_name="cli",
                modality="text",
                content="hello",
                channel="cli",
                metadata=None,
                provenance_signal_id="001",
            ),
        ),
    )

    with pytest.raises(RapidAppraisalError, match="StimulusBatch contains stimulus with incomplete provenance"):
        engine.assess_batch(malformed_batch)

    assert dimension_estimator.calls == 0
    assert aggregate_estimator.calls == 0


def test_engine_assesses_valid_batch_with_injected_estimators() -> None:
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=CountingDimensionEstimator(),
        aggregate_estimator=CountingAggregateEstimator(),
    )

    result = engine.assess_batch(_build_valid_batch())

    assert result.batch_id == "rapid-appraisal-batch:stimulus-batch:1:1"
    assert len(result.appraisals) == 1
    assert result.appraisals[0].salience.uncertainty == 0.4
    assert result.appraisals[0].salience.aggregate == 0.25


def test_engine_builds_assess_request_op_from_valid_batch() -> None:
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=CountingDimensionEstimator(),
        aggregate_estimator=CountingAggregateEstimator(),
    )

    op = engine.build_assess_batch_op(_build_valid_batch())

    assert op.op_name == "assess_stimulus_batch"
    assert op.owner == "rapid_salience_appraisal"
    assert op.stimulus_count == 1
    assert op.source_names == ("cli",)


def test_engine_builds_publish_op_from_valid_appraisal_batch() -> None:
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=CountingDimensionEstimator(),
        aggregate_estimator=CountingAggregateEstimator(),
    )
    appraisal_batch = engine.assess_batch(_build_valid_batch())

    op = engine.build_publish_batch_op(appraisal_batch)

    assert op.op_name == "publish_rapid_appraisal_batch"
    assert op.owner == "rapid_salience_appraisal"
    assert op.appraisal_count == 1
    assert op.source_names == ("cli",)


# --- Requirement 35: memory-grounded novelty appraisal ---


from helios_v2.appraisal import MemoryGroundedDimensionEstimator, MemorySimilaritySource


@dataclass
class FixedSimilaritySource(MemorySimilaritySource):
    """Test double returning a fixed max-similarity (or None) as a retrieval fact."""

    similarity: float | None
    calls: int = 0

    def max_similarity_for(self, stimulus: Stimulus) -> float | None:
        self.calls += 1
        return self.similarity


def _stimulus(content: str = "hello") -> Stimulus:
    return Stimulus(
        stimulus_id="stimulus:cli:001",
        source_name="cli",
        modality="text",
        content=content,
        channel="cli",
        metadata=None,
        provenance_signal_id="001",
    )


def test_memory_grounded_estimator_keeps_four_constant_dimensions() -> None:
    estimator = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=0.5))
    estimate = estimator.estimate_dimensions(_stimulus())
    # The four non-novelty dimensions stay at first-version constants.
    assert estimate.threat == 0.2
    assert estimate.reward == 0.1
    assert estimate.social == 0.0
    assert estimate.uncertainty == 0.3


def test_memory_grounded_estimator_maps_high_similarity_to_low_novelty() -> None:
    near = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=0.9))
    far = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=0.1))

    near_novelty = near.estimate_dimensions(_stimulus()).novelty
    far_novelty = far.estimate_dimensions(_stimulus()).novelty

    # novelty = 1 - similarity (the salience mapping is owned by 03).
    assert near_novelty == pytest.approx(0.1)
    assert far_novelty == pytest.approx(0.9)
    assert near_novelty < far_novelty


def test_memory_grounded_estimator_none_similarity_is_max_novelty() -> None:
    estimator = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=None))
    assert estimator.estimate_dimensions(_stimulus()).novelty == 1.0


def test_memory_grounded_estimator_clamps_negative_similarity_to_max_novelty() -> None:
    # An opposite vector (negative cosine) is "unlike anything remembered" -> novelty 1.0.
    estimator = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=-0.5))
    assert estimator.estimate_dimensions(_stimulus()).novelty == 1.0


def test_memory_grounded_estimator_stays_in_unit_range_and_is_deterministic() -> None:
    estimator = MemoryGroundedDimensionEstimator(similarity_source=FixedSimilaritySource(similarity=0.37))
    first = estimator.estimate_dimensions(_stimulus()).novelty
    second = estimator.estimate_dimensions(_stimulus()).novelty
    assert first == second
    assert 0.0 <= first <= 1.0


def test_memory_grounded_estimator_produces_valid_salience_vector_through_engine() -> None:
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=MemoryGroundedDimensionEstimator(
            similarity_source=FixedSimilaritySource(similarity=0.8)
        ),
        aggregate_estimator=CountingAggregateEstimator(),
    )
    result = engine.assess_batch(_build_valid_batch())
    salience = result.appraisals[0].salience
    # Real novelty flows through the unchanged RapidSalienceVector contract.
    assert salience.novelty == pytest.approx(0.2)
    assert 0.0 <= salience.novelty <= 1.0


# --- Requirement 39: memory-grounded uncertainty + transport-grounded social ---


from helios_v2.appraisal import (
    GroundedDimensionEstimator,
    RetrievalAmbiguitySource,
    SocialContextSource,
)


@dataclass
class FixedAmbiguitySource(RetrievalAmbiguitySource):
    """Test double returning a fixed top-N cosine tuple as a retrieval fact."""

    similarities: tuple[float, ...] = ()

    def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
        return self.similarities


@dataclass
class FixedSocialSource(SocialContextSource):
    """Test double returning a fixed social-presence transport fact."""

    presence: float = 0.0

    def social_presence_for(self, stimulus: Stimulus) -> float:
        return self.presence


def _grounded(
    *,
    similarity: float | None = 0.5,
    similarities: tuple[float, ...] = (),
    presence: float = 0.0,
) -> GroundedDimensionEstimator:
    return GroundedDimensionEstimator(
        similarity_source=FixedSimilaritySource(similarity=similarity),
        ambiguity_source=FixedAmbiguitySource(similarities=similarities),
        social_source=FixedSocialSource(presence=presence),
    )


def test_grounded_estimator_unique_match_yields_low_uncertainty() -> None:
    # One dominant match (high top1, low top2) -> small (1 - margin) -> low uncertainty.
    estimate = _grounded(similarities=(0.9, -0.8)).estimate_dimensions(_stimulus())
    # n1 = 0.95, n2 = 0.10, margin = 0.85 -> uncertainty = 0.15
    assert estimate.uncertainty == pytest.approx(0.15)


def test_grounded_estimator_near_equal_matches_yield_high_uncertainty() -> None:
    # Several near-equal matches (top1 ~ top2) -> margin ~ 0 -> uncertainty ~ 1.
    estimate = _grounded(similarities=(0.8, 0.78)).estimate_dimensions(_stimulus())
    # n1 = 0.90, n2 = 0.89, margin = 0.01 -> uncertainty = 0.99
    assert estimate.uncertainty == pytest.approx(0.99)


def test_grounded_estimator_no_hits_is_max_uncertainty() -> None:
    estimate = _grounded(similarities=()).estimate_dimensions(_stimulus())
    assert estimate.uncertainty == 1.0


def test_grounded_estimator_single_hit_uses_zero_second_margin() -> None:
    # Only one hit -> n2 = 0.0; uncertainty = 1 - n1.
    estimate = _grounded(similarities=(0.6,)).estimate_dimensions(_stimulus())
    # n1 = 0.80 -> uncertainty = 0.20
    assert estimate.uncertainty == pytest.approx(0.20)


def test_grounded_estimator_novelty_and_uncertainty_are_distinct_signals() -> None:
    # Familiar but ambiguous: the stimulus strongly matches several stored experiences about
    # equally -> low novelty (top-1 high) yet high uncertainty (top1 ~ top2).
    estimate = _grounded(similarity=0.9, similarities=(0.9, 0.88)).estimate_dimensions(_stimulus())
    assert estimate.novelty == pytest.approx(0.1)  # 1 - 0.9
    # n1 = 0.95, n2 = 0.94, margin = 0.01 -> uncertainty = 0.99
    assert estimate.uncertainty == pytest.approx(0.99)
    assert estimate.uncertainty > estimate.novelty


def test_grounded_estimator_high_social_presence_raises_social() -> None:
    high = _grounded(presence=1.0).estimate_dimensions(_stimulus()).social
    low = _grounded(presence=0.0).estimate_dimensions(_stimulus()).social

    assert high > low
    assert high == pytest.approx(1.0)  # social_floor 0 + social_gain 1 * 1.0
    assert low == pytest.approx(0.0)


def test_grounded_estimator_keeps_threat_and_reward_constant() -> None:
    estimate = _grounded(similarities=(0.5, 0.4), presence=1.0).estimate_dimensions(_stimulus())
    assert estimate.threat == 0.2
    assert estimate.reward == 0.1


def test_grounded_estimator_dimensions_within_range_and_deterministic() -> None:
    estimator = _grounded(similarity=0.37, similarities=(0.7, 0.2), presence=0.5)
    first = estimator.estimate_dimensions(_stimulus())
    second = estimator.estimate_dimensions(_stimulus())

    assert first == second
    for dimension in ("threat", "reward", "novelty", "social", "uncertainty"):
        value = getattr(first, dimension)
        assert 0.0 <= value <= 1.0


def test_grounded_estimator_empty_content_path_through_real_sources() -> None:
    # With real-style sources that return "no comparable memory" for empty content, both novelty
    # and uncertainty saturate to 1.0 (the cold/empty maxima), consistent with R35.
    estimate = _grounded(similarity=None, similarities=()).estimate_dimensions(_stimulus(content=""))
    assert estimate.novelty == 1.0
    assert estimate.uncertainty == 1.0


def test_grounded_estimator_produces_valid_salience_vector_through_engine() -> None:
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=_grounded(similarity=0.8, similarities=(0.8, 0.2), presence=1.0),
        aggregate_estimator=CountingAggregateEstimator(),
    )
    salience = engine.assess_batch(_build_valid_batch()).appraisals[0].salience
    assert salience.novelty == pytest.approx(0.2)
    assert 0.0 <= salience.uncertainty <= 1.0
    assert salience.social == pytest.approx(1.0)
