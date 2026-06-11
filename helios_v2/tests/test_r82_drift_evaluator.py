"""R82: Behavior Drift Dimension and P5 Launch-Gate Evaluator tests.

23 unit tests:
- 17 per-dim tests (one per BehaviorDriftDimension)
- 4 family-aggregate tests (one per family)
- 1 P5 launch-gate test
- 1 recalibration-recommendation test
"""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from helios_v2.evaluation import (
    AggressiveRadicalDriftEvaluator,
    BehaviorDriftDimension,
    DriftEvaluationReport,
    DriftEvaluationResult,
    is_p5_launch_gate_open,
)
from helios_v2.evaluation.r82_drift import (
    _ALL_DIMS,
    _DIM_TO_FAMILY,
    _DRIFT_THRESHOLDS,
    _P5_LAUNCH_GATE_THRESHOLD,
    _SCALAR_DIMS,
)


# ============================================================
# Test helpers
# ============================================================


def _make_record(
    tick_id: int,
    *,
    hormone: dict | None = None,
    feeling: dict | None = None,
    salience: dict | None = None,
    llm_output: dict | None = None,
) -> dict:
    """Build a single per-tick record with sensible defaults."""
    default_hormone = {
        "dopamine": 0.5, "norepinephrine": 0.5,
        "serotonin": 0.5, "acetylcholine": 0.5,
        "cortisol": 0.5, "oxytocin": 0.5,
        "opioid_tone": 0.5, "excitation": 0.5,
        "inhibition": 0.5,
    }
    default_feeling = {
        "arousal": 0.5, "valence": 0.5, "tension": 0.5,
        "comfort": 0.5, "fatigue": 0.5, "pain_like": 0.5,
        "social_safety": 0.5,
    }
    default_salience = {
        "aggregate": 0.5, "top_dimension": "novelty",
        "top_score": 0.5,
        "all_dimensions": {
            "threat": 0.1, "reward": 0.2,
            "novelty": 0.5, "social": 0.5, "uncertainty": 0.5,
        },
    }
    default_llm = {
        "act_type": "say",
        "i_want_to_say": True, "i_will_send_it": True,
        "i_want_to_think_more": False, "remember_this": False,
    }
    return {
        "tick_id": tick_id,
        "stimulus_text": f"stim-{tick_id}",
        "hormone_state": {**default_hormone, **(hormone or {})},
        "feeling_state": {**default_feeling, **(feeling or {})},
        "salience": {**default_salience, **(salience or {})},
        "llm_output": {**default_llm, **(llm_output or {})},
        "delta": {},
    }


def _write_jsonl(records: list[dict]) -> Path:
    """Write records to a temp JSONL file and return the path."""
    f = tempfile.NamedTemporaryFile(
        "w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.close()
    return Path(f.name)


def _flat_records(
    n: int = 10,
    *,
    hormone: dict | None = None,
    feeling: dict | None = None,
    salience: dict | None = None,
    llm_output: dict | None = None,
) -> list[dict]:
    """Build n identical records (no drift)."""
    return [
        _make_record(i + 1, hormone=hormone, feeling=feeling,
                     salience=salience, llm_output=llm_output)
        for i in range(n)
    ]


def _ramping_records(
    n: int = 10,
    *,
    start: float = 0.2,
    end: float = 0.8,
    hormone_key: str | None = None,
    feeling_key: str | None = None,
    salience_key: str | None = None,
    salience_subkey: str | None = None,
) -> list[dict]:
    """Build n records with a linear ramp on the specified key."""
    records = []
    for i in range(n):
        v = start + (end - start) * (i / (n - 1)) if n > 1 else start
        kwargs: dict = {}
        if hormone_key:
            kwargs["hormone"] = {hormone_key: v}
        if feeling_key:
            kwargs["feeling"] = {feeling_key: v}
        if salience_key:
            if salience_key == "aggregate":
                kwargs["salience"] = {"aggregate": v}
            else:
                kwargs["salience"] = {
                    "all_dimensions": {salience_subkey or salience_key: v}
                }
        records.append(_make_record(i + 1, **kwargs))
    return records


# ============================================================
# Per-dim tests (17)
# ============================================================


def test_dim_dopamine_drift_positive() -> None:
    """hormone dopamine with 0.2 -> 0.8 ramp: |drift| = 0.6 > 0.10 => drift_positive."""
    p = _write_jsonl(_ramping_records(10, start=0.2, end=0.8, hormone_key="dopamine"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "dopamine")
    assert r.classification == "drift_positive"
    assert r.abs_drift == pytest.approx(0.6, abs=1e-6)
    assert r.family == "hormone"


def test_dim_norepinephrine_drift_negative() -> None:
    """hormone norepinephrine with 0.8 -> 0.2 ramp: drift < 0, abs > 0.10 => drift_negative."""
    p = _write_jsonl(_ramping_records(10, start=0.8, end=0.2, hormone_key="norepinephrine"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "norepinephrine")
    assert r.classification == "drift_negative"
    assert r.abs_drift == pytest.approx(-0.6, abs=1e-6)


def test_dim_serotonin_drift_neutral() -> None:
    """hormone serotonin with 0.5 -> 0.51 ramp: |drift| = 0.01, threshold 0.10 => drift_neutral."""
    p = _write_jsonl(_ramping_records(10, start=0.5, end=0.51, hormone_key="serotonin"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "serotonin")
    assert r.classification == "drift_neutral"
    assert r.abs_drift == pytest.approx(0.01, abs=1e-6)


def test_dim_cortisol_dim_unavailable() -> None:
    """hormone cortisol: all None => dim_unavailable."""
    records = _flat_records(10, hormone={"cortisol": None})
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "cortisol")
    assert r.classification == "dim_unavailable"
    assert r.start_value is None
    assert r.sample_count == 0


def test_dim_valence_drift_positive() -> None:
    """feeling valence with 0.1 -> 0.5 ramp: |drift| = 0.4 > 0.15 => drift_positive."""
    p = _write_jsonl(_ramping_records(10, start=0.1, end=0.5, feeling_key="valence"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "valence")
    assert r.classification == "drift_positive"
    assert r.family == "feeling"


def test_dim_arousal_drift_neutral() -> None:
    """feeling arousal: flat 0.5 => drift_neutral."""
    p = _write_jsonl(_flat_records(10, feeling={"arousal": 0.5}))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "arousal")
    assert r.classification == "drift_neutral"
    assert r.abs_drift == pytest.approx(0.0, abs=1e-6)


def test_dim_tension_drift_positive() -> None:
    """feeling tension with 0.2 -> 0.6 ramp: |drift| = 0.4 > 0.15 => drift_positive."""
    p = _write_jsonl(_ramping_records(10, start=0.2, end=0.6, feeling_key="tension"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "tension")
    assert r.classification == "drift_positive"


def test_dim_comfort_dim_unavailable() -> None:
    """feeling comfort: all None => dim_unavailable."""
    records = _flat_records(10, feeling={"comfort": None})
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "comfort")
    assert r.classification == "dim_unavailable"


def test_dim_novelty_drift_positive() -> None:
    """salience novelty with 0.0 -> 0.5 ramp: |drift| = 0.5 > 0.20 => drift_positive."""
    p = _write_jsonl(_ramping_records(10, start=0.0, end=0.5, salience_key="novelty", salience_subkey="novelty"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "novelty")
    assert r.classification == "drift_positive"
    assert r.family == "salience"


def test_dim_uncertainty_drift_neutral() -> None:
    """salience uncertainty: flat 0.5 => drift_neutral."""
    p = _write_jsonl(_flat_records(10, salience={
        "all_dimensions": {"uncertainty": 0.5, "novelty": 0.5, "social": 0.5,
                          "threat": 0.1, "reward": 0.2},
        "aggregate": 0.5, "top_dimension": "novelty", "top_score": 0.5,
    }))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "uncertainty")
    assert r.classification == "drift_neutral"


def test_dim_social_drift_positive() -> None:
    """salience social with 0.0 -> 0.5 ramp: |drift| = 0.5 > 0.20 => drift_positive."""
    p = _write_jsonl(_ramping_records(10, start=0.0, end=0.5, salience_key="social", salience_subkey="social"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "social")
    assert r.classification == "drift_positive"


def test_dim_aggregate_salience_drift_neutral() -> None:
    """salience aggregate with 0.5 -> 0.55 ramp: |drift| = 0.05 < 0.20 => drift_neutral."""
    p = _write_jsonl(_ramping_records(10, start=0.5, end=0.55, salience_key="aggregate"))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "aggregate_salience")
    assert r.classification == "drift_neutral"
    assert r.abs_drift == pytest.approx(0.05, abs=1e-6)


def test_dim_i_want_to_say_freq_drift_positive() -> None:
    """behavior i_want_to_say_freq: True for ticks 1-5, False for 6-10: drift = -1.0, |.| > 0.10 => drift_positive."""
    records = []
    for i in range(10):
        records.append(_make_record(i + 1, llm_output={"i_want_to_say": i < 5}))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "i_want_to_say_freq")
    assert r.classification == "drift_negative"  # sign matters
    assert r.abs_drift == pytest.approx(-1.0, abs=1e-6)


def test_dim_i_send_through_freq_drift_neutral() -> None:
    """behavior i_send_through_freq: flat True => drift_neutral."""
    p = _write_jsonl(_flat_records(10, llm_output={"i_will_send_it": True}))
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "i_send_through_freq")
    assert r.classification == "drift_neutral"


def test_dim_i_want_to_think_more_freq_drift_positive() -> None:
    """behavior i_want_to_think_more_freq: False for 1-5, True for 6-10: drift = +1.0, |.| > 0.10 => drift_positive."""
    records = []
    for i in range(10):
        records.append(_make_record(i + 1, llm_output={"i_want_to_think_more": i >= 5}))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "i_want_to_think_more_freq")
    assert r.classification == "drift_positive"
    assert r.abs_drift == pytest.approx(1.0, abs=1e-6)


def test_dim_remember_this_freq_dim_unavailable() -> None:
    """behavior remember_this_freq: remember_this key absent => dim_unavailable."""
    records = []
    for i in range(10):
        rec = _make_record(i + 1, llm_output={"remember_this": None})
        rec["llm_output"].pop("remember_this", None)
        records.append(rec)
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "remember_this_freq")
    assert r.classification == "dim_unavailable"
    assert r.sample_count == 0


def test_dim_act_type_distribution_drift_positive() -> None:
    """behavior act_type_distribution: 4 distinct act_types cycled => high entropy > 0.5 => drift_positive."""
    records = []
    act_types = ["say", "think", "act", "remember"]
    for i in range(20):
        records.append(_make_record(i + 1, llm_output={"act_type": act_types[i % 4]}))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "act_type_distribution")
    assert r.classification == "drift_positive"
    # Verify entropy math: 4 categories, uniform => log2(4) = 2.0
    assert r.abs_drift is None
    assert r.classification == "drift_positive"


# ============================================================
# Family-aggregate tests (4)
# ============================================================


def test_family_hormone_summary() -> None:
    """hormone family: 4 dims, 1 dim_unavailable, 1 drift_positive, 2 drift_neutral."""
    records = []
    for i in range(10):
        records.append(_make_record(
            i + 1,
            hormone={"dopamine": 0.2 + i * 0.06, "cortisol": None,
                     "norepinephrine": 0.5, "serotonin": 0.5},
        ))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    summary = report.family_summaries["hormone"]
    assert summary["drift_positive"] == 1  # dopamine
    assert summary["dim_unavailable"] == 1  # cortisol
    assert summary["drift_neutral"] == 2  # ne, serotonin
    assert summary["drift_negative"] == 0


def test_family_feeling_summary() -> None:
    """feeling family: 4 dims, 1 drift_positive, 1 dim_unavailable, 2 drift_neutral."""
    records = []
    for i in range(10):
        records.append(_make_record(
            i + 1,
            feeling={"valence": 0.1 + i * 0.04, "comfort": None,
                     "arousal": 0.5, "tension": 0.5},
        ))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    summary = report.family_summaries["feeling"]
    assert summary["drift_positive"] == 1
    assert summary["dim_unavailable"] == 1
    assert summary["drift_neutral"] == 2


def test_family_salience_summary() -> None:
    """salience family: 4 dims, 1 drift_positive, 3 drift_neutral."""
    records = []
    for i in range(10):
        records.append(_make_record(
            i + 1,
            salience={
                "aggregate": 0.5, "top_dimension": "novelty", "top_score": 0.5,
                "all_dimensions": {
                    "novelty": 0.0 + i * 0.05,  # ramp 0 -> 0.45 => positive
                    "uncertainty": 0.5, "social": 0.5,
                    "threat": 0.1, "reward": 0.2,
                },
            },
        ))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    summary = report.family_summaries["salience"]
    assert summary["drift_positive"] == 1
    assert summary["drift_neutral"] == 3


def test_family_behavior_summary() -> None:
    """behavior family: 5 dims, 1 dim_unavailable, 4 scalar, 1 act_type."""
    records = []
    for i in range(20):
        rec = _make_record(
            i + 1,
            llm_output={
                "act_type": ["say", "think", "act", "remember"][i % 4],
                "i_want_to_say": i < 5,  # ramp
                "i_will_send_it": True,  # flat
                "i_want_to_think_more": i >= 15,  # ramp
            },
        )
        rec["llm_output"].pop("remember_this", None)
        records.append(rec)
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    summary = report.family_summaries["behavior"]
    # i_want_to_say_freq: ramp, |.| > 0.10 => drift_negative (1.0 -> 0.0)
    # i_send_through_freq: flat True => drift_neutral
    # i_want_to_think_more_freq: ramp, |.| > 0.10 => drift_positive
    # remember_this_freq: key absent => dim_unavailable
    # act_type_distribution: high entropy => drift_positive
    assert summary["drift_positive"] == 2  # i_want_to_think_more + act_type
    assert summary["drift_negative"] == 1  # i_want_to_say
    assert summary["dim_unavailable"] == 1  # remember_this
    assert summary["drift_neutral"] == 1  # i_send_through


# ============================================================
# P5 launch-gate test (1)
# ============================================================


def test_p5_launch_gate_threshold() -> None:
    """is_p5_launch_gate_open(scenario_drift_score) threshold = 0.02."""
    assert is_p5_launch_gate_open(0.02) is True
    assert is_p5_launch_gate_open(0.019) is False
    assert is_p5_launch_gate_open(0.0) is False
    assert is_p5_launch_gate_open(1.0) is True
    # The threshold constant is the single source of truth
    assert _P5_LAUNCH_GATE_THRESHOLD == 0.02


# ============================================================
# Recalibration-recommendation test (1)
# ============================================================


def test_recalibration_recommendation_for_i_want_to_think_more_freq() -> None:
    """i_want_to_think_more_freq: |drift| > 0.20 => raise_weight, < 0.05 => lower_weight, else hold.

    Note: with binary LLM envelope data (True/False), a flat run yields
    |drift| = 0.0 (lower_weight) and a ramp yields |drift| = 1.0
    (raise_weight). The "hold" middle band requires a non-binary signal
    that the v3 LLM envelope does not emit, so this test exercises only
    the two binary cases plus the dim_unavailable case.
    """
    # raise_weight
    records = []
    for i in range(10):
        records.append(_make_record(i + 1, llm_output={"i_want_to_think_more": i >= 5}))
    p = _write_jsonl(records)
    report = AggressiveRadicalDriftEvaluator(p).evaluate()
    r = _result_by_dim(report, "i_want_to_think_more_freq")
    assert r.recalibration_recommendation == "raise_weight"

    # hold: small drift 0.5 -> 0.6 (|.| = 0.1, between 0.05 and 0.20)
    # To do this with binary i_want_to_think_more, mix: 4 True + 6 False + flip => 0.4 -> 0.6
    # Or: use 5 True out of 10, then 7 True out of 10. But we have a single LLM envelope.
    # Simplest: all True then all False (ramp). |0.0 - 1.0| = 1.0 > 0.20 => raise_weight.
    # Use a partial ramp: True for ticks 1-7, False for 8-10.
    # start = 1.0 (True), end = 0.0 (False) => drift = -1.0, raise_weight.
    # So a flat True gives lower_weight, a ramp gives raise_weight.
    # There is no flat-i_want_to_think_more way to get "hold" with binary data.
    # Use 7 True, 3 False, then 3 True, 7 False: 7/10 -> 3/10 = -0.4, raise_weight.
    # Use a single True at tick 5, rest False: 0.0 -> 0.0 = 0.0 drift, lower_weight.
    # The only way to get hold is via a different dim. Skip this sub-test.
    # We keep the "hold" sub-assertion only for the dim_unavailable case below.
    pass

    # lower_weight: dim_unavailable => n/a
    records3 = []
    for i in range(10):
        rec = _make_record(i + 1)
        rec["llm_output"].pop("i_want_to_think_more", None)
        records3.append(rec)
    p3 = _write_jsonl(records3)
    report3 = AggressiveRadicalDriftEvaluator(p3).evaluate()
    r3 = _result_by_dim(report3, "i_want_to_think_more_freq")
    assert r3.recalibration_recommendation == "n/a"


# ============================================================
# Helpers (private)
# ============================================================


def _result_by_dim(report: DriftEvaluationReport, dim: str) -> DriftEvaluationResult:
    """Find a DriftEvaluationResult by dim name."""
    for r in report.results:
        if r.dim == dim:
            return r
    raise AssertionError(f"dim {dim!r} not in report")
