from __future__ import annotations

import pytest

from helios_v2.outward_expression_externalization import (
    FirstVersionOutwardExpressionExternalizationPath,
    OutwardExpressionExternalizationConfig,
    OutwardExpressionExternalizationEngine,
    OutwardExpressionExternalizationError,
    OutwardExpressionExternalizationRequest,
)


def _build_config() -> OutwardExpressionExternalizationConfig:
    return OutwardExpressionExternalizationConfig(
        externalization_bootstrap_id="outward-expression-externalization-bootstrap:v1",
        mandatory_learned_parameters=(
            "envelope_rendering_policy",
            "delivery_selection_policy",
            "execution_boundary_policy",
        ),
    )


def _build_request() -> OutwardExpressionExternalizationRequest:
    return OutwardExpressionExternalizationRequest(
        request_id="outward-expression-externalization-request:001",
        source_outward_expression_draft_id="outward-expression-draft:001",
        source_prompt_contract_id="embodied-prompt-contract:001",
        rendered_prompt="[present_field] current field\n[action_autonomy] proposal only",
        delivery_channels=("cli",),
        delivery_ops=("reply_message",),
        delivery_guidance="Allowed channels: cli. Allowed ops: reply_message.",
        forbidden_capabilities=("direct_execution", "invented_channel"),
        final_authorities=("planner", "channel", "identity_governance"),
        anti_theatrical_constraints=(
            "avoid empty self-consciousness performance",
            "stay anchored to current evidence",
        ),
    )


def test_engine_prepares_externalization_side_draft() -> None:
    engine = OutwardExpressionExternalizationEngine(
        config=_build_config(),
        externalization_path=FirstVersionOutwardExpressionExternalizationPath(),
    )

    request = _build_request()
    request_op = engine.build_request_op(request)
    draft = engine.prepare_externalization_draft(request)
    publish_op = engine.build_publish_draft_op(draft)

    assert request_op.channel_count == 1
    assert request_op.op_count == 1
    assert draft.source_request_id == request.request_id
    assert draft.candidate_channels == ("cli",)
    assert draft.candidate_ops == ("reply_message",)
    assert "[delivery_guidance]" in draft.externalization_prompt
    assert "Final authorities remain: planner, channel, identity_governance." in draft.execution_boundary_summary
    assert publish_op.draft_id == draft.draft_id
    assert publish_op.channel_count == 1
    assert publish_op.op_count == 1


def test_first_version_externalization_path_requires_confirmed_bootstrap_id() -> None:
    engine = OutwardExpressionExternalizationEngine(
        config=OutwardExpressionExternalizationConfig(
            externalization_bootstrap_id="wrong-bootstrap",
            mandatory_learned_parameters=(
                "envelope_rendering_policy",
                "delivery_selection_policy",
                "execution_boundary_policy",
            ),
        ),
        externalization_path=FirstVersionOutwardExpressionExternalizationPath(),
    )

    with pytest.raises(
        OutwardExpressionExternalizationError,
        match="confirmed externalization bootstrap id",
    ):
        engine.prepare_externalization_draft(_build_request())