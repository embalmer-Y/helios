from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import pytest

from helios_v2.runtime.contracts import RuntimeDependencyStatus, RuntimeFrame
from helios_v2.runtime.dependencies import RuntimeDependencySpec, RuntimeStartupError
from helios_v2.runtime.kernel import RuntimeKernel


@dataclass
class FakeDependencyProvider:
    statuses: dict[str, bool]

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        return RuntimeDependencyStatus(name=name, available=self.statuses.get(name, False))


@dataclass
class FakeStage:
    name: str
    payload: object
    seen_frames: list[RuntimeFrame] = field(default_factory=list)

    @property
    def stage_name(self) -> str:
        return self.name

    def run(self, frame: RuntimeFrame) -> object:
        self.seen_frames.append(frame)
        return self.payload


def test_startup_succeeds_when_all_dependencies_are_available() -> None:
    kernel = RuntimeKernel(
        dependency_specs=[
            RuntimeDependencySpec(name="llm"),
            RuntimeDependencySpec(name="memory"),
        ],
        dependency_provider=FakeDependencyProvider({"llm": True, "memory": True}),
    )

    kernel.startup()


def test_startup_fails_fast_when_critical_dependency_is_missing() -> None:
    kernel = RuntimeKernel(
        dependency_specs=[
            RuntimeDependencySpec(name="llm"),
            RuntimeDependencySpec(name="memory"),
            RuntimeDependencySpec(name="evaluation"),
        ],
        dependency_provider=FakeDependencyProvider({"llm": True, "memory": False, "evaluation": False}),
    )

    with pytest.raises(RuntimeStartupError) as exc_info:
        kernel.startup()

    assert exc_info.value.missing_dependencies == ("memory", "evaluation")


def test_tick_aggregates_stage_results_by_owner_name() -> None:
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=FakeDependencyProvider({}),
    )
    sensory_stage = FakeStage(name="sensory_ingress", payload={"stimuli": 2})
    monitor_stage = FakeStage(name="runtime_monitor", payload={"alive": True})
    kernel.register_stage(sensory_stage)
    kernel.register_stage(monitor_stage)

    result = kernel.tick()

    assert result.tick_id == 1
    assert result.stage_results == {
        "sensory_ingress": {"stimuli": 2},
        "runtime_monitor": {"alive": True},
    }
    assert sensory_stage.seen_frames == [RuntimeFrame(tick_id=1, stage_results={})]
    assert monitor_stage.seen_frames == [
        RuntimeFrame(tick_id=1, stage_results={"sensory_ingress": {"stimuli": 2}})
    ]


def test_tick_passes_immutable_prior_stage_outputs_to_later_stages() -> None:
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=FakeDependencyProvider({}),
    )

    @dataclass
    class MutatingStage:
        name: str

        @property
        def stage_name(self) -> str:
            return self.name

        def run(self, frame: RuntimeFrame) -> Mapping[str, object]:
            with pytest.raises(TypeError):
                frame.stage_results["tamper"] = True
            return {"observed": dict(frame.stage_results)}

    kernel.register_stage(FakeStage(name="sensory_ingress", payload={"stimuli": 2}))
    kernel.register_stage(MutatingStage(name="observer"))

    result = kernel.tick()

    assert result.stage_results["observer"] == {"observed": {"sensory_ingress": {"stimuli": 2}}}


def test_duplicate_stage_names_are_rejected() -> None:
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=FakeDependencyProvider({}),
    )
    kernel.register_stage(FakeStage(name="memory", payload={}))

    with pytest.raises(ValueError, match="Duplicate runtime stage: memory"):
        kernel.register_stage(FakeStage(name="memory", payload={}))