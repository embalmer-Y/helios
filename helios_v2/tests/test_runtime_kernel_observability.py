from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder
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


@dataclass
class FailingStage:
    name: str

    @property
    def stage_name(self) -> str:
        return self.name

    def run(self, frame: RuntimeFrame) -> object:
        raise ValueError("stage boom")


def _recorder(minimum_severity: str = "debug") -> tuple[RuntimeObservabilityRecorder, InMemoryLogSink]:
    sink = InMemoryLogSink()
    return RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity=minimum_severity), sink


def test_startup_emits_success_event_when_recorder_present():
    recorder, sink = _recorder()
    kernel = RuntimeKernel(
        dependency_specs=[RuntimeDependencySpec(name="llm")],
        dependency_provider=FakeDependencyProvider({"llm": True}),
        recorder=recorder,
    )
    kernel.startup()
    kinds = [event.event_kind for event in sink.events]
    assert kinds == ["runtime_startup"]
    assert sink.events[0].severity == "info"


def test_startup_failure_emits_event_then_raises():
    recorder, sink = _recorder()
    kernel = RuntimeKernel(
        dependency_specs=[RuntimeDependencySpec(name="memory")],
        dependency_provider=FakeDependencyProvider({"memory": False}),
        recorder=recorder,
    )
    with pytest.raises(RuntimeStartupError):
        kernel.startup()
    assert len(sink.events) == 1
    failure = sink.events[0]
    assert failure.event_kind == "runtime_startup_failed"
    assert failure.severity == "critical"
    assert failure.payload["missing_dependencies"] == ["memory"]


def test_tick_emits_ordered_stage_timeline_with_correlation():
    recorder, sink = _recorder()
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=FakeDependencyProvider({}),
        recorder=recorder,
    )
    kernel.register_stage(FakeStage(name="sensory_ingress", payload={"stimuli": 1}))
    kernel.register_stage(FakeStage(name="rapid_salience_appraisal", payload={"salience": 0.5}))

    result = kernel.tick()

    assert result.tick_id == 1
    timeline = [(event.event_kind, event.stage_name) for event in sink.events]
    assert timeline == [
        ("stage_started", "sensory_ingress"),
        ("stage_completed", "sensory_ingress"),
        ("stage_started", "rapid_salience_appraisal"),
        ("stage_completed", "rapid_salience_appraisal"),
        ("runtime_tick_completed", None),
    ]
    # All stage events carry the current tick id.
    assert all(event.tick_id == 1 for event in sink.events)
    # Sequence numbers are strictly monotonic across the whole stream.
    sequences = [event.sequence for event in sink.events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    # Completion events carry a measured duration.
    completions = [event for event in sink.events if event.event_kind == "stage_completed"]
    assert all("duration_ms" in event.payload for event in completions)


def test_tick_emits_stage_failure_event_then_raises():
    recorder, sink = _recorder()
    kernel = RuntimeKernel(
        dependency_specs=[],
        dependency_provider=FakeDependencyProvider({}),
        recorder=recorder,
    )
    kernel.register_stage(FakeStage(name="sensory_ingress", payload={"ok": True}))
    kernel.register_stage(FailingStage(name="rapid_salience_appraisal"))

    with pytest.raises(ValueError, match="stage boom"):
        kernel.tick()

    kinds = [(event.event_kind, event.stage_name) for event in sink.events]
    assert kinds == [
        ("stage_started", "sensory_ingress"),
        ("stage_completed", "sensory_ingress"),
        ("stage_started", "rapid_salience_appraisal"),
        ("stage_failed", "rapid_salience_appraisal"),
    ]
    failure = sink.events[-1]
    assert failure.severity == "error"
    assert failure.payload["error_type"] == "ValueError"


def test_kernel_without_recorder_emits_nothing_and_preserves_behavior():
    kernel = RuntimeKernel(
        dependency_specs=[RuntimeDependencySpec(name="llm")],
        dependency_provider=FakeDependencyProvider({"llm": True}),
    )
    stage = FakeStage(name="sensory_ingress", payload={"stimuli": 2})
    kernel.register_stage(stage)

    kernel.startup()
    result = kernel.tick()

    assert result.tick_id == 1
    assert result.stage_results["sensory_ingress"] == {"stimuli": 2}
    assert len(stage.seen_frames) == 1
