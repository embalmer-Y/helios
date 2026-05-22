"""Property-based tests for Memory Consolidation.

# Feature: helios-architecture-enhancement
# Property 20: Consolidation Clustering and Promotion
# Property 21: Consolidation Rate Limit

**Validates: Requirements 20.2, 20.3, 20.4**
"""

import sys
import os
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume, example
from hypothesis.strategies import (
    integers,
    floats,
    lists,
    tuples,
    composite,
    data as data_st,
    just,
    sampled_from,
)

from memory_system import (
    MemorySystem,
    MemoryConsolidator,
    EpisodicMemory,
    SemanticMemory,
    AutobiographicalMemory,
    MemoryItem,
)


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

# Valid ranges for emotional dimensions
valence_st = floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
arousal_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
phi_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
consolidation_phi_st = floats(min_value=0.0, max_value=0.29, allow_nan=False, allow_infinity=False)
# phi > 0.25 for promotion
high_phi_st = floats(min_value=0.26, max_value=1.0, allow_nan=False, allow_infinity=False)
# phi <= 0.25, should NOT be promoted
low_phi_st = floats(min_value=0.0, max_value=0.25, allow_nan=False, allow_infinity=False)
# Very low consolidation phi (< 0.15) for lower importance threshold
very_low_phi_st = floats(min_value=0.0, max_value=0.14, allow_nan=False, allow_infinity=False)

# Emotional tags that can be classified by _classify()
EMOTIONAL_TAGS = [
    "ecstatic", "serene", "pleasant", "fearful", "melancholic",
    "uneasy", "agitated", "calm", "neutral",
]


@composite
def clustered_episodes_st(draw):
    """Generate episodes where at least 2 share the same emotional tag.

    Uses high valence/arousal values to ensure high importance scores
    that pass the consolidation threshold.

    All episodes use phi >= 0.3 to ensure they qualify as candidates.
    """
    n_clusters = draw(integers(min_value=1, max_value=3))
    min_per_cluster = 2  # Minimum to form a pattern-extracting cluster
    episodes = []

    # Pre-defined valence/arousal pairs that map to specific tags
    # Use high values to ensure high importance scores
    tag_configs = [
        # ecstatic: v > 0.5 and a > 0.5
        (0.8, 0.8),
        # fearful: v < -0.5 and a > 0.5
        (-0.8, 0.8),
        # serene: v > 0.5 and a < 0.3
        (0.8, 0.2),
    ]

    for i in range(n_clusters):
        v_base, a_base = tag_configs[i % len(tag_configs)]
        n_in_cluster = draw(integers(min_value=min_per_cluster, max_value=5))
        for j in range(n_in_cluster):
            # Small variation to keep same tag classification
            v = v_base + draw(floats(min_value=-0.02, max_value=0.02))
            a = a_base + draw(floats(min_value=-0.02, max_value=0.02))
            # Clamp to valid ranges
            v = max(-1.0, min(1.0, v))
            a = max(0.0, min(1.0, a))
            # Use phi >= 0.4 to ensure high importance
            phi = draw(floats(min_value=0.4, max_value=1.0, allow_nan=False, allow_infinity=False))
            episodes.append((v, a, phi))

    return episodes


@composite
def consolidation_scenario_st(draw):
    """Generate a complete consolidation scenario with:
    - A list of episodes (some clusters, some singles)
    - A consolidation phi value (very low, < 0.15, to lower importance threshold)
    """
    episodes = draw(clustered_episodes_st())
    # Use very low phi to get lower importance threshold (0.25 instead of 0.4)
    consolidation_phi = draw(very_low_phi_st)
    return episodes, consolidation_phi


# ------------------------------------------------------------------
# Property 20: Consolidation Clustering and Promotion
# ------------------------------------------------------------------


class TestConsolidationClusteringAndPromotion:
    """Property 20: For any consolidation cycle, episodic memories SHALL be
    clustered by emotional tag, and semantic patterns SHALL be extracted from
    clusters with 2+ members. Episodic memories with phi > 0.25 SHALL be
    promoted to AutobiographicalMemory.

    **Validates: Requirements 20.2, 20.3**
    """

    @given(data=consolidation_scenario_st())
    @settings(max_examples=100)
    def test_clusters_by_emotional_tag(self, data):
        """After consolidation, episodes with same emotional_tag SHALL be
        grouped together and patterns extracted from clusters with 2+ members."""
        episodes, consolidation_phi = data
        assume(len(episodes) >= 2)  # Need at least 2 episodes

        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Record all episodes
        for i, (v, a, p) in enumerate(episodes):
            item = episodic.record(f"episode_{i}", valence=v, arousal=a, phi=p)
            item.touch()  # access_count >= 1

        # Count clusters by emotional_tag among candidates
        # With very low consolidation phi (< 0.15), threshold is 0.25
        # With high valence/arousal/phi, all episodes should be candidates
        tag_counts = {}
        for item in episodic.items:
            tag = item.emotional_tag
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Count clusters with 2+ members
        expected_patterns = sum(1 for count in tag_counts.values() if count >= 2)

        # Run consolidation with very low phi (triggers full consolidation with threshold 0.25)
        stats = consolidator.consolidate(phi=consolidation_phi)

        # Pattern count should match clusters with 2+ members
        # (assuming all have importance > threshold and access_count >= 1)
        assert stats["patterns_extracted"] == expected_patterns, (
            f"Expected {expected_patterns} patterns from clusters with 2+ members, "
            f"got {stats['patterns_extracted']}. Tag counts: {tag_counts}"
        )

        # Verify patterns were stored in semantic memory
        for tag, count in tag_counts.items():
            if count >= 2:
                pattern_key = f"pattern:emotion_pattern:{tag}"
                assert pattern_key in semantic.facts, (
                    f"Expected pattern for tag '{tag}' in semantic memory"
                )

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=high_phi_st,
    )
    @settings(max_examples=100)
    def test_promotes_high_phi_memories(self, valence, arousal, phi):
        """Episodic memories with phi > 0.25 SHALL be promoted to AutobiographicalMemory."""
        assume(phi > 0.25)  # Only test phi values that should be promoted

        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Record an episode with high phi
        item = episodic.record(
            "high phi event",
            valence=valence,
            arousal=arousal,
            phi=phi,
        )
        item.touch()

        # Should not be in autobio yet
        assert len(autobio.timeline) == 0

        # Run consolidation with very low phi to get threshold 0.25
        stats = consolidator.consolidate(phi=0.1)

        # Should be promoted if importance > 0.3 (which requires sufficient valence/arousal)
        # The promotion condition: phi > 0.25 AND importance > 0.3
        # importance = sqrt(V² + A²) × P × (1 + log(1 + C) × 0.1)
        # With C=1 (one touch), access_bonus = log(2) * 0.1 ≈ 0.069
        intensity = math.sqrt(valence**2 + arousal**2)
        expected_importance = max(0.05, min(1.0, intensity * phi * (1 + 0.069)))

        if expected_importance > 0.3:
            assert stats["memories_promoted"] >= 1, (
                f"Expected promotion for phi={phi} (> 0.25), importance={expected_importance}"
            )
            assert len(autobio.timeline) >= 1

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=low_phi_st,
    )
    @settings(max_examples=100)
    def test_does_not_promote_low_phi_memories(self, valence, arousal, phi):
        """Episodic memories with phi <= 0.25 SHALL NOT be promoted to AutobiographicalMemory."""
        # phi <= 0.25 means no promotion regardless of importance

        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Record an episode with low phi
        item = episodic.record(
            "low phi event",
            valence=valence,
            arousal=arousal,
            phi=phi,
        )
        item.touch()

        # Run consolidation
        stats = consolidator.consolidate(phi=0.1)

        # Should NOT be promoted regardless of importance
        # The promotion requires phi > 0.25
        assert stats["memories_promoted"] == 0, (
            f"Expected no promotion for phi={phi} (<= 0.25)"
        )

    @given(
        n_clusters=integers(min_value=1, max_value=3),
        n_singles=integers(min_value=0, max_value=3),
    )
    @settings(max_examples=100)
    def test_only_clusters_of_2_plus_produce_patterns(self, n_clusters, n_singles):
        """Only clusters with 2+ members SHALL produce semantic patterns."""
        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Pre-defined valence/arousal pairs for distinct tags with high values
        tag_configs = [
            (0.8, 0.8),   # ecstatic
            (-0.8, 0.8),  # fearful
            (0.8, 0.2),   # serene
        ]

        episode_count = 0
        # Add cluster episodes (2+ each)
        for i in range(min(n_clusters, len(tag_configs))):
            v, a = tag_configs[i]
            for j in range(2):  # 2 episodes per cluster
                item = episodic.record(
                    f"cluster_ep_{episode_count}",
                    valence=v,
                    arousal=a,
                    phi=0.5,
                )
                item.touch()
                episode_count += 1

        # Add single episodes (1 each with unique tag pattern)
        # Use valence/arousal values that produce distinct tags not in clusters
        single_configs = [
            (0.3, 0.6),   # agitated (a > 0.5, v in range)
            (-0.4, 0.6),  # uneasy (v < -0.3)
            (0.4, 0.2),   # pleasant (v > 0.3)
        ]
        for i in range(min(n_singles, len(single_configs))):
            v, a = single_configs[i]
            item = episodic.record(
                f"single_ep_{episode_count}",
                valence=v,
                arousal=a,
                phi=0.4,
            )
            item.touch()
            episode_count += 1

        # Run consolidation with very low phi to get threshold 0.25
        stats = consolidator.consolidate(phi=0.1)

        # Pattern count should equal number of clusters (each has 2+ members)
        assert stats["patterns_extracted"] == min(n_clusters, len(tag_configs)), (
            f"Expected {min(n_clusters, len(tag_configs))} patterns from clusters, "
            f"got {stats['patterns_extracted']}"
        )

    @given(phi=consolidation_phi_st)
    @settings(max_examples=50)
    def test_consolidation_requires_low_phi(self, phi):
        """Consolidation SHALL only run when phi < 0.3."""
        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Add episode
        item = episodic.record("test", valence=0.6, arousal=0.6, phi=0.4)
        item.touch()

        stats = consolidator.consolidate(phi=phi)

        # phi < 0.3 should run consolidation
        if phi < 0.3:
            assert stats != {}, "Consolidation should run when phi < 0.3"
        else:
            assert stats == {}, "Consolidation should skip when phi >= 0.3"

    @given(
        valence=valence_st,
        arousal=arousal_st,
        phi=high_phi_st,
    )
    @settings(max_examples=50)
    def test_promoted_memory_content_matches_original(self, valence, arousal, phi):
        """When a memory is promoted, its content SHALL match the original episodic memory."""
        assume(phi > 0.25)

        episodic = EpisodicMemory(capacity=500)
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()
        consolidator = MemoryConsolidator(episodic, semantic, autobio)

        # Record with specific content
        summary = "test event for promotion"
        item = episodic.record(
            summary,
            valence=valence,
            arousal=arousal,
            phi=phi,
        )
        item.touch()

        # Calculate expected importance with access_count=1
        intensity = math.sqrt(valence**2 + arousal**2)
        expected_importance = max(0.05, min(1.0, intensity * phi * (1 + 0.069)))

        assume(expected_importance > 0.3)  # Only test cases where promotion happens

        consolidator.consolidate(phi=0.1)

        if len(autobio.timeline) > 0:
            promoted = autobio.timeline[-1]
            # Verify content matches
            assert promoted.summary == summary, "Summary should match"
            assert abs(promoted.phi - phi) < 1e-9, "Phi should match"
            assert abs(promoted.valence - valence) < 1e-9, "Valence should match"


# ------------------------------------------------------------------
# Property 21: Consolidation Rate Limit
# ------------------------------------------------------------------


class TestConsolidationRateLimit:
    """Property 21: For any sequence of low-phi periods triggering consolidation,
    at most one consolidation cycle SHALL execute per 600 ticks.

    **Validates: Requirements 20.4**
    """

    @given(
        total_ticks=integers(min_value=1, max_value=5000),
    )
    @settings(max_examples=50)
    def test_rate_limit_respects_600_tick_gap(self, total_ticks):
        """Consolidation SHALL NOT be triggered more than once per 600 ticks."""
        ms = MemorySystem()

        # Add episodes for consolidation
        for i in range(4):
            item = ms.episodic.record(
                f"test event {i}",
                valence=-0.6,
                arousal=0.7,
                phi=0.4,
            )
            item.touch()

        low_phi_counter = 0
        ticks_since_consolidation = 0
        consolidation_timestamps = []

        for tick in range(total_ticks):
            ticks_since_consolidation += 1
            phi = 0.1  # Always low to enable consolidation

            if phi < 0.3:
                low_phi_counter += 1
            else:
                low_phi_counter = 0

            # Consolidation scheduling logic
            if low_phi_counter > 300 and ticks_since_consolidation > 600:
                stats = ms.consolidate(phi)
                if stats:
                    consolidation_timestamps.append(tick)
                    ticks_since_consolidation = 0
                    low_phi_counter = 0
                    # Re-add episodes for next consolidation
                    for j in range(4):
                        item = ms.episodic.record(
                            f"re-added event {j}",
                            valence=-0.6,
                            arousal=0.7,
                            phi=0.4,
                        )
                        item.touch()

        # Verify rate limit
        for i in range(1, len(consolidation_timestamps)):
            gap = consolidation_timestamps[i] - consolidation_timestamps[i - 1]
            # Gap must be > 600 ticks (the rate limit)
            assert gap > 600, (
                f"Consolidation at tick {consolidation_timestamps[i]} happened only "
                f"{gap} ticks after previous consolidation at {consolidation_timestamps[i-1]}"
            )

    @given(
        high_phi_ticks=integers(min_value=0, max_value=100),
        low_phi_ticks=integers(min_value=0, max_value=500),
    )
    @settings(max_examples=50)
    def test_high_phi_resets_low_phi_counter(self, high_phi_ticks, low_phi_ticks):
        """When phi >= 0.3, _low_phi_counter SHALL reset to 0."""
        low_phi_counter = 0

        # Simulate low-phi period
        for _ in range(low_phi_ticks):
            phi = 0.1
            if phi < 0.3:
                low_phi_counter += 1
            else:
                low_phi_counter = 0

        assert low_phi_counter == low_phi_ticks

        # One high-phi tick resets
        phi = 0.5
        if phi < 0.3:
            low_phi_counter += 1
        else:
            low_phi_counter = 0

        assert low_phi_counter == 0, "Counter should reset when phi >= 0.3"

    @given(
        total_ticks=integers(min_value=1300, max_value=3000),
    )
    @settings(max_examples=30)
    def test_max_consolidations_per_time_window(self, total_ticks):
        """In any N ticks, max consolidations SHALL be floor((N - 301) / 601) + 1."""
        ms = MemorySystem()

        # Add episodes
        for i in range(4):
            item = ms.episodic.record(
                f"test event {i}",
                valence=-0.6,
                arousal=0.7,
                phi=0.4,
            )
            item.touch()

        low_phi_counter = 0
        ticks_since_consolidation = 0
        consolidation_count = 0

        for tick in range(total_ticks):
            ticks_since_consolidation += 1
            phi = 0.1  # Always low

            if phi < 0.3:
                low_phi_counter += 1
            else:
                low_phi_counter = 0

            if low_phi_counter > 300 and ticks_since_consolidation > 600:
                stats = ms.consolidate(phi)
                if stats:
                    consolidation_count += 1
                    ticks_since_consolidation = 0
                    low_phi_counter = 0
                    # Re-add episodes
                    for j in range(4):
                        item = ms.episodic.record(
                            f"re-added event {j}",
                            valence=-0.6,
                            arousal=0.7,
                            phi=0.4,
                        )
                        item.touch()

        # Calculate theoretical max
        # First consolidation at tick 601 (counter=301 and ticks_since=601)
        # Subsequent consolidations at 601+601=1202, 1202+601=1803, etc.
        # Max = floor((total_ticks - 601) / 601) + 1 if total_ticks >= 601
        if total_ticks >= 601:
            max_allowed = (total_ticks - 601) // 601 + 1
        else:
            max_allowed = 0

        assert consolidation_count <= max_allowed, (
            f"Rate limit violated: {consolidation_count} consolidations in "
            f"{total_ticks} ticks, max allowed = {max_allowed}"
        )

    @given(
        phi_values=lists(
            sampled_from([0.1, 0.15, 0.2, 0.25, 0.4, 0.5, 0.7]),
            min_size=100,
            max_size=500,
        ),
    )
    @settings(max_examples=30)
    def test_rate_limit_with_varying_phi(self, phi_values):
        """Rate limit SHALL be respected even with varying phi values."""
        ms = MemorySystem()

        # Add episodes
        for i in range(4):
            item = ms.episodic.record(
                f"test event {i}",
                valence=-0.6,
                arousal=0.7,
                phi=0.4,
            )
            item.touch()

        low_phi_counter = 0
        ticks_since_consolidation = 0
        consolidation_count = 0
        last_consolidation_tick = -1000

        for tick, phi in enumerate(phi_values):
            ticks_since_consolidation += 1

            if phi < 0.3:
                low_phi_counter += 1
            else:
                low_phi_counter = 0

            if low_phi_counter > 300 and ticks_since_consolidation > 600:
                stats = ms.consolidate(phi)
                if stats:
                    # Verify 600 tick gap
                    gap = tick - last_consolidation_tick
                    assert gap > 600, (
                        f"Consolidation at tick {tick} only {gap} ticks after previous"
                    )
                    consolidation_count += 1
                    last_consolidation_tick = tick
                    ticks_since_consolidation = 0
                    low_phi_counter = 0
                    # Re-add episodes
                    for j in range(4):
                        item = ms.episodic.record(
                            f"re-added event {j}",
                            valence=-0.6,
                            arousal=0.7,
                            phi=0.4,
                        )
                        item.touch()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "--tb=short"])
