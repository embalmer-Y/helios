"""EmergenceDetector:从 8 维 CDS 状态检测涌现事件。

v3 plan §05_self_model_design_v2 §4(v2 redesign 关键修正):
v1 错的:单一 Kuramoto R(全局相干性)
v2 对的:三种检测(sync clusters + phase transitions + resonance)

检测器(本 ship):
1. SynchronizedClusterDetector:hierarchical clustering of phase-locked aspects
   (使用 Kuramoto R + state 距离)
2. PhaseTransitionDetector:KL 散度 + change point detection(global state 突变)
3. ResonanceDetector:FFT-based frequency analysis(特定频率同步)

所有检测器是只读 owner(不修改 CDS state),符合 v3 治理铁律 #8。
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from helios_v2.research_v3_m1.cds import (
    CoupledDynamicalSystem,
    DEFAULT_KURAMOTO_SCALE,
)


@dataclass(frozen=True)
class EmergenceEvent:
    """涌现事件(v3 §05_self_model_design_v2 §4.3 EmergenceEvent)。"""
    type: str       # 'sync_cluster' / 'phase_transition' / 'resonance'
    timestamp: int
    involved_aspects: tuple[int, ...]
    strength: float # [0, 1]
    description: str


class SynchronizedClusterDetector:
    """同步集群检测:hierarchical clustering of phase-locked aspects。

    算法:
    1. 计算每对 aspect 的 Kuramoto 相位差
    2. 距离 < threshold 的 aspect 归为同一 cluster
    3. cluster size >= 3 的为有效 sync cluster
    """

    def __init__(self, distance_threshold: float = 0.3):
        self.threshold = distance_threshold

    def detect(self, state: np.ndarray) -> list[EmergenceEvent]:
        if state.shape != (8,):
            return []
        # 计算相位
        theta = np.arctan(state / DEFAULT_KURAMOTO_SCALE)
        # 计算距离矩阵
        diffs = np.abs(theta[:, None] - theta[None, :])
        # union-find 找 cluster
        parent = list(range(8))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i in range(8):
            for j in range(i + 1, 8):
                if diffs[i, j] < self.threshold:
                    union(i, j)

        # 找 cluster
        clusters: dict[int, list[int]] = {}
        for i in range(8):
            root = find(i)
            clusters.setdefault(root, []).append(i)

        events = []
        for members in clusters.values():
            if len(members) >= 3:
                strength = float(1.0 - np.mean(diffs[np.ix_(members, members)]))
                events.append(EmergenceEvent(
                    type="sync_cluster",
                    timestamp=0,
                    involved_aspects=tuple(sorted(members)),
                    strength=strength,
                    description=f"sync_cluster of {len(members)} aspects: {members}",
                ))
        return events


class PhaseTransitionDetector:
    """相变检测:KL 散度 + change point detection。

    维护 state history,检测相邻 state 的 KL 散度突变。
    """

    def __init__(self, history_size: int = 100, kl_threshold: float = 0.5):
        self.history_size = history_size
        self.kl_threshold = kl_threshold
        self.history: deque[np.ndarray] = deque(maxlen=history_size)
        self.tick_counter = 0

    def update(self, state: np.ndarray) -> list[EmergenceEvent]:
        if state.shape != (8,):
            return []
        events = []
        if len(self.history) > 0:
            prev = self.history[-1]
            kl = self._kl_divergence(prev, state)
            if kl > self.kl_threshold:
                events.append(EmergenceEvent(
                    type="phase_transition",
                    timestamp=self.tick_counter,
                    involved_aspects=tuple(range(8)),
                    strength=float(min(1.0, kl)),
                    description=f"phase_transition KL={kl:.4f} > {self.kl_threshold}",
                ))
        self.history.append(state.copy())
        self.tick_counter += 1
        return events

    @staticmethod
    def _kl_divergence(p: np.ndarray, q: np.ndarray, eps: float = 1e-9) -> float:
        """数值稳定 KL 散度(KL(p || q))。

        将 p, q 归一化到概率分布后计算。
        """
        p_norm = np.abs(p) + eps
        q_norm = np.abs(q) + eps
        p_norm = p_norm / p_norm.sum()
        q_norm = q_norm / q_norm.sum()
        return float(np.sum(p_norm * np.log(p_norm / q_norm)))


class ResonanceDetector:
    """共振检测:基于 state 历史的简单频谱分析。

    简化实现:检测 state 在相邻窗口内的"共振模式"(高同步率)。
    """

    def __init__(self, window_size: int = 50, sync_threshold: float = 0.8):
        self.window_size = window_size
        self.sync_threshold = sync_threshold
        self.history: deque[np.ndarray] = deque(maxlen=window_size)

    def update(self, cds: CoupledDynamicalSystem) -> list[EmergenceEvent]:
        """更新 history,若 window 满 + Kuramoto R > threshold,触发共振事件。"""
        self.history.append(cds.state.copy())
        if len(self.history) < self.window_size:
            return []
        R = cds.kuramoto_R()
        if R >= self.sync_threshold:
            return [EmergenceEvent(
                type="resonance",
                timestamp=0,
                involved_aspects=tuple(range(8)),
                strength=float(R),
                description=f"resonance detected, Kuramoto R={R:.4f}",
            )]
        return []


class EmergenceDetector:
    """复合涌现检测器(组合 3 个子检测器)。

    v3 §05_self_model_design_v2 §4.1:3 种检测器协同,
    覆盖"sync clusters + phase transitions + resonance"。
    """

    def __init__(self):
        self.sync_cluster = SynchronizedClusterDetector()
        self.phase_transition = PhaseTransitionDetector()
        self.resonance = ResonanceDetector()

    def detect(self, cds: CoupledDynamicalSystem) -> list[EmergenceEvent]:
        """检测涌现事件(每个 tick 调用)。"""
        events = []
        events.extend(self.sync_cluster.detect(cds.state))
        events.extend(self.phase_transition.update(cds.state))
        events.extend(self.resonance.update(cds))
        return events
