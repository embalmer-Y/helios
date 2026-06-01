"""Owner: sensory ingress.

Owns:
- source-facing raw signal contracts
- normalized stimulus contracts
- ingress API and ops contracts

Does not own:
- salience scoring
- memory retrieval
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable


def _freeze_metadata(metadata: Mapping[str, object] | None) -> Mapping[str, object]:
    frozen = dict(metadata or {})
    return MappingProxyType(frozen)


@dataclass(frozen=True)
class RawSignal:
    """Owner: sensory ingress.

    Purpose:
        Represent one raw source-owned signal before normalization.

    Failure semantics:
        Invalid required fields must be rejected by the ingress owner rather than normalized by fallback.
    """

    signal_id: str
    source_name: str
    signal_type: str
    content: str
    channel: str | None = None
    metadata: Mapping[str, object] | None = None
    required: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class Stimulus:
    """Owner: sensory ingress.

    Purpose:
        Represent one normalized stimulus record published by sensory ingress.

    Failure semantics:
        Stimuli must only be constructed from valid raw signals with explicit provenance.
    """

    stimulus_id: str
    source_name: str
    modality: str
    content: str
    channel: str | None
    metadata: Mapping[str, object] | None
    provenance_signal_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))


@dataclass(frozen=True)
class StimulusBatch:
    """Owner: sensory ingress.

    Purpose:
        Publish one immutable batch of normalized stimuli for a runtime cycle.

    Failure semantics:
        A batch must not hide invalid required source signals.
    """

    batch_id: str
    stimuli: tuple[Stimulus, ...]


@dataclass(frozen=True)
class IngestSignalOp:
    """Owner: sensory ingress.

    Purpose:
        Describe one raw signal submission from a source owner into sensory ingress.

    Inputs:
        Stable op name, ingress owner, source owner, signal identity, and required flag.

    Output:
        A serializable op record for provenance and audit.

    Failure semantics:
        Invalid required source signals must be rejected by the ingress owner.
    """

    op_name: str
    owner: str
    source_name: str
    signal_id: str
    required: bool


@dataclass(frozen=True)
class PublishStimulusBatchOp:
    """Owner: sensory ingress.

    Purpose:
        Describe publication of one normalized stimulus batch to downstream runtime owners.

    Inputs:
        Stable op name, owner, batch identity, stimulus count, and source summary.

    Output:
        A serializable publication record for runtime orchestration and diagnostics.

    Failure semantics:
        Publication must not occur if required signal normalization failed.
    """

    op_name: str
    owner: str
    batch_id: str
    stimulus_count: int
    source_names: tuple[str, ...]


class SensoryIngressError(RuntimeError):
    """Hard-stop error raised when required sensory normalization invariants fail."""


@runtime_checkable
class SensorySource(Protocol):
    """Owner: sensory ingress API.

    Purpose:
        Define the source-owner contract for providing raw signal batches.
    """

    @property
    def source_name(self) -> str:
        """Owner: sensory ingress.

        Purpose:
            Return the stable owner name for this source.

        Inputs:
            None.

        Returns:
            A stable, unique source owner name.

        Raises:
            No direct error contract.

        Notes:
            Duplicate names are rejected at registration time.
        """

        ...

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        """Owner: sensory ingress.

        Purpose:
            Emit the current batch of raw source-owned signals.

        Inputs:
            None.

        Returns:
            An immutable tuple of `RawSignal` values.

        Raises:
            Source-local errors may propagate if emission itself fails.

        Notes:
            Sensory ingress owns validation and normalization, not source-local interpretation.
        """

        ...


@runtime_checkable
class SensoryIngressAPI(Protocol):
    """Owner: sensory ingress API.

    Purpose:
        Define the public owner-facing sensory ingress interface.
    """

    def register_source(self, source: SensorySource) -> None:
        """Owner: sensory ingress.

        Purpose:
            Register one source owner for future collection.

        Inputs:
            A `SensorySource` with a stable unique `source_name`.

        Returns:
            None.

        Raises:
            ValueError if the source name is already registered.

        Notes:
            Registration does not imply downstream interpretation rights.
        """

    def collect_stimuli(self) -> StimulusBatch:
        """Owner: sensory ingress.

        Purpose:
            Collect raw signals from all registered sources and publish one normalized stimulus batch.

        Inputs:
            None.

        Returns:
            A `StimulusBatch` owned by sensory ingress.

        Raises:
            SensoryIngressError when required signals are invalid or normalization fails.

        Notes:
            The returned batch contains no salience, memory, or action semantics.
        """

        ...

    def build_ingest_signal_op(self, raw_signal: RawSignal) -> IngestSignalOp:
        """Owner: sensory ingress.

        Purpose:
            Build the ops contract describing one source-to-owner raw signal ingestion request.

        Inputs:
            One `RawSignal` submitted by a registered or future source owner.

        Returns:
            An `IngestSignalOp` summarizing source submission identity.

        Raises:
            SensoryIngressError if the raw signal lacks required identity fields.

        Notes:
            This op records ingress provenance and request semantics only.
        """

        ...

    def build_publish_batch_op(self, batch: StimulusBatch) -> PublishStimulusBatchOp:
        """Owner: sensory ingress.

        Purpose:
            Build the ops contract describing publication of a normalized batch.

        Inputs:
            A normalized `StimulusBatch` produced by sensory ingress.

        Returns:
            A `PublishStimulusBatchOp` summarizing publication fields.

        Raises:
            SensoryIngressError if the batch cannot be represented safely.

        Notes:
            This op is for provenance and orchestration visibility rather than transport execution.
        """

        ...