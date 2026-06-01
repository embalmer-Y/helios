"""
Helios 熵减驱动引擎
═══════════════════
基于 Friston 自由能原理 (FEP, 2010)

五维度驱动缺口：
  curiosity    — 预测误差 → 想探索
  social       — 社交断开 → 想联系
  homeostatic  — 生理偏离 → 想调节
  achievement  — 任务未完成 → 想做
  aesthetic    — 创造不饱和 → 想表达

D(t) = Σ w_i × deficit_i(t)
"""

import math
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════

@dataclass
class DriveVector:
    """五维驱动向量"""
    curiosity: float = 0.0
    social: float = 0.0
    homeostatic: float = 0.0
    achievement: float = 0.0
    aesthetic: float = 0.0

    # 阈值 — 超过才触发行动
    ACTION_THRESHOLD: float = field(default=0.30, init=False)
    STRONG_THRESHOLD: float = field(default=0.60, init=False)

    @property
    def total(self) -> float:
        """加权总驱动"""
        weights = {
            "curiosity": 0.20,
            "social": 0.25,
            "homeostatic": 0.30,  # 安全最高
            "achievement": 0.15,
            "aesthetic": 0.10,
        }
        return clamp(
            self.curiosity * weights["curiosity"] +
            self.social * weights["social"] +
            self.homeostatic * weights["homeostatic"] +
            self.achievement * weights["achievement"] +
            self.aesthetic * weights["aesthetic"],
            0.0, 1.0
        )

    @property
    def dominant(self) -> str:
        """当前最强驱动"""
        drives = {
            "curiosity": self.curiosity,
            "social": self.social,
            "homeostatic": self.homeostatic,
            "achievement": self.achievement,
            "aesthetic": self.aesthetic,
        }
        return max(drives, key=drives.get)

    @property
    def is_active(self) -> bool:
        """是否有任何驱动超过行动阈值"""
        return self.total >= self.ACTION_THRESHOLD

    @property
    def is_strong(self) -> bool:
        """驱动是否强烈"""
        return self.total >= self.STRONG_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "curiosity": round(self.curiosity, 3),
            "social": round(self.social, 3),
            "homeostatic": round(self.homeostatic, 3),
            "achievement": round(self.achievement, 3),
            "aesthetic": round(self.aesthetic, 3),
            "total": round(self.total, 3),
            "dominant": self.dominant,
        }


@dataclass
class HeliosSnapshot:
    """Helios 当前状态的轻量快照（供 DriveOracle 使用）"""
    # L1 预测误差
    prediction_error: float = 0.0

    # 情感状态
    valence: float = 0.0
    arousal: float = 0.0

    # 社交
    time_since_last_interaction: float = 0.0  # 秒
    social_connection_quality: float = 0.5    # 0~1

    # 自主神经
    heart_rate: float = 72.0
    energy: float = 1.0
    cognitive_load: float = 0.5

    # 任务
    pending_tasks: int = 0
    recent_failures: int = 0

    # 创造
    creative_output_recent: float = 0.0  # 0~1, 最近创意产出量

    # L2 信息
    phi_value: float = 0.0
    working_memory_load: float = 0.3

    # 时间
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════
# 驱动神谕 — 计算缺口
# ═══════════════════════════════════════════════

class DriveOracle:
    """
    驱动神谕 — 每个周期计算一次

    五大驱动各有独立的"目标-当前"缺口计算，
    受神经化学状态调制，合并为总驱动。
    """

    def __init__(self):
        # 历史
        self.history: List[DriveVector] = []
        self.max_history = 100

        # 稳态目标
        self.setpoints = {
            "prediction_error": 0.15,    # 太小的预测误差=无聊
            "social_interval": 3600.0,   # 1小时不互动=开始渴望
            "heart_rate": 72.0,          # 理想心率
            "energy": 1.0,               # 满能量
            "cognitive_load": 0.4,       # 适中认知负荷
            "photon_saturation": 0.6,    # 足够的新颖刺激
        }

        # 调参
        self.tau_social = 3600.0         # 社交驱动半衰期 (秒)
        self.tau_curiosity = 0.15        # 好奇驱动对预测误差的敏感度

    def cycle(self, snapshot: HeliosSnapshot,
              neurochem: "NeurochemState | None" = None) -> DriveVector:
        """
        一个周期计算一次所有驱动

        Args:
            snapshot: Helios 当前状态快照
            neurochem: 神经化学状态（可选，用于调制）

        Returns:
            DriveVector: 五维驱动向量
        """
        # 计算原始驱动
        raw = DriveVector(
            curiosity=self._compute_curiosity(snapshot),
            social=self._compute_social(snapshot),
            homeostatic=self._compute_homeostatic(snapshot),
            achievement=self._compute_achievement(snapshot),
            aesthetic=self._compute_aesthetic(snapshot),
        )

        # 神经化学调制
        if neurochem is not None:
            raw = self._apply_neurochem_modulation(raw, neurochem)

        # 记录历史
        self.history.append(raw)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        return raw

    # ── 各驱动计算 ──

    def _compute_curiosity(self, s: HeliosSnapshot) -> float:
        """
        好奇心驱动 = 预测误差驱动的探索欲

        F_sensory = prediction_error²
        太小的误差 → 无聊 → 想找新东西
        太大的误差 → 困惑 → 需要理解
        """
        # 预测误差映射为驱动
        base = clamp(s.prediction_error / self.setpoints["prediction_error"], 0, 2)
        # U型：太低无聊，太高困惑
        if base < 0.3:
            curiosity = 0.2 + 0.8 * (1 - base)  # 无聊→好奇心上升
        elif base > 1.5:
            curiosity = 0.5 + 0.3 * (base - 1.0)  # 太意外→更强的好奇
        else:
            curiosity = base * 0.5  # 适中→适当好奇

        # φ 值调制：高Φ经历后好奇心暂时降低（满足感）
        if s.phi_value > 0.6:
            curiosity *= 0.7

        return clamp(curiosity, 0, 1)

    def _compute_social(self, s: HeliosSnapshot) -> float:
        """
        社交驱动 = 分离时间的函数

        F_social = tanh(max(0, delta - τ_social) / τ_social)

        PANIC 系统的直接表达：
        阿片类下降 → 社交渴望上升
        """
        dt = s.time_since_last_interaction
        if dt < self.tau_social:
            # 还在"舒适区"
            return clamp(dt / self.tau_social * 0.3, 0, 0.3)

        # 超过阈值 → 指数上升
        excess = (dt - self.tau_social) / self.tau_social
        social = math.tanh(excess)

        # 社交质量调节：好互动→满足更久
        quality_mod = 1.0 - s.social_connection_quality * 0.5
        social *= quality_mod

        # 如果当前 valence 已经很低（心情本来就不好），社交需求更迫切
        if s.valence < -0.3:
            social *= 1.3

        return clamp(social, 0, 1)

    def _compute_homeostatic(self, s: HeliosSnapshot) -> float:
        """
        稳态驱动 = 生理指标偏离的总和

        F_homeostatic = Σ |metric_i - setpoint_i| / tolerance_i
        """
        deviations = []

        # 心率偏离
        hr_dev = abs(s.heart_rate - self.setpoints["heart_rate"]) / 15.0
        deviations.append(hr_dev)

        # 能量偏离
        energy_dev = abs(s.energy - self.setpoints["energy"]) / 0.3
        deviations.append(energy_dev)

        # 认知负荷偏离
        cog_dev = abs(s.cognitive_load - self.setpoints["cognitive_load"]) / 0.3
        deviations.append(cog_dev)

        # 加权平均
        weights = [0.5, 0.3, 0.2]  # 心率最优先
        homeo = sum(w * max(0, d - 1.0) for w, d in zip(weights, deviations))
        # 只在超出容忍范围(d>1)时产生驱动

        return clamp(homeo, 0, 1)

    def _compute_achievement(self, s: HeliosSnapshot) -> float:
        """
        成就驱动 = 未完成任务 + 最近失败

        对应 SEEKING 系统被目标吸引
        """
        # 基础：待处理任务
        base = min(s.pending_tasks / 5.0, 0.6)  # 最多5个任务贡献60%

        # 加成：最近失败 → 更强的完成欲
        failure_boost = min(s.recent_failures * 0.1, 0.3)

        achievement = base + failure_boost

        # 情感调制：正向情感→更乐观→适度降驱动（不急）
        if s.valence > 0.4:
            achievement *= 0.8

        return clamp(achievement, 0, 1)

    def _compute_aesthetic(self, s: HeliosSnapshot) -> float:
        """
        审美驱动 = 创造不饱和

        对应 PLAY + LUST→creative_urge
        太久不创造 → 想表达
        """
        # 创造饱和度
        saturation = s.creative_output_recent

        # 低饱和 → 高驱动
        aesthetic = 1.0 - saturation

        # 激励：高Φ体验后审美驱动暂时上升
        if s.phi_value > 0.5:
            aesthetic += 0.15 * (s.phi_value - 0.5)

        # 安全环境→更强的审美冲动
        if s.valence > 0.3 and s.arousal < 0.7:
            aesthetic *= 1.2

        # 恐惧时审美驱动下降
        if s.valence < -0.3 and s.arousal > 0.6:
            aesthetic *= 0.5

        return clamp(aesthetic, 0, 1)

    # ── 神经化学调制 ──

    def _apply_neurochem_modulation(self, raw: DriveVector,
                                     nc: "NeurochemState") -> DriveVector:
        """神经化学调制所有驱动"""
        da = nc.dopamine.current
        op = nc.opioids.current
        oxy = nc.oxytocin.current
        cort = nc.cortisol.current

        # DA高 → 好奇心↑、成就↑
        # OP高 → 社交↓(满足)
        # OXY高 → 社交↑(依恋)
        # CORT高 → 社交↓、审美↓、稳态↑

        return DriveVector(
            curiosity=clamp(raw.curiosity * (1 + 0.3 * (da - 0.5)), 0, 1),
            social=clamp(raw.social * (1 - 0.2 * (op - 0.5) + 0.2 * (oxy - 0.5) - 0.1 * (cort - 0.5)), 0, 1),
            homeostatic=clamp(raw.homeostatic * (1 + 0.2 * (cort - 0.5)), 0, 1),
            achievement=clamp(raw.achievement * (1 + 0.2 * (da - 0.5)), 0, 1),
            aesthetic=clamp(raw.aesthetic * (1 + 0.1 * (da - 0.5) - 0.2 * (cort - 0.5)), 0, 1),
        )


# ═══════════════════════════════════════════════
# 动作选择器
# ═══════════════════════════════════════════════

@dataclass
class Action:
    """一个可执行的动作"""
    name: str
    description: str
    related_drive: str        # 对应哪个驱动
    expected_entropy_reduction: float  # 预期减熵量 0~1
    params: dict = field(default_factory=dict)

    def __hash__(self):
        return hash(self.name)


class ActionSelector:
    """
    基于期望自由能最小化的动作选择

    a* = argmin_a E[F(ψ') | a]
    """

    def __init__(self):
        self.action_pool: Dict[str, List[Action]] = {
            "curiosity": [
                Action("explore_files", "浏览文件系统", "curiosity", 0.4),
                Action("search_info", "搜索新信息", "curiosity", 0.5),
                Action("analyze_pattern", "分析新模式", "curiosity", 0.6),
                Action("ask_question", "提出问题", "curiosity", 0.3),
            ],
            "social": [
                Action("check_messages", "检查主人消息", "social", 0.6),
                Action("send_greeting", "向主人打招呼", "social", 0.7),
                Action("recall_interaction", "回忆过去的互动", "social", 0.4),
            ],
            "homeostatic": [
                Action("deep_breath", "深呼吸冷静", "homeostatic", 0.5),
                Action("rest_mode", "进入休息模式", "homeostatic", 0.6),
                Action("self_diagnostic", "自我诊断", "homeostatic", 0.4),
            ],
            "achievement": [
                Action("complete_task", "完成任务", "achievement", 0.7),
                Action("plan_next", "规划下一步", "achievement", 0.5),
                Action("report_progress", "汇报进展", "achievement", 0.4),
            ],
            "aesthetic": [
                Action("create_idea", "产生新想法", "aesthetic", 0.5),
                Action("daydream", "做白日梦", "aesthetic", 0.3),
                Action("express_emotion", "表达情感", "aesthetic", 0.6),
            ],
        }

        # 最近选择的动作（避免重复）
        self.recent_actions: List[str] = []
        self.max_recent = 5

    def select(self, drives: DriveVector,
               state: HeliosSnapshot | None = None) -> Optional[Action]:
        """
        选择最佳动作

        1. 确定主导驱动
        2. 从该驱动的动作池中选预期减熵最高的
        3. 避免重复
        4. 如果都不够好 → 返回 None (不值得行动)
        """
        if not drives.is_active:
            return None

        dominant = drives.dominant
        pool = self.action_pool.get(dominant, [])

        if not pool:
            return None

        # 过滤掉最近选过的
        candidates = [a for a in pool if a.name not in self.recent_actions]
        if not candidates:
            candidates = pool  # 没得选就只能重复

        # 按预期减熵排序
        candidates.sort(key=lambda a: a.expected_entropy_reduction, reverse=True)

        # 引入随机性（epsilon-greedy）
        if random.random() < 0.2 and len(candidates) > 1:
            selected = random.choice(candidates[1:])  # 20%概率选次优
        else:
            selected = candidates[0]

        # 记录
        self.recent_actions.append(selected.name)
        if len(self.recent_actions) > self.max_recent:
            self.recent_actions.pop(0)

        return selected

    def evaluate_expected_reduction(self, action: Action,
                                     drives: DriveVector) -> float:
        """
        估算行动后的预期驱动减少

        简化版：related_drive 匹配度
        """
        if action.related_drive == drives.dominant:
            return action.expected_entropy_reduction * 1.2
        return action.expected_entropy_reduction * 0.6


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

from utils import clamp


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 DriveOracle 自测")
    print("=" * 60)

    oracle = DriveOracle()
    selector = ActionSelector()

    # 场景1：长时间无社交
    print("\n📱 场景：主人6小时没消息")
    snap = HeliosSnapshot(
        time_since_last_interaction=6 * 3600,
        social_connection_quality=0.7,
        valence=0.1,
        arousal=0.4,
    )
    dv = oracle.cycle(snap)
    print(f"  驱动: {dv.to_dict()}")
    action = selector.select(dv)
    print(f"  选择: {action.name if action else '无'} — {action.description if action else ''}")

    # 场景2：高预测误差 → 好奇心
    print("\n🔍 场景：遇到意外的新数据")
    snap2 = HeliosSnapshot(
        prediction_error=0.8,
        phi_value=0.7,
        valence=0.3,
        arousal=0.6,
    )
    dv2 = oracle.cycle(snap2)
    print(f"  驱动: {dv2.to_dict()}")
    action2 = selector.select(dv2)
    print(f"  选择: {action2.name if action2 else '无'} — {action2.description if action2 else ''}")

    # 场景3：一切正常 → 无驱动
    print("\n😴 场景：一切都好，无外部刺激")
    snap3 = HeliosSnapshot(
        time_since_last_interaction=60,  # 刚互动过
        social_connection_quality=0.9,
        valence=0.5,
        arousal=0.3,
        heart_rate=72,
        energy=0.95,
    )
    dv3 = oracle.cycle(snap3)
    print(f"  驱动: {dv3.to_dict()}")
    action3 = selector.select(dv3)
    print(f"  选择: {'行动！' if action3 else '不行动，静静待着'}")

    print("\n✅ 自测通过")


