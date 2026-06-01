"""Owner: rapid salience appraisal.

Owns:
- coarse early-appraisal contracts
- appraisal API boundary from sensory ingress
- request and publication ops contracts

Does not own:
- fine semantic interpretation
- memory retrieval
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.sensory import Stimulus, StimulusBatch


def _validate_score(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise RapidAppraisalError(f"Salience score '{name}' must be within [0.0, 1.0]")


@dataclass(frozen=True)
class RapidSalienceVector:
    """Owner: rapid salience appraisal.

    Purpose:
        Represent coarse early salience dimensions for one stimulus.

    Failure semantics:
        Scores outside the allowed range raise `RapidAppraisalError`.

    Notes:
        `aggregate` is an owner-produced overall coarse judgment. Early implementations may allow partial contribution from dimension combination, but the contract leaves room for later learned or model-assisted overall appraisal.
    """

    threat: float
    reward: float
    novelty: float
    social: float
    uncertainty: float
    aggregate: float

    def __post_init__(self) -> None:
        _validate_score("threat", self.threat)
        _validate_score("reward", self.reward)
        _validate_score("novelty", self.novelty)
        _validate_score("social", self.social)
        _validate_score("uncertainty", self.uncertainty)
        _validate_score("aggregate", self.aggregate)


@dataclass(frozen=True)
class RapidAppraisal:
    """Owner: rapid salience appraisal.

    Purpose:
        Represent one coarse appraisal result derived from one normalized stimulus.

    Failure semantics:
        Missing provenance or malformed salience data raises `RapidAppraisalError`.
    """

    appraisal_id: str
    stimulus_id: str
    source_name: str
    salience: RapidSalienceVector
    provenance_signal_id: str

    @classmethod
    def from_stimulus(
        cls,
        stimulus: Stimulus,
        salience: RapidSalienceVector,
    ) -> "RapidAppraisal":
        """Owner: rapid salience appraisal.

        Purpose:
            Build one appraisal result from one normalized stimulus.

        Inputs:
            A `Stimulus` from sensory ingress and one `RapidSalienceVector`.

        Returns:
            A `RapidAppraisal` with preserved source and signal provenance.

        Raises:
            RapidAppraisalError if the stimulus lacks provenance fields.

        Notes:
            This constructor preserves upstream provenance and does not add action semantics.
        """

        if not stimulus.stimulus_id or not stimulus.source_name or not stimulus.provenance_signal_id:
            raise RapidAppraisalError("Stimulus must include complete provenance for rapid appraisal")
        return cls(
            appraisal_id=f"rapid-appraisal:{stimulus.stimulus_id}",
            stimulus_id=stimulus.stimulus_id,
            source_name=stimulus.source_name,
            salience=salience,
            provenance_signal_id=stimulus.provenance_signal_id,
        )


@dataclass(frozen=True)
class RapidAppraisalBatch:
    """Owner: rapid salience appraisal.

    Purpose:
        Publish one immutable batch of coarse appraisal results.

    Failure semantics:
        A batch must not contain appraisal records without preserved provenance.
    """

    batch_id: str
    appraisals: tuple[RapidAppraisal, ...]


@dataclass(frozen=True)
class AssessStimulusBatchOp:
    """Owner: rapid salience appraisal.

    Purpose:
        Describe one request to assess a normalized stimulus batch.

    Inputs:
        Stable op name, owner, stimulus batch identity, count, and source summary.

    Output:
        A serializable request record for orchestration and audit.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    stimulus_batch_id: str
    stimulus_count: int
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class PublishRapidAppraisalBatchOp:
    """Owner: rapid salience appraisal.

    Purpose:
        Describe publication of one coarse appraisal batch.

    Inputs:
        Stable op name, owner, appraisal batch identity, count, and source summary.

    Output:
        A serializable publication record for downstream gating layers.

    Failure semantics:
        Publication must not occur if the appraisal batch is malformed.
    """

    op_name: str
    owner: str
    appraisal_batch_id: str
    appraisal_count: int
    source_names: tuple[str, ...]


class RapidAppraisalError(RuntimeError):
    """Hard-stop error raised when rapid salience appraisal contract invariants fail."""


@runtime_checkable
class RapidSalienceAppraisalAPI(Protocol):
    """Owner: rapid salience appraisal API.

    Purpose:
        Define the public owner-facing API from sensory ingress into coarse appraisal.
    """

    def assess_batch(self, batch: StimulusBatch) -> RapidAppraisalBatch:
        """Owner: rapid salience appraisal.

        Purpose:
            Consume one normalized stimulus batch and return one coarse appraisal batch.

        Inputs:
            A `StimulusBatch` emitted by sensory ingress.

        Returns:
            A `RapidAppraisalBatch` owned by rapid salience appraisal.

        Raises:
            RapidAppraisalError when required batch invariants are violated.

        Notes:
            The returned batch contains only coarse early-appraisal semantics.
        """

    def build_assess_batch_op(self, batch: StimulusBatch) -> AssessStimulusBatchOp:
        """Owner: rapid salience appraisal.

        Purpose:
            Build the request op describing one batch assessment.

        Inputs:
            A `StimulusBatch` emitted by sensory ingress.

        Returns:
            An `AssessStimulusBatchOp` summarizing the request.

        Raises:
            RapidAppraisalError if the batch summary cannot be represented safely.

        Notes:
            This op does not execute appraisal by itself.
        """

    def build_publish_batch_op(self, batch: RapidAppraisalBatch) -> PublishRapidAppraisalBatchOp:
        """Owner: rapid salience appraisal.

        Purpose:
            Build the publication op for one coarse appraisal batch.

        Inputs:
            A `RapidAppraisalBatch` produced by this owner.

        Returns:
            A `PublishRapidAppraisalBatchOp` summarizing publication metadata.

        Raises:
            RapidAppraisalError if the appraisal batch is malformed.

        Notes:
            This op is for orchestration visibility and audit rather than transport execution.
        """