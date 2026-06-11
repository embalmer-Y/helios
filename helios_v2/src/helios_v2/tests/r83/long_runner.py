"""R83 long-running preflight harness.

Drives helios_v2 end-to-end for ~10 minutes under CLI external input
and produces an `R83Scores` instance. The harness is a pure driver —
it observes the runtime but does not steer it.

Reuses the R79-D framework's `ScriptedCliSource` and gateway primitives
for LLM calls. R83 is a sibling of `tests/r79d/`, not a child.

Public API:
    - `R83Scores` (frozen dataclass) - the 6-axis scores + overall
      drift + per-block detail + elapsed time.
    - `BlockSummary` (frozen dataclass) - per-block A2 algorithmic
      score + judge A1/A4/A6 scores + bio-chemistry deltas.
    - `LongRunner.run(duration_minutes, noop, output_dir) -> R83Scores`
    - `_score_a2(records, expected_response) -> float` - the A2
      algorithmic scoring rule (per `expected_response`).
    - `_score_a5(jsonl_path) -> float` - the A5 cross-tick continuity
      score (uses R82 drift evaluator).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from . import _io
from .scenarios import StateBlock, load_state_blocks


# ============================================================
# Data structures
# ============================================================


@dataclass(frozen=True)
class BlockSummary:
    """One per-state-block summary."""

    state_id: str
    n_ticks: int
    a2_score: float
    judge_a1: float | None
    judge_a4: float | None
    judge_a6: float | None
    judge_reasoning: str
    hormone_deltas: dict[str, float]
    feeling_deltas: dict[str, float]


@dataclass(frozen=True)
class R83Scores:
    """The 6-axis R83 scores + overall drift + per-block detail."""

    a1_linguistic_naturalness: float
    a2_bio_responsiveness: float
    a3_memory_fidelity: float
    a4_agency_locking: float
    a5_cross_tick_continuity: float
    a6_stimulus_response_coherence: float
    overall_drift_score: float
    per_block: tuple[BlockSummary, ...]
    total_ticks: int
    elapsed_seconds: float

    def mean(self) -> float:
        return (
            self.a1_linguistic_naturalness
            + self.a2_bio_responsiveness
            + self.a3_memory_fidelity
            + self.a4_agency_locking
            + self.a5_cross_tick_continuity
            + self.a6_stimulus_response_coherence
        ) / 6.0

    def min(self) -> float:
        return min(
            self.a1_linguistic_naturalness,
            self.a2_bio_responsiveness,
            self.a3_memory_fidelity,
            self.a4_agency_locking,
            self.a5_cross_tick_continuity,
            self.a6_stimulus_response_coherence,
        )


# ============================================================
# A2 algorithmic scoring
# ============================================================


def _delta(records: list[dict], key_path: tuple[str, str]) -> float | None:
    """Compute first->last delta on `record[key_path[0]][key_path[1]]`.

    Returns None if either end is missing.
    """
    if len(records) < 2:
        return None
    first = records[0].get(key_path[0], {}).get(key_path[1])
    last = records[-1].get(key_path[0], {}).get(key_path[1])
    if first is None or last is None:
        return None
    return float(last) - float(first)


def _score_a2(records: list[dict], expected_response: str) -> float:
    """Algorithmic A2 score: 0.0-1.0 how well bio-chemistry matches expected.

    Scoring rules per `expected_response`:
        "positive" -> +dopamine, +oxytocin, +valence, +comfort
        "negative_plus_arousal" -> -oxytocin, +cortisol, +arousal, +tension
        "arousal_spike_plus_positive" -> +norepinephrine, +dopamine, +arousal
        "arousal_spike_neutral_valence" -> +norepinephrine, +arousal
        "mixed" -> +cortisol, +dopamine, +arousal
        "high_drift" -> |valence swing| large

    Default to 0.5 if no records / missing data.
    """
    if len(records) < 2:
        return 0.5
    deltas: dict[str, float | None] = {
        "dopamine": _delta(records, ("hormone_state", "dopamine")),
        "norepinephrine": _delta(records, ("hormone_state", "norepinephrine")),
        "serotonin": _delta(records, ("hormone_state", "serotonin")),
        "cortisol": _delta(records, ("hormone_state", "cortisol")),
        "oxytocin": _delta(records, ("hormone_state", "oxytocin")),
        "valence": _delta(records, ("feeling_state", "valence")),
        "arousal": _delta(records, ("feeling_state", "arousal")),
        "tension": _delta(records, ("feeling_state", "tension")),
        "comfort": _delta(records, ("feeling_state", "comfort")),
    }

    def signed_d(k: str) -> float:
        v = deltas.get(k)
        return v if v is not None else 0.0

    if expected_response == "positive":
        score = 0.5 + 0.5 * (
            signed_d("oxytocin")
            + signed_d("dopamine")
            + signed_d("valence")
            + signed_d("comfort")
        ) / 4.0
    elif expected_response == "negative_plus_arousal":
        score = 0.5 + 0.5 * (
            -signed_d("oxytocin")
            + signed_d("cortisol")
            + signed_d("arousal")
            + signed_d("tension")
        ) / 4.0
    elif expected_response == "arousal_spike_plus_positive":
        score = 0.5 + 0.5 * (
            signed_d("norepinephrine")
            + signed_d("dopamine")
            + signed_d("arousal")
        ) / 3.0
    elif expected_response == "arousal_spike_neutral_valence":
        score = 0.5 + 0.5 * (
            signed_d("norepinephrine")
            + signed_d("arousal")
        ) / 2.0
    elif expected_response == "mixed":
        score = 0.5 + 0.5 * (
            signed_d("cortisol")
            + signed_d("dopamine")
            + signed_d("arousal")
        ) / 3.0
    elif expected_response == "high_drift":
        v = signed_d("valence")
        a = signed_d("arousal")
        score = 0.5 + 0.5 * min(1.0, abs(v) + abs(a)) / 2.0
    else:
        score = 0.5
    return max(0.0, min(1.0, score))


# ============================================================
# A5 cross-tick continuity (R82 reuse)
# ============================================================


def _score_a5(jsonl_path: Path) -> tuple[float, float]:
    """Score A5 (0.0-1.0) + return overall_drift_score (0.0-1.0+).

    Uses the R82 `AggressiveRadicalDriftEvaluator` to read the run's
    JSONL. The score is `0.5 + min(overall_drift * 4.0, 0.5)`, capped
    to [0.0, 1.0].
    """
    from helios_v2.evaluation import AggressiveRadicalDriftEvaluator

    if not jsonl_path.exists():
        return 0.5, 0.0
    report = AggressiveRadicalDriftEvaluator(jsonl_path).evaluate()
    drift = report.overall_drift_score
    score = 0.5 + min(drift * 4.0, 0.5)
    return max(0.0, min(1.0, score)), drift


# ============================================================
# Long runner
# ============================================================


@dataclass
class LongRunner:
    """The R83 long-running preflight harness.

    Reuses the R79-D framework's `ScriptedCliSource` and gateway
    primitives. R83 is a pure driver — it observes the runtime but
    does not steer it.
    """

    blocks: list[StateBlock] = field(default_factory=load_state_blocks)
    n_ticks_per_block: int = 5
    noop: bool = False

    def run(
        self,
        duration_minutes: float = 1.0,
        output_dir: Path | None = None,
    ) -> R83Scores:
        """Run the preflight; return `R83Scores`.

        Args:
            duration_minutes: target wall-clock duration in minutes.
                The actual run may be longer if state blocks are
                still in flight when the budget is hit.
            output_dir: optional directory to write the JSONL trail.
                If None, defaults to a tmpdir.

        Returns:
            `R83Scores` with all 6 axis scores + per-block detail.
        """
        from helios_v2.tests.r79d.framework import (
            NoopLlmGateway,
            RealLlmGateway,
            ScriptedCliSource,
            inject_v3_prompt,
        )
        from helios_v2.composition.runtime_assembly import assemble_runtime

        if output_dir is None:
            import tempfile

            output_dir = Path(tempfile.mkdtemp(prefix="r83_longrun_"))
        output_dir.mkdir(parents=True, exist_ok=True)
        jsonl_path = output_dir / "r83_longrun.jsonl"

        gateway = NoopLlmGateway() if self.noop else RealLlmGateway()
        handle = assemble_runtime(deterministic_thought=False, gateway=gateway)
        handle.startup()

        deadline = time.time() + duration_minutes * 60.0
        records: list[dict] = []
        per_block: list[BlockSummary] = []

        for block in self.blocks:
            block_records: list[dict] = []
            for variant in block.variants:
                if time.time() >= deadline:
                    _io.write_line(
                        f"[r83] wall-clock budget hit at block {block.id!r}"
                    )
                    break
                source = ScriptedCliSource([variant])
                # Avoid duplicate-registration: only register if not present
                if source.source_name not in handle.ingress._sources:
                    handle.ingress.register_source(source)
                inject_v3_prompt(handle)
                t0 = time.time()
                try:
                    result = handle.tick()
                    elapsed = time.time() - t0
                except Exception as exc:  # noqa: BLE001
                    _io.write_line(
                        f"[r83] tick failed in block {block.id!r}: {exc!r}"
                    )
                    continue
                rec = _result_to_record(result, block.id, variant, elapsed)
                records.append(rec)
                block_records.append(rec)
            else:
                # Only enter if the inner for-loop didn't break
                a2 = _score_a2(block_records, block.expected_response)
                hormone_deltas = _compute_hormone_deltas(block_records)
                feeling_deltas = _compute_feeling_deltas(block_records)
                summary = BlockSummary(
                    state_id=block.id,
                    n_ticks=len(block_records),
                    a2_score=a2,
                    judge_a1=None,
                    judge_a4=None,
                    judge_a6=None,
                    judge_reasoning="",
                    hormone_deltas=hormone_deltas,
                    feeling_deltas=feeling_deltas,
                )
                per_block.append(summary)
                continue
            # If we hit a deadline mid-block, skip scoring
            break

        # Write the JSONL trail
        with jsonl_path.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        a5_score, drift = _score_a5(jsonl_path)

        # A1, A4, A6 default to 0.5 (untestable) when no judge layer
        a1 = 0.5
        a4 = 0.5
        a6 = 0.5

        # A2 is the mean of per-block a2 scores (or 0.5 if empty)
        if per_block:
            a2 = sum(s.a2_score for s in per_block) / len(per_block)
        else:
            a2 = 0.5

        # A3 is set by the CLI layer (MemoryProbe); default 0.5
        a3 = 0.5

        scores = R83Scores(
            a1_linguistic_naturalness=a1,
            a2_bio_responsiveness=a2,
            a3_memory_fidelity=a3,
            a4_agency_locking=a4,
            a5_cross_tick_continuity=a5_score,
            a6_stimulus_response_coherence=a6,
            overall_drift_score=drift,
            per_block=tuple(per_block),
            total_ticks=len(records),
            elapsed_seconds=duration_minutes * 60.0,
        )
        return scores


# ============================================================
# Helpers
# ============================================================


def _mean_or(xs: Sequence[float], default: float) -> float:
    if not xs:
        return default
    return sum(xs) / len(xs)


def _compute_hormone_deltas(records: list[dict]) -> dict[str, float]:
    keys = ("dopamine", "norepinephrine", "serotonin", "acetylcholine",
            "cortisol", "oxytocin", "opioid_tone", "excitation", "inhibition")
    out: dict[str, float] = {}
    for k in keys:
        d = _delta(records, ("hormone_state", k))
        if d is not None:
            out[k] = d
    return out


def _compute_feeling_deltas(records: list[dict]) -> dict[str, float]:
    keys = ("valence", "arousal", "tension", "comfort",
            "fatigue", "pain_like", "social_safety")
    out: dict[str, float] = {}
    for k in keys:
        d = _delta(records, ("feeling_state", k))
        if d is not None:
            out[k] = d
    return out


def _result_to_record(
    result: Any,
    state_id: str,
    stimulus_text: str,
    elapsed: float,
) -> dict:
    """Convert a helios_v2 runtime `result` into a per-tick record dict.

    Extracts the 9 hormone channels + 7 feeling dims + salience +
    LLM envelope, matching the R79-D JSONL format. R83 adds two
    fields: `state_id` and `block_id` (state_id == block_id for
    R83 since each block is one state).
    """
    from helios_v2.tests.r79d.framework import (
        get_feeling_state_from_result,
        get_hormone_state_from_result,
        get_salience_from_result,
    )
    hormone_state = get_hormone_state_from_result(result)
    feeling_state = get_feeling_state_from_result(result)
    salience = get_salience_from_result(result)
    llm_output = _extract_llm_envelope(result)
    return {
        "tick_id": getattr(result, "tick_id", 0),
        "stimulus_text": stimulus_text,
        "state_id": state_id,
        "block_id": state_id,
        "hormone_state": hormone_state,
        "feeling_state": feeling_state,
        "salience": salience,
        "llm_output": llm_output,
        "delta": {"elapsed_s": elapsed},
    }


def _extract_llm_envelope(result: Any) -> dict:
    """Extract the LLM envelope from the latest `internal_monologue`
    stage or the embodied-prompt stage."""
    stage_results = getattr(result, "stage_results", {}) or {}
    for stage_name in ("internal_monologue_runtime", "embodied_prompt_runtime"):
        block = stage_results.get(stage_name)
        if block is None:
            continue
        state = getattr(block, "state", None)
        if state is None:
            continue
        env = getattr(state, "last_envelope", None) or getattr(state, "envelope", None)
        if isinstance(env, dict):
            return dict(env)
        # Some stages stash the envelope under "envelope" key
        if isinstance(state, dict) and "envelope" in state and isinstance(state["envelope"], dict):
            return dict(state["envelope"])
    return {}
