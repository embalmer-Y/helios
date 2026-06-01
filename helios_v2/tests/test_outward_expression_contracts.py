from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.outward_expression import (
    OutwardExpressionConfig,
    OutwardExpressionDraft,
    OutwardExpressionError,
    OutwardExpressionRequest,
)


def test_outward_expression_config_requires_confirmed_categories() -> None:
    with pytest.raises(OutwardExpressionError, match="mandatory learned-parameter"):
        OutwardExpressionConfig(
            outward_expression_bootstrap_id="outward-expression-bootstrap:v1",
            mandatory_learned_parameters=("delivery_guidance_policy",),
        )


def test_outward_expression_request_is_immutable() -> None:
    request = OutwardExpressionRequest(
        request_id="outward-expression-request:001",
        source_prompt_view_id="outward-expression-view:001",
        source_prompt_contract_id="embodied-prompt-contract:001",
        rendered_prompt="[present_field] current field",
        available_channels=("cli",),
        available_ops=("reply_message",),
        forbidden_capabilities=("direct_execution",),
        final_authorities=("planner", "channel", "identity_governance"),
        anti_theatrical_constraints=("avoid empty self-consciousness performance",),
    )

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"


def test_outward_expression_request_requires_non_empty_fields() -> None:
    with pytest.raises(OutwardExpressionError, match="available_channels"):
        OutwardExpressionRequest(
            request_id="outward-expression-request:001",
            source_prompt_view_id="outward-expression-view:001",
            source_prompt_contract_id="embodied-prompt-contract:001",
            rendered_prompt="[present_field] current field",
            available_channels=(),
            available_ops=("reply_message",),
            forbidden_capabilities=("direct_execution",),
            final_authorities=("planner",),
            anti_theatrical_constraints=("avoid empty self-consciousness performance",),
        )


def test_outward_expression_draft_is_immutable() -> None:
    draft = OutwardExpressionDraft(
        draft_id="outward-expression-draft:001",
        source_request_id="outward-expression-request:001",
        source_prompt_view_id="outward-expression-view:001",
        source_prompt_contract_id="embodied-prompt-contract:001",
        rendered_prompt="[present_field] current field",
        delivery_channels=("cli",),
        delivery_ops=("reply_message",),
        delivery_guidance="Allowed channels: cli. Allowed ops: reply_message.",
        forbidden_capabilities=("direct_execution",),
        final_authorities=("planner", "channel", "identity_governance"),
        anti_theatrical_constraints=("avoid empty self-consciousness performance",),
    )

    with pytest.raises(FrozenInstanceError):
        draft.delivery_guidance = "changed"