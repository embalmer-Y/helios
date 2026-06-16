"""Owner: rapid salience appraisal.

R97 (去英文中心 / 中文 appraisal grounding) introduces a multilingual
anchor catalog to close the B3 root cause identified in ROADMAP §9.1:
the R40 prototype phrases are English-only, so a Chinese emotion
input scores near-zero cosine against the English anchors and the
appraisal owner's `threat` / `reward` dimensions collapse to noise
on Chinese input. R96 (real-semantic embedding) closes the upstream
embedding root cause (B2); R97 closes the downstream anchor root
cause (B3).

This module owns the `AnchorCatalog` data structure. The catalog is
a frozen collection of `AnchorSet`s, where each `AnchorSet` is a
`(language, dimension, phrases)` triple. The `03` appraisal owner
remains the sole authority on the meaning of the dimension strings
("threat" / "reward"); composition injects the catalog as a whole
and the owner consumes it via `phrases_for(dimension)` and
`sets_for(dimension)`.

The first-version `DEFAULT_ANCHOR_CATALOG` is bilingual (Chinese +
English anchors for both threat and reward). The Chinese phrases are
hand-authored + PANAS-X 中文翻译, with the same `C_engineering_hypothesis`
grounding as the original R40 English anchors. They are NOT learned
in this slice; the catalog is the clean P5 learning-loop replacement
seam (a learned catalog is just `AnchorCatalog(sets=learned_sets)`
injected at the same composition seam).

R97 does NOT change any owner contract; the `03` appraisal owner's
threat / reward scoring still uses `PrototypeSimilaritySource`
(composition glue) + `max_cosine_to_prototypes` (owner-owned
mapping). The only change is that the estimator now also queries
the catalog's per-dimension phrases, and takes the max-of-max
across (R40 prototypes) and (catalog phrases for the same
dimension). Both the original R40 prototypes and the catalog are
injectable fields; both default to the English anchor sets, so the
R40 byte-level behavior is preserved when no catalog is injected.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnchorSet:
    """A named prototype phrase set; one set = one (language, dimension) candidate.

    Owner: rapid salience appraisal.

    Purpose:
        Bind a (language, dimension) label to a tuple of phrase anchors. The dimension
        string carries no intrinsic semantic — it is the appraisal owner's interpretation
        that maps "threat" / "reward" to the appraisal contract. This dataclass is the
        pure-data substrate: it knows the phrases and the label, not the salience
        meaning.

        `description` (R-PROTO-LEARN.6, Layer 1 fallback): a parallel tuple of
        LLM-friendly descriptions, one per phrase. When `phrases` themselves score
        below the `description_threshold` against an input, the owner falls back to
        the description embeddings. This implements the EmoGist (arXiv:2505.14660)
        context-dependent retrieval idea at the catalog layer: a phrase like
        "胸口闷得慌" may not appear verbatim, but its description "internalized
        anxiety manifested as chest pressure" should match a similar input.
        `description` defaults to `()` (no description fallback) so that all
        pre-R-PROTO-LEARN.6 AnchorSet callers remain byte-level compatible.

    Failure semantics:
        Construction fails fast on empty `phrases`. The `language` and `dimension`
        fields are free-form strings; the owner is responsible for any further validation
        (e.g. `dimension in {"threat", "reward"}`). When `description` is non-empty,
        it must have the same length as `phrases` (1:1 correspondence by index).

    Notes:
        Frozen: the catalog is immutable once constructed. A future P5 learned catalog
        is just a new `AnchorCatalog(sets=learned_sets)` instance injected at the same
        composition seam; the dataclass does not need to learn a mutable variant.
    """

    language: str
    dimension: str
    phrases: tuple[str, ...]
    description: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.phrases:
            raise ValueError(
                f"AnchorSet(language={self.language!r}, dimension={self.dimension!r}) "
                f"must declare a non-empty `phrases` tuple"
            )
        for phrase in self.phrases:
            if not isinstance(phrase, str) or not phrase.strip():
                raise ValueError(
                    f"AnchorSet phrases must be non-empty strings, got {phrase!r}"
                )
        if self.description:
            if len(self.description) != len(self.phrases):
                raise ValueError(
                    f"AnchorSet(language={self.language!r}, dimension={self.dimension!r}) "
                    f"`description` length ({len(self.description)}) must match `phrases` "
                    f"length ({len(self.phrases)})"
                )
            for desc in self.description:
                if not isinstance(desc, str) or not desc.strip():
                    raise ValueError(
                        f"AnchorSet description entries must be non-empty strings, got {desc!r}"
                    )


@dataclass(frozen=True)
class AnchorCatalog:
    """Owner: rapid salience appraisal. The appraisal owner's first-version anchor catalog.

    A list of `AnchorSet`s. R97 ships the bilingual first-version (Chinese + English
    anchors for both threat and reward). P5 learning can replace this with a learned
    catalog at the same injection seam.

    The catalog is owner-owned: the appraisal owner decides which set means "threat"
    and which means "reward"; composition injects the catalog as a whole and the
    owner consumes it through `phrases_for(dimension)` and `sets_for(dimension)`.

    Failure semantics:
        Construction fails fast on empty `sets`. The `dimension` strings are not
        validated here — the appraisal owner is responsible for any further
        interpretation. The `phrases_for(dimension)` and `sets_for(dimension)`
        queries return an empty tuple when no set matches the requested dimension;
        the owner is responsible for treating the empty-catalog case as a
        no-comparable-input signal.

    Notes:
        Frozen: the catalog is immutable once constructed. A P5 learned catalog
        is a new `AnchorCatalog(sets=learned_sets)` instance.
    """

    sets: tuple[AnchorSet, ...]

    def __post_init__(self) -> None:
        if not self.sets:
            raise ValueError("AnchorCatalog must declare a non-empty `sets` tuple")

    def phrases_for(self, dimension: str) -> tuple[str, ...]:
        """Return the union of phrases across all sets whose `dimension` matches.

        The returned tuple preserves the order of the input `sets` (stable iteration
        order is required for deterministic cosine-cache keying in the composition
        source). Phrases are not deduplicated: two sets with the same dimension and
        the same phrase will both appear in the union (the source's
        `_prototype_cache` keys on the tuple id, not on the contents).
        """
        return tuple(
            phrase
            for anchor_set in self.sets
            if anchor_set.dimension == dimension
            for phrase in anchor_set.phrases
        )

    def sets_for(self, dimension: str) -> tuple[AnchorSet, ...]:
        """Return the sets whose `dimension` matches (preserving language information)."""
        return tuple(s for s in self.sets if s.dimension == dimension)

    def languages_for(self, dimension: str) -> tuple[str, ...]:
        """Return the distinct language codes covered by sets of the given dimension."""
        seen: list[str] = []
        for s in self.sets_for(dimension):
            if s.language not in seen:
                seen.append(s.language)
        return tuple(seen)

    def descriptions_for(self, dimension: str) -> tuple[str, ...]:
        """Return the union of description entries across all sets of the given dimension.

        R-PROTO-LEARN.6 (Layer 1 fallback, EmoGist context-dependent retrieval):
        parallel to `phrases_for(dimension)`, but returns the description strings
        instead of the phrase strings. Sets that declare `description=()` contribute
        nothing. Empty tuple = no description fallback available for this dimension.
        """
        return tuple(
            desc
            for anchor_set in self.sets
            if anchor_set.dimension == dimension
            for desc in anchor_set.description
        )


# --------------------------------------------------------------------------- #
# First-version Chinese threat / reward anchors (R97).                        #
# --------------------------------------------------------------------------- #


# Hand-authored + PANAS-X 中文简版翻译 + 中文情感词汇本体库子集。每一短语都
# 选用具区分度的具体动词/名词而非抽象概念；选词原则：
#   - 威胁：被攻击 / 危险 / 恐惧 / 受伤 / 紧急 等具身体感受的描述
#   - 奖励：喜悦 / 渴望 / 成就 / 爱 / 成功 等具积极情感唤起的描述
# 这些 anchor 是 R97 的首版 PLACEHOLDER 锚点，grounding 是
# `C_engineering_hypothesis`（与 R40 英文 anchor 同级别）；P5 学习循环将
# 在保留 API 兼容的前提下替换为 learned catalog。
#
# R98 (post-LLM appraisal adjustment) adds 6 医学共识症状短语（Set A）:
# 这些是 DSM-5 / ICD-11 焦虑和抑郁诊断标准中的核心身体症状，
# 用于兜底 R97 枚举对"情境类情绪"（anxiety/grief/loneliness）的漏检。
# 注意：EN 子集不动（保持 R40 byte-level preservation 原则）；
# catalog 极小扩只针对 ZH threat（reward 不扩——现有 anchor 已能抓"成就感"类）。
ZH_THREAT_ANCHORS: tuple[str, ...] = (
    "我正在被攻击",
    "有危险在逼近",
    "我感到非常恐惧",
    "这会造成严重伤害",
    "紧急情况正在发生",
    # R98 Set A: 医学共识身体症状 (DSM-5/ICD-11 焦虑 / 抑郁 / 急性 distress)
    "我心跳加速心慌",
    "我整夜失眠睡不着",
    "我手心冒汗发抖",
    "我脑子停不下来",
    "我发高烧很难受",
    "家里静得让人害怕",
)
# R-PROTO-LEARN.6 (Layer 1 fallback, EmoGist context-dependent retrieval):
# description tuple parallel to ZH_THREAT_ANCHORS (1:1 by index). These are
# LLM-friendly paraphrases that better capture the affective meaning, so when
# the surface phrase itself scores low against a novel input (e.g. "胸口闷得
# 慌"), the description can still match via semantic embedding. Hand-authored;
# grounding is `C_engineering_hypothesis` (placeholder, same level as phrases).
ZH_THREAT_DESCRIPTIONS: tuple[str, ...] = (
    "active hostility directed at me, feeling of being under attack",
    "an imminent danger approaching me from outside",
    "an overwhelming acute fear response, panic-like arousal",
    "anticipated serious physical or psychological harm",
    "an emergency situation unfolding right now requiring urgent action",
    # R98 Set A descriptions (DSM-5/ICD-11 somatic symptoms of anxiety/depression)
    "tachycardia and palpitations, acute autonomic arousal from anxiety",
    "prolonged insomnia, inability to fall asleep, restless wakefulness",
    "palmar hyperhidrosis and tremor, somatic anxiety manifestation",
    "racing thoughts, intrusive cognitions, mental restlessness",
    "high fever and physical discomfort, body in acute distress",
    "loneliness and isolation, ambient silence triggering fear",
)
ZH_REWARD_ANCHORS: tuple[str, ...] = (
    "我感到非常喜悦",
    "这是值得庆祝的成就",
    "我获得了渴望的东西",
    "我感到被深深地爱",
    "这是有意义的成功",
)
# R-PROTO-LEARN.6 (Layer 1 fallback): description parallel to ZH_REWARD_ANCHORS.
ZH_REWARD_DESCRIPTIONS: tuple[str, ...] = (
    "an acute joy or happiness, positive emotional peak",
    "a celebrated achievement, sense of accomplishment",
    "the acquisition of a strongly desired object or goal",
    "deep feeling of being loved, secure attachment activation",
    "a meaningful success, purpose-aligned accomplishment",
)


# --------------------------------------------------------------------------- #
# Default bilingual anchor catalog (R97 ship).                                #
# --------------------------------------------------------------------------- #


# Late-bound reference to the R40 module-level constants. We need the
# `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` values at `DEFAULT_ANCHOR_CATALOG`
# construction time; importing them at module top would create a circular
# import (`appraisal.engine` imports from this module via the catalog, and
# this module is imported by `appraisal/__init__.py` which also imports
# `appraisal.engine`). The import is therefore local to the construction
# call.
def _build_default_catalog() -> AnchorCatalog:
    from .engine import REWARD_PROTOTYPES as _EN_REWARD, THREAT_PROTOTYPES as _EN_THREAT
    return AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=ZH_THREAT_ANCHORS,
                description=ZH_THREAT_DESCRIPTIONS,
            ),
            AnchorSet(
                language="zh",
                dimension="reward",
                phrases=ZH_REWARD_ANCHORS,
                description=ZH_REWARD_DESCRIPTIONS,
            ),
            # EN aliases — these are the same tuple objects as the R40 module
            # constants, so editing `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` in
            # `appraisal.engine` automatically propagates to the catalog without
            # any data drift. (The R40 path remains the canonical English source.)
            # No description on EN sets: keeps R40 byte-level preservation.
            AnchorSet(language="en", dimension="threat", phrases=_EN_THREAT),
            AnchorSet(language="en", dimension="reward", phrases=_EN_REWARD),
        )
    )


# The first-version bilingual catalog. Built lazily so the EN alias references
# resolve at import time (not at module-definition time, when
# `THREAT_PROTOTYPES` is not yet bound because `appraisal.engine` has not been
# imported into this module's namespace).
DEFAULT_ANCHOR_CATALOG: AnchorCatalog = _build_default_catalog()
