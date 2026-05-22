"""
cognition/ — Helios Cognition Layer

Contains the DAISY emotion engine, ICRI consciousness measurement,
appraisal, emotions, habituation, and agent awareness.
"""

from cognition.daisy_emotion import (
    DaisySystemEngine,
    AffectState,
    AffectiveChronometer,
    OpponentRegulator,
    get_activation_vector,
    get_opponent_state,
    PANKSEPP_SYSTEMS,
    CHRONOMETRY,
    OPPONENT_PAIRS,
)
from cognition.emotions import (
    PankseppEmotionEngine,
)
from cognition.appraisal import (
    SECFeatures,
    AppraisalEngine,
)
from cognition.phi import (
    UnifiedPhi,
    ConsciousnessLabel,
    CognitiveImpactProfile,
    AdaptiveAlphaICRI,
)
from cognition.habituation import HabituationTracker
from cognition.agent_awareness import AgentAwareness

__all__ = [
    # daisy_emotion
    "DaisySystemEngine",
    "AffectState",
    "AffectiveChronometer",
    "OpponentRegulator",
    "get_activation_vector",
    "get_opponent_state",
    "PANKSEPP_SYSTEMS",
    "CHRONOMETRY",
    "OPPONENT_PAIRS",
    # emotions
    "PankseppEmotionEngine",
    # appraisal
    "SECFeatures",
    "AppraisalEngine",
    # phi
    "UnifiedPhi",
    "ConsciousnessLabel",
    "CognitiveImpactProfile",
    "AdaptiveAlphaICRI",
    # habituation
    "HabituationTracker",
    # agent_awareness
    "AgentAwareness",
]
