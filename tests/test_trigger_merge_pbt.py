"""Property-based tests for EventSource trigger merge with max-value semantics.

# Feature: helios-architecture-enhancement, Property 7: EventSource Trigger Merge with Max Semantics

**Validates: Requirements 10.4**
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hypothesis import given, settings
from hypothesis.strategies import (
    dictionaries,
    floats,
    lists,
    sampled_from,
)

from core.trigger_merge import merge_triggers


# The 7 Panksepp system keys used in Helios
PANKSEPP_SYSTEMS = ["SEEKING", "PLAY", "CARE", "PANIC", "FEAR", "RAGE", "LUST"]

# Strategy: a single Panksepp trigger dictionary
trigger_dict_strategy = dictionaries(
    keys=sampled_from(PANKSEPP_SYSTEMS),
    values=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    max_size=7,
)

# Strategy: a list of trigger dictionaries (simulating multiple EventSources)
trigger_dicts_strategy = lists(
    trigger_dict_strategy,
    min_size=0,
    max_size=10,
)


# ------------------------------------------------------------------
# Property 7: EventSource Trigger Merge with Max Semantics
# ------------------------------------------------------------------


class TestTriggerMergeMaxSemantics:
    """Property 7: For any set of Panksepp trigger dictionaries returned by
    multiple EventSources, the merged result SHALL map each system key to the
    maximum value across all sources.
    """

    @given(trigger_dicts=trigger_dicts_strategy)
    @settings(max_examples=200)
    def test_merged_keys_are_union_of_all_source_keys(self, trigger_dicts):
        """The merged result contains exactly the union of all keys from all sources."""
        merged = merge_triggers(trigger_dicts)

        expected_keys = set()
        for d in trigger_dicts:
            expected_keys.update(d.keys())

        assert set(merged.keys()) == expected_keys

    @given(trigger_dicts=trigger_dicts_strategy)
    @settings(max_examples=200)
    def test_merged_value_equals_max_across_sources(self, trigger_dicts):
        """Each key in the merged result maps to the maximum value for that key
        across all source dictionaries."""
        merged = merge_triggers(trigger_dicts)

        for key in merged:
            expected_max = max(d[key] for d in trigger_dicts if key in d)
            assert merged[key] == expected_max, (
                f"Key {key}: expected max {expected_max}, got {merged[key]}"
            )

    @given(trigger_dicts=trigger_dicts_strategy)
    @settings(max_examples=200)
    def test_merged_value_at_least_as_large_as_any_source(self, trigger_dicts):
        """For every key, the merged value is >= every individual source value."""
        merged = merge_triggers(trigger_dicts)

        for d in trigger_dicts:
            for key, value in d.items():
                assert merged[key] >= value, (
                    f"Key {key}: merged {merged[key]} < source {value}"
                )

    @given(trigger_dicts=trigger_dicts_strategy)
    @settings(max_examples=200)
    def test_empty_input_returns_empty_dict(self, trigger_dicts):
        """Merging an empty list of trigger dicts returns an empty dict."""
        result = merge_triggers([])
        assert result == {}

    @given(trigger_dicts=trigger_dicts_strategy)
    @settings(max_examples=200)
    def test_single_source_returns_same_dict(self, trigger_dicts):
        """Merging a single trigger dict returns the same key-value pairs."""
        for d in trigger_dicts:
            merged = merge_triggers([d])
            assert merged == d
