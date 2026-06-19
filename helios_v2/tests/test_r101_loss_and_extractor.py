"""R101 T6: MemoryImportanceLoss protocol + MiningRecord + SqlBackedTrainingDatasetExtractor tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.memory import (
    DoubleConfirmationClass,
    MemoryContentPacket,
    MemoryFamily,
    MemoryImportanceLoss,
    MemoryRecord,
    MiningRecord,
    ObjectiveImportanceVector,
)


def _make_record(layer="L3_short", recall_count=0, utility=None, objective_score=None, dc_class=None) -> MemoryRecord:
    return MemoryRecord(
        memory_id="m1",
        layer=layer,
        affect_intensity_at_write=0.5,
        outcome_class_at_write="executed",
        source_feeling_state_id="f1",
        family="episodic",
        content=MemoryContentPacket(
            content_kind="perceived-stimulus-summary",
            summary_ref="s1",
            context_ref=None,
            salient_tokens=("hello",),
        ),
        binding_context_id="c1",
        tick_id=1,
        created_at_wall=1234567890.0,
        recall_count=recall_count,
        recall_utility_score=utility,
        objective_score=objective_score,
        double_confirmation=dc_class,
    )


# =============================================================================
# MemoryImportanceLoss protocol tests
# =============================================================================


def test_memory_importance_loss_protocol_can_be_implemented() -> None:
    """R101 does NOT provide a first-version loss; verify the protocol is implementable."""
    @dataclass(frozen=True)
    class StubLoss:
        def loss(self, *, predicted_objective_score, observed_recall_utility, recall_count, record):
            if observed_recall_utility is None:
                return 0.0
            return abs(predicted_objective_score - observed_recall_utility)
    # Protocol is structural; instance should satisfy it
    loss = StubLoss()
    rec = _make_record()
    result = loss.loss(
        predicted_objective_score=0.7,
        observed_recall_utility=0.5,
        recall_count=3,
        record=rec,
    )
    assert result == pytest.approx(0.2)


def test_memory_importance_loss_protocol_runtime_checkable() -> None:
    """Protocol is @runtime_checkable; verify isinstance check works."""
    class ImplementsLoss:
        def loss(self, *, predicted_objective_score, observed_recall_utility, recall_count, record):
            return 0.0
    class DoesNotImplementLoss:
        pass
    assert isinstance(ImplementsLoss(), MemoryImportanceLoss)
    assert not isinstance(DoesNotImplementLoss(), MemoryImportanceLoss)


# =============================================================================
# MiningRecord tests
# =============================================================================


def test_mining_record_construction() -> None:
    v = ObjectiveImportanceVector(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    mr = MiningRecord(
        memory_id="m1",
        objective_vector=v,
        objective_score=0.5,
        subjective_score=0.6,
        double_confirmation_class="both_pass",
        recall_count=3,
        recall_utility_score=0.7,
        last_updated_at_wall=1234567890.0,
        layer="L4_long",
        outcome_class="executed",
        tick_id=42,
    )
    assert mr.memory_id == "m1"
    assert mr.objective_score == 0.5
    assert mr.subjective_score == 0.6
    assert mr.double_confirmation_class == "both_pass"
    assert mr.recall_count == 3
    assert mr.recall_utility_score == 0.7
    assert mr.layer == "L4_long"
    assert mr.outcome_class == "executed"
    assert mr.tick_id == 42


def test_mining_record_optional_fields_can_be_none() -> None:
    v = ObjectiveImportanceVector(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    mr = MiningRecord(
        memory_id="m1",
        objective_vector=v,
        objective_score=0.0,
        subjective_score=None,
        double_confirmation_class="skip",
        recall_count=0,
        recall_utility_score=None,
        last_updated_at_wall=None,
        layer="L2_working",
        outcome_class="no_outcome",
        tick_id=None,
    )
    assert mr.subjective_score is None
    assert mr.recall_utility_score is None
    assert mr.last_updated_at_wall is None
    assert mr.tick_id is None


# =============================================================================
# SqlBackedTrainingDatasetExtractor tests
# =============================================================================


@dataclass
class FakeRecord:
    """Minimal stand-in for PersistedExperienceRecord for extractor testing."""
    record_id: str
    layer: str | None
    objective_score: float | None = None
    subjective_score: float | None = None
    double_confirmation_class: str | None = None
    recall_count: int | None = 0
    recall_utility_score: float | None = None
    last_updated_at_wall: float | None = None
    outcome_class: str = "no_outcome"
    tick_id: int | None = None
    objective_importance_json: str | None = None


class FakeStore:
    def __init__(self, records):
        self.records = records

    def read_recent(self, *, limit=None, layer_filter=None):
        out = list(self.records)
        if layer_filter is not None:
            out = [r for r in out if r.layer == layer_filter]
        if limit is not None:
            out = out[:limit]
        return out


def test_extractor_empty_store_returns_empty() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore([]))
    result = extractor.extract_mining_dataset()
    assert result == ()


def test_extractor_filters_by_recall_count() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", objective_score=0.5, recall_count=0),
        FakeRecord("m2", "L3_short", objective_score=0.5, recall_count=3),
        FakeRecord("m3", "L3_short", objective_score=0.5, recall_count=5),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(min_recall_count=3)
    assert len(result) == 2
    assert {r.memory_id for r in result} == {"m2", "m3"}


def test_extractor_filters_by_objective_score() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", objective_score=0.3),
        FakeRecord("m2", "L3_short", objective_score=0.5),
        FakeRecord("m3", "L3_short", objective_score=0.8),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(min_objective_score=0.5)
    assert len(result) == 2
    assert {r.memory_id for r in result} == {"m2", "m3"}


def test_extractor_filters_by_double_confirmation_class() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", objective_score=0.5, double_confirmation_class="both_pass"),
        FakeRecord("m2", "L3_short", objective_score=0.5, double_confirmation_class="skip"),
        FakeRecord("m3", "L3_short", objective_score=0.5, double_confirmation_class="both_pass"),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(double_confirmation_filter=("both_pass",))
    assert len(result) == 2
    assert {r.memory_id for r in result} == {"m1", "m3"}


def test_extractor_filters_by_layer_single() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short"),
        FakeRecord("m2", "L4_long"),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(layer_filter=("L4_long",))
    assert len(result) == 1
    assert result[0].memory_id == "m2"


def test_extractor_filters_by_since_wall_seconds() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", last_updated_at_wall=100.0),
        FakeRecord("m2", "L3_short", last_updated_at_wall=200.0),
        FakeRecord("m3", "L3_short", last_updated_at_wall=300.0),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(since_wall_seconds=200.0)
    assert len(result) == 2
    assert {r.memory_id for r in result} == {"m2", "m3"}


def test_extractor_respects_limit() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord(f"m{i}", "L3_short", objective_score=0.5, recall_count=i) for i in range(10)
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(min_recall_count=0, limit=3)
    assert len(result) == 3


def test_extractor_returns_mining_record_type() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [FakeRecord("m1", "L3_short", objective_score=0.5, recall_count=1)]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset()
    assert isinstance(result[0], MiningRecord)


def test_extractor_skip_class_record_included() -> None:
    """P5 key invariant: skip records are retained as negative training data."""
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L2_working", objective_score=0.2, recall_count=0, double_confirmation_class="skip"),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(double_confirmation_filter=("skip",))
    assert len(result) == 1
    assert result[0].double_confirmation_class == "skip"
    assert result[0].layer == "L2_working"


def test_extractor_handles_missing_json_gracefully() -> None:
    """Records without objective_importance_json get a neutral vector."""
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", objective_score=0.5, objective_importance_json=None),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset()
    assert len(result) == 1
    # Neutral vector used
    assert result[0].objective_vector.stimulus_intensity == 0.5


def test_extractor_skips_malformed_json() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        FakeRecord("m1", "L3_short", objective_score=0.5, objective_importance_json="not valid json"),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset()
    assert len(result) == 0  # Malformed JSON silently skipped (P5 failure-safe)


def test_extractor_combines_all_filters() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    records = [
        # Should match all filters
        FakeRecord("m1", "L4_long", objective_score=0.7, recall_count=3, double_confirmation_class="both_pass", last_updated_at_wall=200.0),
        # Should NOT match (low recall)
        FakeRecord("m2", "L4_long", objective_score=0.7, recall_count=1, double_confirmation_class="both_pass", last_updated_at_wall=200.0),
        # Should NOT match (low score)
        FakeRecord("m3", "L4_long", objective_score=0.3, recall_count=3, double_confirmation_class="both_pass", last_updated_at_wall=200.0),
        # Should NOT match (wrong class)
        FakeRecord("m4", "L4_long", objective_score=0.7, recall_count=3, double_confirmation_class="skip", last_updated_at_wall=200.0),
        # Should NOT match (too old)
        FakeRecord("m5", "L4_long", objective_score=0.7, recall_count=3, double_confirmation_class="both_pass", last_updated_at_wall=50.0),
    ]
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=FakeStore(records))
    result = extractor.extract_mining_dataset(
        min_recall_count=3,
        min_objective_score=0.5,
        layer_filter=("L4_long",),
        double_confirmation_filter=("both_pass",),
        since_wall_seconds=200.0,
    )
    assert len(result) == 1
    assert result[0].memory_id == "m1"


def test_extractor_none_store_returns_empty() -> None:
    from helios_v2.memory import SqlBackedTrainingDatasetExtractor
    extractor = SqlBackedTrainingDatasetExtractor(experience_store=None)
    result = extractor.extract_mining_dataset()
    assert result == ()