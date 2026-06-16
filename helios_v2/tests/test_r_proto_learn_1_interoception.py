"""Owner: rapid salience appraisal.

Tests for R-PROTO-LEARN.1 (Layer 1 interoception, hormone -> appraisal).

These tests verify:
  1. InteroceptionSource Protocol can be implemented by a stub.
  2. GroundedDimensionEstimator._apply_interoception is a no-op when
     interoception_source is None (cold start).
  3. _apply_interoception is a no-op when gain = 0.0 (R40 byte-level
     preservation on the interoception axis).
  4. _apply_interoception is a no-op when hormone state is None.
  5. cortisol > 0.7 raises threat by +0.05 * gain (default 0.1 -> +0.005).
  6. cortisol < 0.3 lowers threat by -0.02 * gain.
  7. oxytocin > 0.7 raises reward by +0.05 * gain.
  8. serotonin > 0.7 lowers uncertainty by -0.03 * gain.
  9. dopamine > 0.7 lowers novelty by -0.03 * gain.
  10. norepinephrine > 0.7 raises uncertainty by +0.04 * gain.
  11. inhibition > 0.7 raises novelty by +0.04 * gain.
  12. estimate_dimensions auto-applies interoception adjustment (returns
      the adjusted estimate, not the raw stimulus-only read).
  13. The adjustment clamps to [0, 1] per dimension (no out-of-range).
  14. Multiple channels can fire simultaneously; the final estimate is
      the union of all biases (capped at the per-dimension [0, 1] range).
  15. R-PROTO-LEARN.1 is independent of the Layer 5 Bayesian update
      (concept_prior observation uses the pre-bias estimate).
"""

from __future__ import annotations

import pytest

from helios_v2.appraisal.engine import (
    GroundedDimensionEstimator,
    InteroceptionSource,
    RapidDimensionEstimate,
)


class _StubInteroception:
    """Stub InteroceptionSource returning a scripted hormone state."""

    def __init__(self, state: dict[str, float] | None) -> None:
        self._state = state

    def hormone_state_snapshot(self) -> dict[str, float] | None:
        return self._state


class _StubProtoSource:
    def max_similarity_to(self, stimulus, prototypes):  # noqa: ARG002
        return 0.0


def _make_estimator(
    *,
    interoception_source: InteroceptionSource | None = None,
    interoception_gain: float = 0.1,
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
        description_threshold=0.0,  # disable description path for determinism
        interoception_source=interoception_source,
        interoception_gain=interoception_gain,
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
# 1. InteroceptionSource Protocol shape                                      #
# --------------------------------------------------------------------------- #


def test_interoception_source_protocol_shape() -> None:
    # The stub implements the Protocol; runtime_checkable should accept it.
    stub = _StubInteroception(state={"cortisol": 0.5})
    assert isinstance(stub, InteroceptionSource)


# --------------------------------------------------------------------------- #
# 2-4. No-op paths                                                            #
# --------------------------------------------------------------------------- #


def test_apply_interoception_no_source_is_noop() -> None:
    est = _make_estimator(interoception_source=None)
    base = RapidDimensionEstimate(
        threat=0.3, reward=0.4, novelty=0.5, social=0.2, uncertainty=0.6
    )
    out = est._apply_interoception(base)
    assert out == base


def test_apply_interoception_zero_gain_is_noop() -> None:
    src = _StubInteroception(state={"cortisol": 0.9, "oxytocin": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=0.0)
    base = RapidDimensionEstimate(
        threat=0.3, reward=0.4, novelty=0.5, social=0.2, uncertainty=0.6
    )
    out = est._apply_interoception(base)
    assert out == base


def test_apply_interoception_none_state_is_noop() -> None:
    src = _StubInteroception(state=None)
    est = _make_estimator(interoception_source=src)
    base = RapidDimensionEstimate(
        threat=0.3, reward=0.4, novelty=0.5, social=0.2, uncertainty=0.6
    )
    out = est._apply_interoception(base)
    assert out == base


# --------------------------------------------------------------------------- #
# 5-11. Single-channel bias                                                  #
# --------------------------------------------------------------------------- #


def test_cortisol_high_raises_threat() -> None:
    src = _StubInteroception(state={"cortisol": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    # +0.05 * 0.1 = +0.005
    assert out.threat == pytest.approx(0.505, rel=1e-3)


def test_cortisol_low_lowers_threat() -> None:
    src = _StubInteroception(state={"cortisol": 0.2})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    # -0.02 * 0.1 = -0.002
    assert out.threat == pytest.approx(0.498, rel=1e-3)


def test_oxytocin_high_raises_reward() -> None:
    src = _StubInteroception(state={"oxytocin": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.5, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    assert out.reward == pytest.approx(0.505, rel=1e-3)


def test_oxytocin_low_lowers_reward() -> None:
    src = _StubInteroception(state={"oxytocin": 0.2})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.5, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    assert out.reward == pytest.approx(0.498, rel=1e-3)


def test_serotonin_high_lowers_uncertainty() -> None:
    src = _StubInteroception(state={"serotonin": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.5
    )
    out = est._apply_interoception(base)
    assert out.uncertainty == pytest.approx(0.497, rel=1e-3)


def test_dopamine_high_lowers_novelty() -> None:
    src = _StubInteroception(state={"dopamine": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.5, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    assert out.novelty == pytest.approx(0.497, rel=1e-3)


def test_norepinephrine_high_raises_uncertainty() -> None:
    src = _StubInteroception(state={"norepinephrine": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.5
    )
    out = est._apply_interoception(base)
    # +0.04 * 0.1 = +0.004
    assert out.uncertainty == pytest.approx(0.504, rel=1e-3)


def test_inhibition_high_raises_novelty() -> None:
    src = _StubInteroception(state={"inhibition": 0.8})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.0, reward=0.0, novelty=0.5, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    assert out.novelty == pytest.approx(0.504, rel=1e-3)


# --------------------------------------------------------------------------- #
# 12. estimate_dimensions auto-applies interoception                        #
# --------------------------------------------------------------------------- #


def test_estimate_dimensions_applies_interoception_to_output() -> None:
    # Build an estimator with hormone state that would shift threat upward,
    # and a stimulus that produces threat = 0.0 from R40 (default prototypes
    # score 0.0). The output should reflect the interoception bias.
    src = _StubInteroception(state={"cortisol": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    out = est.estimate_dimensions(_stimulus())
    # threat = 0.0 (R40) + 0.005 (interoception) = 0.005
    assert out.threat == pytest.approx(0.005, rel=1e-3)


def test_estimate_dimensions_no_source_returns_raw_estimate() -> None:
    est = _make_estimator(interoception_source=None)
    out = est.estimate_dimensions(_stimulus())
    # No source => no interoception bias. R40 prototypes score 0.0
    # with the stub, so threat = 0.0 exactly.
    assert out.threat == 0.0


# --------------------------------------------------------------------------- #
# 13. Clamping                                                                #
# --------------------------------------------------------------------------- #


def test_apply_interoception_clamps_to_unit_range() -> None:
    # Stack multiple channels that would push threat above 1.0.
    src = _StubInteroception(
        state={
            "cortisol": 0.9,
            "norepinephrine": 0.9,
            "oxytocin": 0.9,
        }
    )
    est = _make_estimator(interoception_source=src, interoception_gain=1.0)
    base = RapidDimensionEstimate(
        threat=0.99, reward=0.99, novelty=0.99, social=0.99, uncertainty=0.99
    )
    out = est._apply_interoception(base)
    # All dimensions clamped to [0, 1]
    assert 0.0 <= out.threat <= 1.0
    assert 0.0 <= out.reward <= 1.0
    assert 0.0 <= out.novelty <= 1.0
    assert 0.0 <= out.uncertainty <= 1.0
    assert 0.0 <= out.social <= 1.0


def test_apply_interoception_clamps_to_zero() -> None:
    # Channels that lower threat/reward below 0.
    src = _StubInteroception(state={"cortisol": 0.2, "oxytocin": 0.2})
    est = _make_estimator(interoception_source=src, interoception_gain=1.0)
    base = RapidDimensionEstimate(
        threat=0.01, reward=0.01, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est._apply_interoception(base)
    assert out.threat >= 0.0
    assert out.reward >= 0.0


# --------------------------------------------------------------------------- #
# 14. Multiple channels firing simultaneously                                #
# --------------------------------------------------------------------------- #


def test_multiple_channels_combine() -> None:
    # cortisol high + oxytocin high + serotonin high => threat up,
    # reward up, uncertainty down.
    src = _StubInteroception(
        state={"cortisol": 0.8, "oxytocin": 0.8, "serotonin": 0.8}
    )
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.5, novelty=0.5, social=0.5, uncertainty=0.5
    )
    out = est._apply_interoception(base)
    # threat: +0.005; reward: +0.005; uncertainty: -0.003
    assert out.threat == pytest.approx(0.505, rel=1e-3)
    assert out.reward == pytest.approx(0.505, rel=1e-3)
    assert out.uncertainty == pytest.approx(0.497, rel=1e-3)


# --------------------------------------------------------------------------- #
# 15. Layer 1 + Layer 5 independent                                          #
# --------------------------------------------------------------------------- #


def test_layer_5_uses_pre_bias_estimate_for_concept_observation() -> None:
    # Layer 5 (Bayesian observation) should use the stimulus-only estimate,
    # not the body-modulated one. Verify: even with interoception bias
    # pushing threat above 0.5, the concept_prior stays empty when the
    # raw R40 estimate is below 0.5.
    src = _StubInteroception(state={"cortisol": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=10.0)
    # High gain pushes the final threat well above 0.5, but R40 raw is 0.0.
    est.seed_prior()
    out = est.estimate_dimensions(_stimulus())
    assert out.threat >= 0.5  # body-modulated (R40=0.0 + interoception=0.5)
    # But concept_prior stays empty (Layer 5 saw threat=0.0 from R40).
    prior = est.concept_prior[0]
    assert all(v == 0.0 for v in prior.counts.values())


# --------------------------------------------------------------------------- #
# 16. Public surface: interoception_bias re-runnable                         #
# --------------------------------------------------------------------------- #


def test_interoception_bias_public_surface_returns_new_estimate() -> None:
    src = _StubInteroception(state={"cortisol": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.0
    )
    out = est.interoception_bias(base)
    # Returns a NEW instance; the input is not mutated.
    assert out is not base
    assert out.threat == pytest.approx(0.505, rel=1e-3)
    # The input estimate retains its original value.
    assert base.threat == 0.5


def test_interoception_bias_does_not_mutate_input() -> None:
    src = _StubInteroception(state={"oxytocin": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=0.5)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.5, novelty=0.5, social=0.5, uncertainty=0.5
    )
    _ = est.interoception_bias(base)
    assert base.reward == 0.5  # unchanged


# --------------------------------------------------------------------------- #
# 17. Unknown hormone channels are silently ignored                          #
# --------------------------------------------------------------------------- #


def test_unknown_hormone_channels_silently_ignored() -> None:
    # "serotonin_doesnt_exist" or other bogus keys must not raise.
    src = _StubInteroception(state={"serotonin": 0.9, "fake_hormone_xyz": 0.9})
    est = _make_estimator(interoception_source=src, interoception_gain=0.1)
    base = RapidDimensionEstimate(
        threat=0.5, reward=0.0, novelty=0.0, social=0.0, uncertainty=0.5
    )
    # No exception; serotonin still applies its bias, fake channel ignored.
    out = est._apply_interoception(base)
    assert out.uncertainty == pytest.approx(0.497, rel=1e-3)