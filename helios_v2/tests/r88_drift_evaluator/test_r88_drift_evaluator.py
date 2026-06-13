"""R88 behavioral-drift evaluator verification.

Synthetic fixtures exercise each drift class, the deadband boundary, and the saturation-toward-bound
divergence flags; a committed-baseline-trace test runs the evaluator against the real
`logs/r83/semantic_600.jsonl`; robustness tests cover empty and malformed traces. The evaluator is
read-only and emits no logging; this module renders the report (a test may print).
"""

from __future__ import annotations

import os

import pytest

from r88_drift_evaluator import (
    DIM_UNAVAILABLE,
    DRIFT_NEGATIVE,
    DRIFT_NEUTRAL,
    DRIFT_POSITIVE,
    DriftConfig,
    evaluate_drift,
    evaluate_trace_file,
    load_samples,
)


_SEMANTIC_600 = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs",
    "r83",
    "semantic_600.jsonl",
)


def _samples(dim: str, values: list[float]) -> list[dict]:
    """Build a minimal R83-shaped sample list carrying one owner dimension over `values`."""

    return [{"tick": float(i), dim: v} for i, v in enumerate(values)]


# --- synthetic-fixture drift classes -------------------------------------------------------------


def test_rising_dimension_is_positive() -> None:
    # `04.dopamine` ramps 0.1 -> 0.85 (well below the 0.98 saturation edge): a non-divergent rise.
    values = [0.1 + (0.75 * i / 19) for i in range(20)]
    report = evaluate_drift(
        _samples("04.dopamine", values),
        DriftConfig(expected_dimensions=frozenset({"04.dopamine"})),
    )
    dim = report.dimensions["04.dopamine"]
    assert dim.drift_class == DRIFT_POSITIVE, report.summary()
    assert dim.divergence == "none"
    assert report.analysis_ok, report.violations()


def test_falling_dimension_is_negative() -> None:
    # 0.9 -> 0.15 (above the 0.02 low saturation edge): a non-divergent fall.
    values = [0.9 - (0.75 * i / 19) for i in range(20)]
    report = evaluate_drift(
        _samples("04.dopamine", values),
        DriftConfig(expected_dimensions=frozenset({"04.dopamine"})),
    )
    dim = report.dimensions["04.dopamine"]
    assert dim.drift_class == DRIFT_NEGATIVE, report.summary()
    assert dim.divergence == "none"
    assert report.analysis_ok, report.violations()


def test_flat_dimension_is_neutral() -> None:
    report = evaluate_drift(
        _samples("05.valence", [0.5] * 20),
        DriftConfig(expected_dimensions=frozenset({"05.valence"})),
    )
    assert report.dimensions["05.valence"].drift_class == DRIFT_NEUTRAL
    assert report.analysis_ok, report.violations()


def test_deadband_boundary_is_neutral() -> None:
    # Early window all 0.50, late window all 0.52 -> delta 0.02 == neutral_band -> neutral (the
    # documented `==` tie-break). 20 samples, window=5, so first 5 are early and last 5 are late.
    values = [0.50] * 10 + [0.52] * 10
    report = evaluate_drift(
        _samples("05.valence", values),
        DriftConfig(expected_dimensions=frozenset({"05.valence"}), neutral_band=0.02),
    )
    dim = report.dimensions["05.valence"]
    assert dim.normalized_delta == pytest.approx(0.02)
    assert dim.drift_class == DRIFT_NEUTRAL, report.summary()


def test_absent_expected_dimension_is_unavailable_and_fails() -> None:
    report = evaluate_drift(
        _samples("05.valence", [0.5] * 20),
        DriftConfig(expected_dimensions=frozenset({"04.dopamine"})),
    )
    assert report.dimensions["04.dopamine"].drift_class == DIM_UNAVAILABLE
    assert "04.dopamine" in report.missing_dimensions
    assert not report.analysis_ok


def test_sparse_dimension_is_unavailable() -> None:
    # Three observations (< min_samples_for_trend default 4) -> unavailable, never a fabricated neutral.
    report = evaluate_drift(
        _samples("04.dopamine", [0.5, 0.5, 0.5]),
        DriftConfig(expected_dimensions=frozenset({"04.dopamine"})),
    )
    assert report.dimensions["04.dopamine"].drift_class == DIM_UNAVAILABLE
    assert not report.analysis_ok


# --- divergence (saturation toward a legal bound) ------------------------------------------------


def test_divergent_high_flags_and_fails() -> None:
    # Ramps into the top 0.02 of [0,1]; the late-window mean is pinned near the ceiling while rising.
    values = [0.5 + (0.49 * i / 19) for i in range(15)] + [0.99] * 5
    report = evaluate_drift(
        _samples("04.cortisol", values),
        DriftConfig(expected_dimensions=frozenset({"04.cortisol"})),
    )
    dim = report.dimensions["04.cortisol"]
    assert dim.drift_class == DRIFT_POSITIVE
    assert dim.divergence == "divergent_high", report.summary()
    assert "04.cortisol" in report.divergent_dimensions
    assert not report.analysis_ok


def test_divergent_low_flags_and_fails() -> None:
    values = [0.5 - (0.49 * i / 19) for i in range(15)] + [0.01] * 5
    report = evaluate_drift(
        _samples("04.cortisol", values),
        DriftConfig(expected_dimensions=frozenset({"04.cortisol"})),
    )
    dim = report.dimensions["04.cortisol"]
    assert dim.drift_class == DRIFT_NEGATIVE
    assert dim.divergence == "divergent_low", report.summary()
    assert not report.analysis_ok


def test_outward_drive_above_one_is_not_false_divergent() -> None:
    # `18.outward_drive` legal range is [0, 8.0]; a 1.3 -> 1.7 step is a small positive drift
    # (normalized 0.05) but nowhere near the 8.0 ceiling, so it must NOT be flagged divergent and the
    # run stays ok. This guards against treating an above-unit drive as a runaway just because its
    # raw value exceeds 1.
    values = [1.3] * 10 + [1.7] * 10
    report = evaluate_drift(
        _samples("18.outward_drive", values),
        DriftConfig(expected_dimensions=frozenset({"18.outward_drive"})),
    )
    dim = report.dimensions["18.outward_drive"]
    assert dim.drift_class == DRIFT_POSITIVE, report.summary()
    assert dim.normalized_delta == pytest.approx(0.05)
    assert dim.divergence == "none"
    assert report.analysis_ok, report.violations()


# --- committed baseline trace (real R83 data) ----------------------------------------------------


def test_committed_semantic_600_trace_is_settled_and_ok() -> None:
    assert os.path.exists(_SEMANTIC_600), _SEMANTIC_600
    report = evaluate_trace_file(_SEMANTIC_600)

    # All 50 sampled ticks parsed.
    assert report.total_samples == 50, report.summary()

    # All 19 expected owner dimensions present and classifiable (zero unexpected unavailability).
    assert report.missing_dimensions == (), report.summary()
    assert len(report.expected_dimensions) == 19
    assert report.class_counts[DIM_UNAVAILABLE] == 0

    # This deterministic run reaches a fixed point within its first sampled tick and stays frozen, so
    # every dimension's early-vs-late delta is inside the deadband: a settled run, all neutral.
    assert report.class_counts[DRIFT_NEUTRAL] == 19, report.summary()
    assert report.divergent_dimensions == ()
    assert report.analysis_ok, report.violations()

    # Render the readout so the CI log carries the evidence (print allowed in tests, not in src).
    print("\n" + report.summary())


def test_committed_trace_loads_all_lines() -> None:
    samples = load_samples(_SEMANTIC_600)
    assert len(samples) == 50
    assert all("tick" in s for s in samples)


# --- robustness ----------------------------------------------------------------------------------


def test_empty_trace_fails_with_reason() -> None:
    report = evaluate_drift([], DriftConfig(expected_dimensions=frozenset({"04.dopamine"})))
    assert report.parse_reason == "empty_trace"
    assert not report.analysis_ok
    assert report.dimensions["04.dopamine"].drift_class == DIM_UNAVAILABLE


def test_malformed_file_skips_bad_lines(tmp_path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        "not json\n"
        '{"tick": 0.0, "04.dopamine": 0.5}\n'
        "\n"
        "{broken\n"
        '{"tick": 1.0, "04.dopamine": 0.5}\n',
        encoding="utf-8",
    )
    samples = load_samples(str(path))
    # Two valid JSON object lines survive; the two garbage lines and the blank line are skipped.
    assert len(samples) == 2
    report = evaluate_trace_file(str(path), DriftConfig(min_samples_for_trend=4))
    # Two valid samples is below the trend minimum -> not ok, but no exception escaped.
    assert not report.analysis_ok
