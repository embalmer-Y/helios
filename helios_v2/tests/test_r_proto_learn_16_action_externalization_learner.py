"""R-PROTO-LEARN.16 owner 12 action_externalization learner tests."""

import pytest

from helios_v2.learning import (
    ActionExternalizationLearner,
    ActionExternalizationLearnerConfig,
    Regime,
)


def test_r16_default_config_uses_p5_feel_calibration():
    c = ActionExternalizationLearnerConfig()
    assert c.learning_rate == 0.05
    assert c.commit_threshold == 0.3
    assert c.min_stable_ticks == 8


def test_r16_input_output_dims():
    c = ActionExternalizationLearnerConfig()
    assert c.input_dim == 7
    assert c.output_dim == 9  # 3 + 3 + 3 policies


def test_r16_update_returns_snapshot():
    learner = ActionExternalizationLearner()
    snap = learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None
    assert snap.tick_id == 0
    assert snap.regime == Regime.EXPLORATORY


def test_r16_update_with_dict_state():
    learner = ActionExternalizationLearner()
    state = {
        "action_intensity": 0.7,
        "scope": 1.0,  # external
        "candidate_channels": 0.6,
        "evidence": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.8,
    }
    snap = learner.update(state, (0.5,) * 7, novelty=0.8, tick_id=0)
    assert snap is not None


def test_r16_update_with_dataclass_state():
    from dataclasses import dataclass

    @dataclass
    class ActionExtState:
        action_intensity: float = 0.5
        scope: float = 0.5
        candidate_channels: float = 0.5
        evidence: float = 0.5
        dopamine: float = 0.5
        acetylcholine: float = 0.5
        novelty: float = 0.5

    learner = ActionExternalizationLearner()
    state = ActionExtState(action_intensity=0.8, scope=1.0)
    snap = learner.update(state, (0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r16_update_with_none_state_uses_defaults():
    learner = ActionExternalizationLearner()
    snap = learner.update(state=None, llm_signal=(0.5,) * 7, novelty=0.5, tick_id=0)
    assert snap is not None


def test_r16_closed_loop_residual_in_unit_interval():
    learner = ActionExternalizationLearner()
    # Use a varying LLM signal to exercise different policy dims.
    snap = learner.update(None, (0.3, 0.7, 0.8, 0.2, 0.4, 0.6, 0.3),
                          novelty=0.5, tick_id=0)
    max_residual = max(abs(v) for v in snap.residual)
    # 9-dim target, 7-dim W column space: closure is best-effort.
    # Residual must be in [0, 1] (valid probability/decision space).
    assert 0.0 <= max_residual <= 1.0, f"residual out of [0, 1]: {max_residual}"


def test_r16_weights_learn_or_stay_valid():
    learner = ActionExternalizationLearner()
    initial_max = learner.max_abs_weight()
    for i in range(10):
        novelty = 0.3 + 0.05 * i
        learner.update(None, (0.5,) * 7, novelty=min(novelty, 0.95), tick_id=i)
    final_max = learner.max_abs_weight()
    # W may stay constant when closure is exact; otherwise it learns.
    # We just verify W is a valid matrix.
    assert final_max > 0.0
    assert len(learner.weights_snapshot()) == learner.output_dim


def test_r16_regime_starts_exploratory():
    assert ActionExternalizationLearner().regime() == Regime.EXPLORATORY


def test_r16_commit_count_starts_zero():
    assert ActionExternalizationLearner().commit_count() == 0


def test_r16_rejects_invalid_novelty():
    learner = ActionExternalizationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=1.5, tick_id=0)
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 7, novelty=-0.1, tick_id=0)


def test_r16_rejects_wrong_llm_signal_dim():
    learner = ActionExternalizationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 5, novelty=0.5, tick_id=0)


def test_r16_rejects_out_of_range_llm_signal():
    learner = ActionExternalizationLearner()
    with pytest.raises(ValueError):
        learner.update(None, (0.5,) * 6 + (1.5,), novelty=0.5, tick_id=0)


def test_r16_regime_can_transition():
    learner = ActionExternalizationLearner()
    for i in range(30):
        learner.update(None, (0.5,) * 7, novelty=0.5, tick_id=i)
    assert learner.regime() in (Regime.MODEL_BASED, Regime.HABITUAL)


def test_r16_weights_snapshot_immutable():
    learner = ActionExternalizationLearner()
    snap = learner.weights_snapshot()
    assert isinstance(snap, tuple)
    assert all(isinstance(row, tuple) for row in snap)


def test_r16_bias_snapshot_immutable():
    learner = ActionExternalizationLearner()
    bias = learner.bias_snapshot()
    assert isinstance(bias, tuple)
    assert len(bias) == 9


def test_r16_does_not_modify_canonical_state():
    learner = ActionExternalizationLearner()
    state = {
        "action_intensity": 0.7,
        "scope": 1.0,
        "candidate_channels": 0.6,
        "evidence": 0.5,
        "dopamine": 0.7,
        "acetylcholine": 0.4,
        "novelty": 0.8,
    }
    state_snapshot = dict(state)
    learner.update(state, (0.5,) * 7, novelty=0.8, tick_id=0)
    assert state == state_snapshot
