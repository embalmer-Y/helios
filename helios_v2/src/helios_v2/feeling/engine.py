"""Owner: interoceptive feeling layer.

Owns:
- batch-level feeling update orchestration
- construction-path invocation order
- request and publication op construction

Does not own:
- permanent feeling strategy semantics
- memory tagging
- action gating
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.neuromodulation import NeuromodulatorState
from helios_v2.sensory import Stimulus

from .contracts import (
    InteroceptiveFeelingAPI,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingError,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
    PublishInteroceptiveFeelingStateOp,
    UpdateInteroceptiveFeelingOp,
    validate_internal_body_signal,
)


def _validate_neuromodulator_state(state: NeuromodulatorState) -> None:
    if not state.state_id:
        raise InteroceptiveFeelingError("NeuromodulatorState must declare a non-empty state_id")
    if not state.source_appraisal_batch_id:
        raise InteroceptiveFeelingError("NeuromodulatorState must declare a non-empty source_appraisal_batch_id")


@runtime_checkable
class FeelingConstructionPath(Protocol):
    """Owner: interoceptive feeling layer.

    Purpose:
        Produce the next feeling vector from validated upstream state and owner config.
    """

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        """Owner: interoceptive feeling layer.

        Purpose:
            Produce the next dimensional feeling vector.

        Inputs:
            One validated `NeuromodulatorState`, optional validated internal signals, one owner config, and an optional tick id.

        Returns:
            One `InteroceptiveFeelingVector` within contract range.

        Raises:
            InteroceptiveFeelingError if the required construction capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved construction semantics are not guessed here.
        """


@runtime_checkable
class DominantDimensionReporter(Protocol):
    """Owner: interoceptive feeling layer.

    Purpose:
        Report dominant dimensions for publication diagnostics without hardcoding ranking or threshold semantics.
    """

    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        """Owner: interoceptive feeling layer.

        Purpose:
            Report the dimension names that should appear as dominant in publication diagnostics.

        Inputs:
            One `InteroceptiveFeelingState` and the owner config used to construct it.

        Returns:
            A stable tuple of dominant dimension names.

        Raises:
            InteroceptiveFeelingError if dominant-dimension reporting cannot proceed safely.

        Notes:
            This interface keeps unresolved reporting semantics out of the public owner skeleton.
        """


@dataclass
class InteroceptiveFeelingEngine(InteroceptiveFeelingAPI):
    """Owner: interoceptive feeling layer.

    Purpose:
        Execute feeling-state updates using injected construction and reporting collaborators.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: InteroceptiveFeelingConfig
    construction_path: FeelingConstructionPath
    dominant_dimension_reporter: DominantDimensionReporter

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
            One `NeuromodulatorState`, optional body/interoceptive `Stimulus` values, and an optional runtime tick id.

        Returns:
            An `InteroceptiveFeelingState` containing the owner-produced dimensional feeling vector.

        Raises:
            InteroceptiveFeelingError when input invariants or construction-path outputs are invalid.

        Notes:
            Remaining unresolved feeling semantics stay inside the injected construction path.
        """

        _validate_neuromodulator_state(neuromodulator_state)
        for signal in internal_signals:
            validate_internal_body_signal(signal)
        feeling = self.construction_path.construct_feeling(
            neuromodulator_state,
            internal_signals,
            self.config,
            tick_id,
        )
        return InteroceptiveFeelingState(
            state_id=f"interoceptive-feeling-state:{neuromodulator_state.state_id}:{tick_id if tick_id is not None else 'na'}",
            source_neuromodulator_state_id=neuromodulator_state.state_id,
            feeling=feeling,
            tick_id=tick_id,
        )

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
            An `UpdateInteroceptiveFeelingOp` summarizing request identity and optional internal-signal count.

        Raises:
            InteroceptiveFeelingError if the request is malformed.

        Notes:
            This method validates upstream provenance and input eligibility before creating the request op.
        """

        _validate_neuromodulator_state(neuromodulator_state)
        for signal in internal_signals:
            validate_internal_body_signal(signal)
        return UpdateInteroceptiveFeelingOp(
            op_name="update_interoceptive_feeling",
            owner="interoceptive_feeling_layer",
            neuromodulator_state_id=neuromodulator_state.state_id,
            internal_signal_count=len(internal_signals),
        )

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
            Dominant-dimension reporting stays injectable until the unresolved semantics are confirmed.
        """

        if not state.state_id or not state.source_neuromodulator_state_id:
            raise InteroceptiveFeelingError("InteroceptiveFeelingState contains incomplete provenance")
        dominant_dimensions = self.dominant_dimension_reporter.report_dominant_dimensions(state, self.config)
        return PublishInteroceptiveFeelingStateOp(
            op_name="publish_interoceptive_feeling_state",
            owner="interoceptive_feeling_layer",
            state_id=state.state_id,
            source_neuromodulator_state_id=state.source_neuromodulator_state_id,
            dominant_dimensions=tuple(sorted(dominant_dimensions)),
        )