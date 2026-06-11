"""Owner: 04 neuromodulator system (R79-C).

Hormone-predict coupling corroborator.

Purpose:
    Bridge the v3 LLM JSON's `hormone_response_i_predict` field (a 9-key
    dict mirroring `NeuromodulatorLevels`, each value in [-1.0, +1.0])
    with the formula-derived drive from
    `AppraisalDerivedNeuromodulatorUpdatePath.update_levels`. Per channel,
    the corroborator emits one of three verdicts:

    - ``corroborate``: the LLM's predict sign matches the formula's drive
      sign and the magnitudes agree within tolerance. Emits a small
      positive bonus.
    - ``conflict``: the LLM's predict sign disagrees with the formula's
      drive sign and the magnitudes agree. Emits a small negative penalty.
    - ``silent``: the LLM's predict is zero, the formula's drive is zero,
      or the magnitudes are too far apart to call. Emits zero.

    The bias is consumed by the next-tick `RapidAppraisalBatch` (a future
    slice; R80 composition bridge). The corroborator is a pure producer
    of a `NeuromodulatorLevels` bias vector. It does not feed back on the
    same tick (avoiding LLM-predict ↔ formula co-variation).

Failure semantics:
    Out-of-bounds config fields raise `NeuromodulatorError` at construction
    time. The corroborator is a frozen dataclass; it cannot be mutated
    after construction. The `classify_predict` and `aggregate_coupling_bias`
    methods are total deterministic functions of their inputs.

Notes:
    The corroborator imports only the `04` owner contracts in this
    package. It is owner-neutral glue: it does not import the LLM owner,
    the appraisal owner, the prompt-contract owner, or the channel
    subsystem. The composition owner-boundary guard covers it
    transitively (same package, no cross-owner import).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Mapping

from .contracts import (
    NeuromodulatorError,
    NeuromodulatorLevels,
)


class HormonePredictCouplingChannel(Enum):
    """Owner: 04 neuromodulator (R79-C).

    The 9 channels whose LLM predict the corroborator classifies.
    The ``.value`` matches the corresponding ``NeuromodulatorLevels``
    field name exactly so the corroborator can iterate over
    ``NeuromodulatorLevels.__dataclass_fields__`` and look up the LLM
    predict by name.
    """

    DOPAMINE = "dopamine"
    NOREPINEPHRINE = "norepinephrine"
    SEROTONIN = "serotonin"
    ACETYLCHOLINE = "acetylcholine"
    CORTISOL = "cortisol"
    OXYTOCIN = "oxytocin"
    OPIOID_TONE = "opioid_tone"
    EXCITATION = "excitation"
    INHIBITION = "inhibition"


HormonePredictCouplingVerdict = Literal[
    "corroborate",  # LLM predict matches formula drive (sign + magnitude)
    "conflict",  # LLM predict sign disagrees with formula drive
    "silent",  # either predict is zero, drive is zero, or magnitude is far
]


@dataclass(frozen=True)
class HormonePredictCouplingConfig:
    """Owner: 04 neuromodulator (R79-C).

    Configuration for the corroborator's bonus / penalty / tolerance
    constants. All fields are first-version constants under the
    ``hormone_predict_coupling`` learned-parameter category. P5 will
    tune them later without changing the corroborator's equation shape.

    Bounds:
        - corroborate_bonus: [0.0, 0.2]
        - conflict_penalty: [-0.2, 0.0]
        - sign_match_tolerance: (0.0, 0.5]
        - magnitude_match_tolerance: (0.0, 0.5]

    Sign convention:
        - corroborate_bonus >= 0 (positive bonus when LLM agrees)
        - conflict_penalty <= 0 (negative penalty when LLM disagrees)
    """

    corroborate_bonus: float = 0.05
    conflict_penalty: float = -0.05
    sign_match_tolerance: float = 0.1
    magnitude_match_tolerance: float = 0.2

    def __post_init__(self) -> None:
        if not (0.0 <= self.corroborate_bonus <= 0.2):
            raise NeuromodulatorError(
                f"HormonePredictCouplingConfig.corroborate_bonus must be in [0.0, 0.2], "
                f"got {self.corroborate_bonus}"
            )
        if not (-0.2 <= self.conflict_penalty <= 0.0):
            raise NeuromodulatorError(
                f"HormonePredictCouplingConfig.conflict_penalty must be in [-0.2, 0.0], "
                f"got {self.conflict_penalty}"
            )
        if not (0.0 < self.sign_match_tolerance <= 0.5):
            raise NeuromodulatorError(
                f"HormonePredictCouplingConfig.sign_match_tolerance must be in (0.0, 0.5], "
                f"got {self.sign_match_tolerance}"
            )
        if not (0.0 < self.magnitude_match_tolerance <= 0.5):
            raise NeuromodulatorError(
                f"HormonePredictCouplingConfig.magnitude_match_tolerance must be in (0.0, 0.5], "
                f"got {self.magnitude_match_tolerance}"
            )


@dataclass(frozen=True)
class HormonePredictCouplingClassification:
    """Owner: 04 neuromodulator (R79-C).

    One channel's classification result. The corroborator emits one of
    these per channel whose predict is non-zero and the formula drive
    is non-zero.
    """

    channel: HormonePredictCouplingChannel
    verdict: HormonePredictCouplingVerdict
    magnitude: float  # the LLM predict value, in [-1.0, +1.0]

    def __post_init__(self) -> None:
        if self.verdict not in ("corroborate", "conflict", "silent"):
            raise NeuromodulatorError(
                f"HormonePredictCouplingClassification.verdict must be one of "
                f"'corroborate' / 'conflict' / 'silent', got {self.verdict!r}"
            )
        if not (-1.0 <= self.magnitude <= 1.0):
            raise NeuromodulatorError(
                f"HormonePredictCouplingClassification.magnitude must be in [-1.0, 1.0], "
                f"got {self.magnitude}"
            )


def _sign(value: float) -> int:
    """Return the sign of ``value`` as -1 / 0 / +1."""
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


@dataclass(frozen=True)
class HormonePredictCorroborator:
    """Owner: 04 neuromodulator (R79-C).

    The corroborator. Frozen dataclass; two pure methods.

    Failure semantics:
        Both methods are total deterministic functions of their inputs;
        they raise `NeuromodulatorError` only on invalid input
        (out-of-bound magnitude, missing tonic_baseline channel).
    """

    config: HormonePredictCouplingConfig

    def classify_predict(
        self,
        formula_drive: NeuromodulatorLevels,
        predict: "Mapping[str, float] | None",
        tonic_baseline: NeuromodulatorLevels,
    ) -> tuple[HormonePredictCouplingClassification, ...]:
        """Classify the LLM's ``predict`` against the formula-derived drive.

        The classification rule per channel (see requirement §3.2):

        1. ``predict_value = predict.get(channel.name, 0.0)``
        2. ``drive_value = formula_drive.<channel> - tonic_baseline.<channel>``
        3. ``drive_sign = sign(drive_value)``
        4. ``predict_sign = sign(predict_value)``
        5. If ``predict_value == 0.0`` or ``predict is None``: ``silent``.
        6. If ``drive_sign == 0`` or ``predict_sign == 0``: ``silent``.
        7. If ``drive_sign == predict_sign`` and
           ``|drive_value - predict_value| <= magnitude_match_tolerance``:
           ``corroborate``, ``magnitude = predict_value``.
        8. If ``drive_sign != predict_sign`` and
           ``|drive_value + predict_value| <= magnitude_match_tolerance``:
           ``conflict``, ``magnitude = predict_value``.
        9. Otherwise: ``silent`` (LLM was confidently wrong; do not punish).

        Returns an empty tuple if ``predict`` is empty or ``None``.
        """
        if not predict:
            return ()
        classifications: list[HormonePredictCouplingClassification] = []
        for channel in HormonePredictCouplingChannel:
            predict_value = predict.get(channel.value, 0.0)
            if predict_value == 0.0:
                continue
            drive_value = getattr(formula_drive, channel.value) - getattr(
                tonic_baseline, channel.value
            )
            drive_sign = _sign(drive_value)
            predict_sign = _sign(predict_value)
            if drive_sign == 0 or predict_sign == 0:
                continue
            if drive_sign == predict_sign:
                if abs(drive_value - predict_value) <= self.config.magnitude_match_tolerance:
                    classifications.append(
                        HormonePredictCouplingClassification(
                            channel=channel,
                            verdict="corroborate",
                            magnitude=predict_value,
                        )
                    )
                continue
            # drive_sign != predict_sign
            if abs(drive_value + predict_value) <= self.config.magnitude_match_tolerance:
                classifications.append(
                    HormonePredictCouplingClassification(
                        channel=channel,
                        verdict="conflict",
                        magnitude=predict_value,
                    )
                )
        return tuple(classifications)

    def aggregate_coupling_bias(
        self,
        classifications: tuple[HormonePredictCouplingClassification, ...],
        tonic_baseline: NeuromodulatorLevels,
        legal_min: NeuromodulatorLevels,
        legal_max: NeuromodulatorLevels,
    ) -> dict[str, float]:
        """Convert classifications into a 9-channel bias vector.

        Per channel:

        - ``corroborate``: bias = corroborate_bonus * magnitude
        - ``conflict``: bias = conflict_penalty * magnitude
        - ``silent``: bias = 0.0

        The bias is the **offset** relative to the tonic baseline; the
        caller (R80 composition bridge or R79-D baseline framework)
        adds it to the next-tick `RapidAppraisalBatch` as a small
        per-channel offset.

        The result is returned as a ``dict[str, float]`` (not
        ``NeuromodulatorLevels``) because the bias can be **negative**
        (a conflict verdict produces a negative penalty) and
        ``NeuromodulatorLevels`` enforces ``[0.0, 1.0]`` per channel.

        The bias is clamped per-channel to
        ``[legal_min - tonic_baseline, legal_max - tonic_baseline]``
        so the bias cannot push the drive outside the legal range.
        """
        bias_by_channel: dict[str, float] = {ch.value: 0.0 for ch in HormonePredictCouplingChannel}
        for classification in classifications:
            if classification.verdict == "corroborate":
                bias_by_channel[classification.channel.value] = (
                    self.config.corroborate_bonus * classification.magnitude
                )
            elif classification.verdict == "conflict":
                bias_by_channel[classification.channel.value] = (
                    self.config.conflict_penalty * classification.magnitude
                )
            # silent: 0.0 (default; no entry needed)

        for channel_name in bias_by_channel:
            lower = getattr(legal_min, channel_name) - getattr(tonic_baseline, channel_name)
            upper = getattr(legal_max, channel_name) - getattr(tonic_baseline, channel_name)
            value = bias_by_channel[channel_name]
            if value < lower:
                bias_by_channel[channel_name] = lower
            elif value > upper:
                bias_by_channel[channel_name] = upper
        return bias_by_channel
