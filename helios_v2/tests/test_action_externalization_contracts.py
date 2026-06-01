from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.action_externalization import (
    ActionExternalizationConfig,
    ActionExternalizationError,
    EquivalentBridgeEvidence,
    NormalizedThoughtActionProposal,
    ThoughtExternalizationRequest,
    ThoughtExternalizationResult,
)


def test_externalization_request_is_immutable_and_contexts_are_read_only() -> None:
    request = ThoughtExternalizationRequest(
        request_id="externalization-request:001",
        source_thought_cycle_result_id="thought-cycle-result:001",
        proposal_carrier_present=True,
        target_binding_context={"target_user_id": "user:001"},
        channel_hint_context={"channel_family": "cli"},
        tick_id=1,
    )

    with pytest.raises(FrozenInstanceError):
        request.proposal_carrier_present = False

    with pytest.raises(TypeError):
        request.target_binding_context["target_user_id"] = "user:002"


def test_normalized_external_proposal_requires_final_outbound_text() -> None:
    proposal = NormalizedThoughtActionProposal(
        proposal_id="normalized-proposal:001",
        origin_thought_id="thought:001",
        owner_path="thought_action_bridge",
        scope="external",
        behavior_name="reply_message",
        preferred_op="reply_message",
        params={"outbound_text": "hello"},
        channel_constraints={"preferred_channels": ("cli",)},
        outbound_intensity=0.7,
        reason_trace=("explicit proposal",),
        governance_hints={"requires_identity_review": False},
    )

    assert proposal.params["outbound_text"] == "hello"

    with pytest.raises(ActionExternalizationError, match="outbound_text"):
        NormalizedThoughtActionProposal(
            proposal_id="normalized-proposal:bad",
            origin_thought_id="thought:001",
            owner_path="thought_action_bridge",
            scope="external",
            behavior_name="reply_message",
            preferred_op="reply_message",
            params={},
            channel_constraints={"preferred_channels": ("cli",)},
            outbound_intensity=0.7,
            reason_trace=("explicit proposal",),
            governance_hints={"requires_identity_review": False},
        )


def test_equivalent_evidence_stays_distinct_from_normalized_outcome() -> None:
    evidence = EquivalentBridgeEvidence(
        origin_thought_id="thought:001",
        bridge_evidence_kind="completed_thought_without_explicit_action",
        reason_trace=("evidence only",),
        candidate_summary={"thought_type": "reflective"},
    )
    result = ThoughtExternalizationResult(
        result_id="thought-externalization-result:001",
        source_request_id="externalization-request:001",
        status="equivalent_evidence_only",
        normalized_proposal=None,
        bridge_rejection_reason=None,
        equivalent_evidence=evidence,
        tick_id=1,
    )

    assert result.equivalent_evidence is evidence


def test_externalization_config_requires_fixed_learned_policy_surface() -> None:
    config = ActionExternalizationConfig(
        legal_min_outbound_intensity=0.0,
        legal_max_outbound_intensity=1.0,
        externalization_bootstrap_id="action-externalization-bootstrap:v1",
        mandatory_learned_parameters=(
            "normalization_policy",
            "bridge_evidence_policy",
            "bridge_rejection_policy",
        ),
    )

    assert config.externalization_bootstrap_id == "action-externalization-bootstrap:v1"

    with pytest.raises(ActionExternalizationError, match="mandatory learned-parameter categories"):
        ActionExternalizationConfig(
            legal_min_outbound_intensity=0.0,
            legal_max_outbound_intensity=1.0,
            externalization_bootstrap_id="action-externalization-bootstrap:v1",
            mandatory_learned_parameters=("normalization_policy",),
        )
