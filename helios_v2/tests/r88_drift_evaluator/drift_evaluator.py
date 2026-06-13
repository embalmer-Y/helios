"""R88 behavioral-drift evaluator core.

`evaluate_drift(samples, config)` consumes an iterable of already-parsed R83 JSONL sample mappings
(each carrying meta keys plus `NN.field` owner dimensions) and returns a `DriftReport` classifying
every owner dimension's long-horizon drift. It is read-only and offline: no runtime, no mutation, no
network, no model call, and no `print`/`logging` (R21 discipline). It asserts nothing; a consuming
test renders/asserts on the report.

Drift classification is direction-only. `drift_positive`/`drift_negative` denote the SIGN of the
cross-window change (late-window mean minus early-window mean), NOT a quality or value judgment: a
rising cortisol is `drift_positive`, not "good". Insufficient data is `dim_unavailable` (honest
absence), never a fabricated `drift_neutral`.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Final, Iterable, Mapping, Sequence

# The R83 package supplies the shared legal-range / expected-dimension source. The `__init__` of this
# package puts `tests/` on `sys.path`, so this flat import resolves the sibling R83 harness.
from r83_long_runner import TRACKED_FIELD_BOUNDS


# Drift classes (string constants so a report renders/serializes plainly and a test compares directly).
DRIFT_POSITIVE: Final = "drift_positive"
DRIFT_NEGATIVE: Final = "drift_negative"
DRIFT_NEUTRAL: Final = "drift_neutral"
DIM_UNAVAILABLE: Final = "dim_unavailable"

# Divergence flags (saturation toward a legal bound while drifting in that direction).
DIVERGENCE_NONE: Final = "none"
DIVERGENCE_HIGH: Final = "divergent_high"
DIVERGENCE_LOW: Final = "divergent_low"

# Trace meta keys that are NOT owner dimensions.
_META_KEYS: Final = frozenset({"tick", "tick_duration_ms", "store_count", "memory_mb"})

# An owner dimension key is a two-digit owner prefix, a dot, then the field (e.g. `04.dopamine`).
_OWNER_DIM_PATTERN: Final = re.compile(r"^\d\d\..+")

# A tiny tolerance so a normalized delta landing exactly on the neutral-band edge (subject to float
# representation, e.g. 0.52 - 0.50 == 0.020000000000000018) classifies neutral, not directional.
# This makes the documented `<= neutral_band` boundary robust, mirroring R83's `_RANGE_EPSILON`.
_CLASSIFY_EPSILON: Final = 1e-9


@dataclass(frozen=True)
class DriftConfig:
    """Configuration for one drift evaluation.

    `expected_dimensions` / `dimension_bounds` default to the R83 tracked set so a vanilla R83 trace
    is fully checked; pass explicit values to evaluate a different trace shape.
    """

    window_fraction: float = 0.25
    neutral_band: float = 0.02
    min_samples_for_trend: int = 4
    saturation_margin: float = 0.02
    expected_dimensions: frozenset[str] | None = None
    dimension_bounds: Mapping[str, tuple[float, float]] | None = None

    def resolved_expected(self) -> frozenset[str]:
        if self.expected_dimensions is not None:
            return self.expected_dimensions
        return frozenset(TRACKED_FIELD_BOUNDS)

    def resolved_bounds(self) -> Mapping[str, tuple[float, float]]:
        if self.dimension_bounds is not None:
            return self.dimension_bounds
        return TRACKED_FIELD_BOUNDS


@dataclass(frozen=True)
class DimensionDrift:
    """The classified long-horizon drift of one owner dimension over the trace."""

    name: str
    owner: str
    samples: int
    early_mean: float
    late_mean: float
    delta: float
    normalized_delta: float
    minimum: float
    maximum: float
    late_spread: float
    drift_class: str
    divergence: str

    @property
    def available(self) -> bool:
        return self.drift_class != DIM_UNAVAILABLE

    @property
    def is_divergent(self) -> bool:
        return self.divergence != DIVERGENCE_NONE


@dataclass
class DriftReport:
    """The structured outcome of one drift evaluation (no logging; a test renders/asserts on it)."""

    source: str
    total_samples: int
    dimensions: dict[str, DimensionDrift] = field(default_factory=dict)
    expected_dimensions: frozenset[str] = frozenset()
    missing_dimensions: tuple[str, ...] = ()
    divergent_dimensions: tuple[str, ...] = ()
    class_counts: dict[str, int] = field(default_factory=dict)
    min_samples_for_trend: int = 4
    parse_reason: str | None = None

    @property
    def analysis_ok(self) -> bool:
        return (
            self.parse_reason is None
            and self.total_samples >= self.min_samples_for_trend
            and not self.missing_dimensions
            and not self.divergent_dimensions
        )

    def violations(self) -> list[str]:
        out: list[str] = []
        if self.parse_reason is not None:
            out.append(f"parse: {self.parse_reason}")
        if self.total_samples < self.min_samples_for_trend:
            out.append(
                f"insufficient samples: {self.total_samples} < {self.min_samples_for_trend}"
            )
        if self.missing_dimensions:
            out.append("missing expected dimensions: " + ", ".join(self.missing_dimensions))
        for name in self.divergent_dimensions:
            dim = self.dimensions.get(name)
            flag = dim.divergence if dim is not None else "divergent"
            out.append(f"{name}: {flag}")
        return out

    def summary(self) -> str:
        lines = [
            f"R88 drift: source={self.source} samples={self.total_samples} "
            f"verdict={'OK' if self.analysis_ok else 'FAIL'}",
            "  class counts: "
            + ", ".join(f"{cls}={self.class_counts.get(cls, 0)}" for cls in _CLASS_ORDER),
            "  dimensions:",
        ]
        for name in sorted(self.dimensions):
            dim = self.dimensions[name]
            flag = "" if dim.divergence == DIVERGENCE_NONE else f" [{dim.divergence}]"
            lines.append(
                f"    {name}: {dim.drift_class} "
                f"(early={dim.early_mean:.4f} late={dim.late_mean:.4f} "
                f"delta={dim.delta:+.4f} norm={dim.normalized_delta:+.4f} n={dim.samples}){flag}"
            )
        violations = self.violations()
        if violations:
            lines.append("  violations: " + "; ".join(violations))
        return "\n".join(lines)


_CLASS_ORDER: Final = (DRIFT_POSITIVE, DRIFT_NEGATIVE, DRIFT_NEUTRAL, DIM_UNAVAILABLE)


def load_samples(path: str) -> list[dict]:
    """Parse a JSONL trace file into a list of sample dicts.

    Each non-blank line is JSON-decoded; an un-decodable line is skipped (the caller can detect skips
    by comparing the returned count against the file's non-blank line count). Never raises on a
    routine malformed line.
    """

    samples: list[dict] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                samples.append(decoded)
    return samples


def _is_real_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _classify_dimension(
    name: str,
    values: list[float],
    config: DriftConfig,
    bounds: Mapping[str, tuple[float, float]],
) -> DimensionDrift:
    owner = name.split(".", 1)[0]
    count = len(values)
    if count < config.min_samples_for_trend:
        return DimensionDrift(
            name=name,
            owner=owner,
            samples=count,
            early_mean=0.0,
            late_mean=0.0,
            delta=0.0,
            normalized_delta=0.0,
            minimum=min(values) if values else 0.0,
            maximum=max(values) if values else 0.0,
            late_spread=0.0,
            drift_class=DIM_UNAVAILABLE,
            divergence=DIVERGENCE_NONE,
        )

    window = max(1, int(math.floor(count * config.window_fraction)))
    early = values[:window]
    late = values[-window:]
    early_mean = _mean(early)
    late_mean = _mean(late)
    delta = late_mean - early_mean

    known_bounds = name in bounds
    if known_bounds:
        low, high = bounds[name]
        legal_range = high - low
    else:
        low, high = min(values), max(values)
        legal_range = high - low

    normalized_delta = delta / legal_range if legal_range > 0 else 0.0

    if abs(normalized_delta) <= config.neutral_band + _CLASSIFY_EPSILON:
        drift_class = DRIFT_NEUTRAL
    elif normalized_delta > 0:
        drift_class = DRIFT_POSITIVE
    else:
        drift_class = DRIFT_NEGATIVE

    divergence = DIVERGENCE_NONE
    if known_bounds and legal_range > 0:
        margin = config.saturation_margin * legal_range
        if drift_class == DRIFT_POSITIVE and late_mean >= high - margin:
            divergence = DIVERGENCE_HIGH
        elif drift_class == DRIFT_NEGATIVE and late_mean <= low + margin:
            divergence = DIVERGENCE_LOW

    return DimensionDrift(
        name=name,
        owner=owner,
        samples=count,
        early_mean=early_mean,
        late_mean=late_mean,
        delta=delta,
        normalized_delta=normalized_delta,
        minimum=min(values),
        maximum=max(values),
        late_spread=max(late) - min(late),
        drift_class=drift_class,
        divergence=divergence,
    )


def evaluate_drift(
    samples: Iterable[Mapping[str, object]], config: DriftConfig = DriftConfig()
) -> DriftReport:
    """Classify each owner dimension's long-horizon drift over `samples`.

    Order-preserving: the R83 JSONL is already tick-ordered and the evaluator does not re-sort. A
    missing / non-numeric / NaN / inf field on a tick contributes no observation for that dimension.
    """

    expected = config.resolved_expected()
    bounds = config.resolved_bounds()

    sample_list = list(samples)
    if not sample_list:
        dimensions = {
            name: _classify_dimension(name, [], config, bounds) for name in sorted(expected)
        }
        return _finalize_report(
            source="<samples>",
            total_samples=0,
            dimensions=dimensions,
            expected=expected,
            config=config,
            parse_reason="empty_trace",
        )

    observations: dict[str, list[float]] = {}
    for sample in sample_list:
        for key, value in sample.items():
            if key in _META_KEYS or not _OWNER_DIM_PATTERN.match(key):
                continue
            if _is_real_number(value):
                observations.setdefault(key, []).append(float(value))

    discovered = set(observations) | set(expected)
    dimensions = {
        name: _classify_dimension(name, observations.get(name, []), config, bounds)
        for name in sorted(discovered)
    }

    return _finalize_report(
        source="<samples>",
        total_samples=len(sample_list),
        dimensions=dimensions,
        expected=expected,
        config=config,
        parse_reason=None,
    )


def evaluate_trace_file(path: str, config: DriftConfig = DriftConfig()) -> DriftReport:
    """Load a JSONL trace file and evaluate its drift, recording the file path as the report source."""

    samples = load_samples(path)
    report = evaluate_drift(samples, config)
    report.source = path
    return report


def _finalize_report(
    *,
    source: str,
    total_samples: int,
    dimensions: dict[str, DimensionDrift],
    expected: frozenset[str],
    config: DriftConfig,
    parse_reason: str | None,
) -> DriftReport:
    class_counts: dict[str, int] = {cls: 0 for cls in _CLASS_ORDER}
    for dim in dimensions.values():
        class_counts[dim.drift_class] = class_counts.get(dim.drift_class, 0) + 1

    missing = tuple(
        name
        for name in sorted(expected)
        if name not in dimensions or dimensions[name].drift_class == DIM_UNAVAILABLE
    )
    divergent = tuple(
        name for name in sorted(dimensions) if dimensions[name].is_divergent
    )

    return DriftReport(
        source=source,
        total_samples=total_samples,
        dimensions=dimensions,
        expected_dimensions=expected,
        missing_dimensions=missing,
        divergent_dimensions=divergent,
        class_counts=class_counts,
        min_samples_for_trend=config.min_samples_for_trend,
        parse_reason=parse_reason,
    )
