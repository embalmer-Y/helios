"""Owner: rapid salience appraisal.

Owns:
- coarse fast-path salience contracts
- stimulus-batch to appraisal-batch API boundary
- appraisal request and publication ops contracts

Does not own:
- fine semantic interpretation
- memory retrieval
- action selection
"""

from .contracts import (
    AssessStimulusBatchOp,
    PublishRapidAppraisalBatchOp,
    RapidAppraisal,
    RapidAppraisalBatch,
    RapidAppraisalError,
    RapidSalienceAppraisalAPI,
    RapidSalienceVector,
)
from .engine import (
    GroundedDimensionEstimator,
    MemoryGroundedDimensionEstimator,
    MemorySimilaritySource,
    PrototypeSimilaritySource,
    RapidSalienceAppraisalEngine,
    RetrievalAmbiguitySource,
    REWARD_PROTOTYPES,
    SocialContextSource,
    THREAT_PROTOTYPES,
    WeightedAggregateEstimator,
)
from .r80_internal_monologue import InternalMonologueAppraisalEstimator

__all__ = [
    "AssessStimulusBatchOp",
    "GroundedDimensionEstimator",
    "MemoryGroundedDimensionEstimator",
    "MemorySimilaritySource",
    "PrototypeSimilaritySource",
    "PublishRapidAppraisalBatchOp",
    "RapidAppraisal",
    "RapidAppraisalBatch",
    "RapidSalienceAppraisalEngine",
    "RapidAppraisalError",
    "RapidSalienceAppraisalAPI",
    "RapidSalienceVector",
    "RetrievalAmbiguitySource",
    "REWARD_PROTOTYPES",
    "SocialContextSource",
    "THREAT_PROTOTYPES",
    "WeightedAggregateEstimator",
    "InternalMonologueAppraisalEstimator",
]