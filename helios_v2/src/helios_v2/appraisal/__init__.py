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

# Import order matters here: `appraisal.engine` imports from `appraisal.anchor_catalog`
# (for `DEFAULT_ANCHOR_CATALOG` / `AnchorCatalog`), and `appraisal.anchor_catalog` imports
# from `appraisal.engine` (for the R40 `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES` module
# constants used as the English subset of the default catalog). To break the import cycle,
# `engine` is imported first (its module-level code does not read catalog symbols until
# the `GroundedDimensionEstimator` dataclass is constructed at runtime), then
# `anchor_catalog` is imported (its top-level `_build_default_catalog()` helper runs
# lazily, after `engine` has already bound `THREAT_PROTOTYPES` / `REWARD_PROTOTYPES`).
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
from .anchor_catalog import (
    DEFAULT_ANCHOR_CATALOG,
    ZH_REWARD_ANCHORS,
    ZH_THREAT_ANCHORS,
    AnchorCatalog,
    AnchorSet,
)
from .post_llm_hormone_adjuster import (
    LLM_HORMONE_DELTA_MAX,
    LLM_HORMONE_DELTA_MIN,
    LLM_HORMONE_HIGH_THRESHOLD,
    LLM_HORMONE_LOW_THRESHOLD,
    PostLLMHormoneAdjustment,
    PostLLMHormoneAdjuster,
)

__all__ = [
    "AssessStimulusBatchOp",
    "DEFAULT_ANCHOR_CATALOG",
    "AnchorCatalog",
    "AnchorSet",
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
    "ZH_REWARD_ANCHORS",
    "ZH_THREAT_ANCHORS",
]