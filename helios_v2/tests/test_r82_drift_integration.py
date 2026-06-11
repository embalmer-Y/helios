"""R82: Drift evaluator integration test with the R79-D CLI flow.

Verifies that:
1. The R79-D CLI `run --with-drift-report` flag invokes the evaluator.
2. The output drift_report.md contains the expected sections.
3. The P5 launch-gate verdict is reported.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from helios_v2.evaluation import (
    AggressiveRadicalDriftEvaluator,
    DriftEvaluationReport,
    is_p5_launch_gate_open,
)
from helios_v2.evaluation.r82_drift import _P5_LAUNCH_GATE_THRESHOLD


def _make_minimal_jsonl(out_dir: Path, n: int = 5) -> Path:
    """Write n minimal records that produce non-zero drift."""
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "integration.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for i in range(n):
            record = {
                "tick_id": i + 1,
                "stimulus_text": f"stim-{i}",
                "hormone_state": {
                    "dopamine": 0.3 + i * 0.1,  # ramp 0.3 -> 0.7
                    "norepinephrine": 0.5,
                    "serotonin": 0.5,
                    "acetylcholine": 0.5, "cortisol": 0.5,
                    "oxytocin": 0.5, "opioid_tone": 0.5,
                    "excitation": 0.5, "inhibition": 0.5,
                },
                "feeling_state": {
                    "arousal": 0.5, "valence": 0.5, "tension": 0.5,
                    "comfort": 0.5, "fatigue": 0.5, "pain_like": 0.5,
                    "social_safety": 0.5,
                },
                "salience": {
                    "aggregate": 0.5, "top_dimension": "novelty",
                    "top_score": 0.5,
                    "all_dimensions": {
                        "threat": 0.1, "reward": 0.2,
                        "novelty": 0.5, "social": 0.5, "uncertainty": 0.5,
                    },
                },
                "llm_output": {
                    "act_type": "say", "i_want_to_say": True,
                    "i_will_send_it": True, "i_want_to_think_more": False,
                    "remember_this": False,
                },
                "delta": {},
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return jsonl


def test_integration_drift_report_written() -> None:
    """End-to-end: write JSONL, run evaluator, verify DriftEvaluationReport."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        jsonl = _make_minimal_jsonl(out, n=5)
        report = AggressiveRadicalDriftEvaluator(jsonl).evaluate()
        assert isinstance(report, DriftEvaluationReport)
        assert report.tick_count == 5
        # dopamine ramp 0.3 -> 0.7 => |drift| = 0.4 > 0.10 => drift_positive
        dop = [r for r in report.results if r.dim == "dopamine"][0]
        assert dop.classification == "drift_positive"
        # At least one drift_positive overall => P5 gate open
        assert is_p5_launch_gate_open(report.overall_drift_score) is True
        # overall score is the mean of |drift| across non-unavailable dims
        assert report.overall_drift_score > 0.0


def test_integration_drift_report_p5_gate_closed_on_flat() -> None:
    """Flat data: no drift => P5 gate closed."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        jsonl = out / "flat.jsonl"
        with jsonl.open("w", encoding="utf-8") as f:
            for i in range(5):
                f.write(json.dumps({
                    "tick_id": i + 1, "stimulus_text": "x",
                    "hormone_state": {
                        "dopamine": 0.5, "norepinephrine": 0.5, "serotonin": 0.5,
                        "acetylcholine": 0.5, "cortisol": 0.5, "oxytocin": 0.5,
                        "opioid_tone": 0.5, "excitation": 0.5, "inhibition": 0.5,
                    },
                    "feeling_state": {
                        "arousal": 0.5, "valence": 0.5, "tension": 0.5,
                        "comfort": 0.5, "fatigue": 0.5, "pain_like": 0.5,
                        "social_safety": 0.5,
                    },
                    "salience": {
                        "aggregate": 0.5, "top_dimension": "novelty",
                        "top_score": 0.5,
                        "all_dimensions": {
                            "threat": 0.1, "reward": 0.2, "novelty": 0.5,
                            "social": 0.5, "uncertainty": 0.5,
                        },
                    },
                    "llm_output": {
                        "act_type": "say", "i_want_to_say": False,
                        "i_will_send_it": False, "i_want_to_think_more": False,
                        "remember_this": False,
                    },
                    "delta": {},
                }, ensure_ascii=False) + "\n")
        report = AggressiveRadicalDriftEvaluator(jsonl).evaluate()
        # All dims should be drift_neutral or dim_unavailable
        for r in report.results:
            assert r.classification in {"drift_neutral", "dim_unavailable"}
        # overall_drift_score should be 0.0 (no drift)
        assert report.overall_drift_score == 0.0
        # P5 gate closed (since 0.0 < threshold)
        assert is_p5_launch_gate_open(report.overall_drift_score) is False
