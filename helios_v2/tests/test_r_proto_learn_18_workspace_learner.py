"""R-PROTO-LEARN.18 owner 07 workspace learner tests."""

import pytest

from helios_v2.learning import (
    WorkspaceLearner, WorkspaceLearnerConfig, Regime,
)


def test_r18_default_config_uses_p5_feel_calibration():
    c = WorkspaceLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r18_input_output_dims():
    c = WorkspaceLearnerConfig()
    assert c.input_dim == 7
    assert c.output_dim == 9  # 3 + 3 + 3 policies


def test_r18_update_returns_snapshot():
    learner = WorkspaceLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.tick_id == 0
    assert snap.regime == Regime.EXPLORATORY


def test_r18_update_with_dict_state():
    learner = WorkspaceLearner()
    state = {
        "candidate_count": 0.6,
        "signal_strength": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.8,
        "working_state_size": 0.5,
        "cross_tick_carry": 0.6,
    }
    snap = learner.update(state, (0.5,) * 7, novelty=0.8, tick_id=0)
    assert snap is not None


def test_r18_update_with_dataclass_state():
    from dataclasses import dataclass

    @dataclass
    class WorkspaceState:
        candidate_count: float = 0.5
        signal_strength: float = 0.5
        dopamine: float = 0.5
        acetylcholine: float = 0.5
        novelty: float = 0.5
        working_state_size: float = 0.5
        cross_tick_carry: float = 0.5

    learner = WorkspaceLearner()
    state = WorkspaceState(candidate_count=0.8, novelty=0.7)
    snap = learner.update(state, (0.5,) * 7, novelty=0.7, tick_id=0)
    assert snap is not None


def test_r18_update_with_none_state_uses_defaults():
    learner = WorkspaceLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r18_closed_loop_residual_in_unit_interval():
    learner = WorkspaceLearner()
    snap = learner.update(None, (0.3, 0.7, 0.8, 0.2, 0.4, 0.6, 0.3),
                          novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r18_weights_learn_or_stay_valid():
    learner = WorkspaceLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r18_regime_starts_exploratory():
    assert WorkspaceLearner().regime() == Regime.EXPLORATORY


def test_r18_commit_count_starts_zero():
    assert WorkspaceLearner().commit_count() == 0


def test_r18_rejects_invalid_novelty():
    learner = WorkspaceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=-0.1, tick_id=0)


def test_r18_rejects_wrong_llm_signal_dim():
    learner = WorkspaceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 5, novelty=0.5, tick_id=0)


def test_r18_rejects_out_of_range_llm_signal():
    learner = WorkspaceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r18_regime_can_transition():
    learner = WorkspaceLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r18_weights_snapshot_immutable():
    learner = WorkspaceLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r18_bias_snapshot_immutable():
    learner = WorkspaceLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 9


def test_r18_does_not_modify_canonical_state():
    learner = WorkspaceLearner()
    state = {
        "candidate_count": 0.6, "signal_strength": 0.5, "dopamine": 0.7,
        "acetylcholine": 0.4, "novelty": 0.8, "working_state_size": 0.5,
        "cross_tick_carry": 0.6,
    }
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.8, tick_id=0)
    assert state == state_snapshot
