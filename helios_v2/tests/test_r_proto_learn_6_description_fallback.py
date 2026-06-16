"""Owner: rapid salience appraisal.

Tests for R-PROTO-LEARN.6 (Layer 1 fallback, EmoGist context-dependent retrieval).

These tests verify:
  1. AnchorSet accepts a `description` tuple parallel to `phrases`.
  2. AnchorSet.__post_init__ enforces 1:1 length parity between phrases and description.
  3. AnchorCatalog.descriptions_for(dimension) returns the union of descriptions
     across sets of that dimension (skipping sets with empty description).
  4. GroundedDimensionEstimator runs the description fallback when the phrase-level
     max is below `description_threshold` AND the catalog has descriptions.
  5. GroundedDimensionEstimator skips the description fallback when the phrase-level
     max is at or above `description_threshold`.
  6. The EN subset of `DEFAULT_ANCHOR_CATALOG` has empty descriptions (R40 byte-level
     preservation: the English path is unaffected).
  7. `_max_of_three_scaled` returns 0.0 only when all three inputs are None.
  8. Description fallback raises `RapidAppraisalError` (hard stop) when prototype_source
     fails on description path — no silent degradation.

Grounding:
    These tests are owner-internal acceptance; they are not on the public API.
    The hard-stop semantics is preserved per the existing R40/R97 path: a source failure
    is propagated, never swallowed.
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal.anchor_catalog import (
    DEFAULT_ANCHOR_CATALOG,
    AnchorCatalog,
    AnchorSet,
)
from helios_v2.appraisal.engine import (
    GroundedDimensionEstimator,
    PrototypeSimilaritySource,
    RapidAppraisalError,
    _max_of_three_scaled,
)
from helios_v2.sensory import Stimulus


# --------------------------------------------------------------------------- #
# Stubs                                                                     #
# --------------------------------------------------------------------------- #


class _StubPrototypeSource:
    """Stub that returns scripted cosine similarities per phrase-set call.

    A `cosines` mapping maps `tuple(prototypes)` to a `float | None` result.
    Unmapped calls return `None`.
    """

    def __init__(self, cosines: dict[tuple[str, ...], float | None] | None = None) -> None:
        # Use a list of (prototypes, value) pairs to support unhashable inputs in tests
        # if needed; but for our test we always pass tuples of strings, so dict is fine.
        self._cosines: dict[tuple[str, ...], float | None] = dict(cosines or {})

    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        return self._cosines.get(prototypes)


class _FailingPrototypeSource:
    """Prototype source that always raises to test hard-stop propagation."""

    def max_similarity_to(self, stimulus: Stimulus, prototypes: tuple[str, ...]) -> float | None:
        raise RapidAppraisalError("simulated description path failure")


def _stub_memory_source() -> object:
    from helios_v2.appraisal.engine import MemorySimilaritySource, RetrievalAmbiguitySource, SocialContextSource

    class _MemSrc:
        def max_similarity_for(self, stimulus: Stimulus) -> float | None:
            return 0.0

        def top_similarities_for(self, stimulus: Stimulus) -> tuple[float, ...]:
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus: Stimulus) -> float:
            return 0.0

    return _MemSrc(), _SocSrc()


def _make_estimator(
    prototype_source: PrototypeSimilaritySource,
    *,
    description_threshold: float = 1.0,
    catalog: AnchorCatalog = DEFAULT_ANCHOR_CATALOG,
) -> GroundedDimensionEstimator:
    mem_src, soc_src = _stub_memory_source()
    return GroundedDimensionEstimator(
        similarity_source=mem_src,
        ambiguity_source=mem_src,
        social_source=soc_src,
        prototype_source=prototype_source,
        anchor_catalog=catalog,
        description_threshold=description_threshold,
    )


def _stimulus(text: str = "test") -> Stimulus:
    return Stimulus(
        stimulus_id="s1",
        source_name="test",
        modality="text",
        content=text,
        channel=None,
        metadata=None,
        provenance_signal_id="p1",
    )


# --------------------------------------------------------------------------- #
# 1. AnchorSet accepts description                                           #
# --------------------------------------------------------------------------- #


def test_anchor_set_with_description_constructs() -> None:
    s = AnchorSet(
        language="zh",
        dimension="threat",
        phrases=("我正在被攻击",),
        description=("active hostility directed at me",),
    )
    assert s.description == ("active hostility directed at me",)


def test_anchor_set_default_description_is_empty() -> None:
    s = AnchorSet(language="en", dimension="threat", phrases=("attacked",))
    assert s.description == ()


def test_anchor_set_description_length_must_match_phrases() -> None:
    with pytest.raises(ValueError, match="length"):
        AnchorSet(
            language="zh",
            dimension="threat",
            phrases=("a", "b"),
            description=("only one",),
        )


def test_anchor_set_description_must_be_non_empty_strings() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        AnchorSet(
            language="zh",
            dimension="threat",
            phrases=("a",),
            description=("  ",),
        )


# --------------------------------------------------------------------------- #
# 2. AnchorCatalog.descriptions_for(dimension)                              #
# --------------------------------------------------------------------------- #


def test_catalog_descriptions_for_returns_union() -> None:
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("p1", "p2"),
                description=("d1", "d2"),
            ),
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("p3",),
                description=("d3",),
            ),
        )
    )
    out = catalog.descriptions_for("threat")
    assert out == ("d1", "d2", "d3")


def test_catalog_descriptions_for_skips_empty_description_sets() -> None:
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("p1",),
                description=("d1",),
            ),
            # EN set: no description (R40 byte-level preservation)
            AnchorSet(language="en", dimension="threat", phrases=("attacked",)),
        )
    )
    out = catalog.descriptions_for("threat")
    assert out == ("d1",)


def test_catalog_descriptions_for_unknown_dimension_returns_empty() -> None:
    out = DEFAULT_ANCHOR_CATALOG.descriptions_for("nonexistent")
    assert out == ()


def test_catalog_descriptions_for_reward_returns_zh_only() -> None:
    out = DEFAULT_ANCHOR_CATALOG.descriptions_for("reward")
    assert len(out) == 5  # 5 ZH_REWARD_ANCHORS / descriptions
    # All entries are non-empty English-ish descriptions
    assert all(isinstance(d, str) and d.strip() for d in out)


def test_catalog_descriptions_for_threat_returns_zh_only() -> None:
    out = DEFAULT_ANCHOR_CATALOG.descriptions_for("threat")
    assert len(out) == 11  # 11 ZH_THREAT_ANCHORS / descriptions


def test_default_catalog_en_subsets_have_no_descriptions() -> None:
    # Build a tiny catalog with EN sets only and check description_for returns ().
    from helios_v2.appraisal.anchor_catalog import AnchorCatalog as _AC, AnchorSet as _AS

    en_only = _AC(
        sets=(
            _AS(language="en", dimension="threat", phrases=("attacked", "in danger")),
        )
    )
    assert en_only.descriptions_for("threat") == ()


# --------------------------------------------------------------------------- #
# 3. _max_of_three_scaled                                                   #
# --------------------------------------------------------------------------- #


def test_max_of_three_all_none_returns_zero() -> None:
    assert _max_of_three_scaled(None, None, None, gain=1.0) == 0.0


def test_max_of_three_one_value() -> None:
    assert _max_of_three_scaled(0.5, None, None, gain=1.0) == 0.5


def test_max_of_three_two_values() -> None:
    assert _max_of_three_scaled(0.5, 0.3, None, gain=1.0) == 0.5


def test_max_of_three_three_values_takes_max() -> None:
    assert _max_of_three_scaled(0.5, 0.3, 0.7, gain=1.0) == 0.7


def test_max_of_three_with_gain_applied_to_max() -> None:
    assert _max_of_three_scaled(None, None, 0.4, gain=2.0) == 0.8


def test_max_of_three_clamps_to_unit_after_gain() -> None:
    assert _max_of_three_scaled(None, None, 0.9, gain=2.0) == 1.0


def test_max_of_three_clamps_negative_to_zero() -> None:
    assert _max_of_three_scaled(-0.5, None, None, gain=1.0) == 0.0


# --------------------------------------------------------------------------- #
# 4. Description fallback runs when phrase-level max < threshold            #
# --------------------------------------------------------------------------- #


def test_description_fallback_runs_when_phrase_max_low() -> None:
    # Build a custom catalog with descriptions and phrase that score below threshold.
    # threshold=0.5 means "fall back when phrase_max < 0.5".
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("phrase_with_no_match",),
                description=("description that scores higher",),
            ),
        )
    )
    src = _StubPrototypeSource(
        cosines={
            ("phrase_with_no_match",): 0.1,  # below 0.5 threshold
            ("description that scores higher",): 0.9,
        }
    )
    est = _make_estimator(src, description_threshold=0.5, catalog=catalog)
    out = est.estimate_dimensions(_stimulus())
    # description path was triggered and contributed 0.9; final threat is gain*0.9 = 0.9
    assert out.threat == 0.9


def test_description_fallback_skipped_when_phrase_max_high() -> None:
    # threshold=0.5; phrase_max=0.8 >= 0.5 => description path skipped.
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("phrase_that_matches",),
                description=("description that scores higher",),
            ),
        )
    )
    src = _StubPrototypeSource(
        cosines={
            ("phrase_that_matches",): 0.8,  # >= 0.5 threshold
            ("description that scores higher",): 0.9,
        }
    )
    est = _make_estimator(src, description_threshold=0.5, catalog=catalog)
    out = est.estimate_dimensions(_stimulus())
    # description path was skipped; final threat is gain*0.8 = 0.8
    assert out.threat == 0.8


def test_description_fallback_default_threshold_one_always_runs() -> None:
    # Default `description_threshold=1.0` means description ALWAYS runs when
    # descriptions exist (since phrase_max < 1.0 is always True for non-1.0 matches).
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("any_phrase",),
                description=("a description",),
            ),
        )
    )
    src = _StubPrototypeSource(
        cosines={
            ("any_phrase",): 0.0,
            ("a description",): 0.7,
        }
    )
    est = _make_estimator(src, catalog=catalog)  # default threshold = 1.0
    out = est.estimate_dimensions(_stimulus())
    # description path runs (0.0 < 1.0); final threat = 0.7
    assert out.threat == 0.7


def test_description_fallback_threshold_zero_disables_path() -> None:
    # threshold=0.0 means description path NEVER runs (any phrase_max >= 0.0).
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("any_phrase",),
                description=("a description",),
            ),
        )
    )
    src = _StubPrototypeSource(
        cosines={
            ("any_phrase",): 0.5,
            ("a description",): 0.9,
        }
    )
    est = _make_estimator(src, description_threshold=0.0, catalog=catalog)
    out = est.estimate_dimensions(_stimulus())
    # description NOT run (0.5 < 0.0 = False); final threat = 0.5
    assert out.threat == 0.5


def test_description_fallback_no_descriptions_skips_silently() -> None:
    # Catalog has no descriptions for "threat" (e.g. EN-only catalog).
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(language="en", dimension="threat", phrases=("any_phrase",)),
        )
    )
    src = _StubPrototypeSource(
        cosines={
            ("any_phrase",): 0.5,
        }
    )
    est = _make_estimator(src, description_threshold=0.0, catalog=catalog)
    out = est.estimate_dimensions(_stimulus())
    # No descriptions => description path skipped; final threat = 0.5
    assert out.threat == 0.5


# --------------------------------------------------------------------------- #
# 5. Hard-stop on description path failure                                   #
# --------------------------------------------------------------------------- #


def test_description_fallback_failure_propagates_hard_stop() -> None:
    # When the prototype_source fails on the description path, the estimator must
    # propagate as a hard stop (no silent degradation to phrase-level-only).
    catalog = AnchorCatalog(
        sets=(
            AnchorSet(
                language="zh",
                dimension="threat",
                phrases=("any_phrase",),
                description=("a description",),
            ),
        )
    )
    failing_src = _FailingPrototypeSource()
    est = _make_estimator(failing_src, description_threshold=0.0, catalog=catalog)
    with pytest.raises(RapidAppraisalError, match="simulated description path failure"):
        est.estimate_dimensions(_stimulus())


# --------------------------------------------------------------------------- #
# 6. Default catalog has ZH threat/reward descriptions, EN does not          #
# --------------------------------------------------------------------------- #


def test_default_catalog_zh_threat_has_descriptions() -> None:
    descs = DEFAULT_ANCHOR_CATALOG.descriptions_for("threat")
    # All 11 ZH_THREAT_ANCHORS have a description
    assert len(descs) == 11


def test_default_catalog_zh_reward_has_descriptions() -> None:
    descs = DEFAULT_ANCHOR_CATALOG.descriptions_for("reward")
    # All 5 ZH_REWARD_ANCHORS have a description
    assert len(descs) == 5


def test_default_catalog_en_threat_no_descriptions() -> None:
    # Build an EN-only catalog to confirm EN sets have no descriptions.
    from helios_v2.appraisal.engine import REWARD_PROTOTYPES, THREAT_PROTOTYPES

    en_only = AnchorCatalog(
        sets=(
            AnchorSet(language="en", dimension="threat", phrases=THREAT_PROTOTYPES),
            AnchorSet(language="en", dimension="reward", phrases=REWARD_PROTOTYPES),
        )
    )
    assert en_only.descriptions_for("threat") == ()
    assert en_only.descriptions_for("reward") == ()


# --------------------------------------------------------------------------- #
# 7. R40 byte-level preservation: DEFAULT_ANCHOR_CATALOG EN path unchanged  #
# --------------------------------------------------------------------------- #


def test_default_catalog_en_subsets_have_empty_description() -> None:
    # The R97 ship invariant: EN subsets of DEFAULT_ANCHOR_CATALOG alias the
    # R40 module constants and have empty `description`. The R40 byte-level
    # preservation depends on this.
    en_threat_sets = DEFAULT_ANCHOR_CATALOG.sets_for("threat")
    en_threat_sets = tuple(s for s in en_threat_sets if s.language == "en")
    assert en_threat_sets, "expected at least one EN threat set"
    for s in en_threat_sets:
        assert s.description == ()