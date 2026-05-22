"""
Backward-compatibility stub — real implementation moved to cognition/phi.py

All public APIs are re-exported here so existing imports continue to work:
    from phi import UnifiedPhi, ConsciousnessLabel, AdaptiveAlphaICRI, ...

Note: The consciousness metric has been renamed from Φ (Phi) to ICRI
(Integrated Consciousness Richness Index). The UnifiedPhi class and phi
field names are retained for backward compatibility during the deprecation
period.
"""
# Re-export everything from the new location
from cognition.phi import *  # noqa: F401, F403
from cognition.phi import (  # explicit re-exports for type checkers
    UnifiedPhi,
    ConsciousnessLabel,
    CognitiveImpactProfile,
    AdaptiveAlphaICRI,
)
