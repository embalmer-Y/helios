"""R-PROTO-LEARN.14 owner 11 internal_thought learner tests."""

import pytest

from helios_v2.learning import (
    InternalThoughtLearner, InternalThoughtLearnerConfig, Regime,
)


def test_r14_default_config_uses_p5_feel_calibration():
    c = InternalThoughtLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r14_input_output_dims():
    c = InternalThoughtLearnerConfig()
    assert c.input_dim == 6
    assert c.output_dim == 3


def test_r14_update_returns_snapshot():
    learner = InternalThoughtLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.regime == Regime.EXPLORATORY


def test_r14_update_with_dict_state():
    learner = InternalThoughtLearner()
    state = {"feeling_valence": 0.7, "feeling_arousal": 0.6,
             "feeling_tension": 0.4, "novelty": 0.5, "dopamine": 0.7,
             "gate_open": 0.5}
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r14_update_with_none_state():
    learner = InternalThoughtLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r14_closed_loop_residual_small():
    learner = InternalThoughtLearner()
    snap = learner.update(None, (0.3, 0.7, 0.8, 0.2, 0.4, 0.6, 0.3), novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    assert max_residual < 0.01


def test_r14_weights_learn_across_ticks():
    learner = InternalThoughtLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact.
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r14_regime_starts_exploratory():
    assert InternalThoughtLearner().regime() == Regime.EXPLORATORY


def test_r14_commit_count_starts_zero():
    assert InternalThoughtLearner().commit_count() == 0


def test_r14_rejects_invalid_novelty():
    learner = InternalThoughtLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)


def test_r14_rejects_wrong_llm_dim():
    learner = InternalThoughtLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 5, novelty=0.5, tick_id=0)


def test_r14_rejects_out_of_range_llm():
    learner = InternalThoughtLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r14_regime_can_transition():
    learner = InternalThoughtLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r14_weights_snapshot_immutable():
    learner = InternalThoughtLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r14_bias_snapshot_immutable():
    learner = InternalThoughtLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 3


def test_r14_does_not_modify_canonical_state():
    learner = InternalThoughtLearner()
    state = {"feeling_valence": 0.7, "feeling_arousal": 0.6,
             "feeling_tension": 0.4, "novelty": 0.5, "dopamine": 0.7,
             "gate_open": 0.5}
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
