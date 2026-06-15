"""Owner: neuromodulator system (R81).

Owns:
- the hormone-predict corroboration policy: classifying a model-supplied hormone forecast against
  the formula drive per channel into a three-state verdict, and applying a bounded, owner-judged
  bias only on agreement
- the corroboration-biased update path that injects that bias between the R36/R80 drive and the
  R43 dual-timescale wrapper

Does not own:
- the model forecast itself (that is `11`-owned content, transported owner-neutrally by composition)
- the instantaneous drive (the injected inner `drive_path`, R36/R80)
- cross-tick carry/decay (the R43 dual-timescale wrapper)
- subjective feeling construction, gating, or action routing

This is the project's first model-assertion-plus-owner-corroboration path (a cautious
`C_engineering_hypothesis` analogy to the brain's reward/affect prediction error). The model
supplies a subjective forecast (content + self-assessment); the owner keeps judgment: the bias only
fires when the forecast agrees with the formula's direction, so the model can refine magnitude
within the agreed direction but can never move a channel against the formula or veto it
(`ARCHITECTURE_PHILOSOPHY` §14 content/judgment separation).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from helios_v2.appraisal import RapidAppraisalBatch

from .contracts import NeuromodulatorConfig, NeuromodulatorLevels
from .engine import _NEUROMODULATOR_CHANNELS, NeuromodulatorUpdatePath, _clamp

# The three corroboration verdicts (`ARCHITECTURE_PHILOSOPHY` §14 / brain.mmd prediction-error
# analogy). `silent` means the model gave no forecast for the channel; `corroborate` means the
# forecast and the formula drive are on the same side of the tonic baseline; `conflict` means they
# point to opposite sides. Only `corroborate` applies a bias.
HORMONE_CORROBORATION_VERDICTS: tuple[str, ...] = ("corroborate", "conflict", "silent")


@runtime_checkable
class HormonePredictionSource(Protocol):
    """Owner: neuromodulator system (R81).

    Purpose:
        Provide the prior-tick model hormone forecast the corroborator checks against this tick's
        formula drive, as an owner-neutral channel->value mapping (or `None` when the model made no
        forecast). Because `04` runs before `11`, a forecast made while thinking in tick N can only
        be corroborated against tick N+1's drive; composition carries it forward verbatim.
    """

    def current_prediction(self) -> Mapping[str, float] | None:
        """Return the carried prior-tick hormone forecast (channel name -> `[0, 1]`), or `None`."""


@runtime_checkable
class PostLLMHormoneAdjustmentSource(Protocol):
    """Owner: neuromodulator system (R98).

    Purpose:
        Provide the prior-tick appraisal-owned `PostLLMHormoneAdjustment` that the
        `04` drive formula adds to the rapid appraisal's threat / reward outputs
        before computing the drive. The translation rules (which channels, what
        magnitude) are owned by `appraisal.post_llm_hormone_adjuster`; this
        source is just the owner-neutral carry seam.

    Notes:
        The `current_adjustment()` mapping is a `dict` of channel-delta fields
        (`threat_delta`, `reward_delta`, `social_delta`, `uncertainty_delta`)
        plus a `confidence` field (scaling factor in `[0, 1]`). The path uses
        `effective_delta = delta * confidence` and clamps the result to the
        legal range. When `confidence == 0` or the holder is cleared, the path
        is a byte-for-byte no-op (the inner drive is returned unchanged).
    """

    def current_adjustment(self) -> Mapping[str, float] | None:
        """Return the carried prior-tick appraisal Δ adjustment, or `None`."""


@dataclass(frozen=True)
class HormoneCorroborationOutcome:
    """Owner: neuromodulator system (R81).

    Purpose:
        Carry the corroboration result: the biased neuromodulator levels and the per-channel
        three-state verdict (owner-private provenance for tests and future `17`/`23` surfacing).

    Failure semantics:
        Built only by `HormonePredictCorroborator.corroborate`; the verdict map is frozen.
    """

    biased_levels: NeuromodulatorLevels
    verdicts: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "verdicts", MappingProxyType(dict(self.verdicts)))


@dataclass
class HormonePredictCorroborator:
    """Owner: neuromodulator system (R81).

    Purpose:
        Corroborate a model hormone forecast against the formula drive per channel and apply a
        bounded, owner-judged bias only on directional agreement.

    Failure semantics:
        Total deterministic function; every biased channel is clamped to the legal range, so it
        never diverges. A `None` forecast (or a channel with no forecast) leaves the channel at the
        drive value (silent), so it is byte-for-byte the drive.

    Notes:
        `coupling_gain` and `agreement_deadzone` are explicit bounded first-version constants under
        the config's declared `hormone_predict_coupling` learned-parameter category (P5-learnable
        later); they are held here, as R80's channel gains are held on the drive path. The bias is a
        bounded pull from the drive toward the forecast (`drive + gain * (forecast - drive)`), so the
        model only ever refines within the formula's agreed direction.
    """

    coupling_gain: float = 0.15
    agreement_deadzone: float = 0.05

    def _direction(self, value: float, baseline: float) -> int:
        delta = value - baseline
        if abs(delta) <= self.agreement_deadzone:
            return 0
        return 1 if delta > 0 else -1

    def _verdict(self, forecast: float | None, drive: float, baseline: float) -> str:
        if forecast is None:
            return "silent"
        if self._direction(forecast, baseline) == self._direction(drive, baseline):
            return "corroborate"
        return "conflict"

    def corroborate(
        self,
        prediction: Mapping[str, float] | None,
        drive: NeuromodulatorLevels,
        config: NeuromodulatorConfig,
    ) -> HormoneCorroborationOutcome:
        """Owner: neuromodulator system (R81).

        Purpose:
            Classify the forecast against the drive per channel and return the bounded biased
            levels plus the three-state verdict map.

        Inputs:
            `prediction` - the carried prior-tick model forecast (channel -> `[0, 1]`) or `None`.
            `drive` - this tick's formula-derived `NeuromodulatorLevels` (R36/R80).
            `config` - the owner config (tonic baseline + legal range).

        Returns:
            A `HormoneCorroborationOutcome` with clamped biased levels and per-channel verdicts.

        Notes:
            On `corroborate` the channel moves `coupling_gain` of the way from the drive toward the
            forecast and is clamped; on `conflict`/`silent` it stays at the drive. A `None` forecast
            yields the drive unchanged on every channel (all silent).
        """

        base = config.tonic_baseline
        low = config.legal_min
        high = config.legal_max
        biased: dict[str, float] = {}
        verdicts: dict[str, str] = {}
        for channel in _NEUROMODULATOR_CHANNELS:
            drive_value = getattr(drive, channel)
            forecast = self._channel_forecast(prediction, channel)
            verdict = self._verdict(forecast, drive_value, getattr(base, channel))
            verdicts[channel] = verdict
            if verdict == "corroborate" and forecast is not None:
                stepped = drive_value + self.coupling_gain * (forecast - drive_value)
                biased[channel] = _clamp(stepped, getattr(low, channel), getattr(high, channel))
            else:
                biased[channel] = drive_value
        return HormoneCorroborationOutcome(
            biased_levels=NeuromodulatorLevels(**biased),
            verdicts=verdicts,
        )

    @staticmethod
    def _channel_forecast(
        prediction: Mapping[str, float] | None,
        channel: str,
    ) -> float | None:
        if prediction is None:
            return None
        value = prediction.get(channel)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if value < 0.0 or value > 1.0:
            return None
        return float(value)


@dataclass
class CorroborationBiasedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: neuromodulator system (R81 + R98).

    Purpose:
        Inject two bounded, owner-judged signals between the R36/R80 instantaneous drive and
        the R43 dual-timescale wrapper:

        1. R98 post-LLM appraisal adjustment (NEW): read the carried prior-tick
           appraisal-owned `PostLLMHormoneAdjustment` (translated from the LLM's
           `hormone_response_i_predict` by the appraisal owner) and add the
           bounded Δ to the inner drive. The adjustment is **additive**, not
           replacement: the rapid appraisal's main signal stays in charge. The
           adjustment is the cortico-amygdalar bounded modulation; without it
           context-only emotion (anxiety / grief / loneliness) is dropped on
           the floor.

        2. R81 hormone-predict corroboration bias: read the carried prior-tick
           model forecast and bias the now-adjusted drive toward the forecast
           on directional agreement (the model can refine within the agreed
           direction; it can never veto the formula or move a channel against it).

    Failure semantics:
        Total deterministic function. A `None` forecast (the common case: no model forecast, or a
        non-fired prior tick) and a `None` post-LLM adjustment both yield the inner drive
        byte-for-byte. Each layer is a no-op when its input is absent, so the path is invariant
        unless both inputs are present.

    Notes:
        Stateless with respect to `prior_levels` (it forwards `None` to the inner drive and ignores
        its own `prior_levels`); cross-tick carry/decay is the dual-timescale wrapper's job and the
        forecast / adjustment carry is the composition holder's job. The forecast / adjustment are
        read through the injected sources exactly as `03`'s grounded estimators read injected fact
        sources; this owner imports no composition glue.

    Order of operations (R98 -> R81):
        1. `drive = inner_drive(batch)` -- R36/R80 baseline
        2. `drive = drive + post_llm_adjustment * confidence` (clamped) -- R98
        3. `drive = corroborate(forecast, drive, config)` -- R81 (含 adjustment 模式)
        4. Return `drive` to the R43 dual-timescale wrapper for cross-tick smoothing
    """

    drive_path: NeuromodulatorUpdatePath
    prediction_source: HormonePredictionSource
    corroborator: HormonePredictCorroborator
    # R98: the prior-tick appraisal-owned adjustment source. Optional (default
    # None) so callers that have not yet wired R98 see byte-for-byte R81 behavior.
    # The translation rules (which LLM channels map to which appraisal deltas) are
    # owned by `appraisal.post_llm_hormone_adjuster`; this path only reads the
    # result and applies it to the drive.
    post_llm_adjustment_source: PostLLMHormoneAdjustmentSource | None = None

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: NeuromodulatorLevels | None = None,
    ) -> NeuromodulatorLevels:
        """Return the post-LLM-adjusted + R81-corroborated instantaneous drive for this tick."""

        del prior_levels
        drive = self.drive_path.update_levels(batch, config, tick_id, None)
        # R98: apply the bounded appraisal Δ adjustment to the drive (additive,
        # per-channel clamp). When the holder is absent or the adjustment has
        # confidence=0, this is a byte-for-byte no-op.
        drive = self._apply_post_llm_adjustment(drive, config)
        # R81: corroborate the (now-adjusted) drive against the model forecast.
        # When the model made no forecast, the corroborator returns the drive
        # unchanged; this is the common case and must be invariant.
        prediction = self.prediction_source.current_prediction()
        return self.corroborator.corroborate(prediction, drive, config).biased_levels

    def _apply_post_llm_adjustment(
        self,
        drive: NeuromodulatorLevels,
        config: NeuromodulatorConfig,
    ) -> NeuromodulatorLevels:
        """Add the bounded R98 post-LLM adjustment to the drive (per-channel clamp).

        R98 channel mapping (the appraisal owner's contract):
            `threat_delta`      -> `cortisol`     (primary magnitude, ±0.10)
            `reward_delta`      -> `dopamine`     (primary magnitude, ±0.10)
            `reward_delta`      -> `serotonin`    (secondary magnitude, ±0.05)
            `social_delta`      -> `oxytocin`     (primary magnitude, ±0.10)
            `social_delta`      -> `opioid_tone`  (secondary magnitude, ±0.05)
            `uncertainty_delta` -> `norepinephrine` (primary magnitude, ±0.10)

        The contract is owned by the appraisal owner; this path only consumes
        the deltas. The `confidence` field scales the effective delta and the
        per-channel clamp guards against any owner misbehavior.
        """

        if self.post_llm_adjustment_source is None:
            return drive
        adjustment = self.post_llm_adjustment_source.current_adjustment()
        if not adjustment:
            return drive
        confidence = float(adjustment.get("confidence", 0.0) or 0.0)
        if confidence <= 0.0:
            return drive
        low = config.legal_min
        high = config.legal_max
        # R98 channel-to-channel mapping. The appraisal owner decides which
        # appraisal deltas flow to which neuromodulator channels; this list
        # is the owner-neutral consumption surface.
        channel_deltas: tuple[tuple[str, float], ...] = (
            ("cortisol", float(adjustment.get("threat_delta", 0.0) or 0.0)),
            ("dopamine", float(adjustment.get("reward_delta", 0.0) or 0.0)),
            ("serotonin", float(adjustment.get("reward_delta", 0.0) or 0.0) * 0.5),
            ("oxytocin", float(adjustment.get("social_delta", 0.0) or 0.0)),
            ("opioid_tone", float(adjustment.get("social_delta", 0.0) or 0.0) * 0.5),
            ("norepinephrine", float(adjustment.get("uncertainty_delta", 0.0) or 0.0)),
        )
        adjusted: dict[str, float] = {}
        for channel, raw_delta in channel_deltas:
            drive_value = getattr(drive, channel)
            channel_low = getattr(low, channel)
            channel_high = getattr(high, channel)
            effective = drive_value + raw_delta * confidence
            adjusted[channel] = _clamp(effective, channel_low, channel_high)
        # All other channels (excitation, inhibition) carry no R98 adjustment;
        # pass them through unchanged.
        for channel in _NEUROMODULATOR_CHANNELS:
            if channel not in adjusted:
                adjusted[channel] = getattr(drive, channel)
        return NeuromodulatorLevels(**adjusted)
