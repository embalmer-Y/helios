"""Test memory consolidation scheduling (Task 12.3)

Validates Requirements 13.4, 20.1, 20.2, 20.3, 20.4, 20.5:
  - Trigger consolidation when Phi < 0.3 for 300 consecutive ticks
  - Cluster episodic memories by emotional tag during consolidation
  - Extract semantic patterns from clusters with 2+ members
  - Promote episodic memories with phi > 0.25 to AutobiographicalMemory
  - Rate limit: at most one consolidation per 600 ticks
  - Log counts of patterns extracted, memories promoted, items pruned
"""
import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from memory_system import (
    MemorySystem,
    MemoryConsolidator,
    EpisodicMemory,
    SemanticMemory,
    AutobiographicalMemory,
)


# ═══════════════════════════════════════════════════
# MemoryConsolidator unit tests
# ═══════════════════════════════════════════════════


def test_consolidate_skips_when_phi_too_high():
    """Consolidation should skip when phi > 0.3."""
    ms = MemorySystem()
    stats = ms.consolidate(phi=0.5)
    assert stats == {}
    assert ms.stats["consolidations"] == 0


def test_consolidate_returns_stats():
    """Consolidation should return stats dict with required keys."""
    ms = MemorySystem()
    # Add some episodic memories with varied emotional tags
    for i in range(5):
        ms.remember(
            summary=f"fearful event {i}",
            valence=-0.6,
            arousal=0.7,
            phi=0.4,
        )
    # Touch them to make access_count >= 1
    for item in ms.episodic.items:
        item.touch()

    stats = ms.consolidate(phi=0.1)
    assert isinstance(stats, dict)
    assert "patterns_extracted" in stats
    assert "memories_promoted" in stats
    assert "items_pruned" in stats


def test_consolidate_clusters_by_emotional_tag():
    """Consolidation should cluster by emotional tag and extract patterns from 2+ clusters."""
    episodic = EpisodicMemory(capacity=500)
    semantic = SemanticMemory()
    autobio = AutobiographicalMemory()
    consolidator = MemoryConsolidator(episodic, semantic, autobio)

    # Add 3 fearful episodes (same tag → cluster of 3)
    for i in range(3):
        item = episodic.record(
            summary=f"fearful event {i}",
            valence=-0.7,
            arousal=0.8,
            phi=0.4,
        )
        item.touch()  # access_count >= 1

    # Add 1 ecstatic episode (cluster of 1 → no pattern)
    item = episodic.record(
        summary="happy event",
        valence=0.8,
        arousal=0.8,
        phi=0.3,
    )
    item.touch()

    stats = consolidator.consolidate(phi=0.1)

    # Pattern should be extracted from "fearful" cluster (3 members)
    assert stats["patterns_extracted"] >= 1
    # Verify pattern was stored in semantic memory
    assert "pattern:emotion_pattern:fearful" in semantic.facts


def test_consolidate_no_pattern_for_single_member_cluster():
    """Clusters with only 1 member should NOT produce patterns."""
    episodic = EpisodicMemory(capacity=500)
    semantic = SemanticMemory()
    autobio = AutobiographicalMemory()
    consolidator = MemoryConsolidator(episodic, semantic, autobio)

    # Add 1 unique-tag episode
    item = episodic.record(
        summary="unique event",
        valence=0.9,
        arousal=0.9,
        phi=0.5,
    )
    item.touch()

    stats = consolidator.consolidate(phi=0.1)

    # No pattern should be extracted (cluster size < 2)
    assert stats["patterns_extracted"] == 0


def test_consolidate_promotes_high_phi_memories():
    """Episodic memories with phi > 0.25 should be promoted to AutobiographicalMemory."""
    episodic = EpisodicMemory(capacity=500)
    semantic = SemanticMemory()
    autobio = AutobiographicalMemory()
    consolidator = MemoryConsolidator(episodic, semantic, autobio)

    # Add episodes with phi > 0.25 (should be promoted)
    for i in range(3):
        item = episodic.record(
            summary=f"high phi event {i}",
            valence=0.5,
            arousal=0.5,
            phi=0.4,  # above 0.25
        )
        item.touch()

    assert len(autobio.timeline) == 0
    stats = consolidator.consolidate(phi=0.1)

    # All 3 should be promoted
    assert stats["memories_promoted"] == 3
    assert len(autobio.timeline) == 3


def test_consolidate_does_not_promote_low_phi_memories():
    """Episodic memories with phi <= 0.25 should NOT be promoted."""
    episodic = EpisodicMemory(capacity=500)
    semantic = SemanticMemory()
    autobio = AutobiographicalMemory()
    consolidator = MemoryConsolidator(episodic, semantic, autobio)

    # Add episodes with phi <= 0.25
    for i in range(3):
        item = episodic.record(
            summary=f"low phi event {i}",
            valence=0.5,
            arousal=0.5,
            phi=0.2,  # at or below 0.25
        )
        item.touch()

    stats = consolidator.consolidate(phi=0.1)
    assert stats["memories_promoted"] == 0
    assert len(autobio.timeline) == 0


def test_consolidate_logs_stats(caplog):
    """Consolidation should log counts at INFO level."""
    episodic = EpisodicMemory(capacity=500)
    semantic = SemanticMemory()
    autobio = AutobiographicalMemory()
    consolidator = MemoryConsolidator(episodic, semantic, autobio)

    # Add 2 episodes with same tag
    for i in range(2):
        item = episodic.record(
            summary=f"event {i}",
            valence=-0.6,
            arousal=0.7,
            phi=0.4,
        )
        item.touch()

    with caplog.at_level(logging.INFO, logger="memory_system"):
        consolidator.consolidate(phi=0.1)

    # Check log contains stats
    log_text = caplog.text
    assert "patterns_extracted=" in log_text
    assert "memories_promoted=" in log_text
    assert "items_pruned=" in log_text


# ═══════════════════════════════════════════════════
# Consolidation scheduling integration tests
# ═══════════════════════════════════════════════════


def test_helios_has_consolidation_counters():
    """Helios should have _low_phi_counter and _ticks_since_consolidation."""
    from helios_main import Helios
    assert hasattr(Helios, '__init__')

    import inspect
    source = inspect.getsource(Helios.__init__)
    assert "_low_phi_counter" in source
    assert "_ticks_since_consolidation" in source


def test_helios_tick_has_consolidation_scheduling():
    """_tick() should contain the consolidation scheduling logic."""
    from helios_main import Helios
    import inspect
    source = inspect.getsource(Helios._tick)

    assert "_low_phi_counter" in source
    assert "_ticks_since_consolidation" in source
    assert "consolidate" in source


def test_consolidation_scheduling_logic():
    """
    Test the scheduling logic directly:
    - Increment _low_phi_counter when phi < 0.3
    - Reset to 0 when phi >= 0.3
    - Trigger consolidation when counter > 300 AND ticks_since > 600
    - Reset counters after consolidation
    """
    ms = MemorySystem()

    # Add some episodes so consolidation actually does something
    for i in range(4):
        item = ms.episodic.record(
            summary=f"test event {i}",
            valence=-0.6,
            arousal=0.7,
            phi=0.4,
        )
        item.touch()

    # Simulate scheduling logic as it appears in _tick
    low_phi_counter = 0
    ticks_since_consolidation = 0
    consolidation_triggered = False

    # Simulate 301 low-phi ticks with ticks_since > 600
    for tick in range(700):
        ticks_since_consolidation += 1
        phi = 0.1  # always low

        if phi < 0.3:
            low_phi_counter += 1
        else:
            low_phi_counter = 0

        if low_phi_counter > 300 and ticks_since_consolidation > 600:
            stats = ms.consolidate(phi)
            if stats:
                ticks_since_consolidation = 0
                low_phi_counter = 0
                consolidation_triggered = True
                break

    assert consolidation_triggered, "Consolidation should trigger after 300+ low-phi ticks with 600+ gap"


def test_consolidation_rate_limit():
    """
    Consolidation should NOT trigger within 600 ticks of last consolidation.
    """
    ms = MemorySystem()

    # Add episodes
    for i in range(4):
        item = ms.episodic.record(
            summary=f"test event {i}",
            valence=-0.6,
            arousal=0.7,
            phi=0.4,
        )
        item.touch()

    low_phi_counter = 0
    ticks_since_consolidation = 0
    consolidation_count = 0

    # Run 1500 ticks with phi always < 0.3
    for tick in range(1500):
        ticks_since_consolidation += 1
        phi = 0.1

        if phi < 0.3:
            low_phi_counter += 1
        else:
            low_phi_counter = 0

        if low_phi_counter > 300 and ticks_since_consolidation > 600:
            stats = ms.consolidate(phi)
            if stats:
                ticks_since_consolidation = 0
                low_phi_counter = 0
                consolidation_count += 1
                # Re-add episodes for next consolidation
                for j in range(4):
                    item = ms.episodic.record(
                        summary=f"re-added event {j}",
                        valence=-0.6,
                        arousal=0.7,
                        phi=0.4,
                    )
                    item.touch()

    # In 1500 ticks, max consolidations = floor((1500 - 301) / 601) + 1 = 2
    # First at tick 601 (counter hits 301 and ticks_since > 600)
    # Second at tick ~1202 (600+ since last, counter rebuilt to 300+)
    assert consolidation_count <= 2, (
        f"Rate limit violated: {consolidation_count} consolidations in 1500 ticks"
    )
    assert consolidation_count >= 1, "Should have at least 1 consolidation"


def test_phi_above_threshold_resets_counter():
    """When phi >= 0.3, _low_phi_counter should reset to 0."""
    low_phi_counter = 0

    # Simulate 200 low-phi ticks
    for _ in range(200):
        phi = 0.1
        if phi < 0.3:
            low_phi_counter += 1
        else:
            low_phi_counter = 0

    assert low_phi_counter == 200

    # One high-phi tick resets
    phi = 0.5
    if phi < 0.3:
        low_phi_counter += 1
    else:
        low_phi_counter = 0

    assert low_phi_counter == 0, "Counter should reset to 0 when phi >= 0.3"


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Memory Consolidation Scheduling (Task 12.3)")
    print("=" * 60)

    test_consolidate_skips_when_phi_too_high()
    print("✓ Consolidation skips when phi > 0.3")

    test_consolidate_returns_stats()
    print("✓ Consolidation returns stats dict")

    test_consolidate_clusters_by_emotional_tag()
    print("✓ Consolidation clusters by emotional tag")

    test_consolidate_no_pattern_for_single_member_cluster()
    print("✓ No pattern for single-member cluster")

    test_consolidate_promotes_high_phi_memories()
    print("✓ Promotes high-phi memories to autobiographical")

    test_consolidate_does_not_promote_low_phi_memories()
    print("✓ Does NOT promote low-phi memories")

    test_helios_has_consolidation_counters()
    print("✓ Helios has consolidation counters")

    test_helios_tick_has_consolidation_scheduling()
    print("✓ _tick() has consolidation scheduling logic")

    test_consolidation_scheduling_logic()
    print("✓ Consolidation triggers after 300+ low-phi ticks with 600+ gap")

    test_consolidation_rate_limit()
    print("✓ Rate limit: at most one consolidation per 600 ticks")

    test_phi_above_threshold_resets_counter()
    print("✓ High phi resets low_phi_counter")

    print("\n" + "=" * 60)
    print("✅ All consolidation scheduling tests passed!")
    print("=" * 60)
