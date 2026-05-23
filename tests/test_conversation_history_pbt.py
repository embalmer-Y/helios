"""Property-based tests for conversation history management.

# Feature: helios-architecture-enhancement, Properties 4 & 5

**Validates: Requirements 7.4, 8.1, 8.2, 8.3, 8.4**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from helios_io.conversation_history import (
    DEFAULT_MAX_HISTORY,
    ConversationExchange,
    ConversationHistoryManager,
)

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    composite,
    dictionaries,
    floats,
    integers,
    lists,
    text,
)


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

sec_values = floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)

sec_results = dictionaries(
    keys=text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=20,
    ),
    values=sec_values,
    min_size=1,
    max_size=7,
)

emotional_contexts = dictionaries(
    keys=text(
        alphabet="abcdefghijklmnopqrstuvwxyz_",
        min_size=1,
        max_size=20,
    ),
    values=sec_values,
    min_size=1,
    max_size=5,
)

user_messages = text(min_size=1, max_size=100)

timestamps = floats(min_value=1000000000.0, max_value=2000000000.0, allow_nan=False, allow_infinity=False)


@composite
def message_sequences(draw, min_size=1, max_size=50):
    """Generate a list of (message, sec_result, timestamp) tuples."""
    n = draw(integers(min_value=min_size, max_value=max_size))
    items = []
    for i in range(n):
        msg = draw(user_messages)
        sec = draw(sec_results)
        ts = draw(timestamps)
        items.append((msg, sec, ts))
    return items


# ------------------------------------------------------------------
# Property 4: Conversation History Bounded Buffer
# ------------------------------------------------------------------


class TestConversationHistoryBoundedBuffer:
    """Property 4: For any sequence of message exchanges appended to a user's
    conversation history, the buffer SHALL never exceed 20 entries and SHALL
    always retain the most recent 20 exchanges (FIFO eviction of oldest).

    **Validates: Requirements 7.4, 8.1, 8.4**
    """

    @given(messages=message_sequences(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_buffer_never_exceeds_max_history(self, messages):
        """Buffer size never exceeds the configured max_history (default 20)."""
        mgr = ConversationHistoryManager()  # default max_history=20

        for msg, sec, ts in messages:
            mgr.append_message("user1", msg, sec, timestamp=ts)
            # Invariant: buffer size <= max_history at all times
            assert mgr.history_length("user1") <= mgr.max_history

    @given(messages=message_sequences(min_size=21, max_size=50))
    @settings(max_examples=100)
    def test_buffer_retains_most_recent_20(self, messages):
        """After more than 20 messages, buffer retains the most recent 20."""
        mgr = ConversationHistoryManager()  # default max_history=20

        for msg, sec, ts in messages:
            mgr.append_message("user1", msg, sec, timestamp=ts)

        history = mgr.get_history("user1")
        n = len(messages)
        expected_count = min(n, 20)
        assert len(history) == expected_count

        # The retained entries should correspond to the last 20 messages appended
        expected_messages = [m[0] for m in messages[-20:]]
        actual_messages = [ex.user_message for ex in history]
        assert actual_messages == expected_messages

    @given(
        n=integers(min_value=1, max_value=100),
        max_hist=integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_buffer_bounded_for_any_max_history(self, n, max_hist):
        """Buffer never exceeds max_history for any configured limit."""
        mgr = ConversationHistoryManager(max_history=max_hist)

        for i in range(n):
            mgr.append_message(
                "user1",
                f"msg{i}",
                {"novelty": 0.5},
                timestamp=1000.0 + i,
            )

        assert mgr.history_length("user1") <= max_hist
        assert mgr.history_length("user1") == min(n, max_hist)

    @given(messages=message_sequences(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_fifo_eviction_preserves_order(self, messages):
        """Eviction is FIFO: the oldest entries are dropped first, order is preserved."""
        mgr = ConversationHistoryManager()

        for msg, sec, ts in messages:
            mgr.append_message("user1", msg, sec, timestamp=ts)

        history = mgr.get_history("user1")
        retained_count = min(len(messages), 20)

        # The entries in history should match the tail of the input sequence
        expected_tail = messages[-retained_count:]
        for i, ex in enumerate(history):
            assert ex.user_message == expected_tail[i][0]
            assert ex.sec_result == expected_tail[i][1]
            assert ex.timestamp == expected_tail[i][2]


# ------------------------------------------------------------------
# Property 5: Conversation Exchange Completeness
# ------------------------------------------------------------------


class TestConversationExchangeCompleteness:
    """Property 5: For any message appended to conversation history, the stored
    entry SHALL contain a timestamp and SEC evaluation result. For any reply
    appended, the entry SHALL contain the emotional context that produced it.

    **Validates: Requirements 8.2, 8.3**
    """

    @given(
        message=user_messages,
        sec=sec_results,
        ts=timestamps,
    )
    @settings(max_examples=100)
    def test_appended_message_has_timestamp_and_sec(self, message, sec, ts):
        """Every appended message entry contains the original timestamp and SEC result."""
        mgr = ConversationHistoryManager()

        exchange = mgr.append_message("user1", message, sec, timestamp=ts)

        # The returned exchange has timestamp and SEC result
        assert exchange.timestamp == ts
        assert exchange.sec_result == sec

        # Verify from history retrieval as well
        history = mgr.get_history("user1")
        assert len(history) == 1
        assert history[0].timestamp == ts
        assert history[0].sec_result == sec
        assert history[0].user_message == message

    @given(
        message=user_messages,
        sec=sec_results,
        ts=timestamps,
        reply_text=user_messages,
        emo_ctx=emotional_contexts,
    )
    @settings(max_examples=100)
    def test_appended_reply_has_emotional_context(self, message, sec, ts, reply_text, emo_ctx):
        """Every appended reply entry contains the emotional context that produced it."""
        mgr = ConversationHistoryManager()

        # First append a message
        mgr.append_message("user1", message, sec, timestamp=ts)

        # Then append the reply with emotional context
        result = mgr.append_reply("user1", reply_text, emo_ctx)
        assert result is True

        # Verify the entry contains the emotional context
        history = mgr.get_history("user1")
        assert len(history) == 1
        assert history[0].reply == reply_text
        assert history[0].emotional_context == emo_ctx

    @given(messages=message_sequences(min_size=1, max_size=30))
    @settings(max_examples=100)
    def test_all_entries_have_timestamp_and_sec_after_multiple_appends(self, messages):
        """After multiple appends, every retained entry still has timestamp and SEC result."""
        mgr = ConversationHistoryManager()

        for msg, sec, ts in messages:
            mgr.append_message("user1", msg, sec, timestamp=ts)

        history = mgr.get_history("user1")
        for ex in history:
            # Every entry must have a numeric timestamp
            assert isinstance(ex.timestamp, float)
            assert ex.timestamp > 0
            # Every entry must have a SEC result dict
            assert isinstance(ex.sec_result, dict)
            assert len(ex.sec_result) >= 1

    @given(
        message=user_messages,
        sec=sec_results,
        ts=timestamps,
        reply_text=user_messages,
        emo_ctx=emotional_contexts,
    )
    @settings(max_examples=100)
    def test_reply_does_not_overwrite_message_fields(self, message, sec, ts, reply_text, emo_ctx):
        """Appending a reply preserves the original message fields (timestamp, sec_result)."""
        mgr = ConversationHistoryManager()

        mgr.append_message("user1", message, sec, timestamp=ts)
        mgr.append_reply("user1", reply_text, emo_ctx)

        history = mgr.get_history("user1")
        ex = history[0]

        # Original message fields preserved
        assert ex.timestamp == ts
        assert ex.user_message == message
        assert ex.sec_result == sec

        # Reply fields added
        assert ex.reply == reply_text
        assert ex.emotional_context == emo_ctx
