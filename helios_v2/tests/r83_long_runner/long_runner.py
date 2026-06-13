"""R83 reusable long-run harness.

`run_long_run(handle, config)` drives an assembled `RuntimeHandle` for `config.ticks` ticks and
returns a `LongRunReport`. It asserts nothing itself (a consuming test decides pass/fail from the
report) and emits no `print`/`logging` (R21 discipline). It is deterministic given a deterministic
runtime (the durable-but-repeatable production-shaped assembly with a deterministic thought driver).
"""

from __future__ import annotations

import math
import tracemalloc
from dataclasses import dataclass, field
from typing import Mapping


# Per-owner tracked fields and their legal bounds. 04 neuromodulator levels and 05 feeling
# dimensions are contract-clamped to [0, 1]; the 09 gate score is [0, 1]. The 18 outward drive is
# NOT a [0, 1] quantity (it crosses an action threshold ~1.6), so it is bounded only against a
# divergence ceiling: the check is "finite and below the divergence bound", not a unit interval.
TRACKED_FIELD_BOUNDS: dict[str, tuple[float, float]] = {
    # 04 neuromodulator levels
    "04.dopamine": (0.0, 1.0),
    "04.norepinephrine": (0.0, 1.0),
    "04.serotonin": (0.0, 1.0),
    "04.acetylcholine": (0.0, 1.0),
    "04.cortisol": (0.0, 1.0),
    "04.oxytocin": (0.0, 1.0),
    "04.opioid_tone": (0.0, 1.0),
    "04.excitation": (0.0, 1.0),
    "04.inhibition": (0.0, 1.0),
    # 05 interoceptive feeling
    "05.valence": (0.0, 1.0),
    "05.arousal": (0.0, 1.0),
    "05.tension": (0.0, 1.0),
    "05.comfort": (0.0, 1.0),
    "05.fatigue": (0.0, 1.0),
    "05.pain_like": (0.0, 1.0),
    "05.social_safety": (0.0, 1.0),
    # 09 gating
    "09.gate_score": (0.0, 1.0),
    "09.continuation_level": (0.0, 1.0),
    # 18 proactive drive (divergence ceiling, not a unit interval)
    "18.outward_drive": (0.0, 8.0),
}

# A tiny tolerance so a clamped value rounded to its legal edge is not flagged as out of range.
_RANGE_EPSILON = 1e-6


@dataclass
class FieldStat:
    """Running boundedness statistics for one tracked owner field over the run."""

    name: str
    legal_min: float
    legal_max: float
    observations: int = 0
    minimum: float = math.inf
    maximum: float = -math.inf
    last: float = math.nan
    nan_count: int = 0
    nonfinite_count: int = 0
    out_of_range_count: int = 0

    def observe(self, value: float) -> None:
        self.observations += 1
        self.last = value
        if isinstance(value, float) and math.isnan(value):
            self.nan_count += 1
            return
        if not math.isfinite(value):
            self.nonfinite_count += 1
            return
        self.minimum = min(self.minimum, value)
        self.maximum = max(self.maximum, value)
        if value < self.legal_min - _RANGE_EPSILON or value > self.legal_max + _RANGE_EPSILON:
            self.out_of_range_count += 1

    @property
    def ok(self) -> bool:
        return self.nan_count == 0 and self.nonfinite_count == 0 and self.out_of_range_count == 0


@dataclass
class LongRunConfig:
    """Configuration for one long run."""

    ticks: int
    sample_every: int = 0  # 0 -> auto (about 50 evenly-spaced samples)
    memory_ceiling_mb: float = 500.0

    def resolved_sample_every(self) -> int:
        if self.sample_every > 0:
            return self.sample_every
        return max(1, self.ticks // 50)


@dataclass
class LongRunReport:
    """The structured outcome of one long run (no logging; a test renders/asserts on it)."""

    ticks_requested: int
    ticks_completed: int = 0
    crash: str | None = None
    field_stats: dict[str, FieldStat] = field(default_factory=dict)
    evolution_samples: list[dict[str, float]] = field(default_factory=list)
    store_count_start: int = 0
    store_count_end: int = 0
    memory_start_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_end_mb: float = 0.0
    memory_ceiling_mb: float = 500.0

    @property
    def boundedness_ok(self) -> bool:
        return all(stat.ok for stat in self.field_stats.values())

    @property
    def memory_ok(self) -> bool:
        return self.memory_peak_mb <= self.memory_ceiling_mb

    @property
    def completed_all(self) -> bool:
        return self.crash is None and self.ticks_completed == self.ticks_requested

    @property
    def verdict_ok(self) -> bool:
        return self.completed_all and self.boundedness_ok and self.memory_ok

    def violations(self) -> list[str]:
        out: list[str] = []
        if self.crash is not None:
            out.append(f"crash: {self.crash}")
        if not self.completed_all:
            out.append(
                f"incomplete: {self.ticks_completed}/{self.ticks_requested} ticks"
            )
        for name, stat in self.field_stats.items():
            if stat.nan_count:
                out.append(f"{name}: {stat.nan_count} NaN")
            if stat.nonfinite_count:
                out.append(f"{name}: {stat.nonfinite_count} non-finite")
            if stat.out_of_range_count:
                out.append(
                    f"{name}: {stat.out_of_range_count} out of [{stat.legal_min},{stat.legal_max}]"
                )
        if not self.memory_ok:
            out.append(f"memory peak {self.memory_peak_mb:.1f}MB > {self.memory_ceiling_mb}MB")
        return out

    def summary(self) -> str:
        lines = [
            f"R83 long run: {self.ticks_completed}/{self.ticks_requested} ticks, "
            f"verdict={'PASS' if self.verdict_ok else 'FAIL'}",
            f"  store: {self.store_count_start} -> {self.store_count_end} records",
            f"  memory: start={self.memory_start_mb:.1f}MB peak={self.memory_peak_mb:.1f}MB "
            f"end={self.memory_end_mb:.1f}MB (ceiling {self.memory_ceiling_mb}MB)",
            "  owner boundedness:",
        ]
        for name, stat in self.field_stats.items():
            flag = "ok" if stat.ok else "VIOLATION"
            lines.append(
                f"    {name}: [{stat.minimum:.4f}, {stat.maximum:.4f}] "
                f"n={stat.observations} {flag}"
            )
        violations = self.violations()
        if violations:
            lines.append("  violations: " + "; ".join(violations))
        return "\n".join(lines)


def _extract_fields(result) -> dict[str, float]:
    """Extract the tracked per-owner bounded facts from one tick result (defensive, read-only)."""

    fields: dict[str, float] = {}
    stage_results = getattr(result, "stage_results", {}) or {}

    neuro = stage_results.get("neuromodulator_system")
    levels = getattr(getattr(neuro, "state", None), "levels", None)
    if levels is not None:
        for channel in (
            "dopamine",
            "norepinephrine",
            "serotonin",
            "acetylcholine",
            "cortisol",
            "oxytocin",
            "opioid_tone",
            "excitation",
            "inhibition",
        ):
            value = getattr(levels, channel, None)
            if isinstance(value, (int, float)):
                fields[f"04.{channel}"] = float(value)

    feeling_state = stage_results.get("interoceptive_feeling_layer")
    feeling = getattr(getattr(feeling_state, "state", None), "feeling", None)
    if feeling is not None:
        for dimension in (
            "valence",
            "arousal",
            "tension",
            "comfort",
            "fatigue",
            "pain_like",
            "social_safety",
        ):
            value = getattr(feeling, dimension, None)
            if isinstance(value, (int, float)):
                fields[f"05.{dimension}"] = float(value)

    gating = stage_results.get("thought_gating_and_continuation_pressure")
    gate_result = getattr(gating, "result", None)
    gate_score = getattr(gate_result, "gate_score", None)
    if isinstance(gate_score, (int, float)):
        fields["09.gate_score"] = float(gate_score)
    continuation = getattr(gating, "continuation_state", None)
    level = getattr(continuation, "level", None)
    if isinstance(level, (int, float)):
        fields["09.continuation_level"] = float(level)

    autonomy = stage_results.get("subjective_autonomy_and_proactive_evolution")
    drive_state = getattr(getattr(autonomy, "result", None), "drive_state", None)
    components = getattr(drive_state, "pressure_components", None)
    if isinstance(components, Mapping):
        outward = components.get("outward_drive")
        if isinstance(outward, (int, float)) and not isinstance(outward, bool):
            fields["18.outward_drive"] = float(outward)

    return fields


def _store_count(handle) -> int:
    store = getattr(handle, "experience_store", None)
    if store is None:
        return 0
    try:
        return int(store.count())
    except Exception:  # noqa: BLE001 - count is diagnostic only; never fail the run on it
        return -1


def run_long_run(handle, config: LongRunConfig) -> LongRunReport:
    """Drive `handle` for `config.ticks` ticks and return a `LongRunReport`.

    The runtime must already be started (`handle.startup()`), since the harness only exercises the
    per-tick path. A per-tick exception is captured as a crash (the run stops at that tick); the
    report records how far it got. Per tracked owner field it records min/max/NaN/non-finite/
    out-of-range over the whole run, and it samples the evolution curve at `sample_every`.
    """

    report = LongRunReport(
        ticks_requested=config.ticks,
        memory_ceiling_mb=config.memory_ceiling_mb,
    )
    for name, (low, high) in TRACKED_FIELD_BOUNDS.items():
        report.field_stats[name] = FieldStat(name=name, legal_min=low, legal_max=high)

    report.store_count_start = _store_count(handle)
    sample_every = config.resolved_sample_every()

    tracing = not tracemalloc.is_tracing()
    if tracing:
        tracemalloc.start()
    start_current, _ = tracemalloc.get_traced_memory()
    report.memory_start_mb = start_current / (1024 * 1024)

    for tick_index in range(config.ticks):
        try:
            result = handle.tick()
        except Exception as error:  # noqa: BLE001 - a per-tick crash is the headline fact
            report.crash = f"tick {tick_index}: {type(error).__name__}: {error}"
            break
        report.ticks_completed += 1
        fields = _extract_fields(result)
        for name, value in fields.items():
            stat = report.field_stats.get(name)
            if stat is not None:
                stat.observe(value)
        if tick_index % sample_every == 0:
            sample = {"tick": float(tick_index)}
            sample.update(fields)
            report.evolution_samples.append(sample)

    current, peak = tracemalloc.get_traced_memory()
    report.memory_end_mb = current / (1024 * 1024)
    report.memory_peak_mb = peak / (1024 * 1024)
    if tracing:
        tracemalloc.stop()

    report.store_count_end = _store_count(handle)
    return report
