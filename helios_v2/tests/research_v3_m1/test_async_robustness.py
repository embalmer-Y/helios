"""M1-T7 CDS 跟 LLM 异步鲁棒性测试。

5 个场景:
  - 场景 A: 同步(LLM 响应延迟 0)
  - 场景 B: 快速异步(LLM 响应延迟 1-2 ticks)
  - 场景 C: 慢速异步(LLM 响应延迟 5 ticks)
  - 场景 D: 随机抖动(LLM 响应延迟 uniform(0, 8))
  - 场景 E: 超时(10% 请求 delay > max_age,模拟 timeout)
"""
import pytest
import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m1.async_loop import (
    AsyncReflectBuffer,
    simulate_async_loop,
    pattern_synchronous,
    pattern_fast_async,
    pattern_slow_async,
    pattern_random_jitter,
    pattern_with_timeouts,
)


class TestAsyncReflectBuffer:
    """AsyncReflectBuffer 单元测试。"""

    def test_submit_and_advance(self):
        """submit → advance 触发 arrived。"""
        buf = AsyncReflectBuffer()
        rid = buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=1)
        assert buf.pending_count() == 1
        assert buf.arrived_count() == 0
        n_new = buf.advance_to_tick(1)
        assert n_new == 1
        assert buf.pending_count() == 0
        assert buf.arrived_count() == 1

    def test_get_latest_returns_none_if_empty(self):
        """empty buffer → None。"""
        buf = AsyncReflectBuffer()
        assert buf.get_latest_arrived(current_tick=0) is None

    def test_get_latest_returns_fresh(self):
        """arrived reflect 可被取出。"""
        buf = AsyncReflectBuffer(max_age_ticks=5)
        buf.submit(reflect=np.array([0.5] * 8), current_tick=0, delay_ticks=1)
        buf.advance_to_tick(1)
        reflect = buf.get_latest_arrived(current_tick=1)
        assert reflect is not None
        assert np.allclose(reflect, [0.5] * 8)

    def test_stale_arrived_dropped(self):
        """超过 max_age 的 arrived 被丢弃。"""
        buf = AsyncReflectBuffer(max_age_ticks=3)
        buf.submit(reflect=np.array([0.5] * 8), current_tick=0, delay_ticks=1)
        buf.advance_to_tick(1)
        # tick=10,age = 10-1 = 9 > 3
        reflect = buf.get_latest_arrived(current_tick=10)
        assert reflect is None

    def test_pending_timeout_cleanup(self):
        """超过 max_age*2 还没到的 pending 被清理。"""
        buf = AsyncReflectBuffer(max_age_ticks=3)
        # delay=10,远大于 max_age=3
        buf.submit(reflect=np.array([0.5] * 8), current_tick=0, delay_ticks=10)
        assert buf.pending_count() == 1
        # tick=20,age = 20-0 = 20 > max_age*2=6
        cleaned = buf.cleanup_stale(current_tick=20)
        assert cleaned == 1
        assert buf.pending_count() == 0

    def test_multiple_pending_with_different_delays(self):
        """多个不同延迟的 pending 按 expected_arrival_tick 顺序触发。"""
        buf = AsyncReflectBuffer()
        buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=5)
        buf.submit(reflect=np.array([0.2] * 8), current_tick=0, delay_ticks=2)
        buf.submit(reflect=np.array([0.3] * 8), current_tick=0, delay_ticks=1)
        # tick=1,只触发 delay=1
        n_new = buf.advance_to_tick(1)
        assert n_new == 1
        assert buf.pending_count() == 2
        assert buf.arrived_count() == 1

    def test_heap_order_is_by_arrival_tick(self):
        """heap 按 expected_arrival_tick 排序,先到先出。"""
        buf = AsyncReflectBuffer()
        buf.submit(reflect=np.array([0.5] * 8), current_tick=0, delay_ticks=10)
        buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=1)
        # tick=1
        n_new = buf.advance_to_tick(1)
        assert n_new == 1
        # 应该取到 [0.1](delay=1)
        reflect = buf.get_latest_arrived(current_tick=1)
        assert np.allclose(reflect, [0.1] * 8)

    def test_drain_arrived_returns_sorted_by_recency(self):
        """drain_arrived 按 arrival_tick 降序(最新优先)。"""
        buf = AsyncReflectBuffer()
        # 在 tick=0 提交 delay=1
        buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=1)
        buf.advance_to_tick(1)
        # 在 tick=1 提交 delay=1
        buf.submit(reflect=np.array([0.2] * 8), current_tick=1, delay_ticks=1)
        buf.advance_to_tick(2)
        fresh = buf.drain_arrived(current_tick=2)
        assert len(fresh) == 2
        # 最新的应该是 [0.2]
        assert np.allclose(fresh[0].reflect, [0.2] * 8)
        assert np.allclose(fresh[1].reflect, [0.1] * 8)


class TestAsyncSimulationScenarios:
    """5 个异步场景的端到端测试。"""

    def _assert_robust(self, stats):
        """鲁棒性断言:1000 tick 后状态稳定。"""
        d = stats.to_dict()
        assert d["n_solver_failures"] == 0, f"solver failures: {d}"
        assert d["n_nan"] == 0, f"NaN count: {d}"
        assert d["state_abs_max"] < 30.0, f"state diverged: {d}"
        assert 0.0 <= d["R_min"] <= d["R_max"] <= 1.0, f"R out of range: {d}"

    def test_scenario_a_synchronous(self):
        """场景 A: 同步 — baseline。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_synchronous, seed=42
        )
        d = stats.to_dict()
        assert d["n_ticks"] == 1000
        assert d["n_reflect_applied"] > 500  # 大多数 tick 都有 reflect
        self._assert_robust(stats)

    def test_scenario_b_fast_async(self):
        """场景 B: 快速异步(1-2 tick 延迟)。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_fast_async, seed=42
        )
        d = stats.to_dict()
        self._assert_robust(stats)
        assert d["n_reflect_applied"] > 100

    def test_scenario_c_slow_async(self):
        """场景 C: 慢速异步(5 tick 延迟)。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_slow_async, seed=42
        )
        d = stats.to_dict()
        self._assert_robust(stats)
        # 慢速异步:应有大量 reflect 因为累积了多个 arrived
        assert d["n_reflect_applied"] > 500

    def test_scenario_d_random_jitter(self):
        """场景 D: 随机抖动(uniform(0, 8))。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42
        )
        d = stats.to_dict()
        self._assert_robust(stats)

    def test_scenario_e_with_timeouts(self):
        """场景 E: 10% 请求 timeout。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_with_timeouts, seed=42
        )
        d = stats.to_dict()
        # 10% tick (每 10 tick) 提交 delay=100 的请求,应该被 timeout 清理
        assert d["n_reflect_timeout"] >= 50, f"timeout count too low: {d}"
        self._assert_robust(stats)


class TestAsyncSimulationProperties:
    """异步仿真的高级性质测试。"""

    def test_async_R_stays_within_bounds(self):
        """1000 tick 异步后 Kuramoto R ∈ [0, 1]。"""
        owner = SelfModelOwner.default()
        stats, _ = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42
        )
        d = stats.to_dict()
        assert 0.0 <= d["R_min"]
        assert d["R_max"] <= 1.0

    def test_async_state_stays_in_legal_range(self):
        """异步状态下 state 不发散(|state| < 30)。"""
        owner = SelfModelOwner.default()
        stats, _ = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42
        )
        d = stats.to_dict()
        assert d["state_abs_max"] < 30.0

    def test_async_zero_solver_failures(self):
        """1000 tick 异步下 0 solver failure。"""
        owner = SelfModelOwner.default()
        stats, _ = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42
        )
        assert stats.n_solver_failures == 0

    def test_async_reflect_buffer_does_not_grow_unbounded(self):
        """buffer peak 应该有限(受 max_age 限制)。"""
        owner = SelfModelOwner.default()
        stats, buf = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42,
            max_age_ticks=10,
        )
        d = stats.to_dict()
        # 异步 buffer peak 应该 <= max_age 的常数倍
        assert d["pending_peak"] + d["arrived_peak"] < 100, f"buffer unbounded: {d}"

    def test_async_does_not_cause_NaN(self):
        """异步循环 1000 tick 0 NaN。"""
        owner = SelfModelOwner.default()
        stats, _ = simulate_async_loop(
            owner, n_ticks=1000, reflect_pattern=pattern_random_jitter, seed=42
        )
        assert stats.n_nan == 0

    def test_reflect_with_zero_delay_works(self):
        """delay=0 也能正常处理(arrived 在 submit 的同一个 tick)。"""
        owner = SelfModelOwner.default()
        # 手动构造: submit with delay=0 at tick=0, advance to tick=0
        from helios_v2.research_v3_m1.async_loop import AsyncReflectBuffer
        buf = AsyncReflectBuffer()
        rid = buf.submit(reflect=np.array([0.5] * 8), current_tick=0, delay_ticks=0)
        # tick=0 时推进,应该触发 arrived
        n_new = buf.advance_to_tick(0)
        assert n_new == 1
        reflect = buf.get_latest_arrived(current_tick=0)
        assert reflect is not None
        assert np.allclose(reflect, [0.5] * 8)


class TestReflectBufferEdgeCases:
    """AsyncReflectBuffer 边界条件测试。"""

    def test_zero_size_buffer(self):
        """初始 buffer 大小为 0。"""
        buf = AsyncReflectBuffer()
        assert buf.total_in_flight() == 0

    def test_advance_with_no_pending(self):
        """无 pending 时 advance 返回 0。"""
        buf = AsyncReflectBuffer()
        n_new = buf.advance_to_tick(100)
        assert n_new == 0

    def test_get_latest_with_multiple_arrived(self):
        """多个 arrived 时返回最新的一个。"""
        buf = AsyncReflectBuffer()
        buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=1)
        buf.advance_to_tick(1)
        buf.submit(reflect=np.array([0.2] * 8), current_tick=1, delay_ticks=1)
        buf.advance_to_tick(2)
        # tick=2,最新的应该是 [0.2]
        reflect = buf.get_latest_arrived(current_tick=2)
        assert np.allclose(reflect, [0.2] * 8)

    def test_cleanup_returns_zero_when_no_stale(self):
        """无 stale 时 cleanup 返回 0。"""
        buf = AsyncReflectBuffer(max_age_ticks=10)
        buf.submit(reflect=np.array([0.1] * 8), current_tick=0, delay_ticks=1)
        cleaned = buf.cleanup_stale(current_tick=2)
        assert cleaned == 0
        assert buf.pending_count() == 1  # 还在 pending,没被清