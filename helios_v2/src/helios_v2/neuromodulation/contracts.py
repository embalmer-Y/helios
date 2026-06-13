"""Owner: neuromodulator system.

Owns:
- independently modeled neuromodulator state contracts
- modulation update API boundary from rapid appraisal
- update and publication ops contracts

Does not own:
- subjective feeling construction
- memory tagging
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.appraisal import RapidAppraisalBatch


def _validate_level(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise NeuromodulatorError(f"Neuromodulator level '{name}' must be within [0.0, 1.0]")


LearnedParameterCategory = Literal[
    "channel_gain_sensitivity",
    "cross_channel_coupling_strength",
    "decay_speed_persistence",
    "gate_influence_strength",
    # R81: the bounded coupling gain (and agreement deadzone) by which a corroborated model
    # hormone forecast biases the formula drive. A distinct learnable surface from the channel
    # gains, so P5 can tune the forecast-corroboration coupling independently.
    "hormone_predict_coupling",
]

DecayFamily = Literal["dual_timescale_tonic_phasic"]


@dataclass(frozen=True)
class NeuromodulatorLevels:
    """Owner: neuromodulator system.

    Purpose:
        Represent one immutable independently modeled neuromodulator level vector.

    Failure semantics:
        Channel values outside the contract range raise `NeuromodulatorError`.
    """

    dopamine: float
    norepinephrine: float
    serotonin: float
    acetylcholine: float
    cortisol: float
    oxytocin: float
    opioid_tone: float
    excitation: float
    inhibition: float

    def __post_init__(self) -> None:
        _validate_level("dopamine", self.dopamine)
        _validate_level("norepinephrine", self.norepinephrine)
        _validate_level("serotonin", self.serotonin)
        _validate_level("acetylcholine", self.acetylcholine)
        _validate_level("cortisol", self.cortisol)
        _validate_level("oxytocin", self.oxytocin)
        _validate_level("opioid_tone", self.opioid_tone)
        _validate_level("excitation", self.excitation)
        _validate_level("inhibition", self.inhibition)


@dataclass(frozen=True)
class NeuromodulatorConfig:
    """Owner: neuromodulator system.

    Purpose:
        Expose the confirmed initialization and learned-parameter policy for the neuromodulator owner.

    Failure semantics:
        Invalid prior ranges or unsupported learned-parameter policy raise `NeuromodulatorError`.
    """

    tonic_baseline: NeuromodulatorLevels
    legal_min: NeuromodulatorLevels
    legal_max: NeuromodulatorLevels
    mandatory_learned_parameters: tuple[LearnedParameterCategory, ...]
    decay_family: DecayFamily = "dual_timescale_tonic_phasic"
    hard_gate_eligibility_channels: tuple[str, ...] = ("cortisol", "inhibition")

    def __post_init__(self) -> None:
        expected_learned_parameters = {
            "channel_gain_sensitivity",
            "cross_channel_coupling_strength",
            "decay_speed_persistence",
            "gate_influence_strength",
            "hormone_predict_coupling",
        }
        if set(self.mandatory_learned_parameters) != expected_learned_parameters:
            raise NeuromodulatorError(
                "Neuromodulator config must declare the confirmed mandatory learned-parameter categories"
            )
        if tuple(sorted(self.hard_gate_eligibility_channels)) != ("cortisol", "inhibition"):
            raise NeuromodulatorError(
                "Only cortisol and inhibition may emit hard-gate eligibility signals in this slice"
            )
        for channel_name in self.tonic_baseline.__dataclass_fields__:
            minimum = getattr(self.legal_min, channel_name)
            baseline = getattr(self.tonic_baseline, channel_name)
            maximum = getattr(self.legal_max, channel_name)
            if minimum > maximum:
                raise NeuromodulatorError(
                    f"Neuromodulator config legal range is inverted for channel '{channel_name}'"
                )
            if baseline < minimum or baseline > maximum:
                raise NeuromodulatorError(
                    f"Neuromodulator tonic baseline for channel '{channel_name}' is outside legal bounds"
                )


@dataclass(frozen=True)
class NeuromodulatorState:
    """Owner: neuromodulator system.

    Purpose:
        Represent one immutable neuromodulator state snapshot with upstream provenance.

    Failure semantics:
        Missing provenance or malformed levels raise `NeuromodulatorError`.
    """

    state_id: str
    source_appraisal_batch_id: str
    levels: NeuromodulatorLevels
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.state_id:
            raise NeuromodulatorError("NeuromodulatorState must declare a non-empty state_id")
        if not self.source_appraisal_batch_id:
            raise NeuromodulatorError("NeuromodulatorState must declare a non-empty source_appraisal_batch_id")


@dataclass(frozen=True)
class UpdateNeuromodulatorsOp:
    """Owner: neuromodulator system.

    Purpose:
        Describe one request to update neuromodulator state from an appraisal batch.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    appraisal_batch_id: str
    appraisal_count: int
    source_names: tuple[str, ...]


@dataclass(frozen=True)
class PublishNeuromodulatorStateOp:
    """Owner: neuromodulator system.

    Purpose:
        Describe publication of one neuromodulator state snapshot.

    Failure semantics:
        Publication must not occur if the state snapshot is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    source_appraisal_batch_id: str
    active_channels: tuple[str, ...]


class NeuromodulatorError(RuntimeError):
    """Hard-stop error raised when neuromodulator owner invariants fail."""


@runtime_checkable
class NeuromodulatorSystemAPI(Protocol):
    """Owner: neuromodulator system API.

    Purpose:
        Define the public owner-facing API from rapid appraisal into neuromodulator state update.
    """

    def update_state(
        self,
        batch: RapidAppraisalBatch,
        tick_id: int | None = None,
        prior_state: "NeuromodulatorState | None" = None,
    ) -> NeuromodulatorState:
        """Owner: neuromodulator system.

        Purpose:
            Consume one rapid appraisal batch and return one neuromodulator state snapshot.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal, an optional runtime tick
            id, and the optional prior-tick `NeuromodulatorState` (`None` on a cold start or for a
            stateless path).

        Returns:
            A `NeuromodulatorState` owned by neuromodulator system.

        Raises:
            NeuromodulatorError when required batch or update invariants are violated.

        Notes:
            `prior_state` is additive (default `None`); a stateless update path ignores it, a
            dual-timescale path uses it as the integrator's prior. The returned state contains
            modulation semantics only, not feeling or action semantics.
        """

        ...

    def build_update_op(self, batch: RapidAppraisalBatch) -> UpdateNeuromodulatorsOp:
        """Owner: neuromodulator system.

        Purpose:
            Build the request op describing one neuromodulator update request.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal.

        Returns:
            An `UpdateNeuromodulatorsOp` summarizing the request.

        Raises:
            NeuromodulatorError if the batch summary cannot be represented safely.

        Notes:
            This op does not execute modulation by itself.
        """

        ...

    def build_publish_state_op(self, state: NeuromodulatorState) -> PublishNeuromodulatorStateOp:
        """Owner: neuromodulator system.

        Purpose:
            Build the publication op for one neuromodulator state snapshot.

        Inputs:
            A `NeuromodulatorState` produced by this owner.

        Returns:
            A `PublishNeuromodulatorStateOp` summarizing publication metadata.

        Raises:
            NeuromodulatorError if the state is malformed.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        ...