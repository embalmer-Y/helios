"""First-version path for outward-expression draft assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import (
    OutwardExpressionAPI,
    OutwardExpressionConfig,
    OutwardExpressionDraft,
    OutwardExpressionError,
    OutwardExpressionRequest,
    PrepareOutwardExpressionOp,
    PublishOutwardExpressionDraftOp,
)


def _require_text(name: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise OutwardExpressionError(f"{name} must resolve to non-empty text")
    return text


@runtime_checkable
class OutwardExpressionPath(Protocol):
    """Owner-private path that turns an outward-expression request into a bounded draft."""

    def compose_draft(
        self,
        request: OutwardExpressionRequest,
        config: OutwardExpressionConfig,
    ) -> OutwardExpressionDraft:
        """Return one deterministic outward-expression draft from a validated request."""


@dataclass(frozen=True)
class FirstVersionOutwardExpressionPath:
    """First shipped outward-expression path preserving proposal-only execution boundaries."""

    def compose_draft(
        self,
        request: OutwardExpressionRequest,
        config: OutwardExpressionConfig,
    ) -> OutwardExpressionDraft:
        if config.outward_expression_bootstrap_id != "outward-expression-bootstrap:v1":
            raise OutwardExpressionError(
                "FirstVersionOutwardExpressionPath requires the confirmed outward-expression bootstrap id"
            )
        delivery_guidance = _require_text(
            "delivery_guidance",
            (
                f"Allowed channels: {', '.join(request.available_channels)}. "
                f"Allowed ops: {', '.join(request.available_ops)}. "
                f"Final authorities remain: {', '.join(request.final_authorities)}. "
                f"Never claim or simulate: {', '.join(request.forbidden_capabilities)}."
            ),
        )
        return OutwardExpressionDraft(
            draft_id=f"outward-expression-draft:{request.request_id}",
            source_request_id=request.request_id,
            source_prompt_view_id=request.source_prompt_view_id,
            source_prompt_contract_id=request.source_prompt_contract_id,
            rendered_prompt=request.rendered_prompt,
            delivery_channels=request.available_channels,
            delivery_ops=request.available_ops,
            delivery_guidance=delivery_guidance,
            forbidden_capabilities=request.forbidden_capabilities,
            final_authorities=request.final_authorities,
            anti_theatrical_constraints=request.anti_theatrical_constraints,
        )


@dataclass(frozen=True)
class OutwardExpressionEngine(OutwardExpressionAPI):
    """Public outward-expression owner that publishes bounded draft artifacts."""

    config: OutwardExpressionConfig
    outward_expression_path: OutwardExpressionPath

    def build_prepare_op(
        self,
        request: OutwardExpressionRequest,
    ) -> PrepareOutwardExpressionOp:
        return PrepareOutwardExpressionOp(
            op_name="prepare_outward_expression_draft",
            owner="outward_expression_owner",
            request_id=request.request_id,
            source_prompt_view_id=request.source_prompt_view_id,
            channel_count=len(request.available_channels),
            op_count=len(request.available_ops),
        )

    def prepare_draft(
        self,
        request: OutwardExpressionRequest,
    ) -> OutwardExpressionDraft:
        return self.outward_expression_path.compose_draft(request, self.config)

    def build_publish_draft_op(
        self,
        draft: OutwardExpressionDraft,
    ) -> PublishOutwardExpressionDraftOp:
        return PublishOutwardExpressionDraftOp(
            op_name="publish_outward_expression_draft",
            owner="outward_expression_owner",
            draft_id=draft.draft_id,
            source_request_id=draft.source_request_id,
            channel_count=len(draft.delivery_channels),
            op_count=len(draft.delivery_ops),
        )