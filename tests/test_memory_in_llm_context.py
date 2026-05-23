"""
tests/test_memory_in_llm_context.py — Tests for memory context inclusion in LLM pipelines.

Validates Requirement 13.3: When the LLM is invoked for speech generation or reply
generation, the Helios SHALL retrieve relevant memories from Memory_System and include
them as context.
"""

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
        mock_memory.get_llm_context.return_value = "[最近在想]\n  · 我很开心"
        pipeline = ResponsePipeline(memory_system=mock_memory, api_key="test-key")

        state = MockState(valence=0.5, arousal=0.4)

        # Test via internal method
        prompt = pipeline._build_user_prompt(
            text="你好",
            history=[],
            memory_context="[最近在想]\n  · 我很开心",
            autobio_context="",
            sec_result={"goal_relevance": 0.5},
        )
        assert "我很开心" in prompt
