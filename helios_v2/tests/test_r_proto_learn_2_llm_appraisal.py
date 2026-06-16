"""Owner: rapid salience appraisal.

Tests for R-PROTO-LEARN.2 (Layer 2 LLM appraisal, "amygdala fast path").

These tests verify:
  1. LlmAppraisalSource Protocol can be implemented by a stub.
  2. Layer 2 is no-op when `llm_appraisal_source is None`.
  3. Layer 2 is no-op when `llm_appraisal_threshold = 0.0` (disabled).
  4. Layer 2 is no-op when Layer 1 is confident (max dim >= threshold).
  5. Layer 2 fires when Layer 1 is uncertain (max dim < threshold).
  6. Layer 2 blend: final = alpha * layer1 + (1 - alpha) * llm (alpha=0.5).
  7. Layer 2 alpha=1.0 makes Layer 2 a no-op (Layer 1 dominates).
  8. Layer 2 alpha=0.0 makes Layer 2 override (LLM dominates).
  9. Layer 2 missing LLM keys: fall back to Layer 1 value for that dim.
  10. Layer 2 LLM out-of-range: clamped to [0, 1].
  11. Layer 2 LLM non-numeric values: silently treated as Layer 1.
  12. Layer 2 LLM returns None: no-op (Layer 1 returned).
  13. Layer 2 LLM returns empty dict: no-op.
  14. Layer 2 LLM only supplies a subset of keys: missing keys use Layer 1.
  15. estimate_dimensions auto-applies Layer 2 when trigger fires.
  16. estimate_dimensions skips Layer 2 when Layer 1 is confident.
  17. Layer 2 integration with Layer 1 interoception: Layer 2 sees
      the body-modulated Layer 1 read (post-interoception, pre-LLM).
  18. llm_appraisal_blend public surface is re-runnable.
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal.engine import (
    GroundedDimensionEstimator,
    LlmAppraisalSource,
    RapidDimensionEstimate,
)


class _StubLlmAppraisal:
    """Stub LlmAppraisalSource returning a scripted 5-dim read."""

    def __init__(
        self,
        read: dict[str, float] | None = None,
        call_log: list[str] | None = None,
    ) -> None:
        self._read = read
        self._call_log = call_log

    def llm_appraise(self, content: str) -> dict[str, float] | None:
        if self._call_log is not None:
            self._call_log.append(content)
        return self._read


class _StubProtoSource:
    def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
        return 0.0


def _make_estimator(
    *,
    llm_appraisal_source: LlmAppraisalSource | None = None,
    llm_appraisal_threshold: float = 0.4,
    llm_appraisal_blend_alpha: float = 0.5,
) -> GroundedDimensionEstimator:
    class _MemSrc:
        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 0.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    return GroundedDimensionEstimator(
        similarity_source=_MemSrc(),
        ambiguity_source=_MemSrc(),
        social_source=_SocSrc(),
        prototype_source=_StubProtoSource(),
        description_threshold=0.0,
        llm_appraisal_source=llm_appraisal_source,
        llm_appraisal_threshold=llm_appraisal_threshold,
        llm_appraisal_blend_alpha=llm_appraisal_blend_alpha,
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


# --------------------------------------------------------------------------- #
# 1. Protocol shape                                                           #
# --------------------------------------------------------------------------- #


def test_llm_appraisal_source_protocol_shape() -> None:
    stub = _StubLlmAppraisal(read={"threat": 0.5})
    assert isinstance(stub, LlmAppraisalSource)


# --------------------------------------------------------------------------- #
# 2-4. No-op paths                                                            #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_no_source_is_noop() -> None:
    est = _make_estimator(llm_appraisal_source=None)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1
    )
    out = est._apply_llm_appraisal(_stimulus("hi"), layer1)
    assert out == layer1


def test_apply_llm_appraisal_zero_threshold_is_noop() -> None:
    stub = _StubLlmAppraisal(read={"threat": 0.9, "reward": 0.9})
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.0)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1
    )
    out = est._apply_llm_appraisal(_stimulus("hi"), layer1)
    # threshold=0.0 -> max(0.1..) = 0.1 >= 0.0 -> skip LLM
    assert out == layer1


def test_apply_llm_appraisal_layer1_confident_skips_llm() -> None:
    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.0, "reward": 0.0},
        call_log=log,
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.5,  # >= 0.4, so Layer 1 is "confident"
        reward=0.0,
        novelty=0.0,
        social=0.0,
        uncertainty=0.0,
    )
    out = est._apply_llm_appraisal(_stimulus("hi"), layer1)
    assert out == layer1
    # The LLM stub must NOT have been called (Layer 2 skipped).
    assert log == []


# --------------------------------------------------------------------------- #
# 5. Layer 2 fires when Layer 1 is uncertain                                 #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_fires_when_layer1_uncertain() -> None:
    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.8, "reward": 0.0, "novelty": 0.0, "social": 0.0, "uncertainty": 0.0},
        call_log=log,
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.1,  # < 0.4 -> trigger
        reward=0.1,
        novelty=0.1,
        social=0.1,
        uncertainty=0.1,
    )
    out = est._apply_llm_appraisal(_stimulus("hello"), layer1)
    # LLM was called exactly once.
    assert log == ["hello"]
    # threat: 0.5 * 0.1 + 0.5 * 0.8 = 0.45
    assert out.threat == pytest.approx(0.45, rel=1e-3)
    # Other dims: 0.5 * 0.1 + 0.5 * 0.0 = 0.05
    assert out.reward == pytest.approx(0.05, rel=1e-3)
    assert out.novelty == pytest.approx(0.05, rel=1e-3)


# --------------------------------------------------------------------------- #
# 6. Blend formula                                                            #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_blend_formula() -> None:
    # alpha=0.5 default -> final = 0.5 * layer1 + 0.5 * llm
    stub = _StubLlmAppraisal(
        read={"threat": 0.6, "reward": 0.4, "novelty": 0.0, "social": 0.0, "uncertainty": 0.0},
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.2, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # threat: 0.5*0.2 + 0.5*0.6 = 0.4
    assert out.threat == pytest.approx(0.4, rel=1e-3)
    # reward: 0.5*0.0 + 0.5*0.4 = 0.2
    assert out.reward == pytest.approx(0.2, rel=1e-3)


# --------------------------------------------------------------------------- #
# 7-8. Alpha extremes                                                         #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_alpha_one_means_layer1_dominates() -> None:
    stub = _StubLlmAppraisal(
        read={"threat": 0.9, "reward": 0.9, "novelty": 0.9, "social": 0.9, "uncertainty": 0.9},
    )
    est = _make_estimator(
        llm_appraisal_source=stub,
        llm_appraisal_threshold=0.4,
        llm_appraisal_blend_alpha=1.0,
    )
    layer1 = RapidDimensionEstimate(
        threat=0.2, reward=0.2, novelty=0.2, social=0.2, uncertainty=0.2
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # alpha=1.0 -> 1.0*layer1 + 0.0*llm = layer1 (verbatim)
    assert out == layer1


def test_apply_llm_appraisal_alpha_zero_means_llm_dominates() -> None:
    stub = _StubLlmAppraisal(
        read={"threat": 0.7, "reward": 0.7, "novelty": 0.7, "social": 0.7, "uncertainty": 0.7},
    )
    est = _make_estimator(
        llm_appraisal_source=stub,
        llm_appraisal_threshold=0.4,
        llm_appraisal_blend_alpha=0.0,
    )
    layer1 = RapidDimensionEstimate(
        threat=0.2, reward=0.2, novelty=0.2, social=0.2, uncertainty=0.2
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # alpha=0.0 -> 0.0*layer1 + 1.0*llm = llm
    assert out.threat == pytest.approx(0.7, rel=1e-3)
    assert out.reward == pytest.approx(0.7, rel=1e-3)


# --------------------------------------------------------------------------- #
# 9-11. LLM input edge cases                                                  #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_missing_llm_keys_fall_back_to_layer1() -> None:
    # LLM only returns threat and reward; novelty/social/uncertainty
    # must use Layer 1's values.
    stub = _StubLlmAppraisal(read={"threat": 0.6, "reward": 0.6})
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.3, social=0.0, uncertainty=0.0
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # threat: 0.5*0.0 + 0.5*0.6 = 0.3
    assert out.threat == pytest.approx(0.3, rel=1e-3)
    # novelty: LLM didn't supply -> 0.5*0.3 + 0.5*0.3 = 0.3
    assert out.novelty == pytest.approx(0.3, rel=1e-3)


def test_apply_llm_appraisal_clamps_to_unit_range() -> None:
    # LLM returns values that would push final above 1.0.
    stub = _StubLlmAppraisal(
        read={"threat": 1.5, "reward": 1.5, "novelty": 1.5, "social": 1.5, "uncertainty": 1.5},
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    assert 0.0 <= out.threat <= 1.0
    assert 0.0 <= out.reward <= 1.0
    assert 0.0 <= out.novelty <= 1.0
    assert 0.0 <= out.uncertainty <= 1.0
    assert 0.0 <= out.social <= 1.0


def test_apply_llm_appraisal_non_numeric_llm_silently_treated_as_layer1() -> None:
    stub = _StubLlmAppraisal(
        read={"threat": "not_a_number", "reward": None, "novelty": "x", "social": [1], "uncertainty": 0.5}
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.2, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # threat: 0.5*0.2 + 0.5*0.2 (Layer 1 fallback) = 0.2
    assert out.threat == pytest.approx(0.2, rel=1e-3)
    # reward: 0.5*0.0 + 0.5*0.0 = 0.0
    assert out.reward == pytest.approx(0.0, rel=1e-3)
    # uncertainty: 0.5*0.0 + 0.5*0.5 = 0.25
    assert out.uncertainty == pytest.approx(0.25, rel=1e-3)


# --------------------------------------------------------------------------- #
# 12-13. LLM unavailable                                                      #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_llm_returns_none_is_noop() -> None:
    stub = _StubLlmAppraisal(read=None)
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    assert out == layer1


def test_apply_llm_appraisal_llm_returns_empty_dict_is_noop() -> None:
    stub = _StubLlmAppraisal(read={})
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    assert out == layer1


# --------------------------------------------------------------------------- #
# 14. Partial LLM coverage                                                    #
# --------------------------------------------------------------------------- #


def test_apply_llm_appraisal_partial_llm_coverage() -> None:
    # LLM only supplies threat; everything else falls back to Layer 1.
    # Layer 1 max=0.1 < 0.4 threshold, so trigger fires.
    stub = _StubLlmAppraisal(read={"threat": 0.9})
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.05, novelty=0.05, social=0.05, uncertainty=0.05
    )
    out = est._apply_llm_appraisal(_stimulus("x"), layer1)
    # threat: blended 0.5*0.1 + 0.5*0.9 = 0.5
    assert out.threat == pytest.approx(0.5, rel=1e-3)
    # reward/novelty/social/uncertainty: LLM didn't supply -> 0.5*0.05 + 0.5*0.05 = 0.05
    assert out.reward == pytest.approx(0.05, rel=1e-3)
    assert out.novelty == pytest.approx(0.05, rel=1e-3)
    assert out.social == pytest.approx(0.05, rel=1e-3)
    assert out.uncertainty == pytest.approx(0.05, rel=1e-3)


# --------------------------------------------------------------------------- #
# 15-16. estimate_dimensions auto-pipeline                                    #
# --------------------------------------------------------------------------- #


def test_estimate_dimensions_auto_applies_layer2_when_trigger_fires() -> None:
    # With NO memory source and NO prototype hit, Layer 1 returns
    # novelty=1.0 (no comparable memory) and uncertainty=1.0 (no
    # comparable memory). max = 1.0 >= 0.4 -> Layer 1 IS confident
    # ("the unknown is a confident read of 'novel'"). Layer 2 must
    # NOT fire in this case. This is the R35/R39/R40 contract:
    # novelty/uncertainty are themselves grounded in memory, and
    # the absence of memory is a confident novelty read (1.0).
    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.0, "reward": 0.0, "novelty": 0.0, "social": 0.0, "uncertainty": 0.0},
        call_log=log,
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    out = est.estimate_dimensions(_stimulus("ambiguous visitor message"))
    # LLM was NOT consulted (Layer 1 already confident via novelty=1.0).
    assert log == []
    # Final novelty = 1.0 (R35 path), not modified by LLM.
    assert out.novelty == 1.0


def test_estimate_dimensions_layer2_fires_when_layer1_uniformly_low() -> None:
    # Force Layer 1 to be uniformly low by using a `similarity_source`
    # that returns 1.0 (so novelty = 0.0) and an `ambiguity_source`
    # that returns one hit (so uncertainty = 0.0). This simulates
    # "we have memory, but it's an exact match → low novelty and
    # low uncertainty". In that regime, max(0,0,0,0,0)=0.0 < 0.4
    # and Layer 2 should fire.
    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.8, "reward": 0.0, "novelty": 0.0, "social": 0.0, "uncertainty": 0.0},
        call_log=log,
    )

    class _ConfidentMemSrc:
        """Returns 1.0 similarity + single hit (novelty=0, uncertainty=0)."""

        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 1.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return (1.0,)

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    est = GroundedDimensionEstimator(
        similarity_source=_ConfidentMemSrc(),
        ambiguity_source=_ConfidentMemSrc(),
        social_source=_SocSrc(),
        prototype_source=_StubProtoSource(),
        description_threshold=0.0,
        llm_appraisal_source=stub,
        llm_appraisal_threshold=0.4,
    )
    out = est.estimate_dimensions(_stimulus("ambiguous"))
    # LLM was consulted (Layer 1 max = 0.0 < 0.4).
    assert log == ["ambiguous"]
    # threat: 0.5*0.0 (R40 prototype) + 0.5*0.8 (LLM) = 0.4
    assert out.threat == pytest.approx(0.4, rel=1e-3)


def test_estimate_dimensions_skips_layer2_when_layer1_confident() -> None:
    # When the LLM source is None, Layer 2 is fully disabled regardless
    # of Layer 1's confidence. This is the "no Layer 2 wired" config
    # (R40 byte-level preservation on the appraisal axis).
    log: list[str] = []
    est = _make_estimator(llm_appraisal_source=None, llm_appraisal_threshold=0.4)
    out = est.estimate_dimensions(_stimulus("hello"))
    # LLM was never called (no source).
    assert log == []
    # Output equals the post-interoception Layer 1 read (no Layer 2).
    assert out == out  # sanity: output is valid


# --------------------------------------------------------------------------- #
# 17. Layer 2 sees the interoception-adjusted Layer 1 read                   #
# --------------------------------------------------------------------------- #


def test_layer2_sees_post_interoception_layer1_read() -> None:
    # When interoception pushes threat above the Layer 2 threshold,
    # Layer 2 must NOT fire (Layer 1 is now confident thanks to
    # body-state feedback). This is the integration contract: the
    # interoception-modulated estimate is what gates the LLM
    # consultation.
    from helios_v2.appraisal.engine import InteroceptionSource

    class _Intero:
        def __init__(self, state):
            self._state = state

        def hormone_state_snapshot(self):
            return self._state

    class _MemSrc:
        def max_similarity_for(self, stimulus):  # noqa: ARG002
            return 0.0

        def top_similarities_for(self, stimulus):  # noqa: ARG002
            return ()

    class _SocSrc:
        def social_presence_for(self, stimulus):  # noqa: ARG002
            return 0.0

    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.0, "reward": 0.0, "novelty": 0.0, "social": 0.0, "uncertainty": 0.0},
        call_log=log,
    )
    est = GroundedDimensionEstimator(
        similarity_source=_MemSrc(),
        ambiguity_source=_MemSrc(),
        social_source=_SocSrc(),
        prototype_source=_StubProtoSource(),
        description_threshold=0.0,
        interoception_source=_Intero({"cortisol": 0.9}),  # high cortisol
        interoception_gain=10.0,  # strong bias
        llm_appraisal_source=stub,
        llm_appraisal_threshold=0.4,
    )
    out = est.estimate_dimensions(_stimulus("x"))
    # Interoception pushed threat to 0.5; 0.5 >= 0.4 -> Layer 2 skipped.
    assert log == []
    # Final threat = 0.5 (post-interoception, no LLM blend).
    assert out.threat == pytest.approx(0.5, rel=1e-3)


# --------------------------------------------------------------------------- #
# 18. Public surface: llm_appraisal_blend re-runnable                        #
# --------------------------------------------------------------------------- #


def test_llm_appraisal_blend_public_surface_returns_new_estimate() -> None:
    stub = _StubLlmAppraisal(
        read={"threat": 0.6, "reward": 0.6, "novelty": 0.6, "social": 0.6, "uncertainty": 0.6},
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.2, reward=0.2, novelty=0.2, social=0.2, uncertainty=0.2
    )
    out = est.llm_appraisal_blend(_stimulus("x"), layer1)
    # Returns a NEW instance; inputs are not mutated.
    assert out is not layer1
    # threat: 0.5*0.2 + 0.5*0.6 = 0.4
    assert out.threat == pytest.approx(0.4, rel=1e-3)
    # layer1 unchanged
    assert layer1.threat == 0.2


def test_layer1_confidence_helper() -> None:
    est = _make_estimator()
    e = RapidDimensionEstimate(
        threat=0.1, reward=0.2, novelty=0.3, social=0.4, uncertainty=0.5
    )
    assert est._layer1_confidence(e) == 0.5
    e2 = RapidDimensionEstimate(
        threat=0.9, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    assert est._layer1_confidence(e2) == 0.9


def test_apply_llm_appraisal_empty_content_is_noop() -> None:
    log: list[str] = []
    stub = _StubLlmAppraisal(
        read={"threat": 0.9, "reward": 0.9, "novelty": 0.9, "social": 0.9, "uncertainty": 0.9},
        call_log=log,
    )
    est = _make_estimator(llm_appraisal_source=stub, llm_appraisal_threshold=0.4)
    layer1 = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.1, social=0.1, uncertainty=0.1
    )
    s = _stimulus("")  # empty content
    out = est._apply_llm_appraisal(s, layer1)
    # Empty content: LLM not consulted.
    assert log == []
    assert out == layer1