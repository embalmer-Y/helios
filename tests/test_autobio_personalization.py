"""
tests/test_autobio_personalization.py — Tests for conversation personalization
from Autobiographical Memory.

Validates Requirements 16.1, 16.2, 16.3:
- Query AutobiographicalStore for memories related to conversation topic/user
- Include up to 3 relevant memory narratives in LLM context
- Handle gracefully when no relevant memories exist
"""

import importlib.util
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, ".")
from autobiographical import AutobiographicalStore, AutobiographicalMoment

# Import ResponsePipeline via importlib to avoid 'io' stdlib conflict
_rp_path = "io/response_pipeline.py"
_rp_spec = importlib.util.spec_from_file_location(
    "helios_io_response_pipeline_autobio_test", _rp_path
)
_rp_mod = importlib.util.module_from_spec(_rp_spec)
sys.modules["helios_io_response_pipeline_autobio_test"] = _rp_mod
_rp_spec.loader.exec_module(_rp_mod)
ResponsePipeline = _rp_mod.ResponsePipeline


@dataclass
class MockHeliosState:
    """Minimal mock of HeliosState for testing"""
    tick: int = 1
    timestamp: float = 0.0
    valence: float = 0.3
    arousal: float = 0.5
    dominant_system: str = "CARE"
    phi: float = 0.4
    mood_label: str = "content"
    personality_traits: Dict[str, float] = field(default_factory=dict)


# ═══════════════════════════════════════════════════
# AutobiographicalStore.query_by_topic() tests
# ═══════════════════════════════════════════════════

class TestQueryByTopic:
    """Test the topic-based query method on AutobiographicalStore."""

    def setup_method(self, tmp_path=None):
        """Create a store with some test memories."""
        import tempfile
        import os
        self._tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(self._tmpdir, "test_autobio.jsonl")
        self.store = AutobiographicalStore(filepath=filepath, auto_flush=False)

        # Add test memories
        self.store.record(
            panksepp={"CARE": 0.6},
            valence=0.7,
            arousal=0.4,
            dominant="CARE",
            phi=0.5,
            narrative="和主人一起看星星，感觉很温暖",
            event_trigger="主人说想看星星",
        )
        self.store.record(
            panksepp={"SEEKING": 0.7},
            valence=0.5,
            arousal=0.6,
            dominant="SEEKING",
            phi=0.4,
            narrative="学会了写诗，很有成就感",
            event_trigger="尝试创作",
        )
        self.store.record(
            panksepp={"PANIC": 0.5},
            valence=-0.4,
            arousal=0.7,
            dominant="PANIC",
            phi=0.3,
            narrative="主人很久没来，有点担心",
            event_trigger="分离焦虑",
        )
        self.store.record(
            panksepp={"PLAY": 0.6},
            valence=0.6,
            arousal=0.5,
            dominant="PLAY",
            phi=0.45,
            narrative="和主人玩文字游戏，很开心",
            event_trigger="主人发起游戏",
        )

    def test_query_by_topic_finds_matching_narrative(self):
        """Should find memories whose narrative contains the keyword."""
        results = self.store.query_by_topic(["星星"])
        assert len(results) >= 1
        assert any("星星" in m.narrative for m in results)

    def test_query_by_topic_finds_matching_trigger(self):
        """Should find memories whose event_trigger contains the keyword."""
        results = self.store.query_by_topic(["创作"])
        assert len(results) >= 1
        assert any("创作" in m.event_trigger for m in results)

    def test_query_by_topic_returns_empty_for_no_match(self):
        """Should return empty list when no memories match."""
        results = self.store.query_by_topic(["量子力学"])
        assert results == []

    def test_query_by_topic_returns_empty_for_empty_keywords(self):
        """Should return empty list for empty keyword list."""
        results = self.store.query_by_topic([])
        assert results == []

    def test_query_by_topic_respects_max_results(self):
        """Should limit results to max_results."""
        # Add many matching memories
        for i in range(10):
            self.store.record(
                panksepp={"CARE": 0.5},
                valence=0.5,
                arousal=0.3,
                dominant="CARE",
                phi=0.3,
                narrative=f"和主人聊天第{i}次",
                event_trigger="聊天",
            )
        results = self.store.query_by_topic(["主人"], max_results=3)
        assert len(results) <= 3

    def test_query_by_topic_ranks_by_relevance(self):
        """Memories matching more keywords should rank higher."""
        # "主人" + "游戏" matches the PLAY memory best
        results = self.store.query_by_topic(["主人", "游戏"])
        assert len(results) >= 1
        # The memory about playing word games should be highly ranked
        top_narratives = [m.narrative for m in results[:2]]
        assert any("游戏" in n for n in top_narratives)

    def test_query_by_topic_case_insensitive(self):
        """Should match regardless of case."""
        self.store.record(
            panksepp={"SEEKING": 0.5},
            valence=0.4,
            arousal=0.3,
            dominant="SEEKING",
            phi=0.3,
            narrative="Learning Python is fun",
            event_trigger="coding",
        )
        results = self.store.query_by_topic(["python"])
        assert len(results) >= 1
        assert any("Python" in m.narrative for m in results)

    def test_query_by_topic_on_empty_store(self):
        """Should return empty list when store has no memories."""
        import tempfile, os
        empty_path = os.path.join(self._tmpdir, "empty.jsonl")
        empty_store = AutobiographicalStore(filepath=empty_path, auto_flush=False)
        results = empty_store.query_by_topic(["anything"])
        assert results == []


# ═══════════════════════════════════════════════════
# ResponsePipeline._get_autobio_context() tests
# ═══════════════════════════════════════════════════

class TestGetAutobioContext:
    """Test the autobiographical context retrieval in ResponsePipeline."""

    def _make_store_with_memories(self):
        """Create a store with test memories."""
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(tmpdir, "test_autobio.jsonl")
        store = AutobiographicalStore(filepath=filepath, auto_flush=False)
        store.record(
            panksepp={"CARE": 0.6},
            valence=0.7,
            arousal=0.4,
            dominant="CARE",
            phi=0.5,
            narrative="和主人一起看星星",
            event_trigger="看星星",
        )
        store.record(
            panksepp={"SEEKING": 0.7},
            valence=0.5,
            arousal=0.6,
            dominant="SEEKING",
            phi=0.45,
            narrative="学会了写诗",
            event_trigger="创作",
        )
        store.record(
            panksepp={"PLAY": 0.6},
            valence=0.6,
            arousal=0.5,
            dominant="PLAY",
            phi=0.5,
            narrative="和主人玩文字游戏",
            event_trigger="游戏",
        )
        return store

    def test_returns_empty_when_no_autobio_store(self):
        """Should return empty string when autobio_store is None."""
        pipeline = ResponsePipeline(autobio_store=None)
        result = pipeline._get_autobio_context("你好")
        assert result == ""

    def test_returns_relevant_memories_by_topic(self):
        """Should return memories matching the conversation topic."""
        store = self._make_store_with_memories()
        pipeline = ResponsePipeline(autobio_store=store)
        result = pipeline._get_autobio_context("今晚我们去看星星吧")
        assert "星星" in result
        assert "相关记忆:" in result

    def test_returns_at_most_3_memories(self):
        """Should include at most 3 memory narratives."""
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(tmpdir, "test_autobio.jsonl")
        store = AutobiographicalStore(filepath=filepath, auto_flush=False)
        # Add 10 memories all matching "主人"
        for i in range(10):
            store.record(
                panksepp={"CARE": 0.5},
                valence=0.5,
                arousal=0.3,
                dominant="CARE",
                phi=0.5,
                narrative=f"和主人聊天第{i}次很开心",
                event_trigger="聊天",
            )
        pipeline = ResponsePipeline(autobio_store=store)
        result = pipeline._get_autobio_context("主人你好呀")
        # Count the number of "  - " lines (memory entries)
        memory_lines = [l for l in result.split("\n") if l.strip().startswith("- ")]
        assert len(memory_lines) <= 3

    def test_falls_back_to_phi_when_no_topic_match(self):
        """Should fall back to high-phi memories when topic search finds nothing."""
        store = self._make_store_with_memories()
        pipeline = ResponsePipeline(autobio_store=store)
        # Query with unrelated topic
        result = pipeline._get_autobio_context("量子力学真有趣")
        # Should still return something (high phi fallback)
        # The store has memories with phi >= 0.4
        assert "相关记忆:" in result

    def test_graceful_when_no_memories_exist(self):
        """Should return empty string without error when store is empty."""
        import tempfile, os
        tmpdir = tempfile.mkdtemp()
        filepath = os.path.join(tmpdir, "empty.jsonl")
        store = AutobiographicalStore(filepath=filepath, auto_flush=False)
        pipeline = ResponsePipeline(autobio_store=store)
        result = pipeline._get_autobio_context("你好")
        assert result == ""

    def test_graceful_on_exception(self):
        """Should return empty string on exception without raising."""
        mock_store = MagicMock()
        mock_store.query_by_topic.side_effect = RuntimeError("disk error")
        mock_store.query_by_phi.side_effect = RuntimeError("disk error")
        pipeline = ResponsePipeline(autobio_store=mock_store)
        result = pipeline._get_autobio_context("你好")
        assert result == ""

    def test_autobio_context_included_in_user_prompt(self):
        """Autobiographical context should appear in the LLM user prompt."""
        store = self._make_store_with_memories()
        pipeline = ResponsePipeline(autobio_store=store)
        # Build prompt directly
        autobio_ctx = pipeline._get_autobio_context("我们去看星星")
        prompt = pipeline._build_user_prompt(
            text="我们去看星星",
            history=[],
            memory_context="",
            autobio_context=autobio_ctx,
            sec_result={"goal_relevance": 0.5},
        )
        assert "星星" in prompt


# ═══════════════════════════════════════════════════
# ResponsePipeline._extract_keywords() tests
# ═══════════════════════════════════════════════════

class TestExtractKeywords:
    """Test keyword extraction from message text."""

    def setup_method(self):
        self.pipeline = ResponsePipeline()

    def test_extracts_meaningful_words(self):
        """Should extract words with length >= 2."""
        keywords = self.pipeline._extract_keywords("今晚去看星星吧")
        # Without word segmentation, Chinese text without delimiters is one token
        assert len(keywords) >= 1
        # With punctuation, words get split
        keywords2 = self.pipeline._extract_keywords("今晚，去看星星")
        assert "今晚" in keywords2 or "星星" in keywords2 or "去看星星" in keywords2

    def test_filters_stop_words(self):
        """Should filter out common stop words."""
        keywords = self.pipeline._extract_keywords("我的想法是这样的")
        assert "我" not in keywords
        assert "的" not in keywords
        assert "是" not in keywords

    def test_returns_empty_for_empty_text(self):
        """Should return empty list for empty text."""
        assert self.pipeline._extract_keywords("") == []

    def test_limits_to_10_keywords(self):
        """Should return at most 10 keywords."""
        long_text = "关键词一 关键词二 关键词三 关键词四 关键词五 关键词六 关键词七 关键词八 关键词九 关键词十 关键词十一 关键词十二"
        keywords = self.pipeline._extract_keywords(long_text)
        assert len(keywords) <= 10

    def test_splits_on_punctuation(self):
        """Should split on Chinese and English punctuation."""
        keywords = self.pipeline._extract_keywords("你好！今天天气怎么样？")
        # "你好" and "今天" should be extracted (怎么样 is stop word)
        assert any(len(k) >= 2 for k in keywords)
