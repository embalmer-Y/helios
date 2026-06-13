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
    """Owner: neuromodulator system (R81).

    Purpose:
        Inject the hormone-predict corroboration bias between the R36/R80 instantaneous drive and
        the R43 dual-timescale wrapper. It computes the inner drive, reads the carried prior-tick
        model forecast, and returns the corroborated (biased) levels as the instantaneous target the
        dual-timescale wrapper then smooths (bias and drive at the same layer).

    Failure semantics:
        Total deterministic function. A `None` forecast (the common case: no model forecast, or a
        non-fired prior tick) returns the inner drive byte-for-byte, so the path is invariant unless
        the model actually forecasts.

    Notes:
        Stateless with respect to `prior_levels` (it forwards `None` to the inner drive and ignores
        its own `prior_levels`); cross-tick carry/decay is the dual-timescale wrapper's job and the
        forecast carry is the composition holder's job. The forecast is read through the injected
        `prediction_source` exactly as `03`'s grounded estimators read injected fact sources; this
        owner imports no composition glue.
    """

    drive_path: NeuromodulatorUpdatePath
    prediction_source: HormonePredictionSource
    corroborator: HormonePredictCorroborator

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: NeuromodulatorLevels | None = None,
    ) -> NeuromodulatorLevels:
        """Return the corroboration-biased instantaneous drive for this tick."""

        del prior_levels
        drive = self.drive_path.update_levels(batch, config, tick_id, None)
        prediction = self.prediction_source.current_prediction()
        return self.corroborator.corroborate(prediction, drive, config).biased_levels
