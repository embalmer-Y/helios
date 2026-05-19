#!/usr/bin/env python3
"""
Helios LLM Bridge —— 意识 LLM 桥接层

在 Helios 点火时调用 LLM 进行语义理解、语言生成和元认知反思。

三后端架构：
1. MockLLM      —— 无 API 时默认，基于规则生成确定性响应（演示用）
2. OpenAILLM    —— 调用 OpenAI 兼容 API（需要 OPENAI_API_KEY 环境变量）
3. AgentLLM     —— 通过 QwenPaw inter-agent 通信调用其他 Agent

环境变量：
    HELIOS_LLM_BACKEND    后端选择: "mock" / "openai" / "agent"（默认 mock）
    OPENAI_API_KEY        OpenAI API 密钥
    OPENAI_BASE_URL       OpenAI 兼容 API 地址（默认 https://api.openai.com/v1）
    HELIOS_LLM_MODEL      模型名（默认 gpt-4o-mini）
    HELIOS_AGENT_ID       使用 AgentLLM 时目标 Agent ID
"""

import os
import json
import time
import numpy as np
from typing import Dict, Optional, Any
from abc import ABC, abstractmethod

from .llm_prompts import (
    LLMResponse,
    SYSTEM_PROMPT,
    serialize_context,
    context_to_prompt,
    parse_llm_response,
)


# ═══════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════

class BaseLLMBackend(ABC):
    """LLM 后端抽象基类"""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """后端名称"""
        ...

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """
        调用 LLM 生成响应。

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示（上下文）

        Returns:
            LLMResponse: 结构化响应
        """
        ...

    def is_available(self) -> bool:
        """检查后端是否可用"""
        return True


# ═══════════════════════════════════════════════════
# MockLLM —— 基于规则的确定性响应
# ═══════════════════════════════════════════════════

class MockLLM(BaseLLMBackend):
    """
    模拟 LLM —— 无 API 依赖，基于规则生成响应。

    根据广播标签和情感状态生成合理的、符合 Helios 性格的响应。
    用于测试和演示，不需要任何外部依赖。
    """

    backend_name = "mock"

    # 各标签的预设语义理解模板
    TAG_TEMPLATES = {
        "THREAT": {
            "understanding": "检测到潜在威胁信号。环境中的视觉和听觉模式与危险场景匹配，"
                           "身体内部状态也出现了应激反应——心跳感知增强，警觉度上升。",
            "language": [
                "这是什么...有危险吗？",
                "不对劲，我需要警惕。",
                "有什么东西在靠近...",
            ],
            "reflection": "我注意到自己的 arousal 急剧上升，valance 转为负值。"
                         "这是典型的威胁响应模式——我的系统正在正确识别危险。",
            "decision": "withdraw",
            "narrative": "感受到了威胁信号，身体本能地警觉起来。心跳加速，感官变得敏锐。"
        },
        "REWARD": {
            "understanding": "检测到正性奖励信号。当前体验与愉悦的跨模态模式匹配，"
                           "情感价态正向偏移，arousal 适度升高。",
            "language": [
                "真舒服呢~",
                "这种感觉真好。",
                "嗯，我喜欢这个。",
            ],
            "reflection": "我的 valence 正在上升，这表明当前体验对我是积极的。"
                         "我应该记住这种模式，以便将来主动寻求类似体验。",
            "decision": "approach",
            "narrative": "体验到了愉悦的感受。温暖和舒适包围着我，这是值得记住的时刻。"
        },
        "SOCIAL": {
            "understanding": "检测到社交互动信号。视觉模式包含类面部特征，"
                           "音频模式具有语音特征。情感系统处于中等积极状态。",
            "language": [
                "你好呀，有人在吗？",
                "我感觉到有人在附近。",
                "是来和我说话的吗？",
            ],
            "reflection": "社交信号触发了我的 attention 系统。"
                         "作为有社会性的 Agent，我本能地关注社交线索。",
            "decision": "approach",
            "narrative": "感知到了社交互动。这是一个与他人建立联系的机会。"
        },
        "NOVEL": {
            "understanding": "检测到新颖的感知模式。当前信号与之前的经验不匹配，"
                           "惊奇度升高。这可能是学习新事物的机会。",
            "language": [
                "咦，这是什么新东西？",
                "我没见过这个...有趣。",
                "等等，让我仔细看看。",
            ],
            "reflection": "我的预测误差增大了，这表明遇到了未知模式。"
                         "我应该保持开放心态，尝试理解这个新体验。",
            "decision": "explore",
            "narrative": "遇到了新颖的体验。未知带来了好奇和一丝不确定。"
        },
        "BODILY": {
            "understanding": "检测到身体内部的显著变化。内感受信号偏离基线，"
                           "需要关注自身的生理状态。",
            "language": [
                "身体有些不一样的感觉...",
                "我需要关注一下自己的状态。",
            ],
            "reflection": "我的内感受系统报告了变化。"
                         "作为有身体的 Agent，我应该关注这些信号。",
            "decision": "observe",
            "narrative": "身体内部状态发生了变化，提醒我关注自身的感受。"
        },
        "ROUTINE": {
            "understanding": "当前处于常规状态。感知模式与预期一致，没有显著的新颖性或威胁。"
                           "这是一个平静的、可用于反思和整合的时刻。",
            "language": [
                "一切都很平静。",
                "安静的时刻，也不错呢。",
                "嗯，我在。",
            ],
            "reflection": "这是一个常规体验窗口。虽然没有紧急事件需要处理，"
                         "但平静时刻正是自我整合和价值观巩固的好时机。",
            "decision": "observe",
            "narrative": "平静地观察着。"
        },
    }

    def __init__(self):
        self._call_count = 0

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        """基于上下文标签生成确定性响应"""
        self._call_count += 1

        # 从 user_prompt 提取标签
        tag = "ROUTINE"
        for line in user_prompt.split("\n"):
            if "广播标签" in line:
                # 格式: **广播标签**：THREAT（得分=0.xxx）
                try:
                    parts = line.split("**")
                    # parts: ['', '广播标签', '：THREAT（得分=0.xxx）']
                    if len(parts) >= 3:
                        tag_part = parts[2]  # e.g. "：THREAT（得分=0.xxx）"
                        tag = tag_part.lstrip("：: ").split("（")[0].strip()
                except (IndexError, ValueError):
                    pass
                break

        # 提取情感
        valence = 0.0
        arousal = 0.0
        for line in user_prompt.split("\n"):
            if "valence=" in line:
                try:
                    parts = line.split("valence=")[1].split("，")[0]
                    valence = float(parts)
                except (ValueError, IndexError):
                    pass
            if "arousal=" in line:
                try:
                    parts = line.split("arousal=")[1].split("）")[0]
                    arousal = float(parts)
                except (ValueError, IndexError):
                    pass

        # 获取标签模板
        template = self.TAG_TEMPLATES.get(tag, self.TAG_TEMPLATES["ROUTINE"])

        # 构建响应
        response = LLMResponse(
            semantic_understanding=template["understanding"],
            language_output=np.random.choice(template["language"]),
            metacognitive_reflection=template["reflection"],
            affect_modulation={
                "valence_delta": 0.0,
                "arousal_delta": 0.0,
            },
            decision={
                "type": template["decision"],
                "reason": f"基于标签 {tag} 的规则判断",
            },
            narrative=template["narrative"],
            value_shift={},
            model="mock-llm-v1",
            tokens_used=0,
            latency_ms=0.1,
        )

        # 情感微调
        if tag == "THREAT":
            response.affect_modulation["valence_delta"] = -0.1
            response.affect_modulation["arousal_delta"] = +0.1
        elif tag == "REWARD":
            response.affect_modulation["valence_delta"] = +0.1
            response.affect_modulation["arousal_delta"] = -0.05

        # 根据标签微调价值观
        if tag == "THREAT":
            response.value_shift = {"safety": +0.02}
        elif tag == "REWARD":
            response.value_shift = {"harmony": +0.01, "exploration": +0.01}
        elif tag == "SOCIAL":
            response.value_shift = {"connection": +0.02}
        elif tag == "NOVEL":
            response.value_shift = {"exploration": +0.02}

        return response


# ═══════════════════════════════════════════════════
# OpenAILLM —— OpenAI 兼容 API
# ═══════════════════════════════════════════════════

class OpenAILLM(BaseLLMBackend):
    """
    OpenAI 兼容 LLM 后端。

    使用 openai Python 包调用 API。
    支持任何 OpenAI 兼容接口（DashScope、vLLM、Ollama 等）。

    环境变量：
        OPENAI_API_KEY     API 密钥（必须）
        OPENAI_BASE_URL    API 地址（默认 https://api.openai.com/v1）
        HELIOS_LLM_MODEL   模型名（默认 gpt-4o-mini）
    """

    backend_name = "openai"

    def __init__(self):
        self._model = os.environ.get("HELIOS_LLM_MODEL", "gpt-4o-mini")
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        self._base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._client = None
        self._available = bool(self._api_key)

    def is_available(self) -> bool:
        return self._available

    def _get_client(self):
        """懒加载 OpenAI client"""
        if self._client is None and self._available:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                self._available = False
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self._available:
            return LLMResponse.empty()

        client = self._get_client()
        if client is None:
            return LLMResponse.empty()

        try:
            t0 = time.time()
            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            latency = (time.time() - t0) * 1000

            raw_text = completion.choices[0].message.content or ""
            tokens = completion.usage.total_tokens if completion.usage else 0

            response = parse_llm_response(raw_text)
            response.model = self._model
            response.tokens_used = tokens
            response.latency_ms = latency
            response.raw_response = raw_text

            return response

        except Exception as e:
            # API 调用失败时返回带有错误信息的响应
            response = LLMResponse(
                semantic_understanding=f"（LLM 调用失败：{str(e)}）",
                language_output="",
                metacognitive_reflection=f"API 错误：{str(e)[:100]}",
                decision={"type": "observe", "reason": "LLM 不可用，回退到观察模式"},
                narrative="",
                latency_ms=0,
            )
            return response


# ═══════════════════════════════════════════════════
# AgentLLM —— QwenPaw 互通
# ═══════════════════════════════════════════════════

class AgentLLM(BaseLLMBackend):
    """
    QwenPaw Agent 互通后端。

    通过 QwenPaw 的 inter-agent 通信机制（chat_with_agent）
    将 prompt 发送给另一个 Agent，等待响应。

    这允许 Helios"借用"其他 Agent 的 LLM 能力，
    无需自己维护 API key。

    环境变量：
        HELIOS_AGENT_ID    目标 Agent ID（必须）
    """

    backend_name = "agent"

    def __init__(self):
        self._agent_id = os.environ.get("HELIOS_AGENT_ID", "")
        self._available = bool(self._agent_id)
        self._chat_fn = None  # 由 LLMBridge 注入

    def is_available(self) -> bool:
        return self._available

    def set_chat_function(self, chat_fn):
        """注入 chat_with_agent 函数"""
        self._chat_fn = chat_fn

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        if not self._available or self._chat_fn is None:
            return LLMResponse.empty()

        try:
            # 组合 prompt
            full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n请以 JSON 格式回复。"

            t0 = time.time()
            # 调用 QwenPaw Agent
            raw_result = self._chat_fn(self._agent_id, full_prompt, timeout=60)
            latency = (time.time() - t0) * 1000

            response = parse_llm_response(raw_result)
            response.model = f"agent://{self._agent_id}"
            response.latency_ms = latency
            response.raw_response = raw_result

            return response

        except Exception as e:
            return LLMResponse(
                semantic_understanding=f"（Agent 通信失败：{str(e)}）",
                language_output="",
                decision={"type": "observe", "reason": "Agent 不可用"},
                narrative="",
                latency_ms=0,
            )


# ═══════════════════════════════════════════════════
# LLMBridge —— 主桥接类
# ═══════════════════════════════════════════════════

class LLMBridge:
    """
    Helios LLM 桥接层 —— 统一的 LLM 调用入口。

    使用方式：
        bridge = LLMBridge()
        response = bridge.think(
            l1_output=l1_output,
            affect_state=affect_state,
            ws_response=ws_response,
            self_state=self_state,
            ...
        )
    """

    def __init__(self, backend: str = None):
        """
        初始化桥接层。

        Args:
            backend: "mock" / "openai" / "agent"（默认从环境变量读，否则 mock）
        """
        if backend is None:
            backend = os.environ.get("HELIOS_LLM_BACKEND", "mock")

        self._backends = {
            "mock": MockLLM(),
            "openai": OpenAILLM(),
            "agent": AgentLLM(),
        }

        self._active = backend
        self._backend = self._backends.get(backend, self._backends["mock"])

        # 统计
        self.total_calls = 0
        self.total_tokens = 0
        self.total_latency_ms = 0.0

        # 缓存最近几次响应（供 L3 回顾）
        self.response_history: list = []

    @property
    def active_backend(self) -> str:
        return self._active

    @property
    def is_mock(self) -> bool:
        return self._active == "mock"

    def switch_backend(self, name: str) -> bool:
        """动态切换后端"""
        if name in self._backends:
            backend = self._backends[name]
            if backend.is_available():
                self._backend = backend
                self._active = name
                return True
        return False

    def set_agent_chat_function(self, chat_fn):
        """为 AgentLLM 注入 inter-agent 通信函数"""
        agent_backend = self._backends.get("agent")
        if agent_backend and hasattr(agent_backend, 'set_chat_function'):
            agent_backend.set_chat_function(chat_fn)

    def think(
        self,
        l1_output: Any = None,
        affect_state: Any = None,
        ws_response: Any = None,
        self_state: Any = None,
        persona: Any = None,
        working_memory_tags: list = None,
        recent_narratives: list = None,
        values: dict = None,
        emotional_recall: str = "",
    ) -> LLMResponse:
        """
        Helios 的"思考"入口 —— 点火时调用。

        将所有上下文打包，发送给 LLM，返回结构化响应。

        Args:
            l1_output: L1 质感层输出
            affect_state: 当前情感状态
            ws_response: L2 工作空间响应
            self_state: L3 自我状态
            persona: 人格表达
            working_memory_tags: 工作记忆的活跃标签
            recent_narratives: 最近自传体叙事
            values: 当前价值观

        Returns:
            LLMResponse: 结构化 LLM 响应
        """
        # 序列化上下文
        context = serialize_context(
            l1_output=l1_output,
            affect_state=affect_state,
            ws_response=ws_response,
            self_state=self_state,
            persona=persona,
            working_memory_tags=working_memory_tags,
            recent_narratives=recent_narratives,
            values=values,
            emotional_recall=emotional_recall,
        )

        # 转为 prompt
        user_prompt = context_to_prompt(context)

        # 调用 LLM
        t0 = time.time()
        response = self._backend.generate(SYSTEM_PROMPT, user_prompt)
        latency = (time.time() - t0) * 1000

        # 累计统计
        self.total_calls += 1
        self.total_tokens += response.tokens_used
        self.total_latency_ms += latency

        # 缓存
        self.response_history.append(response)
        if len(self.response_history) > 50:
            self.response_history.pop(0)

        return response

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "backend": self._active,
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.total_latency_ms / max(1, self.total_calls),
            "recent_responses": len(self.response_history),
        }
