"""
Unit tests for Memory System state persistence (Requirements 22.1-22.5).

Tests the save/load functionality for:
  - SemanticMemory facts
  - EpisodicMemory items (high-importance only, > 0.3)
  - MemorySystem unified interface
  - Corruption handling (graceful degradation with warning)
"""

import json
import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from memory import MemorySystem, SemanticMemory, EpisodicMemory, MemoryItem


@pytest.fixture
def tmp_data_dir():
    """Create a temporary data directory for each test."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------
# SemanticMemory persistence tests
# ------------------------------------------------------------------


class TestSemanticMemoryPersistence:
    """Tests for SemanticMemory.save_to_file() and load_from_file()."""

    def test_save_creates_valid_json_file(self, tmp_data_dir):
        """Saved file should be valid JSON with expected structure."""
        sm = SemanticMemory()
        sm.learn("test.key", "value", tags=["test"], confidence=0.8)

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm.save_to_file(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert "timestamp" in data
        assert "facts" in data
        assert len(data["facts"]) == 1
        assert data["facts"][0]["key"] == "test.key"
        assert data["facts"][0]["value"] == "value"
        assert data["facts"][0]["confidence"] == 0.8
        assert "test" in data["facts"][0]["tags"]

    def test_load_restores_facts(self, tmp_data_dir):
        """Load should restore facts to a fresh SemanticMemory instance."""
        sm1 = SemanticMemory()
        sm1.learn("key1", "value1", tags=["tag1"])
        sm1.learn("key2", "value2", tags=["tag2"])

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm1.save_to_file(filepath)

        sm2 = SemanticMemory()
        sm2.load_from_file(filepath)

        assert len(sm2.facts) == 2
        assert sm2.know("key1") == "value1"
        assert sm2.know("key2") == "value2"

    def test_load_restores_tag_index(self, tmp_data_dir):
        """Load should rebuild the concepts tag index."""
        sm1 = SemanticMemory()
        sm1.learn("key1", "v1", tags=["shared", "unique1"])
        sm1.learn("key2", "v2", tags=["shared", "unique2"])

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm1.save_to_file(filepath)

        sm2 = SemanticMemory()
        sm2.load_from_file(filepath)

        # Check tag index is rebuilt
        assert "shared" in sm2.concepts
        assert "unique1" in sm2.concepts
        assert "unique2" in sm2.concepts
        assert "key1" in sm2.concepts["shared"]
        assert "key2" in sm2.concepts["shared"]

    def test_load_preserves_access_count(self, tmp_data_dir):
        """Load should restore last_accessed and access_count."""
        sm1 = SemanticMemory()
        sm1.learn("key", "value")
        # Access multiple times
        for _ in range(5):
            sm1.know("key")

        original_count = sm1.facts["key"].access_count
        original_accessed = sm1.facts["key"].last_accessed

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm1.save_to_file(filepath)

        sm2 = SemanticMemory()
        sm2.load_from_file(filepath)

        assert sm2.facts["key"].access_count == original_count
        assert sm2.facts["key"].last_accessed == original_accessed

    def test_missing_file_no_error(self, tmp_data_dir, caplog):
        """Missing file should log debug message and not crash."""
        sm = SemanticMemory()

        with caplog.at_level(logging.DEBUG):
            sm.load_from_file(os.path.join(tmp_data_dir, "nonexistent.json"))

        assert len(sm.facts) == 0  # Empty storage initialized

    def test_corrupted_json_no_crash(self, tmp_data_dir, caplog):
        """Corrupted JSON should log warning and init empty storage."""
        filepath = os.path.join(tmp_data_dir, "semantic.json")
        with open(filepath, "w") as f:
            f.write("not valid json {{{")

        sm = SemanticMemory()

        with caplog.at_level(logging.WARNING):
            sm.load_from_file(filepath)

        assert len(sm.facts) == 0  # Empty storage initialized
        assert any("corrupted" in r.message.lower() for r in caplog.records)

    def test_non_dict_root_ignored(self, tmp_data_dir, caplog):
        """Non-dict root should be ignored with warning."""
        filepath = os.path.join(tmp_data_dir, "semantic.json")
        with open(filepath, "w") as f:
            json.dump(["not", "a", "dict"], f)

        sm = SemanticMemory()

        with caplog.at_level(logging.WARNING):
            sm.load_from_file(filepath)

        assert len(sm.facts) == 0

    def test_atomic_write_no_partial_files(self, tmp_data_dir):
        """Save should not leave .tmp files after completion."""
        sm = SemanticMemory()
        sm.learn("key", "value")

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm.save_to_file(filepath)

        files = os.listdir(tmp_data_dir)
        tmp_files = [f for f in files if f.endswith(".tmp")]
        assert len(tmp_files) == 0


# ------------------------------------------------------------------
# EpisodicMemory persistence tests
# ------------------------------------------------------------------


class TestEpisodicMemoryPersistence:
    """Tests for EpisodicMemory.save_to_file() and load_from_file()."""

    def test_save_only_high_importance_items(self, tmp_data_dir):
        """Only items with importance > 0.3 should be saved (Requirement 22.3)."""
        em = EpisodicMemory()
        # Add items with varying importance
        em.record("High importance", valence=0.8, arousal=0.7, phi=0.6)  # High
        em.record("Low importance", valence=0.1, arousal=0.1, phi=0.1)   # Low
        em.record("Medium high", valence=0.5, arousal=0.5, phi=0.5)      # Should be saved

        # Check importance scores
        high_items = [it for it in em.items if it.importance > 0.3]
        assert len(high_items) >= 2  # At least high and medium-high

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        em.save_to_file(filepath, importance_threshold=0.3)

        # Verify saved file
        with open(filepath, "r") as f:
            data = json.load(f)
        assert len(data["items"]) == len(high_items)

    def test_load_restores_items(self, tmp_data_dir):
        """Load should restore episodic items to a fresh instance."""
        em1 = EpisodicMemory()
        em1.record("Important event", valence=0.8, arousal=0.6, phi=0.5)

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        em1.save_to_file(filepath)

        em2 = EpisodicMemory()
        em2.load_from_file(filepath)

        assert len(em2.items) == 1
        assert em2.items[0].summary == "Important event"
        assert abs(em2.items[0].valence - 0.8) < 0.001

    def test_load_preserves_emotional_fields(self, tmp_data_dir):
        """Load should preserve valence, arousal, phi, emotional_tag."""
        em1 = EpisodicMemory()
        em1.record("Emotional event", valence=0.7, arousal=0.5, phi=0.4)

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        em1.save_to_file(filepath)

        em2 = EpisodicMemory()
        em2.load_from_file(filepath)

        item = em2.items[0]
        assert abs(item.valence - 0.7) < 0.001
        assert abs(item.arousal - 0.5) < 0.001
        assert abs(item.phi - 0.4) < 0.001
        assert item.emotional_tag in ["ecstatic", "pleasant", "serene"]

    def test_load_updates_total_recorded(self, tmp_data_dir):
        """Load should update total_recorded counter."""
        em1 = EpisodicMemory()
        em1.record("Event 1", valence=0.7, arousal=0.5, phi=0.4)
        em1.record("Event 2", valence=0.6, arousal=0.4, phi=0.3)

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        em1.save_to_file(filepath)

        em2 = EpisodicMemory()
        initial_count = em2.total_recorded
        em2.load_from_file(filepath)

        assert em2.total_recorded == initial_count + len(em2.items)

    def test_missing_file_no_error(self, tmp_data_dir, caplog):
        """Missing file should not crash, init with empty storage."""
        em = EpisodicMemory()

        with caplog.at_level(logging.DEBUG):
            em.load_from_file(os.path.join(tmp_data_dir, "nonexistent.json"))

        assert len(em.items) == 0

    def test_corrupted_json_no_crash(self, tmp_data_dir, caplog):
        """Corrupted JSON should log warning and init empty storage (Requirement 22.5)."""
        filepath = os.path.join(tmp_data_dir, "episodic.json")
        with open(filepath, "w") as f:
            f.write("{corrupted: json")

        em = EpisodicMemory()

        with caplog.at_level(logging.WARNING):
            em.load_from_file(filepath)

        assert len(em.items) == 0
        assert any("corrupted" in r.message.lower() for r in caplog.records)


# ------------------------------------------------------------------
# MemorySystem unified persistence tests
# ------------------------------------------------------------------


class TestMemorySystemPersistence:
    """Tests for MemorySystem.save_to_directory() and load_from_directory()."""

    def test_save_creates_both_files(self, tmp_data_dir):
        """save_to_directory should create both semantic and episodic files."""
        ms = MemorySystem()
        ms.learn("key", "value")
        ms.remember("Important event", valence=0.8, arousal=0.6, phi=0.5)

        ms.save_to_directory(tmp_data_dir)

        assert os.path.exists(os.path.join(tmp_data_dir, "semantic_memory.json"))
        assert os.path.exists(os.path.join(tmp_data_dir, "episodic_memory.json"))

    def test_round_trip_preserves_state(self, tmp_data_dir):
        """Save then load should preserve all data."""
        ms1 = MemorySystem()
        ms1.learn("fact1", "value1", tags=["tag1"])
        ms1.learn("fact2", "value2")
        ms1.remember("Important memory", valence=0.8, arousal=0.6, phi=0.5)

        ms1.save_to_directory(tmp_data_dir)

        ms2 = MemorySystem()
        ms2.load_from_directory(tmp_data_dir)

        assert len(ms2.semantic.facts) == 2
        assert ms2.know("fact1") == "value1"
        assert ms2.know("fact2") == "value2"
        assert len(ms2.episodic.items) == 1
        assert ms2.episodic.items[0].summary == "Important memory"

    def test_load_handles_missing_directory(self, tmp_data_dir, caplog):
        """Load from empty directory should not crash."""
        ms = MemorySystem()

        with caplog.at_level(logging.DEBUG):
            ms.load_from_directory(tmp_data_dir)

        assert len(ms.semantic.facts) == 0
        assert len(ms.episodic.items) == 0

    def test_load_handles_corrupted_files(self, tmp_data_dir, caplog):
        """Corrupted files should be handled gracefully (Requirement 22.5)."""
        # Create corrupted files
        with open(os.path.join(tmp_data_dir, "semantic_memory.json"), "w") as f:
            f.write("not json")
        with open(os.path.join(tmp_data_dir, "episodic_memory.json"), "w") as f:
            f.write("also not json")

        ms = MemorySystem()

        with caplog.at_level(logging.WARNING):
            ms.load_from_directory(tmp_data_dir)

        # Should initialize with empty storage
        assert len(ms.semantic.facts) == 0
        assert len(ms.episodic.items) == 0


# ------------------------------------------------------------------
# Requirement 22 validation tests
# ------------------------------------------------------------------


class TestRequirement22Validation:
    """
    Validates Requirements 22.1-22.5.

    22.1: SemanticMemory facts serialized on shutdown
    22.2: SemanticMemory facts loaded on startup
    22.3: EpisodicMemory items (importance > 0.3) serialized on shutdown
    22.4: High-importance EpisodicMemory items loaded on startup
    22.5: Corrupted files log warning, init empty without crashing
    """

    def test_req_22_1_semantic_serialized_on_shutdown(self, tmp_data_dir):
        """Requirement 22.1: SemanticMemory facts are serialized."""
        ms = MemorySystem()
        ms.learn("persistent_fact", "persistent_value")

        ms.save_to_directory(tmp_data_dir)

        # Verify file exists and contains the fact
        filepath = os.path.join(tmp_data_dir, "semantic_memory.json")
        assert os.path.exists(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)
        assert any(f["key"] == "persistent_fact" for f in data["facts"])

    def test_req_22_2_semantic_loaded_on_startup(self, tmp_data_dir):
        """Requirement 22.2: SemanticMemory facts are loaded on startup."""
        # Save some facts
        ms1 = MemorySystem()
        ms1.learn("startup_fact", "startup_value")
        ms1.save_to_directory(tmp_data_dir)

        # Simulate restart by creating new instance
        ms2 = MemorySystem()
        ms2.load_from_directory(tmp_data_dir)

        assert ms2.know("startup_fact") == "startup_value"

    def test_req_22_3_episodic_serializes_high_importance_only(self, tmp_data_dir):
        """Requirement 22.3: Only EpisodicMemory items with importance > 0.3 are serialized."""
        ms = MemorySystem()
        # High importance event (should be saved)
        ms.remember("High importance event", valence=0.9, arousal=0.8, phi=0.7)
        # Low importance event (should NOT be saved)
        ms.remember("Low importance event", valence=0.1, arousal=0.1, phi=0.1)

        ms.save_to_directory(tmp_data_dir)

        # Check saved file only has high importance items
        filepath = os.path.join(tmp_data_dir, "episodic_memory.json")
        with open(filepath, "r") as f:
            data = json.load(f)

        for item in data["items"]:
            assert item["importance"] > 0.3

    def test_req_22_4_episodic_loaded_on_startup(self, tmp_data_dir):
        """Requirement 22.4: High-importance EpisodicMemory items are loaded on startup."""
        # Save a high-importance memory
        ms1 = MemorySystem()
        ms1.remember("Memorable event", valence=0.8, arousal=0.7, phi=0.6)
        ms1.save_to_directory(tmp_data_dir)

        # Simulate restart
        ms2 = MemorySystem()
        ms2.load_from_directory(tmp_data_dir)

        assert len(ms2.episodic.items) == 1
        assert ms2.episodic.items[0].summary == "Memorable event"

    def test_req_22_5_corrupted_file_logs_warning_no_crash(self, tmp_data_dir, caplog):
        """Requirement 22.5: Corrupted files log warning and init empty without crashing."""
        # Create a corrupted semantic memory file
        semantic_path = os.path.join(tmp_data_dir, "semantic_memory.json")
        with open(semantic_path, "w") as f:
            f.write("<<<CORRUPTED>>>")

        ms = MemorySystem()

        with caplog.at_level(logging.WARNING):
            ms.load_from_directory(tmp_data_dir)

        # Should NOT crash, should have empty storage
        assert len(ms.semantic.facts) == 0
        assert len(ms.episodic.items) == 0

        # Should have logged a warning
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warning_records) > 0


# ------------------------------------------------------------------
# Edge case tests
# ------------------------------------------------------------------


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_save_empty_semantic_memory(self, tmp_data_dir):
        """Saving empty SemanticMemory should produce valid JSON."""
        sm = SemanticMemory()

        filepath = os.path.join(tmp_data_dir, "semantic.json")
        sm.save_to_file(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert data["facts"] == []

    def test_save_empty_episodic_memory(self, tmp_data_dir):
        """Saving empty EpisodicMemory should produce valid JSON."""
        em = EpisodicMemory()

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        em.save_to_file(filepath)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert data["version"] == 1
        assert data["items"] == []

    def test_custom_importance_threshold(self, tmp_data_dir):
        """save_to_file should respect custom importance_threshold."""
        em = EpisodicMemory()
        em.record("Event A", valence=0.5, arousal=0.5, phi=0.5)  # importance ~0.35
        em.record("Event B", valence=0.9, arousal=0.9, phi=0.9)  # importance ~1.14

        filepath = os.path.join(tmp_data_dir, "episodic.json")
        # Use threshold of 0.5 - only Event B should be saved
        em.save_to_file(filepath, importance_threshold=0.5)

        with open(filepath, "r") as f:
            data = json.load(f)

        assert len(data["items"]) == 1
        assert data["items"][0]["summary"] == "Event B"

    def test_load_with_extra_fields_in_json(self, tmp_data_dir):
        """Load should ignore unknown fields in JSON (forward compatibility)."""
        filepath = os.path.join(tmp_data_dir, "semantic.json")
        with open(filepath, "w") as f:
            json.dump({
                "version": 1,
                "timestamp": 12345.0,
                "facts": [{"key": "k", "value": "v", "confidence": 0.5,
                           "future_field": "should be ignored"}],
                "future_section": "also ignored"
            }, f)

        sm = SemanticMemory()
        sm.load_from_file(filepath)

        assert len(sm.facts) == 1
        assert sm.know("k") == "v"
