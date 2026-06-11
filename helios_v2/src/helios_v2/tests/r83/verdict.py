"""R83 verdict logic.

Pure functions for computing the overall pass/fail verdict from a
frozen `R83Scores` dataclass. No I/O, no LLM calls, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VerdictLabel = Literal["human-like", "needs-recalibration"]

AXIS_NAMES: tuple[str, ...] = (
    "A1_linguistic_naturalness",
    "A2_bio_responsiveness",
    "A3_memory_fidelity",
    "A4_agency_locking",
    "A5_cross_tick_continuity",
    "A6_stimulus_response_coherence",
)


@dataclass(frozen=True)
class Verdict:
    """The overall R83 verdict.

    Attributes:
        label: "human-like" iff mean >= threshold AND min >= min_floor;
            otherwise "needs-recalibration".
        mean_score: arithmetic mean of the 6 axis scores.
        min_axis: name of the lowest-scoring axis (e.g. "A3_memory_fidelity").
        min_score: the value of the lowest axis score.
        recalibration_targets: tuple of axis names whose score is
            strictly below `threshold` (the calibration intervention
            list for the next P5 learning loop).
    """

    label: VerdictLabel
    mean_score: float
    min_axis: str
    min_score: float
    recalibration_targets: tuple[str, ...]

    @classmethod
    def compute(
        cls,
        scores: "R83Scores",  # type: ignore[name-defined]  # noqa: F821
        *,
        threshold: float = 0.6,
        min_floor: float = 0.4,
    ) -> "Verdict":
        """Compute the verdict from a `R83Scores` instance.

        Args:
            scores: the per-axis scores (frozen dataclass with
                `a1_linguistic_naturalness` / `a2_bio_responsiveness` /
                `a3_memory_fidelity` / `a4_agency_locking` /
                `a5_cross_tick_continuity` /
                `a6_stimulus_response_coherence` fields).
            threshold: the mean + min floor for "human-like"
                (default 0.6). Recalibration targets are axes with
                score strictly below this.
            min_floor: the absolute floor for any single axis
                (default 0.4). A score below this flips the verdict
                to "needs-recalibration" even if the mean is high.

        Returns:
            A `Verdict` with `label` / `mean_score` / `min_axis` /
            `min_score` / `recalibration_targets`.
        """
        axis_values: dict[str, float] = {
            "A1_linguistic_naturalness": scores.a1_linguistic_naturalness,
            "A2_bio_responsiveness": scores.a2_bio_responsiveness,
            "A3_memory_fidelity": scores.a3_memory_fidelity,
            "A4_agency_locking": scores.a4_agency_locking,
            "A5_cross_tick_continuity": scores.a5_cross_tick_continuity,
            "A6_stimulus_response_coherence": scores.a6_stimulus_response_coherence,
        }
        min_axis = min(axis_values, key=lambda k: axis_values[k])
        min_score = axis_values[min_axis]
        mean_score = sum(axis_values.values()) / len(axis_values)
        recalibration_targets = tuple(
            name for name, value in axis_values.items() if value < threshold
        )
        if mean_score >= threshold and min_score >= min_floor:
            label: VerdictLabel = "human-like"
        else:
            label = "needs-recalibration"
        return cls(
            label=label,
            mean_score=mean_score,
            min_axis=min_axis,
            min_score=min_score,
            recalibration_targets=recalibration_targets,
        )
