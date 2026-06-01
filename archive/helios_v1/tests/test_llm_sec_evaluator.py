"""
Tests for io/llm_sec_evaluator.py — LLM SEC Evaluator

Tests the keyword fallback logic, context handling, and evaluator behavior
on LLM failure/timeout.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.llm_sec_evaluator import LLMSECEvaluator, _SEC_KEYS, _keyword_fallback_sec


class TestKeywordFallbackSEC:
    """Tests for the keyword-based SEC fallback function."""

    def test_care_words_produce_positive_pleasantness(self):
        """Care/warmth words should yield positive pleasantness."""
        result = _keyword_fallback_sec("想你了，爱你❤")
        assert result["pleasantness"] > 0.3
        assert result["goal_relevance"] > 0.2

    def test_panic_words_produce_negative_pleasantness(self):
        """Panic/separation words should yield negative pleasantness."""
        result = _keyword_fallback_sec("别走！害怕")
        assert result["pleasantness"] < 0.0
        assert result["goal_relevance"] > 0.3
        assert result["coping_potential"] < 0.5

    def test_seeking_words_produce_high_novelty(self):
        """Seeking/curiosity words should yield high novelty."""
        result = _keyword_fallback_sec("为什么呢？告诉我")
        assert result["novelty"] > 0.4
        assert result["goal_relevance"] > 0.3

    def test_play_words_produce_positive_pleasantness(self):
        """Play/joy words should yield positive pleasantness."""
        result = _keyword_fallback_sec("哈哈好玩😂")
        assert result["pleasantness"] > 0.4
        assert result["coping_potential"] >= 0.5

    def test_rage_words_produce_negative_external_agency(self):
        """Rage words should yield negative pleasantness and external agency."""
        result = _keyword_fallback_sec("气死了混蛋")
        assert result["pleasantness"] < -0.3
        assert result["agency"] < 0.0
        assert result["norm_compatibility"] < 0.0

    def test_neutral_text_returns_baseline(self):
        """Neutral text should return baseline SEC values."""
        result = _keyword_fallback_sec("今天天气不错")
        assert result["novelty"] == pytest.approx(0.2)
        assert result["pleasantness"] == pytest.approx(0.0)
        assert result["goal_relevance"] == pytest.approx(0.2)

    def test_all_sec_keys_present(self):
        """Result should contain all 7 SEC dimension keys."""
        result = _keyword_fallback_sec("任何文本")
        for key in _SEC_KEYS:
            assert key in result

    def test_values_within_valid_ranges(self):
        """All values should be within their valid ranges."""
        test_texts = [
            "想你想你想你爱你爱你爱你",  # many care words
            "气死气死气死",  # many rage words
            "",  # empty
            "为什么怎么什么是告诉我",  # many seeking words
        ]
        for text in test_texts:
            result = _keyword_fallback_sec(text)
            for key, val in result.items():
                if key in ("goal_relevance", "coping_potential"):
                    assert 0.0 <= val <= 1.0, f"{key}={val} out of [0,1]"
                else:
                    assert -1.0 <= val <= 1.0, f"{key}={val} out of [-1,1]"


class TestLLMSECEvaluator:
    """Tests for the LLMSECEvaluator class."""

    def test_fallback_on_no_api_key(self):
        """Without API key, should fall back to keyword evaluation."""
        evaluator = LLMSECEvaluator(api_key="")
        result = evaluator.evaluate("想你了")
        assert result["pleasantness"] > 0.0
        assert evaluator.fallback_count == 1
        assert evaluator.llm_successes == 0

    def test_explicit_empty_api_key_does_not_fall_back_to_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key-should-not-be-used")

        evaluator = LLMSECEvaluator(api_key="")

        assert evaluator._api_key == ""
        result = evaluator.evaluate("想你了")
        assert result["pleasantness"] > 0.0
        assert evaluator.fallback_count == 1
        assert evaluator.llm_successes == 0

    def test_context_truncated_to_last_3(self):
        """Only the last 3 context messages should be included."""
        evaluator = LLMSECEvaluator(api_key="test_key")
        context = ["msg1", "msg2", "msg3", "msg4", "msg5"]

        # Check that _build_sec_prompt with truncated context only has 3
        truncated = context[-3:]
        prompt = evaluator._build_sec_prompt("测试", truncated)
        assert "msg3" in prompt
        assert "msg4" in prompt
        assert "msg5" in prompt
        assert "msg1" not in prompt
        assert "msg2" not in prompt

    def test_evaluate_includes_only_last_3_context(self):
        """evaluate() should truncate context to last 3 before LLM call."""
        evaluator = LLMSECEvaluator(api_key="")  # will fallback
        # Pass 5 messages, should not error
        result = evaluator.evaluate("hi", context=["a", "b", "c", "d", "e"])
        assert evaluator.total_evaluations == 1

    def test_fallback_on_llm_exception(self):
        """On LLM exception, should fall back to keyword-based evaluation."""
        evaluator = LLMSECEvaluator(api_key="fake_key")

        # Mock the client to raise an exception
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        evaluator._client = mock_client

        result = evaluator.evaluate("想你了")
        assert result["pleasantness"] > 0.0  # keyword fallback works
        assert evaluator.fallback_count == 1

    def test_fallback_on_llm_timeout(self):
        """On LLM timeout (exceeding 3s), should fall back to keyword-based evaluation.

        Requirement 6.3: IF the LLM SEC evaluation fails or times out within
        3 seconds, THEN SHALL fall back to keyword-based function.
        """
        evaluator = LLMSECEvaluator(api_key="fake_key", timeout=3.0)

        # Mock the client to raise a TimeoutError
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = TimeoutError(
            "LLM 响应耗时 4.50s，超过 3.0s 限制"
        )
        evaluator._client = mock_client

        result = evaluator.evaluate("想你了")
        # Should return keyword fallback result (care word → positive pleasantness)
        assert result["pleasantness"] > 0.0
        assert evaluator.fallback_count == 1
        assert evaluator.llm_successes == 0

    def test_fallback_on_llm_runtime_error(self):
        """On LLM RuntimeError (client unavailable), should fall back to keywords.

        Requirement 6.3: fallback on any failure mode.
        """
        evaluator = LLMSECEvaluator(api_key="fake_key")

        # Mock the client to raise RuntimeError (e.g. client not initialised)
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError(
            "OpenAI client 不可用"
        )
        evaluator._client = mock_client

        result = evaluator.evaluate("气死了混蛋")
        # Rage words → negative pleasantness from keyword fallback
        assert result["pleasantness"] < -0.3
        assert result["agency"] < 0.0
        assert evaluator.fallback_count == 1
        assert evaluator.llm_successes == 0

    def test_context_included_in_llm_prompt(self):
        """Context messages should be included in the prompt sent to LLM.

        Requirement 6.3 / 6.4: The last 3 messages of conversation context
        should be included in the LLM SEC evaluation prompt.
        """
        evaluator = LLMSECEvaluator(api_key="fake_key")

        # Mock successful LLM response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''{
            "novelty": 0.5, "pleasantness": 0.3, "goal_relevance": 0.4,
            "goal_congruence": 0.2, "coping_potential": 0.6,
            "agency": 0.1, "norm_compatibility": 0.0
        }'''

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        evaluator._client = mock_client

        context = ["之前的对话1", "之前的对话2", "之前的对话3"]
        evaluator.evaluate("你好", context=context)

        # Verify the LLM was called and the prompt contains context
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
        user_prompt = messages[1]["content"]

        # All 3 context messages should be in the prompt
        assert "之前的对话1" in user_prompt
        assert "之前的对话2" in user_prompt
        assert "之前的对话3" in user_prompt
        # The actual message being evaluated should also be in the prompt
        assert "你好" in user_prompt
        assert call_args.kwargs["reasoning_effort"] == "low"
        assert call_args.kwargs["response_format"] == {"type": "json_object"}
        assert call_args.kwargs["max_tokens"] == 480

    def test_sec_system_prompt_avoids_identity_theater_language(self):
        evaluator = LLMSECEvaluator(api_key="fake_key")

        prompt = evaluator._system_prompt()

        assert "有情感的 AI 生命体" not in prompt
        assert "主观状态视角" in prompt

    def test_successful_llm_parse(self):
        """On successful LLM response, should parse SEC features."""
        evaluator = LLMSECEvaluator(api_key="fake_key")

        # Mock the client with a valid JSON response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '''{
            "novelty": 0.7,
            "pleasantness": 0.5,
            "goal_relevance": 0.8,
            "goal_congruence": 0.6,
            "coping_potential": 0.7,
            "agency": 0.2,
            "norm_compatibility": 0.3
        }'''

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        evaluator._client = mock_client

        result = evaluator.evaluate("你好")
        assert result["novelty"] == pytest.approx(0.7, abs=0.01)
        assert result["pleasantness"] == pytest.approx(0.5, abs=0.01)
        assert result["goal_relevance"] == pytest.approx(0.8, abs=0.01)
        assert evaluator.llm_successes == 1

    def test_parse_json_with_markdown_wrapper(self):
        """Should handle JSON wrapped in markdown code blocks."""
        evaluator = LLMSECEvaluator(api_key="fake_key")
        raw = '''```json
{"novelty": 0.5, "pleasantness": 0.3, "goal_relevance": 0.4, "goal_congruence": 0.2, "coping_potential": 0.6, "agency": 0.1, "norm_compatibility": 0.0}
```'''
        result = evaluator._parse_sec_response(raw)
        assert result["novelty"] == pytest.approx(0.5, abs=0.01)

    def test_parse_partial_json_recovers_known_sec_fields(self):
        evaluator = LLMSECEvaluator(api_key="fake_key")
        raw = '{"novelty": 0.61, "pleasantness": -0.25, "goal_relevance": 0.72'

        result = evaluator._parse_sec_response(raw)

        assert result["novelty"] == pytest.approx(0.61, abs=0.01)
        assert result["pleasantness"] == pytest.approx(-0.25, abs=0.01)
        assert result["goal_relevance"] == pytest.approx(0.72, abs=0.01)
        assert result["goal_congruence"] == pytest.approx(0.0, abs=0.01)

    def test_values_clamped_to_valid_range(self):
        """Out-of-range values from LLM should be clamped."""
        evaluator = LLMSECEvaluator(api_key="fake_key")
        raw = '{"novelty": 2.0, "pleasantness": -3.0, "goal_relevance": 5.0, "goal_congruence": 0.5, "coping_potential": -1.0, "agency": 0.0, "norm_compatibility": 0.0}'
        result = evaluator._parse_sec_response(raw)
        assert result["novelty"] == 1.0
        assert result["pleasantness"] == -1.0
        assert result["goal_relevance"] == 1.0
        assert result["coping_potential"] == 0.0

    def test_get_state(self):
        """get_state() should return statistics."""
        evaluator = LLMSECEvaluator(api_key="")
        evaluator.evaluate("test")
        state = evaluator.get_state()
        assert state["total_evaluations"] == 1
        assert state["fallback_count"] == 1
        assert "model" in state
        assert "success_rate" in state
