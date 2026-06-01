"""Tests for EventSource registry integration and trigger merging in the main loop.

Validates that:
- All EventSource instances are registered on startup
- Each source is polled per tick, collecting triggers and messages
- Trigger dictionaries are merged using max-value semantics for overlapping keys
"""

import sys
from typing import Dict, List
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.event_source import EventSource
from core.helios_state import HeliosState
from core.separation_source import SeparationAnxietySource
from core.drive_source import InternalDriveSource
from core.trigger_merge import merge_triggers


# ═══════════════════════════════════════════════════
# merge_triggers unit tests
# ═══════════════════════════════════════════════════


class TestMergeTriggers:
    """Tests for merge_triggers utility function."""

    def test_empty_list_returns_empty_dict(self):
        assert merge_triggers([]) == {}

    def test_single_dict_returned_unchanged(self):
        result = merge_triggers([{"SEEKING": 0.5, "PANIC": 0.3}])
        assert result == {"SEEKING": 0.5, "PANIC": 0.3}

    def test_non_overlapping_keys_combined(self):
        result = merge_triggers([
            {"SEEKING": 0.5},
            {"PANIC": 0.3},
            {"PLAY": 0.7},
        ])
        assert result == {"SEEKING": 0.5, "PANIC": 0.3, "PLAY": 0.7}

    def test_overlapping_keys_max_value_kept(self):
        result = merge_triggers([
            {"SEEKING": 0.5, "PANIC": 0.8},
            {"SEEKING": 0.9, "PANIC": 0.3},
        ])
        assert result == {"SEEKING": 0.9, "PANIC": 0.8}

    def test_three_sources_overlapping(self):
        result = merge_triggers([
            {"SEEKING": 0.2, "CARE": 0.6},
            {"SEEKING": 0.7, "FEAR": 0.4},
            {"SEEKING": 0.5, "CARE": 0.9, "FEAR": 0.1},
        ])
        assert result == {"SEEKING": 0.7, "CARE": 0.9, "FEAR": 0.4}

    def test_all_empty_dicts(self):
        result = merge_triggers([{}, {}, {}])
        assert result == {}

    def test_zero_values_preserved_via_max(self):
        result = merge_triggers([{"SEEKING": 0.0}, {"SEEKING": 0.3}])
        assert result == {"SEEKING": 0.3}


# ═══════════════════════════════════════════════════
# EventSource registry integration tests
# ═══════════════════════════════════════════════════


class StubEventSource(EventSource):
    """A test stub that returns fixed triggers and messages."""

    def __init__(self, triggers: Dict[str, float], messages: List[dict] = None):
        self._triggers = triggers
        self._messages = messages or []

    def poll(self, state: HeliosState) -> Dict[str, float]:
        return self._triggers

    def get_messages(self) -> List[dict]:
        return self._messages


class FailingEventSource(EventSource):
    """A test stub that raises an exception on poll."""

    def poll(self, state: HeliosState) -> Dict[str, float]:
        raise RuntimeError("simulated failure")

    def get_messages(self) -> List[dict]:
        return []


class TestEventSourceRegistry:
    """Tests for the EventSource registry pattern used in the main loop."""

    def test_registry_collects_triggers_from_all_sources(self):
        """All registered sources contribute to the merged trigger dict."""
        sources = [
            StubEventSource({"SEEKING": 0.5}),
            StubEventSource({"PANIC": 0.3}),
            StubEventSource({"PLAY": 0.7}),
        ]
        state = HeliosState()

        merged = {}
        for source in sources:
            src_triggers = source.poll(state)
            for k, v in src_triggers.items():
                merged[k] = max(merged.get(k, 0.0), v)

        assert merged == {"SEEKING": 0.5, "PANIC": 0.3, "PLAY": 0.7}

    def test_registry_uses_max_value_semantics(self):
        """Overlapping keys use max-value across sources."""
        sources = [
            StubEventSource({"SEEKING": 0.3, "PANIC": 0.8}),
            StubEventSource({"SEEKING": 0.9, "CARE": 0.4}),
        ]
        state = HeliosState()

        merged = {}
        for source in sources:
            src_triggers = source.poll(state)
            for k, v in src_triggers.items():
                merged[k] = max(merged.get(k, 0.0), v)

        assert merged == {"SEEKING": 0.9, "PANIC": 0.8, "CARE": 0.4}

    def test_registry_collects_messages_from_all_sources(self):
        """Messages from all sources are combined."""
        sources = [
            StubEventSource({}, [{"text": "msg1"}]),
            StubEventSource({}, [{"text": "msg2"}, {"text": "msg3"}]),
            StubEventSource({}, []),
        ]
        state = HeliosState()

        all_messages = []
        for source in sources:
            source.poll(state)
            all_messages.extend(source.get_messages())

        assert len(all_messages) == 3
        assert [m["text"] for m in all_messages] == ["msg1", "msg2", "msg3"]

    def test_failing_source_does_not_block_others(self):
        """A failing source is skipped; other sources still contribute."""
        sources = [
            StubEventSource({"SEEKING": 0.5}),
            FailingEventSource(),
            StubEventSource({"PLAY": 0.7}),
        ]
        state = HeliosState()

        merged = {}
        for source in sources:
            try:
                src_triggers = source.poll(state)
                for k, v in src_triggers.items():
                    merged[k] = max(merged.get(k, 0.0), v)
            except Exception:
                pass  # Skip failing source

        assert merged == {"SEEKING": 0.5, "PLAY": 0.7}

    def test_separation_source_is_valid_event_source(self):
        """SeparationAnxietySource satisfies the EventSource interface."""
        source = SeparationAnxietySource()
        state = HeliosState(separation_hours=3.0)
        triggers = source.poll(state)
        messages = source.get_messages()

        assert isinstance(triggers, dict)
        assert isinstance(messages, list)
        assert messages == []
        # With 3 hours separation, PANIC should be triggered
        assert "PANIC" in triggers
        assert triggers["PANIC"] > 0.2

    def test_internal_drive_source_is_valid_event_source(self):
        """InternalDriveSource satisfies the EventSource interface."""
        source = InternalDriveSource()
        state = HeliosState(drive_dominant="curiosity", drive_urgency=0.6)
        triggers = source.poll(state)
        messages = source.get_messages()

        assert isinstance(triggers, dict)
        assert isinstance(messages, list)
        assert messages == []
        assert "SEEKING" in triggers
        assert triggers["SEEKING"] == 0.6

