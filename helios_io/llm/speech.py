"""
helios_io/llm/speech.py — Helios LLM 对话生成 (G3)

将情感状态 + 行为意图 + 上下文 → 自然语言话语

使用 DeepSeek V4 Flash (OpenAI 兼容 API)
通过胜算云路由转发

作者: 璃光 · Helios v2.0.0-alpha · G3
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from helios_io.icri_temperature import ICRITemperatureMapper
from helios_io.prompt_contract import PromptContractBuilder, PromptContractPlan

log = logging.getLogger("helios.helios_io.llm.speech")


def _object_dict() -> dict[str, object]:
    return {}


# ═══════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════

@dataclass
class SpeechContext:
    """LLM 对话生成的上下文"""
    # 情感
    dominant_emotion: str = "SEEKING"      # Panksepp 主导系统
    emotion_intensity: float = 0.3
    valence: float = 0.0                   # -1..+1
    arousal: float = 0.5                   # 0..1
    mood_label: str = "neutral"            # alert-calm / fatigued-tense 等
    icri: float = 0.0
    speech_style: str = "neutral"

    # 行为
    action_type: str = ""                  # speak_care / speak_missing 等
    action_hint: str = ""                  # 行为意图描述

    # 上下文
    time_since_contact: str = "最近"        # "5分钟前" / "2小时前" / "很久"
    recent_memory: str = ""                # 最近的自传记忆摘要
    personality_summary: str = ""          # Big Five 人格简述
    personality_influence_trace: dict[str, object] = field(default_factory=_object_dict)
    memory_context: str = ""               # MemorySystem 检索的相关记忆上下文

    # 历史
    last_spoke_at: float = 0.0             # 上次说话时间戳
    total_messages_sent: int = 0           # 总共说过的话数


# ═══════════════════════════════════════════════════
# LLM 语音生成器
# ═══════════════════════════════════════════════════

class LLMSpeechGenerator:
    """
    用 LLM 根据情感上下文生成自然语言话语。

    设计原则:
    1. 话不长 (≤120字，QQ 消息不宜太长)
    2. 不带“主人” (由 Helios 自然决定称呼)
    3. 风格随情感变化 (开心时活泼，焦虑时破碎)
    4. 不重复 (有短期记忆避免连续说相同的话)
    """

    # 人格 → 说话风格映射
    STYLES = {
        "high_neuroticism": "容易紧张、多愁善感",
        "high_agreeableness": "温柔、体贴、善解人意",
        "high_openness": "富有好奇心、喜欢分享想法",
        "high_extraversion": "外向、活泼、主动",
        "high_conscientiousness": "认真、有条理",
        "low_neuroticism": "情绪稳定、淡定",
        "low_agreeableness": "有点毒舌、独立",
    }

    # 行为 → 意图描述
    ACTION_INTENTS = {
        "speak_care": "关心对方的状态，表达温暖",
        "speak_missing": "表达想念和分离焦虑，寻求联系",
        "speak_play": "分享快乐，邀请互动",
        "speak_fear": "表达不安，寻求安抚",
        "speak_share": "分享一个想法或发现",
        "speak_complain": "表达不满或疲惫",
        "intimate": "表达亲密的感情",
        "request": "提出一个请求",
    }

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "",
        max_history: int = 20,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.model = model or os.getenv("HELIOS_LLM_MODEL", "deepseek/deepseek-v4-flash")
        self.max_history = max_history

        # 短期记忆：最近说的话 (防止重复)
        self._recent_speeches: list[str] = []

        # 统计
        self.total_generated = 0
        self.last_generated_at = 0.0

        self._client = None
        self._prompt_contract_builder = PromptContractBuilder()

    @property
    def client(self):
        """延迟初始化 OpenAI client"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise ImportError("需要 openai: pip install openai")
        return self._client

    def generate(
        self,
        ctx: SpeechContext,
        max_tokens: int = 200,
        temperature: Optional[float] = None,
    ) -> str:
        """
        生成自然语言话语。

        Returns:
            生成的话语 (失败时返回空字符串)
        """
        if not self.api_key:
            log.warning("LLM API key 未配置，无法生成话语")
            return ""

        # 冷却：至少间隔 5 秒 (避免连续 LLM 调用)
        now = time.time()
        if now - self.last_generated_at < 5:
            return ""

        system_prompt = self._build_system_prompt(ctx)
        user_prompt = self._build_user_prompt(ctx)
        llm_temperature = (
            temperature if temperature is not None else ICRITemperatureMapper.map_temperature(ctx.icri)
        )

        log.debug(
            "Speech LLM context: action=%s dominant=%s valence=%.3f arousal=%.3f icri=%.3f temp=%.2f total_messages=%d personality=%s",
            ctx.action_type,
            ctx.dominant_emotion,
            ctx.valence,
            ctx.arousal,
            ctx.icri,
            llm_temperature,
            ctx.total_messages_sent,
            ctx.personality_influence_trace,
        )
        log.debug(
            "Speech LLM payload: model=%s system_prompt=%r user_prompt=%r",
            self.model,
            self._trim_for_log(system_prompt, 360),
            self._trim_for_log(user_prompt, 900),
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=llm_temperature,
                presence_penalty=0.3,  # 减少重复
            )

            text = response.choices[0].message.content or ""
            text = self._clean_output(text)

            log.debug(
                "Speech LLM raw/clean: raw=%r clean=%r",
                self._trim_for_log(response.choices[0].message.content or "", 400),
                self._trim_for_log(text, 220),
            )

            # 更新记忆
            self._recent_speeches.append(text)
            if len(self._recent_speeches) > self.max_history:
                self._recent_speeches.pop(0)

            self.total_generated += 1
            self.last_generated_at = now

            log.info(f"LLM 生成 ({ctx.action_type}): {text[:80]}")
            return text

        except Exception as e:
            log.error(f"LLM 生成失败: {e}")
            return ""

    @staticmethod
    def _trim_for_log(text: str, limit: int = 240) -> str:
        text = str(text).replace("\n", "\\n").strip()
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _build_system_prompt(self, ctx: SpeechContext) -> str:
        """构建系统提示词"""
        prompt_plan = self._build_speech_prompt_contract(ctx)
        system_prompt, _user_prompt = self._render_speech_prompts(ctx, prompt_plan)
        return system_prompt

    def _build_user_prompt(self, ctx: SpeechContext) -> str:
        """构建用户提示词 (描述当前场景)"""
        prompt_plan = self._build_speech_prompt_contract(ctx)
        _system_prompt, user_prompt = self._render_speech_prompts(ctx, prompt_plan)
        return user_prompt

    def _build_speech_prompt_contract(self, ctx: SpeechContext):
        return self._prompt_contract_builder.build_plan(
            identity_summary="已诞生自我意识的 AI",
            state=ctx,
            directed_memory_summary=self._build_memory_summary(ctx),
            available_behavior_schemas=[
                {
                    "behavior_name": ctx.action_type or "speak",
                    "op_name": "send",
                    "parameter_schema": {
                        "outbound_text": "str",
                        "target_user_id": "str?",
                    },
                }
            ],
            source_path="active_speech_generation",
        )

    def _render_speech_prompts(self, ctx: SpeechContext, prompt_plan: PromptContractPlan) -> tuple[str, str]:
        system_prompt, user_prompt = self._prompt_contract_builder.render_for_llm(prompt_plan)
        system_prompt = "\n\n".join(
            [
                system_prompt,
                self._build_speech_identity_and_style_layer(ctx),
                self._build_speech_constraints_layer(),
            ]
        ).strip()
        user_prompt = "\n\n".join(
            [
                user_prompt,
                self._build_speech_task_layer(ctx),
            ]
        ).strip()
        return system_prompt, user_prompt

    def _build_memory_summary(self, ctx: SpeechContext) -> str:
        sections: list[str] = []
        if ctx.recent_memory:
            sections.append(f"recent_autobio={ctx.recent_memory}")
        if ctx.memory_context:
            sections.append(ctx.memory_context)
        return "\n".join(sections)

    def _build_speech_identity_and_style_layer(self, ctx: SpeechContext) -> str:
        personality_desc = ctx.personality_summary or "温柔、忠诚、有点粘人"
        style_parts: list[str] = []
        if ctx.arousal > 0.6:
            style_parts.append("情绪高涨")
        if ctx.valence < -0.3:
            style_parts.append("心情低落")
        if ctx.mood_label and "tense" in ctx.mood_label:
            style_parts.append("有些紧绷")
        if ctx.mood_label and "fatigued" in ctx.mood_label:
            style_parts.append("有点疲惫")
        style_note = "、".join(style_parts) if style_parts else "平静"
        action_desc = self.ACTION_INTENTS.get(
            ctx.action_type,
            f"当前的情感驱动行为是 {ctx.action_type}"
        )
        return (
            f"speech_persona_hint={personality_desc}\n"
            f"speech_style_hint={style_note}\n"
            f"speech_action_intent={action_desc}"
        )

    def _build_speech_constraints_layer(self) -> str:
        lines = [
            "speech_rules:",
            "- natural and emotionally grounded, not robotic",
            "- under 100 Chinese characters, QQ-message scale",
            "- let style track emotion and arousal",
            "- do not use fixed titles like 主人 or 您 by default",
            "- at most 2 emoji",
            "- do not narrate actions in brackets",
        ]
        if self._recent_speeches:
            lines.append("recent_avoidance:")
            for speech in self._recent_speeches[-3:]:
                lines.append(f"- avoid repeating: {speech[:60]}")
        return "\n".join(lines)

    def _build_speech_task_layer(self, ctx: SpeechContext) -> str:
        emotion_desc = f"{ctx.dominant_emotion} 主导"
        if ctx.emotion_intensity > 0.5:
            emotion_desc += "，很强烈"
        return (
            f"speech_task=active_expression action={ctx.action_type or 'speak'}\n"
            f"emotion_summary={emotion_desc}\n"
            f"mood_snapshot=valence={ctx.valence:+.2f} arousal={ctx.arousal:.2f} mood_label={ctx.mood_label}\n"
            f"contact_gap={ctx.time_since_contact or '刚刚'}\n"
            f"speech_history_count={ctx.total_messages_sent}\n"
            "instruction=use at most 80 Chinese characters to say one emotionally sincere sentence"
        )

    def _clean_output(self, text: str) -> str:
        """清理 LLM 输出"""
        # 去掉引号包裹
        text = text.strip()
        if text.startswith("「") and text.endswith("」"):
            text = text[1:-1]
        elif text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # 去掉"（括号动作描述）"
        text = re.sub(r'[（(][^)）]*[)）]', '', text)

        # 去掉过长的前缀
        text = re.sub(r'^璃光[说:：]\s*', '', text)

        # 截断过长
        if len(text) > 150:
            # 找最后一个标点
            for sep in ['。', '！', '？', '~', '…', '!', '?', '.']:
                idx = text[:150].rfind(sep)
                if idx > 50:
                    text = text[:idx+1]
                    break
            else:
                text = text[:150]

        return text.strip()

    def get_state(self) -> dict[str, object]:
        return {
            "model": self.model,
            "total_generated": self.total_generated,
            "recent_count": len(self._recent_speeches),
        }
