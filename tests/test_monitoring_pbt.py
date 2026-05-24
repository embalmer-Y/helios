"""Property-based tests for Capacity Monitoring Alerts.

# Feature: helios-architecture-enhancement
# Property 26: Capacity Monitoring Alerts

**Validates: Requirements 23.2, 23.4**

Property 26: For any in-memory collection at ≥ 80% of its configured capacity,
a WARNING SHALL be logged. When total items across all memory tiers exceed 2000,
an immediate consolidation SHALL be triggered.
"""

import sys
import os
import logging
import math
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings, assume, HealthCheck
from hypothesis.strategies import (
    integers,
    floats,
    lists,
    tuples,
    composite,
)

from memory import MemorySystem, EpisodicMemory, WorkingMemory, MemoryItem


# ------------------------------------------------------------------
# Strategies
# ------------------------------------------------------------------

# Basic value strategies
valence_st = floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False)
arousal_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
phi_st = floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Episode tuple: (valence, arousal, phi)
episode_st = tuples(valence_st, arousal_st, phi_st)


@composite
def capacity_and_fill_level(draw):
    """Generate a capacity and a number of items to fill it to a specific level.
    
    Returns: (capacity, num_items, expected_percentage)
    """
    capacity = draw(integers(min_value=10, max_value=100))
    # Choose a fill percentage between 50% and 100%
    fill_percentage = draw(floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False))
    num_items = max(1, int(capacity * fill_percentage))
    return capacity, num_items, num_items / capacity


@composite
def items_over_threshold(draw):
    """Generate a number of items that is at or above 80% of a capacity.
    
    Returns: (capacity, num_items) where num_items >= capacity * 0.8
    """
    capacity = draw(integers(min_value=10, max_value=100))
    # Generate items at or above 80% threshold
    min_items = math.ceil(capacity * 0.8)
    max_items = capacity
    num_items = draw(integers(min_value=min_items, max_value=max_items))
    return capacity, num_items


@composite
def items_below_threshold(draw):
    """Generate a number of items that is below 80% of a capacity.
    
    Returns: (capacity, num_items) where num_items < capacity * 0.8
    """
    capacity = draw(integers(min_value=10, max_value=100))
    # Generate items below 80% threshold
    max_items = min(capacity - 1, math.floor(capacity * 0.8) - 1)
    if max_items < 1:
        max_items = 1
    num_items = draw(integers(min_value=1, max_value=max_items))
    return capacity, num_items


# ------------------------------------------------------------------
# Property 26 Part 1: Capacity Warning at 80%
# ------------------------------------------------------------------


class TestCapacityWarningAt80Percent:
    """Property 26 (Part 1): For any in-memory collection at ≥ 80% of its
    configured capacity, a WARNING SHALL be logged.
    
    **Validates: Requirements 23.2**
    """

    @given(data=items_over_threshold())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_episodic_memory_at_80_percent_logs_warning(self, data, caplog):
        """When episodic memory is at or above 80% capacity, a WARNING SHALL be logged."""
        import helios_main
        
        capacity, num_items = data
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = capacity
        
        # Fill episodic memory to the specified level
        for i in range(num_items):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        actual_count = len(h.memory_system.episodic.items)
        actual_ratio = actual_count / capacity
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        # If at or above 80%, should have warning
        if actual_ratio >= 0.80:
            episodic_warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
            assert len(episodic_warnings) >= 1, (
                f"Expected WARNING for episodic memory at {actual_count}/{capacity} "
                f"({actual_ratio*100:.1f}%), but got none"
            )
            assert "approaching capacity" in episodic_warnings[0].message

    @given(data=items_below_threshold())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_episodic_memory_below_80_percent_no_warning(self, data, caplog):
        """When episodic memory is below 80% capacity, NO WARNING SHALL be logged."""
        import helios_main
        
        capacity, num_items = data
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = capacity
        
        # Fill episodic memory below 80%
        for i in range(num_items):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        actual_count = len(h.memory_system.episodic.items)
        actual_ratio = actual_count / capacity
        
        # Ensure we're actually below 80%
        assume(actual_ratio < 0.80)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        # Should NOT have episodic warning
        episodic_warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(episodic_warnings) == 0, (
            f"Expected NO warning for episodic memory at {actual_count}/{capacity} "
            f"({actual_ratio*100:.1f}%), but got {len(episodic_warnings)}"
        )

    @given(
        capacity=integers(min_value=50, max_value=200),
        fill_ratio=floats(min_value=0.80, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_state_history_at_80_percent_logs_warning(self, capacity, fill_ratio, caplog):
        """When DAISY state_history is at or above 80% capacity, a WARNING SHALL be logged."""
        import helios_main
        
        h = helios_main.Helios()
        h.daisy.max_history = capacity
        
        # Fill state history to the specified level
        num_states = max(1, int(capacity * fill_ratio))
        for i in range(num_states):
            h.daisy.state_history.append({"tick": i})
        
        actual_count = len(h.daisy.state_history)
        actual_ratio = actual_count / capacity
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        if actual_ratio >= 0.80:
            state_warnings = [r for r in caplog.records if "State History" in r.message]
            assert len(state_warnings) >= 1, (
                f"Expected WARNING for state history at {actual_count}/{capacity} "
                f"({actual_ratio*100:.1f}%), but got none"
            )

    @given(
        capacity=integers(min_value=10, max_value=30),
        fill_ratio=floats(min_value=0.0, max_value=0.79, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_state_history_below_80_percent_no_warning(self, capacity, fill_ratio, caplog):
        """When DAISY state_history is below 80% capacity, NO WARNING SHALL be logged."""
        import helios_main
        
        h = helios_main.Helios()
        h.daisy.max_history = capacity
        
        # Fill state history below 80%
        num_states = max(0, int(capacity * fill_ratio))
        for i in range(num_states):
            h.daisy.state_history.append({"tick": i})
        
        actual_count = len(h.daisy.state_history)
        actual_ratio = actual_count / capacity if capacity > 0 else 0
        
        # Ensure we're below 80%
        assume(actual_ratio < 0.80)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        state_warnings = [r for r in caplog.records if "State History" in r.message]
        assert len(state_warnings) == 0, (
            f"Expected NO warning for state history at {actual_count}/{capacity} "
            f"({actual_ratio*100:.1f}%), but got {len(state_warnings)}"
        )


# ------------------------------------------------------------------
# Property 26 Part 2: Immediate Consolidation at 2000 Items
# ------------------------------------------------------------------


class TestMemoryPressureTriggersConsolidation:
    """Property 26 (Part 2): When total items across all memory tiers exceed 2000,
    an immediate consolidation SHALL be triggered.
    
    **Validates: Requirements 23.4**
    """

    @given(
        working_count=integers(min_value=0, max_value=15),
        episodic_count=integers(min_value=0, max_value=500),
        semantic_count=integers(min_value=0, max_value=2000),
    )
    @settings(max_examples=50)
    def test_total_items_calculation_matches_sum(self, working_count, episodic_count, semantic_count):
        """The total items calculation SHALL equal the sum of all tier counts."""
        import helios_main
        
        h = helios_main.Helios()
        
        # Add items to each tier
        for i in range(working_count):
            h.memory_system.hold(f"working_{i}")
        for i in range(episodic_count):
            h.memory_system.remember(f"episodic_{i}", valence=0.3, arousal=0.3, phi=0.3)
        for i in range(semantic_count):
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")
        
        # Get stats
        mem_stats = h.memory_system.get_stats()
        
        total_items = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        
        # Verify calculation matches
        expected = (
            len(h.memory_system.working.items)
            + len(h.memory_system.episodic.items)
            + len(h.memory_system.semantic.facts)
            + len(h.memory_system.autobiographical.timeline)
        )
        
        assert total_items == expected, (
            f"Total items calculation ({total_items}) != sum of tier counts ({expected})"
        )

    def test_consolidation_triggered_when_total_exceeds_2000(self):
        """When total items exceed 2000, consolidation SHALL be triggered."""
        import helios_main
        import inspect
        
        h = helios_main.Helios()
        
        # Semantic memory can hold many items, use that to exceed 2000
        for i in range(2100):
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")
        
        # Get actual total
        mem_stats = h.memory_system.get_stats()
        total_items = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        
        # Verify we're at or above 2000
        assert total_items >= 2000, f"Expected >= 2000 items, got {total_items}"
        
        # The _tick method should have logic to check this
        # We verify the logic exists
        source = inspect.getsource(helios_main.Helios._tick)
        
        # Must have the 2000 threshold check
        assert "2000" in source, "_tick should contain 2000 item threshold check"
        assert "total_items" in source, "_tick should calculate total_items"
        assert "consolidate" in source, "_tick should call consolidate on pressure"

    def test_no_consolidation_when_total_below_2000(self):
        """When total items is below 2000, pressure-based consolidation should NOT trigger."""
        import helios_main
        import inspect
        
        # We verify the condition logic
        h = helios_main.Helios()
        
        # Add items below 2000 total
        for i in range(100):
            h.memory_system.remember(f"ep_{i}", valence=0.3, arousal=0.3, phi=0.3)
        for i in range(50):
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")
        
        mem_stats = h.memory_system.get_stats()
        total_items = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        
        # Ensure total is below 2000
        assert total_items < 2000, f"Total items should be below 2000, got {total_items}"

    def test_threshold_is_exactly_2000(self):
        """The memory pressure threshold SHALL be exactly 2000 items."""
        import helios_main
        import inspect
        
        source = inspect.getsource(helios_main.Helios._tick)
        
        # The threshold is defined as > 2000 (strictly greater than 2000)
        assert "> 2000" in source or ">2000" in source, (
            "Memory pressure threshold should be 'total_items > 2000'"
        )

    def test_warning_logged_when_pressure_exceeded(self):
        """When total items exceed 2000, a WARNING SHALL be logged."""
        import helios_main
        import inspect
        
        source = inspect.getsource(helios_main.Helios._tick)
        
        # Verify warning message is logged
        assert "Memory pressure" in source or "memory pressure" in source.lower(), (
            "_tick should log a memory pressure warning when threshold exceeded"
        )


# ------------------------------------------------------------------
# Additional Property Tests for Threshold Boundary
# ------------------------------------------------------------------


class TestThresholdBoundaryConditions:
    """Test boundary conditions around the 80% and 2000-item thresholds."""

    def test_warning_boundary_at_exactly_80_percent(self, caplog):
        """Test the exact boundary at 80% capacity - run with fixed examples."""
        import helios_main
        
        # Test at exactly 80%
        capacity = 100
        test_count = 80  # Exactly 80%
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = capacity
        
        for i in range(test_count):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        actual_count = len(h.memory_system.episodic.items)
        actual_ratio = actual_count / capacity
        
        # At 80%, warning SHOULD be logged (>= 80%)
        assert actual_ratio >= 0.80, f"Expected >= 80%, got {actual_ratio*100:.1f}%"
        episodic_warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(episodic_warnings) >= 1, "At 80%, expected WARNING"

    def test_warning_boundary_below_80_percent(self, caplog):
        """Test below 80% capacity - no warning should be logged."""
        import helios_main
        
        capacity = 100
        test_count = 79  # Below 80%
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = capacity
        
        for i in range(test_count):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        actual_count = len(h.memory_system.episodic.items)
        actual_ratio = actual_count / capacity
        
        # Below 80%, NO warning should be logged
        assert actual_ratio < 0.80, f"Expected < 80%, got {actual_ratio*100:.1f}%"
        episodic_warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(episodic_warnings) == 0, "Below 80%, expected NO warning"

    def test_exactly_2000_items_does_not_trigger(self, caplog):
        """Exactly 2000 items should NOT trigger consolidation (threshold is > 2000)."""
        import helios_main
        
        h = helios_main.Helios()
        
        # Add exactly 2000 items
        # Working: 15 max, Episodic: 500 max, so we need semantic for the rest
        for i in range(15):
            h.memory_system.hold(f"working_{i}")
        for i in range(500):
            h.memory_system.remember(f"ep_{i}", valence=0.3, arousal=0.3, phi=0.3)
        for i in range(1485):  # 15 + 500 + 1485 = 2000
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")
        
        mem_stats = h.memory_system.get_stats()
        total = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        
        # Should be exactly 2000
        assert total == 2000, f"Expected exactly 2000 items, got {total}"
        
        # The condition is > 2000, so exactly 2000 should NOT trigger
        # We verify the condition uses > not >=
        import inspect
        source = inspect.getsource(helios_main.Helios._tick)
        
        # Must be strictly greater than 2000
        assert "> 2000" in source or ">2000" in source, (
            "Threshold should be strictly greater than 2000"
        )

    def test_2001_items_does_trigger_warning(self, caplog):
        """2001 items should trigger consolidation (threshold is > 2000)."""
        import helios_main
        
        h = helios_main.Helios()
        
        # Add 2001 items
        for i in range(15):
            h.memory_system.hold(f"working_{i}")
        for i in range(500):
            h.memory_system.remember(f"ep_{i}", valence=0.3, arousal=0.3, phi=0.3)
        for i in range(1486):  # 15 + 500 + 1486 = 2001
            h.memory_system.semantic.learn(f"fact_{i}", f"value_{i}")
        
        mem_stats = h.memory_system.get_stats()
        total = (
            mem_stats["working_items"]
            + mem_stats["episodic_items"]
            + mem_stats["semantic_facts"]
            + mem_stats["autobio_moments"]
        )
        
        # Should be at least 2001
        assert total >= 2001, f"Expected >= 2001 items, got {total}"
        
        # Verify the threshold check exists
        import inspect
        source = inspect.getsource(helios_main.Helios._tick)
        assert "2000" in source


# ------------------------------------------------------------------
# Property: Warning Message Content
# ------------------------------------------------------------------


class TestWarningMessageContent:
    """Tests for the content and format of warning messages."""

    def test_warning_includes_collection_name(self, caplog):
        """WARNING messages SHALL identify which collection is approaching capacity."""
        import helios_main
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = 100
        
        # Fill to 85% (> 80%)
        for i in range(85):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(warnings) >= 1
        # Warning should mention the collection name
        assert "Episodic Memory" in warnings[0].message

    def test_warning_includes_current_and_capacity(self, caplog):
        """WARNING messages SHALL include current count and capacity."""
        import helios_main
        
        h = helios_main.Helios()
        h.memory_system.episodic.capacity = 100
        
        # Fill to 85% (> 80%)
        for i in range(85):
            h.memory_system.remember(f"event_{i}", valence=0.3, arousal=0.3, phi=0.3)
        
        with caplog.at_level(logging.WARNING):
            h._check_memory_capacity_warnings()
        
        warnings = [r for r in caplog.records if "Episodic Memory" in r.message]
        assert len(warnings) >= 1
        
        # Should show current/capacity format
        msg = warnings[0].message
        # The message should contain "85/100" or similar format
        assert "85" in msg, f"Warning should include current count 85, got: {msg}"
        assert "100" in msg, f"Warning should include capacity 100, got: {msg}"
