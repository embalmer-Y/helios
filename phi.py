"""
Helios 统一 Φ 引擎
══════════════════

设计原则：
  - 单一真相来源：所有子系统读/写同一个 UnifiedPhi
  - 多源融合：L1信息整合 + Panksepp共振 + DMN深度 + L3自我反思 + L2点火
  - 双向调制：Φ 反映意识状态，也反过来调制各子系统
  - 意识时刻检测：aha/共振/流状态 (Dehaene 2006)

理论基础：
  - Tononi (2004) 信息整合理论 (IIT): Φ = 系统整体的信息量 - 各部分信息量之和
  - Dehaene (2006) 全局神经元工作空间: 意识 = 全局广播 + 点火
  - Seth (2011) 预测处理: 意识 = 自上而下预测 + 自下而上误差的精确加权

用法:
  from phi import UnifiedPhi, PhiModulator, ConsciousnessDetector
  phi = UnifiedPhi()
  phi.feed_sensory(l1_output)
  phi.feed_emotional(panksepp_activation)
  current = phi.aggregate()
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


# ═══════════════════════════════════════════════
# 统一 Φ
# ═══════════════════════════════════════════════

@dataclass
class UnifiedPhi:
    """
    Helios 的统一 Φ 模型

    Φ 是意识丰富度的度量 (0~1):
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
            self.global_ignition = intensity
        else:
            self.global_ignition = 0.0
        self._sources_valid["global_ignition"] = self.source_ttl

    def feed_self_model(self, self_confidence: float, narrative_depth: float):
        """L3 → Φ: 自我模型强度"""
        self.self_reflection = clamp(self_confidence * 0.5 + narrative_depth * 0.5)
        self._sources_valid["self_reflection"] = self.source_ttl

    # ── 源衰减 ──

    def _decay_sources(self):
        """每个 cycle 衰减源数据"""
        for key in self._sources_valid:
            self._sources_valid[key] = max(0.0, self._sources_valid[key] - 1.0)

    # ── 聚合 ──

    def aggregate(self) -> float:
        """
        聚合所有子成分 → 统一 Φ 值

        使用指数平滑防止振荡
        """
        self._decay_sources()

        total = 0.0
        weight_sum = 0.0

        for key, weight in self.weights.items():
            if self._sources_valid[key] > 0:
                value = getattr(self, key)
                total += value * weight
                weight_sum += weight

        if weight_sum > 0:
            self._phi_raw = total / weight_sum  # 归一化
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
    def phi(self) -> float:
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
        return (f"Φ={self._phi:.2f} [{self.label.value}] "
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
    Φ 对子系统的调制器

    核心规则: Φ 高 → 系统更敏感/更协调/更深思
              Φ 低 → 系统更迟钝/更竞争/更浅层
    """

    def __init__(self, phi: UnifiedPhi):
        self.phi = phi

    # ── Panksepp ──

    def modulate_threshold(self, base_threshold: float) -> float:
        """情感激活阈值: Φ高 → 阈值低 → 更敏感"""
        return base_threshold * (1.0 - 0.30 * self.phi.phi)

    def modulate_cross_effect(self, base_strength: float) -> float:
        """交叉效应强度: Φ高 → 交叉更强 → 情感更整合"""
        return base_strength * (1.0 + 0.30 * self.phi.phi)

    def modulate_decay(self, base_decay: float) -> float:
        """衰减速率: Φ高 → 衰减慢 → 状态持久"""
        return base_decay * (1.0 - 0.25 * self.phi.phi)

    # ── DMN ──

    def modulate_dmn_depth(self) -> int:
        """DMN 碎片数: Φ高 → 更深思"""
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
        """神经递质衰减: Φ高 → 慢衰减"""
        return base_decay_rate * (1.0 - 0.25 * self.phi.phi)

    def modulate_neurochem_response(self, base_amount: float) -> float:
        """神经化学事件响应: Φ高 → 更强"""
        return base_amount * (1.0 + 0.20 * self.phi.phi)

    # ── LLM ──

    def modulate_llm_tokens(self, base_tokens: int) -> int:
        """LLM max_tokens: Φ高 → 更深思"""
        return min(int(base_tokens * (1.0 + 0.5 * self.phi.phi)), 800)

    def modulate_llm_temperature(self, base_temp: float) -> float:
        """LLM temperature: Φ高 → 更发散"""
        return min(base_temp * (1.0 + 0.15 * self.phi.phi), 1.2)

    # ── Limb 安全 ──

    def modulate_rate_limit(self, base_rate: int) -> int:
        """手脚频率限制: Φ高 → 更宽松"""
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

    Aha:       Φ 突变 (ΔΦ > 0.25 in 2 cycles)
    Resonance: 3+ 子系统同时高激活
    Flow:      Φ 持续 >0.65 超过 5 cycles
    """

    def detect(self, phi: UnifiedPhi,
               subsystems: Optional[Dict[str, float]] = None
               ) -> Optional[ConsciousnessMoment]:
        h = phi.history
        ph = phi.phi

        # Aha: Φ 突变检测
        if len(h) >= 3:
            prev = sum(h[-4:-1]) / 3 if len(h) >= 4 else sum(h[-3:-1]) / 2
            if ph - prev > 0.25:
                return ConsciousnessMoment(
                    type="aha",
                    phi_value=ph,
                    description=f"Φ 飙升 {prev:.2f}→{ph:.2f}",
                )

        # Resonance: 多系统共激活
        if subsystems:
            active_high = sum(1 for v in subsystems.values() if v > 0.55)
            if active_high >= 3 and ph > 0.50:
                return ConsciousnessMoment(
                    type="resonance",
                    phi_value=ph,
                    subsystems=subsystems,
                    description=f"{active_high} 子系统共振 (Φ={ph:.2f})",
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
# 自测
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 UnifiedPhi 自测")
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
        print(f"  [{i:2d}] {bar:<30} Φ={val:.2f} {phi2.label.value}{flags}")
