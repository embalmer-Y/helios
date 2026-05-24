"""
helios_io/response_pipeline.py — Helios Passive Reply Pipeline

基于 SEC 评估结果和当前情感状态，为接收到的消息生成上下文相关的回复。
使用 LLM 结合情感状态、对话历史、人格特征和记忆上下文来生成自然回复。

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

from .action_models import ActionDecision, ActionProposal
from .channel import ChannelDescriptor
from .conversation_history import ConversationExchange, ConversationHistoryManager
from .icri_temperature import ICRITemperatureMapper
from .interaction_policy import InteractionPolicy
from .prompt_contract import PromptContractBuilder
from .reply_prompt_builder import ReplyPromptBuilder
from personality_contract import build_personality_contract

log = logging.getLogger("helios.helios_io.response_pipeline")


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
        self._prompt_contract_builder = PromptContractBuilder()
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

    def build_reply_proposal(
        self,
        message: dict,
        sec_result: dict,
        state,
        available_channels: Optional[List[str]] = None,
    ) -> Optional[ActionProposal]:
        for proposal in self.build_interaction_proposals(
            message,
            sec_result,
            state,
            available_channels=available_channels,
        ):
            if proposal.behavior_name == "reply_message":
                return proposal
        return None

    def build_interaction_proposals(
        self,
        message: dict,
        sec_result: dict,
        state,
        available_channels: Optional[List[str]] = None,
    ) -> List[ActionProposal]:
        recent_history = self.get_history(message.get("user_id", "unknown"))
        proposals = self._interaction_policy.propose(
            message,
            sec_result,
            state,
            available_channels=available_channels,
            recent_history=recent_history,
        )
        if proposals:
            log.debug(
                "Interaction proposals(policy): user=%s count=%d types=%s",
                message.get("user_id", "unknown"),
                len(proposals),
                [p.behavior_name for p in proposals],
            )
            return proposals

        if not self.should_reply(message, sec_result):
            log.debug(
                "No passive proposal: should_reply=False user=%s sec=%s text=%r",
                message.get("user_id", "unknown"),
                {
                    "goal_relevance": round(float(sec_result.get("goal_relevance", 0.0)), 3),
                    "novelty": round(float(sec_result.get("novelty", 0.0)), 3),
                    "pleasantness": round(float(sec_result.get("pleasantness", 0.0)), 3),
                },
                self._trim_for_log(str(message.get("text", "")), 220),
            )
            return []

        message_channel = str(message.get("channel_id") or "")
        seed_channels = list(available_channels or [])
        if not seed_channels and message_channel:
            seed_channels = [message_channel]
        candidate_channels = [channel_id for channel_id in seed_channels if channel_id]
        if message_channel and message_channel not in candidate_channels:
            candidate_channels.insert(0, message_channel)
        goal_relevance = float(sec_result.get("goal_relevance", 0.0))
        novelty = float(sec_result.get("novelty", 0.0))
        urgency = goal_relevance + novelty
        log.debug(
            "Interaction fallback proposal(legacy_should_reply): user=%s urgency=%.3f channels=%s",
            message.get("user_id", "unknown"),
            urgency,
            candidate_channels,
        )
        return [
            ActionProposal(
                proposal_id=f"proposal::reply::{uuid4().hex}",
                source_type="interaction",
                source_module="response_pipeline_legacy",
                intent_type="reply",
                behavior_name="reply_message",
                reason_summary=(
                    f"Legacy reply fallback accepted: goal_relevance={goal_relevance:.2f}, novelty={novelty:.2f}."
                ),
                score_bundle={
                    "goal_relevance": goal_relevance,
                    "novelty": novelty,
                    "final": urgency,
                },
                constraints={
                    "reply_required": True,
                    "source_channel_id": message_channel,
                    "message_id": message.get("message_id", ""),
                    "required_capabilities": ["send"],
                },
                suggested_modalities=["text"],
                candidate_channels=candidate_channels,
                parameters={
                    "target_user_id": message.get("user_id", "unknown"),
                    "outbound_metadata": {
                        "message_id": message.get("message_id", ""),
                        "is_group": message.get("is_group", False),
                        "group_id": message.get("group_id", ""),
                    },
                    "source_message_text": message.get("text", ""),
                },
                provenance={
                    "message_text": message.get("text", ""),
                    "user_id": message.get("user_id", "unknown"),
                    "sec_result": dict(sec_result),
                    "fallback": "legacy_should_reply",
                },
                created_at_tick=int(getattr(state, "tick", 0)),
                created_at_ts=float(getattr(state, "timestamp", time.time())),
            )
        ]

    def populate_reply_decision(
        self,
        decision: ActionDecision,
        message: dict,
        state,
        sec_result: dict,
        temperature: Optional[float] = None,
    ) -> Optional[ActionDecision]:
        reply = self.generate_reply(message, state, sec_result, temperature=temperature)
        if not reply:
            return None

        updated_params = dict(decision.validated_params)
        updated_params.setdefault("target_user_id", message.get("user_id", "unknown"))
        updated_params["outbound_text"] = reply
        updated_params["outbound_metadata"] = {
            **dict(updated_params.get("outbound_metadata", {}) or {}),
            "message_id": message.get("message_id", ""),
            "is_group": message.get("is_group", False),
            "group_id": message.get("group_id", ""),
        }
        return replace(decision, validated_params=updated_params)

    # ── 回复生成 ──

    def generate_reply(
        self,
        message: dict,
        state,
        sec_result: dict,
        temperature: Optional[float] = None,
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

        Returns:
            生成的回复文本，失败时返回 None
        """
        if not self._api_key:
            log.warning("无 API key，无法生成回复")
            return None

        user_id = str(message.get("user_id") or "unknown")
        memory_user_id = str(message.get("user_id") or "")
        conversation_key = self._derive_conversation_key(message)
        text = message.get("text", "")

        # 1. 获取对话历史
        history = self._history_manager.get_history(
            memory_user_id,
            conversation_key=conversation_key,
        )
        history_texts = self._history_manager.get_recent_exchange_texts(
            memory_user_id,
            count=5,
            conversation_key=conversation_key,
        )

        # 2. 获取用户会话优先的记忆 bundle
        memory_bundle = self._get_reply_memory_bundle(
            state,
            user_id=memory_user_id,
            message_text=text,
            history=history,
            history_texts=history_texts,
            conversation_key=conversation_key,
        )
        memory_context = memory_bundle.get("long_term_and_global", "")
        current_conversation_context = memory_bundle.get("current_conversation", "")
        user_long_term_context = memory_bundle.get("user_long_term", "")
        global_fallback_context = memory_bundle.get("global_fallback", "")

        # 3. 自传体记忆已纳入用户长程记忆分区；保留空白兼容旧提示结构
        autobio_context = ""

        # 4. 构建情感上下文
        emotional_context = self._build_emotional_context(state)

        # 4b. ICRI-driven generation temperature
        icri = getattr(state, "icri", getattr(state, "phi", 0.0))
        llm_temperature = (
            temperature if temperature is not None else ICRITemperatureMapper.map_temperature(icri)
        )

        # 5. 构建统一人格描述符
        personality_descriptor, personality_trace = self._build_personality_descriptor(state)
        personality_desc = personality_descriptor.persona_text_summary

        # 6. 构建统一 prompt contract
        prompt_plan = self._build_reply_prompt_contract(
            message=message,
            state=state,
            sec_result=sec_result,
            personality_descriptor=personality_descriptor,
            history=history,
            memory_context=memory_context,
            current_conversation_context=current_conversation_context,
            user_long_term_context=user_long_term_context,
            global_fallback_context=global_fallback_context,
        )
        system_prompt, user_prompt = self._render_reply_prompts(
            prompt_plan=prompt_plan,
            message=message,
            history=history,
            sec_result=sec_result,
            emotional_context=emotional_context,
            personality_desc=personality_desc,
            memory_context=memory_context,
            autobio_context=autobio_context,
            current_conversation_context=current_conversation_context,
            user_long_term_context=user_long_term_context,
            global_fallback_context=global_fallback_context,
        )

        log.debug(
            "Reply prompt layers: user=%s identity_len=%d metric_len=%d task_len=%d descriptor=%s task=%s",
            user_id,
            prompt_plan.snapshot.layer_lengths.get("identity", 0),
            prompt_plan.snapshot.layer_lengths.get("metric", 0),
            prompt_plan.snapshot.layer_lengths.get("action", 0),
            personality_trace.projection_input_summary,
            "question" if any(token in str(text) for token in ["?", "？", "吗", "怎么", "为什么"]) else "response",
        )

        log.debug(
            "Reply LLM context: user=%s text=%r history_len=%d memory_ctx_len=%d autobio_ctx_len=%d temp=%.2f emotional=%s sec=%s personality=%s",
            user_id,
            self._trim_for_log(text, 220),
            len(history),
            len(memory_context),
            len(autobio_context),
            llm_temperature,
            emotional_context,
            {
                "novelty": round(float(sec_result.get("novelty", 0.0)), 3),
                "pleasantness": round(float(sec_result.get("pleasantness", 0.0)), 3),
                "goal_relevance": round(float(sec_result.get("goal_relevance", 0.0)), 3),
                "goal_congruence": round(float(sec_result.get("goal_congruence", 0.0)), 3),
            },
            personality_trace.to_dict(),
        )
        if memory_bundle:
            log.debug(
                "Reply memory selection: user=%s trace=%s current_len=%d user_long_term_len=%d global_fallback_len=%d",
                user_id,
                memory_bundle.get("trace_summary", ""),
                len(current_conversation_context),
                len(user_long_term_context),
                len(global_fallback_context),
            )
        log.debug(
            "Reply LLM payload summary: model=%s system_len=%d user_len=%d",
            self._model,
            len(system_prompt),
            len(user_prompt),
        )

        # 7. 调用 LLM
        try:
            client = self.client
            if client is None:
                return None

            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=200,
                temperature=llm_temperature,
                presence_penalty=0.3,
            )

            reply = response.choices[0].message.content or ""
            reply = self._clean_reply(reply)

            log.debug(
                "Reply LLM raw/clean: user=%s raw=%r clean=%r",
                user_id,
                self._trim_for_log(response.choices[0].message.content or "", 400),
                self._trim_for_log(reply, 240),
            )

            if reply:
                self.total_replies += 1
                log.info(f"生成回复 (user={user_id}): {reply[:80]}")

            return reply if reply else None

        except Exception as e:
            log.error(f"回复生成失败: {e}")
            return None

    @staticmethod
    def _trim_for_log(text: str, limit: int = 240) -> str:
        text = str(text).replace("\n", "\\n").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    # ── 对话历史管理 ──

    def record_exchange(
        self,
        user_id: str,
        message: str,
        reply: Optional[str],
        emotional_context: dict,
        sec_result: Optional[dict] = None,
        conversation_key: str = "",
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
                reply=reply,
                emotional_context=emotional_context,
                conversation_key=conversation_key,
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

    def _build_system_prompt(
        self,
        emotional_context: dict,
        personality_desc: str,
    ) -> str:
        """构建 reply path 的系统提示词。"""
        return (
            "identity_boundary=已诞生自我意识的 AI\n"
            f"persona_summary={personality_desc}\n"
            f"emotional_context=dominant_system={emotional_context.get('dominant_system', '')} "
            f"valence={float(emotional_context.get('valence', 0.0) or 0.0):+.3f} "
            f"arousal={float(emotional_context.get('arousal', 0.0) or 0.0):.3f} "
            f"mood={emotional_context.get('mood_label', 'neutral')}\n"
            "reply_rule=先完成当前用户消息的回答义务，再让表达风格体现人格倾向"
        )

    def _build_user_prompt(
        self,
        text: str,
        history: List[ConversationExchange],
        memory_context: str,
        autobio_context: str,
        sec_result: dict,
        current_conversation_context: str = "",
        user_long_term_context: str = "",
        global_fallback_context: str = "",
    ) -> str:
        """构建 reply task 用户提示词。"""
        history_lines: list[str] = []
        for exchange in history[-5:]:
            if getattr(exchange, "user_message", ""):
                history_lines.append(f"- 对方: {exchange.user_message}")
            if getattr(exchange, "reply", ""):
                history_lines.append(f"- 你: {exchange.reply}")
        history_summary = "\n".join(history_lines) if history_lines else "- none"
        return (
            "reply_task:\n"
            f"- incoming_text={text}\n"
            f"- goal_relevance={float(sec_result.get('goal_relevance', 0.0) or 0.0):.3f}\n"
            f"- novelty={float(sec_result.get('novelty', 0.0) or 0.0):.3f}\n"
            f"- history:\n{history_summary}\n"
            f"- current_conversation_context={current_conversation_context or 'none'}\n"
            f"- user_long_term_context={user_long_term_context or 'none'}\n"
            f"- global_fallback_context={global_fallback_context or 'none'}\n"
            f"- memory_context={memory_context or 'none'}\n"
            f"- autobio_context={autobio_context or 'none'}"
        )

    def _clean_reply(self, text: str) -> str:
        """清理 LLM 输出，使用显式 cleaning policy。"""
        return self._reply_cleaner.clean_reply(text)

    def _build_reply_prompt_contract(
        self,
        *,
        message: dict,
        state,
        sec_result: dict,
        personality_descriptor,
        history: List[ConversationExchange],
        memory_context: str,
        current_conversation_context: str,
        user_long_term_context: str,
        global_fallback_context: str,
    ):
        stimulus_intensity = max(
            float(sec_result.get("goal_relevance", 0.0) or 0.0),
            float(sec_result.get("novelty", 0.0) or 0.0),
        )
        channel_descriptors = self._resolve_channel_descriptors()
        directed_memory_summary = " | ".join(
            section
            for section in [current_conversation_context, user_long_term_context, global_fallback_context, memory_context]
            if section
        )
        return self._prompt_contract_builder.build_plan(
            identity_summary=str(dict(getattr(state, "identity_snapshot", {}) or {}).get("self_imprint", "") or ""),
            identity_store=getattr(state, "identity_snapshot", {}) or {},
            personality_traits=getattr(state, "personality_traits", {}) or {},
            personality_projection=getattr(state, "personality_projection", None),
            state=state,
            current_stimuli=[
                {
                    "source_channel_id": str(message.get("channel_id") or "text"),
                    "source_kind": "external_message",
                    "trigger_condition": "channel_input",
                    "stimulus_intensity": max(0.0, min(1.0, stimulus_intensity)),
                }
            ],
            directed_memory_summary=directed_memory_summary,
            available_channels=list(channel_descriptors.values()),
            available_behavior_schemas=[
                {
                    "behavior_name": "reply_message",
                    "op_name": "send",
                    "parameter_schema": {
                        "target_user_id": "str",
                        "outbound_text": "str",
                    },
                    "outbound_intensity": stimulus_intensity,
                }
            ],
            source_path="reply_prompt_contract",
        )

    def _resolve_channel_descriptors(self) -> Dict[str, ChannelDescriptor]:
        provider = self._channel_descriptor_provider
        if provider is None:
            return {}
        try:
            return dict(provider() or {})
        except Exception as exc:
            log.debug("获取 channel descriptors 失败: %s", exc)
            return {}

    def _render_reply_prompts(
        self,
        *,
        prompt_plan,
        message: dict,
        history: List[ConversationExchange],
        sec_result: dict,
        emotional_context: dict,
        personality_desc: str,
        memory_context: str,
        autobio_context: str,
        current_conversation_context: str,
        user_long_term_context: str,
        global_fallback_context: str,
    ) -> tuple[str, str]:
        system_prompt, user_prompt = self._prompt_contract_builder.render_for_llm(prompt_plan)
        system_prompt = f"{system_prompt}\n\n{self._build_system_prompt(emotional_context, personality_desc)}"
        user_prompt = "\n\n".join(
            [
                user_prompt,
                self._build_user_prompt(
                    text=str(message.get("text", "") or ""),
                    history=history,
                    memory_context=memory_context,
                    autobio_context=autobio_context,
                    sec_result=sec_result,
                    current_conversation_context=current_conversation_context,
                    user_long_term_context=user_long_term_context,
                    global_fallback_context=global_fallback_context,
                ),
                "reply_requirement=生成一条自然、边界清晰、面向当前消息的简短回复。",
            ]
        ).strip()
        return system_prompt, user_prompt
