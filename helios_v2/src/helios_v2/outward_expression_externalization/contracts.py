"""Owner: outward-expression execution/externalization draft preparation.

Owns:
- outward-expression externalization request contract
- outward-expression externalization draft contract and publication ops
- outward-expression externalization owner API

Does not own:
- prompt-contract assembly
- outward-expression prompt/draft assembly
- planner acceptance
- channel transport or execution dispatch
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


class OutwardExpressionExternalizationError(RuntimeError):
    """Hard-stop error raised when outward-expression externalization invariants fail."""


OutwardExpressionExternalizationLearnedParameterCategory = Literal[
    "envelope_rendering_policy",
    "delivery_selection_policy",
    "execution_boundary_policy",
]

_LEARNED_PARAMETER_CATEGORIES = {
    "envelope_rendering_policy",
    "delivery_selection_policy",
    "execution_boundary_policy",
}


@dataclass(frozen=True)
class OutwardExpressionExternalizationConfig:
    """Expose the confirmed initialization and learned-policy surface for externalization draft ownership."""

    externalization_bootstrap_id: str
    mandatory_learned_parameters: tuple[
        OutwardExpressionExternalizationLearnedParameterCategory, ...
    ]

    def __post_init__(self) -> None:
        if set(self.mandatory_learned_parameters) != _LEARNED_PARAMETER_CATEGORIES:
            raise OutwardExpressionExternalizationError(
                "OutwardExpressionExternalizationConfig must declare the confirmed mandatory learned-parameter categories"
            )
        if not self.externalization_bootstrap_id:
            raise OutwardExpressionExternalizationError(
                "OutwardExpressionExternalizationConfig must declare a non-empty externalization_bootstrap_id"
            )


@dataclass(frozen=True)
class OutwardExpressionExternalizationRequest:
    """Immutable owner input contract for one outward-expression externalization cycle."""

    request_id: str
    source_outward_expression_draft_id: str
    source_prompt_contract_id: str
    rendered_prompt: str
    delivery_channels: tuple[str, ...]
    delivery_ops: tuple[str, ...]
    delivery_guidance: str
    forbidden_capabilities: tuple[str, ...]
    final_authorities: tuple[str, ...]
    anti_theatrical_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        for attr_name in (
            "request_id",
            "source_outward_expression_draft_id",
            "source_prompt_contract_id",
            "rendered_prompt",
            "delivery_guidance",
        ):
            if not getattr(self, attr_name):
                raise OutwardExpressionExternalizationError(
                    f"OutwardExpressionExternalizationRequest must declare a non-empty {attr_name}"
                )
        for attr_name in (
            "delivery_channels",
            "delivery_ops",
            "forbidden_capabilities",
            "final_authorities",
            "anti_theatrical_constraints",
        ):
            values = getattr(self, attr_name)
            if not values or any(not value for value in values):
                raise OutwardExpressionExternalizationError(
                    f"OutwardExpressionExternalizationRequest must declare non-empty {attr_name}"
                )


@dataclass(frozen=True)
class RequestOutwardExpressionExternalizationOp:
    """Runtime-visible op describing externalization-request publication."""

    op_name: str
    owner: str
    request_id: str
    source_outward_expression_draft_id: str
    channel_count: int
    op_count: int


@dataclass(frozen=True)
class OutwardExpressionExternalizationDraft:
    """Immutable externalization-side draft prepared for a future planner/channel executor."""

    draft_id: str
    source_request_id: str
    source_outward_expression_draft_id: str
    source_prompt_contract_id: str
    externalization_prompt: str
    candidate_channels: tuple[str, ...]
    candidate_ops: tuple[str, ...]
    execution_boundary_summary: str
    forbidden_capabilities: tuple[str, ...]
    final_authorities: tuple[str, ...]
    anti_theatrical_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        for attr_name in (
            "draft_id",
            "source_request_id",
            "source_outward_expression_draft_id",
            "source_prompt_contract_id",
            "externalization_prompt",
            "execution_boundary_summary",
        ):
            if not getattr(self, attr_name):
                raise OutwardExpressionExternalizationError(
                    f"OutwardExpressionExternalizationDraft must declare a non-empty {attr_name}"
                )
        for attr_name in (
            "candidate_channels",
            "candidate_ops",
            "forbidden_capabilities",
            "final_authorities",
            "anti_theatrical_constraints",
        ):
            values = getattr(self, attr_name)
            if not values or any(not value for value in values):
                raise OutwardExpressionExternalizationError(
                    f"OutwardExpressionExternalizationDraft must declare non-empty {attr_name}"
                )


@dataclass(frozen=True)
class PublishOutwardExpressionExternalizationDraftOp:
    """Runtime-visible publication op for externalization-side draft publication."""

    op_name: str
    owner: str
    draft_id: str
    source_request_id: str
    channel_count: int
    op_count: int


@runtime_checkable
class OutwardExpressionExternalizationAPI(Protocol):
    """Public API for outward-expression execution/externalization draft ownership."""

    def build_request_op(
        self,
        request: OutwardExpressionExternalizationRequest,
    ) -> RequestOutwardExpressionExternalizationOp:
        """Return one runtime-visible op describing externalization-request publication."""

        ...

    def prepare_externalization_draft(
        self,
        request: OutwardExpressionExternalizationRequest,
    ) -> OutwardExpressionExternalizationDraft:
        """Return one bounded externalization draft from a validated request."""

        ...

    def build_publish_draft_op(
        self,
        draft: OutwardExpressionExternalizationDraft,
    ) -> PublishOutwardExpressionExternalizationDraftOp:
        """Return one runtime-visible op describing externalization-draft publication."""

        ...