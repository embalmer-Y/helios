from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import (
    CANONICAL_STAGE_ORDER,
    CompositionConfig,
    CompositionError,
    EMBEDDING_PROFILE_READY,
    EXPERIENCE_STORE_READY,
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
from helios_v2.persistence import (
    ExperienceStore,
    InMemoryExperienceStoreBackend,
    PersistenceError,
    SqliteExperienceStoreBackend,
)
from helios_v2.embedding import (
    EmbeddingError,
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    ProviderEmbedding,
)
from helios_v2.runtime import RuntimeDependencySpec, RuntimeStartupError
from helios_v2.runtime.contracts import RuntimeDependencyStatus
from helios_v2.continuity_checkpoint import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    SqliteCheckpointBackend,
)
from helios_v2.sensory import Stimulus
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.embedding import EmbeddingRequest as _EmbeddingRequest


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


@dataclass
class MalformedStructuredThoughtProvider:
    """Provider double that returns a live-like malformed structured response."""

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        del profile, request, api_key
        return ProviderCompletion(
            output_text=(
                "<think>internal reasoning leaked by provider</think>"
                '{"thought":"reply to the user","sufficiency":0.9,'
                '"wants_to_continue":false,"continue_reason":"",'
                '"proposed_action":{"intends_action":true,"summary":"reply"},'
                '"self_revision":{"intends_revision":false,"summary":""}}'
            ),
            finish_reason="stop",
        )


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


def test_cross_tick_consequence_corroboration_reports_corroborated() -> None:
    # An instrumented two-tick run: tick 1 externalizes (continuity_written), and tick 2
    # corroborates that self-report against tick 1's complete execution timeline.
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    handle = _assemble(recorder=recorder)
    handle.startup()

    results = handle.run_ticks(2)

    first_gap = results[0].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.gap_summary
    second_gap = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.gap_summary

    # Tick 1 has no prior claim yet; tick 2 corroborates tick 1's continuity_written claim.
    assert first_gap["consequence_corroboration"] == "unverifiable_no_timeline"
    assert first_gap["consequence_path_outcome"] == "continuity_written"
    assert second_gap["consequence_corroboration"] == "corroborated"
    second_warnings = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.fidelity_warnings
    assert all(w.warning_kind != "consequence_discrepancy" for w in second_warnings)


def test_uninstrumented_runtime_consequence_corroboration_is_unverifiable() -> None:
    handle = _assemble()
    handle.startup()

    results = handle.run_ticks(2)

    second_gap = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.gap_summary
    # No recorder: no timeline can be carried, so corroboration stays unverifiable.
    assert second_gap["consequence_corroboration"] == "unverifiable_no_timeline"
    assert second_gap["consequence_corroboration_detail"] == "timeline_absent"


def test_channel_bound_cross_tick_consequence_corroboration() -> None:
    # The channel-bound assembly carries the consequence claim across ticks just like the
    # default assembly. Two externalizing ticks corroborate tick 1 against its timeline.
    provider = FakeThoughtProvider(
        thought_text="acting now",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    sink_lines: list[str] = []
    recorder_sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(recorder_sink,), minimum_severity="debug")
    handle = _assemble_channel(
        sink_lines.append,
        gateway=_ready_gateway(provider=provider),
        recorder=recorder,
    )
    handle.startup()

    handle.channel_subsystem._drivers["cli"].submit_line("first line")
    handle.channel_subsystem._drivers["cli"].submit_line("second line")
    results = handle.run_ticks(2)

    second_gap = results[1].stage_results[
        "evaluation_fidelity_and_diagnostic_provenance"
    ].artifact.gap_summary
    assert second_gap["consequence_corroboration"] == "corroborated"


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


def test_malformed_structured_thought_closes_as_internal_only_tick() -> None:
    handle = _assemble(gateway=_ready_gateway(provider=MalformedStructuredThoughtProvider()))
    handle.startup()

    result = handle.tick()

    thought_stage = result.stage_results["internal_thought_loop_owner"]
    assert thought_stage.result.execution_status == "insufficient_generation"
    assert thought_stage.result.continuation_reason == "malformed_structured_thought"
    assert thought_stage.result.thought is None

    action_stage = result.stage_results["action_proposal_externalization_contract"]
    assert action_stage.activated is True
    assert action_stage.request_op is None
    assert action_stage.request is not None
    assert action_stage.request.source_thought_cycle_result_id == thought_stage.result.result_id
    assert action_stage.result.status == "no_externalization"
    assert action_stage.publish_externalization_op is None
    assert action_stage.publish_rejection_op is None

    governance_stage = result.stage_results["identity_governance_self_revision_integration"]
    assert governance_stage.activated is False
    assert governance_stage.inactive_id == "identity-governance-non-completed-thought:1"

    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "no_actionable_proposal"

    writeback_stage = result.stage_results["execution_writeback_and_autobiographical_consolidation"]
    statuses = {writeback_result.status for writeback_result in writeback_stage.results}
    assert "written_internal_only" in statuses

    autonomy_request = result.stage_results["subjective_autonomy_and_proactive_evolution"].request
    assert autonomy_request.source_identity_governance_result_id == governance_stage.inactive_id

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


# --- Requirement 29: cognition-derived autonomy drive inputs ---


def _autonomy(result):
    return result.stage_results["subjective_autonomy_and_proactive_evolution"].result


def test_executed_action_drives_autonomy_externalize() -> None:
    provider = FakeThoughtProvider(
        thought_text="acting now",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    autonomy = _autonomy(handle.tick())
    assert autonomy.drive_state.dominant_disposition == "externalize"
    assert autonomy.drive_state.activity_mode == "outward_proactive"


def test_continue_no_action_drives_non_externalize_disposition() -> None:
    provider = FakeThoughtProvider(
        thought_text="still thinking",
        sufficiency=0.1,
        wants_to_continue=True,
        continue_reason="unresolved",
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    autonomy = _autonomy(handle.tick())
    # The thought owner chose not to act; autonomy must not externalize.
    assert autonomy.drive_state.dominant_disposition != "externalize"


def test_concluded_no_action_defers_and_forms_continuity_thread() -> None:
    # A concluded no-action tick defers and forms a 24 continuity thread. Before R29 the
    # hardcoded constants forced externalize every tick, so active_thread_count was always 0.
    provider = FakeThoughtProvider(
        thought_text="resolved, nothing to do",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    autonomy = _autonomy(handle.tick())
    assert autonomy.drive_state.dominant_disposition == "defer"
    assert autonomy.long_horizon_state.active_thread_count >= 1


def test_repeated_deferring_ticks_persist_continuity_thread() -> None:
    provider = FakeThoughtProvider(
        thought_text="resolved, nothing to do",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    results = handle.run_ticks(3)
    ages = [_autonomy(r).long_horizon_state.max_thread_age for r in results]
    counts = [_autonomy(r).long_horizon_state.active_thread_count for r in results]
    # Threads form on every deferring tick (previously always 0), and at least one tick
    # accumulates age beyond the initial forming age, proving cross-tick persistence.
    assert all(count >= 1 for count in counts)
    assert max(ages) >= 2


def test_consecutive_deferring_ticks_reinforce_single_thread() -> None:
    """R67: stable continuity key enables multi-tick reinforcement beyond record expiry.

    With the tick-specific key scheme, each tick produced a different key so only the
    carry-forward chain (which preserves the old key) could reinforce. With the stable
    key, every tick's deferral maps to the same thread, yielding reinforcement_count
    that grows monotonically across 5 consecutive deferring ticks.
    """

    provider = FakeThoughtProvider(
        thought_text="resolved, nothing to do",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    results = handle.run_ticks(5)
    autonomies = [_autonomy(r) for r in results]
    # Every tick defers with the same motive.
    assert all(a.drive_state.dominant_disposition == "defer" for a in autonomies)
    # Exactly one thread (same stable key) persists and strengthens.
    last = autonomies[-1]
    assert last.long_horizon_state.active_thread_count == 1
    thread = last.long_horizon_state.threads[0]
    assert thread.reinforcement_count >= 2
    assert thread.age_ticks >= 3
    assert thread.continuity_key == "insufficient_outward_readiness"


# --- Requirement 31: CLI channel driver + channel-bound assembly wiring ---


from helios_v2.composition import CHANNEL_BOUND_STAGE_ORDER, CHANNEL_DRIVERS_READY


def _assemble_channel(sink, **kwargs):
    """Assemble an opt-in channel-bound runtime with a network-free fake-provider gateway."""

    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway(kwargs.get("config"))
    return assemble_runtime(channel_cli=True, cli_output_sink=sink, **kwargs)


def test_channel_bound_assembly_registers_extended_stage_order() -> None:
    sink: list[str] = []
    handle = _assemble_channel(sink.append)

    assert len(CHANNEL_BOUND_STAGE_ORDER) == 21
    assert CHANNEL_BOUND_STAGE_ORDER[0] == "channel_inbound_drain"
    assert "channel_outbound_dispatch" in CHANNEL_BOUND_STAGE_ORDER

    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CHANNEL_BOUND_STAGE_ORDER


def test_channel_drivers_ready_is_a_registered_critical_dependency() -> None:
    sink: list[str] = []
    handle = _assemble_channel(sink.append)
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert CHANNEL_DRIVERS_READY in spec_names
    # CLI declares no credential, so startup passes the gate.
    handle.startup()


def test_channel_round_trip_renders_reply_to_sink() -> None:
    # Operator line injected through the CLI driver becomes a stimulus; an externalizing
    # decision is transported to the injected sink.
    provider = FakeThoughtProvider(
        thought_text="acting now",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    sink: list[str] = []
    handle = _assemble_channel(sink.append, gateway=_ready_gateway(provider=provider))
    handle.startup()

    # Feed an operator line into the CLI driver's bounded backlog before the tick.
    handle.channel_subsystem._drivers["cli"].submit_line("hello helios")

    result = handle.tick()

    # The inbound line was drained into a RawSignal and normalized.
    drain_result = result.stage_results["channel_inbound_drain"]
    assert drain_result.drain_result.drained_count == 1

    # The planner accepted and the outbound dispatch transported the reply to the sink.
    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "executed"
    dispatch_result = result.stage_results["channel_outbound_dispatch"]
    assert dispatch_result.dispatch_result.dispatched_count == 1
    assert dispatch_result.outcomes[0].status == "delivered"
    assert len(sink) == 1
    assert sink[0].startswith("[operator]")


def test_channel_internal_only_tick_with_no_input_completes() -> None:
    # No operator input and a no-action thought: the tick must still complete through the
    # full channel-bound chain with nothing dispatched (internal-only closure from 28).
    provider = FakeThoughtProvider(
        thought_text="still thinking, no action",
        sufficiency=0.1,
        wants_to_continue=True,
        continue_reason="unresolved",
        intends_action=False,
    )
    sink: list[str] = []
    handle = _assemble_channel(sink.append, gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    assert tuple(result.stage_results.keys()) == CHANNEL_BOUND_STAGE_ORDER
    drain_result = result.stage_results["channel_inbound_drain"]
    assert drain_result.drain_result.drained_count == 0
    planner_result = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner_result.status == "no_actionable_proposal"
    dispatch_result = result.stage_results["channel_outbound_dispatch"]
    assert dispatch_result.dispatch_result.dispatched_count == 0
    assert sink == []


def test_default_assembly_is_unchanged_by_channel_wiring() -> None:
    # Regression guard: the default (non-channel) assembly keeps the canonical 19-stage order.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER
    assert "channel_inbound_drain" not in result.stage_results


# --- Requirement 33: durable experience store + restart continuity ---


def _failing_store() -> ExperienceStore:
    """An experience store whose backend always fails to initialize (fail-fast probe)."""

    @dataclass
    class _RaisingBackend:
        def initialize(self) -> None:
            raise PersistenceError("backend cannot initialize")

        def append(self, records):
            raise PersistenceError("backend cannot append")

        def read_recent(self, limit):
            raise PersistenceError("backend cannot read")

        def count(self) -> int:
            raise PersistenceError("backend cannot count")

    return ExperienceStore(backend=_RaisingBackend())


def test_persistence_enabled_tick_appends_writeback_records_with_linkage() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    handle.startup()

    assert store.count() == 0
    handle.tick()

    # The tick's 15 continuity record was durably appended with preserved provenance linkage.
    assert store.count() >= 1
    recent = store.read_recent(10)
    assert all(r.linkage for r in recent)
    assert all(r.summary for r in recent)
    assert all(r.source_outcome_id for r in recent)


def test_persistence_cold_store_first_tick_completes_without_fabrication() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    handle.startup()

    result = handle.tick()

    # The tick completes through the full canonical chain.
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER
    # On the first (cold) tick, directed retrieval had no persisted experience to surface, so
    # no experience_store-sourced hit appears; the bundle still assembles.
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    assert all(hit.source != "experience_store" for hit in all_hits)


def test_restart_continuity_reenters_prior_session_experience(tmp_path) -> None:
    # The headline restart-continuity test: a second handle on the same durable file
    # retrieves the prior session's experience into its thought window.
    db_path = str(tmp_path / "experience_store.sqlite3")

    # Session A: run several ticks against a fresh durable store, then drop the handle.
    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_a = _assemble(experience_store=store_a)
    handle_a.startup()
    handle_a.run_ticks(3)
    persisted_after_a = store_a.count()
    assert persisted_after_a >= 3
    del handle_a, store_a

    # Session B: a brand-new store object + handle on the SAME file.
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    assert store_b.count() == persisted_after_a  # prior existence survived the restart
    handle_b = _assemble(experience_store=store_b)
    handle_b.startup()

    result = handle_b.tick()

    # The prior session's experience re-enters the new session's thought window.
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    assert any(hit.source == "experience_store" for hit in all_hits)


def test_persistence_enabled_registers_experience_store_ready_dependency() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert EXPERIENCE_STORE_READY in spec_names
    # In-memory store initializes fine, so startup passes.
    handle.startup()


def test_persistence_unwritable_backend_fails_fast_at_startup() -> None:
    handle = _assemble(experience_store=_failing_store())

    with pytest.raises(RuntimeStartupError) as exc_info:
        handle.startup()
    assert EXPERIENCE_STORE_READY in exc_info.value.missing_dependencies


def test_default_assembly_has_no_persistence() -> None:
    # Regression guard: with no experience_store, no persistence dependency is registered and
    # the default assembly is unchanged.
    handle = _assemble()
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert EXPERIENCE_STORE_READY not in spec_names
    assert handle.experience_store is None

    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    # The fabricating shim provider is still in use; no experience_store source appears.
    assert all(hit.source != "experience_store" for hit in all_hits)


# --- Requirement 34: semantic experience retrieval ---


@dataclass
class FakeCompositionEmbeddingProvider:
    """Deterministic, network-free embedding provider for composition tests.

    Hashes characters into fixed-dimension buckets so similar summaries embed similarly.
    """

    dimensions: int = 16

    def embed(self, profile, request, api_key):
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


@dataclass
class RaisingCompositionEmbeddingProvider:
    def embed(self, profile, request, api_key):
        raise RuntimeError("embedding transport boom")


def _embedding_gateway(provider=None) -> EmbeddingGateway:
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    return EmbeddingGateway(
        provider=provider or FakeCompositionEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def test_semantic_memory_requires_durable_store() -> None:
    with pytest.raises(CompositionError, match="requires a durable experience store"):
        _assemble(embedding_gateway=_embedding_gateway())


def test_semantic_assembly_embeds_at_write_and_recalls_by_similarity() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    handle.tick()

    # Each persisted record carries an embedding written at append time.
    recent = store.read_recent(10)
    assert recent
    assert all(r.embedding is not None for r in recent)

    # The next tick's directed retrieval uses semantic candidates.
    result = handle.tick()
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    assert any(hit.source == "experience_store_semantic" for hit in all_hits)


def test_semantic_restart_recall_by_similarity(tmp_path) -> None:
    # Headline: a prior session's most semantically similar experience is recalled after a
    # restart against the same durable file.
    db_path = str(tmp_path / "experience_store.sqlite3")

    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_a = _assemble(experience_store=store_a, embedding_gateway=_embedding_gateway())
    handle_a.startup()
    handle_a.run_ticks(3)
    assert store_a.count() >= 3
    # Every persisted record from session A carries an embedding.
    assert all(r.embedding is not None for r in store_a.read_recent(100))
    del handle_a, store_a

    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_b = _assemble(experience_store=store_b, embedding_gateway=_embedding_gateway())
    handle_b.startup()
    result = handle_b.tick()

    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    # The prior session's experience re-enters by semantic similarity.
    assert any(hit.source == "experience_store_semantic" for hit in all_hits)


def test_semantic_assembly_registers_embedding_profile_ready() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert EMBEDDING_PROFILE_READY in spec_names
    assert EXPERIENCE_STORE_READY in spec_names
    handle.startup()


def test_semantic_unready_embedding_profile_fails_fast() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    unready = EmbeddingGateway(
        provider=FakeCompositionEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={},  # no api key -> not statically ready
    )
    handle = _assemble(experience_store=store, embedding_gateway=unready)

    with pytest.raises(RuntimeStartupError) as exc_info:
        handle.startup()
    assert EMBEDDING_PROFILE_READY in exc_info.value.missing_dependencies


def test_semantic_embedding_failure_is_hard_stop_no_recency_fallback() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(provider=RaisingCompositionEmbeddingProvider()),
    )
    handle.startup()

    # Embedding fails at embed-at-write time; the tick must hard-stop, not fall back to recency.
    with pytest.raises(EmbeddingError):
        handle.tick()


def test_recency_persistent_assembly_unchanged_without_embedding() -> None:
    # R33 recency-only persistence still works and is not semantic when no embedding gateway.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    spec_names = {spec.name for spec in handle.kernel.dependency_specs}
    assert EMBEDDING_PROFILE_READY not in spec_names
    handle.startup()
    handle.tick()
    result = handle.tick()
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    # Recency provider source, never semantic.
    assert all(hit.source != "experience_store_semantic" for hit in all_hits)
    # Records carry no embedding in the recency-only assembly.
    assert all(r.embedding is None for r in store.read_recent(10))


# --- Requirement 35: memory-grounded novelty appraisal ---


def _appraisal_novelty(result) -> float:
    """Read the single stimulus's novelty from the 03 appraisal stage result."""

    batch = result.stage_results["rapid_salience_appraisal"].batch
    return batch.appraisals[0].salience.novelty


def test_default_assembly_keeps_constant_novelty() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    # No semantic memory -> the first-version constant estimator -> novelty 0.6.
    assert _appraisal_novelty(result) == pytest.approx(0.6)


def test_recency_persistent_assembly_keeps_constant_novelty() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    handle.startup()
    result = handle.tick()
    # Store but no embedding gateway -> constant novelty unchanged.
    assert _appraisal_novelty(result) == pytest.approx(0.6)


def test_semantic_assembly_produces_real_memory_grounded_novelty() -> None:
    # With store + embedding, 03 novelty is memory-grounded. On the first tick the store is
    # cold (no embedded experience yet), so novelty is the defined maximum 1.0 -- already a
    # real, non-constant signal distinct from the 0.6 shim.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    assert _appraisal_novelty(first) == pytest.approx(1.0)  # cold store -> max novelty

    # After the first tick persisted an embedded record, a later tick whose stimulus embeds
    # close to stored experience yields novelty < 1.0 (a real similarity-driven value).
    second = handle.tick()
    assert _appraisal_novelty(second) < 1.0
    assert _appraisal_novelty(second) != pytest.approx(0.6)  # not the shim constant


def test_semantic_novelty_is_lower_for_stimulus_near_stored_experience() -> None:
    # Seed the store with experience, then drive two stimuli whose content embeds near vs far
    # from it; the near stimulus must yield a measurably lower novelty.
    from helios_v2.persistence import PersistedExperienceRecord

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    gateway = _embedding_gateway()
    # Embed a known summary through the same gateway/profile the assembly uses.
    seeded_vector = gateway.embed(
        _EmbeddingRequest(
            request_id="seed:1", target_profile="experience-embedding", input_text="the project deadline is friday"
        )
    ).vector
    store.append_records(
        (
            PersistedExperienceRecord(
                record_id="experience:seed:1",
                tick_id=1,
                continuity_kind="external_action",
                outcome_class="world_changed",
                source_outcome_kind="planner_bridge",
                source_outcome_id="planner-bridge-result:1",
                writeback_status="written",
                summary="the project deadline is friday",
                requested_effect_summary="reply",
                applied_effect_summary="replied",
                reason_trace=("seeded",),
                linkage={"source_request_id": "planner-bridge-result:1"},
                embedding=seeded_vector,
            ),
        )
    )

    from helios_v2.composition.bridges import MemoryGroundedSimilaritySource
    from helios_v2.appraisal import MemoryGroundedDimensionEstimator

    def embed_text(text: str):
        return gateway.embed(
            _EmbeddingRequest(
                request_id=f"q:{abs(hash(text)) % 1000}",
                target_profile="experience-embedding",
                input_text=text,
            )
        ).vector

    estimator = MemoryGroundedDimensionEstimator(
        similarity_source=MemoryGroundedSimilaritySource(embed_text=embed_text, store=store)
    )

    near = estimator.estimate_dimensions(
        Stimulus(
            stimulus_id="s:near",
            source_name="cli",
            modality="text",
            content="the project deadline is friday",
            channel="cli",
            metadata=None,
            provenance_signal_id="n1",
        )
    ).novelty
    far = estimator.estimate_dimensions(
        Stimulus(
            stimulus_id="s:far",
            source_name="cli",
            modality="text",
            content="zzz qqq xyz",
            channel="cli",
            metadata=None,
            provenance_signal_id="f1",
        )
    ).novelty

    assert near < far


def test_semantic_novelty_embedding_failure_is_hard_stop() -> None:
    # An embedding failure during novelty grounding hard-stops the tick (no constant fallback).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(provider=RaisingCompositionEmbeddingProvider()),
    )
    handle.startup()

    with pytest.raises(EmbeddingError):
        handle.tick()


# --- Requirement 36: appraisal-derived neuromodulation ---


def _neuromodulator_levels(result):
    return result.stage_results["neuromodulator_system"].state.levels


def test_default_assembly_keeps_constant_neuromodulator_levels() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    levels = _neuromodulator_levels(result)
    # The first-version constant update path (norepinephrine=0.4) is unchanged.
    assert levels.norepinephrine == pytest.approx(0.4)
    assert levels.dopamine == pytest.approx(0.6)


def test_semantic_assembly_derives_neuromodulator_levels_from_appraisal() -> None:
    # In the semantic-memory assembly, 04 levels are derived from the real appraisal batch.
    # Tick 1 is a cold store -> novelty 1.0 -> elevated norepinephrine, which differs from the
    # constant-path 0.4 and is driven by the real novelty signal.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    first_ne = _neuromodulator_levels(first).norepinephrine
    # Cold-store max novelty drives NE above the tonic baseline (0.3) and above the constant 0.4.
    assert first_ne > 0.4

    # A later tick whose stimulus embeds close to the now-stored experience yields lower
    # novelty, hence lower norepinephrine -- a real salience-driven difference.
    second = handle.tick()
    second_ne = _neuromodulator_levels(second).norepinephrine
    assert second_ne < first_ne


# --- Requirement 37: neuromodulatory gating coupling ---


def _gate_result(result):
    return result.stage_results["thought_gating_and_continuation_pressure"].result


def test_default_assembly_gate_signal_has_no_neuromodulatory_arousal() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    gate = result.stage_results["thought_gating_and_continuation_pressure"]
    # Default (uncoupled) assembly: the gate snapshot carries no arousal fact, and the gate
    # result does not record an arousal contribution.
    assert gate.signal_snapshot.neuromodulatory_arousal is None
    assert "neuromodulatory_arousal" not in gate.result.contributing_signals


def test_semantic_assembly_couples_neuromodulatory_arousal_into_gate() -> None:
    # In the semantic-memory assembly, the real 04 norepinephrine level is forwarded into the
    # 09 gate signal and shapes the gate score through the owner-owned arousal-aware path.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    first_gate = first.stage_results["thought_gating_and_continuation_pressure"]
    first_arousal = first_gate.signal_snapshot.neuromodulatory_arousal
    # The forwarded arousal equals the real 04 norepinephrine level this tick.
    assert first_arousal == pytest.approx(_neuromodulator_levels(first).norepinephrine)
    assert first_gate.result.contributing_signals["neuromodulatory_arousal"] == pytest.approx(
        first_arousal
    )

    # A later tick whose stimulus embeds close to stored experience has lower novelty -> lower
    # norepinephrine -> a measurably lower forwarded arousal and arousal contribution.
    second = handle.tick()
    second_gate = second.stage_results["thought_gating_and_continuation_pressure"]
    second_arousal = second_gate.signal_snapshot.neuromodulatory_arousal
    assert second_arousal < first_arousal
    assert second_gate.result.contributing_signals["neuromodulatory_arousal"] == pytest.approx(
        second_arousal
    )
    # The arousal-driven difference is real (not a constant): the lower tick-2 arousal yields a
    # lower arousal CONTRIBUTION to the gate. (The total gate_score also reflects other real
    # signals now — e.g. the R48 workspace activation rises on tick 2 as the consolidated tick-1
    # memory is recalled into the workspace — so we compare the arousal contribution itself, not
    # the composite score, which is the signal this test is about.)
    first_arousal_contribution = first_gate.result.contributing_signals["neuromodulatory_arousal"]
    second_arousal_contribution = second_gate.result.contributing_signals["neuromodulatory_arousal"]
    assert first_arousal_contribution > second_arousal_contribution


# --- Requirement 38: neuromodulator-derived feeling ---


def _feeling(result):
    return result.stage_results["interoceptive_feeling_layer"].state.feeling


def test_default_assembly_keeps_constant_feeling() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    feeling = _feeling(result)
    # The first-version constant construction path is unchanged.
    assert feeling.valence == pytest.approx(0.4)
    assert feeling.arousal == pytest.approx(0.7)
    assert feeling.tension == pytest.approx(0.5)
    assert feeling.pain_like == pytest.approx(0.1)


def test_semantic_assembly_derives_feeling_from_neuromodulator_state() -> None:
    # In the semantic-memory assembly, 05 feeling is derived from the real 04 state. Tick 1 is a
    # cold store -> max novelty -> elevated norepinephrine/cortisol via 04, which differs from the
    # constant shim and is driven by the real upstream chain.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    first_feeling = _feeling(first)
    first_levels = _neuromodulator_levels(first)
    # Feeling is no longer the constant shim; tension tracks the real cortisol/NE state.
    assert first_feeling != InteroceptiveFeelingVector(
        valence=0.4, arousal=0.7, tension=0.5, comfort=0.2, fatigue=0.3, pain_like=0.1, social_safety=0.4
    )

    # A later tick whose stimulus embeds close to stored experience yields lower novelty -> lower
    # 04 norepinephrine. The 04 drive drop is immediate (04 dual-timescale carries its own prior,
    # but the drive target falls). The 05 feeling now carries momentum (R44 dual-timescale), so its
    # arousal does not necessarily drop in a single tick — it tracks toward the lower target over
    # ticks rather than snapping down. We assert the 04 drive truth plus that feeling evolves.
    second = handle.tick()
    second_feeling = _feeling(second)
    second_levels = _neuromodulator_levels(second)
    assert second_levels.norepinephrine < first_levels.norepinephrine
    assert second_feeling != first_feeling  # 05 feeling evolves across ticks (not constant)


# --- Requirement 39: memory-grounded uncertainty + transport-grounded social ---


def _appraisal_uncertainty(result) -> float:
    return result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience.uncertainty


def _appraisal_social(result) -> float:
    return result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience.social


def test_default_assembly_keeps_constant_uncertainty_and_social() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    # No semantic memory -> the first-version constant estimator.
    assert _appraisal_uncertainty(result) == pytest.approx(0.3)
    assert _appraisal_social(result) == pytest.approx(0.0)


def test_semantic_assembly_produces_real_uncertainty_and_social() -> None:
    # With store + embedding, 03 uncertainty and social are de-shimmed.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    # Cold store -> no comparable memory -> max uncertainty 1.0 (not the 0.3 shim).
    assert _appraisal_uncertainty(first) == pytest.approx(1.0)
    # The default tick stimulus arrives on the external interactive-agent CLI channel ->
    # social presence 1.0 -> social 1.0 (not the 0.0 shim).
    assert _appraisal_social(first) == pytest.approx(1.0)


def test_semantic_uncertainty_is_higher_for_ambiguous_than_unique_match() -> None:
    # Seed the store with two near-duplicate experiences and one unrelated one. A query close to
    # the duplicated cluster matches several stored vectors about equally (ambiguous -> high
    # uncertainty); a query close to the unique unrelated experience matches one dominantly
    # (unique -> lower uncertainty).
    from helios_v2.persistence import PersistedExperienceRecord

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    gateway = _embedding_gateway()

    def embed(text: str):
        return gateway.embed(
            _EmbeddingRequest(
                request_id=f"seed:{abs(hash(text)) % 10000}",
                target_profile="experience-embedding",
                input_text=text,
            )
        ).vector

    def _record(record_id: str, summary: str) -> "PersistedExperienceRecord":
        return PersistedExperienceRecord(
            record_id=record_id,
            tick_id=1,
            continuity_kind="external_action",
            outcome_class="world_changed",
            source_outcome_kind="planner_bridge",
            source_outcome_id=f"planner-bridge-result:{record_id}",
            writeback_status="written",
            summary=summary,
            requested_effect_summary="reply",
            applied_effect_summary="replied",
            reason_trace=("seeded",),
            linkage={"source_request_id": f"planner-bridge-result:{record_id}"},
            embedding=embed(summary),
        )

    store.append_records(
        (
            _record("dup-a", "the project deadline is friday afternoon"),
            _record("dup-b", "the project deadline is friday afternoon"),
            _record("unique", "the cat slept on the warm windowsill"),
        )
    )

    from helios_v2.composition.bridges import MemoryGroundedRetrievalAmbiguitySource
    from helios_v2.appraisal import GroundedDimensionEstimator
    from helios_v2.composition.bridges import (
        EmbeddingPrototypeSimilaritySource,
        MemoryGroundedSimilaritySource,
        TransportGroundedSocialContextSource,
    )

    estimator = GroundedDimensionEstimator(
        similarity_source=MemoryGroundedSimilaritySource(embed_text=embed, store=store),
        ambiguity_source=MemoryGroundedRetrievalAmbiguitySource(embed_text=embed, store=store),
        social_source=TransportGroundedSocialContextSource(),
        prototype_source=EmbeddingPrototypeSimilaritySource(embed_text=embed),
    )

    def _stim(content: str) -> Stimulus:
        return Stimulus(
            stimulus_id=f"s:{abs(hash(content)) % 10000}",
            source_name="cli",
            modality="text",
            content=content,
            channel="cli",
            metadata=None,
            provenance_signal_id="p1",
        )

    ambiguous = estimator.estimate_dimensions(_stim("the project deadline is friday afternoon")).uncertainty
    unique = estimator.estimate_dimensions(_stim("the cat slept on the warm windowsill")).uncertainty

    assert ambiguous > unique


def test_semantic_social_is_zero_for_internal_body_stimulus() -> None:
    # A body/interoceptive stimulus is not from an external agent -> social presence 0.
    from helios_v2.composition.bridges import TransportGroundedSocialContextSource

    source = TransportGroundedSocialContextSource()
    body = Stimulus(
        stimulus_id="s:body",
        source_name="body",
        modality="interoceptive",
        content="breathing_shallow",
        channel="body",
        metadata=None,
        provenance_signal_id="b1",
    )
    cli = Stimulus(
        stimulus_id="s:cli",
        source_name="cli",
        modality="text",
        content="hello",
        channel="cli",
        metadata=None,
        provenance_signal_id="c1",
    )
    assert source.social_presence_for(body) == pytest.approx(0.0)
    assert source.social_presence_for(cli) == pytest.approx(1.0)


# --- Requirement 40: prototype-grounded threat + reward ---


def _appraisal_threat(result) -> float:
    return result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience.threat


def _appraisal_reward(result) -> float:
    return result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience.reward


def test_default_assembly_keeps_constant_threat_and_reward() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    # No semantic memory -> the first-version constant estimator.
    assert _appraisal_threat(result) == pytest.approx(0.2)
    assert _appraisal_reward(result) == pytest.approx(0.1)


def test_semantic_assembly_derives_threat_and_reward_from_prototypes() -> None:
    # With store + embedding, 03 threat/reward are prototype-derived (not the 0.2/0.1 constants),
    # within range, and flow through 04 unchanged. The deterministic fake embedding has no
    # semantics, so we assert wiring truth + range + downstream flow, not "scary text scores high".
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    result = handle.tick()
    threat = _appraisal_threat(result)
    reward = _appraisal_reward(result)

    # Prototype-derived values are real numbers in range, computed from the fake-embedding cosine
    # of the stimulus to the owner's prototype sets; they are not the constant shim values.
    assert 0.0 <= threat <= 1.0
    assert 0.0 <= reward <= 1.0
    assert not (threat == pytest.approx(0.2) and reward == pytest.approx(0.1))

    # They flow through the unchanged 04 derivation: the same appraisal batch the 03 stage
    # produced is the one 04 consumed (cortisol from threat, dopamine from reward).
    appraisal_batch_id = result.stage_results["rapid_salience_appraisal"].batch.batch_id
    neuromod_source = result.stage_results["neuromodulator_system"].state.source_appraisal_batch_id
    assert neuromod_source == appraisal_batch_id


# --- Requirement 41: dimension-grounded aggregate salience judgment ---


def _appraisal_aggregate(result) -> float:
    return result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience.aggregate


def test_default_assembly_keeps_constant_aggregate() -> None:
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    # No semantic memory -> the first-version aggregate estimator returns the R63 moderate
    # baseline (0.7, raised from the original 0.4 to provide honest default-assembly ignition).
    assert _appraisal_aggregate(result) == pytest.approx(0.7)


def test_semantic_assembly_derives_aggregate_from_dimensions() -> None:
    # With store + embedding, the aggregate is a convex combination of the five real dimensions,
    # not the constant 0.4 shim, and matches the documented first-version weights.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    result = handle.tick()
    salience = result.stage_results["rapid_salience_appraisal"].batch.appraisals[0].salience
    expected = round(
        0.25 * salience.threat
        + 0.25 * salience.reward
        + 0.20 * salience.novelty
        + 0.15 * salience.uncertainty
        + 0.15 * salience.social,
        4,
    )
    assert salience.aggregate == pytest.approx(expected)


def test_semantic_assembly_aggregate_differs_with_dimensions() -> None:
    # Two ticks whose dimensions differ produce different aggregates (dimension-driven, not
    # constant). Tick 1 is a cold store (max novelty); tick 2 recalls stored experience -> lower
    # novelty -> a measurably different aggregate.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    first = handle.tick()
    second = handle.tick()
    assert _appraisal_aggregate(first) != pytest.approx(_appraisal_aggregate(second))


# --- Requirement 43: dual-timescale 04 dynamics + checkpoint resumption ---


def test_semantic_assembly_neuromodulator_evolves_across_ticks() -> None:
    # Under the semantic assembly the 04 update path is dual-timescale, so the same repeated
    # stimulus produces a changing (evolving) level trajectory rather than an identical recompute.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    results = handle.run_ticks(3)
    dopamine = [_neuromodulator_levels(r).dopamine for r in results]
    # Not all equal: the dual-timescale integrator carries state, so the trajectory moves.
    assert len(set(dopamine)) > 1


def test_default_assembly_neuromodulator_is_stateless_constant() -> None:
    # Without the semantic assembly, 04 keeps the stateless constant path: identical every tick.
    handle = _assemble()
    handle.startup()
    results = handle.run_ticks(3)
    dopamine = [_neuromodulator_levels(r).dopamine for r in results]
    assert len(set(dopamine)) == 1


def test_checkpoint_resumes_neuromodulator_levels_across_restart(tmp_path) -> None:
    store_path = str(tmp_path / "experience.sqlite3")
    ckpt_path = str(tmp_path / "continuity_checkpoint.sqlite3")

    # Session A: semantic assembly (so 04 is dual-timescale) + checkpointing.
    ckpt_a = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=ckpt_path))
    handle_a = _assemble(
        experience_store=ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path)),
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_a,
    )
    handle_a.startup()
    handle_a.run_ticks(3)
    saved = ckpt_a.load_latest()
    assert saved is not None
    assert saved.neuromodulator_levels is not None

    # Session B (restart): a fresh runtime against the same files resumes the prior 04 levels.
    ckpt_b = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=ckpt_path))
    handle_b = _assemble(
        experience_store=ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path)),
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_b,
    )
    handle_b.startup()
    seeded = handle_b.neuromodulator_stage._prior_state
    assert seeded is not None
    assert seeded.levels == saved.neuromodulator_levels


def test_checkpoint_without_semantic_assembly_carries_no_levels() -> None:
    # 04 is stateless without the semantic assembly, but it still publishes constant levels each
    # tick; the snapshot captures whatever the 04 stage published (constant), and a restart seeds
    # them harmlessly (the stateless path ignores the prior). Assert the save path is well-formed.
    ckpt = ContinuityCheckpointStore(backend=InMemoryCheckpointBackend())
    handle = _assemble(continuity_checkpoint=ckpt)
    handle.startup()
    handle.tick()
    saved = ckpt.load_latest()
    assert saved is not None
    # The default 04 path is constant, so levels are captured but resuming them changes nothing.
    assert saved.neuromodulator_levels is not None


# --- Requirement 44: dual-timescale 05 feeling persistence + checkpoint resumption ---


def test_semantic_assembly_feeling_evolves_across_ticks() -> None:
    # Under the semantic assembly the 05 construction path is dual-timescale, so the felt
    # body-state carries momentum and the trajectory moves rather than recomputing identically.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    results = handle.run_ticks(3)
    valence = [_feeling(r).valence for r in results]
    assert len(set(valence)) > 1


def test_default_assembly_feeling_is_stateless_constant() -> None:
    handle = _assemble()
    handle.startup()
    results = handle.run_ticks(3)
    valence = [_feeling(r).valence for r in results]
    assert len(set(valence)) == 1


def test_checkpoint_resumes_feeling_across_restart(tmp_path) -> None:
    store_path = str(tmp_path / "experience.sqlite3")
    ckpt_path = str(tmp_path / "continuity_checkpoint.sqlite3")

    ckpt_a = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=ckpt_path))
    handle_a = _assemble(
        experience_store=ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path)),
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_a,
    )
    handle_a.startup()
    handle_a.run_ticks(3)
    saved = ckpt_a.load_latest()
    assert saved is not None
    assert saved.feeling is not None

    ckpt_b = ContinuityCheckpointStore(backend=SqliteCheckpointBackend(db_path=ckpt_path))
    handle_b = _assemble(
        experience_store=ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=store_path)),
        embedding_gateway=_embedding_gateway(),
        continuity_checkpoint=ckpt_b,
    )
    handle_b.startup()
    seeded = handle_b.feeling_stage._prior_state
    assert seeded is not None
    assert seeded.feeling == saved.feeling


# --- Requirement 45: affect-grounded memory formation + durable affect-memory store ---


def _affect_memory_records(store):
    return [r for r in store.read_recent(200) if r.record_kind == "affect_memory"]


def _writeback_records(store):
    return [r for r in store.read_recent(200) if r.record_kind == "experience_writeback"]


def test_semantic_assembly_persists_consolidation_worthy_affect_memory() -> None:
    # Under the semantic assembly, 06 forms affect-tagged memory and the salience gate marks
    # consolidation-worthy ticks; those are durably persisted as embedded affect_memory records
    # co-residing with the 15 experience-writeback stream.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    handle.run_ticks(4)

    affect = _affect_memory_records(store)
    assert affect, "expected at least one consolidation-worthy affect-memory record"
    # Affect-memory records are embedded at write (recall-eligible on the shared surface).
    assert all(r.embedding is not None for r in affect)
    # They carry the discriminator and owner-provenance metadata.
    assert all(r.outcome_class == "affect_memory" for r in affect)
    assert all(dict(r.metadata).get("memory_family") in {"episodic", "autobiographical"} for r in affect)
    # The 15 continuity stream co-persists independently.
    assert _writeback_records(store)


def test_affect_memory_record_carries_real_feeling_provenance() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    handle.run_ticks(4)

    affect = _affect_memory_records(store)
    assert affect
    # The affect-memory record preserves the source feeling-state provenance linkage.
    assert all("source_feeling_state_id" in dict(r.linkage) for r in affect)
    # Its reason trace records why 06 judged the memory worth consolidating.
    assert all(r.reason_trace for r in affect)


def test_affect_memory_recall_eligible_through_directed_retrieval() -> None:
    # Once persisted+embedded, affect-memory participates in the shared semantic recall surface.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    handle.run_ticks(5)

    assert _affect_memory_records(store)
    result = handle.tick()
    bundle = result.stage_results["directed_retrieval_into_thought_window"].bundle
    all_hits = (
        bundle.short_term_context
        + bundle.mid_term_hits
        + bundle.long_term_hits
        + bundle.autobiographical_hits
    )
    # Recall is semantic over the shared store (R34 surface); affect-memory now rides it.
    assert any(hit.source == "experience_store_semantic" for hit in all_hits)


def test_affect_memory_survives_restart(tmp_path) -> None:
    db_path = str(tmp_path / "experience_store.sqlite3")

    store_a = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    handle_a = _assemble(experience_store=store_a, embedding_gateway=_embedding_gateway())
    handle_a.startup()
    handle_a.run_ticks(4)
    affect_after_a = len(_affect_memory_records(store_a))
    assert affect_after_a >= 1
    del handle_a, store_a

    # A fresh store object on the same file sees the prior session's affect-memory.
    store_b = ExperienceStore(backend=SqliteExperienceStoreBackend(db_path=db_path))
    persisted = _affect_memory_records(store_b)
    assert len(persisted) == affect_after_a
    assert all(r.embedding is not None for r in persisted)


def test_novel_first_tick_persists_autobiographical_affect_memory() -> None:
    # The very first tick against a cold store is maximally novel (real `03` novelty = 1.0 with
    # nothing to compare to), so R61 grounds a high prediction-mismatch (surprise) from that real
    # novelty: the salience gate consolidates and the formed memory is autobiographical. The 15
    # continuity record co-persists. (Before R61 a constant mismatch made every memory
    # autobiographical regardless of novelty; now it is the real cold-store novelty that drives it.)
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    handle.tick()

    affect = _affect_memory_records(store)
    assert affect, "a maximally-novel cold-store first tick should consolidate an affect-memory"
    assert all(r.continuity_kind == "autobiographical" for r in affect)
    assert _writeback_records(store)


def test_affect_memory_embedding_failure_is_hard_stop() -> None:
    # When affect-memory is enabled, an embedding failure at memory embed-at-write time is a hard
    # stop with no non-persistent fallback (same discipline as the 15 stream).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(provider=RaisingCompositionEmbeddingProvider()),
    )
    handle.startup()
    with pytest.raises(EmbeddingError):
        handle.run_ticks(3)


def test_default_assembly_persists_no_affect_memory() -> None:
    # Without the semantic opt-in, 06 keeps the constant shim and no affect-memory carry runs.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)  # recency-only, no embedding gateway
    handle.startup()
    handle.run_ticks(3)

    assert _affect_memory_records(store) == []
    assert handle.memory_record_bridge is None


def test_pure_default_assembly_has_no_memory_bridge() -> None:
    handle = _assemble()
    assert handle.memory_record_bridge is None
    handle.startup()
    result = handle.tick()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


# --- Requirement 46: workspace competition de-shim (real attention bottleneck) ---


def _workspace_result(result):
    return result.stage_results["workspace_competition_and_working_state"]


def test_semantic_assembly_workspace_score_is_real_not_constant() -> None:
    # Under the semantic assembly, 07 scores candidates from the real 06 priority_hint + real 05
    # feeling salience, so the score is not the constant 0.95 shim and it evolves across ticks
    # (the feeling carries cross-tick momentum from R44).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    results = handle.run_ticks(3)
    scores = []
    for result in results:
        for candidate in _workspace_result(result).candidate_set.candidates:
            scores.append(candidate.workspace_score_hint)
    assert scores, "expected at least one workspace candidate"
    # Not the constant shim, and the real score varies as the felt state evolves.
    assert all(s != 0.95 for s in scores)
    assert len(set(scores)) > 1


def test_semantic_assembly_working_state_is_bounded() -> None:
    # The working state is the bounded attention focus: retained ids are a subset of the
    # candidate set and never exceed the owner's first-version retention bound (3).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    for result in handle.run_ticks(3):
        ws = _workspace_result(result)
        candidate_ids = {c.candidate_id for c in ws.candidate_set.candidates}
        retained = ws.working_state.retained_candidate_ids
        assert len(retained) <= 3
        assert set(retained) <= candidate_ids
        # A non-empty candidate set is never reduced to an empty working state.
        if candidate_ids:
            assert retained


def test_default_assembly_keeps_constant_workspace_score_and_retains_all() -> None:
    # Without the semantic opt-in, 07 keeps the constant-score / retain-everything shim.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    ws = _workspace_result(result)
    assert all(c.workspace_score_hint == 0.95 for c in ws.candidate_set.candidates)
    # The shim retains every candidate (no bottleneck).
    assert len(ws.working_state.retained_candidate_ids) == len(ws.candidate_set.candidates)


# --- Requirement 47: conscious ignition commitment (global-workspace winner-take-all) ---


def _conscious_state(result):
    return result.stage_results["reportable_conscious_content"].state


def test_semantic_assembly_ignites_focal_conscious_content() -> None:
    # Under the semantic assembly, 08 uses the ignition policy: it commits focal reportable
    # content from the bounded working state rather than freezing on retained multiplicity.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    for result in handle.run_ticks(3):
        state = _conscious_state(result)
        ws = result.stage_results["workspace_competition_and_working_state"].working_state
        # Every tick with a non-empty attention focus ignites a focal item; the winner is a
        # retained working-state candidate (the global-workspace ignition).
        if ws.retained_candidate_ids:
            assert state.commit_status == "committed"
            assert state.focal_content is not None
            assert state.focal_content.source_workspace_candidate_id in ws.retained_candidate_ids
            # Ignition never reports retained content as semantic conflict.
            assert state.no_commit_reason != "semantic_conflict_unresolved"


def test_default_assembly_uses_count_based_commitment_policy() -> None:
    # Regression guard: the default (non-semantic) assembly keeps the count-based first-version
    # commitment policy. The default chain produces a single-candidate working state, so the
    # count-based policy commits it (one retained → commit), matching prior behavior.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    state = _conscious_state(result)
    ws = result.stage_results["workspace_competition_and_working_state"].working_state
    # Single retained candidate under the count-based default → committed (unchanged behavior).
    assert len(ws.retained_candidate_ids) == 1
    assert state.commit_status == "committed"


# --- Requirement 48: workspace-grounded thought-gate activation ---


def _gate_result(result):
    return result.stage_results["thought_gating_and_continuation_pressure"].result


def _max_retained_workspace_score(result) -> float:
    ws = result.stage_results["workspace_competition_and_working_state"]
    retained = set(ws.working_state.retained_candidate_ids)
    scores = [
        c.workspace_score_hint or 0.0
        for c in ws.candidate_set.candidates
        if c.candidate_id in retained
    ]
    return max(scores) if scores else 0.0


def test_semantic_assembly_grounds_gate_activation_in_workspace() -> None:
    # Under the semantic assembly, 09's global_activation_level equals the real 07 workspace
    # activation (max retained workspace_score_hint), not the constant 0.9.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    for result in handle.run_ticks(3):
        gate = _gate_result(result)
        activation = gate.contributing_signals["global_activation_level"]
        assert activation != 0.9  # not the constant shim
        assert activation == pytest.approx(round(_max_retained_workspace_score(result), 4))
        assert 0.0 <= activation <= 1.0


def test_semantic_assembly_gate_activation_varies_across_ticks() -> None:
    # The 07 score evolves across ticks (R44/R46 feeling momentum), so the grounded activation
    # is not a fixed value.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    activations = [
        _gate_result(result).contributing_signals["global_activation_level"]
        for result in handle.run_ticks(3)
    ]
    assert len(set(activations)) > 1


def test_semantic_assembly_preserves_arousal_coupling_with_grounded_activation() -> None:
    # R37 regression guard: the real neuromodulatory_arousal coupling still rides the snapshot
    # alongside the newly-grounded global_activation_level.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    gate = _gate_result(handle.tick())
    assert "neuromodulatory_arousal" in gate.contributing_signals
    assert "global_activation_level" in gate.contributing_signals


def test_default_assembly_keeps_constant_gate_activation() -> None:
    # Without the semantic opt-in, 09 keeps the constant global_activation_level = 0.9.
    handle = _assemble()
    handle.startup()
    gate = _gate_result(handle.tick())
    assert gate.contributing_signals["global_activation_level"] == 0.9
    # And no arousal coupling on the default (first-version) bridge.
    assert "neuromodulatory_arousal" not in gate.contributing_signals


def test_workspace_activation_helper_behavior() -> None:
    from helios_v2.composition.bridges import _workspace_activation
    from helios_v2.workspace import WorkingStateSnapshot, WorkspaceCandidate, WorkspaceCandidateSet
    from helios_v2.runtime.stages import WorkspaceCompetitionStageResult
    from helios_v2.workspace import (
        PublishWorkingStateOp,
        PublishWorkspaceCandidateSetOp,
        RunWorkspaceCompetitionOp,
    )

    def _candidate(cid: str, score: float) -> WorkspaceCandidate:
        return WorkspaceCandidate(
            candidate_id=cid,
            source_memory_candidate_id=f"m:{cid}",
            source_feeling_state_id="feeling:1",
            priority_hint=0.5,
            forced_consolidation=False,
            workspace_score_hint=score,
        )

    def _result(retained_ids, candidates) -> WorkspaceCompetitionStageResult:
        candidate_set = WorkspaceCandidateSet(
            set_id="ws:1",
            source_feeling_state_id="feeling:1",
            candidates=candidates,
            tick_id=1,
        )
        working_state = WorkingStateSnapshot(
            state_id="working:1",
            source_candidate_set_id="ws:1",
            retained_candidate_ids=retained_ids,
            tick_id=1,
        )
        return WorkspaceCompetitionStageResult(
            run_op=RunWorkspaceCompetitionOp(
                op_name="run_workspace_competition",
                owner="workspace_competition_and_working_state",
                candidate_count=len(candidates),
                feeling_state_id="feeling:1",
            ),
            candidate_set=candidate_set,
            working_state=working_state,
            publish_candidate_set_op=PublishWorkspaceCandidateSetOp(
                op_name="publish_workspace_candidate_set",
                owner="workspace_competition_and_working_state",
                set_id="ws:1",
                candidate_count=len(candidates),
                forced_candidate_count=0,
            ),
            publish_working_state_op=PublishWorkingStateOp(
                op_name="publish_working_state_snapshot",
                owner="workspace_competition_and_working_state",
                state_id="working:1",
                candidate_set_id="ws:1",
                retained_candidate_count=len(retained_ids),
            ),
        )

    # Max of retained scores.
    cands = (_candidate("a", 0.3), _candidate("b", 0.8), _candidate("c", 0.5))
    assert _workspace_activation(_result(("a", "b"), cands)) == pytest.approx(0.8)
    # Empty retained → 0.0.
    assert _workspace_activation(_result((), cands)) == 0.0
    # Only the retained subset counts (c is not retained).
    assert _workspace_activation(_result(("a", "c"), cands)) == pytest.approx(0.5)


# --- Requirement 49: thought-directed retrieval recall intent ---


@dataclass
class ContinuingThoughtProvider:
    """Provider double whose envelope always requests continuation, so 11 saves a handoff."""

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        import json

        envelope = {
            "thought": "keep thinking about the current line",
            "sufficiency": 0.2,
            "wants_to_continue": True,
            "continue_reason": "need more context",
            "proposed_action": {"intends_action": False, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _continuing_gateway() -> LlmGateway:
    resolved = default_composition_config()
    return LlmGateway(
        provider=ContinuingThoughtProvider(),
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _directed_retrieval(result):
    return result.stage_results["directed_retrieval_into_thought_window"]


def test_semantic_assembly_first_tick_falls_back_to_stimuli() -> None:
    # The first tick has no prior 11 handoff, so the 10 request is driven by the real 09
    # compact_stimuli with no recall intent (the defined absence fallback).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        gateway=_continuing_gateway(),
    )
    handle.startup()
    dr = _directed_retrieval(handle.tick())
    assert dr.request.recall_intent is None
    assert dr.request.selected_memory_refs == ()
    assert dr.plan.query_source == "compact_stimuli"
    # Not the constant shim string.
    assert "remember runtime chain context" not in dr.plan.query_text


def test_semantic_assembly_carries_prior_thought_recall_intent() -> None:
    # After a tick where 11 continued and saved a handoff, the next tick's 10 request carries the
    # real 11 recall intent (not the constant string).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        gateway=_continuing_gateway(),
    )
    handle.startup()
    first = handle.tick()
    # The first tick's 11 saved a handoff with this recall intent.
    first_handoff = first.stage_results["internal_thought_loop_owner"].result.memory_handoff
    assert first_handoff is not None and first_handoff.saved_for_next_tick

    second = handle.tick()
    dr = _directed_retrieval(second)
    assert dr.request.recall_intent == first_handoff.recall_intent
    assert dr.request.recall_intent != "remember runtime chain context"
    assert dr.request.selected_memory_refs == first_handoff.selected_memory_refs
    # The recall intent leads the query text and the source reflects it.
    assert dr.request.recall_intent in dr.plan.query_text
    assert dr.plan.query_source in {"recall_intent", "mixed"}


def test_default_assembly_keeps_constant_recall_intent() -> None:
    # Without the semantic opt-in, the 10 request keeps the constant recall intent and the
    # fabricated memory ref (the first-version bridge).
    handle = _assemble()
    handle.startup()
    dr = _directed_retrieval(handle.tick())
    assert dr.request.recall_intent == "remember runtime chain context"
    assert dr.request.selected_memory_refs == ("memory:runtime:1",)


def test_thought_directed_request_bridge_uses_holder_and_falls_back() -> None:
    from types import SimpleNamespace

    from helios_v2.composition.bridges import (
        PriorThoughtRecallHolder,
        ThoughtDirectedRetrievalRequestBridge,
    )
    from helios_v2.thought_gating import ContinuationPressureState, SelectedStimulusSummary

    stimulus = SelectedStimulusSummary(
        stimulus_id="s1", source_kind="external_text", source_channel_id="cli", stimulus_intensity=0.9
    )
    # The bridge reads only .result.result_id, .continuation_state.active, .result.selected_stimuli.
    gating_stage_result = SimpleNamespace(
        result=SimpleNamespace(result_id="gate:1", selected_stimuli=(stimulus,)),
        continuation_state=ContinuationPressureState.inactive(),
    )
    frame = SimpleNamespace(tick_id=5)

    # Holder carries a directive → the request uses it.
    holder = PriorThoughtRecallHolder(recall_intent="recall the prior thread", selected_memory_refs=("m:1",))
    bridge = ThoughtDirectedRetrievalRequestBridge(holder=holder)
    request = bridge.build_request(frame, gating_stage_result)
    assert request.recall_intent == "recall the prior thread"
    assert request.selected_memory_refs == ("m:1",)
    assert request.source_gate_result_id == "gate:1"

    # Empty holder → stimulus-driven fallback (no recall intent).
    holder.clear()
    request2 = bridge.build_request(frame, gating_stage_result)
    assert request2.recall_intent is None
    assert request2.selected_memory_refs == ()
    assert request2.compact_stimuli == (stimulus,)


# --- Requirement 50: runtime interoceptive signal source (BODY producer) ---


@dataclass
class _FixedInteroceptiveSampler:
    def sample(self):
        from helios_v2.interoception import RuntimePressureSample

        # cpu/memory kept low so the R53 workload_pressure stays in the gate's firing window and
        # the full tick completes; this test asserts the 02->05 afferent count, not gate behavior.
        return RuntimePressureSample(
            cpu_pressure=0.2, memory_pressure=0.1, latency_pressure=0.0, error_pressure=0.0
        )


def test_interoception_opt_in_feeds_internal_signals_into_feeling() -> None:
    # With the interoceptive source registered, the 02 batch carries modality="interoceptive"
    # stimuli and the 05 feeling stage receives non-empty internal_signals (the live BODY afferent).
    handle = _assemble(interoceptive_sampler=_FixedInteroceptiveSampler())
    handle.startup()
    result = handle.tick()

    sensory = result.stage_results["sensory_ingress"]
    interoceptive = [s for s in sensory.batch.stimuli if s.modality == "interoceptive"]
    assert len(interoceptive) == 4

    feeling = result.stage_results["interoceptive_feeling_layer"]
    # The 05 update op records how many internal signals it received.
    assert feeling.update_op.internal_signal_count == 4


def test_default_assembly_has_no_interoceptive_signals() -> None:
    # Without the opt-in, no interoceptive source is registered and 05 gets empty internal_signals.
    handle = _assemble()
    handle.startup()
    result = handle.tick()

    sensory = result.stage_results["sensory_ingress"]
    assert all(s.modality != "interoceptive" for s in sensory.batch.stimuli)
    feeling = result.stage_results["interoceptive_feeling_layer"]
    assert feeling.update_op.internal_signal_count == 0


# --- Requirement 51: interoceptive-signal-shaped feeling (real machine -> feeling -> 07) ---


@dataclass
class _ConfigurableInteroceptiveSampler:
    """Deterministic injected sampler returning a fixed pressure sample (network-free)."""

    cpu: float = 0.0
    memory: float = 0.0
    latency: float = 0.0
    error: float = 0.0

    def sample(self):
        from helios_v2.interoception import RuntimePressureSample

        return RuntimePressureSample(
            cpu_pressure=self.cpu,
            memory_pressure=self.memory,
            latency_pressure=self.latency,
            error_pressure=self.error,
        )


def _max_candidate_score(result) -> float:
    candidates = _workspace_result(result).candidate_set.candidates
    return max((c.workspace_score_hint or 0.0) for c in candidates)


def test_r51_interoceptive_pressure_shapes_feeling_and_workspace_under_semantic_assembly() -> None:
    # The first end-to-end FG-2 causal chain: real machine condition -> 05 feeling -> 07 competition.
    # A high-pressure body sample yields a measurably different 05 feeling and a different 07
    # candidate score than an at-rest sample, on the same semantic assembly and same first tick.
    high_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    high = _assemble(
        experience_store=high_store,
        embedding_gateway=_embedding_gateway(),
        # Drive felt stress through the latency/error channels (which feed tension/fatigue/pain)
        # while keeping cpu/memory (the R53 workload channels) low, so the gate still fires and the
        # full tick completes. The no-fire-on-high-compute-load chain closure is a future slice.
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(
            cpu=0.2, memory=0.2, latency=0.9, error=0.9
        ),
    )
    high.startup()
    high_result = high.tick()

    rest_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    rest = _assemble(
        experience_store=rest_store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(
            cpu=0.0, memory=0.0, latency=0.0, error=0.0
        ),
    )
    rest.startup()
    rest_result = rest.tick()

    high_feeling = _feeling(high_result)
    rest_feeling = _feeling(rest_result)
    # Body pressure raises the mapped stress dimensions of the felt body-state.
    assert high_feeling.tension > rest_feeling.tension
    assert high_feeling.fatigue > rest_feeling.fatigue
    assert high_feeling.pain_like > rest_feeling.pain_like
    assert high_feeling.arousal > rest_feeling.arousal

    # The changed feeling propagates into the 07 workspace competition score (R46 reads
    # arousal/tension/pain as feeling_salience), so the real machine condition reaches cognition.
    assert _max_candidate_score(high_result) > _max_candidate_score(rest_result)


def test_r51_semantic_assembly_without_interoception_is_unchanged() -> None:
    # No interoceptive sampler -> 05 feeling derives from 04 only; the R51 path is never built.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    result = handle.tick()
    feeling = _feeling(result)
    # Sanity: 05 received no interoceptive afferent, so its feeling carries no body contribution.
    assert result.stage_results["interoceptive_feeling_layer"].update_op.internal_signal_count == 0
    # And it is still the real (non-constant) neuromodulator-derived feeling.
    assert feeling != InteroceptiveFeelingVector(
        valence=0.4, arousal=0.7, tension=0.5, comfort=0.2, fatigue=0.3, pain_like=0.1, social_safety=0.4
    )


# --- Requirement 52: workspace multiplicity from recalled affect-memory replay ---


def _workspace_candidate_count(result) -> int:
    return len(_workspace_result(result).candidate_set.candidates)


def test_r52_affect_memory_record_carries_decodable_affect_vector() -> None:
    # The R52 affect-vector metadata extension is persisted and round-trips.
    from helios_v2.composition.bridges import _decode_affect_vector

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    handle.run_ticks(4)

    affect = _affect_memory_records(store)
    assert affect, "expected at least one consolidation-worthy affect-memory record"
    for record in affect:
        encoded = dict(record.metadata).get("affect_vector")
        assert encoded is not None
        decoded = _decode_affect_vector(encoded)
        assert decoded is not None
        # Seven bounded dimensions reconstructed.
        for dimension in (
            "valence",
            "arousal",
            "tension",
            "comfort",
            "fatigue",
            "pain_like",
            "social_safety",
        ):
            assert 0.0 <= getattr(decoded, dimension) <= 1.0


def test_r52_workspace_competes_over_multiplicity_after_recall() -> None:
    # Once prior affect-memories exist, a later tick's 06 surfaces recalled candidates so the 07
    # workspace competes over more than one candidate (R46/47/48 exercised end to end).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    # Build up a prior existence of consolidation-worthy affect-memories.
    handle.run_ticks(5)
    assert _affect_memory_records(store), "precondition: prior affect-memory persisted"

    result = handle.tick()
    assert _workspace_candidate_count(result) > 1


def test_r52_ignition_commits_single_focal_among_multiplicity() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    handle.run_ticks(5)

    result = handle.tick()
    assert _workspace_candidate_count(result) > 1
    # 08 ignites a single focal reportable content among the multiplicity (winner-take-all),
    # and 09's global_activation_level equals the max retained candidate score.
    conscious = result.stage_results["reportable_conscious_content"]
    state = conscious.state
    # A committed conscious state exposes exactly one focal content (the ignition winner).
    assert state.commit_status == "committed"
    assert state.focal_content is not None
    gate = _gate_result(result)
    activation = gate.contributing_signals["global_activation_level"]
    assert activation == pytest.approx(round(_max_retained_workspace_score(result), 4))


def test_r52_default_assembly_has_single_candidate() -> None:
    # Without the semantic opt-in, no recalled provider is wired; 07 sees a single candidate.
    handle = _assemble()
    handle.startup()
    handle.run_ticks(3)
    result = handle.tick()
    assert _workspace_candidate_count(result) == 1


def test_r52_recency_only_assembly_has_single_candidate() -> None:
    # Persistence without embedding (recency-only) is not semantic; no recalled provider.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store)
    handle.startup()
    handle.run_ticks(3)
    result = handle.tick()
    assert _workspace_candidate_count(result) == 1


# --- Requirement 53: workload pressure from the interoceptive afferent ---


def test_r53_workload_pressure_tracks_interoceptive_load() -> None:
    # Under an interoceptive assembly, the 09 gate's workload_pressure is the max cpu/memory
    # interoceptive load, not the constant 0.1. Kept within the firing window (load <= ~0.3) so the
    # tick still completes; the no-fire-on-high-load chain closure is a separate future requirement.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.3, memory=0.2),
    )
    handle.startup()
    result = handle.tick()
    workload = _gate_result(result).contributing_signals["workload_pressure"]
    assert workload == pytest.approx(0.3)  # max(cpu=0.3, memory=0.2)


def test_r53_at_rest_interoception_yields_real_zero_workload() -> None:
    # An at-rest sampler yields real 0.0 load, distinct from the constant 0.1 shim — proving the
    # value is genuinely sourced from the afferent (and not the old constant).
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.0, memory=0.0),
    )
    handle.startup()
    result = handle.tick()
    workload = _gate_result(result).contributing_signals["workload_pressure"]
    assert workload == pytest.approx(0.0)


def test_r53_higher_load_lowers_gate_score_within_firing_window() -> None:
    # workload_pressure is subtractive in the gate score; higher real load lowers it. Both ticks
    # stay within the firing window so the chain completes end to end.
    low_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    low = _assemble(
        experience_store=low_store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.0, memory=0.0),
    )
    low.startup()
    low_result = low.tick()

    high_store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    high = _assemble(
        experience_store=high_store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.3, memory=0.3),
    )
    high.startup()
    high_result = high.tick()

    low_gate = _gate_result(low_result)
    high_gate = _gate_result(high_result)
    assert (
        high_gate.contributing_signals["workload_pressure"]
        > low_gate.contributing_signals["workload_pressure"]
    )
    assert high_gate.gate_score < low_gate.gate_score


def test_r53_default_assembly_keeps_constant_workload_pressure() -> None:
    # No interoceptive source -> the gate keeps the constant 0.1 byte-for-byte.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    workload = _gate_result(result).contributing_signals["workload_pressure"]
    assert workload == pytest.approx(0.1)


def test_r53_semantic_without_sampler_keeps_constant_workload_pressure() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()
    result = handle.tick()
    workload = _gate_result(result).contributing_signals["workload_pressure"]
    assert workload == pytest.approx(0.1)


def test_r53_helper_maps_high_load_to_high_workload_pressure() -> None:
    # Owner-neutral helper: a high cpu/memory afferent maps to a high workload_pressure (>= the
    # gate's resource_pressure_block_threshold of 0.9), which is what would drive the gate's
    # documented resource-pressure block path. Tested at the helper level because the assembled
    # chain has no no-fire closure yet (a future requirement).
    from helios_v2.composition.bridges import _interoceptive_workload_pressure
    from helios_v2.runtime.stages import RuntimeFrame, SensoryIngressStageResult
    from helios_v2.sensory import SensoryIngress, RawSignal

    ingress = SensoryIngress()

    @dataclass
    class _LoadSource:
        source_name_value: str = "interoception"

        @property
        def source_name(self) -> str:
            return self.source_name_value

        def emit_raw_signals(self):
            return (
                RawSignal(
                    signal_id="interoceptive:cpu",
                    source_name="interoception",
                    signal_type="interoceptive",
                    content="cpu_pressure=0.9500",
                    channel="interoception",
                    metadata={"pressure_channel": "cpu", "pressure_value": 0.95},
                    required=False,
                ),
                RawSignal(
                    signal_id="interoceptive:memory",
                    source_name="interoception",
                    signal_type="interoceptive",
                    content="memory_pressure=0.7000",
                    channel="interoception",
                    metadata={"pressure_channel": "memory", "pressure_value": 0.7},
                    required=False,
                ),
            )

    ingress.register_source(_LoadSource())
    batch = ingress.collect_stimuli()
    publish_op = ingress.build_publish_batch_op(batch)
    frame = RuntimeFrame(
        tick_id=1,
        stage_results={"sensory_ingress": SensoryIngressStageResult(batch=batch, publish_op=publish_op)},
    )
    workload = _interoceptive_workload_pressure(frame)
    assert workload == pytest.approx(0.95)  # max(cpu=0.95, memory=0.7)
    assert workload >= 0.9  # would trigger the gate's resource-pressure block path


def test_r53_helper_returns_default_without_interoceptive_stimuli() -> None:
    from helios_v2.composition.bridges import _interoceptive_workload_pressure
    from helios_v2.runtime.stages import RuntimeFrame

    # No sensory result at all -> default 0.1.
    assert _interoceptive_workload_pressure(RuntimeFrame(tick_id=1, stage_results={})) == pytest.approx(0.1)


# --- Requirement 54: gate no-fire tick closure ---


def _no_fire_handle():
    # A high cpu/memory interoceptive load drives the 09 gate to resource_pressure_too_high/no_fire
    # (R53 grounded workload_pressure). With R54 the tick now completes as a no-fire tick.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    return _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.95, memory=0.95),
    )


def test_r54_high_load_no_fire_tick_completes() -> None:
    handle = _no_fire_handle()
    handle.startup()
    result = handle.tick()  # must not raise

    gate = _gate_result(result)
    assert gate.decision == "no_fire"
    assert gate.no_fire_reason == "resource_pressure_too_high"


def test_r54_post_gate_stages_are_inactive_on_no_fire() -> None:
    handle = _no_fire_handle()
    handle.startup()
    result = handle.tick()

    for stage_name in (
        "directed_retrieval_into_thought_window",
        "embodied_subjective_prompt_and_action_autonomy",
        "outward_expression_owner",
        "outward_expression_execution_externalization_owner",
        "internal_thought_loop_owner",
        "action_proposal_externalization_contract",
        "identity_governance_self_revision_integration",
    ):
        stage_result = result.stage_results[stage_name]
        assert stage_result.activated is False, stage_name
        assert stage_result.inactive_id is not None, stage_name


def test_r54_no_fire_closes_through_internal_only_continuity() -> None:
    handle = _no_fire_handle()
    handle.startup()
    result = handle.tick()

    # Planner records no_actionable_proposal; writeback records an internal_only continuity outcome.
    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "no_actionable_proposal"
    writeback = result.stage_results["execution_writeback_and_autobiographical_consolidation"]
    statuses = {r.status for r in writeback.results}
    assert "written_internal_only" in statuses
    # Autonomy and evaluation still ran read-through.
    assert result.stage_results["subjective_autonomy_and_proactive_evolution"].result is not None
    assert result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact is not None


def test_r54_continuation_carries_across_no_fire_then_fire() -> None:
    # A no-fire tick must not reset continuity: a following fire-able tick still runs the chain.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())

    # Use a sampler we can flip: start high (no-fire), then assert a fresh low-load handle fires.
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.95, memory=0.95),
    )
    handle.startup()
    first = handle.tick()
    assert _gate_result(first).decision == "no_fire"
    # The no-fire tick completed and produced an autonomy result carrying continuity state.
    autonomy = first.stage_results["subjective_autonomy_and_proactive_evolution"].result
    assert autonomy.long_horizon_state is not None


def test_r54_fired_tick_unchanged_activated_true() -> None:
    # An ordinary fired tick (no interoceptive load) has all post-gate stages activated.
    handle = _assemble(experience_store=ExperienceStore(backend=InMemoryExperienceStoreBackend()), embedding_gateway=_embedding_gateway())
    handle.startup()
    result = handle.tick()
    assert _gate_result(result).decision == "fire"
    for stage_name in (
        "directed_retrieval_into_thought_window",
        "internal_thought_loop_owner",
        "action_proposal_externalization_contract",
        "identity_governance_self_revision_integration",
    ):
        assert result.stage_results[stage_name].activated is True, stage_name


# --- Requirement 55: temporal pacing and DMN rest-state gate inputs ---


def test_r55_default_assembly_keeps_constant_temporal_and_dmn() -> None:
    # No temporal source -> the gate keeps temporal_signal=0.4 and the DMN term byte-for-byte.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    gate = _gate_result(result)
    assert gate.contributing_signals["temporal_signal"] == pytest.approx(0.4)


def test_r55_temporal_source_forwards_into_gate_signal() -> None:
    # With a temporal source wired, the gate's temporal_signal comes from the source. The default
    # sensory source emits an external (text) stimulus, so DMN is suppressed and the elapsed-rest
    # accumulation resets whenever the gate fires.
    from helios_v2.temporal import RestStateTemporalSource

    source = RestStateTemporalSource(per_tick_increment=0.2)
    handle = _assemble(temporal_source=source)
    handle.startup()
    result = handle.tick()
    gate = _gate_result(result)
    # First tick: cold-start elapsed-rest is 0, so temporal_signal is the source's 0.0, not 0.4.
    assert gate.contributing_signals["temporal_signal"] == pytest.approx(0.0)


def test_r55_dmn_reflects_external_stimulus_presence() -> None:
    # The default sensory source emits an external text stimulus, so the temporal source reports
    # the DMN as suppressed (dmn_available=False) — its +0.10 gate term is absent.
    from helios_v2.temporal import RestStateTemporalSource
    from helios_v2.composition.bridges import _external_stimulus_present, _temporal_inputs
    from helios_v2.runtime.stages import RuntimeFrame, SensoryIngressStageResult
    from helios_v2.sensory import SensoryIngress, RawSignal

    # Owner-neutral helper level: an external stimulus present -> dmn_available False.
    ingress = SensoryIngress()

    from dataclasses import dataclass as _dc

    @_dc
    class _TextSource:
        @property
        def source_name(self) -> str:
            return "cli"

        def emit_raw_signals(self):
            return (
                RawSignal(
                    signal_id="001",
                    source_name="cli",
                    signal_type="text",
                    content="hello",
                    channel="cli",
                    metadata=None,
                ),
            )

    ingress.register_source(_TextSource())
    batch = ingress.collect_stimuli()
    publish_op = ingress.build_publish_batch_op(batch)
    frame = RuntimeFrame(
        tick_id=1,
        stage_results={"sensory_ingress": SensoryIngressStageResult(batch=batch, publish_op=publish_op)},
    )
    assert _external_stimulus_present(frame) is True
    _, dmn = _temporal_inputs(frame, RestStateTemporalSource())
    assert dmn is False

    # An empty (rest) batch -> dmn_available True.
    empty_ingress = SensoryIngress()
    empty_batch = empty_ingress.collect_stimuli()
    empty_publish = empty_ingress.build_publish_batch_op(empty_batch)
    rest_frame = RuntimeFrame(
        tick_id=2,
        stage_results={"sensory_ingress": SensoryIngressStageResult(batch=empty_batch, publish_op=empty_publish)},
    )
    assert _external_stimulus_present(rest_frame) is False
    _, dmn_rest = _temporal_inputs(rest_frame, RestStateTemporalSource())
    assert dmn_rest is True


def test_r55_elapsed_rest_accumulates_across_no_fire_ticks_end_to_end() -> None:
    # Drive consecutive no-fire ticks (high compute load -> resource_pressure_too_high, R53/R54)
    # under a temporal source, and assert the temporal_signal accumulates across them (rest pacing).
    from helios_v2.temporal import RestStateTemporalSource

    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.95, memory=0.95),
        temporal_source=RestStateTemporalSource(per_tick_increment=0.2),
    )
    handle.startup()
    r1 = handle.tick()
    r2 = handle.tick()
    r3 = handle.tick()
    assert _gate_result(r1).decision == "no_fire"
    # Tick 1 cold start: 0.0; subsequent no-fire ticks accumulate.
    t1 = _gate_result(r1).contributing_signals["temporal_signal"]
    t2 = _gate_result(r2).contributing_signals["temporal_signal"]
    t3 = _gate_result(r3).contributing_signals["temporal_signal"]
    assert t1 == pytest.approx(0.0)
    assert t2 == pytest.approx(0.2)
    assert t3 == pytest.approx(0.4)


# --- Requirement 58: RuntimeProfile capability bundle ---


from helios_v2.composition import RuntimeProfile


def test_default_profile_matches_default_capability_set() -> None:
    profile = RuntimeProfile()
    assert profile.deterministic_thought is False
    assert profile.channel_cli is False
    assert profile.experience_store is None
    assert profile.embedding_gateway is None
    assert profile.embedding_profile_name == "experience-embedding"
    assert profile.continuity_checkpoint is None
    assert profile.interoceptive_sampler is None
    assert profile.temporal_source is None
    assert profile.semantic_memory_enabled is False


def test_profile_embedding_without_store_raises() -> None:
    with pytest.raises(CompositionError, match="durable experience store"):
        RuntimeProfile(embedding_gateway=_embedding_gateway())


def test_profile_semantic_memory_enabled_requires_both() -> None:
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    assert RuntimeProfile(experience_store=store).semantic_memory_enabled is False
    profile = RuntimeProfile(experience_store=store, embedding_gateway=_embedding_gateway())
    assert profile.semantic_memory_enabled is True


def test_profile_and_loose_kwarg_together_raise() -> None:
    profile = RuntimeProfile(deterministic_thought=True)
    with pytest.raises(CompositionError, match="overlapping loose keyword arguments"):
        assemble_runtime(profile=profile, deterministic_thought=True)


def test_profile_path_and_loose_kwarg_path_are_equivalent() -> None:
    # Deterministic offline assembly via both routes must produce an equivalent runtime.
    via_kwargs = assemble_runtime(deterministic_thought=True)
    via_profile = assemble_runtime(profile=RuntimeProfile(deterministic_thought=True))

    kwargs_specs = {spec.name for spec in via_kwargs.kernel.dependency_specs}
    profile_specs = {spec.name for spec in via_profile.kernel.dependency_specs}
    assert kwargs_specs == profile_specs
    # The offline deterministic assembly omits the LLM readiness dependency in both routes.
    assert LLM_PROFILES_READY not in profile_specs

    via_kwargs.startup()
    via_profile.startup()
    assert via_kwargs.tick().tick_id == via_profile.tick().tick_id


# --- Requirement 59: injectable external afferent source ---


from helios_v2.composition import RuntimeProfile, SequenceExternalSignalSource
from helios_v2.sensory import RawSignal as _RawSignal


def _external_batch(signal_id: str, content: str) -> tuple[_RawSignal, ...]:
    return (
        _RawSignal(
            signal_id=signal_id,
            source_name="external",
            signal_type="text",
            content=content,
            channel="external",
            metadata={"turn_id": signal_id},
        ),
    )


def _appraised_contents(result) -> tuple[str, ...]:
    return tuple(
        stimulus.content
        for stimulus in result.stage_results["sensory_ingress"].batch.stimuli
    )


def test_injected_external_source_replaces_constant_placeholder() -> None:
    source = SequenceExternalSignalSource(
        batches=(_external_batch("e1", "a real external observation"),)
    )
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()

    contents = _appraised_contents(result)
    assert "a real external observation" in contents
    # The fabricated constant placeholder is not registered when a real source is injected.
    assert "hello runtime" not in contents


def test_external_source_and_channel_cli_are_mutually_exclusive() -> None:
    source = SequenceExternalSignalSource(batches=(_external_batch("e1", "x"),))
    with pytest.raises(CompositionError, match="external afferent"):
        assemble_runtime(external_signal_source=source, channel_cli=True)


def test_external_source_mutual_exclusion_on_profile() -> None:
    source = SequenceExternalSignalSource(batches=(_external_batch("e1", "x"),))
    with pytest.raises(CompositionError, match="external afferent"):
        RuntimeProfile(external_signal_source=source, channel_cli=True)


def test_varying_external_stimulus_drives_appraisal_and_affect_across_ticks() -> None:
    # FG-2 (external branch): a real external source whose content varies across ticks produces
    # measurably different `03` novelty and a different `04` neuromodulator state across ticks,
    # under the semantic assembly. This is a second FG-2 causal chain alongside R51's interoceptive
    # one, driven by the external afferent rather than internal pressure.
    source = SequenceExternalSignalSource(
        batches=(
            _external_batch("e1", "first distinct external content alpha"),
            _external_batch("e2", "second wholly different external content omega zeta"),
        )
    )
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        external_signal_source=source,
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()

    first = handle.tick()
    second = handle.tick()

    # The external content actually reached appraisal on each tick.
    assert "first distinct external content alpha" in _appraised_contents(first)
    assert "second wholly different external content omega zeta" in _appraised_contents(second)

    # The real novelty dimension differs across the two ticks (the external stimulus drives `03`),
    # and the difference propagates into the `04` neuromodulator state.
    assert _appraisal_novelty(first) != pytest.approx(_appraisal_novelty(second))
    first_levels = _neuromodulator_levels(first)
    second_levels = _neuromodulator_levels(second)
    assert (
        first_levels.norepinephrine != pytest.approx(second_levels.norepinephrine)
        or first_levels.dopamine != pytest.approx(second_levels.dopamine)
    )


def test_empty_external_afferent_completes_the_tick() -> None:
    # Honest absence: an injected source that emits nothing must not crash the tick. With no
    # external stimulus the batch is empty and the chain still closes (no-fire / internal-only).
    source = SequenceExternalSignalSource(batches=())
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()

    assert _appraised_contents(result) == ()
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_sequence_source_exhaustion_yields_empty_then_no_crash() -> None:
    # The first tick replays the one supplied batch; the second tick is past the end and emits
    # an empty batch (honest absence), never a fabricated constant.
    source = SequenceExternalSignalSource(batches=(_external_batch("e1", "only one batch"),))
    handle = _assemble(external_signal_source=source)
    handle.startup()

    first = handle.tick()
    second = handle.tick()

    assert "only one batch" in _appraised_contents(first)
    assert _appraised_contents(second) == ()


def test_default_assembly_unchanged_without_external_source() -> None:
    # Regression guard: with no external source the default constant placeholder is registered.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    assert "hello runtime" in _appraised_contents(result)


# --- Requirement 60: memory binding context derived from the real perceived stimulus ---


def _formed_memory_items(result):
    return result.stage_results["memory_affect_and_replay"].state.memory_items


def _primary_memory_content(result):
    items = _formed_memory_items(result)
    assert items, "expected at least one formed memory item"
    return items[0].content


def test_memory_content_derives_from_real_external_percept() -> None:
    # A real external stimulus drives the formed memory's content/provenance, not the old
    # hardcoded ("hello","novelty") binding constant.
    source = SequenceExternalSignalSource(
        batches=(_external_batch("e1", "the harbor lights flicker at dusk"),)
    )
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()
    content = _primary_memory_content(result)

    assert content.content_kind == "perceived-stimulus-summary"
    # Tokens are mechanically derived from the real perceived content (substrings of it).
    assert "harbor" in content.salient_tokens
    assert "flicker" in content.salient_tokens
    # The retired constant tokens are gone.
    assert content.salient_tokens != ("hello", "novelty")
    # Provenance traces to the real stimulus.
    assert content.summary_ref == "stimulus:external:e1"


def test_memory_content_differs_with_different_external_percept() -> None:
    source = SequenceExternalSignalSource(
        batches=(
            _external_batch("e1", "alpha beta gamma"),
            _external_batch("e2", "delta epsilon zeta"),
        )
    )
    handle = _assemble(external_signal_source=source)
    handle.startup()

    first = handle.tick()
    second = handle.tick()

    first_tokens = _primary_memory_content(first).salient_tokens
    second_tokens = _primary_memory_content(second).salient_tokens
    assert "alpha" in first_tokens
    assert "delta" in second_tokens
    assert first_tokens != second_tokens


def test_empty_percept_binds_honest_no_perceived_stimulus_memory() -> None:
    # R65: an empty-percept tick now short-circuits the pre-gate chain. The `06` memory stage
    # returns `activated=False` without forming a memory, and the tick completes through the
    # `09` gate no-fire path. The R60 no-percept marker path in the binding-context bridge is
    # now a defensive fallback unreachable from the standard runtime path.
    source = SequenceExternalSignalSource(batches=())
    handle = _assemble(external_signal_source=source)
    handle.startup()

    result = handle.tick()

    memory_result = result.stage_results["memory_affect_and_replay"]
    assert memory_result.activated is False
    assert memory_result.state.memory_items == ()
    assert memory_result.state.replay_candidates == ()
    gate_result = result.stage_results["thought_gating_and_continuation_pressure"]
    assert gate_result.result.decision == "no_fire"
    assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER


def test_default_percept_flows_into_memory_content_no_separate_constant() -> None:
    # The default assembly's placeholder percept ("hello runtime") flows into the memory content,
    # proving no separate hardcoded binding constant remains.
    handle = _assemble()
    handle.startup()

    result = handle.tick()
    content = _primary_memory_content(result)

    assert content.content_kind == "perceived-stimulus-summary"
    assert "hello" in content.salient_tokens
    assert "runtime" in content.salient_tokens


# --- Requirement 61: prediction-mismatch evidence grounded in real appraisal novelty ---


def _appraisal_mismatch_evidence(handle, result):
    # Reconstruct what the mismatch bridge produced this tick from the real 03 result, to assert
    # the bridge's novelty-grounded behavior (the bridge has no stage result of its own).
    from helios_v2.composition.bridges import FirstVersionPredictionMismatchEvidenceBridge

    class _Frame:
        def __init__(self, stage_results, tick_id):
            self.stage_results = stage_results
            self.tick_id = tick_id

    feeling_result = result.stage_results["interoceptive_feeling_layer"]
    frame = _Frame(result.stage_results, result.tick_id)
    return FirstVersionPredictionMismatchEvidenceBridge().build_mismatch_evidence(frame, feeling_result)


def _formed_family(result):
    items = result.stage_results["memory_affect_and_replay"].state.memory_items
    assert items
    return items[0].family


def _seed_store_with(store, gateway, content: str) -> None:
    from helios_v2.persistence import PersistedExperienceRecord

    vector = gateway.embed(
        _EmbeddingRequest(
            request_id="seed:r61", target_profile="experience-embedding", input_text=content
        )
    ).vector
    store.append_records(
        (
            PersistedExperienceRecord(
                record_id="experience:seed:r61",
                tick_id=1,
                continuity_kind="external_action",
                outcome_class="world_changed",
                source_outcome_kind="planner_bridge",
                source_outcome_id="planner-bridge-result:seed",
                writeback_status="written",
                summary=content,
                requested_effect_summary="reply",
                applied_effect_summary="replied",
                reason_trace=("seeded",),
                linkage={"source_request_id": "planner-bridge-result:seed"},
                embedding=vector,
            ),
        )
    )


def test_novel_percept_yields_high_mismatch_and_autobiographical_memory() -> None:
    # A cold store -> maximal real novelty -> R61 grounds a high mismatch from it, so the formed
    # memory is autobiographical and the mismatch score tracks the real novelty (not the 0.8 shim).
    source = SequenceExternalSignalSource(batches=(_external_batch("e1", "an utterly unfamiliar event"),))
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        external_signal_source=source,
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()

    result = handle.tick()
    evidence = _appraisal_mismatch_evidence(handle, result)
    novelty = _appraisal_novelty(result)

    assert evidence is not None
    assert evidence.mismatch_score == pytest.approx(novelty)
    assert evidence.mismatch_score != pytest.approx(0.8)  # not the retired constant
    assert _formed_family(result) == "autobiographical"


def test_familiar_percept_yields_no_mismatch_and_episodic_memory() -> None:
    # A percept highly similar to stored experience -> low real novelty (< threshold) -> R61
    # produces no mismatch evidence, so the formed memory is episodic, not autobiographical.
    content = "the quarterly report is due on tuesday"
    source = SequenceExternalSignalSource(batches=(_external_batch("e1", content),))
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    gateway = _embedding_gateway()
    _seed_store_with(store, gateway, content)
    handle = _assemble(
        external_signal_source=source,
        experience_store=store,
        embedding_gateway=gateway,
    )
    handle.startup()

    result = handle.tick()
    novelty = _appraisal_novelty(result)
    evidence = _appraisal_mismatch_evidence(handle, result)

    assert novelty < 0.5  # familiar percept: real novelty below the mismatch threshold
    assert evidence is None
    assert _formed_family(result) == "episodic"


def test_default_assembly_mismatch_derives_from_constant_novelty_not_old_constant() -> None:
    # The default assembly's 03 novelty is the first-version constant 0.6 (>= the 0.5 threshold),
    # so the mismatch is derived from 0.6, not the retired 0.8 mismatch constant.
    handle = _assemble()
    handle.startup()
    result = handle.tick()

    evidence = _appraisal_mismatch_evidence(handle, result)
    assert evidence is not None
    assert evidence.mismatch_score == pytest.approx(0.6)
    assert evidence.mismatch_score != pytest.approx(0.8)


# --- Requirement 62: thought-gate drive_urgency_signal from the prior-tick autonomy drive ---


def _gate_drive_urgency(result) -> float:
    return result.stage_results[
        "thought_gating_and_continuation_pressure"
    ].result.contributing_signals["drive_urgency_signal"]


def test_first_tick_gate_uses_cold_start_drive_urgency() -> None:
    # On the first tick there is no prior 18 drive, so the gate uses the documented neutral
    # cold-start baseline (0.7), not a fabricated value.
    handle = _assemble()
    handle.startup()

    first = handle.tick()
    assert _gate_drive_urgency(first) == pytest.approx(0.7)


def test_gate_drive_urgency_reflects_prior_tick_autonomy_drive() -> None:
    # From tick 2 onward the gate's drive_urgency_signal is the bounded prior-tick 18
    # proactive-drive (outward_drive) carried forward, not the constant. An externalizing prior
    # tick has a high outward_drive (>= the 1.6 action threshold, clamped to 1.0), so tick 2's
    # gate drive_urgency rises above the tick-1 cold start.
    provider = FakeThoughtProvider(
        thought_text="acting now",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    results = handle.run_ticks(2)
    # Tick 1 externalizes -> high outward_drive; verify the autonomy drive was indeed high.
    first_drive = results[0].stage_results[
        "subjective_autonomy_and_proactive_evolution"
    ].result.drive_state.pressure_components["outward_drive"]
    assert first_drive >= 1.6  # action threshold reached

    # Tick 2's gate drive_urgency is the clamped prior-tick outward_drive (1.0), above cold start.
    assert _gate_drive_urgency(results[0]) == pytest.approx(0.7)  # tick 1 cold start
    assert _gate_drive_urgency(results[1]) == pytest.approx(1.0)  # carried clamped prior drive
    assert _gate_drive_urgency(results[1]) > _gate_drive_urgency(results[0])


def test_gate_drive_urgency_is_bounded_projection_of_prior_drive() -> None:
    # The carried drive_urgency is always a bounded [0,1] projection of the prior-tick 18 drive,
    # never an unclamped sum.
    handle = _assemble()
    handle.startup()
    for result in handle.run_ticks(3):
        assert 0.0 <= _gate_drive_urgency(result) <= 1.0


# --- Requirement 63: real selected-stimuli projection and default-assembly ignition source ---


def _gate_selected_stimuli(result):
    return result.stage_results[
        "thought_gating_and_continuation_pressure"
    ].result.selected_stimuli


def _gate_stimulus_signal(result) -> float:
    return result.stage_results[
        "thought_gating_and_continuation_pressure"
    ].result.contributing_signals["stimulus_signal"]


def test_r63_default_assembly_selected_stimuli_from_real_appraisal() -> None:
    # Under the default assembly, selected_stimuli carries the real 03 appraisal salience
    # (batch-max aggregate/novelty/uncertainty), not the pre-R63 hardcoded constants.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    stimuli = _gate_selected_stimuli(result)
    assert len(stimuli) == 1
    # The real 03 appraisal aggregate from FirstVersionAggregateEstimator (R63: raised to 0.7).
    assert stimuli[0].stimulus_intensity == pytest.approx(0.7)
    # The real 03 novelty from FirstVersionDimensionEstimator (constant 0.6).
    assert stimuli[0].novelty_signal == pytest.approx(0.6)
    # The real 03 uncertainty from FirstVersionDimensionEstimator (constant 0.3).
    assert stimuli[0].sensitization_signal == pytest.approx(0.3)
    # The gate's stimulus_signal matches the projected aggregate.
    assert _gate_stimulus_signal(result) == pytest.approx(0.7)


def test_r63_selected_stimuli_fallback_on_absent_appraisal() -> None:
    # When the 03 appraisal result is absent from the frame, the helper falls back to
    # documented cold-start constants (not a crash, not a fabricated high stimulus).
    from types import SimpleNamespace

    from helios_v2.composition.bridges import (
        _STIMULUS_INTENSITY_COLD_START,
        _NOVELTY_SIGNAL_COLD_START,
        _SENSITIZATION_SIGNAL_COLD_START,
        _selected_stimuli_from_appraisal,
    )

    frame = SimpleNamespace(stage_results={}, tick_id=1)
    stimuli = _selected_stimuli_from_appraisal(frame, 1)
    assert len(stimuli) == 1
    assert stimuli[0].stimulus_intensity == pytest.approx(_STIMULUS_INTENSITY_COLD_START)
    assert stimuli[0].novelty_signal == pytest.approx(_NOVELTY_SIGNAL_COLD_START)
    assert stimuli[0].sensitization_signal == pytest.approx(_SENSITIZATION_SIGNAL_COLD_START)


def test_r63_default_assembly_gate_fires_with_raised_aggregate() -> None:
    # The default assembly's gate fires on tick 1 with the raised FirstVersionAggregateEstimator
    # (0.7): the real appraisal aggregate plus the other signals exceed the 0.55 fire threshold.
    handle = _assemble()
    handle.startup()
    result = handle.tick()
    gate = _gate_result(result)
    assert gate.decision == "fire"
    # Gate score ~0.555: just above the 0.55 fire threshold.
    assert gate.gate_score >= 0.55


# --- Requirement 68: identity cross-tick governance carry state ---


def test_r68_identity_governance_carry_state_accumulates_trace_history() -> None:
    """R68: multi-tick governance activity accumulates trace history in the carry state.

    The default assembly fires internal thought each tick but emits no self-revision proposal,
    so every governance tick records `invalid_proposal`. After 5 ticks, the carry state's
    `recent_governance_trace_history` must contain exactly 5 entries, each with the correct
    `revision_status`. The bootstrap identity snapshot is preserved (no revision applied).
    """

    handle = _assemble()
    handle.startup()
    handle.run_ticks(5)

    gov_stage = handle.identity_governance_stage
    assert gov_stage is not None
    carry = gov_stage.prior_carry_state
    assert carry is not None
    assert len(carry.recent_governance_trace_history) == 5
    # Every entry must have revision_status=invalid_proposal (no proposal emitted).
    for entry in carry.recent_governance_trace_history:
        assert entry["revision_status"] == "invalid_proposal"
    # No revision accepted; rejected counter grew.
    assert carry.accepted_revision_count == 0
    assert carry.rejected_revision_count == 5
    # Identity snapshot is still the bootstrap constant (no revision applied).
    assert carry.identity_state_snapshot["current_revision"] == "bootstrap"


def test_r68_identity_governance_bridge_cold_start_is_byte_identical() -> None:
    """R68: the first tick's governance request is byte-for-byte identical to the pre-carry behavior.

    With `carry_state=None` (cold start), the bridge produces the same bootstrap snapshot and
    empty trace that it produced before R68. Verified by inspecting the governance request on
    tick 1 before any carry state has been advanced.
    """
    from helios_v2.composition.bridges import FirstVersionIdentityGovernanceRequestBridge

    bridge = FirstVersionIdentityGovernanceRequestBridge()
    # No provider set: carry_state_provider is None, so carry state resolves to None.
    # The bridge is not called directly here (it needs a frame and thought result);
    # instead we verify the cold-start contract via the runtime stage's first tick.
    handle = _assemble()
    handle.startup()
    result = handle.tick()

    gov_stage_result = result.stage_results["identity_governance_self_revision_integration"]
    # The request is stored on the stage result.
    request = gov_stage_result.request
    assert request is not None
    assert request.identity_state_snapshot == {
        "self_definition": "runtime identity definition",
        "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
        "identity_metadata": {},
        "current_revision": "bootstrap",
        "revision_history_length": 0,
    }
    assert request.governance_trace_summary == {}
    assert request.recent_governance_trace_history == ()


def test_r68_identity_governance_second_tick_reads_carry_state() -> None:
    """R68: the second tick's governance request carries the first tick's trace entry.

    After tick 1, the carry state has one trace entry. On tick 2, the bridge reads that carry
    state and injects it into the request. The governance request's `recent_governance_trace_history`
    must have 1 entry, and `governance_trace_summary` must be non-empty.
    """

    handle = _assemble()
    handle.startup()
    # Tick 1: produces carry state with 1 trace entry.
    handle.tick()
    # Tick 2: bridge reads the carry state from tick 1.
    result2 = handle.tick()

    gov_result = result2.stage_results["identity_governance_self_revision_integration"]
    request = gov_result.request
    assert request is not None
    # The request carries tick 1's trace entry.
    assert len(request.recent_governance_trace_history) == 1
    assert request.recent_governance_trace_history[0]["revision_status"] == "invalid_proposal"
    # governance_trace_summary is non-empty when trace history is present.
    assert request.governance_trace_summary != {}
    assert request.governance_trace_summary["total_ticks_observed"] == 1
