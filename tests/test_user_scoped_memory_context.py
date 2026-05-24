import logging
from dataclasses import dataclass, field
from typing import Dict

from helios_io.conversation_history import ConversationHistoryManager
from helios_io.response_pipeline import ResponsePipeline
from memory.memory_system import MemorySystem


@dataclass
class MockState:
    valence: float = 0.3
    arousal: float = 0.5
    dominant_system: str = "SEEKING"
    mood_label: str = "neutral"
    icri: float = 0.3
    personality_traits: Dict[str, float] = field(default_factory=dict)


def test_conversation_history_returns_recent_exchange_texts_only_for_user():
    manager = ConversationHistoryManager(max_history=5)
    manager.append_message("user1", "你好", {"goal_relevance": 0.2})
    manager.append_reply("user1", "在呢", {"dominant_system": "CARE"})
    manager.append_message("user2", "别串线", {"goal_relevance": 0.2})
    manager.append_reply("user2", "不会", {"dominant_system": "CARE"})

    texts = manager.get_recent_exchange_texts("user1", count=5)

    assert len(texts) == 1
    assert "你好" in texts[0]
    assert "别串线" not in texts[0]


def test_conversation_history_filters_by_conversation_key_for_same_user():
    manager = ConversationHistoryManager(max_history=5)
    manager.append_message(
        "user1",
        "群里你好",
        {"goal_relevance": 0.2},
        conversation_key="qq:group:g1",
    )
    manager.append_reply(
        "user1",
        "群里收到",
        {"dominant_system": "CARE"},
        conversation_key="qq:group:g1",
    )
    manager.append_message(
        "user1",
        "私聊你好",
        {"goal_relevance": 0.2},
        conversation_key="qq:dm:user1",
    )
    manager.append_reply(
        "user1",
        "私聊收到",
        {"dominant_system": "CARE"},
        conversation_key="qq:dm:user1",
    )

    texts = manager.get_recent_exchange_texts(
        "user1",
        count=5,
        conversation_key="qq:dm:user1",
    )

    assert len(texts) == 1
    assert "私聊你好" in texts[0]
    assert "群里你好" not in texts[0]


def test_memory_system_reply_bundle_includes_partitioned_sections():
    system = MemorySystem()
    system.hold("当前在想海边散步", content={"user_id": "user1"}, valence=0.4, arousal=0.2)
    system.remember(
        "之前一起聊过海边",
        content={"user_id": "user1"},
        valence=0.5,
        arousal=0.3,
        phi=0.4,
    )

    bundle = system.get_reply_memory_bundle(
        user_id="user1",
        message_text="海边",
        history_texts=["对方: 你好\n你: 在呢"],
        conversation_key="qq:dm:user1",
        valence=0.5,
        arousal=0.4,
    )

    assert "current_conversation" in bundle.resolved_text_sections
    assert "user_long_term" in bundle.resolved_text_sections
    assert bundle.resolved_text_sections["current_conversation"].startswith("[当前会话]")
    assert bundle.trace_summary.startswith("user_id=user1")
    assert "conversation_key=qq:dm:user1" in bundle.trace_summary
    assert "selected=(1," in bundle.trace_summary
    assert bundle.request.conversation_key == "qq:dm:user1"
    assert bundle.layers[0].source_refs[0].conversation_key == "qq:dm:user1"
    assert bundle.layers[1].source_refs[0].owner_user_id == "user1"


def test_memory_system_reply_bundle_reuses_cache_for_same_request():
    system = MemorySystem()
    system.remember(
        "之前一起聊过海边",
        content={"user_id": "user1"},
        valence=0.5,
        arousal=0.3,
        phi=0.4,
    )

    first = system.get_reply_memory_bundle(
        user_id="user1",
        message_text="我们再去海边散步吧",
        history_texts=["对方: 你好\n你: 在呢"],
        conversation_key="qq:dm:user1",
        valence=0.5,
        arousal=0.4,
    )
    second = system.get_reply_memory_bundle(
        user_id="user1",
        message_text="我们再去海边散步吧",
        history_texts=["对方: 你好\n你: 在呢"],
        conversation_key="qq:dm:user1",
        valence=0.5,
        arousal=0.4,
    )

    assert "cache_hit=False" in first.trace_summary
    assert "cache_hit=True" in second.trace_summary


def test_memory_system_reply_bundle_marks_missing_user_degradation():
    system = MemorySystem()

    bundle = system.get_reply_memory_bundle(
        user_id="",
        message_text="普通消息",
        history_texts=["对方: 你好"],
        conversation_key="",
        valence=0.1,
        arousal=0.2,
    )

    assert "reason=missing_user_id" in bundle.trace_summary


def test_memory_system_reply_bundle_logs_observable_counts_and_reason(caplog):
    system = MemorySystem()
    system.remember(
        "之前一起聊过海边",
        content={"user_id": "user1"},
        valence=0.5,
        arousal=0.3,
        phi=0.4,
    )

    with caplog.at_level(logging.DEBUG, logger="memory_system"):
        bundle = system.get_reply_memory_bundle(
            user_id="user1",
            message_text="海边",
            history_texts=["对方: 你好\n你: 在呢"],
            conversation_key="qq:dm:user1",
            valence=0.5,
            arousal=0.4,
        )

    assert bundle.trace_summary.startswith("user_id=user1")
    assert any("ReplyMemory bundle: user_id=user1" in record.message for record in caplog.records)
    assert any("conversation_key=qq:dm:user1" in record.message for record in caplog.records)
    assert any("l1_hits=1" in record.message for record in caplog.records)
    assert any("l2_hits=1" in record.message for record in caplog.records)
    assert any("l3_hits=0" in record.message for record in caplog.records)
    assert any("l1_selected=1" in record.message for record in caplog.records)
    assert any("l2_selected=1" in record.message for record in caplog.records)
    assert any("l3_selected=0" in record.message for record in caplog.records)
    assert any("fallback_reason=none" in record.message for record in caplog.records)


def test_memory_system_reply_bundle_logs_missing_user_fallback_reason(caplog):
    system = MemorySystem()

    with caplog.at_level(logging.DEBUG, logger="memory_system"):
        bundle = system.get_reply_memory_bundle(
            user_id="",
            message_text="普通消息",
            history_texts=["对方: 你好"],
            conversation_key="",
            valence=0.1,
            arousal=0.2,
        )

    assert "reason=missing_user_id" in bundle.trace_summary
    assert any("fallback_reason=missing_user_id" in record.message for record in caplog.records)


def test_response_pipeline_memory_context_falls_back_without_user_context():
    class FakeMemory:
        def get_llm_context(self, **kwargs):
            return "legacy context"

    pipeline = ResponsePipeline(memory_system=FakeMemory())
    ctx = pipeline._get_memory_context(MockState())

    assert ctx == "legacy context"