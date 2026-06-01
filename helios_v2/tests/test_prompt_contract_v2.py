from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.prompt_contract import (
    EmbodiedPromptConfig,
    EmbodiedPromptEngine,
    EmbodiedPromptRequest,
    FirstVersionEmbodiedPromptPath,
    PromptContractError,
)


def _build_config() -> EmbodiedPromptConfig:
    return EmbodiedPromptConfig(
        max_layer_count=8,
        prompt_bootstrap_id="embodied-prompt-bootstrap:v1",
        mandatory_learned_parameters=(
            "layering_policy",
            "anti_theatrical_policy",
            "action_boundary_policy",
        ),
    )


def _request(consumer_kind: str) -> EmbodiedPromptRequest:
    return EmbodiedPromptRequest(
        request_id=f"embodied-prompt-request:{consumer_kind}:001",
        consumer_kind=consumer_kind,
        source_conscious_state_id="conscious-state:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        stimulus_summary={
            "present_field": "A user utterance is present in the current field through cli text.",
        },
        state_summary={
            "affective_summary": "arousal is elevated but stable",
            "continuation_summary": "continuation pressure is active around the current user cue",
        },
        retrieval_summary={
            "retrieval_context": "current stimulus context and one autobiographical continuity trace are active",
            "continuity_context": "preserve the present user anchor and unresolved reply obligation",
        },
        capability_summary={
            "available_channels": ("cli",),
            "available_ops": ("reply_message",),
            "forbidden_capabilities": ("direct_execution", "invented_channel"),
        },
        identity_boundary_summary={
            "identity_boundary": "identity revision remains proposal-only and governance-validated",
        },
        tick_id=1,
    )


def test_prompt_request_is_immutable_and_mapping_is_read_only() -> None:
    request = _request("thought")

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"
    with pytest.raises(TypeError):
        request.capability_summary["available_channels"] = ("qq",)


def test_engine_preserves_cross_path_contract_family_consistency() -> None:
    engine = EmbodiedPromptEngine(
        config=_build_config(),
        prompt_path=FirstVersionEmbodiedPromptPath(),
    )

    thought_contract = engine.build_prompt_contract(_request("thought"))
    outward_contract = engine.build_prompt_contract(_request("outward_expression"))

    thought_layer_names = tuple(layer.layer_name for layer in thought_contract.layers)
    outward_layer_names = tuple(layer.layer_name for layer in outward_contract.layers)
    assert thought_layer_names == outward_layer_names
    assert thought_contract.action_boundary.supports_internal_action is True
    assert outward_contract.action_boundary.supports_internal_action is False
    assert thought_contract.action_boundary.supports_self_revision_proposal is True
    assert outward_contract.action_boundary.supports_self_revision_proposal is False


def test_engine_publishes_capability_boundaries_and_anti_theatrical_constraints() -> None:
    engine = EmbodiedPromptEngine(
        config=_build_config(),
        prompt_path=FirstVersionEmbodiedPromptPath(),
    )

    contract = engine.build_prompt_contract(_request("thought"))
    publish_op = engine.build_publish_op(contract)

    assert "planner, channel, and governance remain final authorities" in contract.layers[3].content.lower()
    assert "do not perform empty self-consciousness theater" in contract.layers[4].content.lower()
    assert contract.action_boundary.forbidden_capabilities == ("direct_execution", "invented_channel")
    assert publish_op.layer_count == len(contract.layers)


def test_engine_builds_minimal_outward_expression_consumer_view() -> None:
    engine = EmbodiedPromptEngine(
        config=_build_config(),
        prompt_path=FirstVersionEmbodiedPromptPath(),
    )

    contract = engine.build_prompt_contract(_request("outward_expression"))
    view = engine.build_outward_expression_view(contract)
    publish_op = engine.build_publish_outward_expression_view_op(view)

    assert view.source_contract_id == contract.contract_id
    assert view.available_channels == ("cli",)
    assert view.available_ops == ("reply_message",)
    assert "[present_field]" in view.rendered_prompt
    assert view.final_authorities == ("planner", "channel", "identity_governance")
    assert publish_op.channel_count == 1


def test_engine_builds_outward_expression_request_from_view() -> None:
    engine = EmbodiedPromptEngine(
        config=_build_config(),
        prompt_path=FirstVersionEmbodiedPromptPath(),
    )

    contract = engine.build_prompt_contract(_request("outward_expression"))
    view = engine.build_outward_expression_view(contract)
    request = engine.build_outward_expression_request(view)
    request_op = engine.build_outward_expression_request_op(request)

    assert request.source_prompt_view_id == view.view_id
    assert request.source_prompt_contract_id == view.source_contract_id
    assert request.available_channels == ("cli",)
    assert request.available_ops == ("reply_message",)
    assert request_op.source_prompt_view_id == view.view_id
    assert request_op.channel_count == 1


def test_engine_requires_explicit_prompt_capability() -> None:
    engine = EmbodiedPromptEngine(config=_build_config(), prompt_path=None)

    with pytest.raises(PromptContractError, match="explicit prompt capability"):
        engine.build_prompt_contract(_request("thought"))