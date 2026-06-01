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
from .engine import RapidSalienceAppraisalEngine

__all__ = [
    "AssessStimulusBatchOp",
    "PublishRapidAppraisalBatchOp",
    "RapidAppraisal",
    "RapidAppraisalBatch",
    "RapidSalienceAppraisalEngine",
    "RapidAppraisalError",
    "RapidSalienceAppraisalAPI",
    "RapidSalienceVector",
]