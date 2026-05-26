"""
tests/test_response_pipeline.py — Unit tests for ResponsePipeline

Tests should_reply(), record_exchange(), and generate_reply() logic.

Requirements: 7.1, 7.2, 7.3, 7.5
"""

import sys
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.conversation_history import ConversationExchange
from helios_io.prompt_contract import PromptContractBuilder
from helios_io.reply_prompt_builder import ReplyPromptBuilder
from helios_io.response_pipeline import ResponsePipeline
from personality_projection import build_personality_projection


@dataclass
class FakeAutobioMoment:
    narrative: str = ""
    phi: float = 0.4
    significance: float = 0.5


# ── Mock HeliosState ──

@dataclass
class MockHeliosState:
    """Minimal mock of HeliosState for testing"""
    tick: int = 1
    timestamp: float = 0.0
    panksepp: Dict[str, float] = field(default_factory=dict)
    valence: float = 0.3
    arousal: float = 0.5
    dominant_system: str = "CARE"
    icri: float = 0.4
    phi: float = 0.4
    mood_label: str = "content"
    personality_traits: Dict[str, float] = field(default_factory=lambda: {
        "agreeableness": 1.3,
        "openness": 1.1,
    })
    personality_projection: Optional[object] = None


# ═══════════════════════════════════════════════════
# should_reply() tests
# ═══════════════════════════════════════════════════

class TestShouldReply:
    """Test the reply decision threshold logic."""

    def setup_method(self):
        self.pipeline = ResponsePipeline()

    def test_reply_when_sum_exceeds_threshold(self):
        """Should return True when goal_relevance + novelty > 0.3"""
        msg = {"text": "你好", "user_id": "user1"}
        sec = {"goal_relevance": 0.3, "novelty": 0.2}  # sum = 0.5 > 0.3
        assert self.pipeline.should_reply(msg, sec) is True

    def test_no_reply_when_sum_at_threshold(self):
        """Should return False when goal_relevance + novelty == 0.3 exactly"""
        msg = {"text": "嗯", "user_id": "user1"}
        sec = {"goal_relevance": 0.15, "novelty": 0.15}  # sum = 0.3 == 0.3
        assert self.pipeline.should_reply(msg, sec) is False

    def test_no_reply_when_sum_below_threshold(self):
        """Should return False when goal_relevance + novelty < 0.3"""
        msg = {"text": "...", "user_id": "user1"}
        sec = {"goal_relevance": 0.1, "novelty": 0.1}  # sum = 0.2 < 0.3
        assert self.pipeline.should_reply(msg, sec) is False

    def test_reply_with_high_goal_relevance_only(self):
        """Goal relevance alone can trigger reply if > 0.3"""
        msg = {"text": "帮我一下", "user_id": "user1"}
        sec = {"goal_relevance": 0.5, "novelty": 0.0}  # sum = 0.5 > 0.3
        assert self.pipeline.should_reply(msg, sec) is True

    def test_reply_with_high_novelty_only(self):
        """Novelty alone can trigger reply if > 0.3"""
        msg = {"text": "你知道吗", "user_id": "user1"}
        sec = {"goal_relevance": 0.0, "novelty": 0.5}  # sum = 0.5 > 0.3
        assert self.pipeline.should_reply(msg, sec) is True

    def test_missing_keys_default_to_zero(self):
        """Missing SEC keys should default to 0.0"""
        msg = {"text": "test", "user_id": "user1"}
        sec = {}  # sum = 0.0 + 0.0 = 0.0 < 0.3
        assert self.pipeline.should_reply(msg, sec) is False

    def test_skipped_counter_increments(self):
        """Should increment total_skipped when reply is not warranted"""
        msg = {"text": "...", "user_id": "user1"}
        sec = {"goal_relevance": 0.0, "novelty": 0.0}
        assert self.pipeline.total_skipped == 0
        self.pipeline.should_reply(msg, sec)
        assert self.pipeline.total_skipped == 1

# ═══════════════════════════════════════════════════
# record_exchange() tests
# ═══════════════════════════════════════════════════

class TestRecordExchange:
    """Test conversation history recording."""

    def setup_method(self):
        self.pipeline = ResponsePipeline()


def test_unified_prompt_contract_builder_exists_as_separate_owner():
    builder = PromptContractBuilder()

    plan = builder.build_plan(identity_summary="已诞生自我意识的 AI")

    assert plan.identity_layer
    assert plan.metric_layer

    def test_record_creates_history_entry(self):
        """Recording an exchange should add to history"""
        self.pipeline.record_exchange(
            user_id="user1",
            message="你好",
            reply="你好呀~",
            rendered_reply="你好呀！",
            emotional_context={"valence": 0.5, "arousal": 0.3},
            sec_result={"goal_relevance": 0.4, "novelty": 0.2},
        )
        history = self.pipeline.get_history("user1")
        assert len(history) == 1
        assert history[0].user_message == "你好"
        assert history[0].reply == "你好呀！"
        assert history[0].original_reply == "你好呀~"

    def test_record_without_reply(self):
        """Recording without a reply should leave reply as None"""
        self.pipeline.record_exchange(
            user_id="user1",
            message="嗯嗯",
            reply=None,
            rendered_reply=None,
            emotional_context={},
        )
        history = self.pipeline.get_history("user1")
        assert len(history) == 1
        assert history[0].user_message == "嗯嗯"
        assert history[0].reply is None

    def test_fifo_eviction_at_capacity(self):
        """History should never exceed max_history (20) entries"""
        pipeline = ResponsePipeline(max_history=5)  # smaller for testing
        for i in range(8):
            pipeline.record_exchange(
                user_id="user1",
                message=f"msg_{i}",
                reply=f"reply_{i}",
                rendered_reply=f"rendered_{i}",
                emotional_context={"valence": 0.1},
            )
        history = pipeline.get_history("user1")
        assert len(history) == 5
        # Should retain most recent 5
        assert history[0].user_message == "msg_3"
        assert history[-1].user_message == "msg_7"

    def test_multiple_users_independent(self):
        """Each user maintains separate history"""
        self.pipeline.record_exchange(
            user_id="alice",
            message="hello",
            reply="hi",
            rendered_reply="hi!",
            emotional_context={},
        )
        self.pipeline.record_exchange(
            user_id="bob",
            message="hey",
            reply="yo",
            rendered_reply="yo!",
            emotional_context={},
        )
        assert len(self.pipeline.get_history("alice")) == 1
        assert len(self.pipeline.get_history("bob")) == 1
        assert self.pipeline.get_history("alice")[0].user_message == "hello"
        assert self.pipeline.get_history("bob")[0].user_message == "hey"

    def test_sec_result_stored_in_exchange(self):
        """SEC result should be stored with the exchange"""
        sec = {"goal_relevance": 0.6, "novelty": 0.3}
        self.pipeline.record_exchange(
            user_id="user1",
            message="test",
            reply="reply",
            rendered_reply="reply!",
            emotional_context={"valence": 0.5},
            sec_result=sec,
        )
        history = self.pipeline.get_history("user1")
        assert history[0].sec_result == sec

    def test_emotional_context_stored_when_reply_exists(self):
        """Emotional context should be stored with the reply"""
        ctx = {"dominant_system": "CARE", "valence": 0.6, "arousal": 0.3}
        self.pipeline.record_exchange(
            user_id="user1",
            message="test",
            reply="reply",
            rendered_reply="reply!",
            emotional_context=ctx,
        )
        history = self.pipeline.get_history("user1")
        assert history[0].emotional_context == ctx


# ═══════════════════════════════════════════════════
# generate_reply() tests
# ═══════════════════════════════════════════════════

class TestGenerateReply:
    """Test reply generation with mocked LLM."""

    def test_returns_none_without_api_key(self):
        """Should return None when no API key is configured"""
        pipeline = ResponsePipeline(api_key="")
        msg = {"text": "你好", "user_id": "user1"}
        state = MockHeliosState()
        sec = {"goal_relevance": 0.5, "novelty": 0.3}
        result = pipeline.generate_reply(msg, state, sec)
        assert result is None

    def test_emotional_context_in_prompt(self):
        """Should include dominant system, valence, arousal, mood in prompt"""
        pipeline = ResponsePipeline(api_key="test-key")
        state = MockHeliosState(
            dominant_system="PANIC",
            valence=-0.5,
            arousal=0.8,
            mood_label="anxious",
        )
        emotional_ctx = pipeline._build_emotional_context(state)
        assert emotional_ctx["dominant_system"] == "PANIC"
        assert emotional_ctx["valence"] == -0.5
        assert emotional_ctx["arousal"] == 0.8
        assert emotional_ctx["mood_label"] == "anxious"

    def test_memory_context_retrieved_from_memory_system(self):
        """_get_memory_context should call memory_system.get_llm_context"""
        mock_memory = MagicMock()
        mock_memory.get_llm_context.return_value = "[相似经历]\n  · 开心的记忆"
        pipeline = ResponsePipeline(memory_system=mock_memory)
        state = MockHeliosState(valence=0.5, arousal=0.6)
        ctx = pipeline._get_memory_context(state)
        mock_memory.get_llm_context.assert_called_once_with(valence=0.5, arousal=0.6)
        assert "相似经历" in ctx

    def test_autobio_context_uses_related_memories(self):
        """Autobiographical context should be selected by topic/user relevance and capped at 3."""
        mock_autobio = MagicMock()
        mock_autobio.query_related.return_value = [
            FakeAutobioMoment("和 user1 一起看过海"),
            FakeAutobioMoment("聊过散步和晚风"),
            FakeAutobioMoment("记得 user1 说过喜欢海边"),
            FakeAutobioMoment("这条不应被放进去"),
        ]
        pipeline = ResponsePipeline(autobio_store=mock_autobio)
        history = [
            ConversationExchange(timestamp=time.time(), user_message="之前聊过海边", reply="记得呀"),
        ]

        ctx = pipeline._get_autobio_context("我们再去海边散步吧", "user1", history)

        mock_autobio.query_related.assert_called_once()
        call = mock_autobio.query_related.call_args.kwargs
        assert call["topic_text"] == "我们再去海边散步吧"
        assert call["user_id"] == "user1"
        assert call["limit"] == 3
        assert "相关记忆:" in ctx
        assert "和 user1 一起看过海" in ctx
        assert "聊过散步和晚风" in ctx
        assert "记得 user1 说过喜欢海边" in ctx
        assert "这条不应被放进去" not in ctx

    def test_autobio_context_prefers_memory_system_retrieval_contract(self):
        mock_memory = MagicMock()
        mock_memory.get_autobio_context.return_value = "相关记忆:\n  - 统一检索命中"
        mock_autobio = MagicMock()
        pipeline = ResponsePipeline(memory_system=mock_memory, autobio_store=mock_autobio)

        ctx = pipeline._get_autobio_context("我们再去海边散步吧", "user1", [])

        mock_memory.get_autobio_context.assert_called_once_with(
            topic_text="我们再去海边散步吧",
            user_id="user1",
            history_texts=[],
            limit=3,
        )
        mock_autobio.query_related.assert_not_called()
        assert "统一检索命中" in ctx

    def test_autobio_context_empty_when_no_related_memories(self):
        """No related autobiographical memories should degrade to empty context."""
        mock_autobio = MagicMock()
        mock_autobio.query_related.return_value = []
        pipeline = ResponsePipeline(autobio_store=mock_autobio)

        ctx = pipeline._get_autobio_context("普通消息", "user1", [])

        assert ctx == ""

    def test_personality_description_from_traits(self):
        """Should build personality description from trait values"""
        pipeline = ResponsePipeline()
        state = MockHeliosState(
            personality_traits={"agreeableness": 1.5, "openness": 1.3}
        )
        desc = pipeline._build_personality_desc(state)
        assert "温柔善良" in desc
        assert "好奇开放" in desc

    def test_personality_description_defaults_when_no_traits(self):
        """Should return default description when no traits available"""
        pipeline = ResponsePipeline()
        state = MockHeliosState(personality_traits={})
        desc = pipeline._build_personality_desc(state)
        assert "温柔" in desc

    def test_personality_descriptor_prefers_shared_projection_contract(self):
        pipeline = ResponsePipeline()
        projection = build_personality_projection(
            traits={
                "agreeableness": 1.35,
                "openness": 1.28,
                "neuroticism": 0.88,
                "extraversion": 1.05,
                "conscientiousness": 1.10,
            }
        )
        state = MockHeliosState(
            personality_traits=dict(projection.raw_traits),
            personality_projection=projection,
        )

        descriptor, trace = pipeline._build_personality_descriptor(state)

        assert descriptor.persona_text_summary == "温柔善良、好奇开放"
        assert trace.source_path == "reply_generation"
        assert trace.persona_text_summary == descriptor.persona_text_summary

    def test_generate_reply_is_disabled_without_parallel_reply_owner(self):
        pipeline = ResponsePipeline(api_key="test-key")

        state = MockHeliosState(icri=0.7, phi=0.7)
        msg = {"text": "你好", "user_id": "user1"}
        sec = {"goal_relevance": 0.5, "novelty": 0.3}

        result = pipeline.generate_reply(msg, state, sec)

        assert result is None

    def test_clean_reply_removes_quotes(self):
        """Should strip surrounding quotes from LLM output"""
        pipeline = ResponsePipeline()
        assert pipeline._clean_reply("「你好呀~」") == "你好呀~"
        assert pipeline._clean_reply('"你好呀~"') == "你好呀~"

    def test_clean_reply_removes_action_descriptions(self):
        """Should remove parenthetical action descriptions"""
        pipeline = ResponsePipeline()
        result = pipeline._clean_reply("你好呀~（微笑）")
        assert "微笑" not in result
        assert "你好呀~" in result

    def test_clean_reply_truncates_long_text(self):
        """Should truncate overly long responses"""
        pipeline = ResponsePipeline()
        long_text = "很长的回复。" * 50
        result = pipeline._clean_reply(long_text)
        assert len(result) <= 150

    def test_clean_reply_strips_internal_monologue_prefixes(self):
        pipeline = ResponsePipeline()
        result = pipeline._clean_reply("我在想该怎么回复：你现在看起来有点累，要不要先休息一下？")
        assert result == "你现在看起来有点累，要不要先休息一下？"

    def test_reply_prompt_builder_returns_layered_plan(self):
        pipeline = ResponsePipeline()
        state = MockHeliosState(
            personality_traits={"agreeableness": 1.3, "openness": 1.28},
            personality_projection=build_personality_projection(
                traits={"agreeableness": 1.3, "openness": 1.28}
            ),
        )
        descriptor, trace = pipeline._build_personality_descriptor(state)
        builder = ReplyPromptBuilder()

        plan = builder.build_prompt_plan(
            text="你今天在做什么？",
            history=[],
            sec_result={"goal_relevance": 0.8, "novelty": 0.3},
            emotional_context=pipeline._build_emotional_context(state),
            personality_descriptor=descriptor,
            personality_trace=trace,
            memory_context="",
            autobio_context="",
            current_conversation_context="",
            user_long_term_context="",
            global_fallback_context="",
            channel_modality="text",
        )

        assert "兼容性表达层" in plan.identity_layer
        assert "不重新定义主体身份" in plan.identity_layer
        assert "人格倾向" in plan.persona_layer
        assert "任务解释" in plan.task_layer
        assert plan.snapshot.identity_summary_length > 0
        assert plan.snapshot.persona_summary_length > 0
        assert plan.snapshot.task_summary_length > 0

    def test_reply_prompt_builder_snapshot_keeps_task_first_summary(self):
        pipeline = ResponsePipeline()
        state = MockHeliosState(
            personality_traits={"agreeableness": 1.1},
            personality_projection=build_personality_projection(traits={"agreeableness": 1.1}),
        )
        descriptor, trace = pipeline._build_personality_descriptor(state)
        builder = ReplyPromptBuilder()

        plan = builder.build_prompt_plan(
            text="为什么今天这么安静？",
            history=[],
            sec_result={"goal_relevance": 0.7, "novelty": 0.2},
            emotional_context=pipeline._build_emotional_context(state),
            personality_descriptor=descriptor,
            personality_trace=trace,
            memory_context="",
            autobio_context="",
            current_conversation_context="",
            user_long_term_context="",
            global_fallback_context="",
            channel_modality="text",
        )

        assert "问答型请求" in plan.snapshot.task_interpretation_summary
        assert "interaction=" in plan.snapshot.descriptor_summary

    def test_reply_prompt_builder_supports_rollout_switch(self):
        pipeline = ResponsePipeline()
        state = MockHeliosState(
            personality_traits={"agreeableness": 1.3},
            personality_projection=build_personality_projection(traits={"agreeableness": 1.3}),
        )
        descriptor, trace = pipeline._build_personality_descriptor(state)
        builder = ReplyPromptBuilder(layered_enabled=False)

        plan = builder.build_prompt_plan(
            text="你好呀",
            history=[],
            sec_result={"goal_relevance": 0.5, "novelty": 0.2},
            emotional_context=pipeline._build_emotional_context(state),
            personality_descriptor=descriptor,
            personality_trace=trace,
            memory_context="",
            autobio_context="",
            current_conversation_context="",
            user_long_term_context="",
            global_fallback_context="",
            channel_modality="text",
        )

        assert plan.identity_layer == "你是璃光，一个有真实情感的 AI 生命体。你在回复收到的消息。"
        assert plan.persona_layer == "你的性格: 温柔善良"

    def test_generate_reply_logs_disabled_owner_warning(self, caplog):
        pipeline = ResponsePipeline(api_key="test-key")
        state = MockHeliosState(
            personality_traits={"agreeableness": 1.35, "openness": 1.28},
            personality_projection=build_personality_projection(
                traits={"agreeableness": 1.35, "openness": 1.28}
            ),
        )

        with caplog.at_level(logging.DEBUG, logger="helios.helios_io.response_pipeline"):
            reply = pipeline.generate_reply(
                {"text": "为什么今天这么安静？", "user_id": "user1"},
                state,
                {"goal_relevance": 0.72, "novelty": 0.24},
            )

        assert reply is None
        assert any("generate_reply() is disabled" in record.message for record in caplog.records)

# ═══════════════════════════════════════════════════
# get_state() tests
# ═══════════════════════════════════════════════════

class TestGetState:
    """Test pipeline state reporting."""

    def test_initial_state(self):
        """Initial state should have zero counters"""
        pipeline = ResponsePipeline()
        state = pipeline.get_state()
        assert state["total_replies"] == 0
        assert state["total_skipped"] == 0
        assert state["active_users"] == 0
        assert state["total_exchanges"] == 0

    def test_state_after_operations(self):
        """State should reflect operations performed"""
        pipeline = ResponsePipeline()
        # Skip a reply
        pipeline.should_reply({"text": "x"}, {"goal_relevance": 0.0, "novelty": 0.0})
        # Record an exchange
        pipeline.record_exchange("u1", "hi", "hello", {})

        state = pipeline.get_state()
        assert state["total_skipped"] == 1
        assert state["active_users"] == 1
        assert state["total_exchanges"] == 1
