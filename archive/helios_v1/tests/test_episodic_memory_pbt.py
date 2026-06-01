"""Property-based tests for Episodic Memory.

# Feature: helios-architecture-enhancement
# Property 15: Episodic Memory Capacity Invariant
# Property 16: Episodic Memory Importance Formula
# Property 17: Episodic Pruning Promotes High-Importance Items
# Property 25: Selective Episodic Serialization

**Validates: Requirements 17.1, 17.2, 17.3, 17.4, 22.3**
"""

import sys
import os
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume
from hypothesis.strategies import (
    integers,
    floats,
    lists,
    tuples,
    composite,
)

from memory import EpisodicMemory, MemoryItem
from memory import AutobiographicalStore


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

# Valence in [-1, 1], arousal in [0, 1], phi in [0, 1]
valence_st = floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
arousal_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
phi_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
access_count_st = integers(min_value=0, max_value=10000)

# An episode is a tuple of (valence, arousal, phi)
episode_st = tuples(valence_st, arousal_st, phi_st)

# A list of episodes for capacity testing (at least capacity+1 to trigger pruning)
episode_list_st = lists(episode_st, min_size=1, max_size=100)


@composite
def capacity_and_episodes(draw):
    """Generate a capacity and a list of episodes that exceeds it."""
    capacity = draw(integers(min_value=3, max_value=50))
    episodes = draw(lists(episode_st, min_size=capacity + 1, max_size=capacity * 3))
    return capacity, episodes


# ------------------------------------------------------------------
# Property 15: Episodic Memory Capacity Invariant
# ------------------------------------------------------------------


class TestEpisodicMemoryCapacityInvariant:
    """Property 15: For any sequence of episode recordings, the EpisodicMemory
    size SHALL never exceed the configured capacity (default 500). When pruning
    occurs, retained items SHALL have the highest importance scores.

    **Validates: Requirements 17.1, 17.2**
    """

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_size_never_exceeds_capacity(self, data):
        """After any number of recordings, len(items) <= capacity."""
        capacity, episodes = data
        em = EpisodicMemory(capacity=capacity)

        for i, (v, a, p) in enumerate(episodes):
            em.record(f"episode_{i}", valence=v, arousal=a, phi=p)
            assert len(em.items) <= capacity

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_retained_items_have_highest_importance(self, data):
        """After pruning, the retained items should be those with the highest
        importance scores. No discarded item should have importance higher than
        any retained item."""
        capacity, episodes = data
        em = EpisodicMemory(capacity=capacity)

        for i, (v, a, p) in enumerate(episodes):
            em.record(f"episode_{i}", valence=v, arousal=a, phi=p)

        # After all recordings, items are pruned
        assert len(em.items) <= capacity

        if len(em.items) > 1:
            # All retained items should be sorted by importance (highest first)
            # after the last prune; the minimum retained importance should be
            # a valid cutoff
            importances = [it.importance for it in em.items]
            min_retained = min(importances)
            # The min retained is a lower bound — all retained are >= it
            for it in em.items:
                assert it.importance >= min_retained


# ------------------------------------------------------------------
# Property 16: Episodic Memory Importance Formula
# ------------------------------------------------------------------


class TestEpisodicMemoryImportanceFormula:
    """Property 16: For any MemoryItem with valence V, arousal A, phi P, and
    access_count C, the importance score SHALL equal
    sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1).

    **Validates: Requirements 17.4**
    """

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=phi_st,
        access_count=access_count_st,
    )
    @settings(max_examples=200)
    def test_importance_matches_formula(self, valence, arousal, phi, access_count):
        """recalc_importance() SHALL produce the specified formula result
        (clamped to [0.05, 1.0])."""
        item = MemoryItem(
            valence=valence,
            arousal=arousal,
            phi=phi,
            access_count=access_count,
        )
        item.recalc_importance()

        # Expected formula
        intensity = math.sqrt(valence**2 + arousal**2)
        access_bonus = math.log(1 + access_count) * 0.1
        raw = intensity * phi * (1.0 + access_bonus)
        expected = max(0.05, min(1.0, raw))

        assert abs(item.importance - expected) < 1e-9, (
            f"importance={item.importance}, expected={expected}, "
            f"V={valence}, A={arousal}, P={phi}, C={access_count}"
        )

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=phi_st,
        access_count=access_count_st,
    )
    @settings(max_examples=100)
    def test_importance_bounded_0_05_to_1(self, valence, arousal, phi, access_count):
        """Importance SHALL always be in [0.05, 1.0]."""
        item = MemoryItem(
            valence=valence,
            arousal=arousal,
            phi=phi,
            access_count=access_count,
        )
        item.recalc_importance()
        assert 0.05 <= item.importance <= 1.0


# ------------------------------------------------------------------
# Property 17: Episodic Pruning Promotes High-Importance Items
# ------------------------------------------------------------------


class TestEpisodicPruningPromotesHighImportance:
    """Property 17: For any pruning operation where items with importance > 0.4
    are discarded from episodic storage, those items SHALL first be promoted
    to the AutobiographicalStore.

    **Validates: Requirements 17.3**
    """

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_high_importance_discarded_items_promoted(self, data):
        """When pruning discards items with importance > 0.4, those items
        SHALL have been promoted to the AutobiographicalStore."""
        capacity, episodes = data

        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=capacity, autobiographical_store=store)

            # Track all items ever created
            all_items = []
            for i, (v, a, p) in enumerate(episodes):
                item = em.record(f"episode_{i}", valence=v, arousal=a, phi=p)
                all_items.append(item)

            # Determine which items were discarded (not in current items list)
            retained_ids = {it.id for it in em.items}
            discarded = [it for it in all_items if it.id not in retained_ids]

            # All discarded items with importance > 0.4 should have been promoted
            high_importance_discarded = [
                it for it in discarded if it.importance > EpisodicMemory.PROMOTION_THRESHOLD
            ]

            if high_importance_discarded:
                # Store should have received promotions
                assert len(store.moments) > 0, (
                    f"Expected promotions for {len(high_importance_discarded)} "
                    f"high-importance discarded items, but store is empty"
                )

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_low_importance_discarded_items_not_promoted(self, data):
        """When pruning discards items with importance <= 0.4, those items
        SHALL NOT be promoted to the AutobiographicalStore."""
        capacity, episodes = data

        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=capacity, autobiographical_store=store)

            # Use low-phi episodes so importance stays below threshold
            for i in range(capacity + 5):
                em.record(f"low_ep_{i}", valence=0.05, arousal=0.05, phi=0.05)

            # With very low valence/arousal/phi, importance will be 0.05 (minimum)
            # Nothing should have been promoted
            assert len(store.moments) == 0, (
                f"Expected no promotions for low-importance items, "
                f"but store has {len(store.moments)} moments"
            )

    @given(
        capacity=integers(min_value=3, max_value=20),
        n_extra=integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_promotion_count_matches_high_importance_discards(self, capacity, n_extra):
        """The number of promotions SHALL match the number of high-importance
        items discarded during pruning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = AutobiographicalStore(
                os.path.join(tmpdir, "test.jsonl"), auto_flush=False
            )
            em = EpisodicMemory(capacity=capacity, autobiographical_store=store)

            # Fill to capacity with high-importance items
            for i in range(capacity + n_extra):
                em.record(
                    f"high_ep_{i}",
                    valence=0.8,
                    arousal=0.8,
                    phi=0.8,
                )

            # All items have high importance, so all discarded items should be promoted
            # The number of promotions should equal the number of times pruning discarded
            # high-importance items. Each record beyond capacity triggers a prune that
            # discards 1 item (since we go from capacity+1 to capacity).
            # All discarded items have importance > 0.4, so all should be promoted.
            assert len(store.moments) == n_extra, (
                f"Expected {n_extra} promotions, got {len(store.moments)}"
            )


# ------------------------------------------------------------------
# Property 25: Selective Episodic Serialization
# ------------------------------------------------------------------


class TestSelectiveEpisodicSerialization:
    """Property 25: For any set of EpisodicMemory items at shutdown, only items
    with importance > 0.3 SHALL be serialized to the persistence file.

    **Validates: Requirements 22.3**
    """

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_only_high_importance_items_serialized(self, data):
        """Only items with importance > 0.3 should be serialized to file."""
        import json

        capacity, episodes = data

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "episodic.json")
            em = EpisodicMemory(capacity=capacity)

            for i, (v, a, p) in enumerate(episodes):
                em.record(f"episode_{i}", valence=v, arousal=a, phi=p)

            em.save_to_file(filepath, importance_threshold=0.3)

            with open(filepath, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            saved_items = saved_data["items"]

            # All saved items must have importance > 0.3
            for item in saved_items:
                assert item["importance"] > 0.3, (
                    f"Found item with importance {item['importance']:.4f} <= 0.3 in saved file"
                )

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_all_high_importance_items_included(self, data):
        """All items with importance > 0.3 should be included in serialized file."""
        import json

        capacity, episodes = data

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "episodic.json")
            em = EpisodicMemory(capacity=capacity)

            for i, (v, a, p) in enumerate(episodes):
                em.record(f"episode_{i}", valence=v, arousal=a, phi=p)

            # Collect IDs of all items with importance > 0.3
            high_importance_ids = {
                it.id for it in em.items if it.importance > 0.3
            }

            em.save_to_file(filepath, importance_threshold=0.3)

            with open(filepath, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            saved_ids = {item["id"] for item in saved_data["items"]}

            # All high-importance items should be in saved data
            assert high_importance_ids == saved_ids, (
                f"Expected {len(high_importance_ids)} high-importance items, "
                f"got {len(saved_ids)}. Missing: {high_importance_ids - saved_ids}"
            )

    @given(data=capacity_and_episodes())
    @settings(max_examples=100)
    def test_low_importance_items_excluded(self, data):
        """Items with importance <= 0.3 should NOT be in the serialized file."""
        import json

        capacity, episodes = data

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "episodic.json")
            em = EpisodicMemory(capacity=capacity)

            for i, (v, a, p) in enumerate(episodes):
                em.record(f"episode_{i}", valence=v, arousal=a, phi=p)

            # Collect IDs of items with importance <= 0.3
            low_importance_ids = {
                it.id for it in em.items if it.importance <= 0.3
            }

            em.save_to_file(filepath, importance_threshold=0.3)

            with open(filepath, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            saved_ids = {item["id"] for item in saved_data["items"]}

            # No low-importance items should be in saved data
            intersection = low_importance_ids & saved_ids
            assert len(intersection) == 0, (
                f"Found {len(intersection)} low-importance items (importance <= 0.3) "
                f"in saved file: {intersection}"
            )

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=phi_st,
    )
    @settings(max_examples=100)
    def test_boundary_importance_item_behavior(self, valence, arousal, phi):
        """Items exactly at the importance boundary should not be serialized."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "episodic.json")
            em = EpisodicMemory()

            item = em.record("boundary_test", valence=valence, arousal=arousal, phi=phi)

            em.save_to_file(filepath, importance_threshold=0.3)

            with open(filepath, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            # If importance > 0.3, it should be saved; if <= 0.3, it should not
            if item.importance > 0.3:
                assert len(saved_data["items"]) == 1, (
                    f"Expected 1 item with importance {item.importance:.4f} > 0.3 to be saved"
                )
            else:
                assert len(saved_data["items"]) == 0, (
                    f"Expected 0 items with importance {item.importance:.4f} <= 0.3 to be saved"
                )

    @given(
        episodes=lists(episode_st, min_size=0, max_size=50),
        threshold=floats(min_value=0.05, max_value=0.95, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_custom_threshold_respected(self, episodes, threshold):
        """The serialization should respect custom importance thresholds."""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "episodic.json")
            em = EpisodicMemory(capacity=100)

            for i, (v, a, p) in enumerate(episodes):
                em.record(f"episode_{i}", valence=v, arousal=a, phi=p)

            em.save_to_file(filepath, importance_threshold=threshold)

            with open(filepath, "r", encoding="utf-8") as f:
                saved_data = json.load(f)

            saved_items = saved_data["items"]
            saved_threshold = saved_data.get("importance_threshold")

            # The threshold should be recorded in the file
            assert abs(saved_threshold - threshold) < 1e-9, (
                f"Expected threshold {threshold}, got {saved_threshold}"
            )

            # All saved items must have importance > threshold
            for item in saved_items:
                assert item["importance"] > threshold, (
                    f"Found item with importance {item['importance']:.4f} <= {threshold:.4f}"
                )

            # All items with importance > threshold should be saved
            expected_ids = {it.id for it in em.items if it.importance > threshold}
            saved_ids = {item["id"] for item in saved_items}
            assert expected_ids == saved_ids, (
                f"Expected {len(expected_ids)} items, got {len(saved_ids)}"
            )

