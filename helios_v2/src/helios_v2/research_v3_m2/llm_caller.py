"""LLM 被动接受接口协议 + 默认 FakeLLMCaller。

v3 design §5.3: LLM 被动接受 self-experience(不做主动协调)。

关键约束:
  - LLMCallerProtocol 是 Protocol(duck typing)
  - FakeLLMCaller 是默认实现,基于 heuristic 产生 reflect + response
  - 真实 LLM 集成在 M5-T1,届时实现 LLMCallerProtocol 即可替换
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class LLMCallerProtocol(Protocol):
    """LLM caller 协议 - 任何能接收 snapshot + trigger 返回 (response, reflect) 的对象。

    M5-T1 将提供 LlmCaller 实现,只需满足这个协议即可接入 ReflectionOwner。
    """

    def call(
        self,
        snapshot: dict,
        trigger: str,
        user_prompt: str | None = None,
    ) -> tuple[str, np.ndarray]:
        """调用 LLM,返回 (text_response, reflect_vector)。

        Args:
            snapshot: SelfModelOwner.get_state_for_llm() 返回的 dict(READ-ONLY)
            trigger: 触发源名称(POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED)
            user_prompt: USER_INVOKED 时用户提示,其他 trigger 为 None

        Returns:
            (text_response, reflect_vector)
              text_response: LLM 的反思文本
              reflect_vector: 8-dim 反思调制向量(注入 CDS 的 reflect 参数)
        """
        ...


class FakeLLMCaller:
    """Fake LLM caller,基于 snapshot heuristic 产生确定性 reflect。

    设计意图:
      - 不调真 LLM(避免依赖 + 加速测试)
      - 产生**确定性** reflect(基于 snapshot 字段)
      - 模拟 LLM 的"passive accept"行为(只读 snapshot,不修改 state)
      - M5-T1 替换为真 LLMCaller

    启发式 reflect 生成:
      - 当 R > 0.7: 反思全同步 → reflect 弱(系统稳定,不需要大幅调制)
      - 当 R < 0.3: 反思低同步 → reflect 强(尝试激发特定维度)
      - 高 arousal → 调制 affective / bodily 维度
      - 高 novelty → 调制 narrative 维度
      - 低 certainty → 调制 minimal_experiential / normative
    """

    def __init__(self, deterministic: bool = True, response_style: str = "concise"):
        self.deterministic = deterministic
        self.response_style = response_style
        self.call_count = 0

    def call(
        self,
        snapshot: dict,
        trigger: str,
        user_prompt: str | None = None,
    ) -> tuple[str, np.ndarray]:
        """基于 snapshot heuristic 返回 deterministic reflect。

        Returns:
            (text_response, reflect_vector)
        """
        self.call_count += 1
        R = snapshot.get("global_coherence_R", 0.5)
        state = np.array(snapshot.get("8d_state", [0.0] * 8))
        rochat = snapshot.get("rochat_level_discrete", 3)

        # heuristic reflect
        reflect = np.zeros(8)
        if R > 0.7:
            # 全同步,弱调制(轻微"确认"系统状态)
            reflect = 0.05 * np.sin(np.linspace(0, 2 * np.pi, 8))
        elif R < 0.3:
            # 低同步,强调制(尝试激发特定维度)
            reflect = 0.4 * np.cos(np.linspace(0, np.pi, 8))
        else:
            # 中等同步,按维度启发
            for i in range(8):
                if abs(state[i]) > 5.0:
                    reflect[i] = -0.3 * np.sign(state[i])
                else:
                    reflect[i] = 0.1 * (state[i] / 5.0 if abs(state[i]) > 1e-6 else 0.0)

        # clip 到 [-1, 1]
        reflect = np.clip(reflect, -1.0, 1.0)

        # 模拟 LLM 文本响应
        if self.response_style == "concise":
            response = (
                f"[fake-llm] trigger={trigger} R={R:.3f} rochat={rochat} "
                f"state_max={float(np.max(np.abs(state))):.3f}"
            )
        else:
            response = (
                f"Reflection triggered by {trigger}. "
                f"Current Kuramoto R = {R:.3f} (Rochat level {rochat}/5). "
                f"State magnitudes: max={float(np.max(np.abs(state))):.3f}, "
                f"std={float(np.std(state)):.3f}. "
                f"Observe without modifying."
            )

        if user_prompt is not None:
            response = f"[user-invoked] {user_prompt}\n" + response

        return response, reflect