"""R83 long-run stability + owner-boundedness verification.

Three tiers:
  - CI tier (`test_r83_ci_long_run`): a fast, repeatable, network-free run on the R82
    production-shaped assembly (SQLite store + R42 checkpoint + semantic chain) driven by a
    deterministic fake LLM gateway. Locked at `_CI_TICKS` (override via `HELIOS_R83_CI_TICKS`).
  - Opt-in long tier (`test_r83_long_run_opt_in`): `_LONG_TICKS` ticks; manual only, skipped
    unless `HELIOS_R83_LONG_RUN` is set. Not in CI.
  - Opt-in real-LLM tier (`test_r83_real_llm_long_run`): a short run against a real LLM gateway;
    skipped unless `HELIOS_R83_REAL_LLM` is set. Not in CI.

The harness is read-only and emits no logging; this module renders the report (a test may print).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_production_runtime, default_composition_config
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion

from r83_long_runner import LongRunConfig, run_long_run


# Locked CI tick count: a repeatable network-free regression smoke that stays fast in CI. The hard
# G0 gate (production scale, >= 100k ticks) is the opt-in long tier, not the CI tier. NOTE (R83
# finding): per-tick cost grows roughly linearly with the stored-memory size because `03` novelty /
# uncertainty / threat-reward and `10`/`06` retrieval each run a naive O(n) cosine over the store
# (R34 deferred an ANN index), so the run is ~O(n^2); the CI tier is deliberately bounded and the
# 100k gate is run manually.
_CI_TICKS = int(os.environ.get("HELIOS_R83_CI_TICKS", "150"))
_LONG_TICKS = int(os.environ.get("HELIOS_R83_LONG_TICKS", "100000"))


@dataclass
class _DeterministicThoughtProvider:
    """Network-free LLM provider returning a fixed structured envelope every tick.

    Includes a fixed `hormone_response_i_predict` so the long run also exercises the R81
    corroboration bias on the `04` state (the corroborated levels must stay bounded too).
    """

    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "a steady internal thought for the long run",
            "sufficiency": 0.9,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": True, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
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


def _run(tmp_path, ticks: int) -> "object":
    handle = assemble_production_runtime(
        data_dir=str(tmp_path), gateway=_deterministic_gateway()
    )
    handle.startup()
    return run_long_run(handle, LongRunConfig(ticks=ticks))


def test_r83_ci_long_run(tmp_path) -> None:
    report = _run(tmp_path, _CI_TICKS)

    # G0: the runtime completed every tick with no crash / uncaught exception.
    assert report.crash is None, report.crash
    assert report.ticks_completed == _CI_TICKS

    # G1: every tracked owner field stayed bounded, finite, and non-divergent over the whole run.
    assert report.boundedness_ok, report.summary()

    # Memory stayed bounded (no in-process leak/divergence over the run).
    assert report.memory_ok, report.summary()

    # The durable store genuinely accumulated experience across the run (persistence is live).
    assert report.store_count_end > report.store_count_start

    # The core affect/gating owners were actually observed every completed tick (not skipped).
    for name in ("04.dopamine", "05.valence", "09.gate_score", "18.outward_drive"):
        assert report.field_stats[name].observations == _CI_TICKS, name

    # Render the report so the CI log carries the evidence (print is allowed in tests, not in src).
    print("\n" + report.summary())


def test_r83_run_is_repeatable(tmp_path) -> None:
    # Determinism: two fresh runs on separate data dirs produce identical owner-field min/max.
    report_a = _run(tmp_path / "a", 25)
    report_b = _run(tmp_path / "b", 25)
    for name in report_a.field_stats:
        stat_a = report_a.field_stats[name]
        stat_b = report_b.field_stats[name]
        assert stat_a.minimum == pytest.approx(stat_b.minimum), name
        assert stat_a.maximum == pytest.approx(stat_b.maximum), name


@pytest.mark.skipif(
    not os.environ.get("HELIOS_R83_LONG_RUN"),
    reason="opt-in production-scale long run; set HELIOS_R83_LONG_RUN=1 to enable (not in CI)",
)
def test_r83_long_run_opt_in(tmp_path) -> None:
    report = _run(tmp_path, _LONG_TICKS)
    print("\n" + report.summary())
    assert report.verdict_ok, report.violations()


@pytest.mark.skipif(
    not os.environ.get("HELIOS_R83_REAL_LLM"),
    reason="opt-in real-LLM long run; set HELIOS_R83_REAL_LLM=1 + LLM credentials (not in CI)",
)
def test_r83_real_llm_long_run(tmp_path) -> None:
    # Real LLM gateway from environment credentials (OPENAI_API_KEY etc.). Network-bound.
    ticks = int(os.environ.get("HELIOS_R83_REAL_LLM_TICKS", "25"))
    handle = assemble_production_runtime(data_dir=str(tmp_path))  # default real gateway from env
    handle.startup()
    report = run_long_run(handle, LongRunConfig(ticks=ticks))
    print("\n" + report.summary())
    assert report.crash is None, report.crash
    assert report.boundedness_ok, report.summary()
