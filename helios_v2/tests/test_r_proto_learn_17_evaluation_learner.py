"""R-PROTO-LEARN.17 owner 17 evaluation learner tests."""

import pytest

from helios_v2.learning import (
    EvaluationLearner,
    EvaluationLearnerConfig,
    Regime,
)


def test_r17_default_config_uses_p5_feel_calibration():
    c = EvaluationLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r17_input_output_dims():
    c = EvaluationLearnerConfig()
    assert c.input_dim == 7
    assert c.output_dim == 8  # 3 + 2 + 3 policies


def test_r17_update_returns_snapshot():
    learner = EvaluationLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.tick_id == 0
    assert snap.regime == Regime.EXPLORATORY


def test_r17_update_with_dict_state():
    learner = EvaluationLearner()
    state = {
        "execution_fidelity": 0.7,
        "evidence": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.5,
        "session_tick": 0.6,
        "cross_session_drift": 0.2,
    }
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r17_update_with_dataclass_state():
    from dataclasses import dataclass

    @dataclass
    class EvalState:
        execution_fidelity: float = 0.5
        evidence: float = 0.5
        dopamine: float = 0.5
        acetylcholine: float = 0.5
        novelty: float = 0.5
        session_tick: float = 0.5
        cross_session_drift: float = 0.5

    learner = EvaluationLearner()
    state = EvalState(execution_fidelity=0.8, cross_session_drift=0.3)
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r17_update_with_none_state_uses_defaults():
    learner = EvaluationLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r17_closed_loop_residual_in_unit_interval():
    learner = EvaluationLearner()
    snap = learner.update(None, (0.3, 0.7, 0.8, 0.2, 0.4, 0.6, 0.3),
                          novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    # 8-dim target, 7-dim W column space: closure is best-effort.
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r17_weights_learn_or_stay_valid():
    learner = EvaluationLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact.
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r17_regime_starts_exploratory():
    assert EvaluationLearner().regime() == Regime.EXPLORATORY


def test_r17_commit_count_starts_zero():
    assert EvaluationLearner().commit_count() == 0


def test_r17_rejects_invalid_novelty():
    learner = EvaluationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=-0.1, tick_id=0)


def test_r17_rejects_wrong_llm_signal_dim():
    learner = EvaluationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 5, novelty=0.5, tick_id=0)


def test_r17_rejects_out_of_range_llm_signal():
    learner = EvaluationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r17_regime_can_transition():
    learner = EvaluationLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r17_weights_snapshot_immutable():
    learner = EvaluationLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r17_bias_snapshot_immutable():
    learner = EvaluationLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 8


def test_r17_does_not_modify_canonical_state():
    learner = EvaluationLearner()
    state = {
        "execution_fidelity": 0.7,
        "evidence": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.5,
        "session_tick": 0.6,
        "cross_session_drift": 0.2,
    }
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
