from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.composition import (
    CANONICAL_STAGE_ORDER,
    CompositionConfig,
    CompositionError,
    FirstVersionDependencyProvider,
    RUNTIME_COGNITION_BASELINE,
    RuntimeHandle,
    assemble_runtime,
    default_composition_config,
    default_critical_dependency_specs,
)
from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder
from helios_v2.runtime import RuntimeDependencySpec, RuntimeStartupError
from helios_v2.runtime.contracts import RuntimeDependencyStatus


@dataclass
class MissingDependencyProvider:
    """Reports the baseline cognition capability as unavailable to exercise fail-fast startup."""

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        return RuntimeDependencyStatus(name=name, available=False, detail="forced missing")


def test_assemble_runtime_registers_canonical_nineteen_stage_order() -> None:
    handle = assemble_runtime()

    assert isinstance(handle, RuntimeHandle)
    assert len(CANONICAL_STAGE_ORDER) == 19
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_assemble_runtime_single_tick_preserves_canonical_provenance() -> None:
    handle = assemble_runtime()
    handle.startup()

    result = handle.tick()

    evaluation = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"]
    assert evaluation.artifact.source_bundle_id == "evaluation-bundle:runtime:1"
    assert evaluation.evidence_bundle.bundle_id == "evaluation-bundle:runtime:1"
    assert evaluation.evidence_bundle.source_request_id == "evaluation-request:runtime:1"
    internal_thought = result.stage_results["internal_thought_loop_owner"]
    assert internal_thought.result.result_id.startswith("thought-cycle-result:")
    planner = result.stage_results["planner_executor_feedback_bridge"]
    assert planner.result.result_id.startswith("planner-bridge-result:")


def test_assemble_runtime_run_ticks_advances_tick_id_monotonically() -> None:
    handle = assemble_runtime()
    handle.startup()

    results = handle.run_ticks(3)

    assert tuple(result.tick_id for result in results) == (1, 2, 3)
    for result in results:
        assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_run_ticks_rejects_non_positive_count() -> None:
    handle = assemble_runtime()
    handle.startup()

    with pytest.raises(ValueError, match="positive integer"):
        handle.run_ticks(0)


def test_startup_fails_fast_when_critical_dependency_missing() -> None:
    handle = assemble_runtime(
        dependency_specs=[RuntimeDependencySpec(name=RUNTIME_COGNITION_BASELINE, required=True)],
        dependency_provider=MissingDependencyProvider(),
    )

    with pytest.raises(RuntimeStartupError):
        handle.startup()


def test_default_dependency_provider_reports_baseline_available() -> None:
    provider = FirstVersionDependencyProvider()

    status = provider.get_dependency_status(RUNTIME_COGNITION_BASELINE)
    unknown = provider.get_dependency_status("undeclared_capability")

    assert status.available is True
    assert unknown.available is False


def test_assembled_runtime_with_recorder_reconstructs_per_tick_timeline() -> None:
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    handle = assemble_runtime(recorder=recorder)
    handle.startup()

    handle.tick()

    events = sink.events
    sequences = [event.sequence for event in events]
    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)

    completed_stage_names = [
        event.stage_name for event in events if event.event_kind == "stage_completed"
    ]
    assert tuple(completed_stage_names) == CANONICAL_STAGE_ORDER

    startup_events = [event for event in events if event.event_kind == "runtime_startup"]
    tick_completed_events = [
        event for event in events if event.event_kind == "runtime_tick_completed"
    ]
    assert len(startup_events) == 1
    assert len(tick_completed_events) == 1


def test_assembled_runtime_without_recorder_emits_nothing() -> None:
    handle = assemble_runtime()
    handle.startup()

    # No recorder is attached, so the kernel must run without any observability side effect.
    result = handle.tick()
    assert handle.kernel.recorder is None
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_default_composition_config_is_valid_and_overridable() -> None:
    config = default_composition_config()
    assert isinstance(config, CompositionConfig)

    handle = assemble_runtime(config=config)
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_default_critical_dependency_specs_declare_required_baseline() -> None:
    specs = default_critical_dependency_specs()
    assert len(specs) == 1
    assert specs[0].name == RUNTIME_COGNITION_BASELINE
    assert specs[0].required is True
