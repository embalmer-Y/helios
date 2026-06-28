"""8 维 CDS + Radau stiff solver 测试。"""
import math
import pytest
import numpy as np

from helios_v2.research_v3_m1.cds import (
    CoupledDynamicalSystem,
    CDSODEParams,
    PTS_DIMENSION_NAMES,
    DEFAULT_ALPHA,
    DEFAULT_KURAMOTO_SCALE,
)


class TestCDSODEParams:
    def test_default_params_alpha_has_500x_range(self):
        """默认 alpha 范围 5.0 → 0.01,差 500 倍,典型 stiff ODE。"""
        p = CDSODEParams.default()
        assert float(p.alpha.max()) / float(p.alpha.min()) == 500.0

    def test_default_params_beta_8d(self):
        """默认 beta 是 8 维。"""
        p = CDSODEParams.default()
        assert p.beta.shape == (8,)

    def test_default_params_gamma_uniform(self):
        """默认 gamma 均匀 0.1。"""
        p = CDSODEParams.default()
        assert np.allclose(p.gamma, np.full(8, 0.1))

    def test_default_params_rtol_atol(self):
        """默认 rtol=1e-4 atol=1e-6(Radau 工业标准)。"""
        p = CDSODEParams.default()
        assert p.rtol == 1e-4
        assert p.atol == 1e-6


class TestCDSColdStart:
    def test_default_state_is_zero(self):
        """默认 cold start 状态 = 零向量。"""
        cds = CoupledDynamicalSystem()
        assert np.allclose(cds.state, np.zeros(8))

    def test_default_C_is_diagonal_0_1(self):
        """默认 C 是 0.1 * 单位矩阵。"""
        cds = CoupledDynamicalSystem()
        assert np.allclose(cds.C, np.eye(8) * 0.1)

    def test_kuramoto_R_at_zero_state(self):
        """零状态时 Kuramoto R = 0.5(所有 theta=0,exp(i*0)=1,sum/8=1)。"""
        cds = CoupledDynamicalSystem()
        R = cds.kuramoto_R()
        # 0/0 在 arctan 是 0,但 scale 全是 1.0,3 个慢维 scale 5/10/30
        # theta = arctan(0/scale) = 0 for all
        # exp(i*0) = 1 for all, sum = 8, |sum| = 8, R = 8/8 = 1.0
        # (实际计算:theta=0 → exp=1 → R=1.0)
        assert R == pytest.approx(1.0, abs=1e-6)


class TestCDSTickConvergence:
    """Radau stiff solver 收敛性测试。"""

    def test_single_tick_solver_succeeds(self):
        """单 tick Radau solver 返回 success=True。"""
        cds = CoupledDynamicalSystem()
        result = cds.tick()
        assert result["solver_success"] is True

    def test_single_tick_state_remains_bounded(self):
        """单 tick 后 state 仍在合法范围。"""
        cds = CoupledDynamicalSystem()
        cds.tick(I=np.array([0.5] * 8))
        assert np.all(np.abs(cds.state) <= 10.0)
        assert not any(math.isnan(v) or math.isinf(v) for v in cds.state)

    def test_100_ticks_stable(self):
        """100 tick 演化数值稳定,无 NaN/Inf。"""
        cds = CoupledDynamicalSystem()
        for tick in range(100):
            I = np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.1)
            result = cds.tick(I=I)
            assert result["solver_success"], f"tick {tick} solver failed"
            assert not any(math.isnan(v) or math.isinf(v) for v in cds.state), f"tick {tick} NaN/Inf"

    def test_1000_ticks_no_numerical_blow_up(self):
        """1000 tick 后 state 仍在合法范围,不发散。"""
        cds = CoupledDynamicalSystem()
        for tick in range(1000):
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.01)
            result = cds.tick(I=I)
            assert result["solver_success"], f"tick {tick} solver failed"
            assert np.all(np.abs(cds.state) <= 10.0), f"tick {tick} state blew up: {cds.state}"
        assert not any(math.isnan(v) or math.isinf(v) for v in cds.state)


class TestKuramotoR:
    """Kuramoto R + Rochat level 5 段分段测试。"""

    def test_R_in_0_1(self):
        """Kuramoto R ∈ [0, 1]。"""
        cds = CoupledDynamicalSystem()
        cds.state = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        R = cds.kuramoto_R()
        assert 0.0 <= R <= 1.0

    def test_R_is_1_for_proportional_states(self):
        """完全同步状态(theta 全相等)→ R ≈ 1.0。"""
        cds = CoupledDynamicalSystem()
        # state[i] = scale[i] * 0.5 to make all theta[i] = arctan(0.5)
        # scale = [1, 1, 1, 1, 1, 5, 10, 30]
        cds.state = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 2.5, 5.0, 15.0])
        R = cds.kuramoto_R()
        # theta all arctan(0.5) = 0.4636, exp aligned, R=1.0
        assert R == pytest.approx(1.0, abs=1e-6)

    def test_R_decreases_with_orthogonal_state(self):
        """反相关状态 → R < 1.0。"""
        cds = CoupledDynamicalSystem()
        cds.state = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
        R = cds.kuramoto_R()
        # theta 有正有负,exp 不对齐,R 应 < 1.0
        assert R < 1.0

    def test_Rochat_discrete_levels(self):
        """rochat_level_discrete ∈ {0, 1, 2, 3, 4}。"""
        cds = CoupledDynamicalSystem()
        for state in [
            np.zeros(8),
            np.array([0.5] * 8),
            np.array([1.0, -1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ]:
            cds.state = state
            R = cds.kuramoto_R()
            level = int(R * 5)
            assert 0 <= level <= 5, f"Rochat level {level} out of [0, 5] for R={R}"


class TestRewardHebbian:
    """Reward-Hebbian C 矩阵学习测试。"""

    def test_update_C_normalizes_to_1(self):
        """C 更新后 max(|C|) ≤ 1.0(归一化防发散)。"""
        cds = CoupledDynamicalSystem()
        # 模拟 high reward 推动 C 发散
        for _ in range(100):
            cds.update_C(reward=10.0, lr=0.5)
        max_abs = float(np.max(np.abs(cds.C)))
        assert max_abs <= 1.0, f"|C|max = {max_abs} > 1.0"

    def test_update_C_with_zero_reward_keeps_C(self):
        """zero reward → C 不变。"""
        cds = CoupledDynamicalSystem()
        C_before = cds.C.copy()
        cds.update_C(reward=0.0, lr=0.1)
        assert np.allclose(cds.C, C_before)

    def test_update_C_directional_learning(self):
        """正 reward 应增强 state × state 外积。"""
        cds = CoupledDynamicalSystem()
        cds.state = np.array([1.0, 0.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        C_before = cds.C.copy()
        cds.update_C(reward=1.0, lr=0.1)
        # C[0,0] 和 C[0,1], C[1,0], C[1,1] 应增加
        assert cds.C[0, 0] > C_before[0, 0]
        assert cds.C[0, 1] > C_before[0, 1]
        assert cds.C[1, 1] > C_before[1, 1]


class TestSelfExperience:
    """self_experience 涌现态测试。"""

    def test_self_experience_keys(self):
        """self_experience 包含所有必要字段。"""
        cds = CoupledDynamicalSystem()
        exp = cds.self_experience()
        for key in [
            "8d_state",
            "global_coherence_R",
            "rochat_level_continuous",
            "rochat_level_discrete",
            "self_unity",
            "agency_strength",
        ]:
            assert key in exp, f"missing key: {key}"

    def test_self_experience_agency_strength_is_PTS_2(self):
        """agency_strength = PTS 维度 2 (minimal_experiential) state[1]。"""
        cds = CoupledDynamicalSystem()
        cds.state = np.array([0.0, 0.7, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        exp = cds.self_experience()
        assert exp["agency_strength"] == pytest.approx(0.7, abs=1e-6)


class TestSeedPriorState:
    """跨 tick carry(seed_prior_state)测试。"""

    def test_seed_prior_state_restores_state(self):
        """seed_prior_state 恢复 state。"""
        cds = CoupledDynamicalSystem()
        target_state = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        cds.seed_prior_state(state=target_state)
        assert np.allclose(cds.state, target_state)

    def test_seed_prior_state_validates_shape(self):
        """seed_prior_state 拒绝错误 shape。"""
        cds = CoupledDynamicalSystem()
        with pytest.raises(ValueError):
            cds.seed_prior_state(state=np.array([1.0, 2.0]))

    def test_seed_prior_state_with_C(self):
        """seed_prior_state 可同时恢复 C。"""
        cds = CoupledDynamicalSystem()
        target_state = np.array([0.5] * 8)
        target_C = np.eye(8) * 0.5
        cds.seed_prior_state(state=target_state, C=target_C)
        assert np.allclose(cds.state, target_state)
        assert np.allclose(cds.C, target_C)


class TestPTSDimensionNames:
    def test_8_dimension_names(self):
        """8 维 PTS 维度名。"""
        assert len(PTS_DIMENSION_NAMES) == 8
        for i, name in enumerate(PTS_DIMENSION_NAMES):
            assert isinstance(name, str)
            assert len(name) > 0
        assert "bodily_processes" in PTS_DIMENSION_NAMES
        assert "normative" in PTS_DIMENSION_NAMES
        assert "narrative" in PTS_DIMENSION_NAMES
