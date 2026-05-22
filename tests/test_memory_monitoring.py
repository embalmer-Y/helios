"""
Tests for memory usage monitoring (Task 12.9).

Requirements: 23.1, 23.2, 23.3, 23.4
"""

import logging
import pytest
from memory_system import MemorySystem


class TestMemoryMonitor:
    """Tests for MemorySystem.monitor() method."""

    def test_monitor_logs_stats(self, caplog):
        """monitor() logs memory subsystem stats at INFO level (Req 23.1)."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        ms.hold("test item", valence=0.1, arousal=0.2)
        ms.remember("episode 1", valence=0.3, arousal=0.4, phi=0.5)
        ms.learn("fact1", "value1")

        with caplog.at_level(logging.INFO, logger="memory_system"):
            result = ms.monitor()

        # Should log stats
        assert any("MemorySystem stats:" in r.message for r in caplog.records)
        # Should include counts in log
        stats_log = [r for r in caplog.records if "MemorySystem stats:" in r.message][0]
        assert "working=1/15" in stats_log.message
        assert "episodic=1/500" in stats_log.message
        assert "semantic=1" in stats_log.message

    def test_monitor_returns_stats(self):
        """monitor() returns dict with current memory statistics."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        ms.hold("item1")
        ms.remember("ep1", valence=0.5, arousal=0.5, phi=0.5)

        result = ms.monitor()

        assert result["working_items"] == 1
        assert result["working_capacity"] == 15
        assert result["episodic_items"] == 1
        assert result["episodic_capacity"] == 500
        assert result["semantic_facts"] == 0
        assert result["autobio_moments"] == 0
        assert result["total_items"] == 2

    def test_monitor_warns_at_80_percent_working(self, caplog):
        """monitor() logs WARNING when working memory exceeds 80% capacity (Req 23.2)."""
        ms = MemorySystem(working_capacity=5, episodic_capacity=500)
        # Fill to 80% (4/5)
        for i in range(4):
            ms.hold(f"item {i}")

        with caplog.at_level(logging.WARNING, logger="memory_system"):
            result = ms.monitor()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("WorkingMemory" in r.message and "80%" in r.message for r in warning_records)
        assert len(result["warnings"]) >= 1
        assert "WorkingMemory" in result["warnings"][0]

    def test_monitor_warns_at_80_percent_episodic(self, caplog):
        """monitor() logs WARNING when episodic memory exceeds 80% capacity (Req 23.2)."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=10)
        # Fill to 80% (8/10)
        for i in range(8):
            ms.remember(f"episode {i}", valence=0.5, arousal=0.5, phi=0.5)

        with caplog.at_level(logging.WARNING, logger="memory_system"):
            result = ms.monitor()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("EpisodicMemory" in r.message and "80%" in r.message for r in warning_records)
        assert any("EpisodicMemory" in w for w in result["warnings"])

    def test_monitor_no_warning_below_80_percent(self, caplog):
        """monitor() does NOT warn when collections are below 80% capacity."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        ms.hold("one item")

        with caplog.at_level(logging.WARNING, logger="memory_system"):
            result = ms.monitor()

        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) == 0
        assert result["warnings"] == []

    def test_monitor_triggers_consolidation_above_2000(self, caplog):
        """monitor() triggers immediate consolidation when total items > 2000 (Req 23.4)."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=3000)
        # Add 2001 episodic items to exceed threshold
        for i in range(2001):
            ms.episodic.items.append(
                __import__("memory_system").MemoryItem(
                    memory_type="episodic",
                    summary=f"item {i}",
                    valence=0.1,
                    arousal=0.1,
                    phi=0.1,
                )
            )

        with caplog.at_level(logging.WARNING, logger="memory_system"):
            result = ms.monitor()

        assert result["consolidation_triggered"] is True
        assert any("exceeds 2000" in r.message for r in caplog.records if r.levelno == logging.WARNING)

    def test_monitor_no_consolidation_below_2000(self):
        """monitor() does NOT trigger consolidation when total items <= 2000."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        ms.hold("item")
        ms.remember("ep", valence=0.5, arousal=0.5, phi=0.5)

        result = ms.monitor()

        assert result["consolidation_triggered"] is False


class TestMemoryGetState:
    """Tests for MemorySystem.get_state() method."""

    def test_get_state_returns_all_fields(self):
        """get_state() exposes memory statistics for external monitoring (Req 23.3)."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        ms.hold("working item")
        ms.remember("episode", valence=0.5, arousal=0.5, phi=0.5)
        ms.learn("key", "value")

        state = ms.get_state()

        assert state["working_items"] == 1
        assert state["working_capacity"] == 15
        assert state["working_utilization"] == round(1 / 15, 3)
        assert state["episodic_items"] == 1
        assert state["episodic_capacity"] == 500
        assert state["episodic_utilization"] == round(1 / 500, 3)
        assert state["semantic_facts"] == 1
        assert state["autobio_moments"] == 0
        assert state["total_items"] == 3
        assert state["episodes_recorded"] == 1
        assert state["facts_learned"] == 1
        assert state["consolidations"] == 0

    def test_get_state_empty_system(self):
        """get_state() works correctly on empty memory system."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)

        state = ms.get_state()

        assert state["working_items"] == 0
        assert state["episodic_items"] == 0
        assert state["semantic_facts"] == 0
        assert state["autobio_moments"] == 0
        assert state["total_items"] == 0
        assert state["working_utilization"] == 0
        assert state["episodic_utilization"] == 0

    def test_get_state_utilization_calculation(self):
        """get_state() correctly calculates utilization percentages."""
        ms = MemorySystem(working_capacity=10, episodic_capacity=100)
        for i in range(5):
            ms.hold(f"item {i}")
        for i in range(50):
            ms.remember(f"ep {i}", valence=0.1, arousal=0.1, phi=0.1)

        state = ms.get_state()

        assert state["working_utilization"] == 0.5
        assert state["episodic_utilization"] == 0.5
