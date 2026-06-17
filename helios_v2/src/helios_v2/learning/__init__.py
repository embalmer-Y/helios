"""Owner: learning framework (R-PROTO-LEARN.Tier1).

Unified learning contract + framework for 5 owner-specific P5 learners.
"""

from helios_v2.learning.contracts import (
    DEFAULT_HORMONE_CHANNELS,
    Learner,
    LearnerConfig,
    Regime,
)
from helios_v2.learning.autonomy_learner import (
    AutonomyLearner,
    AutonomyLearnerConfig,
)
from helios_v2.learning.framework import (
    LearnerABC,
    _compute_closure_adjustment,
    _numpy_pseudo_inverse,
)
from helios_v2.learning.internal_thought_learner import (
    InternalThoughtLearner,
    InternalThoughtLearnerConfig,
)
from helios_v2.learning.memory_learner import (
    MemoryLearner,
    MemoryLearnerConfig,
)
from helios_v2.learning.retrieval_learner import (
    RetrievalLearner,
    RetrievalLearnerConfig,
)
from helios_v2.learning.thought_gating_learner import (
    ThoughtGatingLearner,
    ThoughtGatingLearnerConfig,
)

__all__ = [
    "DEFAULT_HORMONE_CHANNELS",
    "AutonomyLearner",
    "AutonomyLearnerConfig",
    "InternalThoughtLearner",
    "InternalThoughtLearnerConfig",
    "Learner",
    "LearnerABC",
    "LearnerConfig",
    "MemoryLearner",
    "MemoryLearnerConfig",
    "Regime",
    "RetrievalLearner",
    "RetrievalLearnerConfig",
    "ThoughtGatingLearner",
    "ThoughtGatingLearnerConfig",
    "_compute_closure_adjustment",
    "_numpy_pseudo_inverse",
]
