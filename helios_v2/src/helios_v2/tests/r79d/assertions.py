"""R79-D assertion engine.

Each assertion is a function decorated with @register_assertion("name").
Scenarios reference them by name: {"name": "hormone_monotonic", "hormone": "dopamine"}.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .framework import TickRecord, AssertionResult


ASSERTION_REGISTRY: dict[str, Callable[..., AssertionResult]] = {}


def register_assertion(name: str):
    def decorator(fn):
        ASSERTION_REGISTRY[name] = fn
        return fn
    return decorator


def list_assertions() -> list[str]:
    return sorted(ASSERTION_REGISTRY.keys())


def _pass(name: str, detail: str, **kw) -> AssertionResult:
    return AssertionResult(name=name, passed=True, detail=detail, **kw)


def _fail(name: str, detail: str, **kw) -> AssertionResult:
    return AssertionResult(name=name, passed=False, detail=detail, **kw)


def _get_hormone_series(records, key):
    return [r["hormone_state"].get(key) for r in records if r.get("hormone_state", {}).get(key) is not None]


def _get_feeling_series(records, key):
    return [r["feeling_state"].get(key) for r in records if r.get("feeling_state", {}).get(key) is not None]


def _get_llm_field(records, field):
    return [r["llm_output"].get(field) for r in records]


def _non_null(xs):
    return [x for x in xs if x is not None]


# ============================================================
# Built-in assertions
# ============================================================


@register_assertion("hormone_monotonic")
def hormone_monotonic(records, hormone: str = "dopamine", direction: str = "increase", tolerance: float = 0.01) -> AssertionResult:
    """Assert that a hormone series is monotonic in the given direction."""
    series = _get_hormone_series(records, hormone)
    if len(series) < 2:
        return _fail("hormone_monotonic", f"need >=2 records, got {len(series)}")
    if direction == "increase":
        ok = all(series[i+1] >= series[i] - tolerance for i in range(len(series)-1))
    elif direction == "decrease":
        ok = all(series[i+1] <= series[i] + tolerance for i in range(len(series)-1))
    elif direction == "non_increasing":
        ok = all(series[i+1] <= series[i] + tolerance for i in range(len(series)-1))
    elif direction == "non_decreasing":
        ok = all(series[i+1] >= series[i] - tolerance for i in range(len(series)-1))
    else:
        return _fail("hormone_monotonic", f"unknown direction: {direction}")
    detail = f"{hormone}: {series[0]:.3f} -> {series[-1]:.3f} (n={len(series)})"
    return _pass("hormone_monotonic", detail) if ok else _fail("hormone_monotonic", detail)


@register_assertion("hormone_endpoint_delta")
def hormone_endpoint_delta(records, hormone: str = "dopamine", min_delta: float = 0.05) -> AssertionResult:
    series = _get_hormone_series(records, hormone)
    if len(series) < 2:
        return _fail("hormone_endpoint_delta", f"need >=2 records, got {len(series)}")
    delta = series[-1] - series[0]
    ok = abs(delta) >= min_delta
    detail = f"{hormone}: {series[0]:.3f} -> {series[-1]:.3f} (delta={delta:+.3f}, threshold={min_delta:+.3f})"
    return _pass("hormone_endpoint_delta", detail) if ok else _fail("hormone_endpoint_delta", detail)


@register_assertion("hormone_endpoint_sign")
def hormone_endpoint_sign(records, hormone: str = "dopamine", sign: str = "positive") -> AssertionResult:
    series = _get_hormone_series(records, hormone)
    if len(series) < 2:
        return _fail("hormone_endpoint_sign", f"need >=2 records, got {len(series)}")
    delta = series[-1] - series[0]
    if sign == "positive":
        ok = delta > 0
    elif sign == "negative":
        ok = delta < 0
    elif sign == "zero":
        ok = abs(delta) < 0.01
    else:
        return _fail("hormone_endpoint_sign", f"unknown sign: {sign}")
    detail = f"{hormone}: delta={delta:+.4f}, expected sign={sign}"
    return _pass("hormone_endpoint_sign", detail) if ok else _fail("hormone_endpoint_sign", detail)


@register_assertion("feeling_endpoint_delta")
def feeling_endpoint_delta(records, dim: str = "valence", min_delta: float = 0.05) -> AssertionResult:
    series = _get_feeling_series(records, dim)
    if len(series) < 2:
        return _fail("feeling_endpoint_delta", f"need >=2 records, got {len(series)}")
    delta = series[-1] - series[0]
    ok = abs(delta) >= min_delta
    detail = f"{dim}: {series[0]:.3f} -> {series[-1]:.3f} (delta={delta:+.3f}, threshold={min_delta:+.3f})"
    return _pass("feeling_endpoint_delta", detail) if ok else _fail("feeling_endpoint_delta", detail)


@register_assertion("hormone_dead_code")
def hormone_dead_code(records, hormone: str = "serotonin", tolerance: float = 0.005) -> AssertionResult:
    series = _get_hormone_series(records, hormone)
    if not series:
        return _fail("hormone_dead_code", f"no hormone data for {hormone}")
    rng = max(series) - min(series)
    ok = rng > tolerance
    detail = f"{hormone}: range={rng:.4f} (tolerance={tolerance})"
    return _pass("hormone_dead_code", detail) if ok else _fail("hormone_dead_code", detail)


@register_assertion("llm_field_count")
def llm_field_count(records, field: str = "i_want_to_say", min_count: int = 1) -> AssertionResult:
    xs = _non_null(_get_llm_field(records, field))
    count = len(xs)
    ok = count >= min_count
    detail = f"{field}: non-null count = {count} / {len(records)} (need >= {min_count})"
    return _pass("llm_field_count", detail) if ok else _fail("llm_field_count", detail)


@register_assertion("llm_field_count_zero")
def llm_field_count_zero(records, field: str = "i_send_through") -> AssertionResult:
    xs = _get_llm_field(records, field)
    non_null = _non_null(xs)
    ok = len(non_null) == 0
    detail = f"{field}: non-null count = {len(non_null)} / {len(xs)} (expected 0)"
    return _pass("llm_field_count_zero", detail) if ok else _fail("llm_field_count_zero", detail)


@register_assertion("hormone_cumulative_drift")
def hormone_cumulative_drift(records, hormone: str = "cortisol", min_drift: float = 0.10) -> AssertionResult:
    series = _get_hormone_series(records, hormone)
    if len(series) < 2:
        return _fail("hormone_cumulative_drift", f"need >=2 records, got {len(series)}")
    drift = sum(abs(series[i+1] - series[i]) for i in range(len(series)-1))
    ok = drift >= min_drift
    detail = f"{hormone}: cumulative |delta| = {drift:.4f} (need >= {min_drift})"
    return _pass("hormone_cumulative_drift", detail) if ok else _fail("hormone_cumulative_drift", detail)


@register_assertion("hormone_plateau")
def hormone_plateau(records, hormone: str = "cortisol", plateau_start: int = 10, plateau_window: int = 5, tolerance: float = 0.01) -> AssertionResult:
    series = _get_hormone_series(records, hormone)
    if len(series) < plateau_start + plateau_window:
        return _fail("hormone_plateau", f"need >= {plateau_start + plateau_window} records, got {len(series)}")
    window = series[plateau_start:plateau_start + plateau_window]
    rng = max(window) - min(window)
    ok = rng <= tolerance
    detail = f"{hormone}: window=[{plateau_start}, {plateau_start + plateau_window}) range={rng:.4f} (tolerance={tolerance})"
    return _pass("hormone_plateau", detail) if ok else _fail("hormone_plateau", detail)


# ============================================================
# Public API
# ============================================================


BUILTIN_ASSERTIONS = list_assertions()


def evaluate_assertions(assertion_specs: list[dict], records: list[dict]) -> list[AssertionResult]:
    results: list[AssertionResult] = []
    for spec in assertion_specs:
        name = spec.get("name")
        if name is None:
            results.append(_fail("(unnamed)", "spec missing 'name' field"))
            continue
        fn = ASSERTION_REGISTRY.get(name)
        if fn is None:
            results.append(_fail(name, f"unknown assertion '{name}'; available: {list_assertions()}"))
            continue
        kwargs = {k: v for k, v in spec.items() if k != "name"}
        try:
            result = fn(records, **kwargs)
            results.append(result)
        except Exception as e:
            results.append(_fail(name, f"raised {type(e).__name__}: {e}"))
    return results
