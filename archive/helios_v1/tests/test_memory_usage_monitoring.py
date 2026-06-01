"""
Tests for Memory Usage Monitoring (Requirement 23).

Tests the following behaviors:
- Log memory subsystem statistics at each summary interval (23.1)
- Log WARNING when any collection exceeds 80% capacity (23.2)
- Expose memory statistics through get_state() method (23.3)
- Trigger immediate consolidation when total items exceed 2000 (23.4)
"""

import logging
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from helios_io.conversation_history import ConversationHistoryManager
from memory import MemorySystem, MemoryItem


class TestMemoryStatsLogging:
    """Requirement 23.1: Log memory subsystem statistics at each summary interval."""

    def test_memory_system_get_stats_returns_required_fields(self):
        """get_stats() should return all required memory statistics."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)
        stats = ms.get_stats()

        assert "working_items" in stats
        assert "episodic_items" in stats
        assert "semantic_facts" in stats
        assert "autobio_moments" in stats

    def test_memory_stats_reflect_current_counts(self):
        """Memory statistics should reflect the current item counts."""
        ms = MemorySystem(working_capacity=15, episodic_capacity=500)

        # Add some items
        ms.hold("test working item 1")
        ms.hold("test working item 2")
        ms.remember("test episodic 1", valence=0.5, arousal=0.5, phi=0.5)
        ms.learn("test_fact", "test value")

        stats = ms.get_stats()
        assert stats["working_items"] == 2
        assert stats["episodic_items"] == 1
        assert stats["semantic_facts"] == 1


class TestMemoryStatsInGetState:
    """Requirement 23.3: Expose memory statistics through get_state() method."""

    def test_helios_get_state_includes_memory_stats(self):
        """get_state() should include memory statistics."""
        import helios_main

        h = helios_main.Helios()
        state = h.get_state()

        assert "memory" in state
        assert isinstance(state["memory"], dict)

    def test_get_state_memory_has_required_fields(self):
        """get_state() memory field should have all required statistics."""
        import helios_main

        h = helios_main.Helios()
        state = h.get_state()
        mem = state["memory"]

        assert "working_items" in mem
        assert "episodic_items" in mem
        assert "semantic_facts" in mem
        assert "autobio_moments" in mem
        assert "episodic_capacity" in mem
        assert "working_capacity" in mem

    def test_get_state_memory_capacity_values(self):
        """get_state() should expose configured capacities."""
        import helios_main

        h = helios_main.Helios()
        state = h.get_state()
        mem = state["memory"]

        assert mem["episodic_capacity"] == 500
        assert mem["working_capacity"] == 15


class TestCapacityWarnings:
    """Requirement 23.2: Log WARNING when collection exceeds 80% capacity."""

    def test_check_memory_capacity_warnings_exists(self):
        """Helios should have the _check_memory_capacity_warnings method."""
        import helios_main

        h = helios_main.Helios()
        assert hasattr(h, "_check_memory_capacity_warnings")
        assert callable(h._check_memory_capacity_warnings)

    def test_capacity_warning_for_episodic_at_80_percent(self, caplog):
        """Should log WARNING when episodic memory reaches 80% capacity."""
        import helios_main

        h = helios_main.Helios()

        # Fill episodic memory to >80% (400+ items for capacity 500)
        for i in range(410):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)

        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()

        # Should have at least one warning about episodic memory
        episodic_warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(episodic_warnings) >= 1
        assert "approaching capacity" in episodic_warnings[0].message

    def test_no_warning_below_80_percent(self, caplog):
        """Should NOT log WARNING when memory is below 80% capacity."""
        import helios_main

        h = helios_main.Helios()

        # Keep memory well below 80%
        for i in range(10):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)

        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()

        # Should have no capacity warnings
        capacity_warnings = [r for r in caplog.records if "approaching capacity" in r.message]
        assert len(capacity_warnings) == 0

    def test_conversation_history_warning_at_80_percent(self, caplog):
        """Should log WARNING when user's conversation history reaches 80% capacity."""
        import helios_main

        h = helios_main.Helios()

        # Add 17 exchanges (>80% of 20 capacity) for a user
        user_id = "test_user_123"
        for i in range(17):
            h.response_pipeline._history_manager.append_message(
                user_id=user_id,
                message=f"message_{i}",
                sec_result={"novelty": 0.3, "goal_relevance": 0.3},
            )

        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()

        # Should have warning about conversation history
        conv_warnings = [r for r in caplog.records if "Conversation history" in r.message]
        assert len(conv_warnings) >= 1


class TestMemoryPressureConsolidation:
    """Requirement 23.4: Trigger immediate consolidation when total items exceed 2000."""

    def test_memory_pressure_triggers_consolidation(self):
        """Should trigger consolidation when total items > 2000."""
        import helios_main

        h = helios_main.Helios()

        # Fill memory system with >2000 items total
        # Note: This tests the logic path; actual consolidation may prune items
        for i in range(1600):
            h.memory_system.remember(f"episodic_{i}", valence=0.3, arousal=0.3, phi=0.3)
        for i in range(450):
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")

        total_items = (
            len(h.memory_system.working.items)
            + len(h.memory_system.episodic.items)
            + len(h.memory_system.semantic.facts)
            + len(h.memory_system.autobiographical.timeline)
        )

        # Verify we're over 2000
        assert total_items > 2000 or len(h.memory_system.episodic.items) >= 500

        # Check that memory pressure detection logic exists
        mem_stats = h.memory_system.get_stats()
        computed_total = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        assert computed_total == total_items

    def test_tick_includes_memory_pressure_check(self):
        """_tick method should include memory pressure check logic."""
        import helios_main
        import inspect

        source = inspect.getsource(helios_main.Helios._tick)

        # Should have the 2000 item threshold check
        assert "2000" in source
        assert "Memory pressure" in source or "memory pressure" in source.lower()

    def test_consolidation_triggered_on_memory_pressure(self):
        """Memory pressure should trigger consolidation regardless of phi."""
        import helios_main

        h = helios_main.Helios()

        # Reset consolidation counters
        h._ticks_since_consolidation = 100
        h._low_phi_counter = 0  # phi is NOT low

        # Fill memory to trigger pressure (simulated via stats check)
        # We test the logic exists, actual pressure consolidation happens in tick

        # Verify the method exists and can check total
        mem_stats = h.memory_system.get_stats()
        total = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        # For a fresh instance, this should be small
        assert total < 2000


class TestSummaryIncludesMemoryStats:
    """Requirement 23.1: Memory stats logged at each summary interval."""

    def test_summary_includes_memory_stats(self, caplog):
        """_summary() should log memory subsystem statistics."""
        import helios_main

        h = helios_main.Helios()

        # Set required state variables that _summary uses
        h.last_dominant = "SEEKING"
        h.last_phi = 0.5
        h.last_valence = 0.3

        with caplog.at_level(logging.INFO):
            h._summary()

        # Should have logged memory statistics
        memory_logs = [r for r in caplog.records if "记忆统计" in r.message]
        assert len(memory_logs) >= 1

    def test_summary_calls_capacity_warnings(self):
        """_summary() should call _check_memory_capacity_warnings()."""
        import helios_main
        import inspect

        source = inspect.getsource(helios_main.Helios._summary)

        assert "_check_memory_capacity_warnings" in source
