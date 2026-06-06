"""Owner: workspace competition and working-state layer.

Owns:
- workspace candidate-set contracts
- working-state snapshot contracts
- memory-to-workspace API boundary

Does not own:
- final reportable consciousness commitment
- action arbitration
- identity writeback
"""

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
    WorkspaceLearnedParameterCategory,
    validate_memory_replay_candidates,
)
from .engine import (
    BoundedAttentionRetentionPath,
    SalienceWeightedWorkspaceCompetitionPath,
    WorkingStateRetentionPath,
    WorkspaceCompetitionEngine,
    WorkspaceCompetitionPath,
)

__all__ = [
    "BoundedAttentionRetentionPath",
    "PublishWorkingStateOp",
    "PublishWorkspaceCandidateSetOp",
    "RunWorkspaceCompetitionOp",
    "SalienceWeightedWorkspaceCompetitionPath",
    "WorkingStateRetentionPath",
    "WorkingStateSnapshot",
    "WorkspaceCandidate",
    "WorkspaceCandidateSet",
    "WorkspaceCompetitionAPI",
    "WorkspaceCompetitionConfig",
    "WorkspaceCompetitionEngine",
    "WorkspaceCompetitionError",
    "WorkspaceCompetitionPath",
    "WorkspaceLearnedParameterCategory",
    "validate_memory_replay_candidates",
]