"""R90 memory-fidelity probe verification.

A probe test drives a real durable production-shaped run + restart and asserts the three R10/R15/R34
metrics; an integration test feeds the probe report into the R89 harness and asserts the
`memory_fidelity` axis becomes a real reconstructed axis (and stays stubbed without it). The probe is
read-only and emits no logging; this module renders the report (a test may print).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from helios_v2.composition import assemble_production_runtime, default_composition_config
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion

from r88_drift_evaluator import evaluate_drift
from r83_long_runner import LongRunConfig, run_long_run
from r89_turing_harness import (
    AVAILABLE,
    MEMORY_FIDELITY,
    STUBBED,
    evaluate_turing,
)
from r89_turing_harness.turing_harness import RECONSTRUCTED

from r90_memory_fidelity_probe import (
    MemoryFidelityConfig,
    MemoryFidelityReport,
    run_memory_fidelity_probe,
)


# --- deterministic offline runtime (mirrors the R83 CI tier) -------------------------------------


@dataclass
class _DeterministicThoughtProvider:
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "a steady internal thought for the memory-fidelity probe",
            "sufficiency": 0.9,
            "hormone_response_i_predict": {"dopamine": 0.7, "serotonin": 0.6},
        }
        return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")


def _deterministic_gateway() -> LlmGateway:
    config = default_composition_config()
    return LlmGateway(
        provider=_DeterministicThoughtProvider(),
        registry=LlmProfileRegistry(profiles=config.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _handle_factory(data_dir):
    """Build a (not-yet-started) durable runtime over a FIXED data dir, so a restart sees the store."""

    def factory():
        return assemble_production_runtime(
            data_dir=str(data_dir), gateway=_deterministic_gateway()
        )

    return factory


# --- probe metrics -------------------------------------------------------------------------------


def test_probe_measures_real_memory_loop(tmp_path) -> None:
    report = run_memory_fidelity_probe(
        _handle_factory(tmp_path), MemoryFidelityConfig(ticks=60)
    )

    assert report.crash is None, report.summary()
    assert report.ticks_completed == 60
    assert report.usable, report.summary()

    # The durable R15 -> R33 loop actually ran and persisted across the restart.
    assert report.appended > 0, report.summary()
    assert report.writeback_persistence_rate == 1.0 or report.writeback_persistence_rate > 0.9, (
        report.summary()
    )

    # All present metrics are bounded; the composed fidelity is a real bounded score.
    for metric in (report.recall_hit_rate, report.latency_score):
        if metric is not None:
            assert 0.0 <= metric <= 1.0, report.summary()
    assert 0.0 <= report.writeback_persistence_rate <= 1.0
    assert report.fidelity_score is not None
    assert 0.0 <= report.fidelity_score <= 1.0

    print("\n" + report.summary())


def test_probe_is_deterministic(tmp_path) -> None:
    a = run_memory_fidelity_probe(_handle_factory(tmp_path / "a"), MemoryFidelityConfig(ticks=30))
    b = run_memory_fidelity_probe(_handle_factory(tmp_path / "b"), MemoryFidelityConfig(ticks=30))
    assert a.appended == b.appended
    assert a.recall_possible_ticks == b.recall_possible_ticks
    assert a.recall_hit_ticks == b.recall_hit_ticks
    assert a.writeback_persistence_rate == b.writeback_persistence_rate


# --- R89 harness integration ---------------------------------------------------------------------


def _reports_for_turing(tmp_path):
    handle = assemble_production_runtime(
        data_dir=str(tmp_path), gateway=_deterministic_gateway()
    )
    handle.startup()
    long_run = run_long_run(handle, LongRunConfig(ticks=40))
    drift = evaluate_drift(long_run.evolution_samples)
    return long_run, drift


def test_usable_probe_makes_memory_fidelity_a_real_axis(tmp_path) -> None:
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    probe = run_memory_fidelity_probe(
        _handle_factory(tmp_path / "probe"), MemoryFidelityConfig(ticks=40)
    )
    assert probe.usable, probe.summary()

    verdict = evaluate_turing(long_run, drift, memory_fidelity_probe=probe)
    axis = verdict.axis_scores[MEMORY_FIDELITY]
    assert axis.availability == AVAILABLE, verdict.summary()
    assert axis.judge_track == RECONSTRUCTED
    assert axis.score == probe.fidelity_score
    assert "R90 memory-fidelity probe" in axis.provenance
    assert MEMORY_FIDELITY not in verdict.stubbed_axes


def test_absent_probe_keeps_memory_fidelity_stubbed(tmp_path) -> None:
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    verdict = evaluate_turing(long_run, drift)  # no probe -> R89 stub path preserved
    assert verdict.axis_scores[MEMORY_FIDELITY].availability == STUBBED
    assert MEMORY_FIDELITY in verdict.stubbed_axes


def test_unusable_probe_keeps_memory_fidelity_stubbed(tmp_path) -> None:
    long_run, drift = _reports_for_turing(tmp_path / "turing")
    unusable = MemoryFidelityReport(ticks_requested=10, ticks_completed=0, reason="empty_report")
    assert not unusable.usable
    verdict = evaluate_turing(long_run, drift, memory_fidelity_probe=unusable)
    assert verdict.axis_scores[MEMORY_FIDELITY].availability == STUBBED


# --- robustness ----------------------------------------------------------------------------------


def test_crashing_factory_is_not_usable() -> None:
    def boom():
        raise RuntimeError("no runtime here")

    report = run_memory_fidelity_probe(boom, MemoryFidelityConfig(ticks=5))
    assert report.usable is False
    assert report.reason is not None
    assert report.fidelity_score is None or report.fidelity_score >= 0.0
