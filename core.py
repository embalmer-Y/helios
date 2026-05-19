"""
Helios 核心数据结构

所有层之间传递的统一数据类型。
使用纯 numpy 实现，无 PyTorch 依赖，适配 ARM 设备。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
import time


# ═══════════════════════════════════════════════════
# L0 感知层数据结构
# ═══════════════════════════════════════════════════

@dataclass
class SensorFrame:
    """L0 传感器采集的单帧数据"""
    timestamp: float = field(default_factory=time.time)

    # 各模态原始数据
    vision: Optional[np.ndarray] = None       # (H, W) 灰度图 或 (H, W, C) 彩色
    audio: Optional[np.ndarray] = None         # (T,) 音频波形 或 (T, F) 频谱
    touch: Optional[np.ndarray] = None         # (N,) 压力值
    olfactory: Optional[np.ndarray] = None     # (256,) 气味向量
    thermal: float = 25.0                      # 环境温度 ℃
    proprioception: Optional[np.ndarray] = None  # (7,) 姿态四元数+位置
    interoception: Optional[np.ndarray] = None   # (4,) 内部状态 [电池%, 温度, CPU%, 内存%]

    def __repr__(self) -> str:
        parts = [f"t={self.timestamp:.3f}"]
        if self.vision is not None:
            parts.append(f"vis={self.vision.shape}")
        if self.audio is not None:
            parts.append(f"aud={self.audio.shape}")
        if self.interoception is not None:
            b, t, c, m = self.interoception
            parts.append(f"batt={b:.0%} temp={t:.0%} cpu={c:.0%} mem={m:.0%}")
        return f"SensorFrame({' | '.join(parts)})"


# ═══════════════════════════════════════════════════
# L1 质感层数据结构
# ═══════════════════════════════════════════════════

@dataclass
class L1Output:
    """L1 层的输出 —— 当前时刻的'体验质感'"""
    qualia: Dict[str, np.ndarray] = field(default_factory=dict)  # 各模态质感向量
    fused_qualia: Optional[np.ndarray] = None                     # 统一质感 [1024维]
    phi: float = 0.0                                              # 信息整合度 (0~1)
    prediction_errors: Dict[str, float] = field(default_factory=dict)  # 各模态预测误差
    timestamp: float = field(default_factory=time.time)

    @property
    def is_coherent(self) -> bool:
        """体验是否足够整合/一致"""
        return self.phi > 0.3

    @property
    def is_vivid(self) -> bool:
        """体验是否足够'生动'(高整合+低误差)"""
        avg_error = np.mean(list(self.prediction_errors.values())) if self.prediction_errors else 1.0
        return self.phi > 0.5 and avg_error < 0.3

    def __repr__(self) -> str:
        mods = ','.join(self.qualia.keys())
        return f"L1Output(Φ={self.phi:.3f}, mods=[{mods}], err={len(self.prediction_errors)})"


# ═══════════════════════════════════════════════════
# L2 广播层数据结构
# ═══════════════════════════════════════════════════

@dataclass
class WorkspaceResponse:
    """L2 点火后各子系统的响应"""
    memory_stored: bool = False
    language_output: Optional[str] = None
    decision_made: bool = False
    action_planned: bool = False
    affect_expression: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return (f"WorkspaceResponse(mem={self.memory_stored}, "
                f"lang={self.language_output is not None}, "
                f"act={self.action_planned})")


# ═══════════════════════════════════════════════════
# L3 自我层数据结构
# ═══════════════════════════════════════════════════

@dataclass
class SelfState:
    """Agent 对自身的内部表征"""
    # 身体状态
    body_schema: Optional[np.ndarray] = None  # 姿态嵌入
    energy_level: float = 1.0
    comfort: float = 1.0

    # 心理状态
    current_mood: np.ndarray = field(default_factory=lambda: np.full(8, 0.5))
    attention_focus: Optional[str] = None
    cognitive_load: float = 0.0

    # 时间连续性
    self_narrative_embedding: Optional[np.ndarray] = None
    recent_experiences: List[dict] = field(default_factory=list)

    # 元数据
    last_update: float = field(default_factory=time.time)


@dataclass
class MetacognitionOutput:
    """元认知评估输出"""
    confidence: float = 0.5           # 置信度 (0~1)
    uncertainty_areas: List[str] = field(default_factory=list)
    cognitive_state_summary: str = ""
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"Meta(conf={self.confidence:.2f}, uncertain={self.uncertainty_areas})"


# ═══════════════════════════════════════════════════
# 情感系统数据结构
# ═══════════════════════════════════════════════════

@dataclass
class AffectState:
    """情感状态 —— Russell 环状模型 + 离散情感"""
    valence: float = 0.0       # -1(不愉快) ~ +1(愉快)
    arousal: float = 0.0       #  0(平静) ~ 1(激动)
    discrete_emotions: Dict[str, float] = field(default_factory=dict)
    mood: float = 0.0          # 长期心情
    intensity: float = 0.0     # 情感强度 = |valence| * arousal
    timestamp: float = field(default_factory=time.time)

    @property
    def dominant_emotion(self) -> str:
        if not self.discrete_emotions:
            return "neutral"
        max_val = max(self.discrete_emotions.values())
        if max_val < 0.05:
            return "neutral"
        return max(self.discrete_emotions, key=self.discrete_emotions.get)

    @property
    def is_positive(self) -> bool:
        return self.valence > 0.2

    @property
    def is_negative(self) -> bool:
        return self.valence < -0.2

    def __repr__(self) -> str:
        return (f"Affect(v={self.valence:+.2f}, a={self.arousal:.2f}, "
                f"mood={self.mood:+.2f}, dom={self.dominant_emotion})")


# ═══════════════════════════════════════════════════
# 决策和行为数据结构
# ═══════════════════════════════════════════════════

@dataclass
class Goal:
    """Agent 的当前目标"""
    name: str
    description: str
    priority: float = 0.5        # 优先级 (0~1)
    progress: float = 0.0        # 进度 (0~1)
    created_at: float = field(default_factory=time.time)

    def evaluate_relevance(self, candidate: dict) -> float:
        """评估候选行动与目标的相关性（简化版）"""
        # 基于关键词匹配，实际应用中应使用语义相似度
        name_lower = self.name.lower()
        action_desc = candidate.get('description', '').lower()
        keywords = name_lower.split()
        matches = sum(1 for kw in keywords if kw in action_desc)
        return min(1.0, matches / max(1, len(keywords)))


@dataclass
class Decision:
    """决策结果"""
    action: dict
    confidence: float = 0.5
    reasoning: str = ""
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"Decision({self.action.get('type', '?')}, conf={self.confidence:.2f})"


# ═══════════════════════════════════════════════════
# 记忆数据结构
# ═══════════════════════════════════════════════════

@dataclass
class EpisodicMemoryEntry:
    """情景记忆条目"""
    content: np.ndarray                           # 融合质感嵌入
    affect_valence: float = 0.0
    affect_arousal: float = 0.0
    dominant_emotion: str = "neutral"
    phi: float = 0.0
    narrative: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class SemanticMemoryEntry:
    """语义记忆条目"""
    concept: str
    embedding: np.ndarray
    relations: List[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════
# Agent 配置
# ═══════════════════════════════════════════════════

@dataclass
class HeliosConfig:
    """Helios Agent 配置"""
    # 主循环
    cycle_interval: float = 0.1       # 基础循环周期（秒），默认 10Hz
    ignition_threshold: float = 0.5   # 点火阈值
    sustain_base: float = 0.1        # 点火自持基础时长
    sustain_phi_factor: float = 2.0   # Φ 对自持时长的贡献
    sustain_affect_factor: float = 1.5  # 情感对自持时长的贡献

    # L1 配置
    vision_dim: int = 128
    audio_dim: int = 64
    touch_dim: int = 32
    olfactory_dim: int = 128
    proprio_dim: int = 16
    intero_dim: int = 8
    fused_dim: int = 512

    # 多模态融合
    cross_modal_lr: float = 0.05
    phi_noise_floor: float = 0.05

    # 情感配置
    interoception_weight: float = 0.6
    cognitive_weight: float = 0.4
    affect_inertia: float = 0.7       # 情感惯性（指数平滑系数，向后兼容）
    # === v4: 非对称情感惯性 ===
    flare_inertia: float = 0.25       # 点燃惯性（低=快，平静→激烈快速切换）
    recovery_inertia: float = 0.85    # 平复惯性（高=慢，激烈→平静缓恢复）
    recovery_tau: float = 8.0         # 平复时间常数 τ（秒），越大越慢
    peak_inertia: float = 0.95        # 峰值后最大惯性（刚经历峰值时几乎冻结）

    # 记忆配置
    working_memory_capacity: int = 7
    episodic_memory_max: int = 1000
    emotional_recall_bias: float = 0.3  # 情感一致性检索偏差

    # 模拟环境
    simulation_mode: bool = True      # 是否使用模拟传感器
    verbose: bool = True              # 是否打印详细日志
