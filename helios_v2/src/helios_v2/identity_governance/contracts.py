"""Owner: identity governance and self-revision integration.

Owns:
- normalized self-revision proposal, governance request, pressure, result, and applied-state contracts
- governance decision and publication ops
- identity-governance API surface

Does not own:
- internal thought generation
- personality projection rendering or sync application
- audit persistence
- memory-system mutation outside identity state publication
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.internal_thought import ThoughtCycleResult


class IdentityGovernanceError(RuntimeError):
    """Hard-stop error raised when identity-governance owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise IdentityGovernanceError(f"{name} must be within [0.0, 1.0]")


RevisionStatus = Literal[
    "accepted",
    "accepted_with_monitoring",
    "rejected",
    "invalid_proposal",
]
GovernancePressureLevel = Literal["none", "monitor", "stabilize"]
GovernanceRejectionReason = Literal[
    "invalid_self_revision_payload",
    "unsupported_revision_type",
    "identity_boundary_violation",
    "missing_self_definition",
    "missing_personality_adjustment",
    "missing_identity_narrative",
    "governance_backpressure",
]
IdentityGovernanceLearnedParameterCategory = Literal[
    "governance_evaluation_policy",
    "pressure_interpretation_policy",
    "supported_revision_policy",
    "boundary_check_policy",
]

_REVISION_STATUSES = {
    "accepted",
    "accepted_with_monitoring",
    "rejected",
    "invalid_proposal",
}
_PRESSURE_LEVELS = {"none", "monitor", "stabilize"}
_GOVERNANCE_REJECTION_REASONS = {
    "invalid_self_revision_payload",
    "unsupported_revision_type",
    "identity_boundary_violation",
    "missing_self_definition",
    "missing_personality_adjustment",
    "missing_identity_narrative",
    "governance_backpressure",
}


@dataclass(frozen=True)
class GovernedActionAuthorization:
    """Immutable `14` authorization verdict for one pending governed action (requirement 86).

    Owner: identity governance and self-revision integration.

    Purpose:
        The governance authority's authorize/deny decision for a `governed`-tier tool action that the
        `13` planner fail-closed pending authorization. Keyed by the planner's stable
        `action_authorization_key` so a re-proposed action on a later tick matches this verdict. `14`
        authorizes only the action's authorization; it never selects, binds, or executes a channel.

    Failure semantics:
        Construction raises `IdentityGovernanceError` on an empty key, an empty reason, or empty
        reason-trace items.
    """

    action_authorization_key: str
    authorized: bool
    reason: str
    reason_trace: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.action_authorization_key:
            raise IdentityGovernanceError(
                "GovernedActionAuthorization must declare a non-empty action_authorization_key"
            )
        if not self.reason:
            raise IdentityGovernanceError("GovernedActionAuthorization must declare a non-empty reason")
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise IdentityGovernanceError(
                "GovernedActionAuthorization must declare non-empty reason_trace items"
            )


@dataclass(frozen=True)
class IdentityGovernanceConfig:
    """Expose the confirmed initialization and learned-policy surface for identity governance."""

    legal_min_confidence: float
    legal_max_confidence: float
    governance_bootstrap_id: str
    mandatory_learned_parameters: tuple[IdentityGovernanceLearnedParameterCategory, ...]
    authorized_governed_action_prefixes: tuple[tuple[str, ...], ...] = ()

    def __post_init__(self) -> None:
        expected = {
            "governance_evaluation_policy",
            "pressure_interpretation_policy",
            "supported_revision_policy",
            "boundary_check_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise IdentityGovernanceError(
                "Identity-governance config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval(
            "IdentityGovernanceConfig.legal_min_confidence",
            self.legal_min_confidence,
        )
        _validate_unit_interval(
            "IdentityGovernanceConfig.legal_max_confidence",
            self.legal_max_confidence,
        )
        if self.legal_min_confidence > self.legal_max_confidence:
            raise IdentityGovernanceError("Identity-governance confidence range is inverted")
        if not self.governance_bootstrap_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceConfig must declare a non-empty governance_bootstrap_id"
            )


@dataclass(frozen=True)
class IdentityGovernanceRequest:
    """Explicit governance input contract for one self-revision cycle."""

    request_id: str
    source_thought_cycle_result_id: str
    source_proposal_id: str | None
    proposal_present: bool
    proposal_snapshot: Mapping[str, object]
    identity_state_snapshot: Mapping[str, object]
    governance_trace_summary: Mapping[str, object]
    recent_governance_trace_history: tuple[Mapping[str, object], ...]
    tick_id: int | None
    pending_governed_action: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceRequest must declare a non-empty request_id"
            )
        if not self.source_thought_cycle_result_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceRequest must declare a non-empty source_thought_cycle_result_id"
            )
        if self.proposal_present and not self.source_proposal_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceRequest with proposal_present=True must declare source_proposal_id"
            )
        for attr_name in (
            "proposal_snapshot",
            "identity_state_snapshot",
            "governance_trace_summary",
        ):
            mapping = MappingProxyType(dict(getattr(self, attr_name)))
            for key in mapping:
                if not key:
                    raise IdentityGovernanceError(
                        f"IdentityGovernanceRequest {attr_name} must not contain empty keys"
                    )
            object.__setattr__(self, attr_name, mapping)
        history: list[Mapping[str, object]] = []
        for entry in self.recent_governance_trace_history:
            proxy = MappingProxyType(dict(entry))
            for key in proxy:
                if not key:
                    raise IdentityGovernanceError(
                        "IdentityGovernanceRequest recent_governance_trace_history entries must not contain empty keys"
                    )
            history.append(proxy)
        object.__setattr__(self, "recent_governance_trace_history", tuple(history))
        if self.pending_governed_action is not None:
            pending = MappingProxyType(dict(self.pending_governed_action))
            for key in pending:
                if not key:
                    raise IdentityGovernanceError(
                        "IdentityGovernanceRequest pending_governed_action must not contain empty keys"
                    )
            object.__setattr__(self, "pending_governed_action", pending)


@dataclass(frozen=True)
class NormalizedSelfRevisionProposal:
    """Immutable normalized self-revision proposal consumed by the governance owner."""

    proposal_id: str
    origin_thought_id: str
    owner_path: str
    revision_type: str
    requested_change: Mapping[str, object]
    confidence: float
    scope: Literal["identity"]
    reason_trace: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare a non-empty proposal_id"
            )
        if not self.origin_thought_id:
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare a non-empty origin_thought_id"
            )
        if not self.owner_path:
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare a non-empty owner_path"
            )
        if not self.revision_type:
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare a non-empty revision_type"
            )
        if self.scope != "identity":
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal scope must use the fixed taxonomy"
            )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare non-empty reason_trace items"
            )
        _validate_unit_interval(
            "NormalizedSelfRevisionProposal.confidence",
            self.confidence,
        )
        requested_change = MappingProxyType(dict(self.requested_change))
        if not requested_change:
            raise IdentityGovernanceError(
                "NormalizedSelfRevisionProposal must declare non-empty requested_change"
            )
        object.__setattr__(self, "requested_change", requested_change)


@dataclass(frozen=True)
class GovernancePressureState:
    """Immutable governance-pressure state owned by identity governance."""

    active: bool
    pressure_score: float
    pressure_level: GovernancePressureLevel
    review_hint: str
    recent_trace_count: int
    source_consistency_ratio: float
    recent_trigger_sources: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_unit_interval(
            "GovernancePressureState.pressure_score",
            self.pressure_score,
        )
        _validate_unit_interval(
            "GovernancePressureState.source_consistency_ratio",
            self.source_consistency_ratio,
        )
        if self.pressure_level not in _PRESSURE_LEVELS:
            raise IdentityGovernanceError(
                "GovernancePressureState pressure_level must use the fixed taxonomy"
            )
        if self.recent_trace_count < 0:
            raise IdentityGovernanceError(
                "GovernancePressureState recent_trace_count must be >= 0"
            )
        if any(not item for item in self.recent_trigger_sources):
            raise IdentityGovernanceError(
                "GovernancePressureState recent_trigger_sources must not contain empty values"
            )


@dataclass(frozen=True)
class RevisionDecision:
    """Immutable governance decision for one self-revision proposal."""

    revision_id: str
    proposal_id: str
    origin_thought_id: str
    status: RevisionStatus
    requested_change: Mapping[str, object]
    applied_change: Mapping[str, object]
    rejection_reason: GovernanceRejectionReason | None
    reason_trace: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.revision_id:
            raise IdentityGovernanceError("RevisionDecision must declare a non-empty revision_id")
        if not self.proposal_id:
            raise IdentityGovernanceError("RevisionDecision must declare a non-empty proposal_id")
        if not self.origin_thought_id:
            raise IdentityGovernanceError(
                "RevisionDecision must declare a non-empty origin_thought_id"
            )
        if self.status not in _REVISION_STATUSES:
            raise IdentityGovernanceError(
                "RevisionDecision status must use the fixed taxonomy"
            )
        if self.rejection_reason is not None and self.rejection_reason not in _GOVERNANCE_REJECTION_REASONS:
            raise IdentityGovernanceError(
                "RevisionDecision rejection_reason must use the fixed taxonomy"
            )
        if self.status in {"accepted", "accepted_with_monitoring"} and self.rejection_reason is not None:
            raise IdentityGovernanceError(
                "Accepted RevisionDecision must not publish rejection_reason"
            )
        if self.status in {"rejected", "invalid_proposal"} and self.rejection_reason is None:
            raise IdentityGovernanceError(
                "Rejected and invalid RevisionDecision must publish rejection_reason"
            )
        requested_change = MappingProxyType(dict(self.requested_change))
        applied_change = MappingProxyType(dict(self.applied_change))
        if not requested_change:
            raise IdentityGovernanceError(
                "RevisionDecision must declare non-empty requested_change"
            )
        if self.status in {"accepted", "accepted_with_monitoring"} and not applied_change:
            raise IdentityGovernanceError(
                "Accepted RevisionDecision must publish non-empty applied_change"
            )
        if self.status in {"rejected", "invalid_proposal"} and applied_change:
            raise IdentityGovernanceError(
                "Rejected and invalid RevisionDecision must not publish applied_change"
            )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise IdentityGovernanceError(
                "RevisionDecision must declare non-empty reason_trace items"
            )
        object.__setattr__(self, "requested_change", requested_change)
        object.__setattr__(self, "applied_change", applied_change)


@dataclass(frozen=True)
class AppliedIdentityState:
    """Immutable post-acceptance identity-state publication."""

    revision_id: str
    current_revision: str
    identity_state_snapshot: Mapping[str, object]
    changed_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.revision_id:
            raise IdentityGovernanceError(
                "AppliedIdentityState must declare a non-empty revision_id"
            )
        if not self.current_revision:
            raise IdentityGovernanceError(
                "AppliedIdentityState must declare a non-empty current_revision"
            )
        if not self.changed_fields or any(not item for item in self.changed_fields):
            raise IdentityGovernanceError(
                "AppliedIdentityState must declare non-empty changed_fields"
            )
        object.__setattr__(
            self,
            "identity_state_snapshot",
            MappingProxyType(dict(self.identity_state_snapshot)),
        )


@dataclass(frozen=True)
class IdentityGovernanceResult:
    """Immutable published governance result for one evaluated proposal path."""

    result_id: str
    source_request_id: str
    pressure_state: GovernancePressureState
    revision_decision: RevisionDecision
    applied_identity_state: AppliedIdentityState | None
    tick_id: int | None
    governed_action_authorization: GovernedActionAuthorization | None = None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceResult must declare a non-empty result_id"
            )
        if not self.source_request_id:
            raise IdentityGovernanceError(
                "IdentityGovernanceResult must declare a non-empty source_request_id"
            )
        accepted = self.revision_decision.status in {"accepted", "accepted_with_monitoring"}
        if accepted and self.applied_identity_state is None:
            raise IdentityGovernanceError(
                "Accepted IdentityGovernanceResult must publish applied_identity_state"
            )
        if not accepted and self.applied_identity_state is not None:
            raise IdentityGovernanceError(
                "Rejected and invalid IdentityGovernanceResult must not publish applied_identity_state"
            )


@dataclass(frozen=True)
class GovernanceCarryState:
    """Immutable cross-tick carry state for identity governance.

    Owner: identity governance and self-revision integration.

    Encapsulates the evolved identity-state snapshot and a bounded governance
    trace history so subsequent ticks can build on prior governance activity.
    Constructed by the runtime stage after each tick's evaluation; consumed by
    the composition bridge (owner-neutral injection) and the governance owner.

    Failure semantics:
        Construction raises ``IdentityGovernanceError`` on negative counts or
        trace-history entries with empty keys.
    """

    identity_state_snapshot: Mapping[str, object]
    recent_governance_trace_history: tuple[Mapping[str, object], ...]
    accepted_revision_count: int
    rejected_revision_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.accepted_revision_count, int) or self.accepted_revision_count < 0:
            raise IdentityGovernanceError(
                "GovernanceCarryState accepted_revision_count must be a non-negative integer"
            )
        if not isinstance(self.rejected_revision_count, int) or self.rejected_revision_count < 0:
            raise IdentityGovernanceError(
                "GovernanceCarryState rejected_revision_count must be a non-negative integer"
            )
        history: list[Mapping[str, object]] = []
        for entry in self.recent_governance_trace_history:
            proxy = MappingProxyType(dict(entry))
            for key in proxy:
                if not key:
                    raise IdentityGovernanceError(
                        "GovernanceCarryState trace-history entries must not contain empty keys"
                    )
            history.append(proxy)
        object.__setattr__(self, "recent_governance_trace_history", tuple(history))
        object.__setattr__(
            self,
            "identity_state_snapshot",
            MappingProxyType(dict(self.identity_state_snapshot)),
        )


@dataclass(frozen=True)
class EvaluateIdentityGovernanceOp:
    """Runtime-visible request op for one governance evaluation cycle."""

    op_name: str
    owner: str
    request_id: str
    thought_cycle_result_id: str
    proposal_present: bool


@dataclass(frozen=True)
class PublishGovernancePressureOp:
    """Runtime-visible publication op for one governance-pressure state."""

    op_name: str
    owner: str
    request_id: str
    pressure_level: GovernancePressureLevel
    pressure_score: float
    active: bool


@dataclass(frozen=True)
class PublishRevisionDecisionOp:
    """Runtime-visible publication op for one governance decision."""

    op_name: str
    owner: str
    revision_id: str
    status: RevisionStatus
    origin_thought_id: str


@dataclass(frozen=True)
class PublishAppliedIdentityStateOp:
    """Runtime-visible publication op for one accepted identity-state mutation."""

    op_name: str
    owner: str
    revision_id: str
    current_revision: str
    changed_fields: tuple[str, ...]


@runtime_checkable
class IdentityGovernanceAPI(Protocol):
    """Owner: identity governance API."""

    def evaluate_self_revision(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
    ) -> IdentityGovernanceResult:
        """Return one formal governance result from a thought-origin self-revision proposal."""

    def evaluate_self_revision_and_authorize(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
    ) -> IdentityGovernanceResult:
        """Owner: identity governance (requirement 86).

        Return the self-revision governance result, additionally attaching the governed-action
        authorization verdict when the request carries a pending governed action (else the
        byte-for-byte self-revision result).
        """

    def build_evaluate_op(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: IdentityGovernanceRequest,
    ) -> EvaluateIdentityGovernanceOp:
        """Return one request op describing governance evaluation."""

    def build_publish_pressure_op(
        self,
        request: IdentityGovernanceRequest,
        pressure_state: GovernancePressureState,
    ) -> PublishGovernancePressureOp:
        """Return one publication op describing governance-pressure publication."""

    def build_publish_revision_decision_op(
        self,
        decision: RevisionDecision,
    ) -> PublishRevisionDecisionOp:
        """Return one publication op describing revision-decision publication."""

    def build_publish_applied_identity_state_op(
        self,
        applied_identity_state: AppliedIdentityState,
    ) -> PublishAppliedIdentityStateOp:
        """Return one publication op describing accepted identity-state publication."""
