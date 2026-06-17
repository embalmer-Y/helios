"""R100 T6 tests: Composition bridge projection (MemoryRecord → PersistedExperienceRecord).

Validates:
- ExperienceRecordBridge accepts memory_records parameter and projects layer/metadata via linkage
- MemoryRecordBridge projects layer/metadata from MemoryFormationState.memory_records
- When no MemoryRecord matches, layer=None and memory_metadata=empty
- When MemoryRecord matches, layer and memory_metadata are projected correctly
- Additive: both bridges work unchanged when no memory_records provided
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from helios_v2.experience_writeback import (
    ConsolidationCandidate,
    ContinuityEvidencePacket,
    ExperienceWritebackResult,
)
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.memory import (
    AffectTaggedMemoryItem,
    MemoryContentPacket,
    MemoryFormationState,
    MemoryRecord,
    MemoryReplayCandidate,
)
from helios_v2.persistence import PersistedExperienceRecord
from helios_v2.runtime.stages import (
    ExperienceWritebackStageResult,
    MemoryAffectReplayStageResult,
)
from helios_v2.composition.bridges import (
    ExperienceRecordBridge,
    MemoryRecordBridge,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _feeling_vector() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.5, arousal=0.5, tension=0.5,
        comfort=0.3, fatigue=0.1, pain_like=0.1, social_safety=0.6,
    )


def _content() -> MemoryContentPacket:
    return MemoryContentPacket(
        content_kind="situational-summary",
        summary_ref="summary:test",
        context_ref=None,
        salient_tokens=("test",),
    )


def _make_continuity_packet(**provenance_overrides) -> ContinuityEvidencePacket:
    provenance = {"source_request_id": "req:test", **provenance_overrides}
    return ContinuityEvidencePacket(
        packet_id="packet:test",
        continuity_kind="external_action",
        source_outcome_kind="planner_bridge",
        source_outcome_id="decision:test",
        outcome_class="world_changed",
        summary="a summary",
        requested_effect_summary="a request",
        applied_effect_summary="an effect",
        reason_trace=("reason-a",),
        source_provenance=provenance,
    )


def _make_writeback_result(**provenance_overrides) -> ExperienceWritebackResult:
    packet = _make_continuity_packet(**provenance_overrides)
    candidate = ConsolidationCandidate(
        candidate_id="candidate:test",
        target_memory_family="episodic",
        priority_hint=0.5,
        salience_reason="r100-test",
        continuity_packet=packet,
    )
    return ExperienceWritebackResult(
        result_id="result:test",
        source_request_id="req:test",
        status="written",
        continuity_packet=packet,
        consolidation_candidates=(candidate,),
        tick_id=1,
    )


def _make_writeback_stage_result(**provenance_overrides) -> ExperienceWritebackStageResult:
    result = _make_writeback_result(**provenance_overrides)
    return ExperienceWritebackStageResult(
        requests=(),
        results=(result,),
        publish_writeback_ops=(),
        publish_candidate_ops=(),
    )


def _make_memory_record(memory_id: str, layer: str = "L3_short", metadata: dict | None = None) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        layer=layer,
        affect_intensity_at_write=0.35,
        outcome_class_at_write="no_outcome",
        source_feeling_state_id="fs:test",
        family="episodic",
        content=_content(),
        binding_context_id=None,
        tick_id=1,
        created_at_wall=1000.0,
        memory_metadata=metadata or {},
    )


def _make_memory_item(memory_id: str = "m:1") -> AffectTaggedMemoryItem:
    return AffectTaggedMemoryItem(
        memory_id=memory_id,
        family="episodic",
        source_feeling_state_id="fs:test",
        affect_tag=_feeling_vector(),
        content=_content(),
        binding_context_id=None,
        tick_id=1,
    )


def _make_candidate(memory_id: str = "m:1") -> MemoryReplayCandidate:
    return MemoryReplayCandidate(
        candidate_id="candidate:test",
        memory_id=memory_id,
        family="episodic",
        source_feeling_state_id="fs:test",
        replay_reasons=("high_affect_intensity",),
        forced_consolidation=True,
        priority_hint=0.75,
    )


def _make_memory_state(
    items=None,
    candidates=None,
    records=None,
) -> MemoryFormationState:
    items = items or (_make_memory_item(),)
    candidates = candidates or (_make_candidate(),)
    return MemoryFormationState(
        state_id="s:test",
        source_feeling_state_id="fs:test",
        memory_items=items,
        replay_candidates=candidates,
        memory_records=records or (),
        tick_id=1,
    )


def _make_memory_stage_result(state=None) -> MemoryAffectReplayStageResult:
    state = state or _make_memory_state()
    return MemoryAffectReplayStageResult(
        record_op=None,
        state=state,
        publish_replay_candidates_op=None,
        publish_state_op=None,
    )


# ---------------------------------------------------------------------------
# ExperienceRecordBridge tests
# ---------------------------------------------------------------------------

class TestExperienceRecordBridgeLayerProjection:
    """R100: ExperienceRecordBridge projects layer/metadata from memory_records."""

    def test_no_memory_records_layer_none(self):
        """When no memory_records provided, all records get layer=None."""
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result()
        records = bridge.build_records(stage_result, tick_id=1)
        assert len(records) == 1
        assert records[0].layer is None
        assert dict(records[0].memory_metadata) == {}

    def test_matching_memory_record_projects_layer(self):
        """When a MemoryRecord matches via linkage source_memory_id, layer is projected."""
        memory_records = (_make_memory_record("memory:test", layer="L4_long"),)
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result(source_memory_id="memory:test")
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert len(records) == 1
        assert records[0].layer == "L4_long"

    def test_matching_memory_record_projects_metadata(self):
        """When a MemoryRecord matches, memory_metadata is projected."""
        memory_records = (_make_memory_record("memory:test", metadata={"key_a": "value_a"}),)
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result(source_memory_id="memory:test")
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert len(records) == 1
        assert dict(records[0].memory_metadata) == {"key_a": "value_a"}

    def test_no_matching_memory_record_layer_none(self):
        """When linkage has no source_memory_id key, layer=None (honest absence)."""
        memory_records = (_make_memory_record("memory:other"),)
        bridge = ExperienceRecordBridge()
        # No source_memory_id in provenance
        stage_result = _make_writeback_stage_result()
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert len(records) == 1
        assert records[0].layer is None
        assert dict(records[0].memory_metadata) == {}

    def test_mismatching_memory_id_layer_none(self):
        """When source_memory_id doesn't match any MemoryRecord, layer=None."""
        memory_records = (_make_memory_record("memory:other"),)
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result(source_memory_id="memory:different")
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert len(records) == 1
        assert records[0].layer is None

    def test_l5_autobiographical_layer_projection(self):
        """L5_autobiographical layer is projected correctly."""
        memory_records = (_make_memory_record("memory:l5", layer="L5_autobiographical"),)
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result(source_memory_id="memory:l5")
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert records[0].layer == "L5_autobiographical"

    def test_l2_working_layer_projection(self):
        """L2_working layer is projected correctly."""
        memory_records = (_make_memory_record("memory:l2", layer="L2_working"),)
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result(source_memory_id="memory:l2")
        records = bridge.build_records(stage_result, tick_id=1, memory_records=memory_records)
        assert records[0].layer == "L2_working"

    def test_empty_memory_records_default_parameter(self):
        """Default memory_records=() produces layer=None on all records."""
        bridge = ExperienceRecordBridge()
        stage_result = _make_writeback_stage_result()
        records = bridge.build_records(stage_result, tick_id=1)
        # default parameter, no explicit memory_records
        assert records[0].layer is None


# ---------------------------------------------------------------------------
# MemoryRecordBridge tests
# ---------------------------------------------------------------------------

class TestMemoryRecordBridgeLayerProjection:
    """R100: MemoryRecordBridge projects layer/metadata from state.memory_records."""

    def test_no_memory_records_layer_none(self):
        """When state has no memory_records, projected records get layer=None."""
        bridge = MemoryRecordBridge()
        state = _make_memory_state(records=())
        stage_result = _make_memory_stage_result(state=state)
        records = bridge.build_records(stage_result, tick_id=1)
        assert len(records) == 1
        assert records[0].layer is None
        assert dict(records[0].memory_metadata) == {}

    def test_matching_memory_record_projects_layer(self):
        """When a MemoryRecord matches by memory_id, layer is projected."""
        memory_record = _make_memory_record("m:1", layer="L4_long")
        state = _make_memory_state(records=(memory_record,))
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        records = bridge.build_records(stage_result, tick_id=1)
        assert len(records) == 1
        assert records[0].layer == "L4_long"

    def test_matching_memory_record_projects_metadata(self):
        """When a MemoryRecord matches, memory_metadata is projected."""
        memory_record = _make_memory_record("m:1", metadata={"source": "06", "version": "R100"})
        state = _make_memory_state(records=(memory_record,))
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        records = bridge.build_records(stage_result, tick_id=1)
        assert len(records) == 1
        assert dict(records[0].memory_metadata) == {"source": "06", "version": "R100"}

    def test_non_forced_no_record_projected(self):
        """Non-forced consolidation items don't get projected (bridge filters by forced flag)."""
        non_forced_candidate = MemoryReplayCandidate(
            candidate_id="candidate:non-forced",
            memory_id="m:1",
            family="episodic",
            source_feeling_state_id="fs:test",
            replay_reasons=("high_affect_intensity",),
            forced_consolidation=False,
            priority_hint=0.1,
        )
        memory_record = _make_memory_record("m:1", layer="L3_short")
        state = _make_memory_state(
            candidates=(non_forced_candidate,),
            records=(memory_record,),
        )
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        records = bridge.build_records(stage_result, tick_id=1)
        # No durable records produced (forced_consolidation=False filtered out)
        assert len(records) == 0

    def test_multiple_items_with_records(self):
        """Multiple memory items with corresponding MemoryRecords."""
        items = (_make_memory_item("m:1"), _make_memory_item("m:2"))
        candidates = (_make_candidate("m:1"), _make_candidate("m:2"))
        records = (
            _make_memory_record("m:1", layer="L3_short"),
            _make_memory_record("m:2", layer="L5_autobiographical"),
        )
        state = _make_memory_state(items=items, candidates=candidates, records=records)
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        persisted = bridge.build_records(stage_result, tick_id=1)
        assert len(persisted) == 2
        # Sort by record_id for deterministic assertion
        by_id = {r.record_id: r for r in persisted}
        assert by_id["affect-memory:m:1"].layer == "L3_short"
        assert by_id["affect-memory:m:2"].layer == "L5_autobiographical"

    def test_partial_match_layer_none_for_unmatched(self):
        """When some items have MemoryRecords and some don't, unmatched get layer=None."""
        items = (_make_memory_item("m:1"), _make_memory_item("m:2"))
        candidates = (_make_candidate("m:1"), _make_candidate("m:2"))
        records = (_make_memory_record("m:1", layer="L4_long"),)  # only m:1 has a record
        state = _make_memory_state(items=items, candidates=candidates, records=records)
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        persisted = bridge.build_records(stage_result, tick_id=1)
        assert len(persisted) == 2
        by_id = {r.record_id: r for r in persisted}
        assert by_id["affect-memory:m:1"].layer == "L4_long"
        assert by_id["affect-memory:m:2"].layer is None
        assert dict(by_id["affect-memory:m:2"].memory_metadata) == {}

    def test_all_four_layers_projected(self):
        """All four MemoryLayer values can be projected."""
        for layer_name in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
            memory_id = f"m:{layer_name}"
            memory_record = _make_memory_record(memory_id, layer=layer_name)
            item = _make_memory_item(memory_id)
            candidate = _make_candidate(memory_id)
            state = _make_memory_state(items=(item,), candidates=(candidate,), records=(memory_record,))
            stage_result = _make_memory_stage_result(state=state)
            bridge = MemoryRecordBridge()
            persisted = bridge.build_records(stage_result, tick_id=1)
            assert persisted[0].layer == layer_name

    def test_metadata_with_affect_vector_not_overwritten(self):
        """The bridge's own metadata (memory_family, affect_vector) is preserved alongside memory_metadata."""
        memory_record = _make_memory_record("m:1", metadata={"classifier_version": "R100"})
        state = _make_memory_state(records=(memory_record,))
        stage_result = _make_memory_stage_result(state=state)
        bridge = MemoryRecordBridge()
        persisted = bridge.build_records(stage_result, tick_id=1)
        # The bridge's own metadata should still have memory_family and affect_vector
        assert "memory_family" in dict(persisted[0].metadata)
        assert "affect_vector" in dict(persisted[0].metadata)
        # memory_metadata is a separate field
        assert dict(persisted[0].memory_metadata) == {"classifier_version": "R100"}
