"""Owner: reportable conscious-content layer.

Owns:
- conscious material and state contracts
- conscious-content owner API boundary
- conscious commitment owner skeleton

Does not own:
- workspace competition
- internal thought execution
- action arbitration
"""

from .contracts import (
    CommitConsciousContentOp,
    ConsciousCommitStatus,
    ConsciousContentAPI,
    ConsciousContentMaterial,
    ConsciousContentMaterialSet,
    ConsciousState,
    ConsciousnessConfig,
    ConsciousnessError,
    ConsciousnessLearnedParameterCategory,
    NoCommitReason,
    PublishConsciousStateOp,
    PublishReportableConsciousContentOp,
    ReportableConsciousContent,
    SupportingContextItem,
)
from .engine import ConsciousnessEngine, FirstVersionConsciousCommitmentPath, IgnitionFocalSelectionPolicy

__all__ = [
    "CommitConsciousContentOp",
    "ConsciousCommitStatus",
    "ConsciousContentAPI",
    "ConsciousContentMaterial",
    "ConsciousContentMaterialSet",
    "ConsciousState",
    "ConsciousnessConfig",
    "ConsciousnessEngine",
    "ConsciousnessError",
    "ConsciousnessLearnedParameterCategory",
    "FirstVersionConsciousCommitmentPath",
    "IgnitionFocalSelectionPolicy",
    "NoCommitReason",
    "PublishConsciousStateOp",
    "PublishReportableConsciousContentOp",
    "ReportableConsciousContent",
    "SupportingContextItem",
]