"""Owner: interoceptive feeling layer.

Owns:
- subjective body-feeling state contracts
- feeling update API boundary from neuromodulator state
- update and publication ops contracts

Does not own:
- neuromodulator mutation
- memory tagging
- action gating
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.neuromodulation import NeuromodulatorState
from helios_v2.sensory import Stimulus


def _validate_feeling_value(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise InteroceptiveFeelingError(f"Feeling value '{name}' must be within [0.0, 1.0]")


FeelingLearnedParameterCategory = Literal[
    "feeling_mapping_strength",
    "feeling_coupling_strength",
    "feeling_persistence",
]


@dataclass(frozen=True)
class InteroceptiveFeelingVector:
    """Owner: interoceptive feeling layer.

    Purpose:
        Represent one immutable dimensional subjective body-feeling vector.

    Failure semantics:
        Values outside the contract range raise `InteroceptiveFeelingError`.
    """

    valence: float
    arousal: float
    tension: float
    comfort: float
    fatigue: float
    pain_like: float
    social_safety: float

    def __post_init__(self) -> None:
        _validate_feeling_value("valence", self.valence)
        _validate_feeling_value("arousal", self.arousal)
        _validate_feeling_value("tension", self.tension)
        _validate_feeling_value("comfort", self.comfort)
        _validate_feeling_value("fatigue", self.fatigue)
        _validate_feeling_value("pain_like", self.pain_like)
        _validate_feeling_value("social_safety", self.social_safety)


@dataclass(frozen=True)
class InteroceptiveFeelingConfig:
    """Owner: interoceptive feeling layer.

    Purpose:
        Expose the confirmed initialization and learned-construction policy for the feeling owner.

    Failure semantics:
        Invalid prior ranges or unsupported learned-parameter policy raise `InteroceptiveFeelingError`.
    """

    baseline_feeling: InteroceptiveFeelingVector
    legal_min: InteroceptiveFeelingVector
    legal_max: InteroceptiveFeelingVector
    mandatory_learned_parameters: tuple[FeelingLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected_learned_parameters = {
            "feeling_mapping_strength",
            "feeling_coupling_strength",
            "feeling_persistence",
        }
        if set(self.mandatory_learned_parameters) != expected_learned_parameters:
            raise InteroceptiveFeelingError(
                "Feeling config must declare the confirmed mandatory learned-parameter categories"
            )
        for dimension_name in self.baseline_feeling.__dataclass_fields__:
            minimum = getattr(self.legal_min, dimension_name)
            baseline = getattr(self.baseline_feeling, dimension_name)
            maximum = getattr(self.legal_max, dimension_name)
            if minimum > maximum:
                raise InteroceptiveFeelingError(
                    f"Feeling config legal range is inverted for dimension '{dimension_name}'"
                )
            if baseline < minimum or baseline > maximum:
                raise InteroceptiveFeelingError(
                    f"Feeling baseline for dimension '{dimension_name}' is outside legal bounds"
                )


@dataclass(frozen=True)
class InteroceptiveFeelingState:
    """Owner: interoceptive feeling layer.

    Purpose:
        Represent one immutable feeling-state snapshot with upstream provenance.

    Failure semantics:
        Missing provenance or malformed feeling values raise `InteroceptiveFeelingError`.
    """

    state_id: str
    source_neuromodulator_state_id: str
    feeling: InteroceptiveFeelingVector
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.state_id:
            raise InteroceptiveFeelingError("InteroceptiveFeelingState must declare a non-empty state_id")
        if not self.source_neuromodulator_state_id:
            raise InteroceptiveFeelingError(
                "InteroceptiveFeelingState must declare a non-empty source_neuromodulator_state_id"
            )


@dataclass(frozen=True)
class UpdateInteroceptiveFeelingOp:
    """Owner: interoceptive feeling layer.

    Purpose:
        Describe one request to update feeling state from neuromodulator state and optional internal signals.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    neuromodulator_state_id: str
    internal_signal_count: int


@dataclass(frozen=True)
class PublishInteroceptiveFeelingStateOp:
    """Owner: interoceptive feeling layer.

    Purpose:
        Describe publication of one interoceptive feeling-state snapshot.

    Failure semantics:
        Publication must not occur if the state snapshot is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    source_neuromodulator_state_id: str
    dominant_dimensions: tuple[str, ...]


class InteroceptiveFeelingError(RuntimeError):
    """Hard-stop error raised when interoceptive feeling owner invariants fail."""


def validate_internal_body_signal(signal: Stimulus) -> None:
    """Validate that a reused sensory stimulus is eligible as an internal body signal for feeling construction."""

    if signal.modality not in {"body", "interoceptive"}:
        raise InteroceptiveFeelingError(
            f"Interoceptive feeling layer only accepts body/interoceptive signals, got '{signal.modality}'"
        )
    if not signal.stimulus_id or not signal.source_name or not signal.provenance_signal_id:
        raise InteroceptiveFeelingError("Internal body signal contains incomplete provenance")


@runtime_checkable
class InteroceptiveFeelingAPI(Protocol):
    """Owner: interoceptive feeling layer API.

    Purpose:
        Define the public owner-facing API from neuromodulator state into feeling-state update.
    """

    def update_state(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...] = (),
        tick_id: int | None = None,
    ) -> InteroceptiveFeelingState:
        """Owner: interoceptive feeling layer.

        Purpose:
            Consume one neuromodulator state snapshot and optional internal signals and return one feeling-state snapshot.

        Inputs:
            A `NeuromodulatorState`, optional `Stimulus` values limited to `body` or `interoceptive` modality, and an optional runtime tick id.

        Returns:
            An `InteroceptiveFeelingState` owned by the interoceptive feeling layer.

        Raises:
            InteroceptiveFeelingError when required input or construction invariants are violated.

        Notes:
            The returned state contains subjective feeling semantics only, not memory or action semantics.
        """

        ...

    def build_update_op(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...] = (),
    ) -> UpdateInteroceptiveFeelingOp:
        """Owner: interoceptive feeling layer.

        Purpose:
            Build the request op describing one feeling update request.

        Inputs:
            One `NeuromodulatorState` and optional internal body signals.

        Returns:
            An `UpdateInteroceptiveFeelingOp` summarizing the request.

        Raises:
            InteroceptiveFeelingError if the request cannot be represented safely.

        Notes:
            This op does not execute feeling construction by itself.
        """

        ...

    def build_publish_state_op(self, state: InteroceptiveFeelingState) -> PublishInteroceptiveFeelingStateOp:
        """Owner: interoceptive feeling layer.

        Purpose:
            Build the publication op for one feeling-state snapshot.

        Inputs:
            An `InteroceptiveFeelingState` produced by this owner.

        Returns:
            A `PublishInteroceptiveFeelingStateOp` summarizing publication metadata.

        Raises:
            InteroceptiveFeelingError if the state is malformed.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        ...