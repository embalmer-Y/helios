"""Focused tests for the structured cross-layer memory retrieval contract."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalStore, MemorySearchQuery, MemorySystem


def test_memory_system_exposes_public_four_tier_semantics(tmp_path):
    _ = tmp_path
    system = MemorySystem()

    tiers = system.get_public_memory_tiers()

    assert [tier.tier_name for tier in tiers] == [
        "short-term",
        "mid-term",
        "long-term",
        "autobiographical",
    ]
    assert tiers[0].implementation_scopes == ("working",)
    assert tiers[0].capacity_limit == 15
    assert tiers[1].implementation_scopes == ("episodic",)
    assert tiers[2].implementation_scopes == ("semantic",)
    assert tiers[3].implementation_scopes == ("autobiographical",)


def test_memory_system_clamps_short_term_capacity_to_small_boundary(tmp_path):
    _ = tmp_path
    system = MemorySystem(working_capacity=30)

    snapshots = {snapshot.tier_name: snapshot for snapshot in system.get_public_memory_tier_snapshots()}

    assert system.working.capacity == 15
    assert snapshots["short-term"].capacity_limit == 15
    assert snapshots["short-term"].boundary_ok is True


def test_memory_system_tier_snapshots_bind_to_existing_implementations(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    system.hold("temporary thought fragment", valence=0.2, arousal=0.3, phi=0.1)
    system.remember("recent episodic trace", valence=0.5, arousal=0.4, phi=0.3)
    system.learn("topic.memory", "memory tiers are structured", tags=["architecture"])
    store.record(
        panksepp={"CARE": 0.6},
        valence=0.4,
        arousal=0.3,
        dominant="CARE",
        phi=0.5,
        narrative="An autobiographical moment about remembering structure",
        event_trigger="memory",
        source="organic",
    )

    snapshots = {snapshot.tier_name: snapshot for snapshot in system.get_public_memory_tier_snapshots()}

    assert snapshots["short-term"].item_count == 1
    assert snapshots["mid-term"].item_count == 1
    assert snapshots["long-term"].item_count == 1
    assert snapshots["autobiographical"].item_count == 1


def test_memory_system_builds_directed_retrieval_query_plan_from_stimulus_and_recall_intent(tmp_path):
    _ = tmp_path
    system = MemorySystem()

    plan = system.build_retrieval_query_plan(
        current_stimuli=[{"text": "the sea breeze is back"}],
        recall_intent="remember our last walk by the sea",
        limit=4,
    )

    assert plan.current_stimulus[0]["text"] == "the sea breeze is back"
    assert plan.recall_intent == "remember our last walk by the sea"
    assert "the sea breeze is back" in plan.query_text
    assert "remember our last walk by the sea" in plan.query_text
    assert plan.target_tiers == ("mid-term", "long-term", "autobiographical")


def test_memory_system_directed_retrieval_returns_tiered_bundle(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    system.hold("short-term sea fragment", valence=0.2, arousal=0.3, phi=0.1)
    system.remember("Walked by the sea at dusk", valence=0.6, arousal=0.4, phi=0.5)
    system.learn("topic.sea", "The sea helps Helios think calmly", tags=["nature"])
    store.record(
        panksepp={"CARE": 0.7},
        valence=0.5,
        arousal=0.4,
        dominant="CARE",
        phi=0.4,
        narrative="Talked about the sea during a quiet shared walk",
        event_trigger="sea",
        source="organic",
    )
    plan = system.build_retrieval_query_plan(
        current_stimuli=[{"text": "sea"}],
        recall_intent="walk",
        limit=3,
    )

    bundle = system.directed_retrieval(plan, valence=0.5, arousal=0.4)

    assert len(bundle.short_term_context) == 1
    assert any(hit.memory_type == "episodic" for hit in bundle.mid_term_hits)
    assert any(hit.memory_type == "semantic" for hit in bundle.long_term_hits)
    assert any(hit.memory_type == "autobiographical" for hit in bundle.autobiographical_hits)
    assert {trace.tier_name for trace in bundle.selection_trace} == {"mid-term", "long-term", "autobiographical"}


def test_memory_system_directed_retrieval_plan_works_without_recall_intent(tmp_path):
    _ = tmp_path
    system = MemorySystem()

    plan = system.build_retrieval_query_plan(
        current_stimuli=[{"summary": "novel signal"}],
        recall_intent="",
        limit=2,
    )

    assert plan.recall_intent == ""
    assert plan.query_text == "novel signal"


def test_memory_system_directed_retrieval_exposes_rule_based_sec_trace(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    system.remember("Walked by the sea at dusk", valence=0.6, arousal=0.4, phi=0.5)
    system.learn("topic.sea", "The sea helps Helios think calmly", tags=["nature"])
    store.record(
        panksepp={"CARE": 0.7},
        valence=0.5,
        arousal=0.4,
        dominant="CARE",
        phi=0.4,
        narrative="Talked about the sea during a quiet shared walk",
        event_trigger="sea",
        source="organic",
    )
    plan = system.build_retrieval_query_plan(
        current_stimuli=[{"text": "sea"}],
        recall_intent="walk",
        limit=2,
    )

    bundle = system.directed_retrieval(plan, valence=0.5, arousal=0.4)

    assert bundle.retrieval_sec_trace
    assert all(result.candidate_id for result in bundle.retrieval_sec_trace)
    assert any("strategy=rule_based_fallback" in result.reason for result in bundle.retrieval_sec_trace)
    assert any(result.selected for result in bundle.retrieval_sec_trace)


def test_memory_system_get_autobio_context_uses_directed_retrieval_contract(tmp_path):
    store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
    system = MemorySystem(autobiographical_store=store)
    store.record(
        panksepp={"CARE": 0.7},
        valence=0.5,
        arousal=0.4,
        dominant="CARE",
        phi=0.4,
        narrative="Talked about the sea during a quiet shared walk",
        event_trigger="sea",
        source="organic",
    )

    context = system.get_autobio_context(
        topic_text="sea",
        user_id="user1",
        history_texts=["we talked about walking by the sea"],
        limit=3,
    )

    assert "相关记忆:" in context
    assert "Talked about the sea during a quiet shared walk" in context


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