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


@dataclass
class FixedPrototypeSource:
    """Test double returning a fixed max-cosine (or None) for any prototype set."""

    similarity: float | None = 0.0

    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        return self.similarity


def _grounded(
    *,
    similarity: float | None = 0.5,
    similarities: tuple[float, ...] = (),
    presence: float = 0.0,
    prototype_similarity: float | None = 0.0,
) -> GroundedDimensionEstimator:
    return GroundedDimensionEstimator(
        similarity_source=FixedSimilaritySource(similarity=similarity),
        ambiguity_source=FixedAmbiguitySource(similarities=similarities),
        social_source=FixedSocialSource(presence=presence),
        prototype_source=FixedPrototypeSource(similarity=prototype_similarity),
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


def test_grounded_estimator_threat_and_reward_from_prototype_similarity() -> None:
    # R40: threat/reward are prototype-derived, positive-correlation, not constants.
    high = _grounded(prototype_similarity=0.9).estimate_dimensions(_stimulus())
    low = _grounded(prototype_similarity=0.1).estimate_dimensions(_stimulus())

    assert high.threat == pytest.approx(0.9)  # gain 1.0 * max(0, 0.9)
    assert high.reward == pytest.approx(0.9)
    assert high.threat > low.threat
    assert high.reward > low.reward


def test_grounded_estimator_threat_reward_negative_similarity_is_zero() -> None:
    # Only positive similarity contributes; an anti-similar stimulus scores 0 (not negative).
    estimate = _grounded(prototype_similarity=-0.7).estimate_dimensions(_stimulus())
    assert estimate.threat == 0.0
    assert estimate.reward == 0.0


def test_grounded_estimator_threat_reward_none_fact_is_zero() -> None:
    # No comparable input (empty content) -> threat/reward 0.0.
    estimate = _grounded(prototype_similarity=None).estimate_dimensions(_stimulus())
    assert estimate.threat == 0.0
    assert estimate.reward == 0.0


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


# --- Requirement 41: dimension-grounded aggregate salience judgment ---


from helios_v2.appraisal import WeightedAggregateEstimator


def _dims(
    *,
    threat: float = 0.0,
    reward: float = 0.0,
    novelty: float = 0.0,
    social: float = 0.0,
    uncertainty: float = 0.0,
) -> RapidDimensionEstimate:
    return RapidDimensionEstimate(
        threat=threat,
        reward=reward,
        novelty=novelty,
        social=social,
        uncertainty=uncertainty,
    )


def test_weighted_aggregate_equals_convex_combination() -> None:
    estimator = WeightedAggregateEstimator()
    dims = _dims(threat=1.0, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0)
    # Only the threat weight contributes -> 0.25.
    assert estimator.estimate_aggregate(_stimulus(), dims) == pytest.approx(0.25)

    full = _dims(threat=1.0, reward=1.0, novelty=1.0, social=1.0, uncertainty=1.0)
    # Weights sum to 1.0 -> all dimensions at 1.0 -> aggregate 1.0.
    assert estimator.estimate_aggregate(_stimulus(), full) == pytest.approx(1.0)


def test_weighted_aggregate_weights_sum_to_one() -> None:
    e = WeightedAggregateEstimator()
    total = e.weight_threat + e.weight_reward + e.weight_novelty + e.weight_uncertainty + e.weight_social
    assert total == pytest.approx(1.0)


def test_weighted_aggregate_is_monotonic_in_each_dimension() -> None:
    estimator = WeightedAggregateEstimator()
    base = _dims(threat=0.3, reward=0.3, novelty=0.3, social=0.3, uncertainty=0.3)
    base_value = estimator.estimate_aggregate(_stimulus(), base)
    for dimension in ("threat", "reward", "novelty", "social", "uncertainty"):
        raised = estimator.estimate_aggregate(_stimulus(), _dims(**{**{
            "threat": 0.3, "reward": 0.3, "novelty": 0.3, "social": 0.3, "uncertainty": 0.3
        }, dimension: 0.9}))
        assert raised >= base_value


def test_weighted_aggregate_high_salience_exceeds_low_salience() -> None:
    estimator = WeightedAggregateEstimator()
    high = estimator.estimate_aggregate(
        _stimulus(), _dims(threat=0.9, reward=0.8, novelty=0.9, social=0.7, uncertainty=0.8)
    )
    low = estimator.estimate_aggregate(
        _stimulus(), _dims(threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1)
    )
    assert high > low


def test_weighted_aggregate_within_range_and_deterministic() -> None:
    estimator = WeightedAggregateEstimator()
    dims = _dims(threat=1.0, reward=1.0, novelty=1.0, social=1.0, uncertainty=1.0)
    first = estimator.estimate_aggregate(_stimulus(), dims)
    second = estimator.estimate_aggregate(_stimulus(), dims)
    assert first == second
    assert 0.0 <= first <= 1.0


def test_weighted_aggregate_flows_through_engine_not_constant() -> None:
    # Through the engine with real grounded dimensions, the salience vector's aggregate reflects
    # the convex combination of the dimensions, not the constant 0.4 shim.
    engine = RapidSalienceAppraisalEngine(
        dimension_estimator=_grounded(
            similarity=0.5, similarities=(0.5, 0.2), presence=1.0, prototype_similarity=0.4
        ),
        aggregate_estimator=WeightedAggregateEstimator(),
    )
    salience = engine.assess_batch(_build_valid_batch()).appraisals[0].salience
    expected = round(
        0.25 * salience.threat
        + 0.25 * salience.reward
        + 0.20 * salience.novelty
        + 0.15 * salience.uncertainty
        + 0.15 * salience.social,
        4,
    )
    assert salience.aggregate == pytest.approx(expected)
    assert salience.aggregate != pytest.approx(0.4)
