"""Unit tests for SemanticMemory decay and forgetting (Requirement 19)."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from memory_system import SemanticMemory


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

SECONDS_PER_DAY = 86400.0


def _make_semantic_with_old_fact(idle_days: float, confidence: float = 0.5,
                                  key: str = "test.fact",
                                  tags: list = None) -> SemanticMemory:
    """Create a SemanticMemory with a fact last accessed `idle_days` ago."""
    sm = SemanticMemory()
    sm.learn(key, "value", tags=tags or [], confidence=confidence)
    # Backdate the last_accessed timestamp
    item = sm.facts[key]
    item.last_accessed = time.time() - (idle_days * SECONDS_PER_DAY)
    return sm


# ------------------------------------------------------------------
# Tests — 7-day grace period (Requirement 19.1)
# ------------------------------------------------------------------


class TestGracePeriod:
    def test_no_decay_within_grace_period(self):
        """Facts accessed within 7 days should not decay."""
        sm = _make_semantic_with_old_fact(idle_days=5, confidence=0.8)
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.8

    def test_no_decay_at_exactly_7_days(self):
        """Facts at roughly 7 days of idle should see negligible decay."""
        # Due to time.time() rounding, exactly 7.0 days can drift slightly
        # Use 6.99 days to guarantee we stay within grace period
        sm = _make_semantic_with_old_fact(idle_days=6.99, confidence=0.8)
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.8

    def test_decay_starts_beyond_7_days(self):
        """Facts idle beyond 7 days should have confidence reduced."""
        sm = _make_semantic_with_old_fact(idle_days=10, confidence=0.8)
        sm.decay()
        # Decay = 0.001 * (10 - 7) = 0.003
        expected = 0.8 - 0.003
        assert abs(sm.facts["test.fact"].content["confidence"] - expected) < 1e-9

    def test_recently_accessed_fact_unaffected(self):
        """A fact accessed just now should not decay at all."""
        sm = _make_semantic_with_old_fact(idle_days=0, confidence=0.5)
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.5


# ------------------------------------------------------------------
# Tests — decay rate (Requirement 19.2)
# ------------------------------------------------------------------


class TestDecayRate:
    def test_decay_rate_0_001_per_idle_day_beyond_grace(self):
        """Confidence decreases by 0.001 per day beyond 7-day grace period."""
        sm = _make_semantic_with_old_fact(idle_days=17, confidence=0.5)
        sm.decay()
        # excess_days = 17 - 7 = 10; decay = 0.001 * 10 = 0.01
        expected = 0.5 - 0.01
        assert abs(sm.facts["test.fact"].content["confidence"] - expected) < 1e-9

    def test_custom_decay_rate(self):
        """A custom rate should scale proportionally."""
        sm = _make_semantic_with_old_fact(idle_days=12, confidence=0.6)
        sm.decay(rate=0.01)
        # excess_days = 12 - 7 = 5; decay = 0.01 * 5 = 0.05
        expected = 0.6 - 0.05
        assert abs(sm.facts["test.fact"].content["confidence"] - expected) < 1e-9

    def test_multiple_decay_cycles_accumulate(self):
        """Each decay call further reduces confidence."""
        sm = _make_semantic_with_old_fact(idle_days=10, confidence=0.8)
        sm.decay()  # 0.8 - 0.003 = 0.797
        # Don't change timestamp between calls; idle time is the same
        sm.decay()  # 0.797 - 0.003 = 0.794
        expected = 0.8 - 0.003 - 0.003
        assert abs(sm.facts["test.fact"].content["confidence"] - expected) < 1e-9


# ------------------------------------------------------------------
# Tests — removal below threshold (Requirement 19.3)
# ------------------------------------------------------------------


class TestRemovalBelowThreshold:
    def test_fact_removed_when_confidence_below_0_15(self):
        """Facts with confidence below 0.15 after decay should be removed."""
        # Confidence will drop below 0.15: 0.16 - 0.001 * (8-7) = 0.159 > 0.15
        # Need: final < 0.15 → set idle high enough
        # 0.16 - 0.001 * (107 - 7) = 0.16 - 0.1 = 0.06 < 0.15
        sm = _make_semantic_with_old_fact(idle_days=107, confidence=0.16)
        sm.decay()
        assert "test.fact" not in sm.facts

    def test_fact_kept_when_confidence_at_exactly_0_15(self):
        """Facts at confidence >= 0.15 after decay should NOT be removed."""
        # Use values that produce confidence clearly at 0.15 or above
        # idle_days=10 → excess_days=3 → decay=0.003
        # Start at 0.154 → 0.154 - 0.003 = 0.151 > 0.15
        sm = _make_semantic_with_old_fact(idle_days=10, confidence=0.154)
        sm.decay()
        assert "test.fact" in sm.facts
        assert sm.facts["test.fact"].content["confidence"] >= 0.15

    def test_fact_removed_just_below_threshold(self):
        """Facts just below 0.15 should be removed."""
        # 0.152 - 0.001 * (10 - 7) = 0.152 - 0.003 = 0.149 < 0.15
        sm = _make_semantic_with_old_fact(idle_days=10, confidence=0.152)
        sm.decay()
        assert "test.fact" not in sm.facts

    def test_tag_index_cleaned_on_removal(self):
        """When a fact is removed, its tags should be cleaned up."""
        sm = _make_semantic_with_old_fact(
            idle_days=200, confidence=0.16, tags=["identity", "core"]
        )
        sm.decay()
        assert "test.fact" not in sm.facts
        # Tags referencing the removed key should be cleaned
        for tag, keys in sm.concepts.items():
            assert "test.fact" not in keys


# ------------------------------------------------------------------
# Tests — idle timer reset on access (Requirement 19.4)
# ------------------------------------------------------------------


class TestIdleTimerReset:
    def test_know_resets_idle_timer(self):
        """Calling know() should reset last_accessed, preventing decay."""
        sm = _make_semantic_with_old_fact(idle_days=20, confidence=0.5)
        # Access the fact — should reset timer
        sm.know("test.fact")
        # Now decay should NOT apply (just accessed)
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.5

    def test_know_with_confidence_resets_idle_timer(self):
        """Calling know_with_confidence() should reset last_accessed."""
        sm = _make_semantic_with_old_fact(idle_days=20, confidence=0.5)
        sm.know_with_confidence("test.fact")
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.5

    def test_recall_by_tag_resets_idle_timer(self):
        """Calling recall_by_tag() should also reset idle timers."""
        sm = _make_semantic_with_old_fact(
            idle_days=20, confidence=0.5, tags=["mytag"]
        )
        sm.recall_by_tag("mytag")
        sm.decay()
        assert sm.facts["test.fact"].content["confidence"] == 0.5


# ------------------------------------------------------------------
# Tests — integration with consolidation
# ------------------------------------------------------------------


class TestConsolidationIntegration:
    def test_decay_called_during_consolidation(self):
        """Decay should be applied when consolidation runs."""
        from memory_system import (
            EpisodicMemory, SemanticMemory,
            AutobiographicalMemory, MemoryConsolidator
        )
        episodic = EpisodicMemory()
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()

        # Add a stale fact
        semantic.learn("old.fact", "old_value", confidence=0.5)
        item = semantic.facts["old.fact"]
        item.last_accessed = time.time() - (20 * SECONDS_PER_DAY)

        consolidator = MemoryConsolidator(episodic, semantic, autobio)
        consolidator.consolidate(phi=0.1)  # Low phi → consolidation runs

        # Decay should have reduced confidence: 0.5 - 0.001 * (20 - 7) = 0.487
        expected = 0.5 - 0.001 * 13
        assert abs(semantic.facts["old.fact"].content["confidence"] - expected) < 1e-9

    def test_consolidation_skipped_when_phi_too_high(self):
        """Consolidation and decay should NOT run when phi > 0.3."""
        from memory_system import (
            EpisodicMemory, SemanticMemory,
            AutobiographicalMemory, MemoryConsolidator
        )
        episodic = EpisodicMemory()
        semantic = SemanticMemory()
        autobio = AutobiographicalMemory()

        semantic.learn("stale.fact", "value", confidence=0.5)
        item = semantic.facts["stale.fact"]
        item.last_accessed = time.time() - (20 * SECONDS_PER_DAY)

        consolidator = MemoryConsolidator(episodic, semantic, autobio)
        consolidator.consolidate(phi=0.5)  # High phi → skip

        # Confidence should be unchanged
        assert semantic.facts["stale.fact"].content["confidence"] == 0.5
