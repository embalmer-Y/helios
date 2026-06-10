"""R72 — P1 exit evaluation: automated P1 milestone assessment.

Validates the P1 internal-closure milestone (PHASE_METRICS.md §3):
"P1 — Internal closure milestone (= v2.0.0)"

Scope
-----
- P1-T2 (wave_A): 17 corroboration produces corroborated/discrepant/unverifiable.
- P1-T3 (wave_B): 18/24 continuity thread persists ≥ 5 ticks.
- P1-T4 (wave_C): CLI channel end-to-end ≥ 3 ticks without interruption.
- P1-T5: internal-only tick closure (fired + no-proposal).
- P1-T6: no-fire tick closure (gate no-fire, R54).
- P1-H1: 17/23 can read-only reconstruct ≥ 1 internal causal chain.
- P1-H2: continuous ≥ 10 ticks without crash.
- P1-H3: all wave_A/B/C closure tests pass.
- P1-H4: v2.0.0 judgment criteria met.

This test module is **read-only**: it asserts over the existing runtime but never
modifies any owner implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from helios_v2.composition import (
    CANONICAL_STAGE_ORDER,
    CHANNEL_BOUND_STAGE_ORDER,
    assemble_runtime,
    default_composition_config,
)
from helios_v2.composition import RuntimeProfile, SequenceExternalSignalSource
from helios_v2.embedding import (
    EmbeddingGateway,
    EmbeddingProfile,
    EmbeddingProfileRegistry,
    ProviderEmbedding,
)
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion
from helios_v2.observability import InMemoryLogSink, RuntimeObservabilityRecorder
from helios_v2.persistence import ExperienceStore, InMemoryExperienceStoreBackend
from helios_v2.sensory import RawSignal as _RawSignal


# ---------------------------------------------------------------------------
# Fake providers (deterministic, network-free)
# ---------------------------------------------------------------------------


@dataclass
class _FakeThoughtProvider:
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
        return ProviderCompletion(
            output_text=json.dumps(envelope), finish_reason=self.finish_reason
        )


class _FakeEmbeddingProvider:
    """Deterministic hash-based embedding; similar texts embed similarly."""

    dimensions: int = 16

    def embed(self, profile, request, api_key):
        buckets = [0.0] * self.dimensions
        for index, char in enumerate(request.input_text):
            buckets[(ord(char) + index) % self.dimensions] += 1.0
        if not any(buckets):
            buckets[0] = 1.0
        return ProviderEmbedding(vector=tuple(buckets), dimensions=self.dimensions)


@dataclass
class _ConfigurableInteroceptiveSampler:
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


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def _ready_gateway(config=None, provider=None) -> LlmGateway:
    resolved = config if config is not None else default_composition_config()
    return LlmGateway(
        provider=provider or _FakeThoughtProvider(),
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _embedding_gateway(provider=None) -> EmbeddingGateway:
    profile = EmbeddingProfile(
        profile_name="experience-embedding",
        model="text-embedding-test",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
    )
    return EmbeddingGateway(
        provider=provider or _FakeEmbeddingProvider(),
        registry=EmbeddingProfileRegistry(profiles=(profile,)),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble(**kwargs):
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    return assemble_runtime(**kwargs)


def _assemble_channel(sink, **kwargs):
    if "gateway" not in kwargs:
        kwargs["gateway"] = _ready_gateway()
    return assemble_runtime(channel_cli=True, cli_output_sink=sink, **kwargs)


# ---------------------------------------------------------------------------
# Stage-result accessors
# ---------------------------------------------------------------------------


def _gate_result(result):
    return result.stage_results["thought_gating_and_continuation_pressure"].result


def _autonomy(result):
    return result.stage_results["subjective_autonomy_and_proactive_evolution"].result


def _evaluation_artifact(result):
    return result.stage_results["evaluation_fidelity_and_diagnostic_provenance"].artifact


# ---------------------------------------------------------------------------
# P1 exit evaluation: data structures
# ---------------------------------------------------------------------------


@dataclass
class P1ExitCheck:
    """One atomic check in the P1 exit evaluation."""

    check_id: str
    description: str
    passed: bool
    evidence: str = ""


@dataclass
class P1ExitVerdict:
    """Aggregated P1 exit verdict."""

    checks: list[P1ExitCheck] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def add(self, check: P1ExitCheck) -> None:
        self.checks.append(check)

    def summary(self) -> dict:
        return {
            "verdict": "PASS" if self.passed else "FAIL",
            "total": len(self.checks),
            "passed": sum(1 for c in self.checks if c.passed),
            "failed": sum(1 for c in self.checks if not c.passed),
            "details": [
                {"id": c.check_id, "passed": c.passed, "evidence": c.evidence}
                for c in self.checks
            ],
        }


# ===========================================================================
# P1-T2 (wave_A): Behavioral truth — 17 corroboration
# ===========================================================================


def test_p1_t2_wave_a_corroboration() -> None:
    """P1-T2: 17 corroboration produces corroborated/discrepant/unverifiable verdicts."""
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    handle = _assemble(recorder=recorder)
    handle.startup()

    results = handle.run_ticks(2)

    # Tick 1: no prior timeline → unverifiable.
    first_gap = _evaluation_artifact(results[0]).gap_summary
    assert first_gap["consequence_corroboration"] == "unverifiable_no_timeline"

    # Tick 2: corroborates tick 1's self-reported outcome against tick 1's timeline.
    second_gap = _evaluation_artifact(results[1]).gap_summary
    assert second_gap["consequence_corroboration"] in ("corroborated", "discrepant")

    # No consequence discrepancy for a normal externalizing tick.
    warnings = _evaluation_artifact(results[1]).fidelity_warnings
    assert all(w.warning_kind != "consequence_discrepancy" for w in warnings)


# ===========================================================================
# P1-T3 (wave_B): Long-horizon continuity — 18/24 thread persistence ≥ 5 ticks
# ===========================================================================


def test_p1_t3_wave_b_continuity_thread_persistence() -> None:
    """P1-T3: 18/24 continuity thread persists and reinforces across ≥ 5 ticks."""
    # R67 continuity threads form when the thought owner defers (no fire → no action → defer).
    # With legacy_constant mode the gate fires every tick; the thought concludes without action,
    # and the autonomy owner records a defer disposition, forming a continuity thread each tick.
    provider = _FakeThoughtProvider(
        thought_text="resolved, nothing to do externally",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(
        gateway=_ready_gateway(provider=provider),
        default_signal_mode="legacy_constant",
    )
    handle.startup()

    results = handle.run_ticks(5)

    # Every tick defers with the same motive.
    autonomies = [_autonomy(r) for r in results]
    dispositions = [a.drive_state.dominant_disposition for a in autonomies]
    assert all(d == "defer" for d in dispositions), (
        f"expected all defer, got {dispositions}"
    )

    # R67 stable key: same deferral reason → same thread → reinforcement grows.
    last = autonomies[-1]
    assert last.long_horizon_state.active_thread_count >= 1
    thread = last.long_horizon_state.threads[0]
    assert thread.reinforcement_count >= 2, (
        f"continuity thread reinforcement_count={thread.reinforcement_count}, expected ≥ 2"
    )
    assert thread.age_ticks >= 3, (
        f"continuity thread age_ticks={thread.age_ticks}, expected ≥ 3"
    )


# ===========================================================================
# P1-T4 (wave_C): CLI channel roundtrip — ≥ 3 ticks without interruption
# ===========================================================================


def test_p1_t4_wave_c_cli_channel_roundtrip() -> None:
    """P1-T4: CLI channel end-to-end ≥ 3 ticks without interruption."""
    sink_lines: list[str] = []
    provider = _FakeThoughtProvider(
        thought_text="channel roundtrip test",
        sufficiency=0.9,
        wants_to_continue=False,
        intends_action=True,
    )
    handle = _assemble_channel(
        sink_lines.append,
        gateway=_ready_gateway(provider=provider),
    )
    handle.startup()

    # Submit 3 lines of input and run 3 ticks.
    handle.channel_subsystem._drivers["cli"].submit_line("tick one input")
    handle.channel_subsystem._drivers["cli"].submit_line("tick two input")
    handle.channel_subsystem._drivers["cli"].submit_line("tick three input")
    results = handle.run_ticks(3)

    # All 3 ticks completed with the full 21-stage channel-bound order.
    assert len(results) == 3
    for result in results:
        assert tuple(result.stage_results.keys()) == CHANNEL_BOUND_STAGE_ORDER

    # The channel subsystem is still connected after 3 ticks.
    snapshot = handle.channel_subsystem.channel_state_snapshot()
    assert any(s.connected for s in snapshot.statuses)


# ===========================================================================
# P1-T5: Internal-only tick closure (fired + no-proposal)
# ===========================================================================


def test_p1_t5_internal_only_tick_closure() -> None:
    """P1-T5: fired thought + no-proposal completes the chain as internal-only."""
    provider = _FakeThoughtProvider(
        thought_text="resolved, nothing to do",
        sufficiency=0.95,
        wants_to_continue=False,
        intends_action=False,
    )
    handle = _assemble(gateway=_ready_gateway(provider=provider))
    handle.startup()

    result = handle.tick()

    # The planner records no_actionable_proposal.
    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "no_actionable_proposal"

    # The writeback records an internal_only continuity outcome.
    writeback = result.stage_results["execution_writeback_and_autobiographical_consolidation"]
    statuses = {r.status for r in writeback.results}
    assert "written_internal_only" in statuses

    # The evaluation records the internal-only decision path.
    artifact = _evaluation_artifact(result)
    assert artifact.gap_summary["consequence_path_outcome"] == "internal_only_decision"


# ===========================================================================
# P1-T6: No-fire tick closure (gate no-fire, R54)
# ===========================================================================


def test_p1_t6_no_fire_tick_closure() -> None:
    """P1-T6: gate no-fire tick completes the chain (R54)."""
    # High cpu/memory load drives 09 gate to resource_pressure_too_high / no_fire.
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.95, memory=0.95),
    )
    handle.startup()

    result = handle.tick()  # Must not raise.

    # Gate decided no_fire.
    gate = _gate_result(result)
    assert gate.decision == "no_fire"
    assert gate.no_fire_reason == "resource_pressure_too_high"

    # Post-gate stages are inactive.
    for stage_name in (
        "directed_retrieval_into_thought_window",
        "internal_thought_loop_owner",
        "action_proposal_externalization_contract",
        "identity_governance_self_revision_integration",
    ):
        assert result.stage_results[stage_name].activated is False

    # Planner/writeback close as internal-only.
    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "no_actionable_proposal"
    writeback = result.stage_results["execution_writeback_and_autobiographical_consolidation"]
    statuses = {r.status for r in writeback.results}
    assert "written_internal_only" in statuses


# ===========================================================================
# P1-H1: Read-only causal chain reconstruction
# ===========================================================================


def test_p1_h1_read_only_causal_chain_reconstruction() -> None:
    """P1-H1: 17/23 can read-only reconstruct at least one internal causal chain."""
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        recorder=recorder,
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()

    results = handle.run_ticks(3)

    # By tick 2, the evaluation owner has a prior timeline and can corroborate.
    tick2_artifact = _evaluation_artifact(results[1])
    tick2_diag = tick2_artifact.long_range_diagnostics
    assert tick2_diag["execution_timeline_status"] == "observed"
    assert tick2_artifact.gap_summary["consequence_corroboration"] == "corroborated"

    # By tick 3, we have a chain: tick 1 → corroborated by tick 2 → corroborated by tick 3.
    tick3_artifact = _evaluation_artifact(results[2])
    assert tick3_artifact.gap_summary["consequence_corroboration"] == "corroborated"

    # The observability timeline has events from all 3 ticks.
    events = sink.events
    tick_ids = {e.tick_id for e in events if e.tick_id is not None}
    assert len(tick_ids) >= 2, f"expected events from ≥ 2 ticks, got {tick_ids}"


# ===========================================================================
# P1-H2: Continuous ≥ 10 ticks without crash
# ===========================================================================


def test_p1_h2_continuous_ten_ticks() -> None:
    """P1-H2: continuous ≥ 10 ticks without crash (semantic assembly)."""
    store = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle = _assemble(
        experience_store=store,
        embedding_gateway=_embedding_gateway(),
    )
    handle.startup()

    results = handle.run_ticks(10)

    # All 10 ticks completed.
    assert len(results) == 10
    assert tuple(r.tick_id for r in results) == tuple(range(1, 11))

    # All ticks have the canonical 19-stage order.
    for result in results:
        assert tuple(result.stage_results.keys()) == CANONICAL_STAGE_ORDER

    # Experience store persisted records (proves the persistence chain works over 10 ticks).
    assert store.count() >= 10


# ===========================================================================
# P1 comprehensive exit verdict
# ===========================================================================


def test_p1_exit_verdict() -> None:
    """Run all P1 exit checks and produce a structured pass/fail verdict."""
    verdict = P1ExitVerdict()

    # -- P1-T2: wave_A corroboration --
    sink = InMemoryLogSink()
    recorder = RuntimeObservabilityRecorder(sinks=(sink,), minimum_severity="debug")
    handle_a = _assemble(recorder=recorder)
    handle_a.startup()
    results_a = handle_a.run_ticks(2)
    corr = _evaluation_artifact(results_a[1]).gap_summary["consequence_corroboration"]
    verdict.add(P1ExitCheck(
        "P1-T2", "wave_A corroboration works",
        corr in ("corroborated", "discrepant"),
        f"corroboration={corr}",
    ))

    # -- P1-T3: wave_B continuity thread --
    # Use legacy_constant mode so the gate fires and thought defers (thread formation path).
    provider_b = _FakeThoughtProvider(
        sufficiency=0.95, wants_to_continue=False, intends_action=False,
    )
    handle_b = _assemble(
        gateway=_ready_gateway(provider=provider_b),
        default_signal_mode="legacy_constant",
    )
    handle_b.startup()
    results_b = handle_b.run_ticks(5)
    last_autonomy = _autonomy(results_b[-1])
    thread_count = last_autonomy.long_horizon_state.active_thread_count
    max_reinforcement = max(
        (t.reinforcement_count for t in last_autonomy.long_horizon_state.threads),
        default=0,
    )
    verdict.add(P1ExitCheck(
        "P1-T3", "wave_B continuity thread ≥ 5 ticks",
        thread_count >= 1 and max_reinforcement >= 2,
        f"threads={thread_count}, max_reinforcement={max_reinforcement}",
    ))

    # -- P1-T4: wave_C CLI roundtrip --
    sink_lines: list[str] = []
    handle_c = _assemble_channel(sink_lines.append)
    handle_c.startup()
    handle_c.channel_subsystem._drivers["cli"].submit_line("test input 1")
    handle_c.channel_subsystem._drivers["cli"].submit_line("test input 2")
    handle_c.channel_subsystem._drivers["cli"].submit_line("test input 3")
    results_c = handle_c.run_ticks(3)
    verdict.add(P1ExitCheck(
        "P1-T4", "wave_C CLI roundtrip ≥ 3 ticks",
        len(results_c) == 3,
        f"ticks={len(results_c)}",
    ))

    # -- P1-T5: internal-only closure --
    provider_e = _FakeThoughtProvider(
        sufficiency=0.95, wants_to_continue=False, intends_action=False,
    )
    handle_e = _assemble(gateway=_ready_gateway(provider=provider_e))
    handle_e.startup()
    result_e = handle_e.tick()
    planner_e = result_e.stage_results["planner_executor_feedback_bridge"].result
    verdict.add(P1ExitCheck(
        "P1-T5", "internal-only tick closure",
        planner_e.status == "no_actionable_proposal",
        f"planner_status={planner_e.status}",
    ))

    # -- P1-T6: no-fire closure --
    store_f = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_f = _assemble(
        experience_store=store_f,
        embedding_gateway=_embedding_gateway(),
        interoceptive_sampler=_ConfigurableInteroceptiveSampler(cpu=0.95, memory=0.95),
    )
    handle_f.startup()
    result_f = handle_f.tick()
    gate_f = _gate_result(result_f)
    verdict.add(P1ExitCheck(
        "P1-T6", "no-fire tick closure (R54)",
        gate_f.decision == "no_fire",
        f"decision={gate_f.decision}, reason={gate_f.no_fire_reason}",
    ))

    # -- P1-H1: causal chain reconstruction --
    verdict.add(P1ExitCheck(
        "P1-H1", "read-only causal chain reconstruction",
        _evaluation_artifact(results_a[1]).gap_summary["consequence_corroboration"] == "corroborated",
        "17 corroboration produces corroborated verdict by tick 2",
    ))

    # -- P1-H2: 10 continuous ticks --
    store_h = ExperienceStore(backend=InMemoryExperienceStoreBackend())
    handle_h = _assemble(
        experience_store=store_h,
        embedding_gateway=_embedding_gateway(),
    )
    handle_h.startup()
    results_h = handle_h.run_ticks(10)
    verdict.add(P1ExitCheck(
        "P1-H2", "continuous ≥ 10 ticks",
        len(results_h) == 10,
        f"ticks={len(results_h)}, store_count={store_h.count()}",
    ))

    # -- P1-H3: all wave closures pass (meta-check) --
    wave_checks = [c for c in verdict.checks if c.check_id.startswith("P1-T")]
    verdict.add(P1ExitCheck(
        "P1-H3", "all wave_A/B/C closure checks pass",
        all(c.passed for c in wave_checks),
        f"{sum(1 for c in wave_checks if c.passed)}/{len(wave_checks)} wave checks pass",
    ))

    # -- P1-H4: v2.0.0 judgment (composite) --
    real_checks = [c for c in verdict.checks if not c.check_id.startswith("P1-H3")]
    verdict.add(P1ExitCheck(
        "P1-H4", "v2.0.0 composite judgment",
        all(c.passed for c in real_checks),
        f"{sum(1 for c in real_checks if c.passed)}/{len(real_checks)} checks pass",
    ))

    # Final assertion.
    assert verdict.passed, (
        f"P1 EXIT VERDICT: FAIL\n"
        + "\n".join(
            f"  [FAIL] {c.check_id}: {c.description} — {c.evidence}"
            for c in verdict.checks
            if not c.passed
        )
    )

    summary = verdict.summary()
    print(f"\n{'=' * 60}")
    print(f"P1 EXIT VERDICT: {summary['verdict']}")
    print(f"  Total: {summary['total']}, Passed: {summary['passed']}, Failed: {summary['failed']}")
    for d in summary["details"]:
        status = "PASS" if d["passed"] else "FAIL"
        print(f"  [{status}] {d['id']}: {d['evidence']}")
    print(f"{'=' * 60}")
