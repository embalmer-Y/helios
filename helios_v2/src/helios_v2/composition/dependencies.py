"""Owner: runtime composition root.

First-version critical-dependency declaration and provider for the runnable runtime.

This module ships a minimal, explicit dependency surface so the composition root can
exercise the existing fail-fast startup gate (`runtime.dependencies`). It does not
invent capabilities: it declares the baseline capabilities the first-version runtime
actually relies on and reports availability for exactly those.

Owns:
- the default critical-dependency spec set for the first-version runnable runtime
- a first-version dependency provider that reports availability for declared capabilities

Does not own:
- any cognitive runtime decision or owner state
- the startup gate itself (owned by `runtime.dependencies`)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from helios_v2.runtime import RuntimeDependencySpec
from helios_v2.runtime.contracts import RuntimeDependencyStatus

# Stable capability name for the deterministic first-version cognition chain. The
# baseline runtime depends on this single declared capability being present.
RUNTIME_COGNITION_BASELINE = "runtime_cognition_baseline"


def default_critical_dependency_specs() -> list[RuntimeDependencySpec]:
    """Owner: composition.

    Purpose:
        Return the default critical-dependency spec set for the first-version runtime.

    Inputs:
        None.

    Returns:
        A list with one required spec for the deterministic baseline cognition chain.

    Raises:
        None.

    Notes:
        Later requirements that add real capabilities (LLM, persistent memory, channel
        transport) extend this set; they must not weaken the fail-fast gate.
    """

    return [
        RuntimeDependencySpec(
            name=RUNTIME_COGNITION_BASELINE,
            required=True,
            description="Deterministic first-version cognition chain availability.",
        )
    ]


@dataclass
class FirstVersionDependencyProvider:
    """Owner: composition.

    Purpose:
        Report critical-dependency availability for the first-version runnable runtime.

    Failure semantics:
        Reports unavailable for any capability not in the declared available set, so the
        existing startup gate fails fast on an undeclared or missing critical dependency.
    """

    available_capabilities: frozenset[str] = field(
        default_factory=lambda: frozenset({RUNTIME_COGNITION_BASELINE})
    )

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        """Owner: composition.

        Purpose:
            Return the availability status for one declared critical dependency.

        Inputs:
            `name` - the declared critical-dependency name to check.

        Returns:
            A `RuntimeDependencyStatus` reporting availability for the named capability.

        Raises:
            None.

        Notes:
            Availability is membership in the explicit `available_capabilities` set. An
            unknown name is reported unavailable rather than silently treated as present.
        """

        available = name in self.available_capabilities
        detail = "available" if available else "not declared available in first-version runtime"
        return RuntimeDependencyStatus(name=name, available=available, detail=detail)
