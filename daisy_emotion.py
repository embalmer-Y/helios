"""
Backward-compatibility stub — real implementation moved to cognition/daisy_emotion.py

All public APIs are re-exported here so existing imports continue to work:
    from daisy_emotion import DaisySystemEngine, PANKSEPP_SYSTEMS, ...
"""
# Re-export everything from the new location
from cognition.daisy_emotion import *  # noqa: F401, F403
from cognition.daisy_emotion import (  # explicit re-exports for type checkers
    DaisySystemEngine,
    AffectState,
    AffectiveChronometer,
    OpponentRegulator,
    get_activation_vector,
    get_opponent_state,
    PANKSEPP_SYSTEMS,
    CHRONOMETRY,
    OPPONENT_PAIRS,
    BASELINE,
)
