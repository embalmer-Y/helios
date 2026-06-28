"""v2 owner → AspectState 投影。

v2 数据源:
- `04` 9-dim hormone:DA / NE / 5-HT / ACh / Cort / Oxy / Opioid / excitation / inhibition
- `05` 7-dim feeling:valence / arousal / tension / comfort / pain_like / social_safety / fatigue
- `03` 5-dim salience:threat / reward / novelty / uncertainty / social + aggregate
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .aspect_state import AspectState


@dataclass(frozen=True)
class Hormone9D:
    """v2 04 9-dim hormone mock。"""
    dopamine: float
    norepinephrine: float
    serotonin: float
    acetylcholine: float
    cortisol: float
    oxytocin: float
    opioid_tone: float
    excitation: float
    inhibition: float


@dataclass(frozen=True)
class Feeling7D:
    """v2 05 7-dim feeling mock。"""
    valence: float
    arousal: float
    tension: float
    comfort: float
    pain_like: float
    social_safety: float
    fatigue: float


@dataclass(frozen=True)
class Salience5D:
    """v2 03 5-dim salience mock。"""
    threat: float
    reward: float
    novelty: float
    uncertainty: float
    social: float
    aggregate: float


def project_v2_to_aspect_state(
    hormone: Hormone9D,
    feeling: Feeling7D,
    salience: Salience5D,
    alpha_phasic: float = 1.0,
    history_state: "AspectState | None" = None,
) -> AspectState:
    """从 v2 9-dim hormone + 7-dim feeling + 5-dim salience 投影到 AspectState 10 字段。

    投影规则:
    - activation = (DA + NE) / 2,clamp [-1, 1]
    - valence = feeling.valence(直接)
    - arousal = feeling.arousal(直接)
    - certainty = 1 - salience.uncertainty(反向)
    - salience = salience.aggregate(直接)
    - precision = 0.5 * certainty + 0.5 * stability(动态精度)
    - novelty = salience.novelty(直接)
    - coherence = 1 - std(activation, valence, arousal, certainty, salience, precision)
    - stability = 1 - 1/(1 + alpha_phasic)
    - resonance = 跟 history_state 的 cosine 相似度(无 history 则 0.5)
    """
    activation = (hormone.dopamine + hormone.norepinephrine) / 2.0
    activation = float(np.clip(activation, -1.0, 1.0))

    certainty = 1.0 - salience.uncertainty
    stability = 1.0 - 1.0 / (1.0 + alpha_phasic)
    stability = float(np.clip(stability, 0.0, 1.0))
    precision = 0.5 * certainty + 0.5 * stability

    base6 = [activation, feeling.valence, feeling.arousal, certainty, salience.aggregate, precision]
    coherence = 1.0 - float(np.std(base6))
    coherence = float(np.clip(coherence, 0.0, 1.0))

    if history_state is not None:
        hist_dict = history_state.to_dict()
        curr_dict = {
            "activation": activation,
            "valence": feeling.valence,
            "arousal": feeling.arousal,
            "certainty": certainty,
            "salience": salience.aggregate,
            "precision": precision,
            "novelty": salience.novelty,
            "coherence": coherence,
            "stability": stability,
        }
        keys = ["activation", "valence", "arousal", "certainty", "salience",
                "precision", "novelty", "coherence", "stability"]
        hist_vec = np.array([hist_dict[k] for k in keys])
        curr_vec = np.array([curr_dict[k] for k in keys])
        norm_hist = float(np.linalg.norm(hist_vec))
        norm_curr = float(np.linalg.norm(curr_vec))
        if norm_hist > 1e-9 and norm_curr > 1e-9:
            resonance = float(np.dot(hist_vec, curr_vec) / (norm_hist * norm_curr))
            resonance = float(np.clip(resonance, 0.0, 1.0))
        else:
            resonance = 0.5
    else:
        resonance = 0.5

    return AspectState(
        activation=activation,
        valence=feeling.valence,
        arousal=feeling.arousal,
        certainty=certainty,
        salience=salience.aggregate,
        precision=precision,
        novelty=salience.novelty,
        coherence=coherence,
        stability=stability,
        resonance=resonance,
    )


def project_v2_to_aspect_state_default() -> AspectState:
    """从默认值(无历史)投影 AspectState(用于 cold start)。"""
    return project_v2_to_aspect_state(
        hormone=Hormone9D(
            dopamine=0.5, norepinephrine=0.5, serotonin=0.5,
            acetylcholine=0.5, cortisol=0.5, oxytocin=0.5,
            opioid_tone=0.5, excitation=0.5, inhibition=0.5,
        ),
        feeling=Feeling7D(
            valence=0.0, arousal=0.5, tension=0.5, comfort=0.5,
            pain_like=0.5, social_safety=0.5, fatigue=0.5,
        ),
        salience=Salience5D(
            threat=0.5, reward=0.5, novelty=0.5, uncertainty=0.5,
            social=0.5, aggregate=0.5,
        ),
        alpha_phasic=1.0,
        history_state=None,
    )
