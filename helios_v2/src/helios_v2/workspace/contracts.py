"""Owner: workspace competition and working-state layer.

Owns:
- workspace candidate contracts
- working-state snapshot contracts
- competition and publication ops contracts

Does not own:
- memory replay generation
- final reportable consciousness commitment
- action arbitration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState
from helios_v2.memory import MemoryReplayCandidate


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise WorkspaceCompetitionError(f"{name} must be within [0.0, 1.0]")


WorkspaceLearnedParameterCategory = Literal[
    "competition_policy",
    "candidate_retention_policy",
    "working_state_update_policy",
]


@dataclass(frozen=True)
class WorkspaceCompetitionConfig:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Expose the confirmed initialization and learned-policy surface for workspace competition and working state.

    Failure semantics:
        Invalid score ranges, bootstrap identity, or unsupported learned-parameter policy raise `WorkspaceCompetitionError`.
    """

    legal_min_score: float
    legal_max_score: float
    working_state_bootstrap_id: str
    mandatory_learned_parameters: tuple[WorkspaceLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "competition_policy",
            "candidate_retention_policy",
            "working_state_update_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise WorkspaceCompetitionError(
                "Workspace config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("WorkspaceCompetitionConfig.legal_min_score", self.legal_min_score)
        _validate_unit_interval("WorkspaceCompetitionConfig.legal_max_score", self.legal_max_score)
        if self.legal_min_score > self.legal_max_score:
            raise WorkspaceCompetitionError("Workspace config score range is inverted")
        if not self.working_state_bootstrap_id:
            raise WorkspaceCompetitionError(
                "Workspace config must declare a non-empty working_state_bootstrap_id"
            )


@dataclass(frozen=True)
class WorkspaceCandidate:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Represent one immutable workspace-visible candidate derived from a memory replay candidate.

    Failure semantics:
        Missing provenance or out-of-range score hints raise `WorkspaceCompetitionError`.
    """

    candidate_id: str
    source_memory_candidate_id: str
    source_feeling_state_id: str
    priority_hint: float | None
    forced_consolidation: bool
    workspace_score_hint: float | None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise WorkspaceCompetitionError("WorkspaceCandidate must declare a non-empty candidate_id")
        if not self.source_memory_candidate_id:
            raise WorkspaceCompetitionError(
                "WorkspaceCandidate must declare a non-empty source_memory_candidate_id"
            )
        if not self.source_feeling_state_id:
            raise WorkspaceCompetitionError(
                "WorkspaceCandidate must declare a non-empty source_feeling_state_id"
            )
        if self.priority_hint is not None:
            _validate_unit_interval("WorkspaceCandidate.priority_hint", self.priority_hint)
        if self.workspace_score_hint is not None:
            _validate_unit_interval("WorkspaceCandidate.workspace_score_hint", self.workspace_score_hint)


@dataclass(frozen=True)
class WorkspaceCandidateSet:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Represent one immutable workspace candidate set for later consciousness/report layers.

    Failure semantics:
        Missing provenance or malformed candidate references raise `WorkspaceCompetitionError`.
    """

    set_id: str
    source_feeling_state_id: str
    candidates: tuple[WorkspaceCandidate, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.set_id:
            raise WorkspaceCompetitionError("WorkspaceCandidateSet must declare a non-empty set_id")
        if not self.source_feeling_state_id:
            raise WorkspaceCompetitionError(
                "WorkspaceCandidateSet must declare a non-empty source_feeling_state_id"
            )
        for candidate in self.candidates:
            if candidate.source_feeling_state_id != self.source_feeling_state_id:
                raise WorkspaceCompetitionError(
                    "WorkspaceCandidateSet candidates must preserve the published source_feeling_state_id"
                )


@dataclass(frozen=True)
class WorkingStateSnapshot:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Represent one immutable short-lived workspace-owned working-state snapshot.

    Failure semantics:
        Missing provenance or malformed retention identity raise `WorkspaceCompetitionError`.
    """

    state_id: str
    source_candidate_set_id: str
    retained_candidate_ids: tuple[str, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.state_id:
            raise WorkspaceCompetitionError("WorkingStateSnapshot must declare a non-empty state_id")
        if not self.source_candidate_set_id:
            raise WorkspaceCompetitionError(
                "WorkingStateSnapshot must declare a non-empty source_candidate_set_id"
            )
        if any(not candidate_id for candidate_id in self.retained_candidate_ids):
            raise WorkspaceCompetitionError(
                "WorkingStateSnapshot retained_candidate_ids must not contain empty values"
            )


@dataclass(frozen=True)
class RunWorkspaceCompetitionOp:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Describe one request to run workspace competition from memory replay candidates and feeling state.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    candidate_count: int
    feeling_state_id: str


@dataclass(frozen=True)
class PublishWorkingStateOp:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Describe publication of one working-state snapshot.

    Failure semantics:
        Publication must not occur if the working-state snapshot is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    candidate_set_id: str
    retained_candidate_count: int


@dataclass(frozen=True)
class PublishWorkspaceCandidateSetOp:
    """Owner: workspace competition and working-state layer.

    Purpose:
        Describe publication of one workspace candidate set.

    Failure semantics:
        Publication must not occur if the candidate set is malformed.
    """

    op_name: str
    owner: str
    set_id: str
    candidate_count: int
    forced_candidate_count: int


class WorkspaceCompetitionError(RuntimeError):
    """Hard-stop error raised when workspace competition owner invariants fail."""


def validate_memory_replay_candidates(
    candidates: tuple[MemoryReplayCandidate, ...],
) -> tuple[MemoryReplayCandidate, ...]:
    """Validate the required memory-derived candidate inputs used by the workspace owner."""

    if not candidates:
        raise WorkspaceCompetitionError(
            "Workspace competition requires at least one MemoryReplayCandidate input"
        )
    for candidate in candidates:
        if not isinstance(candidate, MemoryReplayCandidate):
            raise WorkspaceCompetitionError(
                "Workspace competition only accepts explicit MemoryReplayCandidate inputs in the first version"
            )
    return candidates


@runtime_checkable
class WorkspaceCompetitionAPI(Protocol):
    """Owner: workspace competition and working-state layer API.

    Purpose:
        Define the public owner-facing API from memory replay candidates plus feeling state into workspace competition and publication.
    """

    def compete(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        tick_id: int | None = None,
    ) -> tuple[WorkspaceCandidateSet, WorkingStateSnapshot]:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Consume one memory-derived candidate tuple plus one feeling-state snapshot and return one workspace candidate set and one working-state snapshot.

        Inputs:
            One tuple of `MemoryReplayCandidate`, one `InteroceptiveFeelingState`, and an optional runtime tick id.

        Returns:
            One `WorkspaceCandidateSet` and one `WorkingStateSnapshot` owned by the workspace layer.

        Raises:
            WorkspaceCompetitionError when required input or workspace invariants are violated.

        Notes:
            The returned outputs do not claim final reportable-consciousness ownership.
        """

        ...

    def build_run_competition_op(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
    ) -> RunWorkspaceCompetitionOp:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Build the request op describing one workspace competition cycle.

        Inputs:
            One tuple of `MemoryReplayCandidate` and one `InteroceptiveFeelingState`.

        Returns:
            A `RunWorkspaceCompetitionOp` summarizing the request.

        Raises:
            WorkspaceCompetitionError if the request cannot be represented safely.

        Notes:
            This op does not execute competition by itself.
        """

        ...

    def build_publish_candidate_set_op(
        self,
        candidate_set: WorkspaceCandidateSet,
    ) -> PublishWorkspaceCandidateSetOp:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Build the publication op for one workspace candidate set.

        Inputs:
            One `WorkspaceCandidateSet` produced by this owner.

        Returns:
            A `PublishWorkspaceCandidateSetOp` summarizing candidate-set publication.

        Raises:
            WorkspaceCompetitionError if the candidate set is malformed.

        Notes:
            This op remains separate from later reportable-consciousness ownership.
        """

        ...

    def build_publish_working_state_op(
        self,
        working_state: WorkingStateSnapshot,
    ) -> PublishWorkingStateOp:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Build the publication op for one working-state snapshot.

        Inputs:
            One `WorkingStateSnapshot` produced by this owner.

        Returns:
            A `PublishWorkingStateOp` summarizing working-state publication.

        Raises:
            WorkspaceCompetitionError if the working-state snapshot is malformed.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        ...