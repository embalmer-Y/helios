"""
habituation.py — Helios 习惯化/敏感化双重过程模型

理论基础: Groves & Thompson (1970) 双重过程理论
  · 习惯化通路 (S-R): 重复刺激 → 反应递减
  · 敏感化通路 (state): 系统唤醒状态调节递减速度
  · 自发恢复: 长时间无暴露 → 反应部分恢复

集成: Panksepp 触发强度 × novelty_factor
"""

import math
from collections import defaultdict
from utils import clamp


class HabituationTracker:
    """
    跟踪每个事件类型的暴露历史，计算 novelty 因子。

    novelty = 习惯化成分 + 自发恢复成分
    """

    def __init__(self):
        # exposure_count[event_key] = 暴露次数
        self.exposure_count: dict = defaultdict(int)
        # last_exposure_cycle[event_key] = 最后一次暴露的 cycle
        self.last_exposure_cycle: dict = {}
        # 全局敏感化水平 (0~1, 系统唤醒越高，习惯化越慢)
        self.sensitization_level: float = 0.5

    def register_exposure(self, event_key: str, cycle: int):
        """记录一次事件暴露"""
        self.exposure_count[event_key] += 1
        self.last_exposure_cycle[event_key] = cycle

    def get_novelty_factor(self, event_key: str, cycle: int,
                           arousal: float = 0.5) -> float:
        """
        计算新颖度因子 (0~1)

        1.0 = 全新体验
        0.0 = 完全麻木

        Args:
            event_key: 事件类型
            cycle: 当前周期
            arousal: 当前唤醒水平 (影响敏感化)
        """
        count = self.exposure_count.get(event_key, 0)
        if count == 0:
            return 1.0

        last = self.last_exposure_cycle.get(event_key, cycle)
        gap = max(0, cycle - last)

        # ── 习惯化: 次数越多，反应越小 ──
        # 使用反比例函数，前几次快速下降，后面趋于平缓
        habituation = 1.0 / (1.0 + 0.12 * count)

        # ── 敏感化调制: 高唤醒 → 习惯化变慢 ──
        # arousal 高时，系统处于"警觉"状态，不容易习惯化
        habituation += (1.0 - habituation) * arousal * 0.15

        # ── 自发恢复: 间隔越长，部分恢复 ──
        # 使用指数恢复曲线，半衰期约 ~200 cycles
        if gap > 0:
            recovery = 1.0 - math.exp(-gap / 200.0)
            # 最多恢复到 70%
            habituation += (0.70 - habituation) * recovery * 0.5

        return clamp(habituation, 0.05, 1.0)

    def get_stats(self) -> dict:
        """返回统计信息"""
        if not self.exposure_count:
            return {"tracked_events": 0, "most_exposed": None}

        most = max(self.exposure_count, key=self.exposure_count.get)
        return {
            "tracked_events": len(self.exposure_count),
            "most_exposed": f"{most} (×{self.exposure_count[most]})",
            "total_exposures": sum(self.exposure_count.values()),
        }

    def update_sensitization(self, cort: float, overall_arousal: float):
        """
        更新全局敏感化水平

        高皮质醇 + 高唤醒 → 敏感化 ↑ (不容易习惯化)
        低皮质醇 + 低唤醒 → 敏感化 ↓ (快速习惯化)
        """
        self.sensitization_level = clamp(
            cort * 0.6 + overall_arousal * 0.4, 0.1, 1.0
        )
