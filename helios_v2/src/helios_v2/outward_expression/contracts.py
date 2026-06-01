"""Owner: outward-expression pre-execution draft assembly.

Owns:
- outward-expression owner input contract
- outward-expression draft contract and publication ops
- outward-expression owner API

Does not own:
- prompt-contract assembly
- planner or channel authority
- expression execution or transport
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable


class OutwardExpressionError(RuntimeError):
    """Hard-stop error raised when outward-expression input-contract invariants fail."""


OutwardExpressionLearnedParameterCategory = Literal[
    "delivery_guidance_policy",
    "boundary_rendering_policy",
    "draft_publication_policy",
]

_LEARNED_PARAMETER_CATEGORIES = {
    "delivery_guidance_policy",
    "boundary_rendering_policy",
    "draft_publication_policy",
}


@dataclass(frozen=True)
class OutwardExpressionConfig:
    """Expose the confirmed initialization and learned-policy surface for outward expression."""

    outward_expression_bootstrap_id: str
    mandatory_learned_parameters: tuple[OutwardExpressionLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        if set(self.mandatory_learned_parameters) != _LEARNED_PARAMETER_CATEGORIES:
            raise OutwardExpressionError(
                "OutwardExpressionConfig must declare the confirmed mandatory learned-parameter categories"
            )
        if not self.outward_expression_bootstrap_id:
            raise OutwardExpressionError(
                "OutwardExpressionConfig must declare a non-empty outward_expression_bootstrap_id"
            )


@dataclass(frozen=True)
class OutwardExpressionRequest:
    """Immutable input contract for one outward-expression owner cycle."""

    request_id: str
    source_prompt_view_id: str
    source_prompt_contract_id: str
    rendered_prompt: str
    available_channels: tuple[str, ...]
    available_ops: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    final_authorities: tuple[str, ...]
    anti_theatrical_constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        for attr_name in (
            "request_id",
            "source_prompt_view_id",
            "source_prompt_contract_id",
            "rendered_prompt",
        ):
            if not getattr(self, attr_name):
                raise OutwardExpressionError(
                    f"OutwardExpressionRequest must declare a non-empty {attr_name}"
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
                raise OutwardExpressionError(
                    f"OutwardExpressionRequest must declare non-empty {attr_name}"
                )


@dataclass(frozen=True)
class BuildOutwardExpressionRequestOp:
    """Runtime-visible request-build op for outward-expression handoff publication."""

    op_name: str
    owner: str
    request_id: str
    source_prompt_view_id: str
    channel_count: int


@dataclass(frozen=True)
class PrepareOutwardExpressionOp:
    """Runtime-visible op describing outward-expression draft preparation."""

    op_name: str
    owner: str
    request_id: str
    source_prompt_view_id: str
    channel_count: int
    op_count: int


@dataclass(frozen=True)
class OutwardExpressionDraft:
    """Immutable bounded draft surface for a future execution owner."""

    draft_id: str
    source_request_id: str
    source_prompt_view_id: str
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
            "draft_id",
            "source_request_id",
            "source_prompt_view_id",
            "source_prompt_contract_id",
            "rendered_prompt",
            "delivery_guidance",
        ):
            if not getattr(self, attr_name):
                raise OutwardExpressionError(
                    f"OutwardExpressionDraft must declare a non-empty {attr_name}"
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
                raise OutwardExpressionError(
                    f"OutwardExpressionDraft must declare non-empty {attr_name}"
                )


@dataclass(frozen=True)
class PublishOutwardExpressionDraftOp:
    """Runtime-visible publication op for outward-expression draft publication."""

    op_name: str
    owner: str
    draft_id: str
    source_request_id: str
    channel_count: int
    op_count: int


@runtime_checkable
class OutwardExpressionAPI(Protocol):
    """Public API for the outward-expression owner."""

    def build_prepare_op(
        self,
        request: OutwardExpressionRequest,
    ) -> PrepareOutwardExpressionOp:
        """Return one runtime-visible op describing outward-expression draft preparation."""

    def prepare_draft(
        self,
        request: OutwardExpressionRequest,
    ) -> OutwardExpressionDraft:
        """Return one bounded outward-expression draft from a validated request."""

    def build_publish_draft_op(
        self,
        draft: OutwardExpressionDraft,
    ) -> PublishOutwardExpressionDraftOp:
        """Return one runtime-visible op describing outward-expression draft publication."""