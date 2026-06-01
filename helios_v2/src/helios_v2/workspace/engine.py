"""Owner: workspace competition and working-state layer.

Owns:
- workspace competition orchestration
- competition and retention collaborator invocation order
- request and publication op construction

Does not own:
- permanent competition strategy semantics
- final reportable consciousness commitment
- action arbitration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState
from helios_v2.memory import MemoryReplayCandidate

from .contracts import (
    PublishWorkingStateOp,
    PublishWorkspaceCandidateSetOp,
    RunWorkspaceCompetitionOp,
    WorkingStateSnapshot,
    WorkspaceCandidate,
    WorkspaceCandidateSet,
    WorkspaceCompetitionAPI,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionError,
    validate_memory_replay_candidates,
)


def _validate_feeling_state(state: InteroceptiveFeelingState) -> None:
    if not state.state_id:
        raise WorkspaceCompetitionError("InteroceptiveFeelingState must declare a non-empty state_id")
    if not state.source_neuromodulator_state_id:
        raise WorkspaceCompetitionError(
            "InteroceptiveFeelingState must declare a non-empty source_neuromodulator_state_id"
        )


def _validate_workspace_candidates(
    candidates: tuple[WorkspaceCandidate, ...],
    replay_candidates: tuple[MemoryReplayCandidate, ...],
    feeling_state: InteroceptiveFeelingState,
) -> None:
    replay_candidate_map = {candidate.candidate_id: candidate for candidate in replay_candidates}
    forced_replay_ids = {
        candidate.candidate_id for candidate in replay_candidates if candidate.forced_consolidation
    }
    published_workspace_ids = {candidate.source_memory_candidate_id for candidate in candidates}
    if len(published_workspace_ids) != len(candidates):
        raise WorkspaceCompetitionError(
            "Workspace candidate sets must not publish duplicate source_memory_candidate_id values"
        )
    for replay_candidate in replay_candidates:
        if replay_candidate.source_feeling_state_id != feeling_state.state_id:
            raise WorkspaceCompetitionError(
                "Replay candidates must preserve the source feeling state provenance used for workspace competition"
            )
    for candidate in candidates:
        if candidate.source_memory_candidate_id not in replay_candidate_map:
            raise WorkspaceCompetitionError(
                "Workspace candidates must reference replay candidates published in the same competition cycle"
            )
        if candidate.source_feeling_state_id != feeling_state.state_id:
            raise WorkspaceCompetitionError(
                "Workspace candidates must preserve the source feeling state provenance used for competition"
            )
        source_replay_candidate = replay_candidate_map[candidate.source_memory_candidate_id]
        if candidate.source_feeling_state_id != source_replay_candidate.source_feeling_state_id:
            raise WorkspaceCompetitionError(
                "Workspace candidates must preserve the source feeling state provenance of their source replay candidate"
            )
        if candidate.forced_consolidation != source_replay_candidate.forced_consolidation:
            raise WorkspaceCompetitionError(
                "Workspace candidates must preserve the forced_consolidation flag of their source replay candidate"
            )
    if not forced_replay_ids.issubset(published_workspace_ids):
        raise WorkspaceCompetitionError(
            "Forced-consolidation replay candidates must be included in the published workspace candidate set"
        )


def _validate_working_state(
    working_state: WorkingStateSnapshot,
    candidate_set: WorkspaceCandidateSet,
) -> None:
    candidate_ids = {candidate.candidate_id for candidate in candidate_set.candidates}
    for retained_candidate_id in working_state.retained_candidate_ids:
        if retained_candidate_id not in candidate_ids:
            raise WorkspaceCompetitionError(
                "Working state may retain only candidate ids published in the same workspace candidate set"
            )
    if working_state.source_candidate_set_id != candidate_set.set_id:
        raise WorkspaceCompetitionError(
            "Working state must preserve the source_candidate_set_id of the published workspace candidate set"
        )


@runtime_checkable
class WorkspaceCompetitionPath(Protocol):
    """Owner: workspace competition and working-state layer.

    Purpose:
        Produce the next workspace candidate set from validated replay candidates and feeling state.
    """

    def build_candidate_set(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkspaceCandidateSet:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Produce one immutable workspace candidate set.

        Inputs:
            One validated replay-candidate tuple, one validated feeling state, one owner config, and an optional tick id.

        Returns:
            One `WorkspaceCandidateSet` value.

        Raises:
            WorkspaceCompetitionError if required competition capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved competition semantics are not guessed here.
        """


@runtime_checkable
class WorkingStateRetentionPath(Protocol):
    """Owner: workspace competition and working-state layer.

    Purpose:
        Produce the next working-state snapshot from the published workspace candidate set.
    """

    def retain_working_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        config: WorkspaceCompetitionConfig,
        tick_id: int | None,
    ) -> WorkingStateSnapshot:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Produce one immutable working-state snapshot.

        Inputs:
            One `WorkspaceCandidateSet`, one owner config, and an optional tick id.

        Returns:
            One `WorkingStateSnapshot` value.

        Raises:
            WorkspaceCompetitionError if required retention capability is unavailable or unsafe.

        Notes:
            This interface keeps unresolved retention semantics out of the public owner skeleton.
        """


@dataclass
class WorkspaceCompetitionEngine(WorkspaceCompetitionAPI):
    """Owner: workspace competition and working-state layer.

    Purpose:
        Execute workspace competition and working-state publication using injected collaborators.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: WorkspaceCompetitionConfig
    competition_path: WorkspaceCompetitionPath
    retention_path: WorkingStateRetentionPath

    def compete(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        tick_id: int | None = None,
    ) -> tuple[WorkspaceCandidateSet, WorkingStateSnapshot]:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Consume replay candidates plus one feeling-state snapshot and return one workspace candidate set and one working-state snapshot.

        Inputs:
            One replay-candidate tuple, one feeling-state snapshot, and an optional runtime tick id.

        Returns:
            One `WorkspaceCandidateSet` and one `WorkingStateSnapshot`.

        Raises:
            WorkspaceCompetitionError when input invariants or collaborator outputs are invalid.

        Notes:
            Remaining unresolved top-1 consciousness and multi-source competition semantics stay outside this owner skeleton.
        """

        replay_candidates = validate_memory_replay_candidates(replay_candidates)
        _validate_feeling_state(feeling_state)
        candidate_set = self.competition_path.build_candidate_set(
            replay_candidates,
            feeling_state,
            self.config,
            tick_id,
        )
        _validate_workspace_candidates(candidate_set.candidates, replay_candidates, feeling_state)
        working_state = self.retention_path.retain_working_state(candidate_set, self.config, tick_id)
        _validate_working_state(working_state, candidate_set)
        return candidate_set, working_state

    def build_run_competition_op(
        self,
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
    ) -> RunWorkspaceCompetitionOp:
        """Owner: workspace competition and working-state layer.

        Purpose:
            Build the request op describing one workspace competition cycle.

        Inputs:
            One replay-candidate tuple and one feeling-state snapshot.

        Returns:
            A `RunWorkspaceCompetitionOp` summarizing request identity.

        Raises:
            WorkspaceCompetitionError if the request is malformed.

        Notes:
            This method validates replay-candidate and feeling-state provenance before creating the request op.
        """

        replay_candidates = validate_memory_replay_candidates(replay_candidates)
        _validate_feeling_state(feeling_state)
        return RunWorkspaceCompetitionOp(
            op_name="run_workspace_competition",
            owner="workspace_competition_and_working_state",
            candidate_count=len(replay_candidates),
            feeling_state_id=feeling_state.state_id,
        )

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
            Candidate-set publication remains separate from later final reportable commitment ownership.
        """

        if not candidate_set.set_id or not candidate_set.source_feeling_state_id:
            raise WorkspaceCompetitionError("WorkspaceCandidateSet contains incomplete provenance")
        forced_candidate_count = sum(1 for candidate in candidate_set.candidates if candidate.forced_consolidation)
        return PublishWorkspaceCandidateSetOp(
            op_name="publish_workspace_candidate_set",
            owner="workspace_competition_and_working_state",
            set_id=candidate_set.set_id,
            candidate_count=len(candidate_set.candidates),
            forced_candidate_count=forced_candidate_count,
        )

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

        if not working_state.state_id or not working_state.source_candidate_set_id:
            raise WorkspaceCompetitionError("WorkingStateSnapshot contains incomplete provenance")
        return PublishWorkingStateOp(
            op_name="publish_working_state_snapshot",
            owner="workspace_competition_and_working_state",
            state_id=working_state.state_id,
            candidate_set_id=working_state.source_candidate_set_id,
            retained_candidate_count=len(working_state.retained_candidate_ids),
        )