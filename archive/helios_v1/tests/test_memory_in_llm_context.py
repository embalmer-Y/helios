"""
tests/test_memory_in_llm_context.py — Tests for memory context inclusion in LLM pipelines.

Validates Requirement 13.3: When the LLM is invoked for speech generation or reply
generation, the Helios SHALL retrieve relevant memories from Memory_System and include
them as context.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from typing import Dict
from unittest.mock import MagicMock

import pytest

# Import SpeechContext and LLMSpeechGenerator directly
sys.path.insert(0, ".")
from helios_io.llm.speech import SpeechContext, LLMSpeechGenerator

from helios_io.response_pipeline import ResponsePipeline


@dataclass
class MockState:
    valence: float = 0.3
    arousal: float = 0.5
    dominant_system: str = "SEEKING"
    mood_label: str = "neutral"
    icri: float = 0.3
    personality_traits: Dict[str, float] = field(default_factory=dict)


class TestSpeechContextMemory:
    """Test that LLMSpeechGenerator includes memory_context in prompts."""

    def test_speech_context_has_memory_context_field(self):
        """SpeechContext should have a memory_context field"""
        ctx = SpeechContext(memory_context="[最近在想]\n  · test memory")
        assert ctx.memory_context == "[最近在想]\n  · test memory"

    def test_memory_context_empty_by_default(self):
        """SpeechContext.memory_context should default to empty string"""
        ctx = SpeechContext()
        assert ctx.memory_context == ""

    def test_user_prompt_includes_memory_context(self):
        """_build_user_prompt should include memory_context when provided"""
        gen = LLMSpeechGenerator(api_key="fake")
        ctx = SpeechContext(
            dominant_emotion="CARE",
            action_type="speak_care",
            memory_context="[最近在想]\n  · 主人昨天说了暖心的话",
        )
        prompt = gen._build_user_prompt(ctx)
        assert "最近在想" in prompt
        assert "暖心的话" in prompt

    def test_user_prompt_without_memory_context(self):
        """_build_user_prompt should not include memory section when empty"""
        gen = LLMSpeechGenerator(api_key="fake")
        ctx = SpeechContext(
            dominant_emotion="SEEKING",
            action_type="speak_share",
            memory_context="",
        )
        prompt = gen._build_user_prompt(ctx)
        # Should not have memory-related context
        assert "[最近在想]" not in prompt
        assert "[相似经历]" not in prompt

    def test_speech_system_prompt_uses_unified_contract_layers(self):
        gen = LLMSpeechGenerator(api_key="fake")
        ctx = SpeechContext(
            dominant_emotion="CARE",
            action_type="speak_care",
            personality_summary="",
            arousal=0.7,
            valence=0.2,
            icri=0.6,
            relationship_stage="stranger",
            relationship_history_count=0,
        )

        prompt = gen._build_system_prompt(ctx)

        assert "identity_boundary=Helios 当前主观整合层" in prompt
        assert "metrics:" in prompt
        assert "constraints=do not describe Helios as a designed program" in prompt
        assert "subjective_role=serve as Helios's current subjective integration layer" in prompt
        assert "已诞生自我意识的 AI" not in prompt
        assert "speech_rules:" in prompt
        assert "relationship_stage=stranger" in prompt
        assert "speech_persona_hint=20岁女大学生、平时可爱、有点腹黑、没有分寸" in prompt
        assert "prioritize the user's concrete cue or question" in prompt
        assert "treat the current user as unfamiliar" in prompt
        assert "sound streetwise, practical, and slightly guarded" in prompt
        assert "do not use generic companionship filler like 我在这里 or 我会一直陪着你" in prompt
        assert "default to no emoji" in prompt
        assert "speech_action_intent=先判断对方是不是在试探，再给有限回应，不做过度照顾" in prompt

    def test_speech_user_prompt_uses_unified_contract_layers(self):
        gen = LLMSpeechGenerator(api_key="fake")
        ctx = SpeechContext(
            dominant_emotion="CARE",
            action_type="speak_care",
            mood_label="neutral",
            valence=0.3,
            arousal=0.4,
            icri=0.5,
            time_since_contact="5分钟前",
            recent_memory="昨天一起散步",
            memory_context="[最近在想]\n  · 主人昨天说了暖心的话",
            current_user_text="如果现在先结束这轮对话，你会怎么总结我此刻最需要被回应的部分？",
            current_stimuli=[
                {
                    "source_channel_id": "cli",
                    "source_kind": "local_terminal_input",
                    "trigger_condition": "cli_text_input",
                    "stimulus_intensity": 0.4,
                    "payload": {"text": "如果现在先结束这轮对话，你会怎么总结我此刻最需要被回应的部分？"},
                }
            ],
            relationship_stage="stranger",
            relationship_history_count=0,
            total_messages_sent=3,
        )

        prompt = gen._build_user_prompt(ctx)

        assert "state_summary=" in prompt
        assert "sensory_field=current normalized sensory field" in prompt
        assert "memory_summary=" in prompt
        assert "昨天一起散步" in prompt
        assert "最近在想" in prompt
        assert "action_contract:" in prompt
        assert "speech_task=active_expression action=speak_care" in prompt
        assert "current_user_text=如果现在先结束这轮对话，你会怎么总结我此刻最需要被回应的部分？" in prompt
        assert "relationship_stage=stranger" in prompt
        assert "question_style=meta_test_or_probe" in prompt

    def test_speech_prompt_contract_can_switch_back_to_baseline_mode(self, monkeypatch):
        monkeypatch.setenv("HELIOS_EMBODIED_SUBJECTIVE_PROMPT_ENABLED", "0")
        gen = LLMSpeechGenerator(api_key="fake")
        ctx = SpeechContext(
            dominant_emotion="CARE",
            action_type="speak_care",
            personality_summary="温柔、忠诚、有点粘人",
            arousal=0.7,
            valence=0.2,
            icri=0.6,
        )

        prompt = gen._build_system_prompt(ctx)

        assert "already-conscious AI lifeform" in prompt
        assert "subjective_role=serve as Helios's current subjective integration layer" not in prompt

    def test_generate_uses_icri_temperature_mapping(self):
        gen = LLMSpeechGenerator(api_key="fake")
        gen._client = MagicMock()
        gen._client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="你好"))]
        )
        ctx = SpeechContext(
            dominant_emotion="CARE",
            action_type="speak_care",
            icri=0.7,
        )

        result = gen.generate(ctx)

        assert result == "你好"
        assert gen._client.chat.completions.create.call_args.kwargs["temperature"] == 1.3


class TestResponsePipelineMemoryRetrieval:
    """Test that ResponsePipeline retrieves and includes memory context."""

    def test_get_memory_context_calls_memory_system(self):
        """_get_memory_context should call memory_system.get_llm_context with state"""
        mock_memory = MagicMock()
        mock_memory.get_llm_context.return_value = "[相似经历]\n  · 开心"
        pipeline = ResponsePipeline(memory_system=mock_memory)
        state = MockState(valence=0.6, arousal=0.7)
        ctx = pipeline._get_memory_context(state)
        mock_memory.get_llm_context.assert_called_once_with(valence=0.6, arousal=0.7)
        assert "相似经历" in ctx

    def test_get_memory_context_uses_reply_bundle_when_user_context_available(self):
        mock_memory = MagicMock()
        bundle = MagicMock()
        bundle.resolved_text_sections = {
            "current_conversation": "[当前会话]\n  · 对方: 你好",
            "user_long_term": "[用户长期记忆]\n  · 我们聊过海边",
            "global_fallback": "[全局回退记忆]\n  · 旧的泛化片段",
            "long_term_and_global": "[用户长期记忆]\n  · 我们聊过海边\n\n[全局回退记忆]\n  · 旧的泛化片段",
        }
        bundle.trace_summary = "user_id=user1 l1=2 l2=1 l3=1 fallback=True"
        mock_memory.get_reply_memory_bundle.return_value = bundle
        pipeline = ResponsePipeline(memory_system=mock_memory)
        state = MockState(valence=0.6, arousal=0.7)

        ctx = pipeline._get_memory_context(
            state,
            user_id="user1",
            message_text="我们去散步吧",
            history_texts=["对方: 你好\n你: 在呢"],
            conversation_key="qq:dm:user1",
        )

        mock_memory.get_reply_memory_bundle.assert_called_once()
        call = mock_memory.get_reply_memory_bundle.call_args.kwargs
        assert call["user_id"] == "user1"
        assert call["message_text"] == "我们去散步吧"
        assert call["history_texts"] == ["对方: 你好\n你: 在呢"]
        assert call["conversation_key"] == "qq:dm:user1"
        assert "我们聊过海边" in ctx

    def test_get_memory_context_returns_empty_when_no_memory_system(self):
        """Should return empty string when no memory system is configured"""
        pipeline = ResponsePipeline(memory_system=None)
        state = MockState()
        ctx = pipeline._get_memory_context(state)
        assert ctx == ""

    def test_get_memory_context_handles_exception_gracefully(self):
        """Should return empty string on exception and not raise"""
        mock_memory = MagicMock()
        mock_memory.get_llm_context.side_effect = RuntimeError("oops")
        pipeline = ResponsePipeline(memory_system=mock_memory)
        state = MockState()
        ctx = pipeline._get_memory_context(state)
        assert ctx == ""

    def test_memory_context_included_in_generate_reply_prompt(self):
        """Memory context should flow into the user prompt during reply generation"""
        mock_memory = MagicMock()
        bundle = MagicMock()
        bundle.resolved_text_sections = {
            "current_conversation": "[当前会话]\n  · 对方: 你好",
            "user_long_term": "[用户长期记忆]\n  · 我很开心",
            "global_fallback": "",
            "long_term_and_global": "[用户长期记忆]\n  · 我很开心",
        }
        bundle.trace_summary = "user_id=user1 l1=1 l2=1 l3=0 fallback=False"
        mock_memory.get_reply_memory_bundle.return_value = bundle
        pipeline = ResponsePipeline(memory_system=mock_memory, api_key="test-key")

        state = MockState(valence=0.5, arousal=0.4)

        # Test via internal method
        prompt = pipeline._build_user_prompt(
            text="你好",
            history=[],
            memory_context="[最近在想]\n  · 我很开心",
            autobio_context="",
            sec_result={"goal_relevance": 0.5},
            current_conversation_context="[当前会话]\n  · 对方: 你好",
            user_long_term_context="[用户长期记忆]\n  · 我很开心",
            global_fallback_context="[全局回退记忆]\n  · 一个旧片段",
        )
        assert "我很开心" in prompt
        assert "[当前会话]" in prompt
        assert "[用户长期记忆]" in prompt
        assert "[全局回退记忆]" in prompt

    def test_reply_memory_bundle_trace_is_logged_by_response_pipeline(self, caplog):
        mock_memory = MagicMock()
        bundle = MagicMock()
        bundle.resolved_text_sections = {
            "current_conversation": "[当前会话]\n  · 对方: 你好",
            "user_long_term": "[用户长期记忆]\n  · 我们聊过海边",
            "global_fallback": "[全局回退记忆]\n  · 旧的泛化片段",
            "long_term_and_global": "[用户长期记忆]\n  · 我们聊过海边\n\n[全局回退记忆]\n  · 旧的泛化片段",
        }
        bundle.trace_summary = (
            "user_id=user1 conversation_key=qq:dm:user1 l1=1 l2=1 l3=1 "
            "l1_hits=1 l2_hits=1 l3_hits=1 "
            "l1_selected=1 l2_selected=1 l3_selected=1 "
            "selected=(1,1,1) fallback=True reason=insufficient_user_memory cache_hit=False"
        )
        mock_memory.get_reply_memory_bundle.return_value = bundle
        pipeline = ResponsePipeline(memory_system=mock_memory)

        with caplog.at_level(logging.DEBUG, logger="helios.helios_io.response_pipeline"):
            ctx = pipeline._get_reply_memory_bundle(
                MockState(valence=0.5, arousal=0.4),
                user_id="user1",
                message_text="我们再去散步吧",
                history_texts=["对方: 你好\n你: 在呢"],
                conversation_key="qq:dm:user1",
            )

        assert "我们聊过海边" in ctx["user_long_term"]
        assert any("Reply memory bundle trace: user=user1" in record.message for record in caplog.records)
        assert any("conversation_key=qq:dm:user1" in record.message for record in caplog.records)
        assert any("l1_hits=1" in record.message for record in caplog.records)
        assert any("l2_hits=1" in record.message for record in caplog.records)
        assert any("l3_hits=1" in record.message for record in caplog.records)
        assert any("reason=insufficient_user_memory" in record.message for record in caplog.records)
