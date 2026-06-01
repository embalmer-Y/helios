from __future__ import annotations

import pytest

from helios_v2.outward_expression import (
    FirstVersionOutwardExpressionPath,
    OutwardExpressionConfig,
    OutwardExpressionEngine,
    OutwardExpressionError,
    OutwardExpressionRequest,
)


def _build_config() -> OutwardExpressionConfig:
    return OutwardExpressionConfig(
        outward_expression_bootstrap_id="outward-expression-bootstrap:v1",
        mandatory_learned_parameters=(
            "delivery_guidance_policy",
            "boundary_rendering_policy",
            "draft_publication_policy",
        ),
    )


def _build_request() -> OutwardExpressionRequest:
    return OutwardExpressionRequest(
        request_id="outward-expression-request:001",
        source_prompt_view_id="outward-expression-view:001",
        source_prompt_contract_id="embodied-prompt-contract:001",
        rendered_prompt="[present_field] current field\n[action_autonomy] proposal only",
        available_channels=("cli",),
        available_ops=("reply_message",),
        forbidden_capabilities=("direct_execution", "invented_channel"),
        final_authorities=("planner", "channel", "identity_governance"),
        anti_theatrical_constraints=(
            "avoid empty self-consciousness performance",
            "stay anchored to current evidence",
        ),
    )


def test_engine_prepares_bounded_outward_expression_draft() -> None:
    engine = OutwardExpressionEngine(
        config=_build_config(),
        outward_expression_path=FirstVersionOutwardExpressionPath(),
    )

    request = _build_request()
    prepare_op = engine.build_prepare_op(request)
    draft = engine.prepare_draft(request)
    publish_op = engine.build_publish_draft_op(draft)

    assert prepare_op.channel_count == 1
    assert prepare_op.op_count == 1
    assert draft.source_request_id == request.request_id
    assert draft.delivery_channels == ("cli",)
    assert draft.delivery_ops == ("reply_message",)
    assert "Final authorities remain: planner, channel, identity_governance." in draft.delivery_guidance
    assert publish_op.draft_id == draft.draft_id
    assert publish_op.channel_count == 1
    assert publish_op.op_count == 1


def test_first_version_path_requires_confirmed_bootstrap_id() -> None:
    engine = OutwardExpressionEngine(
        config=OutwardExpressionConfig(
            outward_expression_bootstrap_id="wrong-bootstrap",
            mandatory_learned_parameters=(
                "delivery_guidance_policy",
                "boundary_rendering_policy",
                "draft_publication_policy",
            ),
        ),
        outward_expression_path=FirstVersionOutwardExpressionPath(),
    )

    with pytest.raises(OutwardExpressionError, match="confirmed outward-expression bootstrap id"):
        engine.prepare_draft(_build_request())