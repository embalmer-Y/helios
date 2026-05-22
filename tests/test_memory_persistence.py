"""Unit tests for Memory System state persistence.

Tests the save/load round-trip for SemanticMemory and EpisodicMemory,
corruption handling, and selective serialization (importance > 0.3).

Validates: Requirements 22.1, 22.2, 22.3, 22.4, 22.5
"""

import json
import logging
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from utils.persistence import StatePersistence
from memory_system import MemorySystem, SemanticMemory, EpisodicMemory


@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory for each test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def persistence(tmp_data_dir):
    """Create a StatePersistence instance with a temp directory."""
    return StatePersistence(tmp_data_dir)


@pytest.fixture
def memory_system():
    """Create a MemorySystem with some test data."""
    ms = MemorySystem(working_capacity=15, episodic_capacity=500)
    return ms


# ------------------------------------------------------------------
# Semantic Memory persistence tests
# ------------------------------------------------------------------


class TestSemanticMemoryPersistence:
    """Validates: Requirements 22.1, 22.2"""

    def test_save_and_load_semantic_facts(self, persistence, memory_system):
        """Semantic facts survive a save/load round-trip."""
        memory_system.learn("helios.name", "Helios", tags=["identity"], confidence=0.9)
        memory_system.learn("helios.creator", "radxa", tags=["identity"], confidence=0.8)
        memory_system.learn("favorite.color", "blue", tags=["preference"], confidence=0.6)

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        assert len(loaded["semantic_facts"]) == 3
        keys = {f["key"] for f in loaded["semantic_facts"]}
        assert "helios.name" in keys
        assert "helios.creator" in keys
        assert "favorite.color" in keys

    def test_semantic_fact_values_preserved(self, persistence, memory_system):
        """Fact values and confidence are preserved through round-trip."""
        memory_system.learn("test.key", "test_value", confidence=0.75)

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        fact = loaded["semantic_facts"][0]
        assert fact["key"] == "test.key"
        assert fact["value"] == "test_value"
        assert abs(fact["confidence"] - 0.75) < 0.001

    def test_semantic_tags_preserved(self, persistence, memory_system):
        """Tags are preserved through round-trip."""
        memory_system.learn("tagged.fact", "value", tags=["tag1", "tag2"])

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        fact = loaded["semantic_facts"][0]
        assert set(fact["tags"]) == {"tag1", "tag2"}

    def test_semantic_access_count_preserved(self, persistence, memory_system):
        """Access count is preserved through round-trip."""
        memory_system.learn("accessed.fact", "value")
        # Access the fact multiple times
        memory_system.know("accessed.fact")
        memory_system.know("accessed.fact")
        memory_system.know("accessed.fact")

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        fact = loaded["semantic_facts"][0]
        assert fact["access_count"] >= 3

    def test_empty_semantic_memory_saves_empty_list(self, persistence, memory_system):
        """Empty semantic memory saves an empty facts list."""
        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        assert loaded["semantic_facts"] == []

    def test_load_missing_semantic_file_returns_empty(self, persistence):
        """Missing semantic memory file returns empty list."""
        loaded = persistence.load_memory_state()
        assert loaded["semantic_facts"] == []

    def test_load_corrupted_semantic_file_returns_empty(self, persistence, tmp_data_dir, caplog):
        """Corrupted semantic memory file returns empty list with warning."""
        filepath = os.path.join(tmp_data_dir, "semantic_memory.json")
        with open(filepath, "w") as f:
            f.write("not valid json {{{")

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["semantic_facts"] == []
        assert any("corrupted" in r.message.lower() or "jsondecodeerror" in r.message.lower()
                   for r in caplog.records)

    def test_load_invalid_structure_returns_empty(self, persistence, tmp_data_dir, caplog):
        """Semantic file with invalid structure returns empty list with warning."""
        filepath = os.path.join(tmp_data_dir, "semantic_memory.json")
        with open(filepath, "w") as f:
            json.dump({"version": 1, "timestamp": 0.0, "facts": "not a list"}, f)

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["semantic_facts"] == []


# ------------------------------------------------------------------
# Episodic Memory persistence tests
# ------------------------------------------------------------------


class TestEpisodicMemoryPersistence:
    """Validates: Requirements 22.3, 22.4"""

    def test_only_high_importance_items_saved(self, persistence, memory_system):
        """Only episodic items with importance > 0.3 are serialized."""
        # Record items with varying importance levels
        # High phi + high valence → high importance
        memory_system.remember("Important event", valence=0.8, arousal=0.7, phi=0.6)
        # Low phi + low valence → low importance
        memory_system.remember("Trivial event", valence=0.05, arousal=0.05, phi=0.1)

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        # Only the high-importance item should be saved
        items = loaded["episodic_items"]
        summaries = [it["summary"] for it in items]
        assert "Important event" in summaries
        # The trivial event should have importance < 0.3 and not be saved
        trivial_items = [it for it in items if it["summary"] == "Trivial event"]
        assert len(trivial_items) == 0

    def test_episodic_item_fields_preserved(self, persistence, memory_system):
        """All episodic item fields are preserved through round-trip."""
        memory_system.remember(
            "Test memory", valence=0.7, arousal=0.6, phi=0.5
        )

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        items = loaded["episodic_items"]
        assert len(items) >= 1
        item = items[0]
        assert item["summary"] == "Test memory"
        assert abs(item["valence"] - 0.7) < 0.01
        assert abs(item["arousal"] - 0.6) < 0.01
        assert abs(item["phi"] - 0.5) < 0.01
        assert "importance" in item
        assert "emotional_tag" in item
        assert "timestamp" in item
        assert "id" in item

    def test_empty_episodic_memory_saves_empty_list(self, persistence, memory_system):
        """Empty episodic memory saves an empty items list."""
        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        assert loaded["episodic_items"] == []

    def test_load_missing_episodic_file_returns_empty(self, persistence):
        """Missing episodic memory file returns empty list."""
        loaded = persistence.load_memory_state()
        assert loaded["episodic_items"] == []

    def test_load_corrupted_episodic_file_returns_empty(self, persistence, tmp_data_dir, caplog):
        """Corrupted episodic memory file returns empty list with warning."""
        filepath = os.path.join(tmp_data_dir, "episodic_memory.json")
        with open(filepath, "w") as f:
            f.write("<<<garbage>>>")

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["episodic_items"] == []

    def test_load_invalid_structure_returns_empty(self, persistence, tmp_data_dir, caplog):
        """Episodic file with invalid structure returns empty list with warning."""
        filepath = os.path.join(tmp_data_dir, "episodic_memory.json")
        with open(filepath, "w") as f:
            json.dump({"version": 1, "timestamp": 0.0, "items": "not a list"}, f)

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["episodic_items"] == []


# ------------------------------------------------------------------
# Full round-trip with MemorySystem restore
# ------------------------------------------------------------------


class TestMemorySystemRestore:
    """Validates: Requirements 22.2, 22.4"""

    def test_full_round_trip_semantic(self, persistence, memory_system):
        """Semantic facts survive save → load → restore cycle."""
        memory_system.learn("helios.name", "Helios", confidence=0.9)
        memory_system.learn("helios.version", "1.0", confidence=0.7)

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        # Create a fresh MemorySystem and restore
        ms2 = MemorySystem()
        ms2.restore_from_persistence(loaded)

        assert ms2.know("helios.name") == "Helios"
        assert ms2.know("helios.version") == "1.0"

    def test_full_round_trip_episodic(self, persistence, memory_system):
        """High-importance episodic items survive save → load → restore cycle."""
        memory_system.remember("Significant event", valence=0.8, arousal=0.7, phi=0.6)

        persistence.save_memory_state(memory_system)
        loaded = persistence.load_memory_state()

        ms2 = MemorySystem()
        ms2.restore_from_persistence(loaded)

        # The restored system should have the episodic item
        assert len(ms2.episodic.items) >= 1
        assert any(it.summary == "Significant event" for it in ms2.episodic.items)

    def test_restore_with_empty_state(self, memory_system):
        """Restoring from empty state doesn't crash."""
        memory_system.restore_from_persistence({
            "semantic_facts": [],
            "episodic_items": [],
        })
        assert len(memory_system.semantic.facts) == 0
        assert len(memory_system.episodic.items) == 0

    def test_restore_handles_malformed_facts_gracefully(self, memory_system, caplog):
        """Malformed facts are skipped with a warning."""
        with caplog.at_level(logging.WARNING):
            memory_system.restore_from_persistence({
                "semantic_facts": [
                    {"key": "valid.fact", "value": "ok", "confidence": 0.5},
                    {"no_key_field": True},  # Malformed
                    "not a dict",  # Malformed
                ],
                "episodic_items": [],
            })

        # Valid fact should be restored
        assert memory_system.know("valid.fact") == "ok"
        # Should have logged warnings for malformed items
        assert any("malformed" in r.message.lower() or "skipping" in r.message.lower()
                   for r in caplog.records)

    def test_restore_handles_malformed_episodes_gracefully(self, memory_system, caplog):
        """Malformed episodic items are skipped with a warning."""
        with caplog.at_level(logging.WARNING):
            memory_system.restore_from_persistence({
                "semantic_facts": [],
                "episodic_items": [
                    {"summary": "Valid item", "valence": 0.5, "arousal": 0.4, "phi": 0.3},
                    {"no_summary": True},  # Malformed
                ],
            })

        # Valid item should be restored
        assert len(memory_system.episodic.items) >= 1
        assert any(it.summary == "Valid item" for it in memory_system.episodic.items)


# ------------------------------------------------------------------
# Corruption safety tests (Requirement 22.5)
# ------------------------------------------------------------------


class TestCorruptionSafety:
    """Validates: Requirement 22.5 — corrupted files don't crash, init empty."""

    def test_semantic_file_with_null_bytes(self, persistence, tmp_data_dir, caplog):
        """File with null bytes is handled gracefully."""
        filepath = os.path.join(tmp_data_dir, "semantic_memory.json")
        with open(filepath, "wb") as f:
            f.write(b"\x00\x00\x00null bytes\x00\x00")

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["semantic_facts"] == []

    def test_episodic_file_with_truncated_json(self, persistence, tmp_data_dir, caplog):
        """Truncated JSON (simulating crash) is handled gracefully."""
        filepath = os.path.join(tmp_data_dir, "episodic_memory.json")
        with open(filepath, "w") as f:
            f.write('{"version": 1, "items": [{"summary": "test"')

        with caplog.at_level(logging.WARNING):
            loaded = persistence.load_memory_state()

        assert loaded["episodic_items"] == []

    def test_one_corrupted_file_doesnt_affect_other(self, persistence, tmp_data_dir, memory_system):
        """Corruption in one file doesn't prevent loading the other."""
        # Save valid semantic memory
        memory_system.learn("valid.fact", "value", confidence=0.8)
        persistence.save_memory_state(memory_system)

        # Corrupt the episodic file
        filepath = os.path.join(tmp_data_dir, "episodic_memory.json")
        with open(filepath, "w") as f:
            f.write("corrupted!")

        loaded = persistence.load_memory_state()

        # Semantic should still load fine
        assert len(loaded["semantic_facts"]) == 1
        assert loaded["semantic_facts"][0]["key"] == "valid.fact"
        # Episodic should be empty due to corruption
        assert loaded["episodic_items"] == []

    def test_version_field_present_in_saved_files(self, persistence, memory_system):
        """Saved files include version field for forward compatibility."""
        memory_system.learn("test", "value")
        memory_system.remember("test event", valence=0.8, arousal=0.7, phi=0.6)

        persistence.save_memory_state(memory_system)

        # Check semantic file
        sem_path = os.path.join(persistence._data_dir, "semantic_memory.json")
        with open(sem_path, "r") as f:
            sem_data = json.load(f)
        assert sem_data["version"] == 1
        assert "timestamp" in sem_data

        # Check episodic file
        ep_path = os.path.join(persistence._data_dir, "episodic_memory.json")
        with open(ep_path, "r") as f:
            ep_data = json.load(f)
        assert ep_data["version"] == 1
        assert "timestamp" in ep_data
