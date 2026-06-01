from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.workspace import (
    WorkingStateSnapshot,
    WorkspaceCandidate,
    WorkspaceCandidateSet,
    WorkspaceCompetitionConfig,
    WorkspaceCompetitionError,
    validate_memory_replay_candidates,
)
from helios_v2.memory import MemoryReplayCandidate


def _build_config() -> WorkspaceCompetitionConfig:
    return WorkspaceCompetitionConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        working_state_bootstrap_id="workspace-bootstrap:v1",
        mandatory_learned_parameters=(
            "competition_policy",
            "candidate_retention_policy",
            "working_state_update_policy",
        ),
    )


def _build_replay_candidate(forced: bool = False) -> MemoryReplayCandidate:
    return MemoryReplayCandidate(
        candidate_id="memory-candidate:001",
        memory_id="memory:001",
        family="episodic",
        source_feeling_state_id="feeling-state:001",
        replay_reasons=("high_affect_intensity",),
        forced_consolidation=forced,
        priority_hint=0.7,
    )


def test_workspace_candidate_is_immutable_and_range_checked() -> None:
    candidate = WorkspaceCandidate(
        candidate_id="workspace-candidate:001",
        source_memory_candidate_id="memory-candidate:001",
        source_feeling_state_id="feeling-state:001",
        priority_hint=0.7,
        forced_consolidation=True,
        workspace_score_hint=0.8,
    )

    with pytest.raises(FrozenInstanceError):
        candidate.workspace_score_hint = 0.1

    with pytest.raises(WorkspaceCompetitionError, match="workspace_score_hint"):
        WorkspaceCandidate(
            candidate_id="workspace-candidate:002",
            source_memory_candidate_id="memory-candidate:001",
            source_feeling_state_id="feeling-state:001",
            priority_hint=0.5,
            forced_consolidation=False,
            workspace_score_hint=1.2,
        )


def test_workspace_candidate_set_preserves_feeling_provenance() -> None:
    candidate_set = WorkspaceCandidateSet(
        set_id="workspace-set:001",
        source_feeling_state_id="feeling-state:001",
        candidates=(
            WorkspaceCandidate(
                candidate_id="workspace-candidate:001",
                source_memory_candidate_id="memory-candidate:001",
                source_feeling_state_id="feeling-state:001",
                priority_hint=0.7,
                forced_consolidation=True,
                workspace_score_hint=0.8,
            ),
        ),
        tick_id=9,
    )

    assert candidate_set.candidates[0].source_feeling_state_id == "feeling-state:001"


def test_working_state_snapshot_requires_non_empty_retained_ids() -> None:
    snapshot = WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=("workspace-candidate:001",),
        tick_id=9,
    )

    assert snapshot.source_candidate_set_id == "workspace-set:001"

    with pytest.raises(WorkspaceCompetitionError, match="must not contain empty values"):
        WorkingStateSnapshot(
            state_id="working-state:002",
            source_candidate_set_id="workspace-set:001",
            retained_candidate_ids=("",),
            tick_id=9,
        )


def test_config_accepts_only_confirmed_learned_parameter_categories() -> None:
    config = _build_config()

    assert config.working_state_bootstrap_id == "workspace-bootstrap:v1"

    with pytest.raises(WorkspaceCompetitionError, match="mandatory learned-parameter categories"):
        WorkspaceCompetitionConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            working_state_bootstrap_id="workspace-bootstrap:v1",
            mandatory_learned_parameters=(
                "competition_policy",
                "candidate_retention_policy",
            ),
        )


def test_validate_memory_replay_candidates_rejects_empty_or_non_contract_inputs() -> None:
    with pytest.raises(WorkspaceCompetitionError, match="requires at least one MemoryReplayCandidate"):
        validate_memory_replay_candidates(())

    class ForeignCandidate:
        candidate_id = "foreign:001"

    with pytest.raises(WorkspaceCompetitionError, match="only accepts explicit MemoryReplayCandidate"):
        validate_memory_replay_candidates((ForeignCandidate(),))  # type: ignore[arg-type]

    validated = validate_memory_replay_candidates((_build_replay_candidate(),))
    assert validated[0].candidate_id == "memory-candidate:001"