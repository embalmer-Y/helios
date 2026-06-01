"""Owner: action proposal externalization contract.

Owns:
- thought-origin externalization request and normalized contract surfaces
- bridge-level rejection and equivalent-evidence contracts
- action externalization API and publication ops

Does not own:
- internal thought execution
- planner acceptance
- executor dispatch
- channel transport
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.internal_thought import ThoughtCycleResult


class ActionExternalizationError(RuntimeError):
    """Hard-stop error raised when action-externalization owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ActionExternalizationError(f"{name} must be within [0.0, 1.0]")


ExternalizationStatus = Literal[
    "normalized",
    "bridge_rejected",
    "equivalent_evidence_only",
    "no_externalization",
]
BridgeRejectionReason = Literal[
    "schema_invalid",
    "missing_candidate_channels",
    "missing_target_user_id",
    "missing_outbound_text",
    "scope_conflict",
]
ActionExternalizationLearnedParameterCategory = Literal[
    "normalization_policy",
    "bridge_evidence_policy",
    "bridge_rejection_policy",
]

_EXTERNALIZATION_STATUSES = {
    "normalized",
    "bridge_rejected",
    "equivalent_evidence_only",
    "no_externalization",
}
_BRIDGE_REJECTION_REASONS = {
    "schema_invalid",
    "missing_candidate_channels",
    "missing_target_user_id",
    "missing_outbound_text",
    "scope_conflict",
}
_PROPOSAL_SCOPES = {"internal", "external"}


@dataclass(frozen=True)
class ActionExternalizationConfig:
    """Expose the confirmed initialization and learned-policy surface for action externalization."""

    legal_min_outbound_intensity: float
    legal_max_outbound_intensity: float
    externalization_bootstrap_id: str
    mandatory_learned_parameters: tuple[ActionExternalizationLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "normalization_policy",
            "bridge_evidence_policy",
            "bridge_rejection_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise ActionExternalizationError(
                "Action-externalization config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval(
            "ActionExternalizationConfig.legal_min_outbound_intensity",
            self.legal_min_outbound_intensity,
        )
        _validate_unit_interval(
            "ActionExternalizationConfig.legal_max_outbound_intensity",
            self.legal_max_outbound_intensity,
        )
        if self.legal_min_outbound_intensity > self.legal_max_outbound_intensity:
            raise ActionExternalizationError("Action-externalization intensity range is inverted")
        if not self.externalization_bootstrap_id:
            raise ActionExternalizationError(
                "ActionExternalizationConfig must declare a non-empty externalization_bootstrap_id"
            )


@dataclass(frozen=True)
class ThoughtExternalizationRequest:
    """Explicit bridge input contract for one thought-origin externalization cycle."""

    request_id: str
    source_thought_cycle_result_id: str
    proposal_carrier_present: bool
    target_binding_context: Mapping[str, object]
    channel_hint_context: Mapping[str, object]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ActionExternalizationError(
                "ThoughtExternalizationRequest must declare a non-empty request_id"
            )
        if not self.source_thought_cycle_result_id:
            raise ActionExternalizationError(
                "ThoughtExternalizationRequest must declare a non-empty source_thought_cycle_result_id"
            )
        target_context = MappingProxyType(dict(self.target_binding_context))
        channel_context = MappingProxyType(dict(self.channel_hint_context))
        for context_name, context_value in (
            ("target_binding_context", target_context),
            ("channel_hint_context", channel_context),
        ):
            for key in context_value:
                if not key:
                    raise ActionExternalizationError(
                        f"ThoughtExternalizationRequest {context_name} must not contain empty keys"
                    )
        object.__setattr__(self, "target_binding_context", target_context)
        object.__setattr__(self, "channel_hint_context", channel_context)


@dataclass(frozen=True)
class NormalizedThoughtActionProposal:
    """Immutable formal thought-origin externalization contract."""

    proposal_id: str
    origin_thought_id: str
    owner_path: str
    scope: Literal["internal", "external"]
    behavior_name: str
    preferred_op: str
    params: Mapping[str, object]
    channel_constraints: Mapping[str, object]
    outbound_intensity: float
    reason_trace: tuple[str, ...]
    governance_hints: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare a non-empty proposal_id"
            )
        if not self.origin_thought_id:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare a non-empty origin_thought_id"
            )
        if not self.owner_path:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare a non-empty owner_path"
            )
        if self.scope not in _PROPOSAL_SCOPES:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal scope must use the fixed taxonomy"
            )
        if not self.behavior_name:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare a non-empty behavior_name"
            )
        if not self.preferred_op:
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare a non-empty preferred_op"
            )
        params = MappingProxyType(dict(self.params))
        channel_constraints = MappingProxyType(dict(self.channel_constraints))
        governance_hints = MappingProxyType(dict(self.governance_hints))
        _validate_unit_interval(
            "NormalizedThoughtActionProposal.outbound_intensity",
            self.outbound_intensity,
        )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise ActionExternalizationError(
                "NormalizedThoughtActionProposal must declare non-empty reason_trace items"
            )
        if self.scope == "external":
            outbound_text = params.get("outbound_text")
            if not isinstance(outbound_text, str) or not outbound_text:
                raise ActionExternalizationError(
                    "NormalizedThoughtActionProposal external user-visible behaviors require final outbound_text"
                )
        object.__setattr__(self, "params", params)
        object.__setattr__(self, "channel_constraints", channel_constraints)
        object.__setattr__(self, "governance_hints", governance_hints)


@dataclass(frozen=True)
class EquivalentBridgeEvidence:
    """Immutable evidence contract for thought-origin externalization signal without explicit proposal success."""

    origin_thought_id: str
    bridge_evidence_kind: str
    reason_trace: tuple[str, ...]
    candidate_summary: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.origin_thought_id:
            raise ActionExternalizationError(
                "EquivalentBridgeEvidence must declare a non-empty origin_thought_id"
            )
        if not self.bridge_evidence_kind:
            raise ActionExternalizationError(
                "EquivalentBridgeEvidence must declare a non-empty bridge_evidence_kind"
            )
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise ActionExternalizationError(
                "EquivalentBridgeEvidence must declare non-empty reason_trace items"
            )
        summary = MappingProxyType(dict(self.candidate_summary))
        object.__setattr__(self, "candidate_summary", summary)


@dataclass(frozen=True)
class ThoughtExternalizationResult:
    """Immutable published bridge result for one externalization cycle."""

    result_id: str
    source_request_id: str
    status: ExternalizationStatus
    normalized_proposal: NormalizedThoughtActionProposal | None
    bridge_rejection_reason: BridgeRejectionReason | None
    equivalent_evidence: EquivalentBridgeEvidence | None
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise ActionExternalizationError(
                "ThoughtExternalizationResult must declare a non-empty result_id"
            )
        if not self.source_request_id:
            raise ActionExternalizationError(
                "ThoughtExternalizationResult must declare a non-empty source_request_id"
            )
        if self.status not in _EXTERNALIZATION_STATUSES:
            raise ActionExternalizationError(
                "ThoughtExternalizationResult status must use the fixed taxonomy"
            )
        if self.bridge_rejection_reason is not None and self.bridge_rejection_reason not in _BRIDGE_REJECTION_REASONS:
            raise ActionExternalizationError(
                "ThoughtExternalizationResult bridge_rejection_reason must use the fixed taxonomy"
            )
        if self.status == "normalized":
            if self.normalized_proposal is None:
                raise ActionExternalizationError(
                    "ThoughtExternalizationResult with status='normalized' must publish normalized_proposal"
                )
            if self.bridge_rejection_reason is not None or self.equivalent_evidence is not None:
                raise ActionExternalizationError(
                    "Normalized externalization results must not mix rejection or equivalent-evidence outcomes"
                )
        elif self.status == "bridge_rejected":
            if self.bridge_rejection_reason is None:
                raise ActionExternalizationError(
                    "ThoughtExternalizationResult with status='bridge_rejected' must publish bridge_rejection_reason"
                )
            if self.normalized_proposal is not None:
                raise ActionExternalizationError(
                    "Bridge-rejected results must not publish normalized_proposal"
                )
        elif self.status == "equivalent_evidence_only":
            if self.equivalent_evidence is None:
                raise ActionExternalizationError(
                    "ThoughtExternalizationResult with status='equivalent_evidence_only' must publish equivalent_evidence"
                )
            if self.normalized_proposal is not None or self.bridge_rejection_reason is not None:
                raise ActionExternalizationError(
                    "Equivalent-evidence-only results must not publish normalized or rejection outcomes"
                )
        else:
            if self.normalized_proposal is not None or self.bridge_rejection_reason is not None or self.equivalent_evidence is not None:
                raise ActionExternalizationError(
                    "No-externalization results must not publish normalized, rejection, or evidence payloads"
                )


@dataclass(frozen=True)
class RequestThoughtExternalizationOp:
    """Runtime-visible request op for one thought-origin bridge normalization cycle."""

    op_name: str
    owner: str
    request_id: str
    thought_cycle_result_id: str
    proposal_carrier_present: bool


@dataclass(frozen=True)
class PublishThoughtExternalizationOp:
    """Runtime-visible publication op for one normalized externalization contract."""

    op_name: str
    owner: str
    result_id: str
    proposal_id: str
    scope: str
    behavior_name: str


@dataclass(frozen=True)
class PublishThoughtExternalizationRejectionOp:
    """Runtime-visible publication op for one bridge-level rejection outcome."""

    op_name: str
    owner: str
    result_id: str
    bridge_rejection_reason: BridgeRejectionReason


@runtime_checkable
class ActionExternalizationAPI(Protocol):
    """Owner: action proposal externalization contract API."""

    def externalize_action_proposal(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
    ) -> ThoughtExternalizationResult:
        """Return one formal bridge result for the current thought cycle."""

    def build_request_op(
        self,
        thought_cycle_result: ThoughtCycleResult,
        request: ThoughtExternalizationRequest,
    ) -> RequestThoughtExternalizationOp:
        """Return one request op describing thought-origin externalization."""

    def build_publish_externalization_op(
        self,
        result: ThoughtExternalizationResult,
    ) -> PublishThoughtExternalizationOp:
        """Return one publication op describing normalized externalization publication."""

    def build_publish_rejection_op(
        self,
        result: ThoughtExternalizationResult,
    ) -> PublishThoughtExternalizationRejectionOp:
        """Return one publication op describing bridge rejection publication."""
