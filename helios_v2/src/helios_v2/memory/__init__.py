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
    MemoryLayer,
    MemoryRecord,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    PublishMemoryFormationStateOp,
    PublishReplayCandidatesOp,
    RecalledMemoryFact,
    RecalledMemoryProvider,
    RecordMemoryOp,
    ReplayReason,
    VALID_MEMORY_LAYERS,
    validate_prediction_mismatch_evidence,
)
from .engine import (
    AffectGroundedMemoryFormationPath,
    AffectOutcomeMemoryLayerClassifier,
    MemoryAffectReplayEngine,
    MemoryFormationPath,
    MemoryLayerClassifier,
    ReplayCandidateSelector,
    SalienceGatedReplayCandidateSelector,
)

__all__ = [
    "AffectGroundedMemoryFormationPath",
    "AffectOutcomeMemoryLayerClassifier",
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
    "MemoryLayer",
    "MemoryLayerClassifier",
    "MemoryRecord",
    "MemoryReplayCandidate",
    "PredictionMismatchEvidence",
    "PublishMemoryFormationStateOp",
    "PublishReplayCandidatesOp",
    "RecalledMemoryFact",
    "RecalledMemoryProvider",
    "RecordMemoryOp",
    "ReplayCandidateSelector",
    "ReplayReason",
    "SalienceGatedReplayCandidateSelector",
    "VALID_MEMORY_LAYERS",
    "validate_prediction_mismatch_evidence",
]