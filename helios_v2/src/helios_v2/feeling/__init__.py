"""Owner: interoceptive feeling layer.

Owns:
- subjective feeling-state contracts
- neuromodulator-to-feeling API boundary
- update and publication ops contracts

Does not own:
- neuromodulator mutation
- memory tagging
- action gating
"""

from .contracts import (
    FeelingLearnedParameterCategory,
    InteroceptiveFeelingAPI,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingError,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
    PublishInteroceptiveFeelingStateOp,
    UpdateInteroceptiveFeelingOp,
    validate_internal_body_signal,
)
from .engine import (
    DominantDimensionReporter,
    FeelingConstructionPath,
    InteroceptiveFeelingEngine,
    InteroceptiveSignalModulatedFeelingConstructionPath,
    NeuromodulatorDerivedFeelingConstructionPath,
    PersistentFeelingConstructionPath,
)

__all__ = [
    "DominantDimensionReporter",
    "FeelingConstructionPath",
    "InteroceptiveSignalModulatedFeelingConstructionPath",
    "NeuromodulatorDerivedFeelingConstructionPath",
    "PersistentFeelingConstructionPath",
    "FeelingLearnedParameterCategory",
    "InteroceptiveFeelingAPI",
    "InteroceptiveFeelingConfig",
    "InteroceptiveFeelingEngine",
    "InteroceptiveFeelingError",
    "InteroceptiveFeelingState",
    "InteroceptiveFeelingVector",
    "PublishInteroceptiveFeelingStateOp",
    "UpdateInteroceptiveFeelingOp",
    "validate_internal_body_signal",
]