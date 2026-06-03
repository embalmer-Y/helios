"""Owner: memory affect and replay layer.

Owns:
- memory-record orchestration
- memory/replay collaborator invocation order
- record and publication op construction

Does not own:
- permanent replay strategy semantics
- conscious workspace promotion
- identity writeback
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState

from .contracts import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayAPI,
    MemoryAffectReplayConfig,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryFormationState,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    PublishMemoryFormationStateOp,
    PublishReplayCandidatesOp,
    RecordMemoryOp,
    validate_prediction_mismatch_evidence,
)


def _validate_feeling_state(state: InteroceptiveFeelingState) -> None:
    if not state.state_id:
        raise MemoryAffectReplayError("InteroceptiveFeelingState must declare a non-empty state_id")
    if not state.source_neuromodulator_state_id:
        raise MemoryAffectReplayError(
            "InteroceptiveFeelingState must declare a non-empty source_neuromodulator_state_id"
        )


def _validate_memory_items(
    memory_items: tuple[AffectTaggedMemoryItem, ...],
    feeling_state: InteroceptiveFeelingState,
    binding_context: MemoryBindingContext | None,
) -> None:
    expected_binding_context_id = binding_context.context_id if binding_context is not None else None
    for item in memory_items:
        if item.source_feeling_state_id != feeling_state.state_id:
            raise MemoryAffectReplayError(
                "Memory items must preserve the source feeling state provenance used for formation"
            )
        if item.binding_context_id != expected_binding_context_id:
            raise MemoryAffectReplayError(
                "Memory items must preserve the binding_context_id of the explicit binding context"
            )


def _validate_replay_candidates(
    replay_candidates: tuple[MemoryReplayCandidate, ...],
    memory_items: tuple[AffectTaggedMemoryItem, ...],
    feeling_state: InteroceptiveFeelingState,
) -> None:
    published_memory_ids = {item.memory_id for item in memory_items}
    for candidate in replay_candidates:
        if candidate.memory_id not in published_memory_ids:
            raise MemoryAffectReplayError(
                "Replay candidates must reference memory items published in the same owner state"
            )
        if candidate.source_feeling_state_id != feeling_state.state_id:
            raise MemoryAffectReplayError(
                "Replay candidates must preserve the source feeling state provenance used for formation"
            )


@runtime_checkable
class MemoryFormationPath(Protocol):
    """Owner: memory affect and replay layer.

    Purpose:
        Produce the next affect-tagged memory items from validated upstream feeling state and explicit binding inputs.
    """

    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        """Owner: memory affect and replay layer.

        Purpose:
            Produce one immutable tuple of affect-tagged memory items.

        Inputs:
            One validated `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`, one owner config, and an optional tick id.

        Returns:
            A tuple of `AffectTaggedMemoryItem` values.

        Raises:
            MemoryAffectReplayError if required memory-formation capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved write semantics are not guessed here.
        """


@runtime_checkable
class ReplayCandidateSelector(Protocol):
    """Owner: memory affect and replay layer.

    Purpose:
        Select replay candidates and bounded continuous priority hints without hardcoding replay thresholds into the owner skeleton.
    """

    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        """Owner: memory affect and replay layer.

        Purpose:
            Produce replay candidates from owner-produced memory items.

        Inputs:
            One tuple of `AffectTaggedMemoryItem`, one validated `InteroceptiveFeelingState`, optional `PredictionMismatchEvidence`, and one owner config.

        Returns:
            A tuple of `MemoryReplayCandidate` values.

        Raises:
            MemoryAffectReplayError if required replay-selection capability is unavailable or unsafe.

        Notes:
            This interface keeps unresolved replay-trigger scoring semantics out of the public owner skeleton.
        """


@dataclass
class MemoryAffectReplayEngine(MemoryAffectReplayAPI):
    """Owner: memory affect and replay layer.

    Purpose:
        Execute affect-linked memory formation and replay-candidate publication using injected collaborators.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: MemoryAffectReplayConfig
    formation_path: MemoryFormationPath
    replay_selector: ReplayCandidateSelector

    def record_state(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None = None,
        mismatch_evidence: PredictionMismatchEvidence | None = None,
        tick_id: int | None = None,
    ) -> MemoryFormationState:
        """Owner: memory affect and replay layer.

        Purpose:
            Consume one feeling-state snapshot and return one owner state containing memory items and replay candidates.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`, and an optional runtime tick id.

        Returns:
            A `MemoryFormationState` containing owner-produced memory items and replay candidates.

        Raises:
            MemoryAffectReplayError when input invariants or collaborator outputs are invalid.

        Notes:
            Remaining unresolved retrieval, workspace-promotion, and identity-writeback semantics stay outside this owner skeleton.
        """

        _validate_feeling_state(feeling_state)
        validate_prediction_mismatch_evidence(mismatch_evidence)
        memory_items = self.formation_path.form_memory_items(
            feeling_state,
            binding_context,
            mismatch_evidence,
            self.config,
            tick_id,
        )
        _validate_memory_items(tuple(memory_items), feeling_state, binding_context)
        replay_candidates = self.replay_selector.select_candidates(
            memory_items,
            feeling_state,
            mismatch_evidence,
            self.config,
        )
        _validate_replay_candidates(tuple(replay_candidates), tuple(memory_items), feeling_state)
        return MemoryFormationState(
            state_id=f"memory-formation-state:{feeling_state.state_id}:{tick_id if tick_id is not None else 'na'}",
            source_feeling_state_id=feeling_state.state_id,
            memory_items=tuple(memory_items),
            replay_candidates=tuple(replay_candidates),
            tick_id=tick_id,
        )

    def build_record_op(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None = None,
        mismatch_evidence: PredictionMismatchEvidence | None = None,
    ) -> RecordMemoryOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the request op describing one affect-linked memory recording request.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, and optional `PredictionMismatchEvidence`.

        Returns:
            A `RecordMemoryOp` summarizing request identity and explicit optional evidence.

        Raises:
            MemoryAffectReplayError if the request is malformed.

        Notes:
            This method validates upstream provenance and optional mismatch-evidence eligibility before creating the request op.
        """

        _validate_feeling_state(feeling_state)
        mismatch_evidence = validate_prediction_mismatch_evidence(mismatch_evidence)
        return RecordMemoryOp(
            op_name="record_memory_affect_state",
            owner="memory_affect_and_replay",
            feeling_state_id=feeling_state.state_id,
            binding_context_id=binding_context.context_id if binding_context is not None else None,
            mismatch_evidence_id=mismatch_evidence.evidence_id if mismatch_evidence is not None else None,
        )

    def build_publish_replay_candidates_op(self, state: MemoryFormationState) -> PublishReplayCandidatesOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the publication op for replay candidates contained in one memory-formation state.

        Inputs:
            One `MemoryFormationState` produced by this owner.

        Returns:
            A `PublishReplayCandidatesOp` summarizing replay-candidate publication.

        Raises:
            MemoryAffectReplayError if the state is malformed.

        Notes:
            Candidate publication remains separate from later workspace promotion and competition ownership.
        """

        if not state.state_id or not state.source_feeling_state_id:
            raise MemoryAffectReplayError("MemoryFormationState contains incomplete provenance")
        families = tuple(sorted({candidate.family for candidate in state.replay_candidates}))
        return PublishReplayCandidatesOp(
            op_name="publish_memory_replay_candidates",
            owner="memory_affect_and_replay",
            state_id=state.state_id,
            candidate_count=len(state.replay_candidates),
            families=families,
        )

    def build_publish_state_op(self, state: MemoryFormationState) -> PublishMemoryFormationStateOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the publication op for one memory-formation state snapshot.

        Inputs:
            One `MemoryFormationState` produced by this owner.

        Returns:
            A `PublishMemoryFormationStateOp` summarizing owner-state publication.

        Raises:
            MemoryAffectReplayError if the state is malformed.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        if not state.state_id or not state.source_feeling_state_id:
            raise MemoryAffectReplayError("MemoryFormationState contains incomplete provenance")
        return PublishMemoryFormationStateOp(
            op_name="publish_memory_formation_state",
            owner="memory_affect_and_replay",
            state_id=state.state_id,
            source_feeling_state_id=state.source_feeling_state_id,
            memory_count=len(state.memory_items),
            candidate_count=len(state.replay_candidates),
        )