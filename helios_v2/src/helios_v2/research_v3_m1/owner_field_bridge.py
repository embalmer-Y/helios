"""M1-T8 OwnerFieldBridge: v2 owner → CDS 8-dim I 桥接器。

v2 owner 数据(21 字段):
  04 Hormone9D:  DA / NE / 5-HT / ACh / Cort / Oxy / Opioid / excitation / inhibition
  05 Feeling7D:  valence / arousal / tension / comfort / pain_like / social_safety / fatigue
  03 Salience5D: threat / reward / novelty / uncertainty / social (+ aggregate)

CDS 8-dim I (PTS_DIMENSION_NAMES):
  0 bodily_processes    (身体状态)
  1 minimal_experiential (基础体验)
  2 affective            (情感)
  3 intersubjective      (主体间性)
  4 psychological_cognitive (心理/认知)
  5 narrative            (叙事)
  6 ecological_extended  (生态扩展)
  7 normative            (规范)

桥接策略:
  - 每个 CDS 维度是 v2 owner 字段的加权和
  - 权重基于 v2 owner 设计文档的"情绪维度 → 自我意识层"映射
  - 输入归一化到 [-1, 1] 以匹配 CDS clip 范围
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from .projections import Hormone9D, Feeling7D, Salience5D
from .aspect_state import AspectState


# CDS 8 维索引常量
IDX_BODILY = 0
IDX_MINIMAL_EXPERIENTIAL = 1
IDX_AFFECTIVE = 2
IDX_INTERSUBJECTIVE = 3
IDX_PSYCHOLOGICAL = 4
IDX_NARRATIVE = 5
IDX_ECOLOGICAL = 6
IDX_NORMATIVE = 7


@dataclass(frozen=True)
class OwnerFieldMapping:
    """单个 CDS 维度到 v2 owner 字段的映射配置。

    Attributes:
        hormone_keys: Hormone9D 字段名 → 权重
        feeling_keys: Feeling7D 字段名 → 权重
        salience_keys: Salience5D 字段名 → 权重
        bias: 偏置项(默认 0)
        scale: 输出缩放(默认 1.0,用于把合成值拉到 [-1, 1])
    """
    hormone_keys: dict[str, float] = field(default_factory=dict)
    feeling_keys: dict[str, float] = field(default_factory=dict)
    salience_keys: dict[str, float] = field(default_factory=dict)
    bias: float = 0.0
    scale: float = 1.0


# 默认映射:v3 设计原则 "v2 owner → v3 self-model" 的初始权重
DEFAULT_MAPPINGS: tuple[OwnerFieldMapping, ...] = (
    # 0 bodily_processes: 身体状态 = cortisol + opioid_tone + pain_like - fatigue
    OwnerFieldMapping(
        hormone_keys={"cortisol": 0.4, "opioid_tone": 0.3},
        feeling_keys={"pain_like": 0.3, "fatigue": -0.2},
        salience_keys={},
        scale=1.0,
    ),
    # 1 minimal_experiential: 基础体验 = serotonin + minimal arousal
    OwnerFieldMapping(
        hormone_keys={"serotonin": 0.6, "acetylcholine": 0.2},
        feeling_keys={"comfort": 0.4},
        salience_keys={"uncertainty": -0.3},
        scale=1.0,
    ),
    # 2 affective: 情感 = valence + arousal + tension
    OwnerFieldMapping(
        hormone_keys={"dopamine": 0.3, "norepinephrine": 0.3},
        feeling_keys={"valence": 0.6, "arousal": 0.5, "tension": 0.4},
        salience_keys={"reward": 0.3},
        scale=1.0,
    ),
    # 3 intersubjective: 主体间性 = oxytocin + social_safety + social
    OwnerFieldMapping(
        hormone_keys={"oxytocin": 0.7},
        feeling_keys={"social_safety": 0.6, "comfort": 0.2},
        salience_keys={"social": 0.5},
        scale=1.0,
    ),
    # 4 psychological_cognitive: 心理/认知 = DA + ACh + novelty
    OwnerFieldMapping(
        hormone_keys={"dopamine": 0.4, "acetylcholine": 0.4},
        feeling_keys={"tension": 0.2},
        salience_keys={"novelty": 0.4, "uncertainty": 0.3},
        scale=1.0,
    ),
    # 5 narrative: 叙事 = excitation + DA + reward
    OwnerFieldMapping(
        hormone_keys={"excitation": 0.5, "dopamine": 0.3},
        feeling_keys={"valence": 0.2},
        salience_keys={"reward": 0.5, "novelty": 0.3},
        scale=1.0,
    ),
    # 6 ecological_extended: 生态扩展 = threat + novelty + NE
    OwnerFieldMapping(
        hormone_keys={"norepinephrine": 0.5},
        feeling_keys={"arousal": 0.3},
        salience_keys={"threat": 0.6, "novelty": 0.4},
        scale=1.0,
    ),
    # 7 normative: 规范 = inhibition + comfort + uncertainty
    OwnerFieldMapping(
        hormone_keys={"inhibition": 0.5, "serotonin": 0.3},
        feeling_keys={"comfort": 0.4},
        salience_keys={"uncertainty": -0.3},
        scale=1.0,
    ),
)


@dataclass
class OwnerFieldBridge:
    """v2 owner → CDS 8-dim I 桥接器。

    Usage:
        bridge = OwnerFieldBridge.default()
        I = bridge.bridge_input(hormone, feeling, salience)
        owner.tick(I=I)
    """
    mappings: tuple[OwnerFieldMapping, ...] = DEFAULT_MAPPINGS

    @classmethod
    def default(cls) -> "OwnerFieldBridge":
        return cls(mappings=DEFAULT_MAPPINGS)

    @classmethod
    def with_mappings(cls, mappings: tuple[OwnerFieldMapping, ...]) -> "OwnerFieldBridge":
        return cls(mappings=mappings)

    def bridge_input(
        self,
        hormone: Hormone9D,
        feeling: Feeling7D,
        salience: Salience5D,
    ) -> np.ndarray:
        """v2 owner → CDS 8-dim I 输入向量。

        Returns:
            8-dim np.ndarray,每个分量 ∈ [-scale, +scale]
        """
        h = {
            "dopamine": hormone.dopamine,
            "norepinephrine": hormone.norepinephrine,
            "serotonin": hormone.serotonin,
            "acetylcholine": hormone.acetylcholine,
            "cortisol": hormone.cortisol,
            "oxytocin": hormone.oxytocin,
            "opioid_tone": hormone.opioid_tone,
            "excitation": hormone.excitation,
            "inhibition": hormone.inhibition,
        }
        f = {
            "valence": feeling.valence,
            "arousal": feeling.arousal,
            "tension": feeling.tension,
            "comfort": feeling.comfort,
            "pain_like": feeling.pain_like,
            "social_safety": feeling.social_safety,
            "fatigue": feeling.fatigue,
        }
        s = {
            "threat": salience.threat,
            "reward": salience.reward,
            "novelty": salience.novelty,
            "uncertainty": salience.uncertainty,
            "social": salience.social,
            "aggregate": salience.aggregate,
        }

        I = np.zeros(8)
        for i, mapping in enumerate(self.mappings):
            value = mapping.bias
            for key, w in mapping.hormone_keys.items():
                value += w * h[key]
            for key, w in mapping.feeling_keys.items():
                value += w * f[key]
            for key, w in mapping.salience_keys.items():
                value += w * s[key]
            I[i] = value * mapping.scale

        return np.clip(I, -1.0, 1.0)

    def bridge_reflect(
        self,
        aspect_state: AspectState,
        history: AspectState | None = None,
    ) -> np.ndarray:
        """AspectState → CDS 8-dim reflect 调制向量(M2 阶段使用)。

        反映"上一刻"aspect state 对"下一刻"CDS 的调制影响。
        """
        a = aspect_state.to_dict()
        reflect = np.zeros(8)

        # 0 bodily: 跟 arousal + activation 强相关
        reflect[IDX_BODILY] = 0.5 * a["arousal"] + 0.3 * abs(a["activation"])

        # 1 minimal_experiential: 跟 certainty + coherence 相关
        reflect[IDX_MINIMAL_EXPERIENTIAL] = 0.4 * a["certainty"] + 0.3 * a["coherence"]

        # 2 affective: 直接传递 valence + arousal
        reflect[IDX_AFFECTIVE] = 0.5 * a["valence"] + 0.4 * a["arousal"]

        # 3 intersubjective: 跟 resonance 相关
        reflect[IDX_INTERSUBJECTIVE] = 0.6 * a["resonance"]

        # 4 psychological_cognitive: 跟 precision + novelty
        reflect[IDX_PSYCHOLOGICAL] = 0.4 * a["precision"] + 0.4 * a["novelty"]

        # 5 narrative: 跟 salience + stability
        reflect[IDX_NARRATIVE] = 0.4 * a["salience"] + 0.3 * a["stability"]

        # 6 ecological_extended: 跟 novelty + salience
        reflect[IDX_ECOLOGICAL] = 0.5 * a["novelty"] + 0.3 * a["salience"]

        # 7 normative: 跟 stability + coherence
        reflect[IDX_NORMATIVE] = 0.5 * a["stability"] + 0.3 * a["coherence"]

        return np.clip(reflect, -1.0, 1.0)

    def describe_mapping(self) -> str:
        """返回映射描述(M2 reflection owner 可读这个了解 v2 → v3 桥接逻辑)。"""
        from .cds import PTS_DIMENSION_NAMES
        lines = ["OwnerFieldBridge mapping (CDS dim ← v2 owner weights):"]
        for i, mapping in enumerate(self.mappings):
            name = PTS_DIMENSION_NAMES[i]
            parts = []
            for k, w in mapping.hormone_keys.items():
                parts.append(f"h.{k}={w:+.1f}")
            for k, w in mapping.feeling_keys.items():
                parts.append(f"f.{k}={w:+.1f}")
            for k, w in mapping.salience_keys.items():
                parts.append(f"s.{k}={w:+.1f}")
            lines.append(f"  [{i}] {name}: " + " ".join(parts))
        return "\n".join(lines)


# === v2 owner fixtures for tests ===

def fixture_neutral() -> tuple[Hormone9D, Feeling7D, Salience5D]:
    """中性 baseline(所有字段 = 0)。"""
    h = Hormone9D(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    f = Feeling7D(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    s = Salience5D(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    return h, f, s


def fixture_high_activation_high_valence() -> tuple[Hormone9D, Feeling7D, Salience5D]:
    """高激活 + 高正价:大 DA + NE + valence 高 + arousal 高。"""
    h = Hormone9D(
        dopamine=0.8, norepinephrine=0.7, serotonin=0.5,
        acetylcholine=0.4, cortisol=0.3, oxytocin=0.6,
        opioid_tone=0.5, excitation=0.7, inhibition=0.2,
    )
    f = Feeling7D(
        valence=0.8, arousal=0.8, tension=0.3,
        comfort=0.7, pain_like=0.0, social_safety=0.8,
        fatigue=0.0,
    )
    s = Salience5D(
        threat=0.1, reward=0.8, novelty=0.6,
        uncertainty=0.2, social=0.7, aggregate=0.5,
    )
    return h, f, s


def fixture_high_threat_high_cortisol() -> tuple[Hormone9D, Feeling7D, Salience5D]:
    """高威胁 + 高皮质醇:危险情境。"""
    h = Hormone9D(
        dopamine=0.3, norepinephrine=0.9, serotonin=0.2,
        acetylcholine=0.5, cortisol=0.9, oxytocin=0.1,
        opioid_tone=0.2, excitation=0.8, inhibition=0.3,
    )
    f = Feeling7D(
        valence=-0.7, arousal=0.9, tension=0.8,
        comfort=-0.5, pain_like=0.7, social_safety=-0.3,
        fatigue=0.4,
    )
    s = Salience5D(
        threat=0.9, reward=0.1, novelty=0.3,
        uncertainty=0.7, social=0.0, aggregate=0.7,
    )
    return h, f, s


def fixture_low_energy_fatigue() -> tuple[Hormone9D, Feeling7D, Salience5D]:
    """低能量疲劳:低 DA + 高 fatigue。"""
    h = Hormone9D(
        dopamine=0.1, norepinephrine=0.1, serotonin=0.3,
        acetylcholine=0.2, cortisol=0.4, oxytocin=0.2,
        opioid_tone=0.2, excitation=0.0, inhibition=0.5,
    )
    f = Feeling7D(
        valence=-0.3, arousal=0.1, tension=0.2,
        comfort=0.3, pain_like=0.3, social_safety=0.3,
        fatigue=0.9,
    )
    s = Salience5D(
        threat=0.2, reward=0.1, novelty=0.1,
        uncertainty=0.5, social=0.2, aggregate=0.2,
    )
    return h, f, s