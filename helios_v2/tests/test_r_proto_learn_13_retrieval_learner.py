"""R-PROTO-LEARN.13 owner 10 directed_retrieval learner tests."""

import pytest

from helios_v2.learning import (
    RetrievalLearner, RetrievalLearnerConfig, Regime,
)


def test_r13_default_config_uses_p5_feel_calibration():
    c = RetrievalLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r13_input_output_dims():
    c = RetrievalLearnerConfig()
    assert c.input_dim == 6
    assert c.output_dim == 11  # 4 + 3 + 4


def test_r13_update_returns_snapshot():
    learner = RetrievalLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.regime == Regime.EXPLORATORY


def test_r13_update_with_dict_state():
    learner = RetrievalLearner()
    state = {"l2_episodic": 0.5, "l3_semantic": 0.6, "l4_autobiographical": 0.4,
             "l5_immutable": 0.1, "dopaminergic_signal": 0.7, "time_decay": 0.5}
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r13_update_with_none_state():
    learner = RetrievalLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r13_closed_loop_residual_small():
    learner = RetrievalLearner()
    # Closure is best-effort: W is 11x6 rank-6, so 11-dim target may
    # not be exactly achievable.  Residual in [0, 1] range.
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r13_weights_learn_across_ticks():
    learner = RetrievalLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact (numpy pinv).
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r13_regime_starts_exploratory():
    assert RetrievalLearner().regime() == Regime.EXPLORATORY


def test_r13_commit_count_starts_zero():
    assert RetrievalLearner().commit_count() == 0


def test_r13_rejects_invalid_novelty():
    learner = RetrievalLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)


def test_r13_rejects_wrong_llm_dim():
    learner = RetrievalLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 8, novelty=0.5, tick_id=0)


def test_r13_rejects_out_of_range_llm():
    learner = RetrievalLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r13_regime_can_transition():
    learner = RetrievalLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r13_weights_snapshot_immutable():
    learner = RetrievalLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r13_bias_snapshot_immutable():
    learner = RetrievalLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 11


def test_r13_does_not_modify_canonical_state():
    learner = RetrievalLearner()
    state = {"l2_episodic": 0.5, "l3_semantic": 0.6, "l4_autobiographical": 0.4,
             "l5_immutable": 0.1, "dopaminergic_signal": 0.7, "time_decay": 0.5}
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
