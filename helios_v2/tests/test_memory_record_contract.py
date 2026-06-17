"""R100 T1: MemoryRecord contract + MemoryLayer + MemoryLearnedParameterCategory tests."""

from types import MappingProxyType

import pytest

from helios_v2.memory import (
    MemoryAffectReplayConfig,
    MemoryAffectReplayError,
    MemoryContentPacket,
    MemoryFamily,
    MemoryFormationState,
    MemoryLayer,
    MemoryLearnedParameterCategory,
    MemoryRecord,
    MemoryReplayCandidate,
    ReplayReason,
    VALID_MEMORY_LAYERS,
)


def _content_packet() -> MemoryContentPacket:
    return MemoryContentPacket(
        content_kind="thought_summary",
        summary_ref="operator spoke about grief",
        context_ref=None,
        salient_tokens=("grief", "loss"),
    )


def _valid_record(**overrides) -> MemoryRecord:
    defaults = dict(
        memory_id="memory:r100:1",
        layer="L3_short",
        affect_intensity_at_write=0.35,
        outcome_class_at_write="world_changed",
        source_feeling_state_id="feeling:r100:1",
        family="episodic",
        content=_content_packet(),
        binding_context_id="binding:r100:1",
        tick_id=1,
        created_at_wall=1000.0,
        memory_metadata={},
    )
    defaults.update(overrides)
    return MemoryRecord(**defaults)


# ===========================================================================
# MemoryLayer type + VALID_MEMORY_LAYERS
# ===========================================================================

class TestMemoryLayerType:
    def test_valid_layers_are_the_four_taxonomy(self):
        assert VALID_MEMORY_LAYERS == frozenset({"L2_working", "L3_short", "L4_long", "L5_autobiographical"})

    def test_memory_layer_literal_values(self):
        for layer in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
            assert layer in VALID_MEMORY_LAYERS


# ===========================================================================
# MemoryRecord construction (happy path)
# ===========================================================================

class TestMemoryRecordConstruction:
    def test_valid_construction_all_fields(self):
        record = _valid_record()
        assert record.memory_id == "memory:r100:1"
        assert record.layer == "L3_short"
        assert record.affect_intensity_at_write == 0.35
        assert record.outcome_class_at_write == "world_changed"
        assert record.source_feeling_state_id == "feeling:r100:1"
        assert record.family == "episodic"
        assert record.binding_context_id == "binding:r100:1"
        assert record.tick_id == 1
        assert record.created_at_wall == 1000.0
        assert record.memory_metadata == MappingProxyType({})

    def test_valid_construction_each_layer(self):
        for layer in VALID_MEMORY_LAYERS:
            record = _valid_record(layer=layer)
            assert record.layer == layer

    def test_valid_construction_with_memory_metadata(self):
        record = _valid_record(memory_metadata={"objective_importance_dim": "0.8"})
        assert record.memory_metadata == MappingProxyType({"objective_importance_dim": "0.8"})

    def test_memory_metadata_is_frozen(self):
        record = _valid_record(memory_metadata={"key": "value"})
        with pytest.raises(TypeError):
            record.memory_metadata["new_key"] = "new_value"

    def test_optional_fields_none(self):
        record = _valid_record(binding_context_id=None, tick_id=None, created_at_wall=None)
        assert record.binding_context_id is None
        assert record.tick_id is None
        assert record.created_at_wall is None

    def test_boundary_affect_intensity_zero(self):
        record = _valid_record(affect_intensity_at_write=0.0, layer="L2_working")
        assert record.affect_intensity_at_write == 0.0

    def test_boundary_affect_intensity_one(self):
        record = _valid_record(affect_intensity_at_write=1.0, layer="L5_autobiographical")
        assert record.affect_intensity_at_write == 1.0


# ===========================================================================
# MemoryRecord rejection (failure semantics)
# ===========================================================================

class TestMemoryRecordRejection:
    def test_empty_memory_id_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="non-empty memory_id"):
            _valid_record(memory_id="")

    def test_empty_source_feeling_state_id_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="non-empty source_feeling_state_id"):
            _valid_record(source_feeling_state_id="")

    def test_invalid_layer_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="4-layer taxonomy"):
            _valid_record(layer="L1_sensory")

    def test_invalid_layer_freeform_string_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="4-layer taxonomy"):
            _valid_record(layer="invalid_layer")

    def test_out_of_range_affect_intensity_negative(self):
        with pytest.raises(MemoryAffectReplayError, match="must be within"):
            _valid_record(affect_intensity_at_write=-0.1)

    def test_out_of_range_affect_intensity_above_one(self):
        with pytest.raises(MemoryAffectReplayError, match="must be within"):
            _valid_record(affect_intensity_at_write=1.5)

    def test_empty_outcome_class_at_write_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="non-empty outcome_class_at_write"):
            _valid_record(outcome_class_at_write="")

    def test_memory_metadata_empty_key_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="non-empty keys"):
            _valid_record(memory_metadata={"": "value"})

    def test_memory_metadata_non_string_value_rejected(self):
        with pytest.raises(MemoryAffectReplayError, match="string values"):
            _valid_record(memory_metadata={"key": 42})


# ===========================================================================
# MemoryLearnedParameterCategory extension
# ===========================================================================

class TestMemoryLearnedParameterCategoryExtension:
    def test_layer_assignment_policy_is_valid_category(self):
        """The new 'layer_assignment_policy' value is accepted."""
        config = MemoryAffectReplayConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            storage_bootstrap_state_id="bootstrap",
            mandatory_learned_parameters=(
                "memory_family_write_policy",
                "replay_priority_policy",
                "consolidation_policy",
                "layer_assignment_policy",
            ),
        )
        assert "layer_assignment_policy" in config.mandatory_learned_parameters

    def test_legacy_three_categories_still_valid(self):
        """The existing 3-category config must still pass."""
        config = MemoryAffectReplayConfig(
            legal_min_priority=0.0,
            legal_max_priority=1.0,
            storage_bootstrap_state_id="bootstrap",
            mandatory_learned_parameters=(
                "memory_family_write_policy",
                "replay_priority_policy",
                "consolidation_policy",
            ),
        )
        assert len(config.mandatory_learned_parameters) == 3

    def test_invalid_category_set_rejected(self):
        """Neither 3+layer only nor other combos are accepted."""
        with pytest.raises(MemoryAffectReplayError, match="learned-parameter"):
            MemoryAffectReplayConfig(
                legal_min_priority=0.0,
                legal_max_priority=1.0,
                storage_bootstrap_state_id="bootstrap",
                mandatory_learned_parameters=("layer_assignment_policy",),
            )
