"""
helios_io/response_pipeline.py — Helios Passive Interaction Helper

负责被动消息处理中的 history、SEC helper 和 observability。
运行时的用户可见外发文本必须来自 thought-origin action proposal；本模块不再拥有独立 reply 或 external proposal owner。

Requirements: 7.1, 7.2, 7.3, 7.5
"""

from __future__ import annotations

from dataclasses import replace
import logging
import os
import re
import time
from typing import Callable, Dict, List, Optional
from uuid import uuid4

from .channel import ChannelDescriptor
from .conversation_history import ConversationExchange, ConversationHistoryManager
from .interaction_policy import InteractionPolicy
from .reply_prompt_builder import ReplyPromptBuilder
from personality_contract import build_personality_contract

log = logging.getLogger("helios.helios_io.response_pipeline")


# ═══════════════════════════════════════════════════
# ResponsePipeline
# ═══════════════════════════════════════════════════

class ResponsePipeline:
    """
        被动交互辅助子系统。

        工作流程:
            1. should_reply() 提供兼容性的 SEC 阈值判断
            2. record_exchange() 记录对话交换到历史缓冲区

    依赖:
      - ConversationHistoryManager 管理对话历史
      - MemorySystem 提供记忆上下文 (可选)
      - AutobiographicalStore 提供自传体记忆叙事 (可选)
            - 不负责独立生成用户可见回复正文或 external proposal
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
        interaction_policy: Optional[InteractionPolicy] = None,
        channel_descriptor_provider: Optional[Callable[[], Dict[str, ChannelDescriptor]]] = None,
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
        self._interaction_policy = interaction_policy or InteractionPolicy()
        self._channel_descriptor_provider = channel_descriptor_provider
        self._reply_cleaner = ReplyPromptBuilder(
            layered_enabled=os.getenv("HELIOS_LAYERED_REPLY_PROMPT_ENABLED", "1") == "1"
        )

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
        temperature: Optional[float] = None,
    ) -> Optional[str]:
        log.warning(
            "generate_reply() is disabled: outbound user-visible text must originate from thought/action proposals user=%s",
            message.get("user_id", "unknown"),
        )
        return None

    @staticmethod
    def _trim_for_log(text: str, limit: int = 240) -> str:
        text = str(text).replace("\n", "\\n").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _build_user_prompt(
        self,
        *,
        text: str,
        history: List[ConversationExchange],
        memory_context: str,
        autobio_context: str,
        sec_result: dict,
        current_conversation_context: str = "",
        user_long_term_context: str = "",
        global_fallback_context: str = "",
    ) -> str:
        """Compatibility wrapper for legacy tests and internal prompt inspection."""
        return self._reply_cleaner.build_user_prompt(
            text=text,
            history=history,
            memory_context=memory_context,
            autobio_context=autobio_context,
            sec_result=sec_result,
            current_conversation_context=current_conversation_context,
            user_long_term_context=user_long_term_context,
            global_fallback_context=global_fallback_context,
        )

    # ── 对话历史管理 ──

    def record_exchange(
        self,
        user_id: str,
        message: str,
        reply: Optional[str],
        emotional_context: dict,
        sec_result: Optional[dict] = None,
        conversation_key: str = "",
        rendered_reply: Optional[str] = None,
        expression_profile: Optional[dict] = None,
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
            conversation_key=conversation_key,
        )

        # 如果有回复，补充回复和情感上下文
        if reply is not None:
            self._history_manager.append_reply(
                user_id=user_id,
                reply=rendered_reply if rendered_reply is not None else reply,
                emotional_context=emotional_context,
                conversation_key=conversation_key,
                original_reply=reply,
                expression_profile=expression_profile,
            )

        log.debug(
            f"记录交换 user={user_id}, "
            f"history_len={self._history_manager.history_length(user_id)}"
        )

    # ── 查询接口 ──

    def get_history(self, user_id: str, conversation_key: str = "") -> List[ConversationExchange]:
        """获取指定用户的对话历史"""
        return self._history_manager.get_history(user_id, conversation_key=conversation_key)

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

    def _get_memory_context(
        self,
        state,
        *,
        user_id: str = "",
        message_text: str = "",
        history: Optional[List[ConversationExchange]] = None,
        history_texts: Optional[List[str]] = None,
        conversation_key: str = "",
    ) -> str:
        """从 MemorySystem 获取记忆上下文。无 user 语境时回退到旧的 affect-first 路径。"""
        bundle = self._get_reply_memory_bundle(
            state,
            user_id=user_id,
            message_text=message_text,
            history=history,
            history_texts=history_texts,
            conversation_key=conversation_key,
        )
        if bundle:
            return bundle.get("long_term_and_global", "")

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

    def _get_reply_memory_bundle(
        self,
        state,
        *,
        user_id: str = "",
        message_text: str = "",
        history: Optional[List[ConversationExchange]] = None,
        history_texts: Optional[List[str]] = None,
        conversation_key: str = "",
    ) -> Dict[str, str]:
        """获取分层回复记忆 bundle，失败时返回空分区。"""
        if self._memory is None:
            return {}
        try:
            history_texts = history_texts or []
            if not history_texts and history:
                for ex in history[-5:]:
                    parts = []
                    if getattr(ex, "user_message", ""):
                        parts.append(f"对方: {ex.user_message}")
                    if getattr(ex, "reply", ""):
                        parts.append(f"你: {ex.reply}")
                    if parts:
                        history_texts.append("\n".join(parts))

            if user_id or message_text or history_texts:
                if hasattr(self._memory, "get_reply_memory_bundle"):
                    bundle = self._memory.get_reply_memory_bundle(
                        user_id=user_id,
                        message_text=message_text,
                        history_texts=history_texts,
                        conversation_key=conversation_key,
                        valence=getattr(state, "valence", 0.0),
                        arousal=getattr(state, "arousal", 0.5),
                    )
                    log.debug(
                        "Reply memory bundle trace: user=%s trace=%s current_len=%d long_term_len=%d fallback_len=%d",
                        user_id or "unknown",
                        getattr(bundle, "trace_summary", ""),
                        len(bundle.resolved_text_sections.get("current_conversation", "")),
                        len(bundle.resolved_text_sections.get("user_long_term", "")),
                        len(bundle.resolved_text_sections.get("global_fallback", "")),
                    )
                    return {
                        **dict(bundle.resolved_text_sections),
                        "trace_summary": getattr(bundle, "trace_summary", ""),
                    }

                context = self._memory.get_llm_context(
                    valence=getattr(state, "valence", 0.0),
                    arousal=getattr(state, "arousal", 0.5),
                    user_id=user_id,
                    message_text=message_text,
                    history_texts=history_texts,
                    conversation_key=conversation_key,
                )
                return {
                    "current_conversation": "",
                    "user_long_term": context,
                    "global_fallback": "",
                    "long_term_and_global": context,
                    "trace_summary": "legacy_bundle_path",
                }

            return {}
        except Exception as e:
            log.debug(f"获取记忆上下文失败: {e}")
            return {}

    @staticmethod
    def _derive_conversation_key(message: dict) -> str:
        explicit_key = str(message.get("conversation_key") or message.get("session_name") or "")
        if explicit_key:
            return explicit_key

        channel_id = str(message.get("channel_id") or message.get("channel") or "")
        if bool(message.get("is_group", False)):
            group_id = str(message.get("group_id") or "")
            if group_id:
                return f"{channel_id}:group:{group_id}" if channel_id else f"group:{group_id}"

        user_id = str(message.get("user_id") or "")
        if user_id:
            return f"{channel_id}:dm:{user_id}" if channel_id else f"dm:{user_id}"

        return ""

    def _get_autobio_context(
        self,
        message_text: str,
        user_id: str = "",
        history: Optional[List[ConversationExchange]] = None,
    ) -> str:
        """
        从自传体记忆中检索相关记忆 (最多 3 条)。

        按用户和话题相关性查询记忆，
        返回格式化的叙事摘要字符串。
        """
        if self._autobio is None:
            return ""
        try:
            history = history or []
            history_texts = []
            for ex in history[-3:]:
                if getattr(ex, "user_message", ""):
                    history_texts.append(ex.user_message)
                if getattr(ex, "reply", ""):
                    history_texts.append(ex.reply)

            if self._memory is not None and hasattr(self._memory, "get_autobio_context"):
                return self._memory.get_autobio_context(
                    topic_text=message_text,
                    user_id=user_id,
                    history_texts=history_texts,
                    limit=3,
                )

            if hasattr(self._autobio, "query_related"):
                memories = self._autobio.query_related(
                    topic_text=message_text,
                    user_id=user_id,
                    history_texts=history_texts,
                    limit=3,
                )
            else:
                memories = self._autobio.query_by_phi(min_phi=0.4)
            if not memories:
                return ""

            # 取有叙事内容的相关记忆 (最多 3 条)
            relevant = [
                m for m in memories if getattr(m, "narrative", "")
            ][:3]

            if not relevant:
                return ""

            lines = ["相关记忆:"]
            for m in relevant:
                narrative = getattr(m, "narrative", "")
                if narrative:
                    lines.append(f"  - {narrative}")
            return "\n".join(lines)

        except Exception as e:
            log.debug(f"获取自传体记忆失败: {e}")
            return ""

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

    def _build_personality_descriptor(self, state):
        return build_personality_contract(
            projection=getattr(state, "personality_projection", None),
            traits=getattr(state, "personality_traits", {}) or {},
            identity_store=getattr(state, "identity_snapshot", {}) or {},
            source_path="reply_generation",
        )

    def _build_personality_desc(self, state) -> str:
        """从统一人格描述符生成自然语言描述"""
        descriptor, _trace = self._build_personality_descriptor(state)
        return descriptor.persona_text_summary

    def _clean_reply(self, text: str) -> str:
        """清理 LLM 输出，使用显式 cleaning policy。"""
        return self._reply_cleaner.clean_reply(text)
