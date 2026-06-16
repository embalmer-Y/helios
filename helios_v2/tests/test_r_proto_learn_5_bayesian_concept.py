"""Owner: rapid salience appraisal.

Tests for R-PROTO-LEARN.5 (Layer 5 learning, Bayesian update of concept prior).

These tests verify:
  1. EmotionConcept constructs; ConceptPrior.empty() returns an empty prior;
     ConceptPrior.from_concepts() seeds zero-count priors from a taxonomy.
  2. bayesian_update: empty observation -> no-op; known concept adds weight;
     unknown concept is added; negative weight is skipped; learning_rate
     multiplier is applied.
  3. normalize: empty prior -> empty mapping; Laplace smoothing prevents
     zero-probability concepts; distribution sums to 1.0.
  4. observe_dimension: threat > 0.5 activates threat concepts; reward > 0.5
     activates reward concepts; both <= 0.5 -> empty observation.
  5. GroundedDimensionEstimator maintains concept_prior across ticks;
     estimate_dimensions auto-applies one observation step.
  6. observe() public surface accepts caller-supplied observations.
  7. concept_distribution() and top_concepts() public surfaces return
     readable distributions.
  8. seed_prior() initializes from a taxonomy.
  9. R-PROTO-LEARN.5 is independent of the description fallback (Layer 1)
     — the two layers compose.
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal.concept_state import (
    DEFAULT_CONCEPTS,
    ConceptPrior,
    EmotionConcept,
    bayesian_update,
    normalize,
    observe_dimension,
    top_concepts,
)
from helios_v2.appraisal.engine import GroundedDimensionEstimator
from helios_v2.appraisal.anchor_catalog import AnchorCatalog, AnchorSet


def _stub_sources() -> tuple[object, object]:
    class _MemSrc:
        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 0.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    return _MemSrc(), _SocSrc()


def _stub_prototype_source() -> object:
    class _PSrc:
        def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
            return 0.0

    return _PSrc()


def _make_estimator(
    *,
    concepts: tuple[EmotionConcept, ...] = DEFAULT_CONCEPTS,
    learning_rate: float = 1.0,
) -> GroundedDimensionEstimator:
    mem_src, soc_src = _stub_sources()
    ps = _stub_prototype_source()
    return GroundedDimensionEstimator(
        similarity_source=mem_src,
        ambiguity_source=mem_src,
        social_source=soc_src,
        prototype_source=ps,
        concepts=concepts,
        concept_learning_rate=learning_rate,
    )


# --------------------------------------------------------------------------- #
# 1. EmotionConcept + ConceptPrior construction                              #
# --------------------------------------------------------------------------- #


def test_emotion_concept_constructs_with_required_fields() -> None:
    c = EmotionConcept(name="x", dimension="threat", description="y")
    assert c.name == "x"
    assert c.dimension == "threat"
    assert c.description == "y"
    assert c.base_weight == 1.0  # default


def test_default_concepts_is_non_empty() -> None:
    assert len(DEFAULT_CONCEPTS) >= 4
    # threat dimension has at least one concept
    assert any(c.dimension == "threat" for c in DEFAULT_CONCEPTS)
    assert any(c.dimension == "reward" for c in DEFAULT_CONCEPTS)


def test_concept_prior_empty_returns_empty_prior() -> None:
    prior = ConceptPrior.empty()
    assert prior.counts == {}
    assert prior.observations == 0
    assert prior.learning_rate == 1.0
    assert prior.smoothing_mass == 1.0


def test_concept_prior_from_concepts_seeds_zero_counts() -> None:
    prior = ConceptPrior.from_concepts(DEFAULT_CONCEPTS)
    assert set(prior.counts.keys()) == {c.name for c in DEFAULT_CONCEPTS}
    assert all(v == 0.0 for v in prior.counts.values())
    assert prior.observations == 0


# --------------------------------------------------------------------------- #
# 2. bayesian_update pure function                                          #
# --------------------------------------------------------------------------- #


def test_bayesian_update_empty_observation_is_noop() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=1)
    new_prior = bayesian_update(prior, {})
    assert new_prior.counts == {"a": 1.0}
    assert new_prior.observations == 1


def test_bayesian_update_adds_weight_to_known_concept() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=0)
    new_prior = bayesian_update(prior, {"a": 2.0})
    assert new_prior.counts["a"] == 3.0
    assert new_prior.observations == 1


def test_bayesian_update_adds_unknown_concept_silently() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=0)
    new_prior = bayesian_update(prior, {"z": 0.5})
    assert new_prior.counts == {"a": 1.0, "z": 0.5}


def test_bayesian_update_skips_negative_weight() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=0)
    new_prior = bayesian_update(prior, {"a": -0.5})
    # Negative weight is silently skipped; counts unchanged
    assert new_prior.counts["a"] == 1.0


def test_bayesian_update_applies_learning_rate() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=0, learning_rate=2.0)
    new_prior = bayesian_update(prior, {"a": 1.0})
    # weight * rate = 1.0 * 2.0 = 2.0 added
    assert new_prior.counts["a"] == 3.0


def test_bayesian_update_does_not_mutate_input() -> None:
    prior = ConceptPrior(counts={"a": 1.0}, observations=0)
    _ = bayesian_update(prior, {"a": 0.5})
    # Original unchanged
    assert prior.counts["a"] == 1.0
    assert prior.observations == 0


# --------------------------------------------------------------------------- #
# 3. normalize: Laplace-smoothed distribution                               #
# --------------------------------------------------------------------------- #


def test_normalize_empty_prior_returns_empty_mapping() -> None:
    prior = ConceptPrior.empty()
    assert normalize(prior) == {}


def test_normalize_smoothing_prevents_zero_probability() -> None:
    prior = ConceptPrior(counts={"a": 0.0, "b": 1.0}, smoothing_mass=1.0)
    dist = normalize(prior)
    # Even "a" (count=0) gets a non-zero probability from smoothing
    assert dist["a"] > 0.0
    assert dist["b"] > dist["a"]


def test_normalize_sums_to_approximately_one() -> None:
    prior = ConceptPrior(counts={"a": 1.0, "b": 2.0, "c": 3.0})
    dist = normalize(prior)
    assert abs(sum(dist.values()) - 1.0) < 1e-5


def test_normalize_single_concept_with_zero_count() -> None:
    prior = ConceptPrior(counts={"only": 0.0})
    dist = normalize(prior)
    assert dist == {"only": 1.0}


# --------------------------------------------------------------------------- #
# 4. observe_dimension: heuristic mapping                                   #
# --------------------------------------------------------------------------- #


def test_observe_dimension_threat_above_threshold() -> None:
    obs = observe_dimension(estimate_threat=0.7, estimate_reward=0.1)
    # Threat dimension concepts activated
    threat_concepts = {c.name for c in DEFAULT_CONCEPTS if c.dimension == "threat"}
    assert set(obs.keys()) == threat_concepts
    # Reward concepts NOT activated
    reward_concepts = {c.name for c in DEFAULT_CONCEPTS if c.dimension == "reward"}
    assert not (set(obs.keys()) & reward_concepts)


def test_observe_dimension_reward_above_threshold() -> None:
    obs = observe_dimension(estimate_threat=0.1, estimate_reward=0.8)
    reward_concepts = {c.name for c in DEFAULT_CONCEPTS if c.dimension == "reward"}
    assert set(obs.keys()) == reward_concepts


def test_observe_dimension_both_above_threshold() -> None:
    obs = observe_dimension(estimate_threat=0.7, estimate_reward=0.6)
    all_concepts = {c.name for c in DEFAULT_CONCEPTS}
    assert set(obs.keys()) == all_concepts


def test_observe_dimension_both_below_threshold_empty() -> None:
    obs = observe_dimension(estimate_threat=0.5, estimate_reward=0.3)
    assert obs == {}


def test_observe_dimension_base_weight_applied() -> None:
    # "shame" has base_weight=0.8 in DEFAULT_CONCEPTS
    obs = observe_dimension(estimate_threat=1.0, estimate_reward=0.0)
    assert obs["shame"] == pytest.approx(0.8, rel=1e-6)


# --------------------------------------------------------------------------- #
# 5. top_concepts                                                            #
# --------------------------------------------------------------------------- #


def test_top_concepts_empty_prior() -> None:
    assert top_concepts(ConceptPrior.empty(), k=3) == ()


def test_top_concepts_returns_descending_order() -> None:
    prior = ConceptPrior(counts={"a": 5.0, "b": 10.0, "c": 3.0})
    out = top_concepts(prior, k=3)
    assert out[0][0] == "b"
    assert out[1][0] == "a"
    assert out[2][0] == "c"


def test_top_concepts_k_clamped_to_count() -> None:
    prior = ConceptPrior(counts={"a": 1.0, "b": 2.0})
    out = top_concepts(prior, k=10)
    assert len(out) == 2


# --------------------------------------------------------------------------- #
# 6. GroundedDimensionEstimator integration                                  #
# --------------------------------------------------------------------------- #


def test_estimator_default_prior_is_empty() -> None:
    est = _make_estimator()
    assert est.concept_prior[0].counts == {}
    assert est.concept_prior[0].observations == 0


def test_estimator_default_concepts_is_default_taxonomy() -> None:
    est = _make_estimator()
    assert est.concepts == DEFAULT_CONCEPTS


def test_estimator_seed_prior_initializes_counts() -> None:
    est = _make_estimator()
    est.seed_prior()
    assert set(est.concept_prior[0].counts.keys()) == {c.name for c in DEFAULT_CONCEPTS}
    assert all(v == 0.0 for v in est.concept_prior[0].counts.values())


def test_estimator_observe_accepts_caller_observation() -> None:
    est = _make_estimator()
    est.seed_prior()
    initial = est.concept_prior[0].counts["acute_fear"]
    est.observe({"acute_fear": 2.0})
    assert est.concept_prior[0].counts["acute_fear"] == pytest.approx(initial + 2.0)
    assert est.concept_prior[0].observations == 1


def test_estimator_observe_unknown_concept_is_added() -> None:
    est = _make_estimator()
    est.observe({"nonexistent_concept": 1.0})
    assert est.concept_prior[0].counts["nonexistent_concept"] == 1.0


def test_estimator_observe_negative_weight_skipped() -> None:
    est = _make_estimator()
    est.seed_prior()
    est.observe({"acute_fear": -1.0})
    # No change in counts
    assert est.concept_prior[0].counts["acute_fear"] == 0.0


def test_estimator_concept_distribution_after_seed() -> None:
    est = _make_estimator()
    est.seed_prior()
    dist = est.concept_distribution()
    # All concepts have equal probability due to Laplace smoothing
    assert len(dist) == len(DEFAULT_CONCEPTS)
    assert abs(max(dist.values()) - min(dist.values())) < 1e-6


def test_estimator_concept_distribution_after_observation() -> None:
    est = _make_estimator()
    est.seed_prior()
    est.observe({"acute_fear": 10.0})
    dist = est.concept_distribution()
    # acute_fear should now dominate
    assert dist["acute_fear"] == max(dist.values())


def test_estimator_top_concepts_public_surface() -> None:
    est = _make_estimator()
    est.seed_prior()
    est.observe({"acute_fear": 5.0})
    est.observe({"joy": 10.0})
    top = est.top_concepts(k=2)
    assert top[0][0] == "joy"
    assert top[1][0] == "acute_fear"


# --------------------------------------------------------------------------- #
# 7. estimate_dimensions auto-applies observation                           #
# --------------------------------------------------------------------------- #


def _make_estimator_with_prototype_cosines(
    threat_cos: float = 0.0, reward_cos: float = 0.0,
) -> GroundedDimensionEstimator:
    """Build estimator with a prototype source that returns scripted cosines."""
    class _PSrc:
        def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
            if prototypes and prototypes[0] in ("a dangerous threat", "I am under attack",
                                                  "this will cause harm", "an urgent emergency",
                                                  "something is broken or failing"):
                return threat_cos
            return reward_cos

    mem_src, soc_src = _stub_sources()
    return GroundedDimensionEstimator(
        similarity_source=mem_src,
        ambiguity_source=mem_src,
        social_source=soc_src,
        prototype_source=_PSrc(),
        description_threshold=0.0,  # disable description path for determinism
    )


def _stimulus(text: str = "test"):
    from helios_v2.sensory import Stimulus
    return Stimulus(
        stimulus_id="s1",
        source_name="test",
        modality="text",
        content=text,
        channel=None,
        metadata=None,
        provenance_signal_id="p1",
    )


def test_estimate_dimensions_auto_observes_high_threat() -> None:
    # threat=0.8 > 0.5 -> threat concepts activated by auto-observe
    # R40 prototypes always score high enough so description path doesn't add value
    est = _make_estimator_with_prototype_cosines(threat_cos=0.8)
    est.seed_prior()
    _ = est.estimate_dimensions(_stimulus())
    # threat concepts should have non-zero counts after auto-observe
    prior = est.concept_prior[0]
    threat_concepts = {c.name for c in DEFAULT_CONCEPTS if c.dimension == "threat"}
    activated = threat_concepts & set(prior.counts.keys())
    assert len(activated) > 0
    assert all(prior.counts[c] > 0.0 for c in activated)


def test_estimate_dimensions_auto_observes_low_threat_noop() -> None:
    # threat=0.3 <= 0.5 -> no concept activated
    est = _make_estimator_with_prototype_cosines(threat_cos=0.3, reward_cos=0.3)
    est.seed_prior()
    _ = est.estimate_dimensions(_stimulus())
    # All counts remain at zero (no auto-observe)
    prior = est.concept_prior[0]
    assert all(v == 0.0 for v in prior.counts.values())


# --------------------------------------------------------------------------- #
# 8. Layer 1 (description fallback) + Layer 5 (Bayesian) compose cleanly   #
# --------------------------------------------------------------------------- #


def test_layers_1_and_5_compose_independently() -> None:
    """Layer 1 (description path) and Layer 5 (Bayesian update) are independent.
    The estimate_dimensions method runs both; they don't interfere.
    """
    # Custom catalog with descriptions
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("any_phrase",),
                description=("any_description",),
            ),
        )
    )

    class _PSrc:
        def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
            # phrase = 0.7, description = 0.5
            if prototypes == ("any_phrase",):
                return 0.7
            if prototypes == ("any_description",):
                return 0.5
            return 0.0  # R40 default prototypes

    mem_src, soc_src = _stub_sources()
    est = GroundedDimensionEstimator(
        similarity_source=mem_src,
        ambiguity_source=mem_src,
        social_source=soc_src,
        prototype_source=_PSrc(),
        anchor_catalog=catalog,
        description_threshold=0.0,  # disable description path
    )
    est.seed_prior()
    # With description_threshold=0.0, description path disabled.
    # threat = 0.7 (R40 + catalog phrase), reward = 0.0
    est.estimate_dimensions(_stimulus())
    # threat > 0.5 -> threat concepts activated
    assert any(v > 0.0 for v in est.concept_prior[0].counts.values())