"""Owner: rapid salience appraisal.

Tests for R-PROTO-LEARN.4 (Layer 4 affect-memory pattern completion).

These tests verify:
  1. AffectMemoryRecallSource Protocol can be implemented by a stub.
  2. _apply_affect_memory is no-op when affect_memory_source is None.
  3. _apply_affect_memory is no-op when affect_memory_gain = 0.0.
  4. _apply_affect_memory is no-op when source returns (None, None).
  5. _apply_affect_memory is no-op when content is empty.
  6. _apply_affect_memory blends threat toward recalled_threat.
  7. _apply_affect_memory blends reward toward recalled_reward.
  8. _apply_affect_memory only touches threat and reward (other dims unchanged).
  9. _apply_affect_memory handles partial recall (only threat, only reward).
  10. _apply_affect_memory handles gain=1.0 (recall overrides actual).
  11. _apply_affect_memory handles gain=0.0 (no-op).
  12. _apply_affect_memory clamps non-numeric recalled values to actual.
  13. _apply_affect_memory clamps out-of-range recalled values to [0, 1].
  14. estimate_dimensions auto-applies affect-memory.
  15. Layer 4 integrates cleanly with Layer 1+2+3 (chained calls).
  16. Public surface affect_memory_recall is re-runnable.
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal.engine import (
    AffectMemoryRecallSource,
    GroundedDimensionEstimator,
    RapidDimensionEstimate,
)


class _StubAffectMemory:
    """Stub AffectMemoryRecallSource returning a scripted (threat, reward) recall."""

    def __init__(
        self,
        recall: "tuple[float | None, float | None]" = (None, None),
        call_log: list[str] | None = None,
    ) -> None:
        self._recall = recall
        self._call_log = call_log

    def recall_affect(
        self, content: str
    ) -> "tuple[float | None, float | None]":
        if self._call_log is not None:
            self._call_log.append(content)
        return self._recall


class _StubProtoSource:
    def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
        return 0.0


def _make_estimator(
    *,
    affect_memory_source: AffectMemoryRecallSource | None = None,
    affect_memory_gain: float = 0.2,
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
        affect_memory_source=affect_memory_source,
        affect_memory_gain=affect_memory_gain,
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


def test_affect_memory_recall_source_protocol_shape() -> None:
    stub = _StubAffectMemory(recall=(0.5, 0.3))
    assert isinstance(stub, AffectMemoryRecallSource)


# --------------------------------------------------------------------------- #
# 2-5. No-op paths                                                            #
# --------------------------------------------------------------------------- #


def test_apply_affect_memory_no_source_is_noop() -> None:
    est = _make_estimator(affect_memory_source=None)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out == actual


def test_apply_affect_memory_zero_gain_is_noop() -> None:
    stub = _StubAffectMemory(recall=(0.9, 0.9))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.0)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out == actual


def test_apply_affect_memory_source_returns_none_pair_is_noop() -> None:
    log: list[str] = []
    stub = _StubAffectMemory(recall=(None, None), call_log=log)
    est = _make_estimator(affect_memory_source=stub)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out == actual
    # Source WAS called (to get the None pair).
    assert log == ["x"]


def test_apply_affect_memory_empty_content_is_noop() -> None:
    stub = _StubAffectMemory(recall=(0.9, 0.9))
    log: list[str] = []
    est = _make_estimator(affect_memory_source=stub)
    est._call_log = log
    stub_with_log = _StubAffectMemory(recall=(0.9, 0.9), call_log=log)
    est2 = _make_estimator(affect_memory_source=stub_with_log)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est2._apply_affect_memory(_stimulus(""), actual)
    assert out == actual
    # Empty content: source not called.
    assert log == []


# --------------------------------------------------------------------------- #
# 6-8. Blend arithmetic                                                       #
# --------------------------------------------------------------------------- #


def test_apply_affect_memory_blends_threat_toward_recalled() -> None:
    # gain = 0.2, threat = 0.5, recalled = 0.9
    # final = 0.8 * 0.5 + 0.2 * 0.9 = 0.4 + 0.18 = 0.58
    stub = _StubAffectMemory(recall=(0.9, None))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out.threat == pytest.approx(0.58, rel=1e-3)


def test_apply_affect_memory_blends_reward_toward_recalled() -> None:
    # gain = 0.2, reward = 0.3, recalled = 0.7
    # final = 0.8 * 0.3 + 0.2 * 0.7 = 0.24 + 0.14 = 0.38
    stub = _StubAffectMemory(recall=(None, 0.7))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.0, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out.reward == pytest.approx(0.38, rel=1e-3)


def test_apply_affect_memory_does_not_change_other_dims() -> None:
    stub = _StubAffectMemory(recall=(0.9, 0.9))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.5)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.7, social=0.4, uncertainty=0.2
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    # Only threat/reward changed.
    assert out.novelty == 0.7
    assert out.social == 0.4
    assert out.uncertainty == 0.2


# --------------------------------------------------------------------------- #
# 9. Partial recall                                                            #
# --------------------------------------------------------------------------- #


def test_apply_affect_memory_partial_recall_threat_only() -> None:
    # recalled = (0.9, None): only threat blended; reward stays.
    stub = _StubAffectMemory(recall=(0.9, None))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out.threat == pytest.approx(0.58, rel=1e-3)
    assert out.reward == 0.3  # unchanged


def test_apply_affect_memory_partial_recall_reward_only() -> None:
    # recalled = (None, 0.9): only reward blended; threat stays.
    stub = _StubAffectMemory(recall=(None, 0.9))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out.threat == 0.5  # unchanged
    assert out.reward == pytest.approx(0.42, rel=1e-3)


# --------------------------------------------------------------------------- #
# 10-11. Gain extremes                                                        #
# --------------------------------------------------------------------------- #


def test_apply_affect_memory_gain_one_recall_overrides() -> None:
    stub = _StubAffectMemory(recall=(0.7, 0.6))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=1.0)
    actual = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.5, social=0.5, uncertainty=0.5
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    # gain=1.0 -> 0.0*actual + 1.0*recalled
    assert out.threat == pytest.approx(0.7, rel=1e-3)
    assert out.reward == pytest.approx(0.6, rel=1e-3)
    # other dims unchanged
    assert out.novelty == 0.5


def test_apply_affect_memory_gain_zero_is_noop() -> None:
    stub = _StubAffectMemory(recall=(0.7, 0.6))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.0)
    actual = RapidDimensionEstimate(
        threat=0.1, reward=0.1, novelty=0.5, social=0.5, uncertainty=0.5
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    assert out == actual


# --------------------------------------------------------------------------- #
# 12-13. Recalled value edge cases                                            #
# --------------------------------------------------------------------------- #


def test_apply_affect_memory_non_numeric_recall_treated_as_actual() -> None:
    stub = _StubAffectMemory(recall=("not_a_number", 0.5))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    # Non-numeric threat: silently fall back to actual value (0.5).
    assert out.threat == 0.5
    # Numeric reward: blended normally.
    assert out.reward == pytest.approx(0.34, rel=1e-3)


def test_apply_affect_memory_out_of_range_recall_clamped() -> None:
    stub = _StubAffectMemory(recall=(1.5, -0.5))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_affect_memory(_stimulus("x"), actual)
    # 1.5 -> clamped to 1.0
    # final threat = 0.8 * 0.5 + 0.2 * 1.0 = 0.6
    assert out.threat == pytest.approx(0.6, rel=1e-3)
    # -0.5 -> clamped to 0.0
    # final reward = 0.8 * 0.3 + 0.2 * 0.0 = 0.24
    assert out.reward == pytest.approx(0.24, rel=1e-3)


# --------------------------------------------------------------------------- #
# 14-15. estimate_dimensions integration                                      #
# --------------------------------------------------------------------------- #


def test_estimate_dimensions_auto_applies_affect_memory() -> None:
    # Layer 1 baseline: novelty=1.0, uncertainty=1.0 (no memory).
    # Layer 4 recall: (0.0, 0.0) - no past threat/reward data.
    # gain=0.2: threat = 0.8*0.0 + 0.2*0.0 = 0.0; reward = 0.8*0.0 + 0.2*0.0 = 0.0
    # final: threat=0.0, reward=0.0, novelty=1.0, uncertainty=1.0
    stub = _StubAffectMemory(recall=(0.0, 0.0))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    out = est.estimate_dimensions(_stimulus("x"))
    assert out.threat == 0.0
    assert out.reward == 0.0
    assert out.novelty == 1.0
    assert out.uncertainty == 1.0


def test_estimate_dimensions_layer4_with_past_threat() -> None:
    # Layer 1 baseline: threat=0.0 (R40 stub). recall=(0.9, None).
    # gain=0.5: final threat = 0.5*0.0 + 0.5*0.9 = 0.45
    stub = _StubAffectMemory(recall=(0.9, None))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.5)
    out = est.estimate_dimensions(_stimulus("x"))
    assert out.threat == pytest.approx(0.45, rel=1e-3)


# --------------------------------------------------------------------------- #
# 16. Public surface                                                          #
# --------------------------------------------------------------------------- #


def test_affect_memory_recall_public_surface_returns_new_estimate() -> None:
    stub = _StubAffectMemory(recall=(0.9, 0.9))
    est = _make_estimator(affect_memory_source=stub, affect_memory_gain=0.2)
    actual = RapidDimensionEstimate(
        threat=0.5, reward=0.3, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est.affect_memory_recall(_stimulus("x"), actual)
    # Returns a NEW instance; inputs not mutated.
    assert out is not actual
    # threat blended
    assert out.threat == pytest.approx(0.58, rel=1e-3)
    # input unchanged
    assert actual.threat == 0.5