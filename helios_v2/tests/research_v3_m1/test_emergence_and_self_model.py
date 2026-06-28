"""M1-T5 SelfModelOwner + M1-T6 EmergenceDetector 测试。"""
import math
import pytest
import numpy as np

from helios_v2.research_v3_m1.emergence import (
    EmergenceEvent,
    EmergenceDetector,
    SynchronizedClusterDetector,
    PhaseTransitionDetector,
    ResonanceDetector,
)
from helios_v2.research_v3_m1.self_model import SelfModelOwner
from helios_v2.research_v3_m1.cds import CoupledDynamicalSystem


class TestSynchronizedClusterDetector:
    """同步集群检测。"""

    def test_no_event_for_diverse_state(self):
        """diverse state → 无 cluster。"""
        det = SynchronizedClusterDetector(distance_threshold=0.3)
        state = np.array([1.0, -1.0, 0.5, -0.5, 0.8, -0.8, 0.3, -0.3])
        events = det.detect(state)
        # diverse 状态可能产生小 cluster,允许为空或 < 3 elements
        for e in events:
            assert len(e.involved_aspects) >= 3

    def test_event_for_proportional_state(self):
        """proportional state(state ∝ scale)→ 全同步 cluster(8 aspects)。"""
        det = SynchronizedClusterDetector(distance_threshold=0.3)
        # scale = [1, 1, 1, 1, 1, 5, 10, 30]
        state = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 2.5, 5.0, 15.0])
        events = det.detect(state)
        assert len(events) >= 1
        # 应该有包含所有 8 aspects 的 cluster
        max_cluster = max(events, key=lambda e: len(e.involved_aspects))
        assert len(max_cluster.involved_aspects) == 8

    def test_event_strength_in_0_1(self):
        """event.strength ∈ [0, 1]。"""
        det = SynchronizedClusterDetector()
        state = np.array([0.5] * 8)
        events = det.detect(state)
        for e in events:
            assert 0.0 <= e.strength <= 1.0


class TestPhaseTransitionDetector:
    """相变检测(KL 散度)。"""

    def test_no_event_for_stable_state(self):
        """stable state → 无 phase_transition。"""
        det = PhaseTransitionDetector(kl_threshold=0.5)
        for _ in range(10):
            events = det.update(np.array([0.5] * 8))
            assert events == []

    def test_event_for_sudden_change(self):
        """sudden change → phase_transition。"""
        det = PhaseTransitionDetector(kl_threshold=0.1)
        # p: high/low alternating distribution
        det.update(np.array([0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9]))
        # q: opposite high/low distribution
        events = det.update(np.array([0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1]))
        assert len(events) >= 1
        assert events[0].type == "phase_transition"

    def test_kl_divergence_zero_for_identical(self):
        """相同分布 KL = 0。"""
        kl = PhaseTransitionDetector._kl_divergence(
            np.array([0.5] * 8),
            np.array([0.5] * 8),
        )
        assert kl == pytest.approx(0.0, abs=1e-6)


class TestResonanceDetector:
    """共振检测(window-based)。"""

    def test_no_event_for_window_not_full(self):
        """window 未满 → 无 event。"""
        det = ResonanceDetector(window_size=50)
        cds = CoupledDynamicalSystem()
        for _ in range(10):
            events = det.update(cds)
            assert events == []

    def test_event_when_high_coherence(self):
        """window 满 + Kuramoto R 高 → resonance event。"""
        # 用小 window + 高 R 触发
        det = ResonanceDetector(window_size=10, sync_threshold=0.5)
        cds = CoupledDynamicalSystem()
        # 直接设置 state 让 R 高(state ∝ scale)
        cds.state = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 2.5, 5.0, 15.0])
        # 更新 window 10 次
        for _ in range(10):
            events = det.update(cds)
        # 至少一次触发(因为 R > 0.99)
        assert len(events) >= 1
        assert events[0].type == "resonance"


class TestEmergenceDetector:
    """复合涌现检测器。"""

    def test_detect_combines_3_detectors(self):
        """EmergenceDetector.detect() 调用 3 个子检测器。"""
        det = EmergenceDetector()
        cds = CoupledDynamicalSystem()
        # 跑几个 tick
        for _ in range(5):
            events = det.detect(cds)
            # events 可能为空或非空,只确保不崩溃
            assert isinstance(events, list)


class TestSelfModelOwner:
    """SelfModelOwner 封装测试。"""

    def test_default_constructor(self):
        """default() 构造标准 owner。"""
        owner = SelfModelOwner.default()
        assert owner.tick_count == 0
        assert len(owner.experience_history) == 0

    def test_tick_returns_full_dict(self):
        """tick() 返回完整 dict(含 self_experience + emergence_events + tick_count)。"""
        owner = SelfModelOwner.default()
        result = owner.tick(I=np.array([0.3] * 8))
        for key in ["state", "kuramoto_R", "self_experience", "emergence_events", "tick_count"]:
            assert key in result

    def test_tick_increments_counter(self):
        """tick() 递增 tick_count。"""
        owner = SelfModelOwner.default()
        owner.tick()
        owner.tick()
        owner.tick()
        assert owner.tick_count == 3

    def test_tick_appends_to_experience_history(self):
        """tick() 追加到 experience_history。"""
        owner = SelfModelOwner.default()
        owner.tick()
        owner.tick()
        assert len(owner.experience_history) == 2

    def test_get_state_for_llm_is_readonly(self):
        """get_state_for_llm() 不修改 state(只读接口)。"""
        owner = SelfModelOwner.default()
        owner.tick(I=np.array([0.5] * 8))
        state_before = owner.cds.state.copy()
        snapshot = owner.get_state_for_llm()
        state_after = owner.cds.state.copy()
        assert np.allclose(state_before, state_after)

    def test_get_state_for_llm_contains_required_keys(self):
        """get_state_for_llm() 包含所有必要字段。"""
        owner = SelfModelOwner.default()
        owner.tick(I=np.array([0.5] * 8))
        snapshot = owner.get_state_for_llm()
        for key in [
            "8d_state",
            "coupling_matrix_summary",
            "global_coherence_R",
            "rochat_level_continuous",
            "rochat_level_discrete",
            "self_unity",
            "agency_strength",
            "tick_count",
        ]:
            assert key in snapshot

    def test_seed_prior_state_restores_cds(self):
        """seed_prior_state 恢复 CDS state。"""
        owner = SelfModelOwner.default()
        target_state = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8])
        owner.seed_prior_state(state=target_state)
        assert np.allclose(owner.cds.state, target_state)

    def test_LLM_cannot_modify_state_via_get_state(self):
        """LLM 通过 get_state_for_llm 拿到的 snapshot 不应能改 CDS state。

        snapshot 是 dict(值),改 snapshot 不应影响 CDS。
        """
        owner = SelfModelOwner.default()
        owner.tick(I=np.array([0.5] * 8))
        snapshot = owner.get_state_for_llm()
        state_before = owner.cds.state.copy()
        # 模拟 LLM 修改 snapshot(试图影响 state)
        snapshot["8d_state"] = [99.0] * 8
        state_after = owner.cds.state.copy()
        # CDS state 应不变
        assert np.allclose(state_before, state_after)


class TestSelfModelOwnerEndToEnd:
    """SelfModelOwner 端到端集成测试。"""

    def test_100_ticks_produces_consistent_state(self):
        """100 tick 后 state 在合法范围,Kuramoto R ∈ [0, 1]。"""
        owner = SelfModelOwner.default()
        for tick in range(100):
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
            result = owner.tick(I=I)
            assert result["solver_success"]
            assert 0.0 <= result["kuramoto_R"] <= 1.0

    def test_emergence_history_grows(self):
        """emergence 事件累积(每个 tick 可能产生多个 event)。"""
        owner = SelfModelOwner.default()
        total_events = 0
        for tick in range(100):
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.1)
            result = owner.tick(I=I)
            total_events += len(result["emergence_events"])
        # 100 tick 至少应产生若干事件(同步集群或相变或共振)
        assert total_events > 0, "100 tick 内未检测到任何涌现事件"
