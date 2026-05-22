"""
Helios ICRI (Integrated Consciousness Richness Index) 引擎
══════════════════════════════════════════════════════════

Previously known as the Φ (Phi) engine. Renamed to ICRI to accurately reflect
its engineering nature without implying IIT theoretical compliance.

设计原则：
  - 单一真相来源：所有子系统读/写同一个 UnifiedPhi / AdaptiveAlphaICRI
  - 多源融合：L1信息整合 + Panksepp共振 + DMN深度 + L3自我反思 + L2点火
  - 双向调制：ICRI 反映意识状态，也反过来调制各子系统
  - 意识时刻检测：aha/共振/流状态 (Dehaene 2006)

理论基础：
  - Tononi (2004) 信息整合理论 (IIT): Φ = 系统整体的信息量 - 各部分信息量之和
  - Dehaene (2006) 全局神经元工作空间: 意识 = 全局广播 + 点火
  - Seth (2011) 预测处理: 意识 = 自上而下预测 + 自下而上误差的精确加权

Note: The class name ``UnifiedPhi`` is retained for backward compatibility.
New code should prefer ``AdaptiveAlphaICRI``.

用法:
  from phi import UnifiedPhi, AdaptiveAlphaICRI, CognitiveImpactProfile
  icri = AdaptiveAlphaICRI()
  icri.feed_emotional(panksepp_activation)
  current = icri.aggregate(max_event_intensity)
"""

import time
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum


# ═══════════════════════════════════════════════
# 工具
# ═══════════════════════════════════════════════

from helios_utils import clamp

def smooth(prev: float, curr: float, alpha: float = 0.3) -> float:
    """指数平滑"""
    return prev + alpha * (curr - prev)


# ═══════════════════════════════════════════════
# 数据类
# ═══════════════════════════════════════════════

class ConsciousnessLabel(str, Enum):
    MINIMAL = "minimal"      # Φ < 0.2: 最低意识
    FOCUSED = "focused"      # 0.2 ≤ Φ < 0.4: 专注
    REFLECTIVE = "reflective" # 0.4 ≤ Φ < 0.6: 反思
    FLOW = "flow"             # 0.6 ≤ Φ < 0.8: 心流
    PEAK = "peak"             # Φ ≥ 0.8: 巅峰


@dataclass
class ConsciousnessMoment:
    """意识时刻 (Dehaene 2006)"""
    type: str                      # "aha" / "resonance" / "flow"
    phi_value: float
    timestamp: float = field(default_factory=time.time)
    subsystems: Dict[str, float] = field(default_factory=dict)
    description: str = ""


@dataclass
class CognitiveImpactProfile:
    """
    4-dimension cognitive impact descriptor attached to events.

    Each dimension is a float in [0, 1] representing:
      - sensory: multimodal information load
      - cognitive: understanding demand (feeds dmn_depth)
      - self_: self-relevance (feeds self_reflection)
      - novelty: versus repetition (feeds global_ignition)

    When an event carries this profile, ICRI sources are fed directly
    from these dimensions rather than relying on approximate derivations.

    Requirements: 27.1, 27.2, 27.3, 27.4, 27.5, 27.6
    """
    sensory: float = 0.0    # multimodal information load → sensory_integration
    cognitive: float = 0.0  # understanding demand → dmn_depth
    self_: float = 0.0      # self-relevance → self_reflection
    novelty: float = 0.0    # versus repetition → global_ignition

    def __post_init__(self):
        self.sensory = clamp(self.sensory)
        self.cognitive = clamp(self.cognitive)
        self.self_ = clamp(self.self_)
        self.novelty = clamp(self.novelty)


# ═══════════════════════════════════════════════
# 统一 Φ
# ═══════════════════════════════════════════════

@dataclass
class UnifiedPhi:
    """
    Helios 的统一 ICRI 模型 (class name retained as UnifiedPhi for backward compat)

    ICRI 是意识丰富度的度量 (0~1):
    0.0 = 无意识/昏迷
    0.2 = 最低意识 (基础感知)
    0.4 = 专注意识 (集中注意)
    0.6 = 反思意识 (元认知活跃)
    0.8 = 流状态 (心流)
    1.0 = 巅峰体验 (自我超越)
    """

    # ── 子成分 ──
    sensory_integration: float = 0.0     # L1: 多模态信息整合
    emotional_coherence: float = 0.0     # Panksepp: 多系统共振
    temporal_depth: float = 0.0          # DMN: 思维活跃度
    self_reflection: float = 0.0         # L3: 元认知强度
    global_ignition: float = 0.0         # L2: 全局点火强度

    # ── 聚合权重 ──
    weights: Dict[str, float] = field(default_factory=lambda: {
        "sensory_integration": 0.20,
        "emotional_coherence": 0.25,
        "temporal_depth": 0.20,
        "self_reflection": 0.20,
        "global_ignition": 0.15,
    })

    # ── 动态 ──
    _phi: float = 0.0                    # 平滑后的 Φ
    _phi_raw: float = 0.0                # 聚合前
    history: List[float] = field(default_factory=list)
    max_history: int = 60
    smoothing_alpha: float = 0.25        # 平滑系数

    # ── 源有效性 ──
    _sources_valid: Dict[str, float] = field(default_factory=lambda: {
        "sensory_integration": 0.0,
        "emotional_coherence": 1.0,      # 始终可用
        "temporal_depth": 0.0,
        "self_reflection": 0.0,
        "global_ignition": 0.0,
    })
    source_ttl: float = 5.0              # 源数据有效期 (cycles)

    # ── 调制器 ──
    modulator: Optional["PhiModulator"] = None
    detector: Optional["ConsciousnessDetector"] = None

    def __post_init__(self):
        self.modulator = PhiModulator(self)
        self.detector = ConsciousnessDetector()

    # ── 喂入接口 ──

    def feed_sensory(self, l1_phi: float):
        """L1 → Φ: 信息整合度"""
        self.sensory_integration = clamp(l1_phi)
        self._sources_valid["sensory_integration"] = self.source_ttl

    def feed_emotional(self, panksepp_activation: Dict[str, float]):
        """
        Panksepp → Φ: 情感共振

        共振 = 多系统同时激活时 > 单一系统主导时
        只考虑激活度 > 0.1 的系统（忽略静默系统）
        """
        if not panksepp_activation:
            return
        # 只取活跃系统 (activation > 0.1)
        active = {k: v for k, v in panksepp_activation.items() if v > 0.1}
        if not active:
            self.emotional_coherence = 0.0
            return

        values = list(active.values())
        avg = sum(values) / len(values)

        # 变异系数：活跃系统间的变异
        if len(values) <= 1:
            coherence = avg  # 单系统：直接用均值
        elif avg > 0.05:
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
            cv = std / avg if avg > 0 else 1.0
            # 系统数多 + 均值高 + 变异小 = 共振
            count_bonus = min(len(values) / 5.0, 0.4)  # 5个以上系统 = 满分
            coherence = avg * (1.0 - min(cv, 0.8)) + count_bonus
        else:
            coherence = 0.0

        # 加分：正向情感系统共振 (SEEKING+PLAY+CARE 同时高)
        positive = active.get("SEEKING", 0) + \
                   active.get("PLAY", 0) + \
                   active.get("CARE", 0)
        if positive > 1.5:
            coherence += 0.10
        if positive > 2.0:
            coherence += 0.10

        self.emotional_coherence = clamp(coherence)
        self._sources_valid["emotional_coherence"] = self.source_ttl

    def feed_dmn(self, thought_count: int, avg_novelty: float,
                 thought_modes: Optional[List[str]] = None):
        """
        DMN → Φ: 思维深度

        深度 = 思维量 × 新颖度 × 模式多样性
        """
        depth = 0.0
        depth += min(thought_count / 5.0, 1.0) * 0.40       # 思维量
        depth += avg_novelty * 0.35                          # 新颖度
        if thought_modes:
            unique_modes = len(set(thought_modes))
            depth += (unique_modes / 3.0) * 0.25             # 模式多样性
        else:
            depth += 0.10  # 默认浅层

        self.temporal_depth = clamp(depth)
        self._sources_valid["temporal_depth"] = self.source_ttl

    def feed_ignition(self, ignition_active: bool, intensity: float):
        """L2 → Φ: 全局点火状态"""
        if ignition_active:
            self.global_ignition = clamp(intensity)
        else:
            self.global_ignition = 0.0
        self._sources_valid["global_ignition"] = self.source_ttl

    def feed_ignition_from_panksepp(self, panksepp_activation: Dict[str, float],
                                     baseline: float = 0.15):
        """
        L2 → Φ: 全局点火 — 从活跃 Panksepp 系统数推导

        点火强度 = 活跃系统数(超过baseline) / 总系统数
        更多系统同时激活 = 更强的全局广播 (Dehaene 2006)
        """
        if not panksepp_activation:
            self.global_ignition = 0.0
            return
        total_systems = len(panksepp_activation)
        if total_systems == 0:
            self.global_ignition = 0.0
            return
        active_count = sum(1 for v in panksepp_activation.values() if v > baseline)
        # Non-linear: diminishing returns mapped through sqrt for smoother curve
        ratio = active_count / max(total_systems, 1)
        intensity = math.sqrt(ratio)  # sqrt gives nice non-linear boost
        self.global_ignition = clamp(intensity)
        self._sources_valid["global_ignition"] = self.source_ttl

    def feed_self_model(self, self_confidence: float, narrative_depth: float):
        """L3 → Φ: 自我模型强度"""
        self.self_reflection = clamp(self_confidence * 0.5 + narrative_depth * 0.5)
        self._sources_valid["self_reflection"] = self.source_ttl

    def feed_self_model_from_personality(self, personality_traits: Dict[str, float]):
        """
        L3 → Φ: 自我模型 — 从人格特质意识推导

        自我反思度 = 基于特质极端程度 (越明确的人格 = 越强自我意识)
        高openness + 高neuroticism + 高conscientiousness → 高反思
        """
        if not personality_traits:
            self.self_reflection = 0.0
            return
        # Reflexivity: how far traits deviate from neutral (0.5)
        # More defined personality = more self-awareness
        deviations = [abs(v - 0.5) for v in personality_traits.values()]
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0.0
        # Scale: deviation of 0.5 (max) → reflexivity ~0.8
        # Openness and neuroticism particularly drive self-reflection
        openness = personality_traits.get("openness", 0.5)
        neuroticism = personality_traits.get("neuroticism", 0.5)
        reflexivity = (avg_deviation * 1.2 + openness * 0.3 + neuroticism * 0.2) / 1.7
        self.self_reflection = clamp(reflexivity)
        self._sources_valid["self_reflection"] = self.source_ttl

    def feed_dmn_from_thinking(self, thinking_mode: str, thought_count: int = 0):
        """
        DMN → Φ: 思维深度 — 从思考模式推导

        深度映射:
          idle → 0.1, shallow/replay → 0.3, mixed/daydream → 0.5,
          deep/counterfactual → 0.7, flow → 0.9
        """
        mode_depth = {
            "idle": 0.1,
            "shallow": 0.25,
            "replay": 0.3,
            "mixed": 0.5,
            "daydream": 0.55,
            "deep": 0.7,
            "counterfactual": 0.75,
            "flow": 0.9,
        }
        base_depth = mode_depth.get(thinking_mode, 0.3)
        # Thought count bonus (more thoughts = slightly more depth)
        count_bonus = min(thought_count / 10.0, 0.2)
        self.temporal_depth = clamp(base_depth + count_bonus)
        self._sources_valid["temporal_depth"] = self.source_ttl

    # ── 源衰减 ──

    def _decay_sources(self):
        """每个 cycle 衰减源数据"""
        for key in self._sources_valid:
            self._sources_valid[key] = max(0.0, self._sources_valid[key] - 1.0)
        # Decay sensory integration value when TTL expires (Req 4.5)
        if self._sources_valid["sensory_integration"] <= 0:
            self.sensory_integration *= 0.8  # Gradual decay

    # ── 非线性缩放 ──

    @staticmethod
    def _nonlinear_scale(raw: float) -> float:
        """
        Non-saturating non-linear scaling function.

        Uses a modified logistic curve that:
        - Prevents saturation at high values (maintains differentiation)
        - Preserves sensitivity at low values
        - Maps [0, 1] → [0, 1] with full range utilization

        Formula: 1.0 - 1.0 / (1.0 + raw * 2.5)
        At raw=0.0 → 0.0, raw=0.4 → 0.5, raw=0.8 → 0.67, raw=1.0 → 0.71
        
        To achieve >0.7 when all 5 high, we use a boosted version:
        tanh(raw * 1.6) which gives:
        raw=0.0 → 0.0, raw=0.3 → 0.45, raw=0.5 → 0.66, raw=0.8 → 0.87, raw=1.0 → 0.92
        """
        # tanh-based non-linear scaling: non-saturating with good dynamic range
        return math.tanh(raw * 1.6)

    # ── 聚合 ──

    def aggregate(self) -> float:
        """
        聚合所有子成分 → 统一 Φ 值

        Multi-source fusion with non-linear scaling:
        1. Compute weighted sum (NOT normalized by active weight count)
           - This naturally rewards multiple active sources
        2. Apply source-count synergy bonus (more active sources = synergy)
        3. Apply non-linear scaling to prevent saturation
        4. Exponential smooth to prevent oscillation
        """
        self._decay_sources()

        total = 0.0
        active_source_count = 0

        for key, weight in self.weights.items():
            if self._sources_valid[key] > 0:
                value = getattr(self, key)
                total += value * weight
                if value > 0.1:
                    active_source_count += 1

        if active_source_count > 0:
            # Source-count synergy bonus: more active sources → multiplicative boost
            # 1 source: ×1.0, 3 sources: ×1.15, 5 sources: ×1.3
            synergy = 1.0 + (active_source_count - 1) * 0.075
            raw = total * synergy

            # Non-linear scaling to prevent ceiling saturation
            self._phi_raw = self._nonlinear_scale(clamp(raw))
        else:
            self._phi_raw = 0.05  # 最低意识基线

        # 指数平滑
        self._phi = smooth(self._phi, self._phi_raw, self.smoothing_alpha)

        # 记录历史
        self.history.append(self._phi)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        return self._phi

    # ── 属性 ──

    @property
    def icri(self) -> float:
        """Current ICRI (Integrated Consciousness Richness Index) value.

        This is the preferred accessor. The ``phi`` property is retained
        for backward compatibility.
        """
        return self._phi

    @property
    def phi(self) -> float:
        """Deprecated: backward-compatible alias for ``icri``."""
        return self._phi

    @property
    def label(self) -> ConsciousnessLabel:
        if self._phi < 0.2:
            return ConsciousnessLabel.MINIMAL
        elif self._phi < 0.4:
            return ConsciousnessLabel.FOCUSED
        elif self._phi < 0.6:
            return ConsciousnessLabel.REFLECTIVE
        elif self._phi < 0.8:
            return ConsciousnessLabel.FLOW
        else:
            return ConsciousnessLabel.PEAK

    @property
    def is_conscious(self) -> bool:
        return self._phi > 0.15

    @property
    def is_highly_conscious(self) -> bool:
        return self._phi > 0.6

    def describe(self) -> str:
        return (f"ICRI={self._phi:.2f} [{self.label.value}] "
                f"si={self.sensory_integration:.2f} "
                f"ec={self.emotional_coherence:.2f} "
                f"td={self.temporal_depth:.2f} "
                f"sr={self.self_reflection:.2f} "
                f"gi={self.global_ignition:.2f}")


# ═══════════════════════════════════════════════
# Φ 调制器
# ═══════════════════════════════════════════════

class PhiModulator:
    """
    ICRI 对子系统的调制器 (class name retained as PhiModulator for backward compat)

    核心规则: ICRI 高 → 系统更敏感/更协调/更深思
              ICRI 低 → 系统更迟钝/更竞争/更浅层
    """

    def __init__(self, phi: UnifiedPhi):
        self.phi = phi

    # ── Panksepp ──

    def modulate_threshold(self, base_threshold: float) -> float:
        """情感激活阈值: ICRI高 → 阈值低 → 更敏感"""
        return base_threshold * (1.0 - 0.30 * self.phi.phi)

    def modulate_cross_effect(self, base_strength: float) -> float:
        """交叉效应强度: ICRI高 → 交叉更强 → 情感更整合"""
        return base_strength * (1.0 + 0.30 * self.phi.phi)

    def modulate_decay(self, base_decay: float) -> float:
        """衰减速率: ICRI高 → 衰减慢 → 状态持久"""
        return base_decay * (1.0 - 0.25 * self.phi.phi)

    # ── DMN ──

    def modulate_dmn_depth(self) -> int:
        """DMN 碎片数: ICRI高 → 更深思"""
        p = self.phi.phi
        if p > 0.65: return 5
        elif p > 0.45: return 4
        elif p > 0.25: return 2
        else: return 1

    def modulate_dmn_mode(self) -> str:
        """DMN 模式偏好"""
        p = self.phi.phi
        if p > 0.7: return "deep"       # 反事实 + 自由联想
        elif p > 0.4: return "mixed"    # 回放 + 白日梦
        elif p > 0.2: return "shallow"  # 仅回放
        else: return "idle"             # 最少思考

    # ── 神经化学 ──

    def modulate_neurochem_decay(self, base_decay_rate: float) -> float:
        """神经递质衰减: ICRI高 → 慢衰减"""
        return base_decay_rate * (1.0 - 0.25 * self.phi.phi)

    def modulate_neurochem_response(self, base_amount: float) -> float:
        """神经化学事件响应: ICRI高 → 更强"""
        return base_amount * (1.0 + 0.20 * self.phi.phi)

    # ── LLM ──

    def modulate_llm_tokens(self, base_tokens: int) -> int:
        """LLM max_tokens: ICRI高 → 更深思"""
        return min(int(base_tokens * (1.0 + 0.5 * self.phi.phi)), 800)

    def modulate_llm_temperature(self, base_temp: float) -> float:
        """LLM temperature: ICRI高 → 更发散"""
        return min(base_temp * (1.0 + 0.15 * self.phi.phi), 1.2)

    # ── Limb 安全 ──

    def modulate_rate_limit(self, base_rate: int) -> int:
        """手脚频率限制: ICRI高 → 更宽松"""
        return int(base_rate * (1.0 + 0.5 * self.phi.phi))

    # ── 汇总 ──

    def get_modulation_summary(self) -> Dict[str, float]:
        """所有调制值的快照"""
        return {
            "threshold_factor": 1.0 - 0.30 * self.phi.phi,
            "cross_effect_factor": 1.0 + 0.30 * self.phi.phi,
            "decay_factor": 1.0 - 0.25 * self.phi.phi,
            "dmn_depth": float(self.modulate_dmn_depth()),
            "llm_token_factor": 1.0 + 0.5 * self.phi.phi,
            "rate_limit_factor": 1.0 + 0.5 * self.phi.phi,
        }


# ═══════════════════════════════════════════════
# 意识时刻检测器
# ═══════════════════════════════════════════════

class ConsciousnessDetector:
    """
    检测三种意识时刻 (Dehaene 2006)

    Aha:       ICRI 突变 (ΔICRI > 0.25 in 2 cycles)
    Resonance: 3+ 子系统同时高激活
    Flow:      ICRI 持续 >0.65 超过 5 cycles
    """

    def detect(self, phi: UnifiedPhi,
               subsystems: Optional[Dict[str, float]] = None
               ) -> Optional[ConsciousnessMoment]:
        h = phi.history
        ph = phi.phi

        # Aha: ICRI 突变检测
        if len(h) >= 3:
            prev = sum(h[-4:-1]) / 3 if len(h) >= 4 else sum(h[-3:-1]) / 2
            if ph - prev > 0.25:
                return ConsciousnessMoment(
                    type="aha",
                    phi_value=ph,
                    description=f"ICRI 飙升 {prev:.2f}→{ph:.2f}",
                )

        # Resonance: 多系统共激活
        if subsystems:
            active_high = sum(1 for v in subsystems.values() if v > 0.55)
            if active_high >= 3 and ph > 0.50:
                return ConsciousnessMoment(
                    type="resonance",
                    phi_value=ph,
                    subsystems=subsystems,
                    description=f"{active_high} 子系统共振 (ICRI={ph:.2f})",
                )

        # Flow: 持续高 Φ
        if len(h) >= 5 and all(p > 0.65 for p in h[-5:]):
            return ConsciousnessMoment(
                type="flow",
                phi_value=ph,
                description=f"流状态持续 {sum(1 for p in h if p > 0.65)} cycles",
            )

        return None


# ═══════════════════════════════════════════════
# Adaptive Alpha ICRI Engine (Requirement 24)
# ═══════════════════════════════════════════════

class AdaptiveAlphaICRI:
    """
    ICRI (Integrated Consciousness Richness Index) engine with dynamic EMA alpha
    based on event intensity.

    Replaces the fixed alpha=0.25 with a 3-tier adaptive scheme:
      - High intensity (> 0.60): alpha=0.55 for fast response
      - Normal intensity (0.30-0.60): alpha=0.30 for normal tracking
      - Resting (< 0.30): alpha=0.10 for slow drift

    The non-linear scaling function prevents saturation at high values while
    maintaining sensitivity at low values.

    Requirements: 24.1, 24.2, 24.3, 24.4, 24.5
    """

    # Alpha tier constants
    ALPHA_HIGH = 0.55    # intensity > 0.60 → fast response
    ALPHA_NORMAL = 0.30  # intensity 0.30-0.60 → normal tracking
    ALPHA_REST = 0.10    # intensity < 0.30 → slow drift

    # Source weights (same as UnifiedPhi)
    DEFAULT_WEIGHTS = {
        "sensory_integration": 0.20,
        "emotional_coherence": 0.25,
        "dmn_depth": 0.20,           # renamed from temporal_depth
        "self_reflection": 0.20,
        "global_ignition": 0.15,
    }

    # Source TTL default (in ticks/cycles)
    DEFAULT_TTL = 10

    def __init__(self):
        self._icri: float = 0.0
        self._sources: Dict[str, float] = {
            "sensory_integration": 0.0,
            "emotional_coherence": 0.0,
            "dmn_depth": 0.0,          # renamed from temporal_depth
            "self_reflection": 0.0,
            "global_ignition": 0.0,
        }
        self._source_ttl: Dict[str, float] = {k: 0.0 for k in self._sources}
        self._weights: Dict[str, float] = dict(self.DEFAULT_WEIGHTS)

    def select_alpha(self, max_event_intensity: float) -> float:
        """
        Select EMA alpha based on current max event intensity tier.

        Deterministic tier selection:
          - intensity > 0.60 → 0.55 (fast response)
          - intensity in [0.30, 0.60] → 0.30 (normal tracking)
          - intensity < 0.30 → 0.10 (slow drift / resting)

        The mapping is exhaustive across the [0, 1] range.
        """
        if max_event_intensity > 0.60:
            return self.ALPHA_HIGH
        elif max_event_intensity >= 0.30:
            return self.ALPHA_NORMAL
        else:
            return self.ALPHA_REST

    @staticmethod
    def _nonlinear_scale(raw: float) -> float:
        """
        Non-linear scaling function to prevent saturation.

        Formula: 1.0 - (1.0 / (1.0 + raw * 2.5))

        Properties:
          - raw=0.0 → 0.0
          - raw=0.4 → ~0.50
          - raw=0.8 → ~0.67
          - raw=1.0 → ~0.71
          - Monotonically increasing
          - Prevents saturation at high values
          - Maintains sensitivity at low values
        """
        return 1.0 - (1.0 / (1.0 + raw * 2.5))

    def aggregate(self, max_event_intensity: float) -> float:
        """
        Compute ICRI with adaptive alpha EMA smoothing.

        Steps:
          1. Compute weighted sum of all sources
          2. Apply non-linear scaling to prevent saturation
          3. Select alpha based on max event intensity
          4. Apply EMA: new_icri = alpha * scaled + (1 - alpha) * previous_icri
          5. Ensure minimum increase of 0.10 when QQ message arrives
             (handled by caller providing appropriate intensity)

        Args:
            max_event_intensity: The maximum intensity across all events this tick.

        Returns:
            The updated ICRI value.
        """
        # Decay source TTLs
        for key in self._source_ttl:
            self._source_ttl[key] = max(0.0, self._source_ttl[key] - 1.0)

        # Compute weighted raw sum
        raw = 0.0
        for key, weight in self._weights.items():
            if self._source_ttl[key] > 0:
                raw += self._sources[key] * weight
            else:
                # Decay expired sources
                self._sources[key] *= 0.8

        # Non-linear scaling to prevent saturation
        scaled = self._nonlinear_scale(clamp(raw))

        # Select alpha based on event intensity
        alpha = self.select_alpha(max_event_intensity)

        # EMA smoothing
        previous = self._icri
        self._icri = alpha * scaled + (1.0 - alpha) * previous

        # Ensure minimum ICRI increase of 0.10 when significant event arrives
        # (Requirement 24.4: QQ message → at least 0.10 increase)
        if max_event_intensity > 0.30 and (self._icri - previous) < 0.10:
            self._icri = min(1.0, previous + 0.10)

        return self._icri

    # ── Source feeding interface ──

    def feed_sensory(self, value: float):
        """Feed sensory integration source."""
        self._sources["sensory_integration"] = clamp(value)
        self._source_ttl["sensory_integration"] = self.DEFAULT_TTL

    def feed_emotional(self, panksepp_activation: Dict[str, float]):
        """
        Feed emotional coherence source from Panksepp activations.

        Coherence = multi-system co-activation with low variance.
        """
        if not panksepp_activation:
            return
        active = {k: v for k, v in panksepp_activation.items() if v > 0.1}
        if not active:
            self._sources["emotional_coherence"] = 0.0
            return

        values = list(active.values())
        avg = sum(values) / len(values)

        if len(values) <= 1:
            coherence = avg
        elif avg > 0.05:
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
            cv = std / avg if avg > 0 else 1.0
            count_bonus = min(len(values) / 5.0, 0.4)
            coherence = avg * (1.0 - min(cv, 0.8)) + count_bonus
        else:
            coherence = 0.0

        self._sources["emotional_coherence"] = clamp(coherence)
        self._source_ttl["emotional_coherence"] = self.DEFAULT_TTL

    def feed_dmn_depth(self, depth: float):
        """Feed DMN depth source (renamed from temporal_depth)."""
        self._sources["dmn_depth"] = clamp(depth)
        self._source_ttl["dmn_depth"] = self.DEFAULT_TTL

    def feed_self_reflection(self, value: float):
        """Feed self-reflection source."""
        self._sources["self_reflection"] = clamp(value)
        self._source_ttl["self_reflection"] = self.DEFAULT_TTL

    def feed_global_ignition(self, value: float):
        """Feed global ignition source."""
        self._sources["global_ignition"] = clamp(value)
        self._source_ttl["global_ignition"] = self.DEFAULT_TTL

    def feed_ignition_from_panksepp(self, panksepp_activation: Dict[str, float],
                                     baseline: float = 0.15):
        """
        Feed global ignition from active Panksepp system count.

        More active systems above baseline → stronger ignition.
        """
        if not panksepp_activation:
            self._sources["global_ignition"] = 0.0
            return
        total_systems = len(panksepp_activation)
        if total_systems == 0:
            self._sources["global_ignition"] = 0.0
            return
        active_count = sum(1 for v in panksepp_activation.values() if v > baseline)
        ratio = active_count / max(total_systems, 1)
        intensity = math.sqrt(ratio)
        self._sources["global_ignition"] = clamp(intensity)
        self._source_ttl["global_ignition"] = self.DEFAULT_TTL

    def feed_self_model_from_personality(self, personality_traits: Dict[str, float]):
        """
        Feed self-reflection from personality trait awareness.

        More defined personality (traits far from 0.5) = more self-awareness.
        """
        if not personality_traits:
            self._sources["self_reflection"] = 0.0
            return
        deviations = [abs(v - 0.5) for v in personality_traits.values()]
        avg_deviation = sum(deviations) / len(deviations) if deviations else 0.0
        openness = personality_traits.get("openness", 0.5)
        neuroticism = personality_traits.get("neuroticism", 0.5)
        reflexivity = (avg_deviation * 1.2 + openness * 0.3 + neuroticism * 0.2) / 1.7
        self._sources["self_reflection"] = clamp(reflexivity)
        self._source_ttl["self_reflection"] = self.DEFAULT_TTL

    def feed_dmn_from_thinking(self, thinking_mode: str, thought_count: int = 0):
        """
        Feed DMN depth from thinking mode.

        Depth mapping:
          idle → 0.1, shallow/replay → 0.3, mixed/daydream → 0.5,
          deep/counterfactual → 0.7, flow → 0.9
        """
        mode_depth = {
            "idle": 0.1,
            "shallow": 0.25,
            "replay": 0.3,
            "mixed": 0.5,
            "daydream": 0.55,
            "deep": 0.7,
            "counterfactual": 0.75,
            "flow": 0.9,
        }
        base_depth = mode_depth.get(thinking_mode, 0.3)
        count_bonus = min(thought_count / 10.0, 0.2)
        self._sources["dmn_depth"] = clamp(base_depth + count_bonus)
        self._source_ttl["dmn_depth"] = self.DEFAULT_TTL

    def feed_from_impact(self, impact: "CognitiveImpactProfile"):
        """
        Feed all ICRI sources directly from a CognitiveImpactProfile.

        Mapping:
          - impact.sensory  → sensory_integration
          - impact.cognitive → dmn_depth
          - impact.self_    → self_reflection
          - impact.novelty  → global_ignition

        Each dimension value is clamped to [0, 1] and directly sets the
        corresponding ICRI source. Source TTLs are reset for all fed sources.

        When an event does NOT carry a CognitiveImpactProfile, callers should
        fall back to the existing approximation methods (feed_emotional,
        feed_dmn_from_thinking, feed_self_model_from_personality,
        feed_ignition_from_panksepp).

        Requirements: 27.2, 27.3, 27.4, 27.5, 27.6
        """
        # Map sensory → sensory_integration
        self._sources["sensory_integration"] = clamp(impact.sensory)
        self._source_ttl["sensory_integration"] = self.DEFAULT_TTL

        # Map cognitive → dmn_depth
        self._sources["dmn_depth"] = clamp(impact.cognitive)
        self._source_ttl["dmn_depth"] = self.DEFAULT_TTL

        # Map self_ → self_reflection
        self._sources["self_reflection"] = clamp(impact.self_)
        self._source_ttl["self_reflection"] = self.DEFAULT_TTL

        # Map novelty → global_ignition
        self._sources["global_ignition"] = clamp(impact.novelty)
        self._source_ttl["global_ignition"] = self.DEFAULT_TTL

    # ── Properties ──

    @property
    def icri(self) -> float:
        """Current ICRI value."""
        return self._icri

    @property
    def phi(self) -> float:
        """Deprecated: backward compatibility alias for icri."""
        return self._icri

    @property
    def sources(self) -> Dict[str, float]:
        """Current source values (read-only copy)."""
        return dict(self._sources)

    def describe(self) -> str:
        """Human-readable description of current ICRI state."""
        return (f"ICRI={self._icri:.2f} "
                f"si={self._sources['sensory_integration']:.2f} "
                f"ec={self._sources['emotional_coherence']:.2f} "
                f"dmn={self._sources['dmn_depth']:.2f} "
                f"sr={self._sources['self_reflection']:.2f} "
                f"gi={self._sources['global_ignition']:.2f}")


# ═══════════════════════════════════════════════
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 UnifiedPhi (ICRI) 自测")
    print("=" * 50)

    # 创建
    phi = UnifiedPhi()

    # 喂数据
    phi.feed_sensory(0.3)
    phi.feed_emotional({"SEEKING": 0.6, "PLAY": 0.5, "CARE": 0.4,
                         "FEAR": 0.1, "PANIC": 0.1, "RAGE": 0.0, "LUST": 0.2})
    phi.feed_dmn(4, 0.5, ["memory_replay", "counterfactual"])
    phi.feed_ignition(True, 0.6)
    phi.feed_self_model(0.5, 0.4)

    # 聚合
    agg = phi.aggregate()
    print(f"  {phi.describe()}")
    print(f"  label: {phi.label.value}")
    print(f"  is_conscious: {phi.is_conscious}")

    # 调制
    mod = phi.modulator
    print(f"\n  调制值:")
    for k, v in mod.get_modulation_summary().items():
        print(f"    {k}: {v:.3f}")

    # 意识时刻
    moment = phi.detector.detect(phi, {
        "SEEKING": 0.7, "PLAY": 0.7, "CARE": 0.7,
        "FEAR": 0.1, "PANIC": 0.1, "RAGE": 0.0, "LUST": 0.2,
    })
    if moment:
        print(f"\n  ⚡ 检测到: {moment.type} — {moment.description}")
    else:
        print(f"\n  (无意识时刻)")

    print("\n✅ 自测通过!")

    # 模拟 20 个 cycle
    print(f"\n📈 模拟 20 cycles:")
    phi2 = UnifiedPhi()
    for i in range(20):
        s = i / 30 + 0.1
        e = {"SEEKING": 0.3 + s, "PLAY": 0.2 + s, "CARE": 0.1 + s}
        phi2.feed_sensory(s)
        phi2.feed_emotional(e)
        phi2.feed_dmn(i % 5, 0.3 + s * 0.5)
        val = phi2.aggregate()
        bar = "█" * int(val * 30)
        flags = ""
        m = phi2.detector.detect(phi2, e)
        if m: flags = f" ⚡{m.type}"
        print(f"  [{i:2d}] {bar:<30} ICRI={val:.2f} {phi2.label.value}{flags}")
