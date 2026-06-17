"""R100 T4: PersistedExperienceRecord additive extension (layer + memory_metadata) tests."""

from types import MappingProxyType

import pytest

from helios_v2.persistence import PersistedExperienceRecord, PersistenceError


def _base_record(**overrides) -> dict:
    defaults = dict(
        record_id="experience:r100:1",
        tick_id=1,
        continuity_kind="executed_outcome",
        outcome_class="self_changed",
        source_outcome_kind="planner_decision",
        source_outcome_id="decision:1",
        writeback_status="written",
        summary="a summary",
        requested_effect_summary="a request",
        applied_effect_summary="an effect",
        reason_trace=("a", "b"),
        linkage={"thought_cycle_result_id": "thought:1"},
    )
    defaults.update(overrides)
    return defaults


# ===========================================================================
# Layer field (additive, optional)
# ===========================================================================

class TestLayerField:
    def test_layer_none_default(self):
        """Default construction has layer=None (honest absence)."""
        record = PersistedExperienceRecord(**_base_record())
        assert record.layer is None

    def test_layer_none_explicit(self):
        """Explicit layer=None succeeds."""
        record = PersistedExperienceRecord(**_base_record(layer=None))
        assert record.layer is None

    def test_layer_l2_working(self):
        record = PersistedExperienceRecord(**_base_record(layer="L2_working"))
        assert record.layer == "L2_working"

    def test_layer_l3_short(self):
        record = PersistedExperienceRecord(**_base_record(layer="L3_short"))
        assert record.layer == "L3_short"

    def test_layer_l4_long(self):
        record = PersistedExperienceRecord(**_base_record(layer="L4_long"))
        assert record.layer == "L4_long"

    def test_layer_l5_autobiographical(self):
        record = PersistedExperienceRecord(**_base_record(layer="L5_autobiographical"))
        assert record.layer == "L5_autobiographical"

    def test_layer_invalid_rejected(self):
        with pytest.raises(PersistenceError, match="layer must be None or one of"):
            PersistedExperienceRecord(**_base_record(layer="invalid_layer"))

    def test_layer_l1_sensory_rejected(self):
        with pytest.raises(PersistenceError, match="layer must be None or one of"):
            PersistedExperienceRecord(**_base_record(layer="L1_sensory"))

    def test_layer_preserved_through_with_sequence(self):
        record = PersistedExperienceRecord(**_base_record(layer="L4_long"))
        stamped = record.with_sequence(1)
        assert stamped.layer == "L4_long"

    def test_layer_none_preserved_through_with_sequence(self):
        record = PersistedExperienceRecord(**_base_record())
        stamped = record.with_sequence(1)
        assert stamped.layer is None

    def test_layer_preserved_through_with_embedding(self):
        record = PersistedExperienceRecord(**_base_record(layer="L5_autobiographical"))
        embedded = record.with_embedding((0.1, 0.2, 0.3))
        assert embedded.layer == "L5_autobiographical"


# ===========================================================================
# memory_metadata field (additive, optional)
# ===========================================================================

class TestMemoryMetadataField:
    def test_memory_metadata_empty_default(self):
        """Default construction has memory_metadata=empty dict (frozen)."""
        record = PersistedExperienceRecord(**_base_record())
        assert record.memory_metadata == MappingProxyType({})

    def test_memory_metadata_with_values(self):
        record = PersistedExperienceRecord(**_base_record(memory_metadata={"objective_importance": "0.8"}))
        assert record.memory_metadata == MappingProxyType({"objective_importance": "0.8"})

    def test_memory_metadata_is_frozen(self):
        record = PersistedExperienceRecord(**_base_record(memory_metadata={"key": "value"}))
        with pytest.raises(TypeError):
            record.memory_metadata["new_key"] = "new_value"

    def test_memory_metadata_empty_key_rejected(self):
        with pytest.raises(PersistenceError, match="non-empty keys"):
            PersistedExperienceRecord(**_base_record(memory_metadata={"": "value"}))

    def test_memory_metadata_non_string_value_rejected(self):
        with pytest.raises(PersistenceError, match="string values"):
            PersistedExperienceRecord(**_base_record(memory_metadata={"key": 42}))

    def test_memory_metadata_preserved_through_with_sequence(self):
        record = PersistedExperienceRecord(**_base_record(memory_metadata={"dim": "0.5"}))
        stamped = record.with_sequence(1)
        assert stamped.memory_metadata == MappingProxyType({"dim": "0.5"})

    def test_memory_metadata_preserved_through_with_embedding(self):
        record = PersistedExperienceRecord(**_base_record(memory_metadata={"dim": "0.5"}))
        embedded = record.with_embedding((0.1, 0.2, 0.3))
        assert embedded.memory_metadata == MappingProxyType({"dim": "0.5"})


# ===========================================================================
# Combined layer + memory_metadata
# ===========================================================================

class TestCombinedLayerAndMetadata:
    def test_layer_with_metadata(self):
        record = PersistedExperienceRecord(**_base_record(
            layer="L4_long",
            memory_metadata={"objective_importance": "0.75"},
        ))
        assert record.layer == "L4_long"
        assert record.memory_metadata == MappingProxyType({"objective_importance": "0.75"})

    def test_both_preserved_through_with_sequence(self):
        record = PersistedExperienceRecord(**_base_record(
            layer="L3_short",
            memory_metadata={"recall_count": "5"},
        ))
        stamped = record.with_sequence(10)
        assert stamped.layer == "L3_short"
        assert stamped.memory_metadata == MappingProxyType({"recall_count": "5"})
