"""Property-based tests for Working Memory bounded lifecycle.

# Feature: helios-architecture-enhancement, Property 18: Working Memory Bounded Lifecycle

**Validates: Requirements 18.1, 18.2, 18.3**
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    integers,
    floats,
    lists,
    tuples,
    composite,
    just,
)

from memory_system import WorkingMemory, EpisodicMemory, MemoryItem


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------


@composite
def working_memory_params(draw):
    """Generate valid WorkingMemory capacity and TTL parameters."""
    capacity = draw(integers(min_value=1, max_value=30))
    default_ttl = draw(floats(min_value=0.01, max_value=600.0, allow_nan=False, allow_infinity=False))
    return capacity, default_ttl


@composite
def item_with_importance(draw):
    """Generate parameters for a memory item with specific importance characteristics."""
    valence = draw(floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    arousal = draw(floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    phi = draw(floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    return valence, arousal, phi


# ------------------------------------------------------------------
# Property 18: Working Memory Bounded Lifecycle
# ------------------------------------------------------------------


class TestWorkingMemoryBoundedLifecycle:
    """Property 18: For any WorkingMemory instance, items with age exceeding
    TTL SHALL be expired on recall. When capacity (default 15) is reached,
    the oldest item SHALL be evicted. Items with importance > 0.5 about to
    expire SHALL be promoted to EpisodicMemory.
    """

    # --- Requirement 18.1: TTL Expiration ---

    @given(
        capacity=integers(min_value=1, max_value=30),
        num_items=integers(min_value=1, max_value=15),
    )
    @settings(max_examples=100)
    def test_expired_items_removed_on_recall(self, capacity: int, num_items: int):
        """Items with age exceeding TTL SHALL be expired on recall.

        For any number of items inserted with a very short TTL, after the TTL
        has elapsed, recall SHALL return none of those items and the internal
        store SHALL be empty.
        """
        assume(num_items <= capacity)
        wm = WorkingMemory(capacity=capacity, default_ttl=0.001)

        for i in range(num_items):
            wm.hold(f"item_{i}")

        # Wait for TTL to elapse
        time.sleep(0.01)

        result = wm.recall(limit=capacity)

        # All items should have been expired
        assert len(result) == 0
        assert len(wm.items) == 0

    @given(
        capacity=integers(min_value=2, max_value=20),
        num_short_ttl=integers(min_value=1, max_value=10),
        num_long_ttl=integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    def test_only_expired_items_removed(self, capacity: int, num_short_ttl: int, num_long_ttl: int):
        """Only items whose age exceeds TTL are expired; others remain.

        For any mix of short-TTL and long-TTL items, after the short TTL
        elapses, recall SHALL remove only the expired items.
        """
        assume(num_short_ttl + num_long_ttl <= capacity)
        wm = WorkingMemory(capacity=capacity, default_ttl=9999.0)

        # Insert short-TTL items
        short_ids = set()
        for i in range(num_short_ttl):
            item = wm.hold(f"short_{i}", ttl=0.001)
            short_ids.add(item.id)

        # Insert long-TTL items
        long_ids = set()
        for i in range(num_long_ttl):
            item = wm.hold(f"long_{i}", ttl=9999.0)
            long_ids.add(item.id)

        # Wait for short TTL to elapse
        time.sleep(0.01)

        wm.recall(limit=capacity)

        # Short-TTL items should be gone, long-TTL items remain
        remaining_ids = set(wm.items.keys())
        assert short_ids.isdisjoint(remaining_ids), "Expired items should be removed"
        assert long_ids.issubset(remaining_ids), "Non-expired items should remain"

    # --- Requirement 18.2: Capacity Eviction ---

    @given(
        capacity=integers(min_value=1, max_value=20),
        num_insertions=integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_capacity_never_exceeded(self, capacity: int, num_insertions: int):
        """When capacity is reached, items SHALL be evicted to maintain the bound.

        For any sequence of insertions into a WorkingMemory with a given capacity,
        the number of items SHALL never exceed the capacity.
        """
        wm = WorkingMemory(capacity=capacity, default_ttl=9999.0)

        for i in range(num_insertions):
            wm.hold(f"item_{i}")
            assert len(wm.items) <= capacity

    @given(capacity=integers(min_value=1, max_value=15))
    @settings(max_examples=100)
    def test_oldest_item_evicted_on_capacity(self, capacity: int):
        """When capacity is reached, the oldest item SHALL be evicted.

        For any capacity, inserting (capacity + 1) items results in the first
        item being evicted while the last `capacity` items remain.
        """
        wm = WorkingMemory(capacity=capacity, default_ttl=9999.0)

        items = []
        for i in range(capacity + 1):
            item = wm.hold(f"item_{i}")
            items.append(item)

        # The first item (oldest) should have been evicted
        assert items[0].id not in wm.items
        # The last `capacity` items should all be present
        for item in items[1:]:
            assert item.id in wm.items

    # --- Requirement 18.3: Promotion on Expiry ---

    @given(
        capacity=integers(min_value=1, max_value=15),
        num_important=integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_important_items_promoted_on_ttl_expiry(self, capacity: int, num_important: int):
        """Items with importance > 0.5 about to expire SHALL be promoted to EpisodicMemory.

        For any number of high-importance items that expire via TTL, each one
        SHALL be promoted to EpisodicMemory.
        """
        assume(num_important <= capacity)
        episodic = EpisodicMemory(capacity=500)
        wm = WorkingMemory(capacity=capacity, default_ttl=0.001, episodic_memory=episodic)

        for i in range(num_important):
            item = wm.hold(f"important_{i}", valence=0.9, arousal=0.9, phi=0.9)
            item.importance = 0.8  # Force importance > 0.5

        # Wait for TTL
        time.sleep(0.01)
        wm.recall(limit=capacity)

        # All important items should have been promoted
        assert len(episodic.items) == num_important
        for i in range(num_important):
            assert any(f"important_{i}" in ep.summary for ep in episodic.items)

    @given(
        capacity=integers(min_value=1, max_value=15),
        num_unimportant=integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100)
    def test_unimportant_items_not_promoted_on_expiry(self, capacity: int, num_unimportant: int):
        """Items with importance <= 0.5 SHALL NOT be promoted on TTL expiry.

        For any number of low-importance items that expire, none SHALL appear
        in EpisodicMemory.
        """
        assume(num_unimportant <= capacity)
        episodic = EpisodicMemory(capacity=500)
        wm = WorkingMemory(capacity=capacity, default_ttl=0.001, episodic_memory=episodic)

        for i in range(num_unimportant):
            item = wm.hold(f"unimportant_{i}", valence=0.0, arousal=0.0, phi=0.0)
            item.importance = 0.1  # Force importance <= 0.5

        # Wait for TTL
        time.sleep(0.01)
        wm.recall(limit=capacity)

        # No items should have been promoted
        assert len(episodic.items) == 0

    @given(capacity=integers(min_value=2, max_value=10))
    @settings(max_examples=100)
    def test_important_items_promoted_on_capacity_eviction(self, capacity: int):
        """Items with importance > 0.5 SHALL be promoted to EpisodicMemory
        when evicted due to capacity limit.

        For any capacity, when a high-importance item is evicted by a new
        insertion exceeding capacity, it SHALL be promoted.
        """
        episodic = EpisodicMemory(capacity=500)
        wm = WorkingMemory(capacity=capacity, default_ttl=9999.0, episodic_memory=episodic)

        # Fill to capacity with the first item having high importance
        first_item = wm.hold("important_evictee", valence=0.9, arousal=0.9, phi=0.9)
        first_item.importance = 0.8  # Force importance > 0.5

        for i in range(capacity - 1):
            wm.hold(f"filler_{i}")

        # Trigger eviction by exceeding capacity
        wm.hold("trigger_eviction")

        # The first (oldest, important) item should have been promoted
        assert len(episodic.items) == 1
        assert "important_evictee" in episodic.items[0].summary
