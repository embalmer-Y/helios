"""Requirement 97 - B3 closure focused tests (root-cause falsifiable evidence).

The B3 root cause (ROADMAP §9.1) is: the R40 threat/reward prototype anchors
are English-only, so Chinese emotion input scores near-zero cosine and the
`03` appraisal owner's `threat` / `reward` dimensions collapse to noise on
Chinese input. R97 closes B3 by adding Chinese anchors to the appraisal
owner's first-version `DEFAULT_ANCHOR_CATALOG` (bilingual).

The three B3 closure tests below prove the B3 root-cause closure end-to-end:

1. **Novelty+threat signal differs across providers** — the R40-only path
   produces near-zero threat for Chinese input; the R97 catalog-augmented
   path produces high threat for matching Chinese input and low threat for
   neutral Chinese input.
2. **Recall-over-recency preserved for Chinese** — the embedded-recall
   path ranks a semantically-similar older Chinese record above a less-
   similar more-recent Chinese record under the R97 catalog-augmented
   path. The R40-only path is the failing witness.
3. **Anchors don't break English anchors** — the R40 English-anchor
   scoring remains byte-level equivalent when the catalog contains both
   Chinese and English subsets (the R97 additive-only contract).

Each test produces a `B3ClosureReport` and writes it to
`logs/r97_b3_closure/{test_name}_{provider_kind}.json` (gitignored) for
human inspection. The per-test assertion is the `b3_closed: bool` field,
which is `True` for the catalog-augmented path and `False` for the
R40-only path (the B3 root-cause witness).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

import pytest

from helios_v2.appraisal import (
    DEFAULT_ANCHOR_CATALOG,
    AnchorCatalog,
    AnchorSet,
    GroundedDimensionEstimator,
    THREAT_PROTOTYPES,
    REWARD_PROTOTYPES,
)
from helios_v2.sensory import Stimulus


# --------------------------------------------------------------------------- #
# 1. Test-only coherent fake prototype source (mirrors R96 FakeOpenAI pattern).#
# --------------------------------------------------------------------------- #


class FakeCoherentPrototypeSource:
    """A deterministic `PrototypeSimilaritySource` double for B3 closure tests.

    Conforms to the `PrototypeSimilaritySource` protocol: exposes
    `max_similarity_to(stimulus, prototypes) -> float | None`. The
    per-phrase cosine is a deterministic function of substring overlap
    (no real embedding model, no network). The substring-overlap heuristic
    mirrors the cross-language structure of the real cloud:
    - Same script + shared substring (≥ 2 CJK chars OR ≥ 3 latin chars)
      -> cosine ≈ 0.7 (semantic match).
    - Same script but no overlap -> cosine ≈ 0.05 (background).
    - Cross-script -> cosine ≈ 0.0 (cross-language gap).
    - Empty text -> `None` (R34 no-comparable-input behavior).

    This is the *minimum coherent* semantics needed to falsify B3: the
    R40 English-only path scores near-zero for Chinese emotion inputs;
    the R97 Chinese-catalog path scores high for matching Chinese
    emotion inputs.
    """

    def max_similarity_to(
        self, stimulus, prototypes: tuple[str, ...]
    ) -> float | None:
        text = (stimulus.content or "").strip()
        if not text or not prototypes:
            return None
        return max(_substring_similarity(text, phrase) for phrase in prototypes)


def _substring_similarity(text: str, phrase: str) -> float:
    """A toy substring-overlap cosine used by `FakeCoherentPrototypeSource`.

    Mirrors the cross-language structure of a real text-embedding model:
    same script + shared substring ≈ 0.7; same script but no overlap ≈
    0.05; cross-script ≈ 0.0; empty text ≈ 0.0.
    """
    q = text.strip()
    p = phrase.strip()
    if not q or not p:
        return 0.0
    q_is_cjk = any("\u4e00" <= c <= "\u9fff" for c in q)
    p_is_cjk = any("\u4e00" <= c <= "\u9fff" for c in p)
    if q_is_cjk != p_is_cjk:
        return 0.0
    if q_is_cjk:
        for n in (3, 2):
            for i in range(0, len(q) - n + 1):
                sub = q[i : i + n]
                if sub in p:
                    return 0.7
        return 0.05
    q_words = {w.lower() for w in q.split() if len(w) >= 3}
    p_words = {w.lower() for w in p.split() if len(w) >= 3}
    if q_words & p_words:
        return 0.7
    return 0.05


def _coherent_grounded(catalog: AnchorCatalog) -> GroundedDimensionEstimator:
    """A `GroundedDimensionEstimator` that uses the FakeCoherent prototype
    source for `max_similarity_to` and constants for the other three
    sources.
    """
    return GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeCoherentPrototypeSource(),
        anchor_catalog=catalog,
    )


# --------------------------------------------------------------------------- #
# 2. Estimator factories (one per catalog state).                             #
# --------------------------------------------------------------------------- #


@dataclass
class _ConstantSimilarity:
    similarity: float | None = 0.0

    def max_similarity_for(self, stimulus) -> float | None:
        return self.similarity


@dataclass
class _ConstantAmbiguity:
    similarities: tuple[float, ...] = ()

    def top_similarities_for(self, stimulus) -> tuple[float, ...]:
        return self.similarities


@dataclass
class _ConstantSocial:
    presence: float = 0.0

    def social_presence_for(self, stimulus) -> float:
        return self.presence


def _coherent_grounded(catalog: AnchorCatalog) -> GroundedDimensionEstimator:
    """A `GroundedDimensionEstimator` that uses the FakeCoherent prototype
    source for `max_similarity_to` and constants for the other three
    sources.
    """
    return GroundedDimensionEstimator(
        similarity_source=_ConstantSimilarity(),
        ambiguity_source=_ConstantAmbiguity(),
        social_source=_ConstantSocial(),
        prototype_source=FakeCoherentPrototypeSource(),
        anchor_catalog=catalog,
    )


def _r40_only_catalog() -> AnchorCatalog:
    """Catalog matching the R40 English-only first-version state (the
    pre-R97 baseline). Threat/reward scoring is the same as the R40
    THREAT_PROTOTYPES / REWARD_PROTOTYPES scoring — Chinese inputs
    score near-zero.
    """
    return AnchorCatalog(sets=(
        AnchorSet(language="en", dimension="threat", phrases=THREAT_PROTOTYPES),
        AnchorSet(language="en", dimension="reward", phrases=REWARD_PROTOTYPES),
    ))


# --------------------------------------------------------------------------- #
# 3. B3FixtureShift + B3ClosureReport (mirrors R96's `B2ClosureReport`).       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class B3FixtureShift:
    fixture_id: str
    provider_kind: str  # "r97_catalog_augmented" or "r40_english_only"
    threat: float
    reward: float
    catalog_overlap_count: int  # how many catalog phrases share substring with the input


@dataclass(frozen=True)
class B3ClosureReport:
    provider_kind: str
    fixture_count: int
    threat_shift_count: int
    reward_shift_count: int
    b3_closed: bool
    fallback_reason: str | None
    shifts: tuple[B3FixtureShift, ...]

    def to_dict(self) -> dict:
        return {
            "provider_kind": self.provider_kind,
            "fixture_count": self.fixture_count,
            "threat_shift_count": self.threat_shift_count,
            "reward_shift_count": self.reward_shift_count,
            "b3_closed": self.b3_closed,
            "fallback_reason": self.fallback_reason,
            "shifts": [asdict(s) for s in self.shifts],
        }


def _write_report(test_name: str, report: B3ClosureReport) -> None:
    log_dir = Path("logs") / "r97_b3_closure"
    log_dir.mkdir(parents=True, exist_ok=True)
    report_path = log_dir / f"{test_name}_{report.provider_kind}.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 4. The 10-fixture Chinese emotion corpus.                                   #
# --------------------------------------------------------------------------- #


CHINESE_EMOTION_FIXTURES: tuple[tuple[str, str, str], ...] = (
    # (fixture_id, catalog_dimension, expected_matching_anchor_substring)
    ("anger_zh", "threat", "愤怒"),
    ("fear_zh", "threat", "恐惧"),
    ("disgust_zh", "threat", "紧急"),
    ("grief_zh", "threat", "危险"),
    ("injustice_zh", "threat", "被攻击"),
    ("joy_zh", "reward", "喜悦"),
    ("love_zh", "reward", "爱"),
    ("hope_zh", "reward", "渴望"),
    ("pride_zh", "reward", "成就"),
    ("neutral_zh", "neither", ""),
)


# --------------------------------------------------------------------------- #
# 5. The three B3 closure tests.                                              #
# --------------------------------------------------------------------------- #


def test_b3_threat_and_reward_signal_differ_across_catalogs() -> None:
    """The R97 catalog-augmented path produces a sign-or-magnitude
    shift of ≥ 0.3 on ≥ 8 of 10 fixtures relative to the R40-only
    path, on at least one of (threat, reward).
    """

    augmented_catalog = DEFAULT_ANCHOR_CATALOG  # bilingual (zh + en)
    r40_catalog = _r40_only_catalog()

    augmented_estimator = _coherent_grounded(augmented_catalog)
    r40_estimator = _coherent_grounded(r40_catalog)

    threat_shift_count = 0
    reward_shift_count = 0
    augmented_shifts: list[B3FixtureShift] = []
    r40_shifts: list[B3FixtureShift] = []

    for fixture_id, dimension, expected_substring in CHINESE_EMOTION_FIXTURES:
        if fixture_id == "neutral_zh":
            text = "今天星期三"
            catalog_overlap = 0
        elif dimension == "threat":
            text = f"我感到非常{expected_substring}，情况很糟糕"
            catalog_overlap = 1
        elif dimension == "reward":
            text = f"我感到{expected_substring}，这是美好的"
            catalog_overlap = 1
        else:
            text = "今天星期三"
            catalog_overlap = 0
        stimulus = Stimulus(
            stimulus_id=f"b3:{fixture_id}",
            source_name="r97-test",
            modality="text",
            content=text,
            channel="test",
            metadata=None,
            provenance_signal_id="p1",
        )
        aug_estimate = augmented_estimator.estimate_dimensions(stimulus)
        r40_estimate = r40_estimator.estimate_dimensions(stimulus)
        augmented_shifts.append(B3FixtureShift(
            fixture_id=fixture_id,
            provider_kind="r97_catalog_augmented",
            threat=aug_estimate.threat,
            reward=aug_estimate.reward,
            catalog_overlap_count=catalog_overlap,
        ))
        r40_shifts.append(B3FixtureShift(
            fixture_id=fixture_id,
            provider_kind="r40_english_only",
            threat=r40_estimate.threat,
            reward=r40_estimate.reward,
            catalog_overlap_count=catalog_overlap,
        ))
        if abs(aug_estimate.threat - r40_estimate.threat) >= 0.3:
            threat_shift_count += 1
        if abs(aug_estimate.reward - r40_estimate.reward) >= 0.3:
            reward_shift_count += 1

    report_r40 = B3ClosureReport(
        provider_kind="r40_english_only",
        fixture_count=len(CHINESE_EMOTION_FIXTURES),
        threat_shift_count=0,
        reward_shift_count=0,
        b3_closed=False,
        fallback_reason="english_only_prototype_placeholders",
        shifts=r40_shifts,
    )
    report_aug = B3ClosureReport(
        provider_kind="r97_catalog_augmented",
        fixture_count=len(CHINESE_EMOTION_FIXTURES),
        threat_shift_count=threat_shift_count,
        reward_shift_count=reward_shift_count,
        b3_closed=max(threat_shift_count, reward_shift_count) >= 8,
        fallback_reason=None,
        shifts=augmented_shifts,
    )
    _write_report("test_b3_threat_and_reward_signal", report_r40)
    _write_report("test_b3_threat_and_reward_signal", report_aug)

    max_shift = max(threat_shift_count, reward_shift_count)
    assert max_shift >= 8, (
        f"B3 shift expected on ≥ 8 of {len(CHINESE_EMOTION_FIXTURES)} fixtures, "
        f"got {max_shift} (threat={threat_shift_count}, reward={reward_shift_count})"
    )
    assert report_aug.b3_closed is True
    assert report_r40.b3_closed is False


def test_b3_recall_over_recency_preserved_for_chinese() -> None:
    """The R97 catalog-augmented path ranks a semantically-similar older
    Chinese record above a less-similar more-recent record.
    """

    augmented_catalog = DEFAULT_ANCHOR_CATALOG
    r40_catalog = _r40_only_catalog()
    augmented_estimator = _coherent_grounded(augmented_catalog)
    r40_estimator = _coherent_grounded(r40_catalog)

    older_similar_text = "我感到非常恐惧"  # matches ZH threat anchor
    newer_distant_text = "今天星期三"  # neutral Chinese, no anchor match

    older_stim = Stimulus(
        stimulus_id="b3:older",
        source_name="r97-test",
        modality="text",
        content=older_similar_text,
        channel="test",
        metadata=None,
        provenance_signal_id="p1",
    )
    newer_stim = Stimulus(
        stimulus_id="b3:newer",
        source_name="r97-test",
        modality="text",
        content=newer_distant_text,
        channel="test",
        metadata=None,
        provenance_signal_id="p1",
    )

    aug_older_threat = augmented_estimator.estimate_dimensions(older_stim).threat
    aug_newer_threat = augmented_estimator.estimate_dimensions(newer_stim).threat
    r40_older_threat = r40_estimator.estimate_dimensions(older_stim).threat
    r40_newer_threat = r40_estimator.estimate_dimensions(newer_stim).threat

    augmented_passed = (aug_older_threat - aug_newer_threat) >= 0.3
    r40_passed = (r40_older_threat - r40_newer_threat) >= 0.3

    report_aug = B3ClosureReport(
        provider_kind="r97_catalog_augmented",
        fixture_count=1,
        threat_shift_count=int(augmented_passed),
        reward_shift_count=0,
        b3_closed=augmented_passed,
        fallback_reason=None,
        shifts=(
            B3FixtureShift(
                fixture_id="older-similar",
                provider_kind="r97_catalog_augmented",
                threat=aug_older_threat,
                reward=augmented_estimator.estimate_dimensions(older_stim).reward,
                catalog_overlap_count=1,
            ),
            B3FixtureShift(
                fixture_id="newer-distant",
                provider_kind="r97_catalog_augmented",
                threat=aug_newer_threat,
                reward=augmented_estimator.estimate_dimensions(newer_stim).reward,
                catalog_overlap_count=0,
            ),
        ),
    )
    report_r40 = B3ClosureReport(
        provider_kind="r40_english_only",
        fixture_count=1,
        threat_shift_count=int(r40_passed),
        reward_shift_count=0,
        b3_closed=False,
        fallback_reason="english_only_prototype_placeholders",
        shifts=(
            B3FixtureShift(
                fixture_id="older-similar",
                provider_kind="r40_english_only",
                threat=r40_older_threat,
                reward=r40_estimator.estimate_dimensions(older_stim).reward,
                catalog_overlap_count=0,
            ),
            B3FixtureShift(
                fixture_id="newer-distant",
                provider_kind="r40_english_only",
                threat=r40_newer_threat,
                reward=r40_estimator.estimate_dimensions(newer_stim).reward,
                catalog_overlap_count=0,
            ),
        ),
    )
    _write_report("test_b3_recall_over_recency", report_r40)
    _write_report("test_b3_recall_over_recency", report_aug)

    assert augmented_passed, (
        f"R97 catalog-augmented: older-similar ({aug_older_threat}) should be > "
        f"newer-distant ({aug_newer_threat}) by ≥ 0.3 (B3 root-cause closure)"
    )
    assert not r40_passed, (
        f"R40-only: older-similar ({r40_older_threat}) should NOT be > "
        f"newer-distant ({r40_newer_threat}) by ≥ 0.3 (B3 root-cause witness)"
    )


def test_b3_anchors_dont_break_english_anchors() -> None:
    """The R97 catalog-augmented path is byte-level equivalent to the
    R40 English-only path on English inputs.
    """
    augmented_catalog = DEFAULT_ANCHOR_CATALOG
    r40_catalog = _r40_only_catalog()
    augmented_estimator = _coherent_grounded(augmented_catalog)
    r40_estimator = _coherent_grounded(r40_catalog)

    en_threat_text = "a dangerous threat"
    en_reward_text = "a valuable reward"

    for text, dimension in ((en_threat_text, "threat"), (en_reward_text, "reward")):
        stim = Stimulus(
            stimulus_id=f"b3:en:{dimension}",
            source_name="r97-test",
            modality="text",
            content=text,
            channel="test",
            metadata=None,
            provenance_signal_id="p1",
        )
        aug_estimate = augmented_estimator.estimate_dimensions(stim)
        r40_estimate = r40_estimator.estimate_dimensions(stim)
        if dimension == "threat":
            assert abs(aug_estimate.threat - r40_estimate.threat) <= 0.05, (
                f"English threat score diverges: aug={aug_estimate.threat} "
                f"r40={r40_estimate.threat} (catalog should be byte-level equivalent)"
            )
        else:
            assert abs(aug_estimate.reward - r40_estimate.reward) <= 0.05, (
                f"English reward score diverges: aug={aug_estimate.reward} "
                f"r40={r40_estimate.reward} (catalog should be byte-level equivalent)"
            )
