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
    # The arousal-driven difference is real (not a constant) and moves the gate score with it.
    assert first_gate.result.gate_score >= second_gate.result.gate_score


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
    # No semantic memory -> the first-version constant aggregate estimator.
    assert _appraisal_aggregate(result) == pytest.approx(0.4)


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


def test_low_salience_first_tick_persists_no_affect_memory_but_writeback_co_persists() -> None:
    # The very first tick's feeling has not yet built up momentum, so the salience gate is below
    # threshold and no affect-memory is persisted; the 15 continuity record still persists.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(experience_store=store, embedding_gateway=_embedding_gateway())
    handle.startup()

    handle.tick()

    assert _affect_memory_records(store) == []
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
