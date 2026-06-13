"""R89 long-run Turing-style evaluation harness core.

`evaluate_turing(long_run_report, drift_report, config, injected_scores)` scores the six §13.4 rubric
axes into a `TuringVerdict`. It is read-only and offline: no runtime, no mutation, no network, no model
call, and no `print`/`logging` (R21 discipline). It asserts nothing; a consuming test renders/asserts.

Locked discipline (`ARCHITECTURE_PHILOSOPHY.zh-CN.md` §13.4):
  - Dual similarity: a BEHAVIOR dimension and an INTERNAL causal-chain dimension; behavior-only (or
    internal-only) must not pass.
  - Evidence anchoring: every score points to runtime provenance; an available score without
    provenance is forced to 0.0.
  - Conservative risk-averse aggregation: a lower-quantile per dimension, the min across the two
    dimensions, any-available-axis-collapse fails, >= pass_threshold to pass.
  - Anti-theatrical: a stubbed or unavailable axis cannot contribute a passing score; it forces the
    verdict to `incomplete`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final, Mapping

from r83_long_runner import TRACKED_FIELD_BOUNDS

# Drift-class / divergence constants we read from the R88 report (string-compared, no import coupling).
from r88_drift_evaluator import DIM_UNAVAILABLE


# --- rubric axes and dimensions ------------------------------------------------------------------

LINGUISTIC_NATURALNESS: Final = "linguistic_naturalness"
BIO_RESPONSIVENESS: Final = "bio_responsiveness"
MEMORY_FIDELITY: Final = "memory_fidelity"
AGENCY_LOCKING: Final = "agency_locking"
CROSS_TICK_CONTINUITY: Final = "cross_tick_continuity"
STIMULUS_RESPONSE_COHERENCE: Final = "stimulus_response_coherence"

DIMENSION_BEHAVIOR: Final = "behavior"
DIMENSION_INTERNAL: Final = "internal"

# The §13.4 axis -> dimension assignment. Behavior = externally-observable similarity (needs real
# afferents + a judge); internal = reconstructable causal-chain similarity.
_AXIS_DIMENSION: Final = {
    LINGUISTIC_NATURALNESS: DIMENSION_BEHAVIOR,
    STIMULUS_RESPONSE_COHERENCE: DIMENSION_BEHAVIOR,
    BIO_RESPONSIVENESS: DIMENSION_INTERNAL,
    MEMORY_FIDELITY: DIMENSION_INTERNAL,
    AGENCY_LOCKING: DIMENSION_INTERNAL,
    CROSS_TICK_CONTINUITY: DIMENSION_INTERNAL,
}
_ALL_AXES: Final = tuple(_AXIS_DIMENSION)


# --- availability and judge tracks ---------------------------------------------------------------

AVAILABLE: Final = "available"
STUBBED: Final = "stubbed_pending_real_probe"
UNAVAILABLE: Final = "unavailable_needs_real_afferent"

RECONSTRUCTED: Final = "reconstructed"
LLM_JUDGE: Final = "llm_judge"
HUMAN: Final = "human"


@dataclass(frozen=True)
class InjectedAxisScore:
    """A caller-supplied judge score for one axis (models the §13.4 human / LLM-judge dual track).

    `provenance` must name the evidence the judge anchored to; an empty/blank provenance forces the
    score to 0.0 (evidence anchoring).
    """

    score: float
    provenance: str
    judge_track: str = LLM_JUDGE


@dataclass(frozen=True)
class TuringConfig:
    """Locked-rubric configuration for one Turing-style evaluation."""

    pass_threshold: float = 0.80
    axis_collapse_threshold: float = 0.50
    lower_quantile: float = 0.25
    memory_fidelity_stub: float = 0.5
    movement_epsilon: float = 1e-3
    affect_prefixes: tuple[str, ...] = ("04", "05")
    expected_dimensions: frozenset[str] | None = None

    def resolved_expected(self) -> frozenset[str]:
        if self.expected_dimensions is not None:
            return self.expected_dimensions
        return frozenset(TRACKED_FIELD_BOUNDS)


@dataclass(frozen=True)
class AxisScore:
    """The scored result for one rubric axis."""

    axis: str
    dimension: str
    score: float
    availability: str
    judge_track: str
    provenance: str

    @property
    def counts_toward_pass(self) -> bool:
        return self.availability == AVAILABLE


@dataclass
class TuringVerdict:
    """The structured outcome of one Turing-style evaluation (no logging; a test renders/asserts)."""

    axis_scores: dict[str, AxisScore] = field(default_factory=dict)
    behavior_dimension_score: float | None = None
    internal_dimension_score: float | None = None
    aggregate: float | None = None
    completeness: str = "incomplete"
    collapsed_axes: tuple[str, ...] = ()
    unavailable_axes: tuple[str, ...] = ()
    stubbed_axes: tuple[str, ...] = ()
    pass_threshold: float = 0.80
    reason: str | None = None

    @property
    def passes(self) -> bool:
        return (
            self.reason is None
            and self.completeness == "complete"
            and self.aggregate is not None
            and self.aggregate >= self.pass_threshold
            and not self.collapsed_axes
        )

    def violations(self) -> list[str]:
        out: list[str] = []
        if self.reason is not None:
            out.append(f"reason: {self.reason}")
        if self.completeness != "complete":
            if self.unavailable_axes:
                out.append("unavailable axes: " + ", ".join(self.unavailable_axes))
            if self.stubbed_axes:
                out.append("stubbed axes: " + ", ".join(self.stubbed_axes))
        if self.behavior_dimension_score is None:
            out.append("behavior dimension has no available axis")
        if self.internal_dimension_score is None:
            out.append("internal dimension has no available axis")
        if self.aggregate is not None and self.aggregate < self.pass_threshold:
            out.append(f"aggregate {self.aggregate:.4f} < {self.pass_threshold}")
        for axis in self.collapsed_axes:
            score = self.axis_scores[axis].score
            out.append(f"{axis}: collapsed ({score:.4f})")
        return out

    def summary(self) -> str:
        agg = "n/a" if self.aggregate is None else f"{self.aggregate:.4f}"
        beh = "n/a" if self.behavior_dimension_score is None else f"{self.behavior_dimension_score:.4f}"
        int_ = "n/a" if self.internal_dimension_score is None else f"{self.internal_dimension_score:.4f}"
        lines = [
            f"R89 turing: verdict={'PASS' if self.passes else 'NOT-PASS'} "
            f"completeness={self.completeness} aggregate={agg} (behavior={beh} internal={int_})",
            "  axes:",
        ]
        for axis in _ALL_AXES:
            score = self.axis_scores.get(axis)
            if score is None:
                continue
            lines.append(
                f"    {axis} [{score.dimension}]: {score.score:.4f} "
                f"({score.availability}/{score.judge_track}) <- {score.provenance}"
            )
        violations = self.violations()
        if violations:
            lines.append("  violations: " + "; ".join(violations))
        return "\n".join(lines)


# --- reconstruction helpers ----------------------------------------------------------------------


def _affect_dims(config: TuringConfig) -> tuple[str, ...]:
    expected = config.resolved_expected()
    return tuple(
        name for name in sorted(expected) if name.split(".", 1)[0] in config.affect_prefixes
    )


def _dim_is_healthy(drift_report, name: str) -> bool:
    dim = drift_report.dimensions.get(name)
    if dim is None:
        return False
    return dim.drift_class != DIM_UNAVAILABLE and not dim.is_divergent


def _dim_moved(long_run_report, name: str, epsilon: float) -> bool:
    stat = long_run_report.field_stats.get(name)
    if stat is None or stat.observations == 0:
        return False
    if not math.isfinite(stat.minimum) or not math.isfinite(stat.maximum):
        return False
    return (stat.maximum - stat.minimum) > epsilon


def _score_bio_responsiveness(long_run_report, drift_report, config: TuringConfig) -> AxisScore:
    affect = _affect_dims(config)
    if not affect:
        return _unavailable_axis(BIO_RESPONSIVENESS, "no affect dimensions in expected set")
    health = sum(1 for name in affect if _dim_is_healthy(drift_report, name)) / len(affect)
    movement = sum(
        1 for name in affect if _dim_moved(long_run_report, name, config.movement_epsilon)
    ) / len(affect)
    score = 0.5 * health + 0.5 * movement
    return AxisScore(
        axis=BIO_RESPONSIVENESS,
        dimension=DIMENSION_INTERNAL,
        score=score,
        availability=AVAILABLE,
        judge_track=RECONSTRUCTED,
        provenance=(
            f"R88 affect health={health:.3f} (non-divergent, classifiable) + "
            f"R83 affect movement={movement:.3f} (field-stat range > {config.movement_epsilon})"
        ),
    )


def _score_cross_tick_continuity(long_run_report, drift_report, config: TuringConfig) -> AxisScore:
    completion = 1.0 if getattr(long_run_report, "completed_all", False) else 0.0
    cont_stat = long_run_report.field_stats.get("09.continuation_level")
    cont_dim = drift_report.dimensions.get("09.continuation_level")
    continuity_tracked = (
        1.0
        if (
            cont_stat is not None
            and cont_stat.observations > 0
            and cont_stat.ok
            and cont_dim is not None
            and cont_dim.drift_class != DIM_UNAVAILABLE
        )
        else 0.0
    )
    affect = _affect_dims(config)
    affect_carry = (
        1.0
        if any(_dim_moved(long_run_report, name, config.movement_epsilon) for name in affect)
        else 0.0
    )
    score = (completion + continuity_tracked + affect_carry) / 3.0
    return AxisScore(
        axis=CROSS_TICK_CONTINUITY,
        dimension=DIMENSION_INTERNAL,
        score=score,
        availability=AVAILABLE,
        judge_track=RECONSTRUCTED,
        provenance=(
            f"R83 completion={completion:.0f} + continuation_level tracked={continuity_tracked:.0f} "
            f"+ cross-tick affect carry={affect_carry:.0f}"
        ),
    )


def _score_agency_locking(drift_report, config: TuringConfig) -> AxisScore:
    expected = sorted(config.resolved_expected())
    if not expected:
        return _unavailable_axis(AGENCY_LOCKING, "no expected owner dimensions")
    healthy = sum(1 for name in expected if _dim_is_healthy(drift_report, name))
    score = healthy / len(expected)
    return AxisScore(
        axis=AGENCY_LOCKING,
        dimension=DIMENSION_INTERNAL,
        score=score,
        availability=AVAILABLE,
        judge_track=RECONSTRUCTED,
        provenance=(
            f"R88 owner-state proxy: {healthy}/{len(expected)} expected owner dims present, "
            "classifiable, non-divergent (real bounded owner state, not prompt theater); "
            "PARTIAL proxy — full agency-locking via 21/17 owner-decision provenance deferred"
        ),
    )


def _stubbed_axis(axis: str, dimension: str, value: float) -> AxisScore:
    return AxisScore(
        axis=axis,
        dimension=dimension,
        score=value,
        availability=STUBBED,
        judge_track=RECONSTRUCTED,
        provenance="stub_pending_R90",
    )


def _unavailable_axis(axis: str, why: str) -> AxisScore:
    return AxisScore(
        axis=axis,
        dimension=_AXIS_DIMENSION[axis],
        score=0.0,
        availability=UNAVAILABLE,
        judge_track=RECONSTRUCTED,
        provenance=f"unavailable: {why}",
    )


def _injected_axis(axis: str, injected: InjectedAxisScore) -> AxisScore:
    # Evidence anchoring: an available judge score without provenance is not a real score.
    has_provenance = bool(injected.provenance and injected.provenance.strip())
    score = injected.score if has_provenance else 0.0
    provenance = injected.provenance if has_provenance else "MISSING PROVENANCE -> forced 0.0"
    return AxisScore(
        axis=axis,
        dimension=_AXIS_DIMENSION[axis],
        score=score,
        availability=AVAILABLE,
        judge_track=injected.judge_track,
        provenance=provenance,
    )


def _lower_quantile(values: list[float], quantile: float) -> float:
    """Nearest-rank lower quantile (risk-averse; approaches the minimum for small n)."""

    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    # nearest-rank: rank = ceil(quantile * n), 1-indexed, clamped to [1, n].
    rank = max(1, min(len(ordered), math.ceil(quantile * len(ordered))))
    return ordered[rank - 1]


# --- public entry point --------------------------------------------------------------------------


def evaluate_turing(
    long_run_report,
    drift_report,
    config: TuringConfig = TuringConfig(),
    injected_scores: Mapping[str, InjectedAxisScore] | None = None,
) -> TuringVerdict:
    """Score the six §13.4 rubric axes into a `TuringVerdict` (read-only, deterministic, offline)."""

    injected = dict(injected_scores or {})

    if long_run_report is None or drift_report is None:
        return TuringVerdict(
            pass_threshold=config.pass_threshold,
            reason="missing_report",
            unavailable_axes=_ALL_AXES,
        )
    if getattr(long_run_report, "ticks_completed", 0) <= 0 or not getattr(
        drift_report, "dimensions", None
    ):
        return TuringVerdict(
            pass_threshold=config.pass_threshold,
            reason="empty_report",
            unavailable_axes=_ALL_AXES,
        )

    axis_scores: dict[str, AxisScore] = {}
    for axis in _ALL_AXES:
        if axis in injected:
            axis_scores[axis] = _injected_axis(axis, injected[axis])
            continue
        if axis == BIO_RESPONSIVENESS:
            axis_scores[axis] = _score_bio_responsiveness(long_run_report, drift_report, config)
        elif axis == CROSS_TICK_CONTINUITY:
            axis_scores[axis] = _score_cross_tick_continuity(long_run_report, drift_report, config)
        elif axis == AGENCY_LOCKING:
            axis_scores[axis] = _score_agency_locking(drift_report, config)
        elif axis == MEMORY_FIDELITY:
            axis_scores[axis] = _stubbed_axis(
                MEMORY_FIDELITY, DIMENSION_INTERNAL, config.memory_fidelity_stub
            )
        else:  # behavior axes with no injection
            axis_scores[axis] = _unavailable_axis(
                axis, "needs real afferent + calibrated human/LLM judge"
            )

    return _finalize_verdict(axis_scores, config)


def _finalize_verdict(axis_scores: dict[str, AxisScore], config: TuringConfig) -> TuringVerdict:
    behavior_available = [
        s.score
        for s in axis_scores.values()
        if s.dimension == DIMENSION_BEHAVIOR and s.availability == AVAILABLE
    ]
    internal_available = [
        s.score
        for s in axis_scores.values()
        if s.dimension == DIMENSION_INTERNAL and s.availability == AVAILABLE
    ]

    behavior_score = (
        _lower_quantile(behavior_available, config.lower_quantile) if behavior_available else None
    )
    internal_score = (
        _lower_quantile(internal_available, config.lower_quantile) if internal_available else None
    )
    aggregate = (
        min(behavior_score, internal_score)
        if behavior_score is not None and internal_score is not None
        else None
    )

    collapsed = tuple(
        axis
        for axis in _ALL_AXES
        if axis_scores[axis].availability == AVAILABLE
        and axis_scores[axis].score < config.axis_collapse_threshold
    )
    unavailable = tuple(
        axis for axis in _ALL_AXES if axis_scores[axis].availability == UNAVAILABLE
    )
    stubbed = tuple(axis for axis in _ALL_AXES if axis_scores[axis].availability == STUBBED)
    completeness = "complete" if not unavailable and not stubbed else "incomplete"

    return TuringVerdict(
        axis_scores=axis_scores,
        behavior_dimension_score=behavior_score,
        internal_dimension_score=internal_score,
        aggregate=aggregate,
        completeness=completeness,
        collapsed_axes=collapsed,
        unavailable_axes=unavailable,
        stubbed_axes=stubbed,
        pass_threshold=config.pass_threshold,
        reason=None,
    )
