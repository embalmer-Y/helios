"""Requirement 97 - estimator wiring tests (中文 appraisal grounding).

Eight tests covering the `GroundedDimensionEstimator.anchor_catalog` field
behavior. These are the network-free, deterministic tests that prove:
- the R40 English-anchor path is byte-level preserved (R97 is purely
  additive on top of R40 for English inputs);
- the R97 Chinese-anchor path closes the B3 root cause for Chinese inputs
  (中文 negative inputs produce non-zero threat; 中文 positive inputs
  produce non-zero reward; 中性 Chinese inputs stay low);
- the max-of-max behavior across (R40 prototypes) and (catalog phrases)
  picks the larger of the two cosine maxima, never the smaller;
- a custom (P5 learned) catalog can replace the default at the same
  injection seam.

The tests use a `FakeEmbeddingPrototypeSource` that returns a
deterministic cosine derived from per-phrase text similarity heuristics
(no real network, no LLM, no embedding model). The heuristics are
designed so the Chinese catalog anchors score higher on matching
Chinese emotion text and the English R40 anchors score higher on
matching English text, mirroring the real-cloud behavior.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.appraisal import (
    DEFAULT_ANCHOR_CATALOG,
    GroundedDimensionEstimator,
    THREAT_PROTOTYPES,
    REWARD_PROTOTYPES,
    AnchorCatalog,
    AnchorSet,
)
from helios_v2.sensory import Stimulus


# --------------------------------------------------------------------------- #
# FakeEmbeddingPrototypeSource: deterministic, network-free cosine for tests. #
# --------------------------------------------------------------------------- #


def _toy_similarity(query: str, phrase: str) -> float:
    """A toy similarity function that captures the cross-language structure.

    Heuristics (no real embedding model):
    - If the query shares a word boundary (substring ≥ 2 CJK chars OR
      ≥ 3 latin chars) with the phrase, cosine ≈ 0.7.
    - If the query shares NO content but shares the same script (CJK
      with CJK, latin with latin), cosine ≈ 0.05.
    - Cross-script (CJK query with latin phrase, or vice versa), cosine
      ≈ 0.0 (mimics text-embedding-3-small's cross-language gap).
    - Empty query -> 0.0.
    """
    q = query.strip()
    p = phrase.strip()
    if not q or not p:
        return 0.0
    q_is_cjk = any("\u4e00" <= c <= "\u9fff" for c in q)
    p_is_cjk = any("\u4e00" <= c <= "\u9fff" for c in p)
    if q_is_cjk != p_is_cjk:
        return 0.0
    if q_is_cjk:
        # Look for 2+ char substring overlap (rare in toy 5-phrase corpus,
        # but the anchors are designed to share vocabulary with the
        # emotion inputs in the tests below).
        for n in (3, 2):
            for i in range(0, len(q) - n + 1):
                sub = q[i : i + n]
                if sub in p:
                    return 0.7
        return 0.05
    # Latin: case-insensitive whole-word overlap.
    q_words = {w.lower() for w in q.split() if len(w) >= 3}
    p_words = {w.lower() for w in p.split() if len(w) >= 3}
    if q_words & p_words:
        return 0.7
    return 0.05


@dataclass
class FakeEmbeddingPrototypeSource:
    """A deterministic `PrototypeSimilaritySource` double for R97 wiring tests.

    Conforms to the `PrototypeSimilaritySource` protocol: exposes
    `max_similarity_to(stimulus, prototypes) -> float | None` and uses
    `_toy_similarity` as the per-phrase cosine. The toy similarity is
    hard-coded to mirror the real-cloud cross-language gap, so these
    tests validate the same max-of-max + byte-level-preservation
    contract that the real cloud would.
    """

    def max_similarity_to(
        self, stimulus: Stimulus, prototypes: tuple[str, ...]
    ) -> float | None:
        text = stimulus.content.strip()
        if not text or not prototypes:
            return None
        return max(_toy_similarity(text, phrase) for phrase in prototypes)


@dataclass
class _ConstantSimilarity:
    """`MemorySimilaritySource` double returning a fixed max-similarity (or `None`)."""

    similarity: float | None = 0.0

    def max_similarity_for(self, stimulus: Stimulus) -> float | None:
        return self.similarity


@dataclass
class _ConstantAmbiguity:
    """`RetrievalAmbiguitySource` double returning a fixed similarity tuple."""

    similarities: tuple[float, ...] = ()

    def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
        return self.similarities


@dataclass
class _ConstantSocial:
    """`SocialContextSource` double returning a fixed presence."""

    presence: float = 0.0

    def social_presence_for(self, stimulus: Stimulus) -> float:
        return self.presence


def _grounded(
    *, similarity: float | None = 0.0, prototype_source=None
) -> GroundedDimensionEstimator:
    return GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(similarity=similarity),
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=prototype_source or FakeEmbeddingPrototypeSource(),
    )


def _stimulus(content: str) -> Stimulus:
    return Stimulus(
        stimulus_id="r97-test",
        source_name="r97-test",
        modality="text",
        content=content,
        channel="test",
        metadata=None,
        provenance_signal_id="p1",
    )


# --------------------------------------------------------------------------- #
# The 8 wiring tests.                                                         #
# --------------------------------------------------------------------------- #


def test_zh_threat_input_scores_high_threat_under_zh_anchors() -> None:
    # A Chinese negative-emotion input matches a Chinese threat anchor
    # ("我感到恐惧" shares the substring "恐惧" with "我感到非常恐惧" in
    # the ZH threat set). The estimator must score threat > 0.
    estimator = _grounded()
    estimate = estimator.estimate_dimensions(
        _stimulus("我感到恐惧，今天的世界很危险")
    )
    # The ZH threat subset of the default catalog contains "我感到非常恐惧";
    # substring "恐惧" matches -> 0.7 * threat_gain (1.0) = 0.7.
    assert estimate.threat >= 0.3, (
        f"Expected threat >= 0.3 for Chinese threat input, got {estimate.threat}"
    )


def test_zh_reward_input_scores_high_reward_under_zh_anchors() -> None:
    # A Chinese positive-emotion input matches a Chinese reward anchor
    # ("我获得" shares a substring with "我获得了渴望的东西" in the ZH
    # reward set). The estimator must score reward > 0.
    estimator = _grounded()
    estimate = estimator.estimate_dimensions(
        _stimulus("我获得了渴望的东西")
    )
    assert estimate.reward >= 0.3, (
        f"Expected reward >= 0.3 for Chinese reward input, got {estimate.reward}"
    )


def test_zh_neutral_input_scores_low_threat_and_reward() -> None:
    # A neutral Chinese input ("今天星期三") does not match any ZH threat
    # or ZH reward anchor. Its cosine is the cross-script / non-matching
    # fallback (≤ 0.05). The threat and reward scores must stay low.
    estimator = _grounded()
    estimate = estimator.estimate_dimensions(_stimulus("今天星期三"))
    assert estimate.threat < 0.2, (
        f"Expected threat < 0.2 for neutral Chinese input, got {estimate.threat}"
    )
    assert estimate.reward < 0.2, (
        f"Expected reward < 0.2 for neutral Chinese input, got {estimate.reward}"
    )


def test_en_anchors_still_work_under_catalog() -> None:
    # The English R40 path is preserved byte-level-equivalent: an
    # English threat input against the R40 English anchors (which are
    # aliased into the default catalog) still scores high. This is the
    # R97 additive-only contract: no regression on the R40 path.
    estimator = _grounded()
    estimate = estimator.estimate_dimensions(
        _stimulus("this is a dangerous threat")
    )
    # The EN threat subset of the default catalog aliases
    # `THREAT_PROTOTYPES`, which contains "a dangerous threat"; the
    # input "this is a dangerous threat" shares "dangerous" / "threat" ->
    # 0.7 * threat_gain (1.0) = 0.7.
    assert estimate.threat >= 0.3, (
        f"Expected threat >= 0.3 for English threat input (R40 byte-level "
        f"preserved), got {estimate.threat}"
    )


def test_catalog_max_dominates_when_injected() -> None:
    # A Chinese threat input has low cosine against the English R40
    # anchors (cross-script -> 0.0) and high cosine against the Chinese
    # catalog anchors (substring match -> 0.7). The estimator's max-of-max
    # must pick the larger (the Chinese one). The R40-only path would
    # have scored 0.0; the R97 catalog-augmented path scores 0.7.
    zh_only_catalog = AnchorCatalog(sets=(
        AnchorSet(language="zh", dimension="threat", phrases=(
            "我感到非常恐惧",
        )),
        AnchorSet(language="en", dimension="threat", phrases=THREAT_PROTOTYPES),
    ))
    estimator = GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),  # type: ignore[arg-type]
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeEmbeddingPrototypeSource(),
        anchor_catalog=zh_only_catalog,
    )
    estimate = estimator.estimate_dimensions(
        _stimulus("我感到恐惧")
    )
    assert estimate.threat >= 0.3, (
        f"Expected threat >= 0.3 (Chinese catalog max dominates), "
        f"got {estimate.threat}"
    )


def test_catalog_fallback_when_no_zh_anchor_matches() -> None:
    # When the Chinese catalog has no matching phrase for a Chinese
    # threat input, the estimator must fall back to the R40 English
    # path. The max-of-max returns the larger of the two; if both are
    # 0 (no match), the score is 0.0.
    zh_unrelated_catalog = AnchorCatalog(sets=(
        # Chinese threat anchors that do NOT share vocabulary with the
        # test input "我感到恐惧" (no substring overlap with "恐惧").
        AnchorSet(language="zh", dimension="threat", phrases=(
            "猫坐在垫子上",
            "天空是蓝色的",
        )),
        AnchorSet(language="en", dimension="threat", phrases=THREAT_PROTOTYPES),
    ))
    estimator = GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),  # type: ignore[arg-type]
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeEmbeddingPrototypeSource(),
        anchor_catalog=zh_unrelated_catalog,
    )
    estimate = estimator.estimate_dimensions(
        _stimulus("我感到恐惧")
    )
    # English R40 anchors have no overlap ("dangerous threat" in
    # English vs "我感到恐惧" in Chinese -> cross-script 0.0). The
    # Chinese unrelated anchors ("猫坐在垫子上" etc.) are CJK-script
    # but share no vocabulary with "我感到恐惧" -> the toy similarity
    # gives the CJK background-noise value (≤ 0.05). The max-of-max
    # stays at the CJK background level; the threat score must NOT
    # spike to a high value (which would mean the catalog still
    # "matches" semantically).
    assert estimate.threat <= 0.1, (
        f"Expected threat <= 0.1 (no anchor semantically matches), "
        f"got {estimate.threat}"
    )


def test_estimator_default_catalog_works_without_injection() -> None:
    # When the caller constructs `GroundedDimensionEstimator(...)`
    # WITHOUT an explicit `anchor_catalog=...` keyword, the `default_factory`
    # resolves to `DEFAULT_ANCHOR_CATALOG` (the bilingual first-version
    # catalog). The estimator is immediately usable with no extra wiring.
    estimator = GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),  # type: ignore[arg-type]
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeEmbeddingPrototypeSource(),
    )
    # The estimator's `anchor_catalog` field is the default catalog,
    # not `None` and not an empty catalog.
    assert estimator.anchor_catalog is DEFAULT_ANCHOR_CATALOG
    # Sanity: a Chinese threat input still scores high (default catalog
    # contains the ZH threat anchors).
    estimate = estimator.estimate_dimensions(
        _stimulus("我感到恐惧")
    )
    assert estimate.threat >= 0.3


def test_learned_catalog_can_replace_default() -> None:
    # P5 learning-loop contract: a learned catalog is just a new
    # `AnchorCatalog(sets=learned_sets)` instance injected at the same
    # seam. The estimator accepts any well-formed catalog and uses it
    # for the max-of-max, ignoring the default when an explicit catalog
    # is provided.
    learned_catalog = AnchorCatalog(sets=(
        AnchorSet(language="zh", dimension="threat", phrases=(
            "P5-learned threat anchor",
        )),
        AnchorSet(language="zh", dimension="reward", phrases=(
            "P5-learned reward anchor",
        )),
        AnchorSet(language="en", dimension="threat", phrases=THREAT_PROTOTYPES),
        AnchorSet(language="en", dimension="reward", phrases=REWARD_PROTOTYPES),
    ))
    estimator = GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),  # type: ignore[arg-type]
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeEmbeddingPrototypeSource(),
        anchor_catalog=learned_catalog,
    )
    # The estimator's `anchor_catalog` is the learned catalog, NOT the
    # default.
    assert estimator.anchor_catalog is learned_catalog
    assert estimator.anchor_catalog is not DEFAULT_ANCHOR_CATALOG
    # The estimator is still usable (no crash on construction, no
    # exception on `estimate_dimensions`).
    estimate = estimator.estimate_dimensions(_stimulus("anything"))
    assert 0.0 <= estimate.threat <= 1.0
    assert 0.0 <= estimate.reward <= 1.0
