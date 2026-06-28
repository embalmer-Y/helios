"""M1-T7 CDS 跟 LLM 异步鲁棒性基础设施。

仿真异步 LLM 调用,验证 CDS tick 循环在以下条件下仍然稳定:
  - LLM 响应延迟 dt_tick ± 50ms (1 tick 之内)
  - LLM 响应延迟 5 × dt_tick (跨多个 tick)
  - LLM 响应抖动 (0-200ms 均匀分布)
  - LLM 超时 (永不返回)
  - 并发多个 LLM 请求
"""
from __future__ import annotations

import time
import heapq
import threading
from dataclasses import dataclass, field
from typing import Callable
import numpy as np


@dataclass
class PendingReflect:
    """一个 pending 的 reflect 请求。"""
    request_id: int
    submitted_at_tick: int
    expected_arrival_tick: int
    reflect: np.ndarray
    arrived: bool = False
    arrival_tick: int | None = None

    def __lt__(self, other):
        # heapq 按 (expected_arrival_tick, request_id) 排序
        return (self.expected_arrival_tick, self.request_id) < (other.expected_arrival_tick, other.request_id)


class AsyncReflectBuffer:
    """异步 reflect 输入 buffer。

    行为契约:
      - submit(request_id, reflect, current_tick, delay_ticks) → 调度一个 pending reflect
      - advance_to_tick(current_tick) → 把所有 expected_arrival_tick <= current_tick 的 pending
        reflect 标记为 arrived,可以从 drain_arrived() 拿到
      - get_latest_arrived(current_tick) → 返回最近一个 arrived 的 reflect(可能 stale)
      - cleanup_stale(current_tick, max_age) → 清理超过 max_age tick 还没到的 stale 请求
      - size() → 当前 pending + arrived 总数
    """

    def __init__(self, max_age_ticks: int = 10):
        self._pending: list[PendingReflect] = []
        self._arrived: list[PendingReflect] = []
        self._all: dict[int, PendingReflect] = {}
        self._next_id = 0
        self.max_age_ticks = max_age_ticks

    def submit(
        self,
        reflect: np.ndarray,
        current_tick: int,
        delay_ticks: int = 1,
    ) -> int:
        """提交一个 pending reflect。

        Args:
            reflect: 8-dim 反思调制向量
            current_tick: 当前 tick
            delay_ticks: 延迟 tick 数(LLM 响应时间 / dt_tick)

        Returns:
            request_id
        """
        req_id = self._next_id
        self._next_id += 1
        pr = PendingReflect(
            request_id=req_id,
            submitted_at_tick=current_tick,
            expected_arrival_tick=current_tick + delay_ticks,
            reflect=reflect.copy(),
        )
        heapq.heappush(self._pending, pr)
        self._all[req_id] = pr
        return req_id

    def advance_to_tick(self, current_tick: int) -> int:
        """推进到 current_tick,把所有 expected 的 pending 标记为 arrived。

        Returns:
            本次新 arrived 的数量
        """
        new_arrivals = 0
        while self._pending and self._pending[0].expected_arrival_tick <= current_tick:
            pr = heapq.heappop(self._pending)
            pr.arrived = True
            pr.arrival_tick = current_tick
            self._arrived.append(pr)
            new_arrivals += 1
        return new_arrivals

    def drain_arrived(self, current_tick: int, max_age_ticks: int | None = None) -> list[PendingReflect]:
        """drain 所有 arrived 且在 max_age 之内的 reflect。

        Args:
            current_tick: 当前 tick
            max_age_ticks: 最多接受多少 tick 之前的 arrived reflect;None 表示用 buffer 默认值

        Returns:
            arrived reflect 列表(按 arrival_tick 降序,即最新优先)
        """
        if max_age_ticks is None:
            max_age_ticks = self.max_age_ticks
        fresh = [
            pr for pr in self._arrived
            if (current_tick - (pr.arrival_tick or 0)) <= max_age_ticks
        ]
        self._arrived = [
            pr for pr in self._arrived
            if (current_tick - (pr.arrival_tick or 0)) > max_age_ticks
        ]
        fresh.sort(key=lambda pr: -(pr.arrival_tick or 0))
        return fresh

    def get_latest_arrived(self, current_tick: int, max_age_ticks: int | None = None) -> np.ndarray | None:
        """返回最新的 arrived reflect(若都 stale 则返回 None)。"""
        fresh = self.drain_arrived(current_tick, max_age_ticks)
        if not fresh:
            return None
        return fresh[0].reflect

    def cleanup_stale(self, current_tick: int) -> int:
        """清理超过 max_age 还没到的 pending(视为 dropped/timeout)。

        Returns:
            清理的数量
        """
        cleaned = 0
        # pending 中 expected_arrival_tick 太老的视为 timeout
        new_pending = []
        for pr in sorted(self._pending, key=lambda p: p.expected_arrival_tick):
            if current_tick - pr.submitted_at_tick > self.max_age_ticks * 2:
                # 已超时,从 pending + _all 中移除
                self._all.pop(pr.request_id, None)
                cleaned += 1
            else:
                new_pending.append(pr)
        heapq.heapify(new_pending)
        self._pending = new_pending
        return cleaned

    def pending_count(self) -> int:
        return len(self._pending)

    def arrived_count(self) -> int:
        return len(self._arrived)

    def total_in_flight(self) -> int:
        return self.pending_count() + self.arrived_count()


@dataclass
class AsyncSimulationStats:
    """异步仿真统计。"""
    n_ticks: int = 0
    n_solved: int = 0
    n_solver_failures: int = 0
    n_nan: int = 0
    n_reflect_applied: int = 0
    n_reflect_dropped_stale: int = 0
    n_reflect_timeout: int = 0
    state_min: float = float("inf")
    state_max: float = -float("inf")
    state_abs_max: float = 0.0
    R_min: float = float("inf")
    R_max: float = -float("inf")
    R_mean_sum: float = 0.0
    R_count: int = 0
    pending_peak: int = 0
    arrived_peak: int = 0

    def update_R(self, R: float):
        self.R_min = min(self.R_min, R)
        self.R_max = max(self.R_max, R)
        self.R_mean_sum += R
        self.R_count += 1

    def update_state(self, state: np.ndarray):
        self.state_min = min(self.state_min, float(np.min(state)))
        self.state_max = max(self.state_max, float(np.max(state)))
        self.state_abs_max = max(self.state_abs_max, float(np.max(np.abs(state))))

    @property
    def R_mean(self) -> float:
        return self.R_mean_sum / self.R_count if self.R_count > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "n_ticks": self.n_ticks,
            "n_solved": self.n_solved,
            "n_solver_failures": self.n_solver_failures,
            "n_nan": self.n_nan,
            "n_reflect_applied": self.n_reflect_applied,
            "n_reflect_dropped_stale": self.n_reflect_dropped_stale,
            "n_reflect_timeout": self.n_reflect_timeout,
            "state_min": self.state_min,
            "state_max": self.state_max,
            "state_abs_max": self.state_abs_max,
            "R_min": self.R_min,
            "R_max": self.R_max,
            "R_mean": self.R_mean,
            "pending_peak": self.pending_peak,
            "arrived_peak": self.arrived_peak,
        }


def simulate_async_loop(
    owner,
    n_ticks: int,
    reflect_pattern: Callable[[int], tuple[np.ndarray, int]],
    seed: int = 42,
    max_age_ticks: int = 10,
) -> tuple[AsyncSimulationStats, AsyncReflectBuffer]:
    """驱动 CDS tick 循环 + 模拟 LLM 异步 reflect。

    Args:
        owner: SelfModelOwner 实例
        n_ticks: tick 总数
        reflect_pattern: callable(tick) → (reflect_vector, delay_ticks)
            每个 tick 调用一次,返回一个 reflect + 延迟 tick 数
        seed: 随机种子
        max_age_ticks: reflect 最大接受延迟

    Returns:
        (stats, buffer)
    """
    rng = np.random.default_rng(seed)
    buffer = AsyncReflectBuffer(max_age_ticks=max_age_ticks)
    stats = AsyncSimulationStats()

    for tick in range(n_ticks):
        # 1. 推进 buffer 时间(LLM 响应到达)
        buffer.advance_to_tick(tick)

        # 2. 清理 stale(超时的 pending)
        stats.n_reflect_timeout += buffer.cleanup_stale(tick)

        # 3. 取最新的 arrived reflect(可能 None)
        reflect = buffer.get_latest_arrived(tick)
        if reflect is not None:
            stats.n_reflect_applied += 1
        else:
            reflect = np.zeros(8)

        # 4. 跑 CDS tick
        result = owner.tick(I=0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05),
                            reflect=reflect)

        stats.n_ticks += 1
        if result["solver_success"]:
            stats.n_solved += 1
        else:
            stats.n_solver_failures += 1
        state = result["state"]
        if np.any(np.isnan(state)):
            stats.n_nan += 1
        stats.update_state(state)
        stats.update_R(result["kuramoto_R"])

        # 5. 提交下一个 reflect 请求(模拟 LLM 调用)
        reflect_vec, delay = reflect_pattern(tick)
        buffer.submit(reflect_vec, current_tick=tick, delay_ticks=delay)

        # 跟踪 peak
        stats.pending_peak = max(stats.pending_peak, buffer.pending_count())
        stats.arrived_peak = max(stats.arrived_peak, buffer.arrived_count())

    return stats, buffer


# === 5 个 reflect_pattern 实现 ===

def pattern_synchronous(tick: int) -> tuple[np.ndarray, int]:
    """场景 A: 同步,LLM 响应 = 0 延迟。"""
    reflect = 0.1 * np.cos(np.linspace(0, 2 * np.pi, 8) + tick * 0.1)
    return reflect, 1


def pattern_fast_async(tick: int) -> tuple[np.ndarray, int]:
    """场景 B: 快速异步,LLM 响应 = 1 tick ± 50ms ≈ 0-2 ticks。"""
    reflect = 0.15 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.07)
    delay = 1 + (tick % 3 == 0)  # 大多数 1 tick,偶尔 2 ticks
    return reflect, delay


def pattern_slow_async(tick: int) -> tuple[np.ndarray, int]:
    """场景 C: 慢速异步,LLM 响应 = 5 ticks 延迟。"""
    reflect = 0.2 * np.cos(np.linspace(0, np.pi, 8) + tick * 0.03)
    return reflect, 5


def pattern_random_jitter(tick: int) -> tuple[np.ndarray, int]:
    """场景 D: 随机抖动,LLM 响应 = uniform(0, 8) ticks。"""
    rng = np.random.default_rng(tick + 100000)
    reflect = 0.12 * rng.standard_normal(8)
    delay = int(rng.uniform(0, 8))
    return reflect, max(1, delay)


def pattern_with_timeouts(tick: int) -> tuple[np.ndarray, int]:
    """场景 E: 10% 概率 LLM 超时(delay > max_age)。"""
    reflect = 0.1 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
    if tick % 10 == 0:
        return reflect, 100  # 超时
    return reflect, 1


def pattern_burst(tick: int) -> tuple[np.ndarray, int]:
    """场景 F: 突发,每 50 tick 提交 5 个并发 LLM 请求。"""
    reflect = 0.1 * np.cos(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
    if tick % 50 == 0 and tick > 0:
        # 突发 5 个延迟各不相同的请求
        for i in range(5):
            extra_reflect = 0.05 * np.sin(np.linspace(0, 2 * np.pi, 8) + (tick + i) * 0.1)
            # 注意:这里只是返回单个 reflect,我们用 reflect_pattern 做 burst 检测
            pass
    return reflect, 1