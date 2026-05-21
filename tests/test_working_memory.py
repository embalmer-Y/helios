"""
Tests for WorkingMemory TTL expiration, capacity eviction, and promotion.

Validates: Requirements 13.5, 18.1, 18.2, 18.3, 18.4
"""

import time
import logging
from unittest.mock import patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_system import WorkingMemory, EpisodicMemory, MemorySystem, MemoryItem


class TestWorkingMemoryTTL:
    """Test TTL expiration during recall (Requirement 18.1)."""

    def test_items_expire_after_ttl(self):
        """Items whose age exceeds TTL should be removed during recall."""
        wm = WorkingMemory(capacity=15, default_ttl=300.0)
        # Insert item with very short TTL
        item = wm.hold("expiring item", ttl=0.01)
        assert item.id in wm.items

        # Wait for TTL to pass
        time.sleep(0.02)

        # Recall should filter out expired items
        result = wm.recall(limit=5)
        assert item.id not in wm.items
        assert len(result) == 0

    def test_non_expired_items_remain(self):
        """Items within TTL should remain after recall."""
        wm = WorkingMemory(capacity=15, default_ttl=300.0)
        item = wm.hold("still valid", ttl=9999)

        result = wm.recall(limit=5)
        assert len(result) == 1
        assert result[0].id == item.id

    def test_default_ttl_300_seconds(self):
        """Default TTL should be 300 seconds."""
        wm = WorkingMemory()
        assert wm.default_ttl == 300.0
        item = wm.hold("test item")
        assert item.ttl == 300.0


class TestWorkingMemoryCapacity:
    """Test capacity limit and oldest-item eviction (Requirement 18.2)."""

    def test_default_capacity_is_15(self):
        """Default capacity should be 15."""
        wm = WorkingMemory()
        assert wm.capacity == 15

    def test_evicts_oldest_when_at_capacity(self):
        """When capacity is reached, the oldest item should be evicted."""
        wm = WorkingMemory(capacity=3, default_ttl=300.0)
        item1 = wm.hold("first")
        item2 = wm.hold("second")
        item3 = wm.hold("third")

        assert len(wm.items) == 3

        # Adding a 4th item should evict the first (oldest)
        item4 = wm.hold("fourth")
        assert len(wm.items) == 3
        assert item1.id not in wm.items
        assert item4.id in wm.items

    def test_capacity_never_exceeded(self):
        """Working memory should never exceed its capacity."""
        wm = WorkingMemory(capacity=5, default_ttl=300.0)
        for i in range(20):
            wm.hold(f"item {i}")
        assert len(wm.items) <= 5


class TestWorkingMemoryPromotion:
    """Test promotion of important items to EpisodicMemory (Requirements 18.3, 18.4)."""

    def test_promotes_important_items_on_expiry(self):
        """Items with importance > 0.5 should be promoted to EpisodicMemory before expiry."""
        episodic = EpisodicMemory(capacity=100)
        wm = WorkingMemory(capacity=15, default_ttl=0.01, episodic_memory=episodic)

        # Create item with high importance — use high valence/arousal/phi to ensure importance > 0.5
        item = wm.hold("important thought", valence=0.9, arousal=0.9, phi=0.9)
        # Force importance > 0.5
        item.importance = 0.8

        time.sleep(0.02)
        # Recall triggers expiry + promotion
        wm.recall(limit=5)

        # Item should be promoted to episodic
        assert len(episodic.items) == 1
        assert "important thought" in episodic.items[0].summary

    def test_does_not_promote_low_importance_on_expiry(self):
        """Items with importance <= 0.5 should just expire without promotion."""
        episodic = EpisodicMemory(capacity=100)
        wm = WorkingMemory(capacity=15, default_ttl=0.01, episodic_memory=episodic)

        item = wm.hold("mundane thought", valence=0.0, arousal=0.0, phi=0.0)
        # Ensure importance is low
        item.importance = 0.1

        time.sleep(0.02)
        wm.recall(limit=5)

        # Should NOT be promoted
        assert len(episodic.items) == 0

    def test_promotes_important_items_on_capacity_eviction(self):
        """Items with importance > 0.5 should be promoted when evicted due to capacity."""
        episodic = EpisodicMemory(capacity=100)
        wm = WorkingMemory(capacity=2, default_ttl=300.0, episodic_memory=episodic)

        # Fill capacity
        item1 = wm.hold("important first item", valence=0.9, arousal=0.9, phi=0.9)
        item1.importance = 0.8  # Force high importance
        wm.hold("second item")

        # Adding a third should evict item1 (oldest) → promoted
        wm.hold("third item")

        assert len(episodic.items) == 1
        assert "important first item" in episodic.items[0].summary

    def test_logs_debug_on_promotion(self, caplog):
        """Debug message should be logged when an item is promoted."""
        episodic = EpisodicMemory(capacity=100)
        wm = WorkingMemory(capacity=15, default_ttl=0.01, episodic_memory=episodic)

        item = wm.hold("will be promoted", valence=0.9, arousal=0.9, phi=0.9)
        item.importance = 0.8

        time.sleep(0.02)
        with caplog.at_level(logging.DEBUG, logger="memory_system"):
            wm.recall(limit=5)

        assert any("promoted" in record.message.lower() for record in caplog.records)

    def test_logs_debug_on_expiration(self, caplog):
        """Debug message should be logged when an item expires."""
        wm = WorkingMemory(capacity=15, default_ttl=0.01)

        wm.hold("will expire", valence=0.0, arousal=0.0, phi=0.0)

        time.sleep(0.02)
        with caplog.at_level(logging.DEBUG, logger="memory_system"):
            wm.recall(limit=5)

        assert any("expired" in record.message.lower() for record in caplog.records)


class TestWorkingMemoryIntegration:
    """Test MemorySystem correctly wires episodic reference."""

    def test_memory_system_wires_episodic_to_working(self):
        """MemorySystem should wire episodic memory into working memory for promotion."""
        ms = MemorySystem(working_capacity=5, episodic_capacity=100)
        assert ms.working._episodic is ms.episodic

    def test_hold_via_memory_system_promotes_on_expiry(self):
        """Items held via MemorySystem.hold() with high importance promote on expiry."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=100)
        ms.working.default_ttl = 0.01  # very short for test

        item = ms.hold("important via system", valence=0.9, arousal=0.9, phi=0.9)
        item.importance = 0.8

        time.sleep(0.02)
        ms.working.recall(limit=5)

        # Should have been promoted to episodic
        assert any("important via system" in ep.summary for ep in ms.episodic.items)


class TestWorkingMemoryHoldQQMessages:
    """Test that QQ messages can be held in working memory (Requirement 13.5)."""

    def test_hold_message_with_sec_result(self):
        """Working memory should hold QQ messages with SEC evaluation results."""
        ms = MemorySystem()
        sec_result = {
            "novelty": 0.6,
            "pleasantness": 0.4,
            "goal_relevance": 0.7,
        }
        item = ms.hold(
            summary="QQ [user123]: Hello there",
            content={"text": "Hello there", "user_id": "user123", "sec_result": sec_result},
            valence=sec_result.get("pleasantness", 0),
            arousal=sec_result.get("novelty", 0),
            phi=0.3,
        )
        assert item.id in ms.working.items
        assert item.content["sec_result"] == sec_result
        assert item.content["text"] == "Hello there"
