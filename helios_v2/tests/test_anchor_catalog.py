"""Requirement 97 - anchor catalog unit tests.

Six unit tests covering the `appraisal.anchor_catalog` data structure.
These are the network-free, deterministic, fail-fast tests for the
catalog substrate. They are referenced by
`docs/requirements/97-chinese-appraisal-grounding/design.md` §5.4 and
form the first of three R97 test files (the other two are
`test_r97_chinese_grounding.py` for the estimator wiring and
`r97_b3_closure.py` for the B3 closure focused tests).
"""

from __future__ import annotations

import dataclasses

import pytest

from helios_v2.appraisal import (
    DEFAULT_ANCHOR_CATALOG,
    REWARD_PROTOTYPES,
    THREAT_PROTOTYPES,
    ZH_REWARD_ANCHORS,
    ZH_THREAT_ANCHORS,
    AnchorCatalog,
    AnchorSet,
)


def test_default_catalog_includes_zh_and_en() -> None:
    # The first-version catalog covers both languages for both threat and
    # reward. This is the B3 root-cause fix: the Chinese subset gives the
    # `03` appraisal owner a Chinese anchor for the `cortisol` (threat)
    # and `dopamine` (reward) channels that the R40 English-only anchors
    # did not provide.
    threat_languages = DEFAULT_ANCHOR_CATALOG.languages_for("threat")
    reward_languages = DEFAULT_ANCHOR_CATALOG.languages_for("reward")
    assert "zh" in threat_languages
    assert "en" in threat_languages
    assert "zh" in reward_languages
    assert "en" in reward_languages


def test_zh_threat_anchors_are_chinese_only() -> None:
    # Every phrase in the Chinese anchors is in the CJK Unified Ideographs
    # block (or the CJK Symbols and Punctuation block, or the CJK Strokes
    # block, etc.). This is a guard against the author accidentally pasting
    # English text into the Chinese anchor sets.
    cjk_ranges = [
        (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        (0x3000, 0x303F),    # CJK Symbols and Punctuation
        (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
        (0xFF00, 0xFFEF),    # Halfwidth and Fullwidth Forms
    ]

    def _is_cjk(char: str) -> bool:
        cp = ord(char)
        return any(start <= cp <= end for start, end in cjk_ranges)

    for phrase in ZH_THREAT_ANCHORS:
        assert any(_is_cjk(c) for c in phrase), (
            f"ZH threat anchor {phrase!r} contains no CJK characters"
        )
    for phrase in ZH_REWARD_ANCHORS:
        assert any(_is_cjk(c) for c in phrase), (
            f"ZH reward anchor {phrase!r} contains no CJK characters"
        )


def test_zh_anchors_distinct_from_en_anchors() -> None:
    # The Chinese and English phrase sets are disjoint. A duplicated
    # phrase would defeat the multilingual coverage.
    assert set(ZH_THREAT_ANCHORS).isdisjoint(set(THREAT_PROTOTYPES))
    assert set(ZH_REWARD_ANCHORS).isdisjoint(set(REWARD_PROTOTYPES))
    # Also: ZH threat is not a subset of ZH reward (and vice versa).
    assert set(ZH_THREAT_ANCHORS).isdisjoint(set(ZH_REWARD_ANCHORS))


def test_anchor_catalog_frozen() -> None:
    # `AnchorCatalog` and `AnchorSet` are frozen dataclasses; any attempt
    # to mutate post-construction is rejected. This is the R57 owner-
    # boundary invariant: the catalog is read-only after construction
    # so a learned (P5) catalog can be safely replaced as a whole without
    # leaking in-place mutation seams into the appraisal owner.
    catalog = AnchorCatalog(sets=(
        AnchorSet(language="zh", dimension="threat", phrases=("a",)),
    ))
    with pytest.raises(dataclasses.FrozenInstanceError):
        catalog.sets = ()  # type: ignore[misc]
    anchor = catalog.sets[0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        anchor.phrases = ()  # type: ignore[misc]


def test_phrases_for_returns_union() -> None:
    # `phrases_for` returns the union of phrases across all sets whose
    # dimension matches, preserving the iteration order of the input
    # `sets` (so the source's `_prototype_cache` keys are deterministic).
    catalog = AnchorCatalog(sets=(
        AnchorSet(language="zh", dimension="threat", phrases=("a", "b")),
        AnchorSet(language="en", dimension="threat", phrases=("c",)),
        AnchorSet(language="zh", dimension="reward", phrases=("d",)),
    ))
    threat = catalog.phrases_for("threat")
    assert threat == ("a", "b", "c")
    reward = catalog.phrases_for("reward")
    assert reward == ("d",)
    # Unknown dimension: empty tuple, not an error (the appraisal owner
    # treats empty-catalog as no-comparable-input).
    assert catalog.phrases_for("unknown") == ()


def test_catalog_with_only_zh_works() -> None:
    # The owner can construct a custom catalog with only the Chinese
    # subset. This is the P5 learned-catalog replacement seam: a future
    # learned catalog could be monolingual (e.g. only Chinese, or only
    # English), and the data structure must support it.
    catalog = AnchorCatalog(sets=(
        AnchorSet(language="zh", dimension="threat", phrases=("我被攻击",)),
        AnchorSet(language="zh", dimension="reward", phrases=("我喜悦",)),
    ))
    assert catalog.languages_for("threat") == ("zh",)
    assert catalog.phrases_for("threat") == ("我被攻击",)
    assert catalog.sets_for("threat")[0].language == "zh"
