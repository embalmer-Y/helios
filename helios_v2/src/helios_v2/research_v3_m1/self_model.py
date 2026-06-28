"""SelfModelOwner:封装 CDS,提供高层 API。

v3 plan §02_v3_design §2:SelfModelOwner 封装 CDS,
提供 tick(I, reflect, reward) + get_state_for_llm() + seed_prior_state() 接口。

封装关系:
    SelfModelOwner → CoupledDynamicalSystem → 8-dim ODE 演化
                → EmergenceDetector → 涌现事件检测
                → self_experience → LLM 被动接受

v3 治理铁律 #8:LLM 只能"看" self_experience,不能修改 8d state 或 C。
SelfModelOwner 保证这个不变性(get_state_for_llm 是 read-only 接口)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from helios_v2.research_v3_m1.cds import CoupledDynamicalSystem
from helios_v2.research_v3_m1.emergence import (
    EmergenceDetector,
    EmergenceEvent,
)


@dataclass
class SelfModelOwner:
    """v3 Layer 2 self-model 完整 owner。

    接口:
        - tick(I, reflect, reward) → 演化 + 学习 + 涌现检测
        - get_state_for_llm() → 返回 self_experience(只读)
        - seed_prior_state(state, C) → 跨 tick carry(从 checkpoint 恢复)

    LLM 只能通过 get_state_for_llm() "看" 状态,不能修改。
    """

    cds: CoupledDynamicalSystem
    emergence: EmergenceDetector
    tick_count: int = 0
    experience_history: list[dict] = None  # type: ignore

    def __post_init__(self):
        if self.experience_history is None:
            self.experience_history = []

    def tick(
        self,
        I: np.ndarray | None = None,
        reflect: np.ndarray | None = None,
        reward: float | None = None,
    ) -> dict:
        """每个 tick 演化 + 涌现检测。

        Returns:
            dict 含 self_experience + 涌现事件 + tick metadata
        """
        # 1. CDS 演化
        cds_result = self.cds.tick(I=I, reflect=reflect, reward=reward)

        # 2. 涌现检测
        emergence_events = self.emergence.detect(self.cds)

        # 3. self_experience 涌现态
        exp = self.cds.self_experience()
        self.experience_history.append(exp)
        self.tick_count += 1

        return {
            **cds_result,
            "self_experience": exp,
            "emergence_events": [
                {
                    "type": e.type,
                    "involved_aspects": list(e.involved_aspects),
                    "strength": e.strength,
                    "description": e.description,
                }
                for e in emergence_events
            ],
            "tick_count": self.tick_count,
        }

    def get_state_for_llm(self) -> dict[str, Any]:
        """返回给 LLM 的 self-model 状态(只读,被动暴露)。

        v3 治理铁律 #8:LLM 只能"看",不能改。
        """
        exp = self.cds.self_experience()
        return {
            "8d_state": exp["8d_state"],
            "coupling_matrix_summary": {
                "max": float(np.max(self.cds.C)),
                "min": float(np.min(self.cds.C)),
                "frobenius_norm": float(np.linalg.norm(self.cds.C)),
            },
            "global_coherence_R": exp["global_coherence_R"],
            "rochat_level_continuous": exp["rochat_level_continuous"],
            "rochat_level_discrete": exp["rochat_level_discrete"],
            "self_unity": exp["self_unity"],
            "agency_strength": exp["agency_strength"],
            "tick_count": self.tick_count,
        }

    def seed_prior_state(self, state: np.ndarray, C: np.ndarray | None = None):
        """跨 tick carry(从 checkpoint 恢复)。

        注意:不重置 experience_history(保留历史)
        """
        self.cds.seed_prior_state(state=state, C=C)

    @classmethod
    def default(cls) -> "SelfModelOwner":
        """默认 SelfModelOwner(标准 CDS + EmergenceDetector)。"""
        cds = CoupledDynamicalSystem()
        emergence = EmergenceDetector()
        return cls(cds=cds, emergence=emergence)
