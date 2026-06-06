"""Owner: memory affect and replay layer.

Owns:
- affect-linked memory-state contracts
- replay-candidate contracts
- feeling-to-memory API boundary

Does not own:
- conscious workspace promotion
- identity writeback
- action selection
"""

from .contracts import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayAPI,
    MemoryAffectReplayConfig,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFamily,
    MemoryFormationState,
    MemoryLearnedParameterCategory,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    PublishMemoryFormationStateOp,
    PublishReplayCandidatesOp,
    RecordMemoryOp,
    ReplayReason,
    validate_prediction_mismatch_evidence,
)
from .engine import (
    AffectGroundedMemoryFormationPath,
    MemoryAffectReplayEngine,
    MemoryFormationPath,
    ReplayCandidateSelector,
    SalienceGatedReplayCandidateSelector,
)

__all__ = [
    "AffectGroundedMemoryFormationPath",
    "AffectTaggedMemoryItem",
    "MemoryAffectReplayAPI",
    "MemoryAffectReplayConfig",
    "MemoryAffectReplayEngine",
    "MemoryAffectReplayError",
    "MemoryBindingContext",
    "MemoryContentPacket",
    "MemoryFamily",
    "MemoryFormationPath",
    "MemoryFormationState",
    "MemoryLearnedParameterCategory",
    "MemoryReplayCandidate",
    "PredictionMismatchEvidence",
    "PublishMemoryFormationStateOp",
    "PublishReplayCandidatesOp",
    "RecordMemoryOp",
    "ReplayCandidateSelector",
    "ReplayReason",
    "SalienceGatedReplayCandidateSelector",
    "validate_prediction_mismatch_evidence",
]