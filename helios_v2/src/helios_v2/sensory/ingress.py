"""Owner: sensory ingress.

Owns:
- source registration
- required-signal validation
- raw signal normalization into stimuli

Does not own:
- salience scoring
- memory retrieval
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json

from .contracts import (
    IngestSignalOp,
    PublishStimulusBatchOp,
    RawSignal,
    SensoryIngressAPI,
    SensoryIngressError,
    SensorySource,
    Stimulus,
    StimulusBatch,
)


def _build_batch_id(stimuli: tuple[Stimulus, ...]) -> str:
    canonical_stimuli = []
    for stimulus in stimuli:
        canonical_stimuli.append(
            {
                "stimulus_id": stimulus.stimulus_id,
                "source_name": stimulus.source_name,
                "modality": stimulus.modality,
                "content": stimulus.content,
                "channel": stimulus.channel,
                "metadata": dict(stimulus.metadata or {}),
                "provenance_signal_id": stimulus.provenance_signal_id,
            }
        )
    encoded = json.dumps(
        sorted(canonical_stimuli, key=lambda item: (item["source_name"], item["stimulus_id"])),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"stimulus-batch:{digest}"


def _normalize_signal(raw_signal: RawSignal) -> Stimulus:
    if not raw_signal.signal_id.strip():
        raise SensoryIngressError("Raw signal must declare a non-empty signal_id")
    if not raw_signal.source_name.strip():
        raise SensoryIngressError("Raw signal must declare a non-empty source_name")
    if not raw_signal.signal_type.strip():
        raise SensoryIngressError("Raw signal must declare a non-empty signal_type")
    if raw_signal.required and not raw_signal.content.strip():
        raise SensoryIngressError(
            f"Required raw signal '{raw_signal.signal_id}' from source '{raw_signal.source_name}' has empty content"
        )
    return Stimulus(
        stimulus_id=f"stimulus:{raw_signal.source_name}:{raw_signal.signal_id}",
        source_name=raw_signal.source_name,
        modality=raw_signal.signal_type,
        content=raw_signal.content,
        channel=raw_signal.channel,
        metadata=raw_signal.metadata,
        provenance_signal_id=raw_signal.signal_id,
    )


@dataclass
class SensoryIngress(SensoryIngressAPI):
    """Owner: sensory ingress.

    Purpose:
        Collect raw signals from registered source owners and publish normalized stimulus batches.

    Failure semantics:
        Required signal validation failures raise `SensoryIngressError` and abort batch publication.
    """

    _sources: dict[str, SensorySource] = field(default_factory=dict)

    def register_source(self, source: SensorySource) -> None:
        """Owner: sensory ingress.

        Purpose:
            Register one source owner by stable name.

        Inputs:
            A `SensorySource` whose `source_name` is unique.

        Returns:
            None.

        Raises:
            ValueError if the source name is already registered.

        Notes:
            Registration only affects signal collection, not downstream interpretation.
        """

        source_name = source.source_name
        if source_name in self._sources:
            raise ValueError(f"Duplicate sensory source: {source_name}")
        self._sources[source_name] = source

    def collect_stimuli(self) -> StimulusBatch:
        """Owner: sensory ingress.

        Purpose:
            Collect and normalize one batch of source-owned raw signals.

        Inputs:
            None.

        Returns:
            One immutable `StimulusBatch` with preserved signal provenance.

        Raises:
            SensoryIngressError when required signals are invalid.

        Notes:
            Optional empty signals may be skipped, but required empty signals abort collection.
        """

        normalized: list[Stimulus] = []
        for source in self._sources.values():
            for raw_signal in source.emit_raw_signals():
                self.build_ingest_signal_op(raw_signal)
                if not raw_signal.content.strip() and not raw_signal.required:
                    continue
                normalized.append(_normalize_signal(raw_signal))
        stimuli = tuple(normalized)
        return StimulusBatch(
            batch_id=_build_batch_id(stimuli),
            stimuli=stimuli,
        )

    def build_ingest_signal_op(self, raw_signal: RawSignal) -> IngestSignalOp:
        """Owner: sensory ingress.

        Purpose:
            Build the source-to-owner ingestion op for one raw signal.

        Inputs:
            One `RawSignal` provided by a source owner.

        Returns:
            An `IngestSignalOp` with stable source and signal identity fields.

        Raises:
            SensoryIngressError if the signal lacks required identity fields.

        Notes:
            This method exposes ingress provenance only and performs no downstream interpretation.
        """

        if not raw_signal.source_name.strip():
            raise SensoryIngressError("Raw signal must declare a non-empty source_name")
        if not raw_signal.signal_id.strip():
            raise SensoryIngressError("Raw signal must declare a non-empty signal_id")
        return IngestSignalOp(
            op_name="ingest_raw_signal",
            owner="sensory_ingress",
            source_name=raw_signal.source_name,
            signal_id=raw_signal.signal_id,
            required=raw_signal.required,
        )

    def build_publish_batch_op(self, batch: StimulusBatch) -> PublishStimulusBatchOp:
        """Owner: sensory ingress.

        Purpose:
            Build the publication op for a normalized stimulus batch.

        Inputs:
            A `StimulusBatch` created by `collect_stimuli`.

        Returns:
            A `PublishStimulusBatchOp` summarizing batch identity and source coverage.

        Raises:
            SensoryIngressError if a stimulus has missing provenance fields.

        Notes:
            This method exposes audit and orchestration metadata only.
        """

        source_names = []
        for stimulus in batch.stimuli:
            if not stimulus.source_name or not stimulus.provenance_signal_id:
                raise SensoryIngressError("Stimulus batch contains incomplete provenance")
            source_names.append(stimulus.source_name)
        return PublishStimulusBatchOp(
            op_name="publish_stimulus_batch",
            owner="sensory_ingress",
            batch_id=batch.batch_id,
            stimulus_count=len(batch.stimuli),
            source_names=tuple(sorted(set(source_names))),
        )