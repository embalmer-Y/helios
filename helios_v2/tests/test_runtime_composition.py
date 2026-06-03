from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import (
    CANONICAL_STAGE_ORDER,
    CompositionConfig,
    CompositionError,
    FirstVersionDependencyProvider,
    LLM_PROFILES_READY,
    RUNTIME_COGNITION_BASELINE,
    RuntimeHandle,
    assemble_runtime,
    default_composition_config,
    default_critical_dependency_specs,
)
from helios_v2.llm import LlmError, LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder
from helios_v2.runtime import RuntimeDependencySpec, RuntimeStartupError
from helios_v2.runtime.contracts import RuntimeDependencyStatus


@dataclass
class FakeThoughtProvider:
    """Deterministic provider double for composition tests; never touches the network.

    Returns a structured JSON thought envelope (R27): `thought_text` becomes the envelope's
    `thought`; the default envelope is "sufficient + intends_action" so the owner externalizes.
    """

    thought_text: str = "deterministic llm thought for the current cycle"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    continue_reason: str = ""
    intends_action: bool = True
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        self.calls.append(profile.profile_name)
        envelope = {
            "thought": self.thought_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": self.continue_reason,
            "proposed_action": {"intends_action": self.intends_action, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason=self.finish_reason)


@dataclass
class RaisingThoughtProvider:
    """Provider double that always fails, to exercise the no-fallback hard stop."""

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        raise RuntimeError("transport boom")


def _ready_gateway(
    config: CompositionConfig | None = None,
    provider=None,
) -> LlmGateway:
    """Build a network-free gateway whose bound thought profile is statically ready."""

    resolved = config if config is not None else default_composition_config()
    return LlmGateway(
        provider=provider or FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble(**kwargs) -> RuntimeHandle:
    """Assemble a runtime with a network-free fake-provider gateway unless overridden."""

    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway(kwargs.get("config"))
    return assemble_runtime(**kwargs)


@dataclass
class MissingDependencyProvider:
    """Reports the baseline cognition capability as unavailable to exercise fail-fast startup."""

    def get_dependency_status(self, name: str) -> RuntimeDependencyStatus:
        return RuntimeDependencyStatus(name=name, available=False, detail="forced missing")


def test_assemble_runtime_registers_canonical_nineteen_stage_order() -> None:
    handle = _assemble()

    assert isinstance(handle, RuntimeHandle)
    assert len(CANONICAL_STAGE_ORDER) == 19
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_assemble_runtime_single_tick_preserves_canonical_provenance() -> None:
    handle = _assemble()
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
    handle = _assemble()
    handle.startup()

    results = handle.run_ticks(3)

    assert tuple(result.tick_id for result in results) == (1, 2, 3)
    for result in results:
        assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_run_ticks_rejects_non_positive_count() -> None:
    handle = _assemble()
    handle.startup()

    with pytest.raises(ValueError, match="positive integer"):
        handle.run_ticks(0)


def test_startup_fails_fast_when_critical_dependency_missing() -> None:
    handle = _assemble(
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
    handle = _assemble(recorder=recorder)
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
    handle = _assemble()
    handle.startup()

    # No recorder is attached, so the kernel must run without any observability side effect.
    result = handle.tick()
    assert handle.kernel.recorder is None
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_default_composition_config_is_valid_and_overridable() -> None:
    config = default_composition_config()
    assert isinstance(config, CompositionConfig)

    handle = _assemble(config=config)
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_default_critical_dependency_specs_declare_required_baseline() -> None:
    specs = default_critical_dependency_specs()
    assert len(specs) == 1
    assert specs[0].name == RUNTIME_COGNITION_BASELINE
    assert specs[0].required is True


def test_cross_tick_timeline_carry_feeds_evaluation_evidence() -> None:
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    handle = _assemble(recorder=recorder)
    handle.startup()

    results = handle.run_ticks(2)

    first_diag = results[0].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.long_range_diagnostics
    second_diag = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.long_range_diagnostics

    # First instrumented tick has no prior timeline yet; the second consumes tick 1's view.
    assert first_diag["execution_timeline_status"] == "no_prior_timeline"
    assert second_diag["execution_timeline_status"] == "observed"
    assert second_diag["execution_timeline_tick_id"] == 1


def test_uninstrumented_runtime_reports_absent_timeline() -> None:
    handle = _assemble()
    handle.startup()

    result = handle.tick()

    diagnostics = result.stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.long_range_diagnostics
    assert diagnostics["execution_timeline_status"] == "absent_uninstrumented"


def test_write_only_sink_runtime_cannot_carry_timeline() -> None:
    # A recorder with only a write-only stream sink has no readable event source, so the
    # carry stays inactive and evaluation records explicit timeline absence.
    import io

    from helios_v2.observability import JsonLineStreamLogSink

    stream = io.StringIO()
    recorder = RuntimeObservabilityRecorder(
        sinks=(JsonLineStreamLogSink(stream=stream),), minimum_severity="debug"
    )
    handle = _assemble(recorder=recorder)
    handle.startup()

    results = handle.run_ticks(2)

    second_diag = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.long_range_diagnostics
    assert second_diag["execution_timeline_status"] == "absent_uninstrumented"


def test_long_horizon_continuity_state_flows_into_evaluation_evidence() -> None:
    handle = _assemble()
    handle.startup()

    result = handle.tick()

    autonomy_result = result.stage_results["subjective_autonomy_and_proactive_evolution"].result
    # The default runtime externalizes, so no threads form, but the long-horizon state must
    # still be a formal owner-owned contract published on the result.
    assert autonomy_result.long_horizon_state.active_thread_count == 0
    assert autonomy_result.long_horizon_state.dominant_thread_id is None

    # Evaluation must consume the autonomy evidence and report explicit long-horizon status.
    diagnostics = result.stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.long_range_diagnostics
    assert diagnostics["long_horizon_continuity"] in {"no_active_thread", "absent"}


# --- Requirement 26: LLM-backed internal thought default wiring ---


def test_default_runtime_uses_llm_backed_thought_path() -> None:
    provider = FakeThoughtProvider(thought_text="a real model thought")
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    thought_stage = result.stage_results["internal_thought_loop_owner"]
    thought = thought_stage.result.thought
    assert thought is not None
    assert thought.llm_used is True
    assert thought.fallback_used is False
    assert thought.source_path == "llm_backed_v1"
    assert thought.content == "a real model thought"
    assert thought_stage.trace.llm_used is True
    # The bound thought profile was actually invoked through the gateway.
    assert provider.calls == ["thought-default"]


def test_llm_profiles_ready_is_a_registered_critical_dependency() -> None:
    handle = _assemble()
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert LLM_PROFILES_READY in spec_names
    assert RUNTIME_COGNITION_BASELINE in spec_names


def test_startup_fails_fast_when_bound_llm_profile_unready() -> None:
    config = default_composition_config()
    unready_gateway = LlmGateway(
        provider=FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={},  # no api key -> bound profile not statically ready
    )
    handle = assemble_runtime(gateway=unready_gateway, config=config)

    with pytest.raises(RuntimeStartupError) as exc_info:
        handle.startup()
    assert LLM_PROFILES_READY in exc_info.value.missing_dependencies


def test_startup_passes_when_bound_llm_profile_ready() -> None:
    handle = _assemble()
    # Should not raise; the bound thought profile resolves a non-empty api key.
    handle.startup()


def test_llm_inference_failure_is_a_hard_stop_no_fallback() -> None:
    failing_gateway = _ready_gateway(provider=RaisingThoughtProvider())
    handle = assemble_runtime(gateway=failing_gateway)
    handle.startup()

    # Inference failure must surface as a hard stop, never a silent deterministic fallback.
    with pytest.raises(LlmError):
        handle.tick()


# --- Requirement 27: structured-output-driven judgment + deterministic offline assembly ---


def test_deterministic_thought_assembly_runs_offline_without_llm_dependency() -> None:
    # Explicit opt-in offline assembly: deterministic thought path, no LLM critical dependency.
    handle = assemble_runtime(deterministic_thought=True)
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert LLM_PROFILES_READY not in spec_names
    assert RUNTIME_COGNITION_BASELINE in spec_names

    handle.startup()
    result = handle.tick()

    thought = result.stage_results["internal_thought_loop_owner"].result.thought
    assert thought is not None
    assert thought.llm_used is False
    assert thought.source_path == "deterministic_first_version"
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_structured_envelope_drives_owner_decision_in_assembled_runtime() -> None:
    # The structured envelope drives the assembled runtime's thought-owner decision. A
    # "sufficient + intends_action" envelope makes the owner externalize (action proposal
    # present) end to end through the full chain.
    provider = FakeThoughtProvider(
        thought_text="resolved for this cycle",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    thought_result = result.stage_results["internal_thought_loop_owner"].result
    assert thought_result.execution_status == "completed"
    assert thought_result.continuation_requested is False
    assert thought_result.action_proposal is not None


# --- Requirement 28: internal-only tick closure ---


def test_continue_no_action_tick_completes_through_full_chain() -> None:
    # An "insufficient + wants_to_continue + no action" envelope produces no proposal. The
    # full chain (planner, writeback, autonomy, evaluation) must complete the tick as an
    # explicit internal-only outcome rather than crashing (the R27-surfaced boundary).
    provider = FakeThoughtProvider(
        thought_text="still working through this, no action yet",
        sufficiency=0.1,
        wants_to_continue=True,
        continue_reason="unresolved",
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER

    thought_result = result.stage_results["internal_thought_loop_owner"].result
    assert thought_result.continuation_requested is True
    assert thought_result.action_proposal is None

    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "no_actionable_proposal"
    assert planner_result.action_decision is None

    writeback_stage = result.stage_results["execution_writeback_and_autobiographical_consolidation"]
    statuses = {r.status for r in writeback_stage.results}
    assert "written_internal_only" in statuses

    artifact = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact
    assert artifact.gap_summary["consequence_path_outcome"] == "internal_only_decision"


def test_no_action_but_complete_tick_also_closes_internally() -> None:
    # "sufficient + no continue + no action": the cycle concludes without acting. This must
    # also complete through the chain as an internal-only outcome.
    provider = FakeThoughtProvider(
        thought_text="resolved, nothing to do",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    thought_result = result.stage_results["internal_thought_loop_owner"].result
    assert thought_result.continuation_requested is False
    assert thought_result.action_proposal is None

    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "no_actionable_proposal"

    artifact = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact
    assert artifact.gap_summary["consequence_path_outcome"] == "internal_only_decision"


def test_externalizing_tick_still_executes_after_internal_only_support() -> None:
    # Regression guard: the externalizing path is unchanged by the internal-only addition.
    provider = FakeThoughtProvider(
        thought_text="acting now",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "executed"
    assert planner_result.action_decision is not None
    artifact = result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact
    assert artifact.gap_summary["consequence_path_outcome"] == "continuity_written"
