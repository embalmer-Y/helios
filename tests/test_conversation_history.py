"""
tests/test_conversation_history.py — Unit tests for conversation history management.

Tests the ConversationExchange dataclass and ConversationHistoryManager
including FIFO eviction, message/reply append, and bounded buffer behavior.

Requirements: 7.4, 8.1, 8.2, 8.3, 8.4
"""

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.conversation_history import (
    DEFAULT_MAX_HISTORY,
    ConversationExchange,
    ConversationHistoryManager,
)


# ═══════════════════════════════════════════════════
# ConversationExchange Tests
# ═══════════════════════════════════════════════════


class TestConversationExchange:
    """Test the ConversationExchange dataclass."""

    def test_create_with_required_fields(self):
        """Exchange created with timestamp, message, sec_result has None reply."""
        ex = ConversationExchange(
            timestamp=1000.0,
            user_message="你好",
            sec_result={"novelty": 0.5, "goal_relevance": 0.3},
        )
        assert ex.timestamp == 1000.0
        assert ex.user_message == "你好"
        assert ex.conversation_key == ""
        assert ex.sec_result == {"novelty": 0.5, "goal_relevance": 0.3}
        assert ex.reply is None
        assert ex.emotional_context == {}

    def test_create_with_all_fields(self):
        """Exchange can be created with all fields including reply and emotional context."""
        ex = ConversationExchange(
            timestamp=2000.0,
            user_message="在吗",
            sec_result={"novelty": 0.2},
            reply="我在呢",
            emotional_context={"valence": 0.6, "arousal": 0.3},
        )
        assert ex.reply == "我在呢"
        assert ex.emotional_context == {"valence": 0.6, "arousal": 0.3}

    def test_mutable_reply_update(self):
        """Reply and emotional_context can be set after creation."""
        ex = ConversationExchange(
            timestamp=1000.0,
            user_message="test",
            sec_result={},
        )
        ex.reply = "response"
        ex.emotional_context = {"dominant_system": "CARE"}
        assert ex.reply == "response"
        assert ex.emotional_context == {"dominant_system": "CARE"}


# ═══════════════════════════════════════════════════
# ConversationHistoryManager Tests
# ═══════════════════════════════════════════════════


class TestConversationHistoryManager:
    """Test the conversation history manager."""

    def test_default_max_history(self):
        """Manager defaults to 20 max history entries per user."""
        mgr = ConversationHistoryManager()
        assert mgr.max_history == DEFAULT_MAX_HISTORY == 20

    def test_custom_max_history(self):
        """Manager accepts custom max_history."""
        mgr = ConversationHistoryManager(max_history=5)
        assert mgr.max_history == 5

    def test_invalid_max_history_raises(self):
        """max_history < 1 raises ValueError."""
        with pytest.raises(ValueError):
            ConversationHistoryManager(max_history=0)
        with pytest.raises(ValueError):
            ConversationHistoryManager(max_history=-1)

    def test_empty_history_for_new_user(self):
        """Unknown user returns empty history."""
        mgr = ConversationHistoryManager()
        assert mgr.get_history("unknown_user") == []
        assert mgr.history_length("unknown_user") == 0

    def test_append_message_creates_exchange(self):
        """append_message creates an exchange with timestamp and SEC result."""
        mgr = ConversationHistoryManager()
        ex = mgr.append_message(
            user_id="user1",
            message="你好",
            sec_result={"novelty": 0.4, "goal_relevance": 0.6},
            timestamp=1000.0,
        )
        assert ex.timestamp == 1000.0
        assert ex.user_message == "你好"
        assert ex.sec_result == {"novelty": 0.4, "goal_relevance": 0.6}
        assert ex.reply is None
        assert mgr.history_length("user1") == 1

    def test_append_message_uses_current_time_by_default(self):
        """append_message uses time.time() when no timestamp provided."""
        mgr = ConversationHistoryManager()
        before = time.time()
        ex = mgr.append_message("user1", "test", {})
        after = time.time()
        assert before <= ex.timestamp <= after

    def test_append_reply_updates_last_exchange(self):
        """append_reply sets reply and emotional_context on the most recent exchange."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "你好", {"novelty": 0.3}, timestamp=100.0)

        result = mgr.append_reply(
            "user1",
            reply="你好呀！",
            emotional_context={"valence": 0.5, "arousal": 0.2, "dominant_system": "CARE"},
        )
        assert result is True

        history = mgr.get_history("user1")
        assert len(history) == 1
        assert history[0].reply == "你好呀！"
        assert history[0].emotional_context["valence"] == 0.5
        assert history[0].emotional_context["dominant_system"] == "CARE"

    def test_append_reply_no_history_returns_false(self):
        """append_reply returns False when user has no history."""
        mgr = ConversationHistoryManager()
        result = mgr.append_reply("nobody", "reply", {"valence": 0.0})
        assert result is False

    def test_fifo_eviction_at_max(self):
        """When buffer exceeds max_history, oldest exchanges are evicted (FIFO)."""
        mgr = ConversationHistoryManager(max_history=3)

        mgr.append_message("user1", "msg1", {"novelty": 0.1}, timestamp=1.0)
        mgr.append_message("user1", "msg2", {"novelty": 0.2}, timestamp=2.0)
        mgr.append_message("user1", "msg3", {"novelty": 0.3}, timestamp=3.0)
        assert mgr.history_length("user1") == 3

        # Adding 4th should evict first
        mgr.append_message("user1", "msg4", {"novelty": 0.4}, timestamp=4.0)
        assert mgr.history_length("user1") == 3

        history = mgr.get_history("user1")
        messages = [ex.user_message for ex in history]
        assert messages == ["msg2", "msg3", "msg4"]

    def test_fifo_retains_most_recent(self):
        """After many appends, buffer contains the most recent max_history exchanges."""
        mgr = ConversationHistoryManager(max_history=5)

        for i in range(50):
            mgr.append_message("user1", f"msg{i}", {"n": float(i)}, timestamp=float(i))

        assert mgr.history_length("user1") == 5
        history = mgr.get_history("user1")
        messages = [ex.user_message for ex in history]
        assert messages == ["msg45", "msg46", "msg47", "msg48", "msg49"]

    def test_independent_user_histories(self):
        """Different users have independent histories."""
        mgr = ConversationHistoryManager(max_history=3)

        mgr.append_message("alice", "hello from alice", {}, timestamp=1.0)
        mgr.append_message("bob", "hello from bob", {}, timestamp=2.0)
        mgr.append_message("alice", "second from alice", {}, timestamp=3.0)

        assert mgr.history_length("alice") == 2
        assert mgr.history_length("bob") == 1

        alice_msgs = [ex.user_message for ex in mgr.get_history("alice")]
        bob_msgs = [ex.user_message for ex in mgr.get_history("bob")]
        assert alice_msgs == ["hello from alice", "second from alice"]
        assert bob_msgs == ["hello from bob"]

    def test_get_recent_messages(self):
        """get_recent_messages returns the last N user message texts."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "first", {}, timestamp=1.0)
        mgr.append_message("user1", "second", {}, timestamp=2.0)
        mgr.append_message("user1", "third", {}, timestamp=3.0)
        mgr.append_message("user1", "fourth", {}, timestamp=4.0)

        recent = mgr.get_recent_messages("user1", count=3)
        assert recent == ["second", "third", "fourth"]

    def test_get_recent_messages_fewer_than_count(self):
        """get_recent_messages returns all if fewer than count exist."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "only one", {}, timestamp=1.0)
        recent = mgr.get_recent_messages("user1", count=5)
        assert recent == ["only one"]

    def test_get_recent_messages_unknown_user(self):
        """get_recent_messages returns empty list for unknown user."""
        mgr = ConversationHistoryManager()
        assert mgr.get_recent_messages("ghost", count=3) == []

    def test_get_history_filters_by_conversation_key(self):
        """get_history can isolate one user's exchanges by conversation key."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "群聊消息", {}, timestamp=1.0, conversation_key="qq:group:g1")
        mgr.append_message("user1", "私聊消息", {}, timestamp=2.0, conversation_key="qq:dm:user1")

        history = mgr.get_history("user1", conversation_key="qq:dm:user1")

        assert [ex.user_message for ex in history] == ["私聊消息"]

    def test_append_reply_targets_matching_conversation_key(self):
        """append_reply updates the latest pending exchange in the same conversation."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "群聊消息", {}, timestamp=1.0, conversation_key="qq:group:g1")
        mgr.append_message("user1", "私聊消息", {}, timestamp=2.0, conversation_key="qq:dm:user1")

        result = mgr.append_reply(
            "user1",
            "私聊回复",
            {"valence": 0.3},
            conversation_key="qq:dm:user1",
        )

        assert result is True
        group_history = mgr.get_history("user1", conversation_key="qq:group:g1")
        dm_history = mgr.get_history("user1", conversation_key="qq:dm:user1")
        assert group_history[0].reply is None
        assert dm_history[0].reply == "私聊回复"

    def test_clear_user(self):
        """clear_user removes all history for a specific user."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "msg", {}, timestamp=1.0)
        mgr.append_message("user2", "msg", {}, timestamp=2.0)

        mgr.clear_user("user1")
        assert mgr.history_length("user1") == 0
        assert mgr.history_length("user2") == 1

    def test_clear_all(self):
        """clear_all removes all user histories."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "msg", {}, timestamp=1.0)
        mgr.append_message("user2", "msg", {}, timestamp=2.0)

        mgr.clear_all()
        assert mgr.get_user_ids() == []

    def test_get_user_ids(self):
        """get_user_ids returns all users with history."""
        mgr = ConversationHistoryManager()
        mgr.append_message("alice", "hi", {}, timestamp=1.0)
        mgr.append_message("bob", "hey", {}, timestamp=2.0)

        ids = sorted(mgr.get_user_ids())
        assert ids == ["alice", "bob"]

    def test_get_state(self):
        """get_state returns monitoring information."""
        mgr = ConversationHistoryManager(max_history=10)
        mgr.append_message("user1", "a", {}, timestamp=1.0)
        mgr.append_message("user1", "b", {}, timestamp=2.0)
        mgr.append_message("user2", "c", {}, timestamp=3.0)

        state = mgr.get_state()
        assert state["max_history_per_user"] == 10
        assert state["active_users"] == 2
        assert state["total_exchanges"] == 3
        assert state["per_user_counts"]["user1"] == 2
        assert state["per_user_counts"]["user2"] == 1

    def test_defensive_copy_sec_result(self):
        """Modifying the original sec_result dict doesn't affect the stored exchange."""
        mgr = ConversationHistoryManager()
        sec = {"novelty": 0.5}
        mgr.append_message("user1", "msg", sec, timestamp=1.0)
        sec["novelty"] = 999.0  # Modify original

        history = mgr.get_history("user1")
        assert history[0].sec_result["novelty"] == 0.5

    def test_defensive_copy_emotional_context(self):
        """Modifying the original emotional_context dict doesn't affect stored exchange."""
        mgr = ConversationHistoryManager()
        mgr.append_message("user1", "msg", {}, timestamp=1.0)

        ctx = {"valence": 0.3}
        mgr.append_reply("user1", "reply", ctx)
        ctx["valence"] = 999.0  # Modify original

        history = mgr.get_history("user1")
        assert history[0].emotional_context["valence"] == 0.3
