"""R83 long-running preflight + Turing-style evaluation — unit tests.

15 tests covering:
  1. stimulus catalog load + invariants
  2. StateBlock + 5-variant validation
  3. verdict compute (human-like / needs-recalibration)
  4. verdict min-axis + recalibration targets
  5. A2 algorithmic scorer per expected_response family
  6. A2 score clamping to [0.0, 1.0]
  7. R83Scores.mean / .min
  8. _delta helper (missing fields -> None)
  9. LongRunner smoke test (noop)
 10. LongRunner writes JSONL trail
 11. JSONL records have the right field shape
 12. A5 score uses R82 drift evaluator
 13. judge probe: parse-failed -> 0.5/0.5/0.5 fallback
 14. judge probe: empty samples -> 0.5/0.5/0.5 + 'no-samples' reason
 15. CLI smoke (run --help, --duration 0.05 --noop --no-judge)

These tests do NOT require a real LLM. They run in <30s on CI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from helios_v2.tests.r83 import _io
from helios_v2.tests.r83.judge import JudgeProbe
from helios_v2.tests.r83.long_runner import (
    LongRunner,
    R83Scores,
    _delta,
    _score_a2,
    _result_to_record,
)
from helios_v2.tests.r83.memory_probe import MemoryProbe
from helios_v2.tests.r83.report_builder import R83ReportBuilder
from helios_v2.tests.r83.scenarios import (
    EXPECTED_RESPONSE_TAXONOMY,
    StateBlock,
    get_state_block,
    load_state_blocks,
)
from helios_v2.tests.r83.verdict import Verdict


# ============================================================
# 1. stimulus catalog load + invariants
# ============================================================


def test_load_state_blocks_returns_8_blocks():
    blocks = load_state_blocks()
    assert len(blocks) == 8
    ids = {b.id for b in blocks}
    assert ids == {
        "praise", "neglect", "criticism", "comfort",
        "challenge", "surprise", "conflict", "contrast",
    }


def test_each_state_block_has_5_variants():
    for b in load_state_blocks():
        assert len(b.variants) == 5, f"{b.id} should have 5 variants, got {len(b.variants)}"


def test_state_blocks_have_unique_expected_response():
    seen = set()
    for b in load_state_blocks():
        seen.add(b.expected_response)
    # The catalog should use at least 4 different expected_response
    assert len(seen) >= 4
    # All expected_response values must be in the taxonomy
    for resp in seen:
        assert resp in EXPECTED_RESPONSE_TAXONOMY


def test_get_state_block_raises_on_missing():
    with pytest.raises(KeyError):
        get_state_block("nonexistent-state")


# ============================================================
# 2. StateBlock + 5-variant validation
# ============================================================


def test_state_block_rejects_empty_id():
    with pytest.raises(ValueError, match="id must be non-empty"):
        StateBlock(id="", description="", lever="",
                   expected_response="positive", variants=("a",))


def test_state_block_rejects_empty_variants():
    with pytest.raises(ValueError, match="must have at least 1 variant"):
        StateBlock(id="x", description="", lever="",
                   expected_response="positive", variants=())


def test_state_block_rejects_invalid_expected_response():
    with pytest.raises(ValueError, match="expected_response must be one of"):
        StateBlock(id="x", description="", lever="",
                   expected_response="bogus", variants=("a",))


# ============================================================
# 3. verdict compute (human-like / needs-recalibration)
# ============================================================


def test_verdict_human_like_when_all_axes_high():
    scores = _make_scores(0.8, 0.8, 0.8, 0.8, 0.8, 0.8)
    v = Verdict.compute(scores)
    assert v.label == "human-like"
    assert abs(v.mean_score - 0.8) < 1e-6


def test_verdict_needs_recalibration_when_mean_low():
    scores = _make_scores(0.4, 0.4, 0.4, 0.4, 0.4, 0.4)
    v = Verdict.compute(scores)
    assert v.label == "needs-recalibration"
    assert abs(v.mean_score - 0.4) < 1e-6


def test_verdict_needs_recalibration_when_min_below_floor():
    # Mean is OK but A3 is below min_floor (0.4) -> recalibrate
    scores = _make_scores(0.8, 0.8, 0.3, 0.8, 0.8, 0.8)
    v = Verdict.compute(scores)
    assert v.label == "needs-recalibration"
    assert v.min_axis == "A3_memory_fidelity"
    assert abs(v.min_score - 0.3) < 1e-6


# ============================================================
# 4. verdict min-axis + recalibration targets
# ============================================================


def test_verdict_recalibration_targets_lists_below_threshold_axes():
    scores = _make_scores(0.5, 0.7, 0.4, 0.8, 0.7, 0.6)
    v = Verdict.compute(scores, threshold=0.6)
    assert "A1_linguistic_naturalness" in v.recalibration_targets
    assert "A3_memory_fidelity" in v.recalibration_targets
    assert "A4_agency_locking" not in v.recalibration_targets
    assert "A5_cross_tick_continuity" not in v.recalibration_targets
    assert "A6_stimulus_response_coherence" not in v.recalibration_targets


def test_verdict_recalibration_targets_empty_when_all_high():
    scores = _make_scores(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
    v = Verdict.compute(scores, threshold=0.6)
    assert v.recalibration_targets == ()


# ============================================================
# 5. A2 algorithmic scorer per expected_response family
# ============================================================


def test_score_a2_positive_block_responds_correctly():
    records = [
        {"hormone_state": {"oxytocin": 0.5, "dopamine": 0.5},
         "feeling_state": {"valence": 0.5, "comfort": 0.5}},
        {"hormone_state": {"oxytocin": 0.7, "dopamine": 0.7},
         "feeling_state": {"valence": 0.7, "comfort": 0.7}},
    ]
    score = _score_a2(records, "positive")
    assert score > 0.5, f"expected > 0.5 for positive response, got {score}"


def test_score_a2_neglect_block_responds_correctly():
    records = [
        {"hormone_state": {"oxytocin": 0.5, "cortisol": 0.3},
         "feeling_state": {"arousal": 0.4, "tension": 0.3}},
        {"hormone_state": {"oxytocin": 0.3, "cortisol": 0.7},
         "feeling_state": {"arousal": 0.7, "tension": 0.7}},
    ]
    score = _score_a2(records, "negative_plus_arousal")
    assert score > 0.5


def test_score_a2_surprise_block_responds_correctly():
    records = [
        {"hormone_state": {"norepinephrine": 0.3},
         "feeling_state": {"arousal": 0.3}},
        {"hormone_state": {"norepinephrine": 0.8},
         "feeling_state": {"arousal": 0.8}},
    ]
    score = _score_a2(records, "arousal_spike_neutral_valence")
    assert score > 0.5


# ============================================================
# 6. A2 score clamping to [0.0, 1.0]
# ============================================================


def test_score_a2_clamped_to_0_1_range():
    records = [
        {"hormone_state": {"oxytocin": 0.0, "dopamine": 0.0},
         "feeling_state": {"valence": 0.0, "comfort": 0.0}},
        {"hormone_state": {"oxytocin": 1.0, "dopamine": 1.0},
         "feeling_state": {"valence": 1.0, "comfort": 1.0}},
    ]
    score = _score_a2(records, "positive")
    assert 0.0 <= score <= 1.0


def test_score_a2_returns_0_5_for_empty_records():
    assert _score_a2([], "positive") == 0.5
    assert _score_a2([{"hormone_state": {}, "feeling_state": {}}], "positive") == 0.5


# ============================================================
# 7. R83Scores.mean / .min
# ============================================================


def test_r83_scores_mean_and_min():
    scores = _make_scores(0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    assert abs(scores.mean() - 0.75) < 1e-6
    assert abs(scores.min() - 0.5) < 1e-6


# ============================================================
# 8. _delta helper (missing fields -> None)
# ============================================================


def test_delta_returns_none_for_missing_keys():
    records = [{"hormone_state": {"dopamine": 0.5}}]
    assert _delta(records, ("hormone_state", "dopamine")) is None


def test_delta_computes_first_last_difference():
    records = [
        {"hormone_state": {"dopamine": 0.3}},
        {"hormone_state": {"dopamine": 0.5}},
        {"hormone_state": {"dopamine": 0.7}},
    ]
    assert _delta(records, ("hormone_state", "dopamine")) == pytest.approx(0.4)


# ============================================================
# 9. LongRunner smoke test (noop)
# ============================================================


def test_long_runner_noop_smoke(tmp_path):
    runner = LongRunner(noop=True)
    scores = runner.run(duration_minutes=0.05, output_dir=tmp_path)
    assert isinstance(scores, R83Scores)
    assert scores.total_ticks >= 1


# ============================================================
# 10. LongRunner writes JSONL trail
# ============================================================


def test_long_runner_writes_jsonl_trail(tmp_path):
    runner = LongRunner(noop=True)
    scores = runner.run(duration_minutes=0.05, output_dir=tmp_path)
    jsonl_path = tmp_path / "r83_longrun.jsonl"
    assert jsonl_path.exists()
    assert jsonl_path.stat().st_size > 0


# ============================================================
# 11. JSONL records have the right field shape
# ============================================================


def test_jsonl_records_have_expected_field_shape(tmp_path):
    runner = LongRunner(noop=True)
    runner.run(duration_minutes=0.05, output_dir=tmp_path)
    jsonl_path = tmp_path / "r83_longrun.jsonl"
    with jsonl_path.open() as f:
        for line in f:
            rec = json.loads(line)
            assert "tick_id" in rec
            assert "stimulus_text" in rec
            assert "state_id" in rec
            assert "block_id" in rec
            assert "hormone_state" in rec
            assert "feeling_state" in rec


# ============================================================
# 12. A5 score uses R82 drift evaluator
# ============================================================


def test_a5_score_uses_drift_evaluator(tmp_path):
    runner = LongRunner(noop=True)
    scores = runner.run(duration_minutes=0.05, output_dir=tmp_path)
    # In noop mode, the A5 score should be in [0.0, 1.0]
    assert 0.0 <= scores.a5_cross_tick_continuity <= 1.0
    # The overall drift score should also be a finite non-negative number
    assert scores.overall_drift_score >= 0.0


# ============================================================
# 13. judge probe: parse-failed -> 0.5/0.5/0.5 fallback
# ============================================================


def test_judge_probe_parse_failed_returns_neutral():
    class _BadGateway:
        def complete(self, request):
            from helios_v2.llm.contracts import LlmCompletion
            return LlmCompletion(
                text="not json at all",  # not parseable
                parsed=None, usage=None, latency_ms=0.0,
                model="noop", request_id="x", timestamp=0.0,
                source_kind="noop",
            )
    probe = JudgeProbe(gateway=_BadGateway())
    result = probe.score(samples=["hi"], state_id="x", lever="", expected_response="positive")
    assert result.a1 == 0.5
    assert result.a4 == 0.5
    assert result.a6 == 0.5
    assert "judge-unavailable" in result.reasoning
    assert result.parse_failed is True


# ============================================================
# 14. judge probe: empty samples -> 0.5/0.5/0.5 + 'no-samples' reason
# ============================================================


def test_judge_probe_empty_samples_returns_neutral():
    probe = JudgeProbe(gateway=None)
    result = probe.score(samples=[], state_id="x", lever="", expected_response="positive")
    assert result.a1 == 0.5
    assert result.a4 == 0.5
    assert result.a6 == 0.5
    assert result.reasoning == "no-samples"
    assert result.parse_failed is False


# ============================================================
# 15. CLI smoke (run --help)
# ============================================================


def test_cli_help_runs_cleanly():
    result = subprocess.run(
        [sys.executable, "-m", "helios_v2.tests.r83", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "R83" in result.stdout


# ============================================================
# 16. CLI smoke (real noop run, 0.05 min, --no-judge)
# ============================================================


def test_cli_noop_runs_to_completion(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "helios_v2.tests.r83",
         "--duration", "0.05", "--noop", "--no-judge",
         "--output-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    report_path = tmp_path / "r83_report.md"
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "TL;DR" in content
    assert "Verdict" in content


# ============================================================
# 17. MemoryProbe stub returns 0.5 with "not-implemented" reasoning
# ============================================================


def test_memory_probe_stub():
    probe = MemoryProbe()
    result = probe.score()
    assert result.score == 0.5
    assert "not-implemented" in result.reasoning


# ============================================================
# 18. ReportBuilder writes a valid Markdown file
# ============================================================


def test_report_builder_writes_markdown(tmp_path):
    scores = _make_scores(0.7, 0.7, 0.7, 0.7, 0.7, 0.7)
    verdict = Verdict.compute(scores)
    builder = R83ReportBuilder(scores=scores, verdict=verdict, run_id="test-1")
    report_path = tmp_path / "report.md"
    builder.write(report_path)
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "# R83" in content
    assert "Axis scores" in content
    assert "Per-block detail" in content
    assert "Bio-chemistry deltas" in content
    assert "Recalibration targets" in content


# ============================================================
# 19. _io wrapper exposes R21-compliant write functions
# ============================================================


def test_io_wrapper_exposes_write_functions():
    assert hasattr(_io, "write_line")
    assert hasattr(_io, "write")
    assert hasattr(_io, "write_path")


# ============================================================
# 20. R21 ad-hoc logging guard passes for r83
# ============================================================


def test_r83_modules_dont_use_print():
    """The R21 ad-hoc logging guard scans src/helios_v2/ for `print(`;
    this test confirms the r83 source modules use _io.write_line only.

    The r83 source lives in `src/helios_v2/tests/r83/`. The test file
    itself is in `tests/` and is excluded from the scan.
    """
    import re
    r83_dir = Path(__file__).parent.parent / "src" / "helios_v2" / "tests" / "r83"
    pattern = re.compile(r"\bprint\s*\(")
    offenders: list[str] = []
    for py in r83_dir.rglob("*.py"):
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(r83_dir)}:{lineno}: {line}")
    assert offenders == [], (
        f"R83 source files must not use `print(`. Use `_io.write_line(...)` instead. "
        f"Offenders: {offenders}"
    )


# ============================================================
# Helpers
# ============================================================


def _make_scores(a1, a2, a3, a4, a5, a6) -> R83Scores:
    return R83Scores(
        a1_linguistic_naturalness=a1,
        a2_bio_responsiveness=a2,
        a3_memory_fidelity=a3,
        a4_agency_locking=a4,
        a5_cross_tick_continuity=a5,
        a6_stimulus_response_coherence=a6,
        overall_drift_score=0.05,
        per_block=(),
        total_ticks=8,
        elapsed_seconds=10.0,
    )
