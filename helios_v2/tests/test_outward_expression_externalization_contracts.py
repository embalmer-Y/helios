from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.outward_expression_externalization import (
    OutwardExpressionExternalizationConfig,
    OutwardExpressionExternalizationDraft,
    OutwardExpressionExternalizationError,
    OutwardExpressionExternalizationRequest,
)


def test_externalization_config_requires_confirmed_categories() -> None:
    with pytest.raises(OutwardExpressionExternalizationError, match="mandatory learned-parameter"):
        OutwardExpressionExternalizationConfig(
            externalization_bootstrap_id="outward-expression-externalization-bootstrap:v1",
            mandatory_learned_parameters=("envelope_rendering_policy",),
        )


def test_externalization_request_is_immutable() -> None:
    request = OutwardExpressionExternalizationRequest(
        request_id="outward-expression-externalization-request:001",
        source_outward_expression_draft_id="outward-expression-draft:001",
        source_prompt_contract_id="embodied-prompt-contract:001",
        rendered_prompt="[present_field] current field",
        delivery_channels=("cli",),
        delivery_ops=("reply_message",),
        delivery_guidance="Allowed channels: cli.",
        forbidden_capabilities=("direct_execution",),
        final_authorities=("planner", "channel", "identity_governance"),
        anti_theatrical_constraints=("avoid empty self-consciousness performance",),
    )

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"


def test_externalization_draft_requires_non_empty_fields() -> None:
    with pytest.raises(OutwardExpressionExternalizationError, match="candidate_channels"):
        OutwardExpressionExternalizationDraft(
            draft_id="outward-expression-externalization-draft:001",
            source_request_id="outward-expression-externalization-request:001",
            source_outward_expression_draft_id="outward-expression-draft:001",
            source_prompt_contract_id="embodied-prompt-contract:001",
            externalization_prompt="[present_field] current field",
            candidate_channels=(),
            candidate_ops=("reply_message",),
            execution_boundary_summary="Final authorities remain outside this owner.",
            forbidden_capabilities=("direct_execution",),
            final_authorities=("planner",),
            anti_theatrical_constraints=("avoid empty self-consciousness performance",),
        )