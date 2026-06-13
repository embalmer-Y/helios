"""Runtime composition root owner package for Helios v2.

Assembles the existing `01 -> 18` owner chain plus the read-only evaluation owner into a
single runnable runtime handle. Assembly-only: holds no cognitive policy and provides no
degraded or fallback assembly path.
"""

from .dependencies import (
    CHANNEL_DRIVERS_READY,
    CONTINUITY_CHECKPOINT_READY,
    EMBEDDING_PROFILE_READY,
    EXPERIENCE_STORE_READY,
    FirstVersionDependencyProvider,
    LLM_PROFILES_READY,
    ChannelReadinessDependencyProvider,
    ContinuityCheckpointReadinessDependencyProvider,
    EmbeddingReadinessDependencyProvider,
    ExperienceStoreReadinessDependencyProvider,
    LlmReadinessDependencyProvider,
    RUNTIME_COGNITION_BASELINE,
    channel_critical_dependency_spec,
    continuity_checkpoint_critical_dependency_spec,
    default_critical_dependency_specs,
    embedding_profile_critical_dependency_spec,
    experience_store_critical_dependency_spec,
    llm_critical_dependency_spec,
)
from .runtime_assembly import (
    CANONICAL_STAGE_ORDER,
    CHANNEL_BOUND_STAGE_ORDER,
    DEFAULT_PRODUCTION_DATA_DIR,
    CompositionConfig,
    CompositionError,
    RuntimeHandle,
    RuntimeProfile,
    assemble_production_runtime,
    assemble_runtime,
    default_composition_config,
)
from .bridges import SequenceExternalSignalSource

__all__ = [
    "CANONICAL_STAGE_ORDER",
    "CHANNEL_BOUND_STAGE_ORDER",
    "CHANNEL_DRIVERS_READY",
    "ChannelReadinessDependencyProvider",
    "CompositionConfig",
    "CompositionError",
    "CONTINUITY_CHECKPOINT_READY",
    "ContinuityCheckpointReadinessDependencyProvider",
    "DEFAULT_PRODUCTION_DATA_DIR",
    "EMBEDDING_PROFILE_READY",
    "EXPERIENCE_STORE_READY",
    "EmbeddingReadinessDependencyProvider",
    "ExperienceStoreReadinessDependencyProvider",
    "FirstVersionDependencyProvider",
    "LLM_PROFILES_READY",
    "LlmReadinessDependencyProvider",
    "RUNTIME_COGNITION_BASELINE",
    "RuntimeHandle",
    "RuntimeProfile",
    "SequenceExternalSignalSource",
    "assemble_production_runtime",
    "assemble_runtime",
    "channel_critical_dependency_spec",
    "continuity_checkpoint_critical_dependency_spec",
    "default_composition_config",
    "default_critical_dependency_specs",
    "embedding_profile_critical_dependency_spec",
    "experience_store_critical_dependency_spec",
    "llm_critical_dependency_spec",
]
