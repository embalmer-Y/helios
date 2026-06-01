"""Owner: embodied subjective prompt and action autonomy.

Owns:
- embodied prompt request, layer, action-boundary, and contract contracts
- minimal outward-expression prompt-consumer view contracts
- prompt-contract build and publication ops
- prompt-contract API for thought and outward-expression consumers

Does not own:
- internal thought execution
- planner or channel authority
- identity-governance judgment
- user-visible behavior decisions
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.outward_expression import BuildOutwardExpressionRequestOp, OutwardExpressionRequest


class PromptContractError(RuntimeError):
    """Hard-stop error raised when prompt-contract owner invariants fail."""


EmbodiedPromptConsumerKind = Literal["thought", "outward_expression"]
PromptContractLearnedParameterCategory = Literal[
    "layering_policy",
    "anti_theatrical_policy",
    "action_boundary_policy",
]

_CONSUMER_KINDS = {"thought", "outward_expression"}


@dataclass(frozen=True)
class EmbodiedPromptConfig:
    """Expose the confirmed initialization and learned-policy surface for prompt assembly."""

    max_layer_count: int
    prompt_bootstrap_id: str
    mandatory_learned_parameters: tuple[PromptContractLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise PromptContractError(
                "Prompt-contract config must declare the confirmed mandatory learned-parameter categories"
            )
        if self.max_layer_count <= 0:
            raise PromptContractError("EmbodiedPromptConfig.max_layer_count must be > 0")
        if not self.prompt_bootstrap_id:
            raise PromptContractError("EmbodiedPromptConfig must declare a non-empty prompt_bootstrap_id")


@dataclass(frozen=True)
class EmbodiedPromptRequest:
    """Explicit normalized prompt-assembly input for one consumer in one runtime cycle."""

    request_id: str
    consumer_kind: EmbodiedPromptConsumerKind
    source_conscious_state_id: str
    source_gate_result_id: str
    source_retrieval_bundle_id: str
    stimulus_summary: Mapping[str, object]
    state_summary: Mapping[str, object]
    retrieval_summary: Mapping[str, object]
    capability_summary: Mapping[str, object]
    identity_boundary_summary: Mapping[str, object]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise PromptContractError("EmbodiedPromptRequest must declare a non-empty request_id")
        if self.consumer_kind not in _CONSUMER_KINDS:
            raise PromptContractError("EmbodiedPromptRequest consumer_kind must use the fixed taxonomy")
        for attr_name in (
            "source_conscious_state_id",
            "source_gate_result_id",
            "source_retrieval_bundle_id",
        ):
            if not getattr(self, attr_name):
                raise PromptContractError(
                    f"EmbodiedPromptRequest must declare a non-empty {attr_name}"
                )
        for attr_name in (
            "stimulus_summary",
            "state_summary",
            "retrieval_summary",
            "capability_summary",
            "identity_boundary_summary",
        ):
            mapping = MappingProxyType(dict(getattr(self, attr_name)))
            if not mapping:
                raise PromptContractError(
                    f"EmbodiedPromptRequest must declare non-empty {attr_name}"
                )
            for key in mapping:
                if not key:
                    raise PromptContractError(
                        f"EmbodiedPromptRequest {attr_name} must not contain empty keys"
                    )
            object.__setattr__(self, attr_name, mapping)


@dataclass(frozen=True)
class PromptContractLayer:
    """Immutable bounded prompt layer emitted by the prompt owner."""

    layer_name: str
    content: str
    required: bool

    def __post_init__(self) -> None:
        if not self.layer_name:
            raise PromptContractError("PromptContractLayer must declare a non-empty layer_name")
        if not self.content:
            raise PromptContractError("PromptContractLayer must declare non-empty content")


@dataclass(frozen=True)
class PromptActionBoundary:
    """Immutable action-boundary contract exposed to the prompt consumer."""

    supports_internal_action: bool
    supports_external_action_proposal: bool
    supports_self_revision_proposal: bool
    forbidden_capabilities: tuple[str, ...]
    final_authorities: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not capability for capability in self.forbidden_capabilities):
            raise PromptContractError(
                "PromptActionBoundary forbidden_capabilities must not contain empty values"
            )
        if not self.final_authorities or any(not authority for authority in self.final_authorities):
            raise PromptContractError(
                "PromptActionBoundary must declare non-empty final_authorities"
            )


@dataclass(frozen=True)
class EmbodiedPromptContract:
    """Immutable embodied prompt contract assembled for one consumer in one cycle."""

    contract_id: str
    consumer_kind: EmbodiedPromptConsumerKind
    source_request_id: str
    layers: tuple[PromptContractLayer, ...]
    action_boundary: PromptActionBoundary
    capability_snapshot: Mapping[str, object]
    anti_theatrical_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.contract_id:
            raise PromptContractError("EmbodiedPromptContract must declare a non-empty contract_id")
        if self.consumer_kind not in _CONSUMER_KINDS:
            raise PromptContractError("EmbodiedPromptContract consumer_kind must use the fixed taxonomy")
        if not self.source_request_id:
            raise PromptContractError("EmbodiedPromptContract must declare a non-empty source_request_id")
        if not self.layers:
            raise PromptContractError("EmbodiedPromptContract must publish at least one layer")
        capability_snapshot = MappingProxyType(dict(self.capability_snapshot))
        if not capability_snapshot:
            raise PromptContractError("EmbodiedPromptContract must declare non-empty capability_snapshot")
        for key in capability_snapshot:
            if not key:
                raise PromptContractError(
                    "EmbodiedPromptContract capability_snapshot must not contain empty keys"
                )
        if any(not constraint for constraint in self.anti_theatrical_constraints):
            raise PromptContractError(
                "EmbodiedPromptContract anti_theatrical_constraints must not contain empty values"
            )
        object.__setattr__(self, "capability_snapshot", capability_snapshot)


@dataclass(frozen=True)
class OutwardExpressionPromptView:
    """Immutable minimal outward-expression consumer view derived from a shared prompt contract."""

    view_id: str
    source_contract_id: str
    rendered_prompt: str
    available_channels: tuple[str, ...]
    available_ops: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    final_authorities: tuple[str, ...]
    anti_theatrical_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.view_id:
            raise PromptContractError("OutwardExpressionPromptView must declare a non-empty view_id")
        if not self.source_contract_id:
            raise PromptContractError(
                "OutwardExpressionPromptView must declare a non-empty source_contract_id"
            )
        if not self.rendered_prompt:
            raise PromptContractError(
                "OutwardExpressionPromptView must declare non-empty rendered_prompt"
            )
        for attr_name in (
            "available_channels",
            "available_ops",
            "forbidden_capabilities",
            "final_authorities",
            "anti_theatrical_constraints",
        ):
            values = getattr(self, attr_name)
            if not values or any(not value for value in values):
                raise PromptContractError(
                    f"OutwardExpressionPromptView must declare non-empty {attr_name}"
                )


@dataclass(frozen=True)
class BuildEmbodiedPromptOp:
    """Runtime-visible request op for one embodied prompt build cycle."""

    op_name: str
    owner: str
    request_id: str
    consumer_kind: EmbodiedPromptConsumerKind


@dataclass(frozen=True)
class PublishEmbodiedPromptContractOp:
    """Runtime-visible publication op for one embodied prompt contract."""

    op_name: str
    owner: str
    contract_id: str
    consumer_kind: EmbodiedPromptConsumerKind
    layer_count: int


@dataclass(frozen=True)
class PublishOutwardExpressionPromptViewOp:
    """Runtime-visible publication op for one minimal outward-expression prompt-consumer view."""

    op_name: str
    owner: str
    view_id: str
    source_contract_id: str
    channel_count: int


@runtime_checkable
class EmbodiedPromptAPI(Protocol):
    """Owner: embodied subjective prompt and action autonomy API."""

    def build_prompt_contract(self, request: EmbodiedPromptRequest) -> EmbodiedPromptContract:
        """Return one embodied prompt contract for one consumer-facing request."""

    def build_request_op(self, request: EmbodiedPromptRequest) -> BuildEmbodiedPromptOp:
        """Return one request op describing prompt-contract assembly."""

    def build_publish_op(self, contract: EmbodiedPromptContract) -> PublishEmbodiedPromptContractOp:
        """Return one publication op describing prompt-contract publication."""

    def build_outward_expression_view(
        self,
        contract: EmbodiedPromptContract,
    ) -> OutwardExpressionPromptView:
        """Return one minimal outward-expression consumer view derived from a shared prompt contract."""

    def build_publish_outward_expression_view_op(
        self,
        view: OutwardExpressionPromptView,
    ) -> PublishOutwardExpressionPromptViewOp:
        """Return one publication op describing outward-expression view publication."""

    def build_outward_expression_request(
        self,
        view: OutwardExpressionPromptView,
    ) -> OutwardExpressionRequest:
        """Return one future-owner outward-expression request derived from a prompt view."""

    def build_outward_expression_request_op(
        self,
        request: OutwardExpressionRequest,
    ) -> BuildOutwardExpressionRequestOp:
        """Return one request-build op describing outward-expression handoff publication."""