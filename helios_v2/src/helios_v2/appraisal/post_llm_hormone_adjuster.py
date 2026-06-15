"""Owner: rapid salience appraisal.

R98 (post-LLM appraisal adjustment) closes the W3 root-cause gap left
by R96+R97 on the real-cloud cortisol positive-vs-negative separation
(headline `-0.0112` vs pre-R97 baseline `-0.0095`, directional shift
`-0.0017`; the unit-test B2/B3 closures were both pass but the
real-cloud headline is not closed).

**The gap (verified)**:
- 16/85 (19%) of real-cloud LLM responses include a
  `hormone_response_i_predict` field, but the runtime treats it as
  a **next-tick self-supervision signal only** (R81, see
  `composition/runtime_assembly._carry_hormone_prediction`). No path
  feeds it back into the current tick's neuromodulator drive.
- The appraisal layer (`GroundedDimensionEstimator.estimate_dimensions`)
  reads only the visitor's raw `Stimulus`; it never consults the LLM
  `thought` or `reply`. For context-only emotion ("心跳加速",
  "反复演练失败", "脑子停不下来"), no ZH/EN anchor has high cosine,
  so the appraisal falls back to a base rate and the LLM's correct
  emotion classification is dropped.

**R98 fix (this module)**:
A new owner-owned `PostLLMHormoneAdjuster` translates an LLM hormone
prediction into a bounded appraisal Δ adjustment. The translation is
strict:
- Missing / malformed input → zero adjustment (silent default).
- Numeric signal → confidence 1.0; phrase signal → confidence 0.7
  (LLM prose is fuzzier than numeric forecasts).
- Magnitude cap is `±0.10` per tick per channel; this guarantees
  the adjustment can never overdrive the rapid appraisal's main
  signal in a single tick.
- Unknown channels are silently ignored (the catalog of supported
  channels is the R81 nine neuromodulators; `gaba` / `histamine` /
  arbitrary extras get `confidence=0.0`).

**Brain analogy**: this is the "cortical modulation" of the amygdala.
Rapid salience = amygdala (pre-conscious, fast, lexically anchored).
The LLM = cortex (slower, contextual, can recognize
context-only emotion). The adjuster is the bounded cortico-amygdalar
channel: cortex does not replace the amygdala's threat assessment; it
modulates it within tight bounds. Magnitude cap is the neuroanatomical
fact that cortex cannot fully suppress amygdala in one cycle.

**R56/R57 owner boundary**:
- This module OWNS the translation rules and the magnitude cap. The
  appraisal owner decides what counts as threat vs reward; the
  composition owner wires the LLM prediction into this owner and the
  drive formula consumes the result. Neither side reads the other
  side's internals.
- The adjuster takes a generic `Mapping[str, Any] | None` (the LLM
  prediction) and returns a `PostLLMHormoneAdjustment` (the appraisal
  contract). Composition only ever calls `adjust(prediction)` and
  forwards the result; it never inspects the prediction's keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


# Magnitude cap: single-tick, single-channel. Cannot overdrive rapid
# appraisal in one cycle. R83 long-run can accumulate; each tick is
# bounded.
LLM_HORMONE_DELTA_MIN: float = -0.10
LLM_HORMONE_DELTA_MAX: float = +0.10

# Numeric forecast thresholds. Numbers above HIGH push the channel in
# the "elevated" direction; below LOW push in the "depressed"
# direction; between 0.4 and 0.6 is the LLM's "no comment" zone
# (returns confidence=0.0 for that channel).
LLM_HORMONE_HIGH_THRESHOLD: float = 0.6
LLM_HORMONE_LOW_THRESHOLD: float = 0.4

# Confidence weights. Numeric forecasts are full weight; phrase
# forecasts are down-weighted to 0.7 because LLM prose is intrinsically
# less precise than a numeric range. (R81 already permits phrase
# forecasts; this just down-weights them at the appraisal boundary.)
_NUMERIC_CONFIDENCE: float = 1.0
_PHRASE_CONFIDENCE: float = 0.7

# Phrase lexicons. Bilingual (English + Chinese) to match the LLM's
# real-cloud output style (R96+R97 real-cloud probe saw English
# ("likely elevated", "high") and Chinese ("升", "高") in the same
# `hormone_response_i_predict` field). Substring match (not whole-word)
# to handle compound phrases like "likely elevated due to social
# bonding".
_ELEVATED_PHRASES: tuple[str, ...] = (
    "elevated",
    "high",
    "raised",
    "increase",
    "rise",
    "升",
    "高",
    "上升",
    "升高",
    "增长",
)
_LOW_PHRASES: tuple[str, ...] = (
    "low",
    "reduced",
    "decreased",
    "drop",
    "fall",
    "低",
    "降",
    "下降",
    "降低",
    "减少",
)


# Channel → direction translation table. A "primary magnitude" is the
# full ±0.10 cap; a "secondary magnitude" is half (±0.05) — used for
# channels whose valence is mixed (serotonin is reward-leaning but
# also affects anxiety; opioid_tone is reward-leaning but broader
# than just reward). This prevents serotonin from overdriving the
# dopamine-style reward signal.
_PRIMARY_MAGNITUDE: float = 0.10
_SECONDARY_MAGNITUDE: float = 0.05

# Map each R81 channel to a (delta_field, magnitude) pair. Channels
# not in this table (e.g. `gaba`, `histamine`, unknown extras) are
# silently dropped with `confidence = 0.0` for that entry.
_CHANNEL_MAP: dict[str, tuple[str, float]] = {
    "dopamine": ("reward_delta", _PRIMARY_MAGNITUDE),
    "cortisol": ("threat_delta", _PRIMARY_MAGNITUDE),
    "norepinephrine": ("uncertainty_delta", _PRIMARY_MAGNITUDE),
    "serotonin": ("reward_delta", _SECONDARY_MAGNITUDE),
    "oxytocin": ("social_delta", _PRIMARY_MAGNITUDE),
    "opioid_tone": ("social_delta", _SECONDARY_MAGNITUDE),
}


@dataclass(frozen=True)
class PostLLMHormoneAdjustment:
    """Owner-neutral projection of an LLM hormone prediction into a bounded
    appraisal Δ adjustment.

    Owner: rapid salience appraisal.

    Each delta field is in `[-0.10, +0.10]` and is the per-tick magnitude
    cap from `LLM_HORMONE_DELTA_*`. The `confidence` field is the
    scaling factor the drive formula uses: `effective_delta = delta * confidence`.
    When `confidence == 0.0`, the drive formula treats the adjustment as
    a no-op (silent default).

    Negative `threat_delta` LOWERS the threat drive (i.e. the LLM says
    cortisol is suppressed; the appraisal should let the rapid estimate
    dominate). Positive `threat_delta` RAISES the threat drive (LLM says
    cortisol should spike; the appraisal adds it to the rapid estimate).
    Same sign convention for the other delta fields.
    """

    threat_delta: float = 0.0
    reward_delta: float = 0.0
    social_delta: float = 0.0
    uncertainty_delta: float = 0.0
    confidence: float = 0.0


def _classify_value(value: Any) -> tuple[float, float]:
    """Classify a single prediction value into (delta_direction, confidence).

    Returns:
        A `(direction, confidence)` tuple where `direction` is `+1.0`,
        `-1.0`, or `0.0` (no-comment zone) and `confidence` is
        `_NUMERIC_CONFIDENCE` or `_PHRASE_CONFIDENCE`. If the value is
        unparseable (e.g. a list, a dict, an unsupported type), returns
        `(0.0, 0.0)` which makes the caller emit a zero adjustment.
    """
    if isinstance(value, bool):
        # `True` is a numeric 1 in Python; reject bool explicitly so a
        # stray `{"dopamine": True}` does not classify as "high".
        return (0.0, 0.0)
    if isinstance(value, (int, float)):
        if value >= LLM_HORMONE_HIGH_THRESHOLD:
            return (+1.0, _NUMERIC_CONFIDENCE)
        if value <= LLM_HORMONE_LOW_THRESHOLD:
            return (-1.0, _NUMERIC_CONFIDENCE)
        # No-comment zone (between LOW and HIGH).
        return (0.0, _NUMERIC_CONFIDENCE)
    if isinstance(value, str):
        lowered = value.lower()
        for phrase in _ELEVATED_PHRASES:
            if phrase in lowered:
                return (+1.0, _PHRASE_CONFIDENCE)
        for phrase in _LOW_PHRASES:
            if phrase in lowered:
                return (-1.0, _PHRASE_CONFIDENCE)
        return (0.0, 0.0)
    # Lists, dicts, None, etc. are not supported as channel values.
    return (0.0, 0.0)


def _clamp_magnitude(value: float, magnitude: float) -> float:
    """Clamp a signed direction * magnitude to `LLM_HORMONE_DELTA_*`."""
    if value > 0:
        return min(LLM_HORMONE_DELTA_MAX, magnitude)
    if value < 0:
        return max(LLM_HORMONE_DELTA_MIN, -magnitude)
    return 0.0


class PostLLMHormoneAdjuster:
    """Translate an LLM `hormone_response_i_predict` payload into a bounded
    appraisal Δ adjustment.

    Owner: rapid salience appraisal.

    The adjuster is **strict**: any of the following yield a zero
    adjustment with `confidence = 0.0` (silent default), never an
    exception or noise log:
    - `prediction` is `None`
    - `prediction` is empty / not a mapping
    - every channel in `prediction` is unknown to `_CHANNEL_MAP`
    - every channel value falls in the no-comment zone or is unparseable

    Otherwise the per-channel `direction` (`±1.0`) is multiplied by the
    channel's `magnitude` (from `_CHANNEL_MAP`) and the result is added
    to the corresponding delta field. The `confidence` field on the
    returned adjustment is the **minimum** per-channel confidence
    (so a payload with one no-comment entry and one high-confidence
    numeric entry still gets the 1.0 confidence for the second; the
    0.0 contribution from the no-comment entry is filtered out before
    the min is taken — see `adjust` for the exact rules).
    """

    def adjust(
        self, prediction: Mapping[str, Any] | None
    ) -> PostLLMHormoneAdjustment:
        if not prediction:
            return PostLLMHormoneAdjustment()

        threat_delta = 0.0
        reward_delta = 0.0
        social_delta = 0.0
        uncertainty_delta = 0.0
        # The "active" confidences we have seen for at least one
        # contributing channel. The final `confidence` is the minimum
        # of the active ones — a payload with a high-confidence numeric
        # signal and a low-confidence phrase signal is treated with
        # the lower of the two confidences for honesty. A payload with
        # only one active signal uses that signal's confidence.
        active_confidences: list[float] = []

        for channel, value in prediction.items():
            target = _CHANNEL_MAP.get(channel)
            if target is None:
                # Unknown channel; silently ignore per R56 boundary.
                continue
            delta_field, magnitude = target
            direction, confidence = _classify_value(value)
            if direction == 0.0 or confidence == 0.0:
                # No-comment zone or unparseable; this channel does not
                # contribute, but it does not contaminate the overall
                # confidence either (it is a non-event).
                continue
            signed = _clamp_magnitude(direction, magnitude)
            if delta_field == "threat_delta":
                threat_delta += signed
            elif delta_field == "reward_delta":
                reward_delta += signed
            elif delta_field == "social_delta":
                social_delta += signed
            elif delta_field == "uncertainty_delta":
                uncertainty_delta += signed
            else:
                # Defensive: _CHANNEL_MAP invariant.
                continue
            active_confidences.append(confidence)

        if not active_confidences:
            return PostLLMHormoneAdjustment()

        # Final confidence: min of the active confidences. Honors the
        # honest-min rule.
        return PostLLMHormoneAdjustment(
            threat_delta=threat_delta,
            reward_delta=reward_delta,
            social_delta=social_delta,
            uncertainty_delta=uncertainty_delta,
            confidence=min(active_confidences),
        )
