"""R-PROTO-LEARN.23 owner 14 identity_governance learner tests."""

import pytest

from helios_v2.learning import (
    IdentityGovernanceLearner, IdentityGovernanceLearnerConfig, Regime,
)


def test_r23_default_config_uses_p5_feel_calibration():
    c = IdentityGovernanceLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r23_input_output_dims():
    c = IdentityGovernanceLearnerConfig()
    assert c.input_dim == 7
    assert c.output_dim == 12  # 3 + 3 + 3 + 3 policies (4 policies)


def test_r23_update_returns_snapshot():
    learner = IdentityGovernanceLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.tick_id == 0
    assert snap.regime == Regime.EXPLORATORY


def test_r23_update_with_dict_state():
    learner = IdentityGovernanceLearner()
    state = {
        "pressure_intensity": 0.6,
        "signal_strength": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.5,
        "proposal_count": 0.5,
        "boundary_risk": 0.6,
    }
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r23_update_with_dataclass_state():
    from dataclasses import dataclass

    @dataclass
    class IdentityGovernanceState:
        pressure_intensity: float = 0.5
        signal_strength: float = 0.5
        dopamine: float = 0.5
        acetylcholine: float = 0.5
        novelty: float = 0.5
        proposal_count: float = 0.5
        boundary_risk: float = 0.5

    learner = IdentityGovernanceLearner()
    state = IdentityGovernanceState(pressure_intensity=0.8, boundary_risk=0.7)
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r23_update_with_none_state_uses_defaults():
    learner = IdentityGovernanceLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r23_closed_loop_residual_in_algebraic_bound():
    """R23 12x7 W rank-7 algebraic 限制: residual 范围放大到 [0, 1.5]."""
    learner = IdentityGovernanceLearner()
    snap = learner.update(None, (0.3, 0.7, 0.8, 0.2, 0.4, 0.6, 0.3),
                          novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    assert 0.0 <= max_residual <= 1.5, f"residual out of [0, 1.5]: {max_residual}"


def test_r23_weights_learn_or_stay_valid():
    learner = IdentityGovernanceLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim == 12


def test_r23_regime_starts_exploratory():
    assert IdentityGovernanceLearner().regime() == Regime.EXPLORATORY


def test_r23_commit_count_starts_zero():
    assert IdentityGovernanceLearner().commit_count() == 0


def test_r23_rejects_invalid_novelty():
    learner = IdentityGovernanceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=-0.1, tick_id=0)


def test_r23_rejects_wrong_llm_signal_dim():
    learner = IdentityGovernanceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 5, novelty=0.5, tick_id=0)


def test_r23_rejects_out_of_range_llm_signal():
    learner = IdentityGovernanceLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r23_regime_can_transition():
    learner = IdentityGovernanceLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r23_weights_snapshot_immutable():
    learner = IdentityGovernanceLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)
    assert len(snap) == 12


def test_r23_bias_snapshot_immutable():
    learner = IdentityGovernanceLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 12


def test_r23_does_not_modify_canonical_state():
    learner = IdentityGovernanceLearner()
    state = {
        "pressure_intensity": 0.6, "signal_strength": 0.5, "dopamine": 0.7,
        "acetylcholine": 0.4, "novelty": 0.5, "proposal_count": 0.5,
        "boundary_risk": 0.6,
    }
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert state == state_snapshot
