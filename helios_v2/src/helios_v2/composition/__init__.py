"""Runtime composition root owner package for Helios v2.

Assembles the existing `01 -> 18` owner chain plus the read-only evaluation owner into a
single runnable runtime handle. Assembly-only: holds no cognitive policy and provides no
degraded or fallback assembly path.
"""

from .dependencies import (
    FirstVersionDependencyProvider,
    RUNTIME_COGNITION_BASELINE,
    default_critical_dependency_specs,
)
from .runtime_assembly import (
    CANONICAL_STAGE_ORDER,
    CompositionConfig,
    CompositionError,
    RuntimeHandle,
    assemble_runtime,
    default_composition_config,
)

__all__ = [
    "CANONICAL_STAGE_ORDER",
    "CompositionConfig",
    "CompositionError",
    "FirstVersionDependencyProvider",
    "RUNTIME_COGNITION_BASELINE",
    "RuntimeHandle",
    "assemble_runtime",
    "default_composition_config",
    "default_critical_dependency_specs",
]
