"""First-version path for outward-expression execution/externalization draft preparation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import (
    OutwardExpressionExternalizationAPI,
    OutwardExpressionExternalizationConfig,
    OutwardExpressionExternalizationDraft,
    OutwardExpressionExternalizationError,
    OutwardExpressionExternalizationRequest,
    PublishOutwardExpressionExternalizationDraftOp,
    RequestOutwardExpressionExternalizationOp,
)


def _require_text(name: str, value: str) -> str:
    text = value.strip()
    if not text:
        raise OutwardExpressionExternalizationError(f"{name} must resolve to non-empty text")
    return text


@runtime_checkable
class OutwardExpressionExternalizationPath(Protocol):
    """Owner-private path that turns an outward-expression draft request into an externalization-side draft."""

    def compose_externalization_draft(
        self,
        request: OutwardExpressionExternalizationRequest,
        config: OutwardExpressionExternalizationConfig,
    ) -> OutwardExpressionExternalizationDraft:
        """Return one deterministic externalization draft from a validated request."""


@dataclass(frozen=True)
class FirstVersionOutwardExpressionExternalizationPath:
    """First shipped externalization path preserving draft-only execution boundaries."""

    def compose_externalization_draft(
        self,
        request: OutwardExpressionExternalizationRequest,
        config: OutwardExpressionExternalizationConfig,
    ) -> OutwardExpressionExternalizationDraft:
        if config.externalization_bootstrap_id != "outward-expression-externalization-bootstrap:v1":
            raise OutwardExpressionExternalizationError(
                "FirstVersionOutwardExpressionExternalizationPath requires the confirmed externalization bootstrap id"
            )
        execution_boundary_summary = _require_text(
            "execution_boundary_summary",
            (
                f"Candidate channels remain: {', '.join(request.delivery_channels)}. "
                f"Candidate ops remain: {', '.join(request.delivery_ops)}. "
                f"Final authorities remain: {', '.join(request.final_authorities)}. "
                f"Never execute or simulate: {', '.join(request.forbidden_capabilities)}."
            ),
        )
        externalization_prompt = _require_text(
            "externalization_prompt",
            (
                f"{request.rendered_prompt}\n\n"
                f"[delivery_guidance]\n{request.delivery_guidance}\n\n"
                f"[execution_boundary]\n{execution_boundary_summary}"
            ),
        )
        return OutwardExpressionExternalizationDraft(
            draft_id=f"outward-expression-externalization-draft:{request.request_id}",
            source_request_id=request.request_id,
            source_outward_expression_draft_id=request.source_outward_expression_draft_id,
            source_prompt_contract_id=request.source_prompt_contract_id,
            externalization_prompt=externalization_prompt,
            candidate_channels=request.delivery_channels,
            candidate_ops=request.delivery_ops,
            execution_boundary_summary=execution_boundary_summary,
            forbidden_capabilities=request.forbidden_capabilities,
            final_authorities=request.final_authorities,
            anti_theatrical_constraints=request.anti_theatrical_constraints,
        )


@dataclass(frozen=True)
class OutwardExpressionExternalizationEngine(OutwardExpressionExternalizationAPI):
    """Public owner that prepares externalization-side drafts from outward-expression drafts."""

    config: OutwardExpressionExternalizationConfig
    externalization_path: OutwardExpressionExternalizationPath

    def build_request_op(
        self,
        request: OutwardExpressionExternalizationRequest,
    ) -> RequestOutwardExpressionExternalizationOp:
        return RequestOutwardExpressionExternalizationOp(
            op_name="request_outward_expression_externalization",
            owner="outward_expression_execution_externalization_owner",
            request_id=request.request_id,
            source_outward_expression_draft_id=request.source_outward_expression_draft_id,
            channel_count=len(request.delivery_channels),
            op_count=len(request.delivery_ops),
        )

    def prepare_externalization_draft(
        self,
        request: OutwardExpressionExternalizationRequest,
    ) -> OutwardExpressionExternalizationDraft:
        return self.externalization_path.compose_externalization_draft(request, self.config)

    def build_publish_draft_op(
        self,
        draft: OutwardExpressionExternalizationDraft,
    ) -> PublishOutwardExpressionExternalizationDraftOp:
        return PublishOutwardExpressionExternalizationDraftOp(
            op_name="publish_outward_expression_externalization_draft",
            owner="outward_expression_execution_externalization_owner",
            draft_id=draft.draft_id,
            source_request_id=draft.source_request_id,
            channel_count=len(draft.candidate_channels),
            op_count=len(draft.candidate_ops),
        )