"""Owner: neuromodulator system.

Owns:
- batch-level neuromodulator update orchestration
- update-path invocation order
- request and publication op construction

Does not own:
- permanent modulation strategy semantics
- subjective feeling construction
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.appraisal import RapidAppraisalBatch

from .contracts import (
    NeuromodulatorConfig,
    NeuromodulatorError,
    NeuromodulatorLevels,
    NeuromodulatorState,
    NeuromodulatorSystemAPI,
    PublishNeuromodulatorStateOp,
    UpdateNeuromodulatorsOp,
)


def _validate_appraisal_batch(batch: RapidAppraisalBatch) -> None:
    if not batch.batch_id:
        raise NeuromodulatorError("RapidAppraisalBatch must declare a non-empty batch_id")
    for appraisal in batch.appraisals:
        if not appraisal.appraisal_id or not appraisal.source_name or not appraisal.provenance_signal_id:
            raise NeuromodulatorError("RapidAppraisalBatch contains appraisal with incomplete provenance")


@runtime_checkable
class NeuromodulatorUpdatePath(Protocol):
    """Owner: neuromodulator system.

    Purpose:
        Produce the next neuromodulator levels from a validated appraisal batch and owner config.
    """

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
    ) -> NeuromodulatorLevels:
        """Owner: neuromodulator system.

        Purpose:
            Produce the next independently modeled neuromodulator levels.

        Inputs:
            A validated `RapidAppraisalBatch`, one owner `NeuromodulatorConfig`, and an optional runtime tick id.

        Returns:
            One `NeuromodulatorLevels` value within contract range.

        Raises:
            NeuromodulatorError if the required update capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved modulation semantics are not guessed here.
        """


@runtime_checkable
class ActiveChannelReporter(Protocol):
    """Owner: neuromodulator system.

    Purpose:
        Report active channels for publication diagnostics without hardcoding threshold heuristics in the owner skeleton.
    """

    def report_active_channels(
        self,
        state: NeuromodulatorState,
        config: NeuromodulatorConfig,
    ) -> tuple[str, ...]:
        """Owner: neuromodulator system.

        Purpose:
            Report the channel names that should appear as active in publication diagnostics.

        Inputs:
            One `NeuromodulatorState` and the owner config used to construct it.

        Returns:
            A stable tuple of active channel names.

        Raises:
            NeuromodulatorError if active-channel reporting cannot proceed safely.

        Notes:
            This interface keeps unresolved activity semantics out of the public owner skeleton.
        """


@dataclass
class NeuromodulatorEngine(NeuromodulatorSystemAPI):
    """Owner: neuromodulator system.

    Purpose:
        Execute neuromodulator state updates using injected update and reporting collaborators.

    Failure semantics:
        Malformed appraisal batches fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: NeuromodulatorConfig
    update_path: NeuromodulatorUpdatePath
    active_channel_reporter: ActiveChannelReporter

    def update_state(self, batch: RapidAppraisalBatch, tick_id: int | None = None) -> NeuromodulatorState:
        """Owner: neuromodulator system.

        Purpose:
            Consume one rapid appraisal batch and return one neuromodulator state snapshot.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal and an optional runtime tick id.

        Returns:
            A `NeuromodulatorState` containing independently modeled channel levels.

        Raises:
            NeuromodulatorError when batch invariants or update-path outputs are invalid.

        Notes:
            Remaining unresolved modulation semantics stay inside the injected update path.
        """

        _validate_appraisal_batch(batch)
        levels = self.update_path.update_levels(batch, self.config, tick_id)
        return NeuromodulatorState(
            state_id=f"neuromodulator-state:{batch.batch_id}:{tick_id if tick_id is not None else 'na'}",
            source_appraisal_batch_id=batch.batch_id,
            levels=levels,
            tick_id=tick_id,
        )

    def build_update_op(self, batch: RapidAppraisalBatch) -> UpdateNeuromodulatorsOp:
        """Owner: neuromodulator system.

        Purpose:
            Build the request op describing one neuromodulator update request.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal.

        Returns:
            An `UpdateNeuromodulatorsOp` summarizing batch identity and source coverage.

        Raises:
            NeuromodulatorError if the batch is malformed.

        Notes:
            This method validates provenance before creating the request op.
        """

        _validate_appraisal_batch(batch)
        return UpdateNeuromodulatorsOp(
            op_name="update_neuromodulators",
            owner="neuromodulator_system",
            appraisal_batch_id=batch.batch_id,
            appraisal_count=len(batch.appraisals),
            source_names=tuple(sorted({appraisal.source_name for appraisal in batch.appraisals})),
        )

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
            Active channel reporting stays injectable until the unresolved semantics are confirmed.
        """

        if not state.state_id or not state.source_appraisal_batch_id:
            raise NeuromodulatorError("NeuromodulatorState contains incomplete provenance")
        active_channels = self.active_channel_reporter.report_active_channels(state, self.config)
        return PublishNeuromodulatorStateOp(
            op_name="publish_neuromodulator_state",
            owner="neuromodulator_system",
            state_id=state.state_id,
            source_appraisal_batch_id=state.source_appraisal_batch_id,
            active_channels=tuple(sorted(active_channels)),
        )