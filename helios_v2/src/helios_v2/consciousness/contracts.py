"""Owner: reportable conscious-content layer.

Owns:
- conscious-content material contracts consumed by the owner
- formal conscious-state contracts and publication ops
- workspace-to-consciousness API boundary

Does not own:
- workspace competition
- internal thought execution
- action arbitration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.workspace import WorkingStateSnapshot, WorkspaceCandidateSet


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ConsciousnessError(f"{name} must be within [0.0, 1.0]")


ConsciousCommitStatus = Literal["committed", "no_commit"]
NoCommitReason = Literal[
    "insufficient_commitment_signal",
    "semantic_conflict_unresolved",
    "context_not_reportable",
    "capability_rejected_cycle",
]
ConsciousnessLearnedParameterCategory = Literal[
    "commitment_policy",
    "quiet_state_policy",
    "semantic_shaping_policy",
]

_NO_COMMIT_REASONS = {
    "insufficient_commitment_signal",
    "semantic_conflict_unresolved",
    "context_not_reportable",
    "capability_rejected_cycle",
}


@dataclass(frozen=True)
class ConsciousContentMaterial:
    """Owner: reportable conscious-content layer.

    Purpose:
        Represent one explicit current-cycle material item aligned to one workspace candidate.

    Failure semantics:
        Missing provenance, ref-only payloads, or out-of-range hints raise `ConsciousnessError`.
    """

    material_id: str
    source_workspace_candidate_id: str
    source_memory_candidate_id: str
    source_memory_id: str
    source_feeling_state_id: str
    content_kind: str
    material_summary: str
    summary_ref: str | None
    context_ref: str | None
    salient_tokens: tuple[str, ...]
    affect_tag: InteroceptiveFeelingVector
    forced_consolidation: bool
    workspace_score_hint: float | None
    priority_hint: float | None

    def __post_init__(self) -> None:
        if not self.material_id:
            raise ConsciousnessError("ConsciousContentMaterial must declare a non-empty material_id")
        if not self.source_workspace_candidate_id:
            raise ConsciousnessError(
                "ConsciousContentMaterial must declare a non-empty source_workspace_candidate_id"
            )
        if not self.source_memory_candidate_id:
            raise ConsciousnessError(
                "ConsciousContentMaterial must declare a non-empty source_memory_candidate_id"
            )
        if not self.source_memory_id:
            raise ConsciousnessError("ConsciousContentMaterial must declare a non-empty source_memory_id")
        if not self.source_feeling_state_id:
            raise ConsciousnessError(
                "ConsciousContentMaterial must declare a non-empty source_feeling_state_id"
            )
        if not self.content_kind:
            raise ConsciousnessError("ConsciousContentMaterial must declare a non-empty content_kind")
        if not self.material_summary:
            raise ConsciousnessError(
                "ConsciousContentMaterial must declare a non-empty material_summary"
            )
        if any(not token for token in self.salient_tokens):
            raise ConsciousnessError(
                "ConsciousContentMaterial salient_tokens must not contain empty values"
            )
        if self.workspace_score_hint is not None:
            _validate_unit_interval(
                "ConsciousContentMaterial.workspace_score_hint",
                self.workspace_score_hint,
            )
        if self.priority_hint is not None:
            _validate_unit_interval(
                "ConsciousContentMaterial.priority_hint",
                self.priority_hint,
            )


@dataclass(frozen=True)
class ConsciousContentMaterialSet:
    """Owner: reportable conscious-content layer.

    Purpose:
        Represent one explicit current-cycle material bundle covering the full workspace candidate set.

    Failure semantics:
        Missing provenance, empty material coverage, or duplicate candidate alignment raise `ConsciousnessError`.
    """

    set_id: str
    source_workspace_candidate_set_id: str
    source_working_state_id: str
    materials: tuple[ConsciousContentMaterial, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.set_id:
            raise ConsciousnessError("ConsciousContentMaterialSet must declare a non-empty set_id")
        if not self.source_workspace_candidate_set_id:
            raise ConsciousnessError(
                "ConsciousContentMaterialSet must declare a non-empty source_workspace_candidate_set_id"
            )
        if not self.source_working_state_id:
            raise ConsciousnessError(
                "ConsciousContentMaterialSet must declare a non-empty source_working_state_id"
            )
        if not self.materials:
            raise ConsciousnessError(
                "ConsciousContentMaterialSet must declare at least one ConsciousContentMaterial"
            )
        material_ids = {material.material_id for material in self.materials}
        candidate_ids = {material.source_workspace_candidate_id for material in self.materials}
        if len(material_ids) != len(self.materials):
            raise ConsciousnessError(
                "ConsciousContentMaterialSet must not contain duplicate material_id values"
            )
        if len(candidate_ids) != len(self.materials):
            raise ConsciousnessError(
                "ConsciousContentMaterialSet must not contain duplicate source_workspace_candidate_id values"
            )


@dataclass(frozen=True)
class ReportableConsciousContent:
    """Owner: reportable conscious-content layer.

    Purpose:
        Represent one semantic focal conscious item that downstream owners may report without ref reconstruction.

    Failure semantics:
        Missing provenance or an empty focal summary raise `ConsciousnessError`.
    """

    content_id: str
    source_material_id: str
    source_workspace_candidate_id: str
    source_memory_candidate_id: str
    source_feeling_state_id: str
    content_kind: str
    focal_summary: str
    affect_trace: InteroceptiveFeelingVector
    salient_tokens: tuple[str, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.content_id:
            raise ConsciousnessError("ReportableConsciousContent must declare a non-empty content_id")
        if not self.source_material_id:
            raise ConsciousnessError(
                "ReportableConsciousContent must declare a non-empty source_material_id"
            )
        if not self.source_workspace_candidate_id:
            raise ConsciousnessError(
                "ReportableConsciousContent must declare a non-empty source_workspace_candidate_id"
            )
        if not self.source_memory_candidate_id:
            raise ConsciousnessError(
                "ReportableConsciousContent must declare a non-empty source_memory_candidate_id"
            )
        if not self.source_feeling_state_id:
            raise ConsciousnessError(
                "ReportableConsciousContent must declare a non-empty source_feeling_state_id"
            )
        if not self.content_kind:
            raise ConsciousnessError("ReportableConsciousContent must declare a non-empty content_kind")
        if not self.focal_summary:
            raise ConsciousnessError(
                "ReportableConsciousContent must declare a non-empty focal_summary"
            )
        if any(not token for token in self.salient_tokens):
            raise ConsciousnessError(
                "ReportableConsciousContent salient_tokens must not contain empty values"
            )


@dataclass(frozen=True)
class SupportingContextItem:
    """Owner: reportable conscious-content layer.

    Purpose:
        Represent one auxiliary context item published alongside a focal conscious item.

    Failure semantics:
        Missing provenance or an empty summary raise `ConsciousnessError`.
    """

    context_item_id: str
    source_material_id: str
    source_workspace_candidate_id: str
    content_kind: str
    summary: str
    affect_trace: InteroceptiveFeelingVector

    def __post_init__(self) -> None:
        if not self.context_item_id:
            raise ConsciousnessError("SupportingContextItem must declare a non-empty context_item_id")
        if not self.source_material_id:
            raise ConsciousnessError(
                "SupportingContextItem must declare a non-empty source_material_id"
            )
        if not self.source_workspace_candidate_id:
            raise ConsciousnessError(
                "SupportingContextItem must declare a non-empty source_workspace_candidate_id"
            )
        if not self.content_kind:
            raise ConsciousnessError("SupportingContextItem must declare a non-empty content_kind")
        if not self.summary:
            raise ConsciousnessError("SupportingContextItem must declare a non-empty summary")


@dataclass(frozen=True)
class ConsciousState:
    """Owner: reportable conscious-content layer.

    Purpose:
        Represent one immutable formal conscious-state outcome for one runtime cycle.

    Failure semantics:
        Inconsistent commit/no-commit semantics or malformed provenance raise `ConsciousnessError`.
    """

    state_id: str
    commit_status: ConsciousCommitStatus
    source_workspace_candidate_set_id: str
    source_working_state_id: str
    focal_content: ReportableConsciousContent | None
    supporting_context: tuple[SupportingContextItem, ...]
    no_commit_reason: NoCommitReason | None
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.state_id:
            raise ConsciousnessError("ConsciousState must declare a non-empty state_id")
        if not self.source_workspace_candidate_set_id:
            raise ConsciousnessError(
                "ConsciousState must declare a non-empty source_workspace_candidate_set_id"
            )
        if not self.source_working_state_id:
            raise ConsciousnessError(
                "ConsciousState must declare a non-empty source_working_state_id"
            )
        if len(self.supporting_context) > 2:
            raise ConsciousnessError(
                "ConsciousState supporting_context must not exceed two items in the first version"
            )
        context_ids = {item.context_item_id for item in self.supporting_context}
        if len(context_ids) != len(self.supporting_context):
            raise ConsciousnessError(
                "ConsciousState supporting_context must not contain duplicate context_item_id values"
            )
        if self.commit_status == "committed":
            if self.focal_content is None:
                raise ConsciousnessError(
                    "ConsciousState with commit_status='committed' must publish focal_content"
                )
            if self.no_commit_reason is not None:
                raise ConsciousnessError(
                    "ConsciousState with commit_status='committed' must not publish no_commit_reason"
                )
        elif self.commit_status == "no_commit":
            if self.focal_content is not None:
                raise ConsciousnessError(
                    "ConsciousState with commit_status='no_commit' must not publish focal_content"
                )
            if self.no_commit_reason not in _NO_COMMIT_REASONS:
                raise ConsciousnessError(
                    "ConsciousState with commit_status='no_commit' must use the fixed no_commit taxonomy"
                )
        else:
            raise ConsciousnessError("ConsciousState commit_status is outside the confirmed contract")


@dataclass(frozen=True)
class ConsciousnessConfig:
    """Owner: reportable conscious-content layer.

    Purpose:
        Expose the confirmed initialization and learned-policy surface for conscious commitment.

    Failure semantics:
        Invalid score ranges, unsupported learned parameters, or an invalid support cap raise `ConsciousnessError`.
    """

    legal_min_score: float
    legal_max_score: float
    conscious_state_bootstrap_id: str
    max_supporting_context_items: int
    mandatory_learned_parameters: tuple[ConsciousnessLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "commitment_policy",
            "quiet_state_policy",
            "semantic_shaping_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise ConsciousnessError(
                "Consciousness config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("ConsciousnessConfig.legal_min_score", self.legal_min_score)
        _validate_unit_interval("ConsciousnessConfig.legal_max_score", self.legal_max_score)
        if self.legal_min_score > self.legal_max_score:
            raise ConsciousnessError("Consciousness config score range is inverted")
        if not self.conscious_state_bootstrap_id:
            raise ConsciousnessError(
                "Consciousness config must declare a non-empty conscious_state_bootstrap_id"
            )
        if self.max_supporting_context_items < 0 or self.max_supporting_context_items > 2:
            raise ConsciousnessError(
                "Consciousness config max_supporting_context_items must be within [0, 2]"
            )


@dataclass(frozen=True)
class CommitConsciousContentOp:
    """Owner: reportable conscious-content layer.

    Purpose:
        Describe one request to commit reportable conscious content from current-cycle materials.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    workspace_candidate_count: int
    retained_candidate_count: int
    material_count: int
    working_state_id: str
    forced_material_count: int


@dataclass(frozen=True)
class PublishConsciousStateOp:
    """Owner: reportable conscious-content layer.

    Purpose:
        Describe publication of one formal conscious state.

    Failure semantics:
        Publication must not occur if the state snapshot is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    commit_status: ConsciousCommitStatus
    no_commit_reason: NoCommitReason | None
    supporting_context_count: int


@dataclass(frozen=True)
class PublishReportableConsciousContentOp:
    """Owner: reportable conscious-content layer.

    Purpose:
        Describe publication of one committed reportable conscious-content payload.

    Failure semantics:
        Publication must not occur if the focal content is malformed or absent.
    """

    op_name: str
    owner: str
    state_id: str
    content_id: str
    source_material_id: str


class ConsciousnessError(RuntimeError):
    """Hard-stop error raised when reportable conscious-content owner invariants fail."""


@runtime_checkable
class ConsciousContentAPI(Protocol):
    """Owner: reportable conscious-content layer API.

    Purpose:
        Define the public owner-facing API from workspace outputs plus explicit current-cycle material into one conscious-state outcome.
    """

    def commit_content(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        tick_id: int | None = None,
    ) -> ConsciousState:
        """Owner: reportable conscious-content layer.

        Purpose:
            Consume one workspace candidate set, one working-state snapshot, and one explicit material set to produce one formal conscious state.

        Inputs:
            One `WorkspaceCandidateSet`, one `WorkingStateSnapshot`, one `ConsciousContentMaterialSet`, and an optional runtime tick id.

        Returns:
            One `ConsciousState` owned by the reportable conscious-content layer.

        Raises:
            ConsciousnessError when required inputs or owner invariants are violated.

        Notes:
            This public API is intentionally limited to current-cycle inputs only.
        """

        ...

    def build_commit_op(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
    ) -> CommitConsciousContentOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the request op describing one conscious-content commitment cycle.

        Inputs:
            One `WorkspaceCandidateSet`, one `WorkingStateSnapshot`, and one `ConsciousContentMaterialSet`.

        Returns:
            A `CommitConsciousContentOp` summarizing the current-cycle request.

        Raises:
            ConsciousnessError if the request cannot be represented safely.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        ...

    def build_publish_state_op(
        self,
        state: ConsciousState,
    ) -> PublishConsciousStateOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the publication op for one formal conscious state.

        Inputs:
            One `ConsciousState` produced by this owner.

        Returns:
            A `PublishConsciousStateOp` summarizing publication.

        Raises:
            ConsciousnessError if the state is malformed.
        """

        ...

    def build_publish_reportable_content_op(
        self,
        state: ConsciousState,
    ) -> PublishReportableConsciousContentOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the publication op for one committed focal conscious-content payload.

        Inputs:
            One `ConsciousState` with `commit_status='committed'`.

        Returns:
            A `PublishReportableConsciousContentOp` summarizing focal payload publication.

        Raises:
            ConsciousnessError if the state has no committed focal content.
        """

        ...