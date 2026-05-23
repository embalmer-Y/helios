"""Focused tests for the structured cross-layer memory retrieval contract."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalStore, MemorySearchQuery, MemorySystem


def test_memory_system_search_memories_returns_structured_hits(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    system.hold("I am thinking about the sea", valence=0.2, arousal=0.4, phi=0.1)
    system.learn("topic.sea", "The sea is calming", tags=["nature"])
    system.remember("Walked by the sea", valence=0.6, arousal=0.5, phi=0.4)

    hits = system.search_memories(text="sea", valence=0.5, arousal=0.4, limit=4)

    assert hits
    assert all(hit.memory_id for hit in hits)
    assert any(hit.memory_type == "semantic" for hit in hits)
    assert any(hit.memory_type == "episodic" for hit in hits)


def test_memory_system_builds_autobio_context_via_query_object(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    store.record(
        panksepp={"CARE": 0.7},
        valence=0.5,
        arousal=0.4,
        dominant="CARE",
        phi=0.4,
        narrative="Talked about the sea with user1",
        event_trigger="sea",
        source="organic",
    )
    system = MemorySystem(autobiographical_store=store)

    context = system.get_autobio_context(
        topic_text="sea",
        user_id="user1",
        history_texts=["we talked about waves"],
        limit=3,
    )

    assert "相关记忆:" in context
    assert "Talked about the sea with user1" in context


def test_memory_system_query_object_accepts_vector_strategy_without_provider(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    system.learn("topic.stars", "Stars are bright", tags=["night"])

    hits = system.retriever.search(
        MemorySearchQuery(
            text="stars",
            limit=3,
            scopes=("semantic",),
            strategies=("keyword", "vector"),
        )
    )

    assert hits
    assert any(hit.memory_type == "semantic" for hit in hits)


def test_memory_system_builds_llm_context_from_unified_query_contract(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    store.record(
        panksepp={"CARE": 0.6},
        valence=0.4,
        arousal=0.3,
        dominant="CARE",
        phi=0.5,
        narrative="Remembered the sea breeze during a quiet walk",
        event_trigger="sea",
        source="organic",
    )
    system = MemorySystem(autobiographical_store=store)
    system.hold("I am still thinking about the sea", valence=0.2, arousal=0.3, phi=0.1)
    system.remember("Walked along the sea at dusk", valence=0.5, arousal=0.4, phi=0.4)

    context = system.retriever.build_llm_context(
        MemorySearchQuery(
            text="sea",
            user_id="user1",
            history_texts=("we talked about waves",),
            valence=0.4,
            arousal=0.3,
            limit=5,
            scopes=("working", "episodic", "autobiographical"),
            strategies=("keyword", "affect", "related"),
        )
    )

    assert "[最近在想]" in context
    assert "[相似经历]" in context
    assert "[我的故事]" in context


def test_memory_system_autobio_search_falls_back_to_runtime_timeline_without_store_query(tmp_path):
    _ = tmp_path
    system = MemorySystem(autobiographical_store=None)
    system.autobiographical.record_moment(
        summary="A quiet autobiographical fallback memory",
        phi=0.4,
        valence=0.3,
        content={"source": "timeline"},
    )

    hits = system.retriever.search(
        MemorySearchQuery(
            text="quiet",
            limit=3,
            scopes=("autobiographical",),
            strategies=("related",),
        )
    )

    assert len(hits) == 1
    assert hits[0].memory_type == "autobiographical"
    assert hits[0].source == "autobiographical_memory"