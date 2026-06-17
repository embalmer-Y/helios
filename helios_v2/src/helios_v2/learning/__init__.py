"""Owner: learning framework (R-PROTO-LEARN.Tier1+2+3).

Unified learning contract + framework for owner-specific P5 learners.
"""

from helios_v2.learning.contracts import (
    DEFAULT_HORMONE_CHANNELS,
    Learner,
    LearnerConfig,
    Regime,
)
from helios_v2.learning.action_externalization_learner import (
    ActionExternalizationLearner,
    ActionExternalizationLearnerConfig,
)
from helios_v2.learning.autonomy_learner import (
    AutonomyLearner,
    AutonomyLearnerConfig,
)
from helios_v2.learning.evaluation_learner import (
    EvaluationLearner,
    EvaluationLearnerConfig,
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
from helios_v2.learning.outward_expression_externalization_learner import (
    OutwardExpressionExternalizationLearner,
    OutwardExpressionExternalizationLearnerConfig,
)
from helios_v2.learning.outward_expression_learner import (
    OutwardExpressionLearner,
    OutwardExpressionLearnerConfig,
)
from helios_v2.learning.prompt_contract_learner import (
    PromptContractLearner,
    PromptContractLearnerConfig,
)
from helios_v2.learning.retrieval_learner import (
    RetrievalLearner,
    RetrievalLearnerConfig,
)
from helios_v2.learning.thought_gating_learner import (
    ThoughtGatingLearner,
    ThoughtGatingLearnerConfig,
)
from helios_v2.learning.workspace_learner import (
    WorkspaceLearner,
    WorkspaceLearnerConfig,
)

__all__ = [
    "DEFAULT_HORMONE_CHANNELS",
    "ActionExternalizationLearner",
    "ActionExternalizationLearnerConfig",
    "AutonomyLearner",
    "AutonomyLearnerConfig",
    "EvaluationLearner",
    "EvaluationLearnerConfig",
    "InternalThoughtLearner",
    "InternalThoughtLearnerConfig",
    "Learner",
    "LearnerABC",
    "LearnerConfig",
    "MemoryLearner",
    "MemoryLearnerConfig",
    "OutwardExpressionExternalizationLearner",
    "OutwardExpressionExternalizationLearnerConfig",
    "OutwardExpressionLearner",
    "OutwardExpressionLearnerConfig",
    "PromptContractLearner",
    "PromptContractLearnerConfig",
    "Regime",
    "RetrievalLearner",
    "RetrievalLearnerConfig",
    "ThoughtGatingLearner",
    "ThoughtGatingLearnerConfig",
    "WorkspaceLearner",
    "WorkspaceLearnerConfig",
    "_compute_closure_adjustment",
    "_numpy_pseudo_inverse",
]
