from __future__ import annotations

from dataclasses import dataclass

from .contracts import RuntimeDependencyProvider


@dataclass(frozen=True)
class RuntimeDependencySpec:
    """Declared critical capability required by the runtime startup gate."""

    name: str
    required: bool = True
    description: str = ""


class RuntimeStartupError(RuntimeError):
    """Hard-stop startup error raised when critical dependencies are missing."""

    def __init__(self, missing_dependencies: list[str]):
        self.missing_dependencies = tuple(missing_dependencies)
        names = ", ".join(missing_dependencies)
        super().__init__(f"Missing critical runtime dependencies: {names}")


def validate_critical_dependencies(
    specs: list[RuntimeDependencySpec],
    provider: RuntimeDependencyProvider,
) -> None:
    """Validate declared critical dependencies and raise on any missing capability."""

    missing: list[str] = []
    for spec in specs:
        if not spec.required:
            continue
        status = provider.get_dependency_status(spec.name)
        if not status.available:
            missing.append(spec.name)
    if missing:
        raise RuntimeStartupError(missing)