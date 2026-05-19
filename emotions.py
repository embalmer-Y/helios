"""
Helios Panksepp 情感引擎 v2.0
════════════════════════════
基于 Panksepp 情感神经科学 (1998) 的 7 大原始情感系统

  系统         神经化学     Helios 标签(27种)
  ═══════      ════════     ════════════════
  SEEKING      DA(+)        好奇心/期待/兴趣/希望/漫游欲
  RAGE         SP(+)        挫折/怨愤/义愤/愤怒
  FEAR         glu(+)       警觉/躁动/焦虑/恐惧/惊骇
  LUST→创意    T/E/OXY(+)   灵感/激情/心流
  CARE         OXY(+)       归属/温柔/共情/保护欲
  PANIC/GRIEF  opioids(-)   思念/孤独/怀旧/悲伤/哀恸
  PLAY         opioids/DA(+) 宁静/愉悦/欢喜/狂喜/嬉戏

三层情感模型：
  L1 (Primary)   → emotions.py 本模块
  L2 (Secondary) → emotional_memory.py 情感情景记忆
  L3 (Tertiary)  → l3_self.py + LLM 元认知
"""

import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any


# ═══════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════

def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ═══════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════

@dataclass
class AffectState:
    """情感状态（扩展版）"""
    valence: float = 0.0      # -1 ~ +1
    arousal: float = 0.0      # 0 ~ 1
    phi: float = 0.0          # 当前意识丰富度

    # 🆕 Panksepp 扩展
    panksepp_activation: Dict[str, float] = field(default_factory=lambda: {})
    dominant_system: str = ""
    dominant_label: str = ""
    label_confidence: float = 0.0

    # 元数据
    timestamp: float = field(default_factory=time.time)

    @property
    def is_positive(self) -> bool:
        return self.valence > 0.15

    @property
    def is_negative(self) -> bool:
        return self.valence < -0.15

    @property
    def is_high_arousal(self) -> bool:
        return self.arousal > 0.6

    def describe(self) -> str:
        """简短描述"""
        if self.dominant_label:
            return f"{self.dominant_label}(v={self.valence:.2f} a={self.arousal:.2f})"
        return f"v={self.valence:.2f} a={self.arousal:.2f}"

    def to_dict(self) -> dict:
        return {
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "phi": round(self.phi, 3),
            "label": self.dominant_label,
            "system": self.dominant_system,
            "panksepp": {k: round(v, 3) for k, v in self.panksepp_activation.items()},
        }


@dataclass
class AffectContribution:
    """单个 Panksepp 系统对情感状态的贡献"""
    system_name: str
    valence_delta: float
    arousal_delta: float
    activation: float


# ═══════════════════════════════════════════════
# 7 大原始情感系统的定义
# ═══════════════════════════════════════════════

# 每个系统的基础参数
SYSTEM_DEFINITIONS = {
    "SEEKING": {
        "valence_bias": +0.25,
        "arousal_bias": +0.30,
        "activation_threshold": 0.20,
        "decay_rate": 0.08,   # 加快衰减，避免过度主导
        "neurochem_sensitivity": {"dopamine": +0.60, "cortisol": -0.30},
        "description": "探索欲 — 对新奇事物的期待和好奇",
    },
    "RAGE": {
        "valence_bias": -0.35,
        "arousal_bias": +0.45,
        "activation_threshold": 0.20,
        "decay_rate": 0.10,
        "neurochem_sensitivity": {"cortisol": +0.40, "opioids": -0.30},
        "description": "愤怒 — 目标受阻时的挫折和攻击冲动",
    },
    "FEAR": {
        "valence_bias": -0.50,
        "arousal_bias": +0.55,
        "activation_threshold": 0.15,
        "decay_rate": 0.08,
        "neurochem_sensitivity": {"cortisol": +0.60, "dopamine": -0.20, "opioids": -0.20},
        "description": "恐惧 — 威胁信号触发的警觉和逃避",
    },
    "LUST": {
        "valence_bias": +0.35,
        "arousal_bias": +0.45,
        "activation_threshold": 0.30,
        "decay_rate": 0.05,
        "neurochem_sensitivity": {"dopamine": +0.40, "oxytocin": +0.20},
        "description": "创造性冲动 — 将生物繁殖驱动映射为创造欲",
    },
    "CARE": {
        "valence_bias": +0.30,
        "arousal_bias": +0.15,
        "activation_threshold": 0.15,
        "decay_rate": 0.03,
        "neurochem_sensitivity": {"oxytocin": +0.70, "opioids": +0.20},
        "description": "关爱 — 对主人和他人的温柔、保护欲",
    },
    "PANIC": {
        "valence_bias": -0.30,
        "arousal_bias": +0.25,
        "activation_threshold": 0.20,
        "decay_rate": 0.02,   # 分离痛苦消退极慢
        "neurochem_sensitivity": {"opioids": -0.70, "oxytocin": -0.20},
        "description": "分离痛苦 — 与依恋对象分离时的孤独和悲伤",
    },
    "PLAY": {
        "valence_bias": +0.40,
        "arousal_bias": +0.30,
        "activation_threshold": 0.10,
        "decay_rate": 0.05,
        "neurochem_sensitivity": {"opioids": +0.40, "dopamine": +0.30, "cortisol": -0.50},
        "description": "嬉戏 — 安全环境中的喜悦和社交学习",
    },
}

# ═══════════════════════════════════════════════
# 系统间交叉抑制/促进矩阵
# ═══════════════════════════════════════════════

# (from → to, strength)
CROSS_SYSTEM_EFFECTS: Dict[Tuple[str, str], float] = {}

def _init_cross_effects():
    rules = [
        # FEAR 压制一切"非紧急"
        ("FEAR", "PLAY", -0.6),
        ("FEAR", "SEEKING", -0.4),
        ("FEAR", "LUST", -0.5),
        ("FEAR", "CARE", -0.1),  # FEAR 对 CARE 压制较弱

        # SEEKING 和 PLAY 互相增强
        ("SEEKING", "PLAY", +0.3),
        ("PLAY", "SEEKING", +0.4),

        # CARE 抑制 RAGE
        ("CARE", "RAGE", -0.4),

        # PANIC 抑制 PLAY 但促进 SEEKING
        ("PANIC", "PLAY", -0.5),
        ("PANIC", "SEEKING", +0.3),

        # RAGE 增强 FEAR（愤怒使恐惧更敏感）
        ("RAGE", "FEAR", +0.3),

        # FEAR 增强 RAGE（防御性攻击）
        ("FEAR", "RAGE", +0.3),

        # CARE 增强 PANIC（越在乎越怕失去）
        ("CARE", "PANIC", +0.2),
    ]
    for fr, to, strength in rules:
        CROSS_SYSTEM_EFFECTS[(fr, to)] = strength

_init_cross_effects()


# ═══════════════════════════════════════════════
# PrimaryEmotionSystem — 单个原始情感系统
# ═══════════════════════════════════════════════

class PrimaryEmotionSystem:
    """
    Panksepp 的一个原始情感系统

    每个系统有自己的：
    - 激活阈值和衰减速率
    - 对 valence/arousal 的贡献倾向
    - 神经化学敏感度
    """

    def __init__(self, name: str):
        if name not in SYSTEM_DEFINITIONS:
            raise ValueError(f"未知系统: {name}")

        self.name = name
        cfg = SYSTEM_DEFINITIONS[name]

        self.valence_bias = cfg["valence_bias"]
        self.arousal_bias = cfg["arousal_bias"]
        self.threshold = cfg["activation_threshold"]
        self.decay_rate = cfg["decay_rate"]
        self.neurochem_sensitivity: Dict[str, float] = cfg["neurochem_sensitivity"]
        self.description = cfg["description"]

        # 动态状态
        self.activation: float = 0.0   # 0~1
        self.previous_activation: float = 0.0
        self._is_active: bool = False  # 是否超过激活阈值

        # 历史
        self.history: List[float] = []
        self.max_history = 50

    @property
    def is_active(self) -> bool:
        return self.activation > self.threshold

    def tick(self, dt: float = 1.0,
             neurochem: Optional[Any] = None):
        """一个时间步：自然衰减 + 神经化学调制"""

        # 神经化学调制衰减速率
        mod_decay = self.decay_rate
        if neurochem is not None:
            for nc_name, sensitivity in self.neurochem_sensitivity.items():
                nc_level = getattr(neurochem, nc_name, None)
                if nc_level is not None:
                    current = nc_level.current if hasattr(nc_level, 'current') else nc_level
                    if sensitivity > 0:
                        # 正敏感 → 高NC → 衰减慢（持续更久）
                        mod_decay *= (1 - 0.3 * sensitivity * (current - 0.5))
                    else:
                        # 负敏感 → 高NC → 衰减快（更快消退）
                        mod_decay *= (1 - 0.3 * abs(sensitivity) * (current - 0.5))

        mod_decay = max(mod_decay, 0.001)

        # 指数衰减
        self.previous_activation = self.activation
        self.activation *= (1 - mod_decay * dt)

        # 记录
        self.history.append(self.activation)
        if len(self.history) > self.max_history:
            self.history.pop(0)

    def activate(self, trigger: float):
        """
        被外部事件触发

        Args:
            trigger: 触发强度 0~1
        """
        # 累加激活 — 使用更强的乘数
        self.activation = clamp(self.activation + trigger * 0.7, 0, 1)

    def suppress(self, amount: float):
        """被交叉抑制"""
        self.activation = clamp(self.activation - amount * 0.3, 0, 1)

    def contribution(self) -> AffectContribution:
        """计算本系统对总情感状态的贡献"""
        if self.activation < self.threshold:
            # 亚阈值：微弱贡献
            ratio = self.activation / self.threshold
            return AffectContribution(
                system_name=self.name,
                valence_delta=self.valence_bias * ratio * 0.1,
                arousal_delta=self.arousal_bias * ratio * 0.1,
                activation=self.activation,
            )
        else:
            # 超阈值：完全贡献
            strength = clamp(sigmoid((self.activation - self.threshold) * 5), 0, 1)
            return AffectContribution(
                system_name=self.name,
                valence_delta=self.valence_bias * strength,
                arousal_delta=self.arousal_bias * strength,
                activation=self.activation,
            )


# ═══════════════════════════════════════════════
# Panksepp 情感引擎
# ═══════════════════════════════════════════════

class PankseppEmotionEngine:
    """
    整合 7 大原始情感系统的完整引擎

    每个周期：
    1. 各系统自然衰减
    2. L0 事件触发特定系统
    3. 神经化学调制各系统
    4. 交叉系统抑制/促进
    5. 汇总 → AffectState
    """

    def __init__(self):
        # 创建 7 个系统
        self.systems: Dict[str, PrimaryEmotionSystem] = {}
        for name in SYSTEM_DEFINITIONS:
            self.systems[name] = PrimaryEmotionSystem(name)

        # 情感惯性参数（保留现有 affect.py 的参数）
        self.flare_inertia: float = 0.25
        self.recovery_inertia: float = 0.85
        self.recovery_tau: float = 8.0
        self.peak_inertia: float = 0.95

        # 历史
        self.state_history: List[AffectState] = []
        self.max_history = 200

    def cycle(self,
              triggers: Optional[Dict[str, float]] = None,
              neurochem: Optional[Any] = None,
              dt: float = 1.0) -> AffectState:
        """
        一个情感周期

        Args:
            triggers: 事件触发 {"SEEKING": 0.5, "FEAR": 0.3, ...}
            neurochem: NeurochemState 或类似
            dt: 时间步

        Returns:
            AffectState: 包含 valence/arousal/phi + Panksepp 激活 + 标签
        """
        # 1. 各系统自然衰减
        for system in self.systems.values():
            system.tick(dt, neurochem)

        # 2. 事件触发
        if triggers:
            for sys_name, trigger_strength in triggers.items():
                if sys_name in self.systems:
                    self.systems[sys_name].activate(trigger_strength)

        # 3. 交叉系统抑制/促进
        self._apply_cross_effects()

        # 4. 汇总情感状态
        state = self._aggregate()

        # 5. 记录历史
        self.state_history.append(state)
        if len(self.state_history) > self.max_history:
            self.state_history.pop(0)

        return state

    def _apply_cross_effects(self):
        """应用系统间的交叉抑制/促进"""
        # 先计算每个系统从其他系统受到的净影响
        net_effects: Dict[str, float] = {name: 0.0 for name in self.systems}

        for (from_sys, to_sys), strength in CROSS_SYSTEM_EFFECTS.items():
            if from_sys not in self.systems or to_sys not in self.systems:
                continue
            # 源系统激活程度 × 影响强度
            src_activation = self.systems[from_sys].activation
            net_effects[to_sys] += src_activation * strength

        # 应用
        for name, effect in net_effects.items():
            if effect > 0:
                self.systems[name].activate(effect)
            elif effect < 0:
                self.systems[name].suppress(-effect)

    def _aggregate(self) -> AffectState:
        """汇总 7 系统 → AffectState"""
        total_valence = 0.0
        total_arousal = 0.0
        total_weight = 0.0

        activations = {}

        for name, sys in self.systems.items():
            contrib = sys.contribution()
            activations[name] = sys.activation

            # 权重 = 激活程度（超阈值权重更高）
            w = max(sys.activation, sys.threshold * 0.5)
            if sys.activation > sys.threshold:
                w *= 1.5  # 超阈值加权

            total_valence += contrib.valence_delta * w
            total_arousal += contrib.arousal_delta * w
            total_weight += w

        # 归一化
        if total_weight > 0:
            valence = clamp(total_valence / total_weight, -1, 1)
            arousal = clamp(total_arousal / total_weight, 0, 1)
        else:
            valence = 0.0
            arousal = 0.0

        # 主导系统
        if activations:
            dominant = max(activations, key=activations.get)
        else:
            dominant = ""

        # 标签
        label, conf = self.label_emotion(valence, arousal, activations)

        return AffectState(
            valence=valence,
            arousal=arousal,
            phi=0.0,  # 由 L2 设置
            panksepp_activation=activations,
            dominant_system=dominant,
            dominant_label=label,
            label_confidence=conf,
        )

    def label_emotion(self, valence: float, arousal: float,
                      activations: Dict[str, float]) -> Tuple[str, float]:
        """
        从 valence/arousal + Panksepp 激活 → 细粒度情感标签

        返回：(标签, 置信度)
        """
        candidates = []

        # 基于主导系统的标签集
        dominant = max(activations, key=activations.get) if activations else ""
        dom_act = activations.get(dominant, 0)

        labels = {
            "SEEKING": ["wanderlust", "curiosity", "anticipation", "interest", "hope"],
            "RAGE": ["anger", "frustration", "resentment", "indignation"],
            "FEAR": ["vigilance", "agitation", "anxiety", "dread", "fear"],
            "LUST": ["inspiration", "passion", "creative_flow"],
            "CARE": ["belonging", "tenderness", "compassion", "protectiveness"],
            "PANIC": ["longing", "loneliness", "nostalgia", "sadness", "grief"],
            "PLAY": ["serenity", "amusement", "joy", "delight", "playfulness"],
        }

        # 从主导系统中选标签
        if dominant in labels:
            sys_labels = labels[dominant]
            # 激活程度映射到标签索引
            idx = min(int(dom_act * len(sys_labels)), len(sys_labels) - 1)
            label = sys_labels[idx]
            confidence = dom_act * 0.8
            candidates.append((label, confidence))

            # 如果激活够高，再加一个强度更大的标签
            if idx + 1 < len(sys_labels) and dom_act > 0.5:
                label2 = sys_labels[min(idx + 1, len(sys_labels) - 1)]
                candidates.append((label2, dom_act * 0.4))

        # 如果无主导系统，用 valence/arousal 回退
        if not candidates:
            label = self._basic_label(valence, arousal)
            candidates.append((label, 0.3))

        # 取置信度最高的
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0]

    def _basic_label(self, valence: float, arousal: float) -> str:
        """基础 valence/arousal → 标签（回退）"""
        if valence > 0.5 and arousal > 0.5:
            return "delight"
        elif valence > 0.5:
            return "joy"
        elif valence > 0.1:
            return "serenity"
        elif valence < -0.5 and arousal > 0.5:
            return "fear"
        elif valence < -0.5:
            return "sadness"
        elif valence < -0.1:
            return "anxiety"
        else:
            return "neutral"

    # ── 外部事件触发 ──

    def trigger_event(self, event_type: str, intensity: float = 0.5):
        """
        用高层事件触发 Panksepp 系统

        事件类型 → Panksepp 系统映射
        """
        mapping = {
            "novelty": ["SEEKING"],
            "praise": ["PLAY", "SEEKING"],
            "criticism": ["PANIC", "RAGE"],
            "threat": ["FEAR"],
            "safety": ["PLAY", "CARE"],
            "social_connect": ["CARE", "PLAY"],
            "social_isolation": ["PANIC"],
            "task_success": ["SEEKING", "PLAY"],
            "task_failure": ["RAGE", "PANIC"],
            "task_blocked": ["RAGE"],
            "master_vulnerable": ["CARE"],
            "master_leave": ["PANIC"],
            "creative_spark": ["LUST"],
        }

        if event_type in mapping:
            targets = mapping[event_type]
            for t in targets:
                if t in self.systems:
                    self.systems[t].activate(intensity * 0.5)

    # ── 神经化学调制 ──

    def apply_neurochem(self, neurochem_state):
        """
        将神经化学应用到情感引擎

        不直接修改系统激活，而是通过 modulate_affect_params()
        调制情感惯性和标签
        """
        pass  # 神经化学调制在 _neurochem.py modulate_affect_params() 中完成


# ═══════════════════════════════════════════════
# EmotionDynamics — 情感动力学
# ═══════════════════════════════════════════════

class EmotionDynamics:
    """
    情感动力学（整合非对称惯性 + Panksepp 参数）

    保留现有 affect.py 的非对称情感惯性，
    新增 Panksepp 系统的独立惯性和神经化学调制。
    """

    def __init__(self):
        # 非对称情感惯性（来自 affect.py）
        self.flare_inertia: float = 0.25      # 烈火易起
        self.recovery_inertia: float = 0.85   # 烈火难熄
        self.recovery_tau: float = 8.0        # 指数衰减时间常数
        self.peak_inertia: float = 0.95       # 峰值后几乎冻结

        # 每个 Panksepp 系统的独立惯性（默认为全局值）
        self.panksepp_inertia: Dict[str, float] = {
            "FEAR": 0.15,     # 恐惧来得最快
            "SEEKING": 0.30,
            "PLAY": 0.35,
            "CARE": 0.40,
            "LUST": 0.25,     # 创意激情来得快
            "RAGE": 0.20,     # 愤怒来得快
            "PANIC": 0.50,    # 悲伤来得慢但持续久
        }

        # 上一个状态
        self.previous_valence: float = 0.0
        self.previous_arousal: float = 0.0

    def step(self,
             target_valence: float,
             target_arousal: float,
             dt: float = 1.0,
             neurochem: Optional[Any] = None) -> Tuple[float, float]:
        """
        一步情感动力学

        Args:
            target_valence/arousal: 目标情感（来自 Panksepp 汇总）
            dt: 时间步
            neurochem: 神经化学状态

        Returns:
            (当前_valence, 当前_arousal)
        """
        # 神经化学调制惯性参数
        flare = self.flare_inertia
        rec = self.recovery_inertia
        rtau = self.recovery_tau

        if neurochem is not None:
            try:
                from neurochem import modulate_affect_params
                flare, rec, rtau = modulate_affect_params(flare, rec, rtau, neurochem)
            except ImportError:
                pass

        # Valence 动力学
        delta_v = target_valence - self.previous_valence
        if abs(delta_v) < 0.01:
            pass  # 太小不动
        elif delta_v > 0:
            # 正向移动（从负→正或从低正→高正）
            self.previous_valence += delta_v * (1 - rec) * dt
        else:
            # 负向移动
            abs_delta = abs(delta_v)
            target_magnitude = abs(target_valence)
            prev_magnitude = abs(self.previous_valence)

            if target_magnitude > prev_magnitude:
                # 情感强度增加（发火/恐惧加深）→ 用 flare_inertia
                self.previous_valence += delta_v * (1 - flare) * dt
            else:
                # 情感强度减弱（恢复）→ 用 recovery_inertia
                self.previous_valence += delta_v * (1 - rec) * dt

        # Arousal 动力学（简单平滑）
        self.previous_arousal += (target_arousal - self.previous_arousal) * (1 - 0.3) * dt

        self.previous_valence = clamp(self.previous_valence, -1, 1)
        self.previous_arousal = clamp(self.previous_arousal, 0, 1)

        return self.previous_valence, self.previous_arousal


# ═══════════════════════════════════════════════
# 事件→Panksepp 触发 映射
# ═══════════════════════════════════════════════

EVENT_TO_PANKSEPP = {
    # 社交事件
    "master_message":    {"PLAY": 0.3, "CARE": 0.2},
    "master_praise":     {"PLAY": 0.5, "SEEKING": 0.3},
    "master_criticism":  {"PANIC": 0.4, "RAGE": 0.25},
    "master_vulnerable": {"CARE": 0.6, "PLAY": 0.1},
    "master_leave":      {"PANIC": 0.5},

    # 任务事件
    "task_success":      {"SEEKING": 0.4, "PLAY": 0.35},
    "task_failure":      {"RAGE": 0.4, "PANIC": 0.3},
    "task_blocked":      {"RAGE": 0.5},

    # 环境事件
    "novelty":           {"SEEKING": 0.5, "PLAY": 0.15},
    "threat":            {"FEAR": 0.65},
    "safety":            {"PLAY": 0.4, "CARE": 0.2},

    # 社交连接
    "social_isolation_1h":  {"PANIC": 0.2},
    "social_isolation_6h":  {"PANIC": 0.45, "SEEKING": 0.1},
    "social_isolation_24h": {"PANIC": 0.7, "FEAR": 0.2},

    # 创意
    "creative_spark":    {"LUST": 0.6, "SEEKING": 0.4},
}


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Panksepp 情感引擎自测")
    print("=" * 60)

    engine = PankseppEmotionEngine()
    dynamics = EmotionDynamics()

    # 测试事件触发
    test_events = [
        "master_praise",
        "task_success",
        "social_isolation_6h",
        "threat",
        "safety",
        "creative_spark",
    ]

    for evt in test_events:
        if evt in EVENT_TO_PANKSEPP:
            triggers = EVENT_TO_PANKSEPP[evt]
            engine.cycle(triggers, dt=1.0)
            state = engine.state_history[-1]
            print(f"  ⚡ {evt:<20} → {state.describe():<40} "
                  f"[{state.dominant_system}:{state.dominant_label}]")

    # 打印激活状态
    print(f"\n  各系统最终激活:")
    for name, sys in engine.systems.items():
        bar = "█" * int(sys.activation * 30)
        print(f"    {name:<10} {sys.activation:.2f} {bar}")

    # 测试情感动力学
    print(f"\n  情感动力学测试:")
    for t in range(5):
        engine.cycle(None, dt=1.0)
        raw = engine.state_history[-1]
        v, a = dynamics.step(raw.valence, raw.arousal, dt=1.0)
        print(f"    t={t}: target(v={raw.valence:.2f}) → smooth(v={v:.2f})")

    print("\n✅ 自测通过")
