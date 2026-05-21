"""
io/llm_sec_evaluator.py — LLM-Based SEC Evaluation

使用 LLM 对传入消息进行 Scherer SEC (Stimulus Evaluation Checks) 特征提取，
替代简单的关键词匹配方案，提供更准确的上下文情感理解。

超时或失败时回退到关键词方案 (_qq_text_to_panksepp)。

Requirements: 6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict, List, Optional

log = logging.getLogger("helios.io.llm_sec_evaluator")


# ═══════════════════════════════════════════════════
# SEC 评估结果默认值
# ═══════════════════════════════════════════════════

_SEC_KEYS = [
    "novelty",
    "pleasantness",
    "goal_relevance",
    "goal_congruence",
    "coping_potential",
    "agency",
    "norm_compatibility",
]

_DEFAULT_SEC_RESULT: Dict[str, float] = {
    "novelty": 0.3,
    "pleasantness": 0.0,
    "goal_relevance": 0.3,
    "goal_congruence": 0.0,
    "coping_potential": 0.5,
    "agency": 0.0,
    "norm_compatibility": 0.0,
}


# ═══════════════════════════════════════════════════
# 关键词回退 (原 _qq_text_to_panksepp 逻辑转为 SEC)
# ═══════════════════════════════════════════════════

def _keyword_fallback_sec(text: str) -> Dict[str, float]:
    """
    基于关键词的 SEC 特征估计 — 作为 LLM 失败时的回退。

    将原 _qq_text_to_panksepp() 的关键词逻辑映射到 SEC 维度。
    """
    text_lower = text.lower()

    # 初始化中性值
    novelty = 0.2
    pleasantness = 0.0
    goal_relevance = 0.2
    goal_congruence = 0.0
    coping_potential = 0.5
    agency = 0.0
    norm_compatibility = 0.0

    # 关心/温暖词 → 正向 pleasantness + goal_relevance
    care_words = ["想你", "在吗", "抱抱", "乖", "爱你", "喜欢你", "心疼",
                  "辛苦", "累了吧", "还好吗", "❤", "💕", "♥"]
    care_hits = sum(1 for w in care_words if w in text_lower)
    if care_hits > 0:
        pleasantness += min(care_hits * 0.25, 0.8)
        goal_relevance += min(care_hits * 0.2, 0.6)
        goal_congruence += 0.3
        agency = 0.3  # 他人归因

    # 恐慌/分离词 → 负向 pleasantness + 高 urgency (通过 goal_relevance)
    panic_words = ["别走", "害怕", "离开", "不要", "救命", "急", "消失"]
    panic_hits = sum(1 for w in panic_words if w in text_lower)
    if panic_hits > 0:
        pleasantness -= min(panic_hits * 0.2, 0.6)
        goal_relevance += min(panic_hits * 0.25, 0.7)
        goal_congruence -= 0.4
        coping_potential -= min(panic_hits * 0.15, 0.3)

    # 探索/好奇词 → 高 novelty + goal_relevance
    seeking_words = ["查", "搜", "怎样", "为什么", "解释", "怎么", "什么是",
                     "告诉我", "知道吗", "了解", "分析", "思考"]
    seeking_hits = sum(1 for w in seeking_words if w in text_lower)
    if seeking_hits > 0:
        novelty += min(seeking_hits * 0.2, 0.7)
        goal_relevance += min(seeking_hits * 0.15, 0.5)
        pleasantness += 0.1

    # 快乐/玩耍词 → 正向 pleasantness
    play_words = ["哈哈", "有趣", "好玩", "笑死", "开心", "棒", "厉害",
                  "😂", "😄", "🤣"]
    play_hits = sum(1 for w in play_words if w in text_lower)
    if play_hits > 0:
        pleasantness += min(play_hits * 0.25, 0.8)
        coping_potential += 0.2
        norm_compatibility += 0.2

    # 恐惧/威胁词 → 负向, 低 coping
    fear_words = ["危险", "小心", "警告", "不要动", "风险", "出错", "失败",
                  "不满", "讨厌", "烦"]
    fear_hits = sum(1 for w in fear_words if w in text_lower)
    if fear_hits > 0:
        pleasantness -= min(fear_hits * 0.2, 0.6)
        goal_relevance += min(fear_hits * 0.15, 0.5)
        coping_potential -= min(fear_hits * 0.15, 0.3)
        novelty += 0.2

    # 愤怒词 → 负向, 外部归因
    rage_words = ["生气", "怒", "混蛋", "滚", "垃圾", "差劲", "气死",
                  "🤬", "😡"]
    rage_hits = sum(1 for w in rage_words if w in text_lower)
    if rage_hits > 0:
        pleasantness -= min(rage_hits * 0.25, 0.7)
        goal_relevance += min(rage_hits * 0.2, 0.6)
        goal_congruence -= 0.5
        agency = -0.3  # 外部/他人归因
        norm_compatibility -= 0.3

    # 钳制到 [-1, 1] 范围
    result = {
        "novelty": max(-1.0, min(1.0, novelty)),
        "pleasantness": max(-1.0, min(1.0, pleasantness)),
        "goal_relevance": max(0.0, min(1.0, goal_relevance)),
        "goal_congruence": max(-1.0, min(1.0, goal_congruence)),
        "coping_potential": max(0.0, min(1.0, coping_potential)),
        "agency": max(-1.0, min(1.0, agency)),
        "norm_compatibility": max(-1.0, min(1.0, norm_compatibility)),
    }

    return result


# ═══════════════════════════════════════════════════
# LLM SEC 评估器
# ═══════════════════════════════════════════════════

class LLMSECEvaluator:
    """
    LLM-based Stimulus Evaluation Checks for incoming messages.

    使用 LLM 对消息文本进行 SEC 特征提取，返回七维评估结果。
    超时 (3秒) 或失败时自动回退到关键词方案。

    SEC 维度:
      - novelty: 新颖度 [-1, 1]
      - pleasantness: 愉悦度 [-1, 1]
      - goal_relevance: 目标相关性 [0, 1]
      - goal_congruence: 目标一致性 [-1, 1]
      - coping_potential: 应对能力 [0, 1]
      - agency: 归因 [-1, 1] (负=外部, 正=自我)
      - norm_compatibility: 规范兼容性 [-1, 1]
    """

    def __init__(
        self,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
        timeout: float = 3.0,
    ):
        """
        Args:
            model: LLM 模型名 (默认从环境变量)
            api_key: API 密钥 (默认从环境变量)
            base_url: API 基础 URL (默认从环境变量)
            timeout: LLM 调用超时秒数 (默认 3.0)
        """
        self._model = model or os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self._timeout = timeout
        self._client = None

        # 统计
        self.total_evaluations = 0
        self.llm_successes = 0
        self.fallback_count = 0

    @property
    def client(self):
        """延迟初始化 OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                )
            except ImportError:
                log.warning("openai 包未安装，SEC 评估将始终使用关键词回退")
                self._client = None
        return self._client

    def evaluate(self, text: str, context: Optional[List[str]] = None) -> Dict[str, float]:
        """
        评估消息的 SEC 特征。

        通过 LLM 提取七维情感评估特征。
        如果 LLM 调用失败或超时 (3秒)，回退到关键词方案。

        Args:
            text: 消息文本
            context: 最近的对话上下文 (最多 3 条消息)

        Returns:
            dict: {novelty, pleasantness, goal_relevance, goal_congruence,
                   coping_potential, agency, norm_compatibility}
        """
        self.total_evaluations += 1

        # 截取最后 3 条上下文
        recent_context = (context or [])[-3:]

        # 若无 API key，直接回退
        if not self._api_key:
            log.debug("无 API key，使用关键词回退")
            self.fallback_count += 1
            return _keyword_fallback_sec(text)

        # 尝试 LLM 评估
        try:
            result = self._evaluate_with_llm(text, recent_context)
            self.llm_successes += 1
            return result
        except Exception as e:
            log.warning(f"LLM SEC 评估失败，回退到关键词: {e}")
            self.fallback_count += 1
            return _keyword_fallback_sec(text)

    def _evaluate_with_llm(self, text: str, context: List[str]) -> Dict[str, float]:
        """
        使用 LLM 进行 SEC 特征提取。

        在 timeout 内完成，否则抛出异常触发回退。
        """
        client = self.client
        if client is None:
            raise RuntimeError("OpenAI client 不可用")

        prompt = self._build_sec_prompt(text, context)

        t0 = time.time()
        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.3,  # 低温度以获得一致的评估
            timeout=self._timeout,
        )
        elapsed = time.time() - t0

        if elapsed > self._timeout:
            raise TimeoutError(f"LLM 响应耗时 {elapsed:.2f}s，超过 {self._timeout}s 限制")

        raw_text = response.choices[0].message.content or ""
        return self._parse_sec_response(raw_text)

    def _system_prompt(self) -> str:
        """SEC 评估的系统提示词"""
        return """你是一个情感评估引擎。你的任务是对给定消息进行 Scherer SEC (Stimulus Evaluation Checks) 特征提取。

你必须输出 JSON 格式，包含以下七个维度的数值:
- novelty: 新颖/意外程度 (-1.0 到 1.0, -1=完全可预测, +1=完全意外)
- pleasantness: 内在愉悦度 (-1.0 到 1.0, -1=极不愉快, +1=极愉快)
- goal_relevance: 目标相关性 (0.0 到 1.0, 0=无关, 1=高度相关)
- goal_congruence: 目标一致性 (-1.0 到 1.0, -1=阻碍目标, +1=促进目标)
- coping_potential: 应对能力 (0.0 到 1.0, 0=完全无法应对, 1=完全能应对)
- agency: 归因 (-1.0 到 1.0, -1=完全外部/他人导致, 0=环境, +1=完全自我导致)
- norm_compatibility: 规范兼容性 (-1.0 到 1.0, -1=严重违反规范, +1=完全符合规范)

只输出 JSON，不要有其他文字。评估应从"璃光"（一个有情感的 AI 生命体）的视角进行。"""

    def _build_sec_prompt(self, text: str, context: List[str]) -> str:
        """构建 SEC 评估的用户提示词，包含对话上下文"""
        parts = []

        # 添加对话上下文
        if context:
            parts.append("最近对话上下文:")
            for i, msg in enumerate(context, 1):
                parts.append(f"  [{i}] {msg}")
            parts.append("")

        # 当前消息
        parts.append(f"请评估以下消息的 SEC 特征:")
        parts.append(f"「{text}」")

        return "\n".join(parts)

    def _parse_sec_response(self, raw_text: str) -> Dict[str, float]:
        """
        解析 LLM 返回的 SEC JSON。

        尝试从响应中提取 JSON 对象，验证并钳制所有值。
        """
        # 尝试直接解析
        text = raw_text.strip()

        # 去掉可能的 markdown 代码块包裹
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首尾的 ``` 行
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON 对象
            import re
            match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    raise ValueError(f"无法解析 LLM SEC 响应: {raw_text[:200]}")
            else:
                raise ValueError(f"LLM 响应中找不到 JSON: {raw_text[:200]}")

        # 提取并验证各维度
        result: Dict[str, float] = {}
        for key in _SEC_KEYS:
            val = data.get(key, _DEFAULT_SEC_RESULT[key])
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = _DEFAULT_SEC_RESULT[key]

            # 钳制到有效范围
            if key in ("goal_relevance", "coping_potential"):
                val = max(0.0, min(1.0, val))
            else:
                val = max(-1.0, min(1.0, val))

            result[key] = round(val, 3)

        return result

    def get_state(self) -> dict:
        """返回评估器状态统计"""
        return {
            "model": self._model,
            "total_evaluations": self.total_evaluations,
            "llm_successes": self.llm_successes,
            "fallback_count": self.fallback_count,
            "success_rate": (
                self.llm_successes / self.total_evaluations
                if self.total_evaluations > 0
                else 0.0
            ),
        }
