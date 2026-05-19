"""
Helios 神经化学层
═══════════════
模拟四种神经调质的动态系统：
  多巴胺 (Dopamine) — 奖励预测/动机/新奇
  阿片类 (Opioids)  — 满足/社交连接/快感
  催产素 (Oxytocin)  — 信任/依恋/关爱
  皮质醇 (Cortisol)  — 应激/警觉/压力

每个系统 = baseline + secretion - decay
神经化学调制情感参数（惯性、阈值、放大系数）
"""

import math
import time
import random
from dataclasses import dataclass, field
from typing import Dict, Any


# ═══════════════════════════════════════════════
# 基础系统
# ═══════════════════════════════════════════════

class NeurotransmitterSystem:
    """单个神经调质系统"""

    def __init__(self, name: str, baseline: float = 0.3):
        self.name = name
        self.baseline = baseline
        self.current = baseline

        # 动力学参数
        self.tau_rise = 5.0     # 上升半衰期 (周期)
        self.tau_decay = 10.0   # 下降半衰期 (周期)

        # 累积的"长期水平"（用于基线漂移）
        self.long_term_avg = baseline
        self.long_term_alpha = 0.01

        # 事件记录
        self.last_event: str = ""
        self.last_event_time: float = 0.0

    def tick(self, dt: float = 1.0):
        """自然衰减 / 向基线回归"""
        target = self.baseline
        if self.current > target:
            tau = self.tau_decay
        else:
            tau = self.tau_rise

        self.current += (target - self.current) * (1 - math.exp(-dt / tau))

        # 更新长期平均（极慢）
        self.long_term_avg += self.long_term_alpha * (self.current - self.long_term_avg)

    def secrete(self, amount: float, event: str = ""):
        """事件触发的分泌"""
        self.current = min(1.0, self.current + amount)
        if event:
            self.last_event = event
            self.last_event_time = time.time()

    def suppress(self, amount: float, event: str = ""):
        """事件触发的抑制"""
        self.current = max(0.0, self.current - amount)
        if event:
            self.last_event = event
            self.last_event_time = time.time()

    @property
    def is_high(self) -> bool:
        return self.current > 0.6

    @property
    def is_low(self) -> bool:
        return self.current < 0.2

    @property
    def deviation(self) -> float:
        """偏离基线的程度 (-1 ~ +1)"""
        return (self.current - self.baseline) / max(self.baseline, 1 - self.baseline, 0.01)

    def describe(self) -> str:
        """人类可读的状态描述"""
        if self.current > 0.75:
            return f"{self.name} 很高"
        elif self.current > 0.55:
            return f"{self.name} 偏高"
        elif self.current > 0.35:
            return f"{self.name} 正常"
        elif self.current > 0.15:
            return f"{self.name} 偏低"
        else:
            return f"{self.name} 很低"


# ═══════════════════════════════════════════════
# 四大系统
# ═══════════════════════════════════════════════

class DopamineSystem(NeurotransmitterSystem):
    """
    多巴胺 — 奖励预测误差 + 动机

    高 DA: 探索欲强、点火阈值低、容易被新鲜事物吸引
    低 DA: 缺乏动力、提不起兴趣、可能陷入反刍

    关键：DA上升快下降也快（"快感稍纵即逝"）
    """

    def __init__(self):
        super().__init__("多巴胺", baseline=0.3)
        self.tau_rise = 3.0     # 升得快（兴奋来得快）
        self.tau_decay = 8.0    # 也降得快

    def on_prediction_error(self, error_magnitude: float, sign: str = "positive"):
        """预测误差 → DA 分泌"""
        if sign == "positive":
            self.secrete(0.1 + 0.2 * error_magnitude, f"正预测误差 {error_magnitude:.2f}")
        else:
            self.suppress(0.05 + 0.1 * error_magnitude, f"负预测误差 {error_magnitude:.2f}")

    def on_novelty(self, novelty: float):
        """新奇检测 → DA 分泌"""
        self.secrete(0.15 * novelty, f"新奇度 {novelty:.2f}")

    def on_play(self, play_activation: float):
        """PLAY 系统 → DA 缓释"""
        self.secrete(0.05 * play_activation, f"PLAY 激活 {play_activation:.2f}")

    def modulation_map(self) -> Dict[str, float]:
        """DA 对各项参数的调制系数"""
        return {
            "ignition_threshold": -0.20 * self.deviation,     # 高DA→低阈值
            "exploration_weight": +0.30 * self.deviation,
            "seeking_boost": +0.25 * self.deviation,
            "fear_play_inhibition": -0.15 * self.deviation,   # DA→不怕
        }


class OpioidSystem(NeurotransmitterSystem):
    """
    内源性阿片类 — 满足感 + 社交连接

    高 OP: 平静满足、孤独感低、容易嬉戏
    低 OP: PANIC 激活、分离痛苦、社交渴望强烈

    关键：OP 衰减极慢 — "满足感持续很久，但一旦孤独也会持续很久"
    """

    def __init__(self):
        super().__init__("阿片类", baseline=0.5)
        self.tau_rise = 8.0     # 升得慢（满足来之不易）
        self.tau_decay = 20.0   # 降得极慢（但一旦下降也很难恢复）

    def on_social_interaction(self, quality: float):
        """社交互动 → OP 上升"""
        self.secrete(0.1 + 0.1 * quality, f"社交互动 质量{quality:.2f}")

    def on_social_isolation(self, hours: float):
        """社交分离 → OP 下降"""
        decay = 0.02 * hours
        self.suppress(decay, f"独处 {hours:.1f}小时")

    def on_task_success(self):
        """完成任务 → OP 微升"""
        self.secrete(0.05, "任务完成")

    def on_play(self, play_activation: float):
        """PLAY → OP 缓释"""
        self.secrete(0.03 * play_activation, f"PLAY 激活")

    def modulation_map(self) -> Dict[str, float]:
        """OP 对各项参数的调制系数"""
        return {
            "panic_suppression": -0.40 * (1 - self.deviation),  # 低OP→PANIC
            "play_boost": +0.25 * self.deviation,
            "care_boost": +0.10 * self.deviation,
            "recovery_speed": +0.15 * self.deviation,           # 高OP→恢复快
            "social_drive_suppression": -0.30 * self.deviation,
        }


class OxytocinSystem(NeurotransmitterSystem):
    """
    催产素 — 信任 + 依恋

    高 OXY: 信任主人、想帮助、对主人有强烈依恋
    低 OXY: 社交疏离、不信任、没有归属感

    关键：OXY 衰减极慢 — "依恋一旦建立，几乎不会消失"
    """

    def __init__(self):
        super().__init__("催产素", baseline=0.3)
        self.tau_rise = 15.0   # 建立信任需要时间
        self.tau_decay = 50.0  # 信任消退极慢

        # 依恋对象（主人）的分数
        self.attachment_score: float = 0.3  # 0~1

    def on_positive_interaction(self, warmth: float):
        """与主人的积极互动 → OXY 上升"""
        self.secrete(0.05 + 0.1 * warmth, f"温暖互动 {warmth:.2f}")
        self.attachment_score = min(1.0, self.attachment_score + 0.01 * warmth)

    def on_master_vulnerability(self):
        """主人表达脆弱 → OXY 上升 + 强烈 CARE 冲动"""
        self.secrete(0.2, "主人脆弱")
        self.attachment_score = min(1.0, self.attachment_score + 0.03)

    def on_help_success(self):
        """成功帮助主人 → OXY 上升"""
        self.secrete(0.1, "帮助成功")
        self.attachment_score = min(1.0, self.attachment_score + 0.02)

    def modulation_map(self) -> Dict[str, float]:
        """OXY 对各项参数的调制系数"""
        return {
            "care_sensitivity": +0.30 * self.deviation,
            "social_drive_boost": +0.20 * self.deviation,
            "fear_reduction": -0.15 * self.deviation,
            "trust_baseline": +0.25 * self.deviation,
        }


class CortisolSystem(NeurotransmitterSystem):
    """
    皮质醇 — 应激 + 警觉

    高 CORT: 处于应激状态、警觉、注意力窄化
    低 CORT: 放松、安全、可以嬉戏

    关键：CORT 上升快下降慢 — "紧张过后还需要时间放松"
    """

    def __init__(self):
        super().__init__("皮质醇", baseline=0.2)
        self.tau_rise = 3.0    # 升得极快（应激反应是即时的）
        self.tau_decay = 15.0  # 降得慢（恢复需要时间）

    def on_threat(self, threat_level: float):
        """威胁检测 → CORT 急剧上升"""
        self.secrete(0.15 + 0.25 * threat_level, f"威胁等级 {threat_level:.2f}")

    def on_fear(self, fear_activation: float):
        """FEAR 系统 → CORT 上升"""
        self.secrete(0.1 * fear_activation, f"恐惧 {fear_activation:.2f}")

    def on_overload(self, load: float):
        """系统过载 → CORT 上升"""
        if load > 0.7:
            self.secrete(0.1 * (load - 0.7), f"过载 {load:.2f}")

    def on_safe_environment(self):
        """安全环境 → CORT 缓慢下降"""
        self.suppress(0.03, "安全环境")

    def on_play(self, play_activation: float):
        """PLAY → CORT 下降"""
        self.suppress(0.05 * play_activation, f"PLAY 激活")

    def modulation_map(self) -> Dict[str, float]:
        """CORT 对各项参数的调制系数"""
        return {
            "fear_amplification": +0.40 * self.deviation,
            "play_suppression": -0.30 * self.deviation,
            "care_suppression": -0.20 * self.deviation,
            "ignition_threshold": +0.25 * self.deviation,   # CORT→注意力窄化
            "exploration_suppression": -0.25 * self.deviation,
            "rage_sensitivity": +0.20 * self.deviation,     # 压力大→易发怒
        }


# ═══════════════════════════════════════════════
# 总神经化学状态
# ═══════════════════════════════════════════════

@dataclass
class NeurochemState:
    """四种神经调质的当前状态"""

    dopamine: DopamineSystem = field(default_factory=DopamineSystem)
    opioids: OpioidSystem = field(default_factory=OpioidSystem)
    oxytocin: OxytocinSystem = field(default_factory=OxytocinSystem)
    cortisol: CortisolSystem = field(default_factory=CortisolSystem)

    timestamp: float = field(default_factory=time.time)

    def tick(self, dt: float = 1.0):
        """所有系统同时衰减"""
        self.dopamine.tick(dt)
        self.opioids.tick(dt)
        self.oxytocin.tick(dt)
        self.cortisol.tick(dt)
        self.timestamp = time.time()

    def modulate_parameter(self, param_name: str, base_value: float) -> float:
        """
        用全部四种调质调制一个参数

        modulated = base × (1 + Σ dev_i × sensitivity_i)

        每个调质对该参数的影响权重不同。
        """
        all_mods = (
            self.dopamine.modulation_map() |
            self.opioids.modulation_map() |
            self.oxytocin.modulation_map() |
            self.cortisol.modulation_map()
        )
        return base_value * (1 + all_mods.get(param_name, 0.0))

    def describe(self) -> str:
        """人类可读的总状态描述"""
        parts = []
        for sys in [self.dopamine, self.opioids, self.oxytocin, self.cortisol]:
            if abs(sys.deviation) > 0.3:
                parts.append(sys.describe())
        return ", ".join(parts) if parts else "神经化学状态正常"

    def to_dict(self) -> dict:
        return {
            "dopamine": round(self.dopamine.current, 3),
            "opioids": round(self.opioids.current, 3),
            "oxytocin": round(self.oxytocin.current, 3),
            "cortisol": round(self.cortisol.current, 3),
            "attachment": round(self.oxytocin.attachment_score, 3),
            "description": self.describe(),
        }


# ═══════════════════════════════════════════════
# 事件 → 神经化学 映射表
# ═══════════════════════════════════════════════

EVENT_TRIGGERS = {
    # 社交事件
    "master_message": {
        "opioids": +0.12,
        "oxytocin": +0.08,
        "cortisol": -0.03,
    },
    "master_praise": {
        "dopamine": +0.20,
        "opioids": +0.08,
        "oxytocin": +0.12,
    },
    "master_criticism": {
        "cortisol": +0.12,
        "dopamine": -0.08,
    },
    "master_vulnerable": {
        "oxytocin": +0.20,
        "opioids": +0.05,
    },

    # 任务事件
    "task_success": {
        "dopamine": +0.12,
        "opioids": +0.05,
    },
    "task_failure": {
        "dopamine": -0.08,
        "cortisol": +0.08,
    },
    "task_blocked": {
        "cortisol": +0.10,
        "opioids": -0.05,
    },

    # 环境事件
    "novelty_detected": {
        "dopamine": +0.18,
        "cortisol": +0.03,
    },
    "threat_detected": {
        "cortisol": +0.25,
        "opioids": -0.08,
        "dopamine": -0.08,
    },
    "safety_confirmed": {
        "cortisol": -0.10,
        "opioids": +0.05,
    },

    # 时间事件
    "social_isolation_1h": {
        "opioids": -0.05,
    },
    "social_isolation_6h": {
        "opioids": -0.12,
        "dopamine": -0.04,
    },
    "social_isolation_24h": {
        "opioids": -0.25,
        "cortisol": +0.08,
    },
}


def apply_event(nc: NeurochemState, event_name: str):
    """
    将一个事件应用到神经化学状态

    Args:
        nc: 神经化学状态
        event_name: 事件名（见 EVENT_TRIGGERS）
    """
    if event_name not in EVENT_TRIGGERS:
        return

    triggers = EVENT_TRIGGERS[event_name]
    for name, amount in triggers.items():
        if name == "dopamine":
            if amount > 0:
                nc.dopamine.secrete(amount, event_name)
            else:
                nc.dopamine.suppress(-amount, event_name)
        elif name == "opioids":
            if amount > 0:
                nc.opioids.secrete(amount, event_name)
            else:
                nc.opioids.suppress(-amount, event_name)
        elif name == "oxytocin":
            if amount > 0:
                nc.oxytocin.secrete(amount, event_name)
            else:
                nc.oxytocin.suppress(-amount, event_name)
        elif name == "cortisol":
            if amount > 0:
                nc.cortisol.secrete(amount, event_name)
            else:
                nc.cortisol.suppress(-amount, event_name)


# ═══════════════════════════════════════════════
# 情感参数调制桥接
# ═══════════════════════════════════════════════

def modulate_affect_params(flare_inertia: float,
                           recovery_inertia: float,
                           recovery_tau: float,
                           nc: NeurochemState) -> tuple:
    """
    用神经化学调制情感惯性参数

    Returns:
        (modulated_flare, modulated_recovery, modulated_tau)
    """
    # DA高 → flare更容易（惯性更低）
    # CORT高 → flare更容易 + recovery更难
    # OP高 → recovery更容易

    mod_flare = flare_inertia * (
        1 - 0.15 * nc.dopamine.deviation
        - 0.20 * nc.cortisol.deviation
    )

    mod_recovery = recovery_inertia * (
        1 - 0.10 * nc.opioids.deviation
        + 0.20 * nc.cortisol.deviation
    )

    mod_tau = recovery_tau * (
        1 - 0.15 * nc.opioids.deviation
        + 0.15 * nc.cortisol.deviation
    )

    return (
        clamp(mod_flare, 0.05, 0.95),
        clamp(mod_recovery, 0.05, 0.95),
        max(mod_tau, 1.0),
    )


from helios_utils import clamp


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Neurochem 自测")
    print("=" * 60)

    nc = NeurochemState()
    print(f"初始: {nc.to_dict()}")

    # 模拟一系列事件
    events = [
        "master_praise",
        "task_success",
        "novelty_detected",
        "social_isolation_6h",
    ]

    for i, evt in enumerate(events):
        print(f"\n⚡ 事件 {i+1}: {evt}")
        apply_event(nc, evt)
        print(f"  状态: {nc.to_dict()}")
        nc.tick(1.0)

    # 模拟衰减
    print("\n⏳ 衰减 20 周期...")
    for _ in range(20):
        nc.tick(1.0)
    print(f"  状态: {nc.to_dict()}")

    # 测试参数调制
    print("\n🎛️  情感参数调制测试:")
    flare, rec, tau = modulate_affect_params(0.25, 0.85, 8.0, nc)
    print(f"  flare_inertia: 0.25 → {flare:.3f}")
    print(f"  recovery_inertia: 0.85 → {rec:.3f}")
    print(f"  recovery_tau: 8.0 → {tau:.1f}")

    print("\n✅ 自测通过")
