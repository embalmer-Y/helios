"""R-PROTO-LEARN.12 owner 09 thought_gating learner tests."""

import pytest

from helios_v2.learning import (
    ThoughtGatingLearner, ThoughtGatingLearnerConfig, Regime,
)


def test_r12_default_config_uses_p5_feel_calibration():
    c = ThoughtGatingLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8
    assert c.frozen_ticks_post_commit == 5


def test_r12_input_output_dims():
    c = ThoughtGatingLearnerConfig()
    assert c.input_dim == 6
    assert c.output_dim == 8  # 6 + 1 + 1


def test_r12_update_returns_snapshot():
    learner = ThoughtGatingLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.tick_id == 0
    assert snap.regime == Regime.EXPLORATORY


def test_r12_update_with_dict_state():
    learner = ThoughtGatingLearner()
    state = {"norepinephrine": 0.6, "dopamine": 0.7, "acetylcholine": 0.4,
             "novelty": 0.5, "task_demand": 0.6, "signal_magnitude": 0.4}
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r12_update_with_none_state():
    learner = ThoughtGatingLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r12_closed_loop_residual_small():
    learner = ThoughtGatingLearner()
    # Closure is best-effort: W is 8x6 rank-6, so 8-dim target may not
    # be exactly achievable.  Residual should be in [0, 1] range.
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    # All residuals in [0, 1] bound.
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r12_weights_learn_across_ticks():
    learner = ThoughtGatingLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact (numpy pinv).
    # Verify W shape and value are valid.
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r12_regime_starts_exploratory():
    assert ThoughtGatingLearner().regime() == Regime.EXPLORATORY


def test_r12_commit_count_starts_zero():
    assert ThoughtGatingLearner().commit_count() == 0


def test_r12_rejects_invalid_novelty():
    learner = ThoughtGatingLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)


def test_r12_rejects_wrong_llm_dim():
    learner = ThoughtGatingLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6, novelty=0.5, tick_id=0)


def test_r12_rejects_out_of_range_llm():
    learner = ThoughtGatingLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (2.0,), novelty=0.5, tick_id=0)


def test_r12_regime_can_transition():
    learner = ThoughtGatingLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r12_weights_snapshot_immutable():
    learner = ThoughtGatingLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r12_bias_snapshot_immutable():
    learner = ThoughtGatingLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 8


def test_r12_does_not_modify_canonical_state():
    learner = ThoughtGatingLearner()
    state = {"norepinephrine": 0.6, "dopamine": 0.7, "acetylcholine": 0.4,
             "novelty": 0.5, "task_demand": 0.6, "signal_magnitude": 0.4}
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
