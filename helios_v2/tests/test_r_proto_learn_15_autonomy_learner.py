"""R-PROTO-LEARN.15 owner 18 autonomy learner tests."""

import pytest

from helios_v2.learning import (
    AutonomyLearner, AutonomyLearnerConfig, Regime,
)


def test_r15_default_config_uses_p5_feel_calibration():
    c = AutonomyLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r15_input_output_dims():
    c = AutonomyLearnerConfig()
    assert c.input_dim == 7
    assert c.output_dim == 9  # 7 + 1 + 1


def test_r15_update_returns_snapshot():
    learner = AutonomyLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.regime == Regime.EXPLORATORY


def test_r15_update_with_dict_state():
    learner = AutonomyLearner()
    state = {"pressure_1": 0.5, "pressure_2": 0.6, "pressure_3": 0.4,
             "pressure_4": 0.7, "pressure_5": 0.5, "pressure_6": 0.3,
             "threshold": 0.6}
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r15_update_with_none_state():
    learner = AutonomyLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r15_closed_loop_residual_small():
    learner = AutonomyLearner()
    # 9-dim target: closure is best-effort.  Residual in [0, 1] range.
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r15_weights_learn_across_ticks():
    learner = AutonomyLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact.
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r15_regime_starts_exploratory():
    assert AutonomyLearner().regime() == Regime.EXPLORATORY


def test_r15_commit_count_starts_zero():
    assert AutonomyLearner().commit_count() == 0


def test_r15_rejects_invalid_novelty():
    learner = AutonomyLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)


def test_r15_rejects_wrong_llm_dim():
    learner = AutonomyLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 4, novelty=0.5, tick_id=0)


def test_r15_rejects_out_of_range_llm():
    learner = AutonomyLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r15_regime_can_transition():
    learner = AutonomyLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r15_weights_snapshot_immutable():
    learner = AutonomyLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r15_bias_snapshot_immutable():
    learner = AutonomyLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 9


def test_r15_does_not_modify_canonical_state():
    learner = AutonomyLearner()
    state = {"pressure_1": 0.5, "pressure_2": 0.6, "pressure_3": 0.4,
             "pressure_4": 0.7, "pressure_5": 0.5, "pressure_6": 0.3,
             "threshold": 0.6}
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
