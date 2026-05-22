"""
Backward-compatibility stub — real implementation moved to cognition/appraisal.py

All public APIs are re-exported here so existing imports continue to work:
    from appraisal import SECFeatures, AppraisalEngine, ...
"""
# Re-export everything from the new location
from cognition.appraisal import *  # noqa: F401, F403
from cognition.appraisal import (  # explicit re-exports for type checkers
    SECFeatures,
    AppraisalEngine,
)
