"""Requirement 97 + 98 - anchor catalog unit tests.

Six unit tests covering the `appraisal.anchor_catalog` data structure.
R98 adds 6 R98 Set A (医学共识身体症状) anchor tests appended below the
R97 base 6 (total 12 tests in this file).
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


# --------------------------------------------------------------------------- #
# R98 Set A: 医学共识身体症状 anchor 极小扩 (6 个)。                            #
# 设计原则（plan §3.2）: 优先 DSM-5/ICD-11 共识的焦虑/抑郁核心身体症状词。       #
# --------------------------------------------------------------------------- #

R98_SET_A_THREAT_ANCHORS: tuple[str, ...] = (
    "我心跳加速心慌",
    "我整夜失眠睡不着",
    "我手心冒汗发抖",
    "我脑子停不下来",
    "我发高烧很难受",
    "家里静得让人害怕",
)


def test_r98_set_a_threat_anchors_in_zh_threat_anchors() -> None:
    # All 6 R98 Set A anchors must be present in `ZH_THREAT_ANCHORS`
    # (the catalog substrate). This guards against silent catalog
    # replacement regressions: R98 ships 5+6=11 ZH threat anchors and
    # this test would fail if any of the 6 Set A items were dropped.
    for anchor in R98_SET_A_THREAT_ANCHORS:
        assert anchor in ZH_THREAT_ANCHORS, (
            f"R98 Set A threat anchor {anchor!r} missing from ZH_THREAT_ANCHORS"
        )


def test_r98_set_a_total_zh_threat_count() -> None:
    # R97 ships 5 ZH threat anchors; R98 adds 6 Set A → 11 total.
    # This bound is the contract: catalog极小扩 (5→11), not 枚举爆炸.
    assert len(ZH_THREAT_ANCHORS) == 11, (
        f"Expected 11 ZH threat anchors (R97 5 + R98 Set A 6); got {len(ZH_THREAT_ANCHORS)}"
    )


def test_r98_set_a_all_chinese() -> None:
    # Same CJK guard as R97 but for the 6 R98 Set A anchors: every
    # phrase must contain at least one CJK character (no accidental
    # English pasting during R98 catalog extension).
    cjk_ranges = [
        (0x4E00, 0x9FFF),
        (0x3000, 0x303F),
        (0x3400, 0x4DBF),
        (0xFF00, 0xFFEF),
    ]

    def _is_cjk(char: str) -> bool:
        cp = ord(char)
        return any(start <= cp <= end for start, end in cjk_ranges)

    for phrase in R98_SET_A_THREAT_ANCHORS:
        assert any(_is_cjk(c) for c in phrase), (
            f"R98 Set A threat anchor {phrase!r} contains no CJK characters"
        )


def test_r98_set_a_distinct_from_en_anchors() -> None:
    # R98 Set A phrases must remain disjoint from R40 English anchors
    # (the multilingual coverage invariant from R97 must continue to hold
    # after catalog extension; otherwise we are duplicating, not adding).
    assert set(R98_SET_A_THREAT_ANCHORS).isdisjoint(set(THREAT_PROTOTYPES))


def test_r98_default_catalog_includes_set_a() -> None:
    # The `DEFAULT_ANCHOR_CATALOG` (used when no catalog is injected)
    # must include the R98 Set A anchors. This is the cold-start 兜底
    # contract: an owner that runs with the default catalog gets the
    # R97 5 + R98 6 ZH threat coverage without any explicit injection.
    phrases = DEFAULT_ANCHOR_CATALOG.phrases_for("threat")
    for anchor in R98_SET_A_THREAT_ANCHORS:
        assert anchor in phrases, (
            f"R98 Set A anchor {anchor!r} missing from DEFAULT_ANCHOR_CATALOG.phrases_for('threat')"
        )


def test_r98_zh_reward_unchanged() -> None:
    # R98 plan §3.2 says: 辅小扩只针对 ZH threat, reward 不动。
    # ZH_REWARD_ANCHORS length must remain 5 (R97 first-version) and
    # the set contents unchanged. This guards against accidental reward
    # extension in R98 (which the主人 explicitly declined).
    assert len(ZH_REWARD_ANCHORS) == 5
    assert ZH_REWARD_ANCHORS == (
        "我感到非常喜悦",
        "这是值得庆祝的成就",
        "我获得了渴望的东西",
        "我感到被深深地爱",
        "这是有意义的成功",
    )
