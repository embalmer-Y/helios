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
    RecalledMemoryFact,
    RecalledMemoryProvider,
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
    objective_importance,
    promote_layer,
)
from .contracts import (
    MemoryRecord,
    MemoryLayer,
    DoubleConfirmationClass,
    OUTCOME_CLASS_WEIGHTS,
    should_persist,
    effective_priority,
    soft_delete_memory_record,
    migrate_persisted_to_memory_v2,
)
from .classifier import (
    MemoryClassification,
    classify_for_persistence,
    make_memory_record,
)

__all__ = [
    "AffectGroundedMemoryFormationPath",
    "AffectTaggedMemoryItem",
    "MemoryAffectReplayAPI",
    "MemoryAffectReplayConfig",
    "MemoryAffectReplayEngine",
    "MemoryAffectReplayError",
    "MemoryBindingContext",
    "MemoryClassification",
    "MemoryContentPacket",
    "MemoryFamily",
    "MemoryFormationPath",
    "MemoryFormationState",
    "MemoryLearnedParameterCategory",
    "MemoryRecord",
    "MemoryLayer",
    "MemoryReplayCandidate",
    "DoubleConfirmationClass",
    "OUTCOME_CLASS_WEIGHTS",
    "PredictionMismatchEvidence",
    "PublishMemoryFormationStateOp",
    "PublishReplayCandidatesOp",
    "RecalledMemoryFact",
    "RecalledMemoryProvider",
    "RecordMemoryOp",
    "ReplayCandidateSelector",
    "ReplayReason",
    "SalienceGatedReplayCandidateSelector",
    "classify_for_persistence",
    "effective_priority",
    "make_memory_record",
    "migrate_persisted_to_memory_v2",
    "objective_importance",
    "promote_layer",
    "should_persist",
    "soft_delete_memory_record",
    "validate_prediction_mismatch_evidence",
]