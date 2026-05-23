"""Cognition package compatibility surface for Phase 4 restructuring."""

from .appraisal import AppraisalEngine, SECFeatures, appraise_event
from .cognitive_impact import CognitiveImpactProfile
from .drives import Action, ActionSelector, DriveOracle, DriveVector, HeliosSnapshot
from .phi import AdaptiveAlphaICRI, ConsciousnessDetector, ConsciousnessLabel, ConsciousnessMoment, PhiModulator, UnifiedPhi
from .thinking import (
    CounterfactualSimulator,
    DaydreamEngine,
    EmotionalEpisode,
    MemoryReplayEngine,
    SimulatedOutcome,
    SpontaneousThoughtStream,
    ThinkingManager,
    ThoughtFragment,
)
from .thinking_integration import EMOTION_THOUGHT_BIAS, THOUGHT_TYPES, ThinkingEngineIntegration, Thought

__all__ = [
    "AppraisalEngine",
    "SECFeatures",
    "appraise_event",
    "CognitiveImpactProfile",
    "Action",
    "ActionSelector",
    "DriveOracle",
    "DriveVector",
    "HeliosSnapshot",
    "AdaptiveAlphaICRI",
    "ConsciousnessDetector",
    "ConsciousnessLabel",
    "ConsciousnessMoment",
    "PhiModulator",
    "UnifiedPhi",
    "CounterfactualSimulator",
    "DaydreamEngine",
    "EmotionalEpisode",
    "MemoryReplayEngine",
    "SimulatedOutcome",
    "SpontaneousThoughtStream",
    "ThinkingManager",
    "ThoughtFragment",
    "THOUGHT_TYPES",
    "EMOTION_THOUGHT_BIAS",
    "ThinkingEngineIntegration",
    "Thought",
]