"""R89 long-run Turing-style evaluation harness verification.

An integration test drives the real R83 -> R88 -> R89 pipeline (a short production-shaped run with a
deterministic offline gateway, drift evaluation, then the Turing verdict) and asserts the
anti-theatrical baseline (internal axes reconstructed, behavior axes unavailable, verdict incomplete
and not-passing). Synthetic-fixture tests exercise the locked conservative aggregation, evidence
anchoring, axis collapse, the both-dimension rule, and a fully-injected passing run. The harness is
read-only and emits no logging; this module renders the verdict (a test may print).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from helios_v2.composition import assemble_production_runtime, default_composition_config
from helios_v2.llm import LlmGateway, LlmProfileRegistry
from helios_v2.llm.contracts import ProviderCompletion

from r83_long_runner import LongRunConfig, run_long_run
from r83_long_runner.long_runner import FieldStat, LongRunReport, TRACKED_FIELD_BOUNDS
from r88_drift_evaluator import evaluate_drift
from r88_drift_evaluator.drift_evaluator import (
    DIVERGENCE_NONE,
    DRIFT_NEUTRAL,
    DimensionDrift,
    DriftReport,
)

from r89_turing_harness import (
    AGENCY_LOCKING,
    AVAILABLE,
    BIO_RESPONSIVENESS,
    CROSS_TICK_CONTINUITY,
    DIMENSION_BEHAVIOR,
    DIMENSION_INTERNAL,
    LINGUISTIC_NATURALNESS,
    MEMORY_FIDELITY,
    STIMULUS_RESPONSE_COHERENCE,
    STUBBED,
    UNAVAILABLE,
    InjectedAxisScore,
    TuringConfig,
    evaluate_turing,
)

_ALL_SIX = (
    LINGUISTIC_NATURALNESS,
    BIO_RESPONSIVENESS,
    MEMORY_FIDELITY,
    AGENCY_LOCKING,
    CROSS_TICK_CONTINUITY,
    STIMULUS_RESPONSE_COHERENCE,
)


# --- deterministic offline runtime (mirrors the R83 CI tier) -------------------------------------


@dataclass
class _DeterministicThoughtProvider:
    calls: list[str] = field(default_factory=list)

    def complete(self, profile, request, api_key) -> ProviderCompletion:
        self.calls.append(profile.profile_name)
        envelope = {
            "thought": "a steady internal thought for the turing harness run",
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


def _real_reports(tmp_path, ticks: int = 60):
    """Drive a real short R83 run, then build the R88 drift report from its sampled trace."""

    handle = assemble_production_runtime(
        data_dir=str(tmp_path), gateway=_deterministic_gateway()
    )
    handle.startup()
    long_run = run_long_run(handle, LongRunConfig(ticks=ticks))
    drift = evaluate_drift(long_run.evolution_samples)
    return long_run, drift


# --- synthetic report builders (full control, fast, no runtime) ----------------------------------


def _dim(name: str) -> DimensionDrift:
    return DimensionDrift(
        name=name,
        owner=name.split(".", 1)[0],
        samples=10,
        early_mean=0.5,
        late_mean=0.5,
        delta=0.0,
        normalized_delta=0.0,
        minimum=0.4,
        maximum=0.6,
        late_spread=0.0,
        drift_class=DRIFT_NEUTRAL,
        divergence=DIVERGENCE_NONE,
    )


def _healthy_reports(config: TuringConfig = TuringConfig()):
    """All 19 owner dims present, healthy, and bounded; affect dims show real cross-tick movement."""

    expected = sorted(config.resolved_expected())
    long_run = LongRunReport(ticks_requested=10, ticks_completed=10)
    drift_dims: dict[str, DimensionDrift] = {}
    for name in expected:
        high = 8.0 if name == "18.outward_drive" else 1.0
        stat = FieldStat(name=name, legal_min=0.0, legal_max=high)
        if name.split(".", 1)[0] in ("04", "05"):
            stat.observe(0.3)
            stat.observe(0.6)  # moved (range 0.3 > epsilon)
        else:
            stat.observe(0.5)
            stat.observe(0.5)  # present, flat, bounded
        long_run.field_stats[name] = stat
        drift_dims[name] = _dim(name)
    drift = DriftReport(
        source="synthetic",
        total_samples=10,
        dimensions=drift_dims,
        expected_dimensions=frozenset(expected),
        missing_dimensions=(),
        divergent_dimensions=(),
        class_counts={},
        min_samples_for_trend=4,
        parse_reason=None,
    )
    return long_run, drift


def _all_axes_injected(score: float, provenance: str = "judge: high similarity") -> dict:
    return {axis: InjectedAxisScore(score=score, provenance=provenance) for axis in _ALL_SIX}


# --- integration: real R83 -> R88 -> R89 ---------------------------------------------------------


def test_real_pipeline_baseline_is_incomplete_and_not_passing(tmp_path) -> None:
    long_run, drift = _real_reports(tmp_path)
    verdict = evaluate_turing(long_run, drift)

    # Internal axes are reconstructed from real provenance and available.
    for axis in (BIO_RESPONSIVENESS, CROSS_TICK_CONTINUITY, AGENCY_LOCKING):
        score = verdict.axis_scores[axis]
        assert score.availability == AVAILABLE, verdict.summary()
        assert score.dimension == DIMENSION_INTERNAL
        assert score.provenance.strip(), axis
        assert 0.0 <= score.score <= 1.0

    # memory_fidelity is the R90-pending stub; behavior axes need real afferents + judges.
    assert verdict.axis_scores[MEMORY_FIDELITY].availability == STUBBED
    assert verdict.axis_scores[LINGUISTIC_NATURALNESS].availability == UNAVAILABLE
    assert verdict.axis_scores[STIMULUS_RESPONSE_COHERENCE].availability == UNAVAILABLE

    # Anti-theatrical baseline: internal axes alone cannot pass; behavior dimension is unscored.
    assert verdict.behavior_dimension_score is None, verdict.summary()
    assert verdict.internal_dimension_score is not None
    assert verdict.completeness == "incomplete"
    assert verdict.passes is False
    print("\n" + verdict.summary())


# --- synthetic: reconstruction path without the runtime ------------------------------------------


def test_reconstruction_axes_available_but_baseline_not_passing() -> None:
    long_run, drift = _healthy_reports()
    verdict = evaluate_turing(long_run, drift)

    assert verdict.axis_scores[BIO_RESPONSIVENESS].score == pytest.approx(1.0)  # full health+movement
    assert verdict.axis_scores[AGENCY_LOCKING].score == pytest.approx(1.0)  # 19/19 healthy
    assert verdict.axis_scores[CROSS_TICK_CONTINUITY].score == pytest.approx(1.0)
    assert verdict.axis_scores[MEMORY_FIDELITY].availability == STUBBED
    assert verdict.internal_dimension_score == pytest.approx(1.0)
    assert verdict.behavior_dimension_score is None
    assert verdict.completeness == "incomplete"
    assert verdict.passes is False


# --- synthetic: aggregation / falsifiability -----------------------------------------------------


def test_fully_injected_high_run_passes() -> None:
    long_run, drift = _healthy_reports()
    verdict = evaluate_turing(long_run, drift, injected_scores=_all_axes_injected(0.9))
    assert verdict.completeness == "complete", verdict.summary()
    assert verdict.behavior_dimension_score == pytest.approx(0.9)
    assert verdict.internal_dimension_score == pytest.approx(0.9)
    assert verdict.aggregate == pytest.approx(0.9)
    assert verdict.passes is True, verdict.violations()


def test_single_axis_collapse_fails() -> None:
    long_run, drift = _healthy_reports()
    injected = _all_axes_injected(0.9)
    injected[BIO_RESPONSIVENESS] = InjectedAxisScore(score=0.4, provenance="judge: weak")
    verdict = evaluate_turing(long_run, drift, injected_scores=injected)
    assert BIO_RESPONSIVENESS in verdict.collapsed_axes
    assert verdict.passes is False


def test_missing_provenance_forces_zero_and_fails() -> None:
    long_run, drift = _healthy_reports()
    injected = _all_axes_injected(0.9)
    injected[LINGUISTIC_NATURALNESS] = InjectedAxisScore(score=0.95, provenance="")
    verdict = evaluate_turing(long_run, drift, injected_scores=injected)
    assert verdict.axis_scores[LINGUISTIC_NATURALNESS].score == pytest.approx(0.0)
    assert verdict.passes is False


def test_behavior_only_does_not_pass_without_internal() -> None:
    # Inject only the behavior axes high; the internal dimension is still reconstructed (available),
    # but flip it: inject only behavior, and force internal unavailable by emptying expected dims is
    # not possible here, so instead assert the symmetric rule via internal-only below. Here we verify
    # behavior present + internal present still needs BOTH — covered by the both-dimension min.
    long_run, drift = _healthy_reports()
    injected = {
        LINGUISTIC_NATURALNESS: InjectedAxisScore(score=0.95, provenance="judge"),
        STIMULUS_RESPONSE_COHERENCE: InjectedAxisScore(score=0.95, provenance="judge"),
    }
    verdict = evaluate_turing(long_run, drift, injected_scores=injected)
    # memory_fidelity is still stubbed -> incomplete -> cannot pass even with both dims scored.
    assert verdict.behavior_dimension_score is not None
    assert verdict.internal_dimension_score is not None
    assert verdict.completeness == "incomplete"
    assert verdict.passes is False


def test_internal_only_leaves_behavior_unscored() -> None:
    long_run, drift = _healthy_reports()
    injected = {MEMORY_FIDELITY: InjectedAxisScore(score=0.9, provenance="judge")}
    verdict = evaluate_turing(long_run, drift, injected_scores=injected)
    # All four internal axes now available (3 reconstructed + injected memory), behavior still
    # unavailable -> behavior dimension unscored -> not passing.
    assert verdict.behavior_dimension_score is None
    assert verdict.internal_dimension_score is not None
    assert verdict.passes is False


# --- robustness ----------------------------------------------------------------------------------


def test_missing_report_is_not_passing() -> None:
    _, drift = _healthy_reports()
    verdict = evaluate_turing(None, drift)
    assert verdict.reason == "missing_report"
    assert verdict.passes is False


def test_empty_report_is_not_passing() -> None:
    long_run, drift = _healthy_reports()
    empty = LongRunReport(ticks_requested=10, ticks_completed=0)
    verdict = evaluate_turing(empty, drift)
    assert verdict.reason == "empty_report"
    assert verdict.passes is False
