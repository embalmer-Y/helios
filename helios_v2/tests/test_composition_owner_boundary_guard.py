"""Repository guard (R56): composition holds no neuromodulator channel-sensitivity policy.

`ARCHITECTURE_BOUNDARIES.md` §4.5 and `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §3.2/§7.1 make the
composition root assembly-only: it constructs owners, owner-neutral bridges, and the kernel,
and holds no cognitive policy. Deciding which appraisal salience drives which neuromodulator
channel, and how strongly, is the `04` neuromodulator owner's defining cognitive policy.

R36 introduced that policy (`AppraisalDerivedNeuromodulatorUpdatePath` with its
`reward_to_dopamine` / `threat_to_cortisol` style sensitivity coefficients) inside the
composition glue; R56 recovered it into the `04` owner package. This guard fails if a
salience-to-neuromodulator-channel sensitivity coefficient reappears under
`helios_v2/composition`, so the recovered boundary cannot silently regress.

Scope note: this guard targets the recovered policy pattern (a `<salience>_to_<channel>`
coefficient binding an appraisal salience dimension to a neuromodulator channel). It does
not forbid the legitimately owner-neutral composition contents that remain: the constant
first-version shim paths (no salience-to-channel mapping) and the pure projection bridges
(which forward an already-published owner field with no scoring weight).
"""

from __future__ import annotations

import re
from pathlib import Path

# Composition source root scanned by the guard.
_COMPOSITION_ROOT = Path(__file__).resolve().parents[1] / "src" / "helios_v2" / "composition"

# The appraisal salience dimensions (the `03` owner) and the neuromodulator channels (the `04`
# owner). A `<salience>_to_<channel>` identifier binds one to the other, which is the `04`
# owner's channel-drive policy and must not live in composition.
_SALIENCE_DIMENSIONS: tuple[str, ...] = (
    "threat",
    "reward",
    "novelty",
    "social",
    "uncertainty",
    "salience",
)
_NEUROMODULATOR_CHANNELS: tuple[str, ...] = (
    "dopamine",
    "norepinephrine",
    "serotonin",
    "acetylcholine",
    "cortisol",
    "oxytocin",
    "opioid",
    "opioid_tone",
    "excitation",
    "inhibition",
)

# Matches e.g. `reward_to_dopamine`, `threat_to_cortisol`, `novelty_to_norepinephrine`.
_SENSITIVITY_COEFFICIENT_PATTERN = re.compile(
    r"\b(?:" + "|".join(_SALIENCE_DIMENSIONS) + r")_to_(?:" + "|".join(_NEUROMODULATOR_CHANNELS) + r")\b"
)


def _iter_composition_source_files() -> list[Path]:
    return [
        path
        for path in _COMPOSITION_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def test_composition_defines_no_neuromodulator_channel_sensitivity_policy() -> None:
    source_files = _iter_composition_source_files()
    assert source_files, "Expected to find Python source files under helios_v2/src/composition"

    violations: list[str] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for match in _SENSITIVITY_COEFFICIENT_PATTERN.finditer(text):
            violations.append(f"{path}: salience-to-channel sensitivity coefficient '{match.group(0)}'")

    assert not violations, (
        "Composition is assembly-only and must not define neuromodulator channel-sensitivity "
        "policy; that semantic is owned by the `04` neuromodulator owner "
        "(helios_v2.neuromodulation). Recover the policy into the owner. Violations:\n"
        + "\n".join(violations)
    )


def test_guard_pattern_is_not_vacuous() -> None:
    # Positive control: the guard must actually detect the recovered policy pattern, so a future
    # regression cannot pass merely because the regex never matches anything.
    planted = "    reward_to_dopamine: float = 0.5\n    threat_to_cortisol: float = 0.5\n"
    matches = _SENSITIVITY_COEFFICIENT_PATTERN.findall(planted)
    assert "reward_to_dopamine" in matches
    assert "threat_to_cortisol" in matches


# --- Requirement 57: composition holds no autonomy drive-pressure / action-threshold policy ---

# The autonomy owner (`18`) owns how cognition outcomes become its drive-input pressures and its
# own `OUTWARD_ACTION_THRESHOLD`. Composition must only forward raw cognition facts. These patterns
# detect the recovered policy: a tuned autonomy drive-pressure constant (a `continuation`/`temporal`/
# `identity`-pressure coefficient assigned a numeric literal) or a literal reference to the autonomy
# action threshold, appearing under `helios_v2/composition`. The pattern is scoped to the autonomy
# drive dimensions so it does not flag the legitimate `09` gate-signal `workload_pressure` projection
# (a raw transport/load fact forwarded to the gate owner, not an autonomy pressure constant).
_AUTONOMY_PRESSURE_CONSTANT_PATTERN = re.compile(
    r"\b[A-Za-z_]*(?:CONTINUATION|TEMPORAL|IDENTITY)_PRESSURE\b[^=\n]*=\s*[0-9]",
    re.IGNORECASE,
)
_AUTONOMY_THRESHOLD_PATTERN = re.compile(r"outward_drive\s*>=|OUTWARD_ACTION_THRESHOLD\s*=")


def test_composition_defines_no_autonomy_drive_pressure_or_threshold_policy() -> None:
    source_files = _iter_composition_source_files()
    assert source_files, "Expected to find Python source files under helios_v2/src/composition"

    violations: list[str] = []
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        for match in _AUTONOMY_PRESSURE_CONSTANT_PATTERN.finditer(text):
            violations.append(f"{path}: autonomy drive-pressure constant '{match.group(0).strip()}'")
        for match in _AUTONOMY_THRESHOLD_PATTERN.finditer(text):
            violations.append(f"{path}: autonomy action-threshold reference '{match.group(0).strip()}'")

    assert not violations, (
        "Composition is assembly-only and must not define autonomy drive-pressure tuning or "
        "reference the autonomy action threshold; that semantic is owned by the `18` autonomy "
        "owner (helios_v2.autonomy). Recover the policy into the owner. Violations:\n"
        + "\n".join(violations)
    )


def test_autonomy_guard_patterns_are_not_vacuous() -> None:
    planted_pressure = "    _ACTION_CONTINUATION_PRESSURE: float = 0.9\n"
    planted_threshold = "        proactive_action_requested = outward_drive >= 1.6\n"
    assert _AUTONOMY_PRESSURE_CONSTANT_PATTERN.search(planted_pressure) is not None
    assert _AUTONOMY_THRESHOLD_PATTERN.search(planted_threshold) is not None
