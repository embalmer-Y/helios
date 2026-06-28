"""AspectState 10 字段向量(替代 v1 标量 s_i)。

v1 标量 s_i 丢掉了"高激活低确定""正效价低唤醒""高激活高精度"等
关键心理状态。v2 redesign 要求 10+ 字段向量,本 ship 实证。

v3 治理铁律 #8:"LLM 只能看 self-experience,不能修改 8d state 或 C"。
所以 AspectState 是 frozen dataclass(不可变)。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


LEGAL_RANGES: dict[str, tuple[float, float]] = {
    "activation": (-1.0, 1.0),
    "valence":    (-1.0, 1.0),
    "arousal":    (0.0, 1.0),
    "certainty":  (0.0, 1.0),
    "salience":   (0.0, 1.0),
    "precision":  (0.0, 1.0),
    "novelty":    (0.0, 1.0),
    "coherence":  (0.0, 1.0),
    "stability":  (0.0, 1.0),
    "resonance":  (0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class AspectState:
    """10 字段 AspectState 向量(frozen 不可变,符合 v3 治理铁律 #8)。

    字段独立:
    - 基础 6 维:activation / valence / arousal / certainty / salience / precision
    - 扩展 4 维:novelty / coherence / stability / resonance

    数值合法性:
    - activation, valence: [-1, 1](双向)
    - 其他 8 字段: [0, 1](单向)
    - 任何字段在 __post_init__ 中 clip 到合法范围
    """

    # 基础 6 维
    activation: float
    valence: float
    arousal: float
    certainty: float
    salience: float
    precision: float

    # 扩展 4 维
    novelty: float
    coherence: float
    stability: float
    resonance: float

    def __post_init__(self) -> None:
        """Clip 每个字段到合法范围(frozen dataclass 用 object.__setattr__)。"""
        for name, (lo, hi) in LEGAL_RANGES.items():
            value = getattr(self, name)
            if not (lo <= value <= hi):
                clipped = max(lo, min(hi, value))
                object.__setattr__(self, name, clipped)

    def to_dict(self) -> dict[str, float]:
        """可序列化为 dict(round-trip 一致)。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> "AspectState":
        """从 dict 构造(允许传入任意 subset,缺失字段用中性默认 0.5)。"""
        defaults = {name: 0.5 for name in LEGAL_RANGES}
        for k, v in d.items():
            if k in LEGAL_RANGES:
                defaults[k] = float(v)
        return cls(**defaults)

    def to_llm_text(self) -> str:
        """序列化为 LLM 可读文本(token 预算 < 200 字符)。"""
        parts = [
            f"{k}={getattr(self, k):.2f}"
            for k in LEGAL_RANGES.keys()
        ]
        return ", ".join(parts)

    def __repr__(self) -> str:
        d = self.to_dict()
        kv = ", ".join(f"{k}={v:.2f}" for k, v in d.items())
        return f"AspectState({kv})"

    def is_high_activation_low_certainty(self) -> bool:
        """Fixture 1: '我强烈觉得不安但说不清为什么'"""
        return self.activation > 0.5 and self.certainty < 0.4

    def is_positive_valence_low_arousal(self) -> bool:
        """Fixture 2: '平静的满足感'"""
        return self.valence > 0.3 and self.arousal < 0.4

    def is_high_activation_high_precision(self) -> bool:
        """Fixture 3: '我确信这是威胁'"""
        return (
            self.activation > 0.5
            and self.precision > 0.8
            and self.valence < 0.0
        )

    def to_scalar_v1(self) -> float:
        """v1 兼容:10 字段压缩为 1 个标量(用于对比实验)。"""
        return (
            0.3 * self.activation
            + 0.2 * self.valence
            + 0.1 * self.arousal
            + 0.2 * self.salience
            + 0.1 * self.precision
            + 0.1 * self.certainty
        )


FIXTURE_HIGH_ACTIVATION_LOW_CERTAINTY = AspectState(
    activation=0.8, valence=-0.3, arousal=0.7,
    certainty=0.2, precision=0.3, salience=0.6,
    novelty=0.5, coherence=0.4, stability=0.3, resonance=0.2,
)

FIXTURE_POSITIVE_VALENCE_LOW_AROUSAL = AspectState(
    activation=0.3, valence=0.7, arousal=0.2,
    certainty=0.6, precision=0.7, salience=0.4,
    novelty=0.2, coherence=0.7, stability=0.8, resonance=0.6,
)

FIXTURE_HIGH_ACTIVATION_HIGH_PRECISION = AspectState(
    activation=0.8, valence=-0.5, arousal=0.8,
    certainty=0.9, precision=0.95, salience=0.9,
    novelty=0.3, coherence=0.8, stability=0.7, resonance=0.7,
)
