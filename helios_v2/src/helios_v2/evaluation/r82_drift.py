"""R82: Behavior Drift Dimension and P5 Launch-Gate Evaluator.

This module is owned by `17` evaluation. It consumes the R79-D
framework's per-scenario JSONL output and produces a per-dim drift
classification.

No new owner, no new boundary. The evaluator is a pure aggregator;
it does not own any cross-cutting salience-to-channel policy.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .contracts import BehaviorDriftDimension

# Per-family drift thresholds (abs_drift magnitude).
_DRIFT_THRESHOLDS: dict[str, float] = {
    "hormone": 0.10,
    "feeling": 0.15,
    "salience": 0.20,
    "behavior": 0.10,  # for the 4 scalar behavior dims
    "act_type_distribution_entropy": 0.5,  # post-warmup entropy threshold
}

# P5 launch-gate threshold: a scenario must show at least this much
# mean abs_drift (across the 12 scalar dims) for the gate to open.
_P5_LAUNCH_GATE_THRESHOLD = 0.02

# Map each BehaviorDriftDimension to its family name.
_DIM_TO_FAMILY: dict[str, str] = {
    "dopamine": "hormone",
    "norepinephrine": "hormone",
    "serotonin": "hormone",
    "cortisol": "hormone",
    "valence": "feeling",
    "arousal": "feeling",
    "tension": "feeling",
    "comfort": "feeling",
    "novelty": "salience",
    "uncertainty": "salience",
    "social": "salience",
    "aggregate_salience": "salience",
    "i_want_to_say_freq": "behavior",
    "i_send_through_freq": "behavior",
    "i_want_to_think_more_freq": "behavior",
    "remember_this_freq": "behavior",
    "act_type_distribution": "behavior",
}

# All 17 dims, in the prescribed order (hormone -> feeling -> salience -> behavior).
_ALL_DIMS: tuple[str, ...] = (
    "dopamine", "norepinephrine", "serotonin", "cortisol",
    "valence", "arousal", "tension", "comfort",
    "novelty", "uncertainty", "social", "aggregate_salience",
    "i_want_to_say_freq", "i_send_through_freq", "i_want_to_think_more_freq",
    "remember_this_freq", "act_type_distribution",
)

# Scalar dims (16 of 17); the 1 non-scalar dim is act_type_distribution.
_SCALAR_DIMS: tuple[str, ...] = tuple(d for d in _ALL_DIMS if d != "act_type_distribution")


# Classification literals.
DriftClassification = Literal[
    "drift_positive", "drift_negative", "drift_neutral",
    "dim_unavailable", "act_type_distribution",
]

RecalibrationRecommendation = Literal[
    "hold", "raise_weight", "lower_weight", "n/a",
]


@dataclass(frozen=True)
class DriftEvaluationResult:
    """Per-dim drift evaluation result. Frozen, hashable, deterministic."""

    scenario_id: str
    family: str  # one of "hormone", "feeling", "salience", "behavior"
    dim: str
    start_value: float | None
    end_value: float | None
    min_value: float | None
    max_value: float | None
    abs_drift: float | None  # end_value - start_value
    range_drift: float | None  # max_value - min_value
    classification: DriftClassification
    sample_count: int
    recalibration_recommendation: RecalibrationRecommendation = "n/a"


@dataclass(frozen=True)
class DriftEvaluationReport:
    """Per-scenario drift evaluation report. Frozen, hashable, deterministic."""

    scenario_id: str
    tick_count: int
    results: tuple[DriftEvaluationResult, ...]  # exactly 17 entries
    family_summaries: dict[str, dict[str, int]]
    overall_drift_score: float  # in [0.0, 1.0]


def is_p5_launch_gate_open(scenario_drift_score: float) -> bool:
    """Return True iff the P5 launch gate is open for the given scenario drift score.

    The P5 launch gate is the canonical mechanism by which a future P5 R
    must consult the drift evaluator before mutating any `04`
    sensitivity coefficient. The threshold is the single source of
    truth: a scenario must show at least `_P5_LAUNCH_GATE_THRESHOLD`
    mean abs_drift across the 12 scalar dims for the gate to open.
    """
    return scenario_drift_score >= _P5_LAUNCH_GATE_THRESHOLD


def _classify_drift(dim: str, abs_drift: float | None) -> DriftClassification:
    """Classify a single dim's drift."""
    if abs_drift is None:
        return "dim_unavailable"
    family = _DIM_TO_FAMILY[dim]
    threshold = _DRIFT_THRESHOLDS[family]
    if abs(abs_drift) > threshold:
        return "drift_positive" if abs_drift > 0 else "drift_negative"
    return "drift_neutral"


def _classify_act_type_distribution(records: list[dict]) -> DriftClassification:
    """Classify the act_type_distribution dim by post-warmup entropy."""
    if not records:
        return "dim_unavailable"
    # Discard the first 20% of ticks (rounded up, minimum 1) as warmup.
    warmup_count = max(1, math.ceil(len(records) * 0.2))
    post_warmup = records[warmup_count:]
    if not post_warmup:
        return "dim_unavailable"
    act_types = [r.get("llm_output", {}).get("act_type") for r in post_warmup]
    act_types = [a for a in act_types if a]
    if not act_types:
        return "dim_unavailable"
    counts = Counter(act_types)
    total = sum(counts.values())
    entropy = -sum((c / total) * math.log2(c / total) for c in counts.values() if c > 0)
    if entropy > _DRIFT_THRESHOLDS["act_type_distribution_entropy"]:
        return "drift_positive"
    return "drift_neutral"


def _recalibration_recommendation(
    dim: str, abs_drift: float | None
) -> RecalibrationRecommendation:
    """Compute the recalibration recommendation for a single dim."""
    if abs_drift is None:
        return "n/a"
    if dim == "i_want_to_think_more_freq":
        if abs_drift > 0.20:
            return "raise_weight"
        if abs_drift < 0.05:
            return "lower_weight"
        return "hold"
    return "n/a"


def _extract_scalar_dim_value(record: dict, dim: str) -> float | None:
    """Extract a single scalar dim value from a per-tick record."""
    if dim in _DIM_TO_FAMILY and _DIM_TO_FAMILY[dim] == "hormone":
        h = record.get("hormone_state", {})
        v = h.get(dim)
        return float(v) if v is not None else None
    if dim in _DIM_TO_FAMILY and _DIM_TO_FAMILY[dim] == "feeling":
        f = record.get("feeling_state", {})
        v = f.get(dim)
        return float(v) if v is not None else None
    if dim in _DIM_TO_FAMILY and _DIM_TO_FAMILY[dim] == "salience":
        s = record.get("salience", {})
        if dim == "aggregate_salience":
            v = s.get("aggregate")
        else:
            all_dims = s.get("all_dimensions", {})
            v = all_dims.get(dim)
        return float(v) if v is not None else None
    if dim in _DIM_TO_FAMILY and _DIM_TO_FAMILY[dim] == "behavior" and dim != "act_type_distribution":
        # Derive behavior freq from the LLM envelope.
        # If the key is absent in the envelope, return None so the dim
        # is treated as dim_unavailable (not 0.0).
        llm = record.get("llm_output", {})
        if dim == "i_want_to_say_freq":
            raw = llm.get("i_want_to_say")
        elif dim == "i_send_through_freq":
            raw = llm.get("i_will_send_it")
        elif dim == "i_want_to_think_more_freq":
            raw = llm.get("i_want_to_think_more")
        elif dim == "remember_this_freq":
            raw = llm.get("remember_this")
        else:
            raw = None
        if raw is None:
            return None
        return 1.0 if raw else 0.0
    return None


@dataclass(frozen=True)
class AggressiveRadicalDriftEvaluator:
    """Per-scenario drift evaluator. Consumes R79-D JSONL output.

    The evaluator is a pure aggregator: it reads a JSONL file produced
    by the R79-D framework's `run_experiment` and produces a
    `DriftEvaluationReport`. It does not mutate any state and does not
    own any cross-cutting salience-to-channel policy.
    """

    jsonl_path: Path

    def evaluate(self) -> DriftEvaluationReport:
        if not self.jsonl_path.exists():
            raise FileNotFoundError(
                f"AggressiveRadicalDriftEvaluator: JSONL not found: {self.jsonl_path}"
            )
        records = [
            json.loads(line)
            for line in self.jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        scenario_id = self.jsonl_path.stem
        return _build_report(scenario_id, records)


def _build_report(scenario_id: str, records: list[dict]) -> DriftEvaluationReport:
    """Build a DriftEvaluationReport from a list of per-tick records."""
    results: list[DriftEvaluationResult] = []
    for dim in _ALL_DIMS:
        if dim == "act_type_distribution":
            classification = _classify_act_type_distribution(records)
            result = DriftEvaluationResult(
                scenario_id=scenario_id,
                family="behavior",
                dim=dim,
                start_value=None,
                end_value=None,
                min_value=None,
                max_value=None,
                abs_drift=None,
                range_drift=None,
                classification=classification,
                sample_count=len(records),
                recalibration_recommendation="n/a",
            )
        else:
            values = [
                v for v in (_extract_scalar_dim_value(r, dim) for r in records)
                if v is not None
            ]
            if not values:
                result = DriftEvaluationResult(
                    scenario_id=scenario_id,
                    family=_DIM_TO_FAMILY[dim],
                    dim=dim,
                    start_value=None, end_value=None,
                    min_value=None, max_value=None,
                    abs_drift=None, range_drift=None,
                    classification="dim_unavailable",
                    sample_count=0,
                    recalibration_recommendation="n/a",
                )
            else:
                start_value = values[0]
                end_value = values[-1]
                min_value = min(values)
                max_value = max(values)
                abs_drift = end_value - start_value
                range_drift = max_value - min_value
                classification = _classify_drift(dim, abs_drift)
                result = DriftEvaluationResult(
                    scenario_id=scenario_id,
                    family=_DIM_TO_FAMILY[dim],
                    dim=dim,
                    start_value=start_value,
                    end_value=end_value,
                    min_value=min_value,
                    max_value=max_value,
                    abs_drift=abs_drift,
                    range_drift=range_drift,
                    classification=classification,
                    sample_count=len(values),
                    recalibration_recommendation=_recalibration_recommendation(dim, abs_drift),
                )
        results.append(result)
    family_summaries = _family_summaries(results)
    overall_drift_score = _overall_drift_score(results)
    return DriftEvaluationReport(
        scenario_id=scenario_id,
        tick_count=len(records),
        results=tuple(results),
        family_summaries=family_summaries,
        overall_drift_score=overall_drift_score,
    )


def _family_summaries(
    results: list[DriftEvaluationResult],
) -> dict[str, dict[str, int]]:
    """Compute per-family drift classification counts."""
    family_counts: dict[str, dict[str, int]] = {}
    for family in ("hormone", "feeling", "salience", "behavior"):
        family_counts[family] = {
            "drift_positive": 0,
            "drift_negative": 0,
            "drift_neutral": 0,
            "dim_unavailable": 0,
        }
    for r in results:
        family_counts[r.family][r.classification] += 1
    return family_counts


def _overall_drift_score(results: list[DriftEvaluationResult]) -> float:
    """Compute the mean abs_drift across the 12 scalar dims in [0, 1]."""
    abs_drifts = [
        abs(r.abs_drift) for r in results
        if r.dim in _SCALAR_DIMS and r.abs_drift is not None
    ]
    if not abs_drifts:
        return 0.0
    return min(1.0, max(0.0, sum(abs_drifts) / len(abs_drifts)))


__all__ = [
    "AggressiveRadicalDriftEvaluator",
    "DriftEvaluationReport",
    "DriftEvaluationResult",
    "is_p5_launch_gate_open",
]
