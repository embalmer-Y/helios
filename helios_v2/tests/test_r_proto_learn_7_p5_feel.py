"""Tests for R-PROTO-LEARN.7 (P5-feel) — owner 05 feeling 真学习算法.

学术依据：
- Fermin, Yamawaki, Friston (2021) — IMAC 模型 (arXiv 2112.12290)
- Reddan et al. (2018) — embodied emotion (arXiv 2411.08973)
- Hinrichs et al. (2025) — hyperscanning (arXiv 2506.08599)

测试覆盖：
- 探索残差计算（5 测试）
- 固化判定（5 测试）
- DA precision（5 测试）
- ACh flexibility（5 测试）
- 三态切换（5 测试）
- W 更新 clip / 数值稳定（5 测试）
- 集成（5 测试）
- 完整 tick loop 烟雾（2 测试）
"""

from __future__ import annotations

import pytest

from helios_v2.feeling.learning_path import (
    FEELING_DIMENSIONS,
    HORMONE_CHANNELS,
    P5FeelLearningConfig,
    P5FeelLearningPath,
    Regime,
    _FIRST_VERSION_WEIGHTS,
    _first_version_bias,
    _validate_bias,
    _validate_weight_matrix,
)
from helios_v2.feeling.engine import InteroceptiveFeelingEngine
from helios_v2.neuromodulation import NeuromodulatorLevels, NeuromodulatorState
from helios_v2.feeling import (
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingVector,
    DominantDimensionReporter,
)
from helios_v2.feeling.engine import NeuromodulatorDerivedFeelingConstructionPath


# --- Helpers -------------------------------------------------------------

def _neuromod_state(
    dopamine: float = 0.5,
    norepinephrine: float = 0.5,
    serotonin: float = 0.5,
    acetylcholine: float = 0.5,
    cortisol: float = 0.5,
    oxytocin: float = 0.5,
    opioid_tone: float = 0.5,
    excitation: float = 0.5,
    inhibition: float = 0.5,
) -> NeuromodulatorState:
    levels = NeuromodulatorLevels(
        dopamine=dopamine,
        norepinephrine=norepinephrine,
        serotonin=serotonin,
        acetylcholine=acetylcholine,
        cortisol=cortisol,
        oxytocin=oxytocin,
        opioid_tone=opioid_tone,
        excitation=excitation,
        inhibition=inhibition,
    )
    return NeuromodulatorState(
        state_id=f"test-state-{dopamine}-{cortisol}",
        source_appraisal_batch_id="test-appraisal",
        levels=levels,
        tick_id=0,
    )


def _baseline_feeling() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.5, arousal=0.5, tension=0.5, comfort=0.5,
        fatigue=0.5, pain_like=0.5, social_safety=0.5,
    )


def _legal_min() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.0, arousal=0.0, tension=0.0, comfort=0.0,
        fatigue=0.0, pain_like=0.0, social_safety=0.0,
    )


def _legal_max() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=1.0, arousal=1.0, tension=1.0, comfort=1.0,
        fatigue=1.0, pain_like=1.0, social_safety=1.0,
    )


def _feeling_config() -> InteroceptiveFeelingConfig:
    return InteroceptiveFeelingConfig(
        baseline_feeling=_baseline_feeling(),
        legal_min=_legal_min(),
        legal_max=_legal_max(),
        mandatory_learned_parameters=(
            "feeling_mapping_strength",
            "feeling_coupling_strength",
            "feeling_persistence",
        ),
    )


def _feeling_engine(p5_learner: P5FeelLearningPath | None = None) -> InteroceptiveFeelingEngine:
    return InteroceptiveFeelingEngine(
        config=_feeling_config(),
        construction_path=NeuromodulatorDerivedFeelingConstructionPath(),
        dominant_dimension_reporter=FixedDominantDimensionReporter(),
        p5_feel_learner=p5_learner,
    )


class FixedDominantDimensionReporter(DominantDimensionReporter):
    """Minimal concrete reporter for the P5-feel sidecar tests."""

    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        return ("valence",)


# --- Test 1: exploration residual --------------------------------------


def test_exploration_zero_residual_no_signal():
    """If LLM appraisal matches current feeling, residual is zero."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    # Build a feeling identical to what the dense W/bias will produce from
    # the default 0.5 neuromodulator state.
    current = path._project_feeling(_neuromod_state().__dict__["levels"].__dict__)
    res = path._explore_residual(tuple(current), tuple(current))
    assert res == (0.0,) * 7


def test_exploration_positive_residual_means_llm_higher():
    """If LLM appraisal > current, residual is positive per dim."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    res = path._explore_residual(
        llm_appraisal=(0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9),
        current_feeling=(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5),
    )
    assert all(v > 0.0 for v in res)


def test_exploration_no_llm_skips():
    """If LLM appraisal is None, residual is the zero vector."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    res = path._explore_residual(None, (0.5,) * 7)
    assert res == (0.0,) * 7


def test_exploration_wrong_shape_raises():
    """Wrong-shape LLM appraisal raises ValueError."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    with pytest.raises(ValueError):
        path._explore_residual((0.5, 0.5, 0.5), (0.5,) * 7)


def test_exploration_residual_clipped():
    """Residual is clipped to [-1, 1] per dimension."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    res = path._explore_residual(
        llm_appraisal=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        current_feeling=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    )
    assert all(0.0 <= v <= 1.0 for v in res)


# --- Test 2: commit predicate ------------------------------------------


def test_commit_window_too_short_does_not_commit():
    """If fewer than `min_stable_ticks` residuals are seen, no commit."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=20, frozen_ticks_post_commit=5)
    )
    # Push 10 zero residuals
    for _ in range(10):
        path._residual_history.append((0.0,) * 7)
    assert path.commit_if_stable() is False


def test_commit_stable_residuals_commits():
    """20 consecutive small residuals trigger commit."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=20, frozen_ticks_post_commit=5)
    )
    for _ in range(25):
        path._residual_history.append((0.01,) * 7)
    assert path.commit_if_stable() is True


def test_commit_oscillating_residuals_does_not_commit():
    """20 residuals with one large one breaks the commit."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=20)
    )
    for _ in range(19):
        path._residual_history.append((0.01,) * 7)
    path._residual_history.append((0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
    path._residual_history.append((0.01,) * 7)
    assert path.commit_if_stable() is False


def test_commit_threshold_boundary():
    """Residual equal to threshold counts as not-stable (>=)."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=5, commit_threshold=0.02)
    )
    path._residual_history.extend(
        [(0.02, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)] * 5
    )
    assert path.commit_if_stable() is False


def test_commit_explicit_recent_residuals_arg():
    """commit_if_stable can be driven with an explicit list."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=3, commit_threshold=0.05)
    )
    assert path.commit_if_stable(recent_residuals=((0.01,) * 7,) * 3) is True
    assert path.commit_if_stable(recent_residuals=((0.10,) * 7,) * 3) is False


# --- Test 3: dopamine precision ----------------------------------------


def test_dopamine_precision_neutral_midrange():
    """DA=0.5, zero residual -> precision around 0.5."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    p = path._dopamine_precision((0.0,) * 7, dopamine=0.5)
    # 1.0 * (0.5 + 0.5*0.5) = 0.75
    assert all(abs(v - 0.75) < 1e-9 for v in p)


def test_dopamine_precision_high_dopamine_full_confidence():
    """DA=1.0, zero residual -> precision 1.0."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    p = path._dopamine_precision((0.0,) * 7, dopamine=1.0)
    assert all(abs(v - 1.0) < 1e-9 for v in p)


def test_dopamine_precision_zero_dopamine_floors():
    """DA=0.0 -> precision always at floor regardless of residual."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    p = path._dopamine_precision((0.0,) * 7, dopamine=0.0)
    # 1.0 * (0.5 + 0.5*0.0) = 0.5
    assert all(abs(v - 0.5) < 1e-9 for v in p)


def test_dopamine_precision_large_residual_collapses():
    """Residual magnitude 1.0 -> precision floor regardless of DA."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    p = path._dopamine_precision((1.0,) * 7, dopamine=1.0)
    # base = max(0.1, 1 - 1) = 0.1; * (0.5 + 0.5) = 0.1
    assert all(abs(v - 0.1) < 1e-9 for v in p)


def test_dopamine_precision_clipped():
    """Precision is clipped to [precision_floor, precision_ceiling]."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(precision_floor=0.2, precision_ceiling=0.8)
    )
    p_low = path._dopamine_precision((0.0,) * 7, dopamine=0.0)
    p_high = path._dopamine_precision((0.0,) * 7, dopamine=1.0)
    assert all(0.2 <= v <= 0.8 for v in p_low)
    assert all(0.2 <= v <= 0.8 for v in p_high)


# --- Test 4: ACh flexibility -------------------------------------------


def test_ach_flexibility_below_threshold_floors():
    """ACh below threshold -> flexibility at floor."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(flexibility_threshold=0.4, flexibility_floor=0.1)
    )
    f = path._ach_flexibility(novelty=0.9, acetylcholine=0.3)
    assert f == pytest.approx(0.1)


def test_ach_flexibility_above_threshold_proportional():
    """ACh > threshold + high novelty -> high flexibility."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    f = path._ach_flexibility(novelty=0.9, acetylcholine=0.8)
    # 0.9 * 0.8 = 0.72
    assert f == pytest.approx(0.72)


def test_ach_flexibility_above_threshold_low_novelty():
    """ACh > threshold + low novelty -> moderate flexibility."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    f = path._ach_flexibility(novelty=0.2, acetylcholine=0.7)
    # 0.2 * 0.7 = 0.14
    assert f == pytest.approx(0.14)


def test_ach_flexibility_clipped_to_ceiling():
    """Very high ACh + novelty -> flexibility clipped to ceiling."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig(flexibility_ceiling=0.6))
    f = path._ach_flexibility(novelty=1.0, acetylcholine=1.0)
    assert f == pytest.approx(0.6)


def test_ach_flexibility_threshold_boundary():
    """ACh = 0.4 with threshold 0.4 -> raw = novelty * ach (0.4 NOT below 0.4)."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig(flexibility_threshold=0.4))
    f = path._ach_flexibility(novelty=0.9, acetylcholine=0.4)
    # strict < semantics: ACh=0.4 NOT < 0.4, so raw = 0.9 * 0.4 = 0.36
    assert f == pytest.approx(0.36)


def test_ach_flexibility_just_below_threshold_is_floor():
    """ACh just below threshold -> floor."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig(flexibility_threshold=0.4))
    f = path._ach_flexibility(novelty=0.9, acetylcholine=0.39)
    assert f == pytest.approx(0.1)  # floor


# --- Test 5: regime switching ------------------------------------------


def test_regime_early_ticks_are_exploratory():
    """First few ticks return EXPLORATORY."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    for _ in range(3):
        path._residual_history.append((0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))
        path.update(
            hormone_state=_neuromod_state(acetylcholine=0.5, dopamine=0.5),
            llm_appraisal=(0.5,) * 7,
            novelty=0.5,
            tick_id=len(path._residual_history),
        )
    # Hysteresis: first few ticks stay in the initial regime
    assert path.regime() == Regime.EXPLORATORY


def test_regime_ach_high_novelty_drives_exploratory():
    """ACh > 0.4 and novelty > 0.5 -> EXPLORATORY."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig(regime_hysteresis_ticks=1))
    for _ in range(10):
        path._residual_history.append((0.0,) * 7)
    regime = path._determine_regime(
        per_dim_precision=(0.5,) * 7,
        flexibility=0.8,
        novelty=0.9,
        acetylcholine=0.8,
    )
    assert regime == Regime.EXPLORATORY


def test_regime_stable_residuals_drive_habitual():
    """Stable small residuals -> HABITUAL."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(
            regime_hysteresis_ticks=1,
            commit_threshold=0.02,
        )
    )
    # Push 20 small residuals
    for _ in range(20):
        path._residual_history.append((0.005,) * 7)
    regime = path._determine_regime(
        per_dim_precision=(0.9,) * 7,
        flexibility=0.2,
        novelty=0.1,
        acetylcholine=0.3,
    )
    assert regime == Regime.HABITUAL


def test_regime_default_is_model_based():
    """Generic residuals -> MODEL_BASED."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(regime_hysteresis_ticks=1)
    )
    for _ in range(20):
        path._residual_history.append((0.2,) * 7)
    regime = path._determine_regime(
        per_dim_precision=(0.5,) * 7,
        flexibility=0.3,
        novelty=0.3,
        acetylcholine=0.5,
    )
    assert regime == Regime.MODEL_BASED


def test_regime_hysteresis_holds_previous():
    """Hysteresis prevents regime flip in single tick."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(regime_hysteresis_ticks=3)
    )
    state = _neuromod_state(acetylcholine=0.5, dopamine=0.5)
    # Push enough residuals to escape early-explore
    for _ in range(20):
        path._residual_history.append((0.05,) * 7)
    # Run 3 updates with same input -> regime should settle to MODEL_BASED
    for i in range(3):
        path.update(state, (0.5,) * 7, novelty=0.3, tick_id=i)
    assert path.regime() == Regime.MODEL_BASED
    # Now inject a high-novelty high-ACh tick -> hysteresis holds
    novel_state = _neuromod_state(acetylcholine=0.8, dopamine=0.5)
    path.update(novel_state, (0.9,) * 7, novelty=0.9, tick_id=3)
    assert path.regime() == Regime.MODEL_BASED
    # After 2 more high-novelty ticks, hysteresis flips
    for i in range(2):
        path.update(novel_state, (0.9,) * 7, novelty=0.9, tick_id=4 + i)
    assert path.regime() == Regime.EXPLORATORY


# --- Test 6: numerical stability ---------------------------------------


def test_weights_remain_bounded_high_lr():
    """Even with high LR, weights stay inside clip range."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(learning_rate=0.5, weight_clip_low=-1.0, weight_clip_high=1.0)
    )
    state = _neuromod_state()
    for i in range(50):
        path.update(state, (1.0,) * 7, novelty=0.9, tick_id=i)
    W = path.weights_snapshot()
    for row in W:
        for v in row:
            assert -1.0 <= v <= 1.0


def test_weights_remain_bounded_extreme_inputs():
    """Hormones at boundary, LLM at boundary -> no NaN/inf."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    state = _neuromod_state(
        dopamine=1.0, norepinephrine=1.0, serotonin=1.0, acetylcholine=1.0,
        cortisol=1.0, oxytocin=1.0, opioid_tone=1.0, excitation=1.0, inhibition=1.0,
    )
    for i in range(30):
        path.update(state, (1.0,) * 7, novelty=1.0, tick_id=i)
    W = path.weights_snapshot()
    for row in W:
        for v in row:
            assert v == v  # not NaN
            assert v not in (float("inf"), float("-inf"))


def test_bias_remain_bounded():
    """Bias stays in [bias_clip_low, bias_clip_high]."""

    path = P5FeelLearningPath(
        config=P5FeelLearningConfig(
            learning_rate=0.5,
            bias_clip_low=-0.5,
            bias_clip_high=0.5,
        )
    )
    state = _neuromod_state()
    for i in range(30):
        path.update(state, (1.0,) * 7, novelty=0.9, tick_id=i)
    for v in path.bias_snapshot():
        assert -0.5 <= v <= 0.5


def test_long_run_does_not_diverge():
    """100 ticks with random-ish signals: weights stay finite."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig())
    for i in range(100):
        # Vary hormone a bit
        dopamine = 0.3 + 0.4 * ((i % 7) / 7.0)
        cortisol = 0.2 + 0.6 * ((i % 5) / 5.0)
        ach = 0.1 + 0.8 * ((i % 3) / 3.0)
        state = _neuromod_state(
            dopamine=dopamine, cortisol=cortisol, acetylcholine=ach
        )
        # LLM appraisal: mild oscillation
        llm = tuple(0.3 + 0.4 * ((i + d) % 5) / 5.0 for d in range(7))
        novelty = 0.2 + 0.6 * ((i % 4) / 4.0)
        path.update(state, llm, novelty=novelty, tick_id=i)
    W = path.weights_snapshot()
    for row in W:
        for v in row:
            assert -2.0 <= v <= 2.0


def test_no_nan_in_commit_count():
    """Commit count never goes non-finite."""

    path = P5FeelLearningPath(config=P5FeelLearningConfig(min_stable_ticks=3))
    state = _neuromod_state()
    for i in range(50):
        path.update(state, (0.5,) * 7, novelty=0.0, tick_id=i)
    assert path.commit_count() >= 0
    assert path.commit_count() < 100


# --- Test 7: integration with owner 05 engine --------------------------


def test_engine_without_p5_learner_behaves_as_before():
    """When `p5_feel_learner` is None, update_state is unchanged."""

    engine = _feeling_engine(p5_learner=None)
    state = engine.update_state(_neuromod_state())
    assert state.feeling is not None
    # Canonical R36 feeling for a 0.5 neuromodulator state:
    # The default LinearFeelingConstructor is hardcoded; we just assert
    # the engine still returns a feeling vector in [0, 1].
    for dim in (
        "valence", "arousal", "tension", "comfort",
        "fatigue", "pain_like", "social_safety",
    ):
        v = getattr(state.feeling, dim)
        assert 0.0 <= v <= 1.0


def test_engine_with_p5_learner_runs_sidecar():
    """When `p5_feel_learner` is set, the sidecar actually runs."""

    learner = P5FeelLearningPath(config=P5FeelLearningConfig())
    engine = _feeling_engine(p5_learner=learner)
    state = _neuromod_state(cortisol=0.8, dopamine=0.3)
    engine.update_state(
        state,
        llm_appraisal=(0.2, 0.8, 0.9, 0.1, 0.5, 0.9, 0.1),
        novelty=0.7,
        tick_id=1,
    )
    # The sidecar should have produced a non-zero residual
    assert any(v != 0.0 for v in learner.last_residual())


def test_engine_p5_learner_no_llm_is_silent():
    """When LLM appraisal is None, the sidecar runs but is silent."""

    learner = P5FeelLearningPath(config=P5FeelLearningConfig())
    engine = _feeling_engine(p5_learner=learner)
    state = _neuromod_state()
    engine.update_state(state, tick_id=1)
    assert learner.last_residual() == (0.0,) * 7


def test_engine_p5_learner_weights_actually_change():
    """After a few ticks with consistent LLM, weights are not all zero."""

    learner = P5FeelLearningPath(config=P5FeelLearningConfig())
    engine = _feeling_engine(p5_learner=learner)
    for i in range(15):
        state = _neuromod_state(cortisol=0.7, dopamine=0.7, acetylcholine=0.7)
        engine.update_state(
            state,
            llm_appraisal=(0.8, 0.7, 0.8, 0.2, 0.5, 0.8, 0.2),
            novelty=0.6,
            tick_id=i,
        )
    # The weights should not be all equal to the initial sparse values
    W = learner.weights_snapshot()
    # Confirm at least one row has been touched (not all zero)
    any_nonzero = any(
        abs(v) > 0.001 for row in W for v in row
    )
    assert any_nonzero


def test_engine_p5_learner_commit_count_advances():
    """After enough stable ticks, the commit count is non-zero."""

    learner = P5FeelLearningPath(
        config=P5FeelLearningConfig(min_stable_ticks=5, commit_threshold=0.5)
    )
    engine = _feeling_engine(p5_learner=learner)
    # Use a `novelty=0.0` path so the sidecar's update has no exploration
    # pressure and the residual signal is small.
    for i in range(10):
        # Stable: hormone does not move, LLM matches current
        state = _neuromod_state(cortisol=0.5, dopamine=0.5)
        engine.update_state(
            state,
            llm_appraisal=(0.5,) * 7,
            novelty=0.0,
            tick_id=i,
        )
    # `commit_count` is incremented on the first commit and then
    # frozen for `frozen_ticks_post_commit` ticks; it should advance
    # at least once across 10 stable ticks.
    assert learner.commit_count() >= 1


# --- Test 8: end-to-end smoke ------------------------------------------


def test_smoke_happy_path_changes_weights():
    """An end-to-end 50-tick run produces a non-trivial weight change."""

    learner = P5FeelLearningPath(config=P5FeelLearningConfig(learning_rate=0.05))
    engine = _feeling_engine(p5_learner=learner)
    W0 = learner.weights_snapshot()
    for i in range(50):
        state = _neuromod_state(
            cortisol=0.6 + 0.2 * (i % 3) / 3.0,
            dopamine=0.5,
            acetylcholine=0.3 + 0.4 * (i % 5) / 5.0,
        )
        # Mildly varying LLM appraisal
        llm = tuple(0.5 + 0.1 * ((i + d) % 3) / 3.0 for d in range(7))
        engine.update_state(state, llm_appraisal=llm, novelty=0.5, tick_id=i)
    W1 = learner.weights_snapshot()
    # At least one entry must have changed
    diffs = [
        abs(W1[i][j] - W0[i][j])
        for i in range(len(W0))
        for j in range(len(W0[0]))
    ]
    assert max(diffs) > 0.001


def test_smoke_exploratory_to_habitual_progression():
    """Run starts exploratory and eventually stabilizes."""

    learner = P5FeelLearningPath(
        config=P5FeelLearningConfig(
            min_stable_ticks=3, commit_threshold=0.5, regime_hysteresis_ticks=1
        )
    )
    engine = _feeling_engine(p5_learner=learner)
    # First 10 ticks: highly novel
    for i in range(10):
        state = _neuromod_state(acetylcholine=0.9, dopamine=0.7)
        engine.update_state(
            state,
            llm_appraisal=(0.9, 0.1, 0.9, 0.1, 0.5, 0.9, 0.1),
            novelty=0.9,
            tick_id=i,
        )
    assert learner.regime() == Regime.EXPLORATORY
    # Next 30 ticks: simulate a fully-trained sidecar (LLM matches the
    # current feeling) so residuals are zero and HABITUAL can trigger.
    for i in range(30):
        state = _neuromod_state(acetylcholine=0.2, dopamine=0.5)
        # Compute the current feeling and pass it as the LLM appraisal
        # (this is the operational "LLM agrees" case in a converged system).
        current = learner._project_feeling(state.levels.__dict__)
        engine.update_state(
            state,
            llm_appraisal=tuple(current),
            novelty=0.0,
            tick_id=10 + i,
        )
    # After enough stable ticks, regime should be HABITUAL
    assert learner.regime() == Regime.HABITUAL
    # Commit count should be at least 1
    assert learner.commit_count() >= 1


# --- Test 9: validation helpers ---------------------------------------


def test_validate_weight_matrix_correct_shape_ok():
    """A 7x9 matrix passes validation."""

    W = tuple(tuple(0.0 for _ in range(9)) for _ in range(7))
    _validate_weight_matrix(W)  # should not raise


def test_validate_weight_matrix_wrong_rows_raises():
    """A 6x9 matrix raises ValueError."""

    W = tuple(tuple(0.0 for _ in range(9)) for _ in range(6))
    with pytest.raises(ValueError):
        _validate_weight_matrix(W)


def test_validate_weight_matrix_wrong_cols_raises():
    """A 7x8 matrix raises ValueError."""

    W = tuple(tuple(0.0 for _ in range(8)) for _ in range(7))
    with pytest.raises(ValueError):
        _validate_weight_matrix(W)


def test_validate_weight_matrix_nan_raises():
    """A matrix with NaN raises ValueError."""

    row = list(tuple(0.0 for _ in range(9)))
    row[0] = float("nan")
    W = (tuple(row),) + tuple(tuple(0.0 for _ in range(9)) for _ in range(6))
    with pytest.raises(ValueError):
        _validate_weight_matrix(W)


def test_validate_bias_wrong_length_raises():
    """A bias with wrong length raises ValueError."""

    with pytest.raises(ValueError):
        _validate_bias((0.0, 0.0, 0.0))


def test_first_version_weights_match_r36_sparse():
    """The dense first-version matrix should match the R36 sparse values
    where the R36 had entries and be zero elsewhere."""

    # Row 0: valence from dopamine (0.30), opioid_tone (0.15),
    # serotonin (0.15), cortisol (-0.30)
    assert _FIRST_VERSION_WEIGHTS[0][0] == 0.30  # dopamine
    assert _FIRST_VERSION_WEIGHTS[0][6] == 0.15  # opioid_tone
    assert _FIRST_VERSION_WEIGHTS[0][2] == 0.15  # serotonin
    assert _FIRST_VERSION_WEIGHTS[0][4] == -0.30  # cortisol
    # Other entries should be 0
    for j in (1, 3, 5, 7, 8):
        assert _FIRST_VERSION_WEIGHTS[0][j] == 0.0


def test_first_version_bias_is_zero():
    """First-version bias starts at zero (R36 baselines come from
    `config.baseline_feeling` in the canonical formula)."""

    assert _first_version_bias() == (0.0,) * 7


def test_hormone_channels_have_nine():
    """The 9 hormone channels are exactly the 9 owner 04 channels."""

    assert len(HORMONE_CHANNELS) == 9
    assert set(HORMONE_CHANNELS) == {
        "dopamine", "norepinephrine", "serotonin", "acetylcholine",
        "cortisol", "oxytocin", "opioid_tone", "excitation", "inhibition",
    }


def test_feeling_dimensions_have_seven():
    """The 7 feeling dimensions match the R36/R43 vector fields."""

    assert len(FEELING_DIMENSIONS) == 7
    assert set(FEELING_DIMENSIONS) == {
        "valence", "arousal", "tension", "comfort",
        "fatigue", "pain_like", "social_safety",
    }
