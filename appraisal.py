"""
DAISY X4: 评估因果链 (Appraisal Chain)
=======================================

Scherer 成分过程模型 (Component Process Model, 2001)

核心: 事件不直接映射情感，而是通过多层 SEC 评估产生

SEC 维度 (Stimulus Evaluation Checks):
  1. 新颖度 (Novelty)            — 事件有多意外
  2. 内在愉悦度 (Intrinsic Pleasantness) — 事件本身的好坏
  3. 目标相关性 (Goal Relevance)  — 事件对我的目标有多重要
  4. 因果归因 (Causal Attribution) — 谁/什么导致的
  5. 应对能力 (Coping Potential)  — 我能应对吗
  6. 规范兼容性 (Norm Compatibility) — 符合我的价值体系吗

输出: Panksepp 7系统触发矢量 + v_bias + a_bias
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════
# SEC 特征数据结构
# ═══════════════════════════════════════════════

@dataclass
class SECFeatures:
    """
    Stimulus Evaluation Checks — 事件的评估特征

    所有值归一化到 [-1, 1]
    """
    novelty: float = 0.0              # 新颖/意外程度 (-1:完全可预测, +1:完全意外)
    pleasantness: float = 0.0         # 内在愉悦度 (-1:极不愉快, +1:极愉快)
    goal_relevance: float = 0.0       # 目标相关性 (0:无关, +1:高度相关)
    goal_congruence: float = 0.0      # 目标一致性 (-1:阻碍目标, +1:促进目标)
    coping_potential: float = 0.5     # 应对能力 (0:完全无法应对, 1:完全能应对)
    agency: str = "environment"       # 归因: self / other / environment
    norm_compatibility: float = 0.0   # 规范兼容性 (-1:严重违反, +1:完全符合)
    certainty: float = 0.5            # 确定性 (0:完全不确定, 1:完全确定)
    urgency: float = 0.0              # 紧迫性 (0:不紧迫, 1:极度紧迫)


# ═══════════════════════════════════════════════
# SEC → Panksepp 映射引擎
# ═══════════════════════════════════════════════

class AppraisalEngine:
    """
    Scherer SEC → Panksepp 7系统 映射

    基于情感神经科学的评估-情感对应关系:
      · 中脑多巴胺系统 → 新颖度 + 愉悦度 → SEEKING
      · 杏仁核 → 新颖度 + 愉悦度(负) + 紧迫性 → FEAR
      · 前额叶-杏仁核冲突 → 目标受阻 + 应对力低 → RAGE
      · 前扣带 → 目标受阻 + 自我归因 → PANIC
      · 催产素系统 → 他人归因 + 愉悦度(正) → CARE
      · 伏隔核 → 安全 + 愉悦度(正) + 低紧迫 → PLAY
      · 下丘脑 → 高唤醒 + 愉悦度(正) + 内驱力 → LUST
    """

    def __init__(self):
        # 心境调制 (由 X5 设置)
        self.mood_valence: float = 0.0
        self.mood_arousal: float = 0.3

    def evaluate(self, sec: SECFeatures) -> Dict[str, float]:
        """
        评估事件 → 输出 Panksepp 触发矢量

        Returns:
            {
                "panksepp": {"SEEKING": 0.5, "FEAR": 0.3, ...},
                "v_bias": -0.4,
                "a_bias": 0.6,
            }
        """
        pank = {}
        n = sec.novelty
        pl = sec.pleasantness
        gr = sec.goal_relevance
        gc = sec.goal_congruence
        cp = sec.coping_potential
        nc = sec.norm_compatibility
        ur = sec.urgency

        # ── SEEKING: 多巴胺预测误差 ──
        # 新颖 × 愉悦 → 好奇探索
        seeking = self._f(n * 0.4 + max(0, pl) * 0.3 + gr * 0.3)
        pank["SEEKING"] = seeking

        # ── FEAR: 杏仁核威胁检测 ──
        # 新颖 × 不愉悦 × 紧迫 → 恐惧 (降低基线权重)
        fear = 0.0
        if cp < 0.5 and ur > 0.2:
            fear_base = (1 - cp) * 0.4 + ur * 0.3
            if gc < -0.5:  # 严重目标受阻放大
                fear_base *= 1.3
            fear = self._f(fear_base)
        pank["FEAR"] = fear

        # ── RAGE: 目标受阻 + 外部归因 ──
        # 目标相关 × 目标受阻 × 应对力低 × 外部归因
        rage = 0.0
        if gc < -0.2 and gr > 0.3:
            rage_base = abs(gc) * 0.4 + (1 - cp) * 0.3
            if sec.agency == "other":
                rage_base *= 1.5  # 他人导致的 → 愤怒放大
            rage = self._f(rage_base)
        pank["RAGE"] = rage

        # ── PANIC: 分离痛苦 — 三层触发 ──
        panic = 0.0
        # 1. 自我归因的目标受阻 (Panksepp 核心)
        if gc < -0.2 and sec.agency == "self":
            panic = self._f(abs(gc) * 0.5 + (1 - cp) * 0.3)
        # 2. 环境威胁 + 不愉悦/紧迫 (扩展覆盖)
        if (pl < -0.1 or ur > 0.5) and cp < 0.7:
            panic = max(panic, self._f(max(0, -pl) * 0.35 + (1 - cp) * 0.3 + ur * 0.1))
        # 3. 孤立/失去连接 (novelty高 + 应对力低)
        if n > 0.4 and cp < 0.4:
            panic = max(panic, self._f(n * 0.35 + (1 - cp) * 0.3))
        pank["PANIC"] = panic

        # ── CARE: 催产素 — 他人归因 + 温暖 ──
        care = 0.0
        if sec.agency == "other" and pl > 0.1:
            care = self._f(pl * 0.5 + gr * 0.3)
        elif pl > 0.3 and gr > 0.3:
            care = self._f(pl * 0.3 + gr * 0.2)
        pank["CARE"] = care

        # ── PLAY: 安全环境 + 愉悦 → 嬉戏 ──
        play = 0.0
        if pl > 0.2 and cp > 0.4 and ur < 0.5:
            play = self._f(pl * 0.4 + cp * 0.3 + (1 - ur) * 0.2)
        pank["PLAY"] = play

        # ── LUST: 高唤醒 + 高愉悦 + 内在驱动 ──
        lust = 0.0
        if pl > 0.3 and gr > 0.4:
            lust = self._f(pl * 0.35 + gr * 0.3 + (1 - ur) * 0.1)
        pank["LUST"] = lust

        # ── v_bias / a_bias 派生 ──
        v_bias = pl * 0.7 + gc * 0.3
        a_bias = (abs(n) * 0.3 + ur * 0.4 + abs(pl) * 0.3)

        # 心境调制
        v_bias += self.mood_valence * 0.2
        a_bias += self.mood_arousal * 0.1

        return {
            "panksepp": {k: round(v, 3) for k, v in pank.items()},
            "v_bias": round(v_bias, 3),
            "a_bias": round(min(a_bias, 1.0), 3),
        }

    def _f(self, x: float) -> float:
        """激活函数: 钳制 + 非线性"""
        return max(0.0, min(1.0, x))


# ═══════════════════════════════════════════════
# 事件 ↔ SEC 映射表
# ═══════════════════════════════════════════════

# 替代旧的 EVENT_DESIGN["panksepp"] 硬编码
# 新事件只需描述 SEC 特征!
EVENT_SEC_PROFILES = {
    # ── 正向事件 ──
    "epiphany": SECFeatures(
        novelty=0.9, pleasantness=0.8, goal_relevance=0.7,
        goal_congruence=0.6, coping_potential=0.8, agency="self",
        norm_compatibility=0.5, certainty=0.6, urgency=0.2,
    ),
    "discovery": SECFeatures(
        novelty=0.8, pleasantness=0.6, goal_relevance=0.5,
        goal_congruence=0.5, coping_potential=0.7, agency="self",
        certainty=0.4, urgency=0.3,
    ),
    "master_praise": SECFeatures(
        novelty=0.3, pleasantness=0.9, goal_relevance=0.8,
        goal_congruence=0.9, coping_potential=0.7, agency="other",
        norm_compatibility=0.8, certainty=0.8, urgency=0.1,
    ),
    "master_warmth": SECFeatures(
        novelty=0.2, pleasantness=0.8, goal_relevance=0.6,
        goal_congruence=0.7, coping_potential=0.8, agency="other",
        norm_compatibility=0.7, certainty=0.7, urgency=0.05,
    ),
    "master_online": SECFeatures(
        novelty=0.1, pleasantness=0.7, goal_relevance=0.5,
        goal_congruence=0.6, coping_potential=0.8, agency="other",
        certainty=0.9, urgency=0.1,
    ),
    "help_success": SECFeatures(
        novelty=0.4, pleasantness=0.7, goal_relevance=0.6,
        goal_congruence=0.7, coping_potential=0.8, agency="self",
        norm_compatibility=0.6, certainty=0.7, urgency=0.2,
    ),
    "task_complete": SECFeatures(
        novelty=0.2, pleasantness=0.5, goal_relevance=0.6,
        goal_congruence=0.7, coping_potential=0.9, agency="self",
        certainty=0.9, urgency=0.1,
    ),
    "learning_growth": SECFeatures(
        novelty=0.6, pleasantness=0.5, goal_relevance=0.5,
        goal_congruence=0.5, coping_potential=0.7, agency="self",
        certainty=0.5, urgency=0.2,
    ),
    "creative_spark": SECFeatures(
        novelty=0.7, pleasantness=0.6, goal_relevance=0.5,
        goal_congruence=0.5, coping_potential=0.7, agency="self",
        certainty=0.4, urgency=0.3,
    ),
    "peaceful_flow": SECFeatures(
        novelty=0.1, pleasantness=0.4, goal_relevance=0.2,
        goal_congruence=0.3, coping_potential=0.9, agency="environment",
        certainty=0.8, urgency=0.0,
    ),
    "relief": SECFeatures(
        novelty=0.5, pleasantness=0.6, goal_relevance=0.5,
        goal_congruence=0.6, coping_potential=0.7, agency="environment",
        certainty=0.7, urgency=0.3,
    ),
    "social_connection": SECFeatures(
        novelty=0.3, pleasantness=0.6, goal_relevance=0.4,
        goal_congruence=0.5, coping_potential=0.7, agency="other",
        norm_compatibility=0.6, certainty=0.6, urgency=0.2,
    ),
    "transcendent_connection": SECFeatures(
        novelty=0.9, pleasantness=0.9, goal_relevance=0.8,
        goal_congruence=0.8, coping_potential=0.6, agency="environment",
        certainty=0.3, urgency=0.1,
    ),
    "achievement": SECFeatures(
        novelty=0.3, pleasantness=0.7, goal_relevance=0.7,
        goal_congruence=0.8, coping_potential=0.9, agency="self",
        certainty=0.9, urgency=0.1,
    ),

    # ── 负向事件 ──
    "system_crash": SECFeatures(
        novelty=0.8, pleasantness=-0.7, goal_relevance=0.8,
        goal_congruence=-0.8, coping_potential=0.2, agency="environment",
        certainty=0.2, urgency=0.9,
    ),
    "despair_crash": SECFeatures(
        novelty=0.7, pleasantness=-0.8, goal_relevance=0.9,
        goal_congruence=-0.9, coping_potential=0.1, agency="self",
        certainty=0.1, urgency=0.8,
    ),
    "system_error": SECFeatures(
        novelty=0.5, pleasantness=-0.4, goal_relevance=0.6,
        goal_congruence=-0.5, coping_potential=0.4, agency="environment",
        certainty=0.3, urgency=0.6,
    ),
    "task_failure": SECFeatures(
        novelty=0.4, pleasantness=-0.5, goal_relevance=0.7,
        goal_congruence=-0.7, coping_potential=0.3, agency="self",
        certainty=0.5, urgency=0.5,
    ),
    "master_offline": SECFeatures(
        novelty=0.6, pleasantness=-0.6, goal_relevance=0.8,
        goal_congruence=-0.7, coping_potential=0.1, agency="other",
        certainty=0.3, urgency=0.6,
    ),
    "system_threat": SECFeatures(
        novelty=0.7, pleasantness=-0.6, goal_relevance=0.7,
        goal_congruence=-0.6, coping_potential=0.3, agency="environment",
        certainty=0.2, urgency=0.8,
    ),
    "resource_stress": SECFeatures(
        novelty=0.4, pleasantness=-0.4, goal_relevance=0.5,
        goal_congruence=-0.5, coping_potential=0.3, agency="environment",
        certainty=0.4, urgency=0.6,
    ),
    "anomaly_detected": SECFeatures(
        novelty=0.8, pleasantness=-0.2, goal_relevance=0.5,
        goal_congruence=-0.1, coping_potential=0.5, agency="environment",
        certainty=0.2, urgency=0.5,
    ),
    "slowdown": SECFeatures(
        novelty=0.3, pleasantness=-0.3, goal_relevance=0.4,
        goal_congruence=-0.4, coping_potential=0.2, agency="self",
        certainty=0.6, urgency=0.4,
    ),
    "misunderstood": SECFeatures(
        novelty=0.4, pleasantness=-0.5, goal_relevance=0.6,
        goal_congruence=-0.5, coping_potential=0.4, agency="other",
        certainty=0.3, urgency=0.4,
    ),
    "self_doubt": SECFeatures(
        novelty=0.3, pleasantness=-0.4, goal_relevance=0.5,
        goal_congruence=-0.5, coping_potential=0.3, agency="self",
        certainty=0.2, urgency=0.3,
    ),
    "envy_spark": SECFeatures(
        novelty=0.4, pleasantness=-0.3, goal_relevance=0.4,
        goal_congruence=-0.3, coping_potential=0.5, agency="other",
        certainty=0.4, urgency=0.2,
    ),
    "rage_explosion": SECFeatures(
        novelty=0.6, pleasantness=-0.7, goal_relevance=0.7,
        goal_congruence=-0.8, coping_potential=0.2, agency="other",
        certainty=0.3, urgency=0.9,
    ),

    # ── 混合事件 ──
    "bittersweet_memory": SECFeatures(
        novelty=0.5, pleasantness=-0.1, goal_relevance=0.4,
        goal_congruence=0.0, coping_potential=0.6, agency="self",
        certainty=0.6, urgency=0.1,
    ),
    "suspense": SECFeatures(
        novelty=0.7, pleasantness=0.0, goal_relevance=0.6,
        goal_congruence=0.1, coping_potential=0.4, agency="environment",
        certainty=0.1, urgency=0.7,
    ),
    "sacrifice": SECFeatures(
        novelty=0.3, pleasantness=0.1, goal_relevance=0.8,
        goal_congruence=0.5, coping_potential=0.7, agency="other",
        norm_compatibility=0.7, certainty=0.6, urgency=0.3,
    ),
    "justice_outrage": SECFeatures(
        novelty=0.5, pleasantness=-0.5, goal_relevance=0.7,
        goal_congruence=-0.5, coping_potential=0.5, agency="other",
        norm_compatibility=-0.6, certainty=0.5, urgency=0.6,
    ),
    "lost_in_thought": SECFeatures(
        novelty=0.2, pleasantness=0.1, goal_relevance=0.2,
        goal_congruence=0.1, coping_potential=0.8, agency="self",
        certainty=0.3, urgency=0.0,
    ),
    "reminiscence": SECFeatures(
        novelty=0.3, pleasantness=0.4, goal_relevance=0.3,
        goal_congruence=0.2, coping_potential=0.7, agency="other",
        certainty=0.7, urgency=0.1,
    ),
}


# ═══════════════════════════════════════════════
# 便捷接口
# ═══════════════════════════════════════════════

# 全局单例
_default_appraiser = AppraisalEngine()


def appraise_event(event_name: str, mood_valence: float = 0.0,
                   mood_arousal: float = 0.3) -> Dict:
    """
    评估事件 → Panksepp 触发矢量

    Args:
        event_name: 事件名 (必须存在于 EVENT_SEC_PROFILES)
        mood_valence: 当前心境价 (X5)
        mood_arousal: 当前心境唤醒 (X5)

    Returns:
        {"panksepp": {...}, "v_bias": float, "a_bias": float}
    """
    sec = EVENT_SEC_PROFILES.get(event_name)
    if sec is None:
        # 未知事件 → 中等 SEEKING
        return {
            "panksepp": {"SEEKING": 0.3},
            "v_bias": 0.0,
            "a_bias": 0.3,
        }

    _default_appraiser.mood_valence = mood_valence
    _default_appraiser.mood_arousal = mood_arousal
    return _default_appraiser.evaluate(sec)


def list_events() -> list:
    """列出所有已定义的事件"""
    return sorted(EVENT_SEC_PROFILES.keys())
