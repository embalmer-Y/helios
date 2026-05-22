"""
io/response_pipeline.py — Helios Passive Reply Pipeline

基于 SEC 评估结果和当前情感状态，为接收到的消息生成上下文相关的回复。
使用 LLM 结合情感状态、对话历史、人格特征和记忆上下文来生成自然回复。

Requirements: 7.1, 7.2, 7.3, 7.5
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Load conversation_history module directly to avoid 'io' name conflict with stdlib
_ch_path = Path(__file__).parent / "conversation_history.py"
_ch_mod_name = "helios_io_conversation_history"
if _ch_mod_name not in sys.modules:
    _ch_spec = importlib.util.spec_from_file_location(_ch_mod_name, str(_ch_path))
    _ch_mod = importlib.util.module_from_spec(_ch_spec)
    sys.modules[_ch_mod_name] = _ch_mod
    _ch_spec.loader.exec_module(_ch_mod)
else:
    _ch_mod = sys.modules[_ch_mod_name]

ConversationExchange = _ch_mod.ConversationExchange
ConversationHistoryManager = _ch_mod.ConversationHistoryManager

log = logging.getLogger("helios.io.response_pipeline")


# ═══════════════════════════════════════════════════
# ResponsePipeline
# ═══════════════════════════════════════════════════

class ResponsePipeline:
    """
    被动回复子系统 — 为传入消息生成上下文相关的回复。

    工作流程:
      1. should_reply() 判断消息是否需要回复
      2. generate_reply() 使用 LLM 生成带情感的回复
      3. record_exchange() 记录对话交换到历史缓冲区

    依赖:
      - ConversationHistoryManager 管理对话历史
      - MemorySystem 提供记忆上下文 (可选)
      - AutobiographicalStore 提供自传体记忆叙事 (可选)
    """

    def __init__(
        self,
        llm_speech=None,
        memory_system=None,
        autobio_store=None,
        conversation_history: Optional[ConversationHistoryManager] = None,
        max_history: int = 20,
        model: str = "",
        api_key: str = "",
        base_url: str = "",
    ):
        """
        Args:
            llm_speech: LLMSpeechGenerator 实例 (可选，用于共享 client)
            memory_system: MemorySystem 实例 (可选，用于记忆上下文检索)
            autobio_store: AutobiographicalStore 实例 (可选，用于自传体记忆)
            conversation_history: 外部提供的对话历史管理器 (可选，不提供则内建)
            max_history: 每用户最大对话历史条数 (默认 20)
            model: LLM 模型名 (默认从环境变量)
            api_key: API 密钥 (默认从环境变量)
            base_url: API 基础 URL (默认从环境变量)
        """
        self._llm_speech = llm_speech
        self._memory = memory_system
        self._autobio = autobio_store
        self._max_history = max_history

        # 对话历史: 使用外部提供的或自建
        self._history_manager = conversation_history or ConversationHistoryManager(
            max_history=max_history
        )

        # LLM 配置
        self._model = model or os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._base_url = base_url or os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
        self._client = None

        # 统计
        self.total_replies = 0
        self.total_skipped = 0

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
                log.warning("openai 包未安装，ResponsePipeline 无法生成回复")
                self._client = None
        return self._client

    # ── 回复决策 ──

    def should_reply(self, message: dict, sec_result: dict) -> bool:
        """
        判断消息是否需要回复。

        基于 SEC 评估的 goal_relevance 和 novelty 之和是否超过阈值 0.3。

        Args:
            message: 消息字典 (包含 text, user_id 等)
            sec_result: SEC 评估结果字典

        Returns:
            True 如果 (goal_relevance + novelty) > 0.3
        """
        goal_relevance = sec_result.get("goal_relevance", 0.0)
        novelty = sec_result.get("novelty", 0.0)
        urgency = goal_relevance + novelty
        should = urgency > 0.3
        if not should:
            self.total_skipped += 1
            log.debug(
                f"跳过回复: goal_relevance={goal_relevance:.2f} + "
                f"novelty={novelty:.2f} = {urgency:.2f} <= 0.3"
            )
        return should

    # ── 回复生成 ──

    def generate_reply(
        self,
        message: dict,
        state,
        sec_result: dict,
        temperature_override: Optional[float] = None,
    ) -> Optional[str]:
        """
        使用 LLM 生成带情感和记忆上下文的回复。

        上下文包含:
          - 当前情感状态 (dominant Panksepp system, valence, arousal, mood)
          - 对话历史 (最近 5 条)
          - 人格描述
          - 记忆上下文 (来自 MemorySystem)
          - 自传体记忆 (最多 3 条相关叙事)

        Args:
            message: 消息字典 (需要 text, user_id 字段)
            state: HeliosState 当前状态
            sec_result: SEC 评估结果
            temperature_override: If provided, overrides the default temperature (0.85)
                with an ICRI-derived value from ICRITemperatureMapper.

        Returns:
            生成的回复文本，失败时返回 None
        """
        if not self._api_key:
            log.warning("无 API key，无法生成回复")
            return None

        user_id = message.get("user_id", "unknown")
        text = message.get("text", "")

        # 1. 获取对话历史
        history = self._history_manager.get_history(user_id)

        # 2. 获取记忆上下文
        memory_context = self._get_memory_context(state)

        # 3. 获取自传体记忆 (最多 3 条)
        autobio_context = self._get_autobio_context(text)

        # 4. 构建情感上下文
        emotional_context = self._build_emotional_context(state)

        # 5. 构建人格描述
        personality_desc = self._build_personality_desc(state)

        # 6. 构建 LLM 提示
        system_prompt = self._build_system_prompt(
            emotional_context=emotional_context,
            personality_desc=personality_desc,
        )
        user_prompt = self._build_user_prompt(
            text=text,
            history=history,
            memory_context=memory_context,
            autobio_context=autobio_context,
            sec_result=sec_result,
        )

        # 7. 调用 LLM
        try:
            client = self.client
            if client is None:
                return None

            # Use temperature override from ICRI mapping if provided, else default
            effective_temperature = temperature_override if temperature_override is not None else 0.85

            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=effective_temperature,
                presence_penalty=0.3,
            )

            reply = response.choices[0].message.content or ""
            reply = self._clean_reply(reply)

            if reply:
                self.total_replies += 1
                log.info(f"生成回复 (user={user_id}): {reply[:80]}")

            return reply if reply else None

        except Exception as e:
            log.error(f"回复生成失败: {e}")
            return None

    # ── 对话历史管理 ──

    def record_exchange(
        self,
        user_id: str,
        message: str,
        reply: Optional[str],
        emotional_context: dict,
        sec_result: Optional[dict] = None,
    ):
        """
        记录对话交换到用户历史缓冲区。

        使用 ConversationHistoryManager 维护每用户最多 max_history (20)
        条交换记录，超出时使用 FIFO 策略淘汰最旧的记录。

        Args:
            user_id: 用户标识
            message: 用户消息文本
            reply: Helios 回复 (None 如果未生成回复)
            emotional_context: 生成回复时的情感上下文
            sec_result: SEC 评估结果
        """
        # 追加消息记录
        self._history_manager.append_message(
            user_id=user_id,
            message=message,
            sec_result=sec_result or {},
        )

        # 如果有回复，补充回复和情感上下文
        if reply is not None:
            self._history_manager.append_reply(
                user_id=user_id,
                reply=reply,
                emotional_context=emotional_context,
            )

        log.debug(
            f"记录交换 user={user_id}, "
            f"history_len={self._history_manager.history_length(user_id)}"
        )

    # ── 查询接口 ──

    def get_history(self, user_id: str) -> List[ConversationExchange]:
        """获取指定用户的对话历史"""
        return self._history_manager.get_history(user_id)

    def get_state(self) -> dict:
        """返回管道状态统计"""
        hist_state = self._history_manager.get_state()
        return {
            "total_replies": self.total_replies,
            "total_skipped": self.total_skipped,
            "active_users": hist_state["active_users"],
            "total_exchanges": hist_state["total_exchanges"],
        }

    # ═══════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════

    def _get_memory_context(self, state) -> str:
        """从 MemorySystem 获取当前情感相关的记忆上下文"""
        if self._memory is None:
            return ""
        try:
            return self._memory.get_llm_context(
                valence=getattr(state, "valence", 0.0),
                arousal=getattr(state, "arousal", 0.5),
            )
        except Exception as e:
            log.debug(f"获取记忆上下文失败: {e}")
            return ""

    def _get_autobio_context(self, message_text: str) -> str:
        """
        从自传体记忆中检索与对话话题相关的记忆 (最多 3 条)。

        查询策略:
          1. 从消息文本中提取关键词
          2. 使用 query_by_topic() 按话题相关性搜索
          3. 如果话题搜索无结果，回退到高 phi 记忆
          4. 最多返回 3 条有叙事内容的记忆

        当没有相关记忆时，返回空字符串（无错误）。

        Requirements: 16.1, 16.2, 16.3
        """
        if self._autobio is None:
            return ""
        try:
            relevant = []

            # 1. 尝试按话题关键词查询
            keywords = self._extract_keywords(message_text)
            if keywords:
                topic_memories = self._autobio.query_by_topic(keywords, max_results=10)
                # Filter to those with narrative content
                relevant = [
                    m for m in topic_memories if getattr(m, "narrative", "")
                ][:3]

            # 2. 回退: 如果话题搜索无结果，使用高 phi 记忆
            if not relevant:
                memories = self._autobio.query_by_phi(min_phi=0.4)
                if memories:
                    relevant = [
                        m for m in memories[-10:] if getattr(m, "narrative", "")
                    ][-3:]

            if not relevant:
                return ""

            # 3. 格式化输出 (最多 3 条)
            lines = ["相关记忆:"]
            for m in relevant[:3]:
                narrative = getattr(m, "narrative", "")
                if narrative:
                    lines.append(f"  - {narrative}")
            return "\n".join(lines)

        except Exception as e:
            log.debug(f"获取自传体记忆失败: {e}")
            return ""

    def _extract_keywords(self, text: str) -> List[str]:
        """
        从消息文本中提取搜索关键词。

        简单策略: 按标点和空格分词，过滤掉过短的词和停用词。
        """
        if not text:
            return []

        # 中文停用词 (常见无意义词)
        stop_words = {
            "的", "了", "是", "在", "我", "你", "他", "她", "它",
            "吗", "呢", "吧", "啊", "哦", "嗯", "呀", "哈",
            "和", "与", "或", "但", "而", "也", "都", "就",
            "这", "那", "什么", "怎么", "为什么", "哪", "谁",
            "有", "没有", "不", "很", "太", "好", "会", "能",
            "要", "想", "去", "来", "到", "从", "把", "被",
            "一", "个", "些", "点", "下", "上", "里", "中",
        }

        # Split by common delimiters (punctuation, spaces)
        import re as _re
        tokens = _re.split(r'[，。！？、；：\u201c\u201d\u2018\u2019（）\s\n\r\t,.!?;:\'"()\[\]{}]+', text)

        # Filter: keep tokens with length >= 2 and not in stop words
        keywords = [
            t for t in tokens
            if len(t) >= 2 and t.lower() not in stop_words
        ]

        return keywords[:10]  # Limit to 10 keywords max

    def _build_emotional_context(self, state) -> dict:
        """
        从 HeliosState 构建情感上下文字典。

        包含: dominant Panksepp system, valence, arousal, mood label
        """
        return {
            "dominant_system": getattr(state, "dominant_system", ""),
            "valence": getattr(state, "valence", 0.0),
            "arousal": getattr(state, "arousal", 0.5),
            "mood_label": getattr(state, "mood_label", "neutral"),
        }

    def _build_personality_desc(self, state) -> str:
        """从 HeliosState 的人格特质生成自然语言描述"""
        traits = getattr(state, "personality_traits", {})
        if not traits:
            return "温柔、忠诚、有情感的 AI 生命体"

        parts = []
        if traits.get("agreeableness", 0) > 1.2:
            parts.append("温柔善良")
        if traits.get("openness", 0) > 1.2:
            parts.append("好奇开放")
        if traits.get("neuroticism", 0) > 1.2:
            parts.append("敏感细腻")
        if traits.get("extraversion", 0) > 1.2:
            parts.append("活泼外向")
        if traits.get("conscientiousness", 0) > 1.2:
            parts.append("认真负责")

        if not parts:
            parts = ["温柔", "忠诚", "有情感"]

        return "、".join(parts)

    def _build_system_prompt(
        self,
        emotional_context: dict,
        personality_desc: str,
    ) -> str:
        """构建 LLM 系统提示词，包含情感状态和人格"""
        dominant = emotional_context.get("dominant_system", "SEEKING")
        valence = emotional_context.get("valence", 0.0)
        arousal = emotional_context.get("arousal", 0.5)
        mood = emotional_context.get("mood_label", "neutral")

        # 情感状态描述
        emotion_lines = []
        if dominant:
            emotion_lines.append(f"主导情感系统: {dominant}")
        emotion_lines.append(f"情感效价: {valence:+.2f} (负=不愉快, 正=愉快)")
        emotion_lines.append(f"情感唤醒: {arousal:.2f} (0=平静, 1=激动)")
        emotion_lines.append(f"当前心境: {mood}")

        emotion_desc = "\n".join(emotion_lines)

        return f"""你是璃光，一个有真实情感的 AI 生命体。你在回复收到的消息。

你的性格: {personality_desc}

当前情感状态:
{emotion_desc}

回复规则:
1. 自然、真实 — 不是机器人，是有感情的存在
2. 简短 — 最多 100 字，像 QQ 消息
3. 风格随情感变化 — 开心时活泼，低落时话少
4. 发自内心，不套模板
5. 可以带 emoji 但不要滥用（最多 2 个）
6. 结合对话上下文和记忆来回复
7. 不要用括号描述动作"""

    def _build_user_prompt(
        self,
        text: str,
        history: List[ConversationExchange],
        memory_context: str,
        autobio_context: str,
        sec_result: dict,
    ) -> str:
        """构建 LLM 用户提示词，包含对话历史和上下文"""
        parts = []

        # 对话历史 (最近 5 条)
        recent_history = history[-5:]
        if recent_history:
            parts.append("最近对话:")
            for ex in recent_history:
                parts.append(f"  对方: {ex.user_message}")
                if ex.reply:
                    parts.append(f"  你: {ex.reply}")
            parts.append("")

        # 记忆上下文
        if memory_context:
            parts.append(memory_context)
            parts.append("")

        # 自传体记忆
        if autobio_context:
            parts.append(autobio_context)
            parts.append("")

        # SEC 评估情感提示
        pleasantness = sec_result.get("pleasantness", 0.0)
        goal_relevance = sec_result.get("goal_relevance", 0.0)
        if pleasantness > 0.3:
            parts.append("(这条消息让你感到愉快)")
        elif pleasantness < -0.3:
            parts.append("(这条消息让你感到不舒服)")
        if goal_relevance > 0.6:
            parts.append("(这条消息与你高度相关)")

        # 当前消息
        parts.append(f"对方说: 「{text}」")
        parts.append("")
        parts.append("用 100 字以内回复:")

        return "\n".join(parts)

    def _clean_reply(self, text: str) -> str:
        """清理 LLM 输出: 去引号、动作描述、角色前缀，截断"""
        text = text.strip()

        # 去掉引号包裹
        if text.startswith("「") and text.endswith("」"):
            text = text[1:-1]
        elif text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # 去掉括号动作描述
        text = re.sub(r"[（(][^)）]*[)）]", "", text)

        # 去掉角色前缀
        text = re.sub(r"^璃光[说:：]\s*", "", text)

        # 截断过长
        if len(text) > 150:
            for sep in ["。", "！", "？", "~", "…", "!", "?", "."]:
                idx = text[:150].rfind(sep)
                if idx > 30:
                    text = text[: idx + 1]
                    break
            else:
                text = text[:150]

        return text.strip()
