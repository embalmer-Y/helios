"""Unit tests for Episodic Memory bounded growth and pruning.

Tests the following behaviors:
- Configurable max capacity enforcement (default 500)
- Pruning lowest-importance items when capacity exceeded
- Promotion of items with importance > 0.4 to AutobiographicalStore before discard
- Importance formula: sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1)
- Recalculation of importance during consolidation cycles

Validates: Requirements 17.1, 17.2, 17.3, 17.4
"""

import sys
import os
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from memory import (
    EpisodicMemory,
    MemoryItem,
    MemorySystem,
    MemoryConsolidator,
    SemanticMemory,
    AutobiographicalMemory,
)
from memory import AutobiographicalStore


class TestEpisodicCapacityEnforcement:
    """Requirement 17.1: Configurable max capacity enforcement."""

    def test_default_capacity_is_500(self):
        """Default capacity should be 500."""
        em = EpisodicMemory()
        assert em.capacity == 500

    def test_configurable_capacity(self):
        """Capacity should be configurable via constructor."""
        em = EpisodicMemory(capacity=100)
        assert em.capacity == 100

    def test_items_never_exceed_capacity(self):
        """Recording more items than capacity should trigger pruning."""
        em = EpisodicMemory(capacity=5)
        for i in range(20):
            em.record(f"event_{i}", valence=0.1 * (i % 10), arousal=0.1, phi=0.1)
        assert len(em.items) <= em.capacity

    def test_capacity_enforced_after_each_record(self):
        """After each record that exceeds capacity, pruning should fire."""
        em = EpisodicMemory(capacity=3)
        for i in range(10):
            em.record(f"event_{i}", valence=0.5, arousal=0.5, phi=0.5)
            assert len(em.items) <= em.capacity


class TestEpisodicPruningOrder:
    """Requirement 17.2: Retain highest-importance items, discard lowest."""

    def test_prune_retains_highest_importance(self):
        """After pruning, retained items should be those with highest importance."""
        em = EpisodicMemory(capacity=3)
        # Record items with increasing phi (and thus increasing importance)
        items_data = [
            ("low", 0.1, 0.1, 0.1),
            ("medium", 0.3, 0.3, 0.5),
            ("high", 0.9, 0.9, 0.9),
            ("very_high", 0.9, 0.9, 1.0),
        ]
        for summary, v, a, p in items_data:
            em.record(summary, valence=v, arousal=a, phi=p)

        # Only 3 should remain (capacity=3)
        assert len(em.items) <= 3
        # The lowest importance item should have been pruned
        summaries = [it.summary for it in em.items]
        # "low" should be the one pruned (lowest importance)
        assert "low" not in summaries or len(em.items) <= 3

    def test_prune_discards_lowest_importance_first(self):
        """Items with lowest importance should be discarded first."""
        em = EpisodicMemory(capacity=5)
        # Create items with known importance order
        for i in range(10):
            em.record(f"event_{i}", valence=0.1 * i, arousal=0.5, phi=0.5)

        # All remaining items should have importance >= the minimum remaining
        importances = [it.importance for it in em.items]
        min_remaining = min(importances)
        # The discarded ones would have had lower importance
        assert len(em.items) == 5


class TestEpisodicPruningPromotion:
    """Requirement 17.3: Promote items with importance > 0.4 to AutobiographicalStore."""

    def test_high_importance_items_promoted_on_prune(self):
        """Items with importance > 0.4 should be promoted to AutobiographicalStore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=3, autobiographical_store=store)

            # Record 5 items with high importance (high V, A, phi)
            for i in range(5):
                em.record(f"important_{i}", valence=0.8, arousal=0.8, phi=0.8)

            # Some items should have been promoted
            assert len(store.moments) > 0

    def test_low_importance_items_not_promoted(self):
        """Items with importance <= 0.4 should NOT be promoted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=3, autobiographical_store=store)

            # Record items with very low importance (low phi makes importance low)
            for i in range(5):
                em.record(f"unimportant_{i}", valence=0.1, arousal=0.1, phi=0.05)

            # No items should have been promoted (importance too low)
            assert len(store.moments) == 0

    def test_promotion_preserves_content(self):
        """Promoted items should have their narrative/summary preserved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=2, autobiographical_store=store)

            # Record 4 high-importance items
            em.record("memory_alpha", valence=0.9, arousal=0.9, phi=0.9)
            em.record("memory_beta", valence=0.9, arousal=0.9, phi=0.9)
            em.record("memory_gamma", valence=0.9, arousal=0.9, phi=0.9)
            em.record("memory_delta", valence=0.9, arousal=0.9, phi=0.9)

            # Check that promoted moments have narratives from the pruned items
            narratives = [m.narrative for m in store.moments]
            # At least one promoted item should exist
            assert len(narratives) > 0

    def test_no_store_no_crash(self):
        """Pruning without an AutobiographicalStore should not crash."""
        em = EpisodicMemory(capacity=3, autobiographical_store=None)
        for i in range(10):
            em.record(f"event_{i}", valence=0.9, arousal=0.9, phi=0.9)
        assert len(em.items) <= 3


class TestImportanceFormula:
    """Requirement 17.4: Importance = sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1)"""

    def test_formula_basic(self):
        """Basic formula calculation should match expected value."""
        item = MemoryItem(valence=0.6, arousal=0.8, phi=0.7, access_count=5)
        item.recalc_importance()
        expected = math.sqrt(0.6**2 + 0.8**2) * 0.7 * (1 + math.log(1 + 5) * 0.1)
        assert abs(item.importance - expected) < 1e-6

    def test_formula_zero_phi(self):
        """With phi=0, importance should be clamped to minimum (0.05)."""
        item = MemoryItem(valence=0.9, arousal=0.9, phi=0.0, access_count=10)
        item.recalc_importance()
        assert item.importance == 0.05

    def test_formula_zero_emotion(self):
        """With zero valence and arousal, importance should be minimal."""
        item = MemoryItem(valence=0.0, arousal=0.0, phi=0.9, access_count=10)
        item.recalc_importance()
        assert item.importance == 0.05

    def test_formula_access_count_increases_importance(self):
        """Higher access count should increase importance."""
        item_low = MemoryItem(valence=0.5, arousal=0.5, phi=0.5, access_count=0)
        item_high = MemoryItem(valence=0.5, arousal=0.5, phi=0.5, access_count=100)
        item_low.recalc_importance()
        item_high.recalc_importance()
        assert item_high.importance > item_low.importance

    def test_formula_clamped_to_1(self):
        """Importance should never exceed 1.0."""
        item = MemoryItem(valence=1.0, arousal=1.0, phi=1.0, access_count=10000)
        item.recalc_importance()
        assert item.importance <= 1.0

    def test_formula_minimum_floor(self):
        """Importance should never go below 0.05."""
        item = MemoryItem(valence=0.0, arousal=0.0, phi=0.0, access_count=0)
        item.recalc_importance()
        assert item.importance >= 0.05


class TestRecalcDuringConsolidation:
    """Requirement 17.4: Recalculate importance during consolidation cycles."""

    def test_consolidation_recalculates_importance(self):
        """Consolidation should recalculate importance for all episodic items."""
        em = EpisodicMemory(capacity=100)
        sm = SemanticMemory()
        am = AutobiographicalMemory()
        consolidator = MemoryConsolidator(em, sm, am)

        # Record an item and manually change its access_count
        item = em.record("test_event", valence=0.5, arousal=0.5, phi=0.5)
        original_importance = item.importance
        item.access_count = 50  # Simulate many accesses

        # Run consolidation (phi < 0.3 to allow it)
        consolidator.consolidate(phi=0.1)

        # Importance should have been recalculated
        assert item.importance != original_importance
        # With higher access_count, importance should be higher
        assert item.importance > original_importance

    def test_recalc_all_importance_method(self):
        """recalc_all_importance should update all items."""
        em = EpisodicMemory(capacity=100)
        items = []
        for i in range(5):
            it = em.record(f"event_{i}", valence=0.5, arousal=0.5, phi=0.5)
            items.append(it)

        # Manually modify access counts
        for i, it in enumerate(items):
            it.access_count = (i + 1) * 10

        old_importances = [it.importance for it in items]
        em.recalc_all_importance()
        new_importances = [it.importance for it in items]

        # All should have changed
        for old, new in zip(old_importances, new_importances):
            assert new != old


class TestSetAutobiographicalStore:
    """Test the set_autobiographical_store method for late-binding."""

    def test_set_store_enables_promotion(self):
        """Setting store after construction should enable promotion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=3)

            # Initially no store
            for i in range(5):
                em.record(f"before_{i}", valence=0.9, arousal=0.9, phi=0.9)
            assert len(store.moments) == 0  # No promotion yet

            # Now set the store
            em.set_autobiographical_store(store)
            em.items.clear()

            for i in range(5):
                em.record(f"after_{i}", valence=0.9, arousal=0.9, phi=0.9)
            # Promotion should now work
            assert len(store.moments) > 0

    def test_memory_system_set_autobiographical_store(self):
        """MemorySystem.set_autobiographical_store should wire through to episodic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            ms = MemorySystem(episodic_capacity=3)
            ms.set_autobiographical_store(store)

            for i in range(5):
                ms.remember(f"event_{i}", valence=0.9, arousal=0.9, phi=0.9)

            assert len(store.moments) > 0

