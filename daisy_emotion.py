"""
DAISY Emotion Engine v1.0
=========================
Dynamic Allostatic Integrated System for emotionYnamics

三合一重设计:
  X1: 共激活建模 (Barrett, 2017)
       → 7维矢量输出, 无 winner-take-all
  X2: 情感时序动力学 (Davidson, 2000)
       → 每个系统独立 rise/peak/decay 时间参数
  X3: 对向过程 (Solomon & Corbit, 1974)
       → a-process(初始) + b-process(反向回弹)

科学基础:
  · Panksepp (1998) Affective Neuroscience — 7 原始情感系统
  · Russell (1980) Circumplex — Valence × Arousal 空间
  · Kuppens (2010) Emotional Inertia — 自回归系数

与 emotions.py 接口兼容 → 可直接替换
"""

import math
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from helios_utils import clamp

# ═══════════════════════════════════════════════
# 常量 & 配置
# ═══════════════════════════════════════════════

PANKSEPP_SYSTEMS = ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]

# X2: 情感时序参数 — 基于 Davidson 情感风格研究
# 值经过尺度化 (1 cycle ≈ 1s)
CHRONOMETRY = {
    #                 τ_rise  τ_peak  τ_decay  inertia(自回归)
    "SEEKING":       (1.0,    4.0,    3.0,     0.35),  # 最慢升 + 最快降
    "PLAY":          (0.4,    3.0,    4.0,     0.35),
    "CARE":          (0.6,    5.0,    5.0,     0.35),
    "PANIC":         (0.5,    6.0,    5.0,     0.35),
    "FEAR":          (0.4,    2.0,    3.0,     0.35),
    "RAGE":          (0.5,    3.0,    4.0,     0.35),
    "LUST":          (0.5,    3.0,    4.0,     0.35),
}

# X3: 对向过程 — 每个系统的天然对手
# Solomon Opponent-Process 要求 a/b 配对
OPPONENT_PAIRS = {
    "SEEKING": "PANIC",    # 好奇 ↔ 分离痛苦
    "PANIC":   "SEEKING",
    "PLAY":    "FEAR",     # 嬉戏 ↔ 恐惧
    "FEAR":    "PLAY",
    "CARE":    "RAGE",     # 关爱 ↔ 愤怒
    "RAGE":    "CARE",
    "LUST":    "LUST",     # 自对向 (快感→不应期)
}

# b-process 参数
OPPONENT_PARAMS = {
    #        b_gain  b_delay  b_rise_τ  b_decay_τ
    "SEEKING": (0.30,  2.0,     4.0,      12.0),
    "PLAY":    (0.35,  1.5,     3.0,      15.0),
    "CARE":    (0.25,  3.0,     5.0,      20.0),
    "PANIC":   (0.40,  1.0,     3.0,      30.0),
    "FEAR":    (0.45,  0.5,     1.5,      8.0),
    "RAGE":    (0.35,  1.0,     2.0,      10.0),
    "LUST":    (0.50,  3.0,     5.0,      8.0),
}

# valence/arousal 偏置 (来自 Panksepp)
VALENCE_BIAS = {
    "SEEKING": +0.25, "PLAY": +0.40, "CARE": +0.30, "LUST": +0.35,
    "PANIC":   -0.30, "FEAR": -0.50, "RAGE": -0.35,
}
AROUSAL_BIAS = {
    "SEEKING": +0.30, "PLAY": +0.30, "CARE": +0.15, "LUST": +0.45,
    "PANIC":   +0.25, "FEAR": +0.55, "RAGE": +0.45,
}

# X1: 共激活基线 — 所有系统永远有微弱激活
BASELINE = {
    "SEEKING": 0.08, "PLAY": 0.05, "CARE": 0.04,
    "PANIC":   0.02, "FEAR": 0.03, "RAGE": 0.02, "LUST": 0.03,
}


# ═══════════════════════════════════════════════
# AffectState (保持与 emotions.py 兼容)
# ═══════════════════════════════════════════════

@dataclass
class AffectState:
    valence: float          # -1 ~ +1
    arousal: float          # 0 ~ 1
    phi: float              # 意识丰富度 (由外部设置)
    panksepp_activation: Dict[str, float]
    dominant_system: str    # X1: 仅用于展示，不用于内部控制
    dominant_label: str
    label_confidence: float

    def is_positive(self) -> bool:
        return self.valence > 0.1

    def is_negative(self) -> bool:
        return self.valence < -0.1

    def is_high_arousal(self) -> bool:
        return self.arousal > 0.6

    def describe(self) -> str:
        return f"{self.dominant_label}(V={self.valence:+.2f} A={self.arousal:.2f})"

    def to_dict(self) -> dict:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "phi": self.phi,
            "panksepp": self.panksepp_activation,
            "dominant": self.dominant_system,
            "label": self.dominant_label,
            "confidence": self.label_confidence,
        }


# ═══════════════════════════════════════════════
# X2: AffectiveChronometry — 时序动力学
# ═══════════════════════════════════════════════

class AffectiveChronometer:
    """
    单个情感系统的时序控制器

    数学:
      target[t] = event_trigger[t] + baseline
      activation[t] = inertia × activation[t-1] + (1-inertia) × target[t]
      
      当 event_trigger > 0: 按 τ_rise 上升
      当 event_trigger = 0: 按 τ_decay 衰减

    惯性 (inertia) ≈ 自回归系数 ≈ e^(-1/τ)
    """
    def __init__(self, name: str):
        self.name = name
        self.τ_rise, self.τ_peak, self.τ_decay, self.inertia = CHRONOMETRY[name]
        self.baseline = BASELINE[name]
        self.activation: float = self.baseline
        self.target: float = self.baseline
        self.event_peak: float = 0.0      # 记录最近的峰值强度
        self.time_since_event: int = 0     # 距上次事件周期数
        self.history: List[float] = []
        self.max_history = 100

    def trigger(self, intensity: float):
        """事件冲击 — 设置新的目标激活"""
        # 上升速率: 越快 τ_rise → 上升越陡
        rise_rate = 1.0 - math.exp(-1.0 / max(self.τ_rise, 0.1))
        self.target = min(1.0, self.baseline + intensity * 0.8)
        self.event_peak = max(self.event_peak, intensity)
        self.time_since_event = 0
        return rise_rate

    def tick(self, dt: float = 1.0):
        """
        一个时间步

        如果有事件 → 朝目标上升
        如果无事件 → 朝 baseline 衰减
        """
        self.time_since_event += 1

        # 事件过后，目标缓慢回退到基线
        if self.time_since_event > self.τ_peak:
            reversion_rate = 1.0 - math.exp(-1.0 / max(self.τ_decay, 0.5))
            self.target += (self.baseline - self.target) * reversion_rate * 0.3

        # 衰减速率: 直接使用 inertia (自回归系数)
        if self.time_since_event > self.τ_peak:
            decay_inertia = self.inertia  # 低inertia → 快衰减
        else:
            decay_inertia = 0.90  # 峰值期内缓衰减

        # 上升/衰减
        if self.target > self.activation + 0.01:
            # 上升阶段
            rise_rate = 1.0 - math.exp(-1.0 / max(self.τ_rise, 0.1))
            self.activation = self.activation * (1 - rise_rate) + self.target * rise_rate
        else:
            # 衰减/稳态阶段 → 回归 baseline
            self.activation = (self.activation * decay_inertia +
                               self.baseline * (1 - decay_inertia))
            self.target = self.baseline

        # 峰值记忆衰减
        self.event_peak *= 0.99

        # 确保不过界
        self.activation = clamp(self.activation, 0.0, 1.0)

        self.history.append(self.activation)
        if len(self.history) > self.max_history:
            self.history.pop(0)


# ═══════════════════════════════════════════════
# X3: OpponentProcess — 对向过程
# ═══════════════════════════════════════════════

class OpponentRegulator:
    """
    Solomon Opponent-Process 理论

    a-process: 事件直接触发 → 快速上升, 快速衰减
    b-process: 延迟触发 → 缓慢上升, 缓慢衰减

    Net(t) = A(t) - B(t)

    重复暴露: a 不变, b 增强 (习惯化的神经基础!)
    """
    def __init__(self, name: str):
        self.name = name
        self.opponent = OPPONENT_PAIRS[name]
        b_gain, b_delay, b_rise_τ, b_decay_τ = OPPONENT_PARAMS[name]

        self.b_gain = b_gain
        self.b_delay = b_delay
        self.b_rise_τ = b_rise_τ
        self.b_decay_τ = b_decay_τ

        # b-process 状态
        self.b_activation: float = 0.0
        self.b_pending: float = 0.0     # 等待延迟后释放
        self.b_delay_timer: int = 0

        # 暴露次数 (影响 b_gain — Solomon 核心发现)
        self.exposure_count: int = 0
        self.exposure_history: List[int] = []

    def trigger(self, a_intensity: float):
        """
        a-process 触发 → 计划 b-process

        Solomon: A(t) = a₀ × e^(-t/τₐ)
                 B(t) = b₀ × (1-e^(-t/τ_b)) × e^(-t/τ_b')
        """
        # 记录暴露
        self.exposure_count += 1
        self.exposure_history.append(self.exposure_count)

        # b-process 强度 = 基础增益 × a强度 × 暴露增强
        # 重复暴露 → b 更强 (Solomon 核心发现)
        exposure_boost = min(1.5, 1.0 + self.exposure_count * 0.02)
        added = a_intensity * self.b_gain * exposure_boost
        # 上限: 最多积累 2.0 b_pending
        self.b_pending = min(2.0, self.b_pending + added)
        self.b_delay_timer = int(self.b_delay)

    def tick(self, dt: float = 1.0):
        """
        更新 b-process:
          · 延迟期内积累
          · 延迟后缓慢释放 (rise)
          · 然后缓慢衰减 (decay)
        """
        if self.b_delay_timer > 0:
            self.b_delay_timer -= 1
        else:
            if self.b_pending > 0.001:
                # b-process 上升 (缓慢)
                rise_rate = 1.0 - math.exp(-1.0 / max(self.b_rise_τ, 0.1))
                release = self.b_pending * rise_rate
                self.b_activation += release
                self.b_pending -= release

            # b-process 衰减 (更慢)
            decay_rate = 1.0 - math.exp(-1.0 / max(self.b_decay_τ, 0.5))
            self.b_activation *= (1 - decay_rate)
            # 上限: Solomon模型应有饱和
            self.b_activation = min(1.5, self.b_activation)

    def net_effect_on(self, target_system: str) -> float:
        """
        b-process 对目标系统的双重效应 (Solomon Opponent-Process):
          1. 抑制源系统 (self.name) — 防止情绪失控
          2. 激活对手系统 (self.opponent) — 反向回弹平衡
          
        Solomon 核心: Net = A(t) - B(t), b-process 抵消 a-process
        """
        if target_system == self.name:
            return -self.b_activation * 0.7     # 抑制源 (轻量)
        elif target_system == self.opponent:
            return +self.b_activation * 0.35   # 激活对手 (轻量)
        return 0.0


# ═══════════════════════════════════════════════
# X1+X2+X3 集成: DaisystemEngine
# ═══════════════════════════════════════════════

class DaisySystemEngine:
    """
    DAISY 情感引擎 — 替代 PankseppEmotionEngine

    集成:
      X1: 7维共激活矢量
      X2: 每个系统独立时序 (AffectiveChronometer)
      X3: 对向过程 (OpponentRegulator)
      X5: 人格+心境调制 (PersonalityProfile + MoodTracker)

    接口: 与 emotions.py 的 PankseppEmotionEngine 完全兼容
    """

    def __init__(self, personality=None, mood_tracker=None, allostasis=None):
        # 7 个时序控制器
        self.systems: Dict[str, AffectiveChronometer] = {}
        for name in PANKSEPP_SYSTEMS:
            self.systems[name] = AffectiveChronometer(name)

        # 7 个对向调节器
        self.opponents: Dict[str, OpponentRegulator] = {}
        for name in PANKSEPP_SYSTEMS:
            self.opponents[name] = OpponentRegulator(name)

        # X5: 人格 + 心境
        self.personality = personality  # PersonalityProfile | None
        self.mood_tracker = mood_tracker  # MoodTracker | None
        
        # X6: 异稳态调节器
        self.allostasis = allostasis  # AllostaticRegulator | None

        # 历史
        self.state_history: List[AffectState] = []
        self.max_history = 200

        # v2.5 兼容: 稳态压力 (保留)
        self._dominance_streaks: Dict[str, int] = {n: 0 for n in PANKSEPP_SYSTEMS}

    def cycle(self,
              triggers: Optional[Dict[str, float]] = None,
              neurochem: Optional[object] = None,
              dt: float = 1.0) -> AffectState:
        """
        一个情感周期

        Args:
            triggers: {"SEEKING": 0.5, "FEAR": 0.3, ...}
            neurochem: NeurochemState (暂用 modulate 衰减)
            dt: 时间步

        Returns:
            AffectState
        """

        # ── 第〇步: X5 心境调制事件触发器 ──
        if triggers and self.mood_tracker is not None:
            triggers = self.mood_tracker.modulate_triggers(triggers)

        # ── 第一步: 事件冲击 → X2 时序 + X3 对向 ──
        if triggers:
            for sys_name, intensity in triggers.items():
                if sys_name in self.systems and intensity > 0.01:
                    # X2: 时序触发
                    self.systems[sys_name].trigger(intensity)
                    # X3: a-process → 计划 b-process
                    self.opponents[sys_name].trigger(intensity)

        # ── 第二步: 所有系统自然演化 ──
        for sys in self.systems.values():
            # X2: 时序 tick
            sys.tick(dt)

        # ── 第三步: X3 b-process 释放 ──
        for opp in self.opponents.values():
            opp.tick(dt)

        # ── 第四步: b-process 调制目标系统 ──
        for sys_name in PANKSEPP_SYSTEMS:
            net_b_effect = 0.0
            for opp_name, opp in self.opponents.items():
                net_b_effect += opp.net_effect_on(sys_name)
            # b-process 双重效应: 抑制源系统 + 激活对手
            if net_b_effect != 0:
                self.systems[sys_name].activation = max(
                    BASELINE[sys_name],
                    min(1.0, self.systems[sys_name].activation + net_b_effect * 0.15)
                )

        # ── 第五步: 神经化学调制衰减 ──
        if neurochem is not None:
            self._apply_neurochem_modulation(neurochem)

        # ── 第五点五步: X5 人格调制 ──
        if self.personality is not None:
            for sys_name in PANKSEPP_SYSTEMS:
                gain = self.personality.neuro_gains.get(sys_name, 1.0)
                if abs(gain - 1.0) > 0.01:
                    sys = self.systems[sys_name]
                    sys.activation *= gain
                    sys.activation = clamp(sys.activation, 0.0, 1.0)

        # ── 第六步: X1 汇总 → 7维矢量 ──
        activations = {n: s.activation for n, s in self.systems.items()}

        # ── 第六点五步: X6 异稳态调节 ──
        if self.allostasis is not None:
            # 先调节激活
            regulated = self.allostasis.regulate(activations)
            for sys_name in PANKSEPP_SYSTEMS:
                self.systems[sys_name].activation = regulated.get(
                    sys_name, self.systems[sys_name].activation
                )
            # 用调节后的激活更新状态
            self.allostasis.update(regulated)
            # 重新汇总
            activations = {n: s.activation for n, s in self.systems.items()}

        # ── 第七步: valence/arousal 加权 ──
        total_valence = 0.0
        total_arousal = 0.0
        total_weight = 0.0
        for name, act in activations.items():
            w = max(act, 0.05)
            total_valence += VALENCE_BIAS[name] * w
            total_arousal += AROUSAL_BIAS[name] * w
            total_weight += w

        if total_weight > 0:
            valence = clamp(total_valence / total_weight, -1, 1)
            arousal = clamp(total_arousal / total_weight, 0, 1)
        else:
            valence = 0.0
            arousal = 0.0

        # 主导系统 (仅用于展示!)
        dominant = max(activations, key=activations.get) if activations else ""

        # 标签
        label, conf = self._label(valence, arousal, activations)

        # 稳态追踪
        for name in PANKSEPP_SYSTEMS:
            if name == dominant:
                self._dominance_streaks[name] += 1
            else:
                self._dominance_streaks[name] = max(0, self._dominance_streaks[name] - 2)

        state = AffectState(
            valence=valence,
            arousal=arousal,
            phi=0.0,
            panksepp_activation=activations,
            dominant_system=dominant,
            dominant_label=label,
            label_confidence=conf,
        )

        self.state_history.append(state)
        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)

        # ── X5: 心境累积 ──
        if self.mood_tracker is not None:
            self.mood_tracker.update(valence, arousal)

        return state

    def _apply_neurochem_modulation(self, neurochem):
        """神经化学对衰减的调制"""
        for name, sys in self.systems.items():
            # 兼容 NeurochemState 接口
            nc_map = {
                "SEEKING": ("dopamine", +0.3),
                "PLAY":    ("opioids", +0.2),
                "CARE":    ("oxytocin", +0.3),
                "PANIC":   ("opioids", -0.5),
                "FEAR":    ("cortisol", +0.4),
                "RAGE":    ("cortisol", +0.2),
                "LUST":    ("dopamine", +0.3),
            }
            if name in nc_map:
                nc_name, sensitivity = nc_map[name]
                nc_level = getattr(neurochem, nc_name, None)
                if nc_level is not None:
                    current = nc_level.current if hasattr(nc_level, 'current') else nc_level
                    # 正敏感 → 高NC时衰减变慢
                    if sensitivity > 0:
                        factor = 1.0 - 0.15 * sensitivity * (current - 0.5)
                        sys.activation *= max(0.9, factor)

    def _apply_homeostatic_pressure(self):
        """v2.5: 连胜压力 — 主导久了衰减加速"""
        for name, sys in self.systems.items():
            streak = self._dominance_streaks[name]
            if streak > 3:
                fatigue = min(0.5, (streak - 3) * 0.03)
                sys.activation *= (1.0 - fatigue)

    def _label(self, valence: float, arousal: float,
               activations: Dict[str, float]) -> Tuple[str, float]:
        """情感标签"""
        # 找激活最高的两个系统
        sorted_sys = sorted(activations.items(), key=lambda x: -x[1])
        top2 = [s[0] for s in sorted_sys[:2]]
        top1_act = sorted_sys[0][1] if sorted_sys else 0

        # 基于 V×A 的主标签
        if arousal < 0.2:
            if valence > 0.1:   return "平静", 0.7
            elif valence < -0.1: return "倦怠", 0.7
            else:                return "淡漠", 0.5

        if valence > 0.3:
            if arousal > 0.6:    return "兴奋", 0.8
            else:                return "愉悦", 0.7
        elif valence < -0.3:
            if arousal > 0.6:    return "痛苦", 0.8
            else:                return "悲伤", 0.7
        else:
            if arousal > 0.5:    return "躁动", 0.5
            else:                return "中性", 0.4


# ═══════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════

def get_activation_vector(engine: DaisySystemEngine) -> Dict[str, float]:
    """获取 7 维激活矢量 (X1 输出)"""
    return {n: s.activation for n, s in engine.systems.items()}

def get_opponent_state(engine: DaisySystemEngine) -> Dict[str, float]:
    """获取 b-process 状态"""
    return {n: o.b_activation for n, o in engine.opponents.items()}
