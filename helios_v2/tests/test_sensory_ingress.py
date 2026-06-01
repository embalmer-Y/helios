from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.sensory import RawSignal, SensoryIngress, SensoryIngressError


@dataclass
class FakeSensorySource:
    name: str
    signals: tuple[RawSignal, ...]

    @property
    def source_name(self) -> str:
        return self.name

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        return self.signals


def test_duplicate_source_names_are_rejected() -> None:
    ingress = SensoryIngress()
    source = FakeSensorySource(name="cli", signals=())
    ingress.register_source(source)

    with pytest.raises(ValueError, match="Duplicate sensory source: cli"):
        ingress.register_source(source)


def test_collect_stimuli_normalizes_valid_signals_and_preserves_provenance() -> None:
    ingress = SensoryIngress()
    ingress.register_source(
        FakeSensorySource(
            name="cli",
            signals=(
                RawSignal(
                    signal_id="001",
                    source_name="cli",
                    signal_type="text",
                    content="hello",
                    channel="cli",
                    metadata={"user_id": "u1"},
                ),
            ),
        )
    )

    batch = ingress.collect_stimuli()

    assert batch.batch_id.startswith("stimulus-batch:")
    assert len(batch.stimuli) == 1
    stimulus = batch.stimuli[0]
    assert stimulus.stimulus_id == "stimulus:cli:001"
    assert stimulus.provenance_signal_id == "001"
    assert stimulus.metadata["user_id"] == "u1"

    ingest_op = ingress.build_ingest_signal_op(
        RawSignal(
            signal_id="001",
            source_name="cli",
            signal_type="text",
            content="hello",
            channel="cli",
            metadata={"user_id": "u1"},
        )
    )
    assert ingest_op.op_name == "ingest_raw_signal"
    assert ingest_op.owner == "sensory_ingress"
    assert ingest_op.source_name == "cli"
    assert ingest_op.signal_id == "001"

    publish_op = ingress.build_publish_batch_op(batch)
    assert publish_op.op_name == "publish_stimulus_batch"
    assert publish_op.stimulus_count == 1
    assert publish_op.source_names == ("cli",)


def test_invalid_required_signal_fails_explicitly() -> None:
    ingress = SensoryIngress()
    ingress.register_source(
        FakeSensorySource(
            name="body",
            signals=(
                RawSignal(
                    signal_id="hr-01",
                    source_name="body",
                    signal_type="interoceptive",
                    content="   ",
                    required=True,
                ),
            ),
        )
    )

    with pytest.raises(SensoryIngressError, match="Required raw signal 'hr-01'"):
        ingress.collect_stimuli()


def test_optional_empty_signal_is_skipped_without_placeholder_stimulus() -> None:
    ingress = SensoryIngress()
    ingress.register_source(
        FakeSensorySource(
            name="vision",
            signals=(
                RawSignal(
                    signal_id="cam-01",
                    source_name="vision",
                    signal_type="image",
                    content="   ",
                    required=False,
                ),
            ),
        )
    )

    batch = ingress.collect_stimuli()

    assert batch.batch_id.startswith("stimulus-batch:")
    assert batch.stimuli == ()


def test_batch_id_changes_when_batch_content_changes() -> None:
    ingress_a = SensoryIngress()
    ingress_a.register_source(
        FakeSensorySource(
            name="cli",
            signals=(
                RawSignal(
                    signal_id="001",
                    source_name="cli",
                    signal_type="text",
                    content="hello",
                ),
            ),
        )
    )
    ingress_b = SensoryIngress()
    ingress_b.register_source(
        FakeSensorySource(
            name="cli",
            signals=(
                RawSignal(
                    signal_id="001",
                    source_name="cli",
                    signal_type="text",
                    content="different",
                ),
            ),
        )
    )

    batch_a = ingress_a.collect_stimuli()
    batch_b = ingress_b.collect_stimuli()

    assert batch_a.batch_id != batch_b.batch_id