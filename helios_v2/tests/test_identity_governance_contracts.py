from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.identity_governance import (
    AppliedIdentityState,
    GovernancePressureState,
    IdentityGovernanceConfig,
    IdentityGovernanceError,
    IdentityGovernanceRequest,
    IdentityGovernanceResult,
    RevisionDecision,
)


def test_identity_governance_request_is_immutable_and_snapshots_are_read_only() -> None:
    request = IdentityGovernanceRequest(
        request_id="identity-governance-request:001",
        source_thought_cycle_result_id="thought-cycle-result:001",
        source_proposal_id="self-revision:001",
        proposal_present=True,
        proposal_snapshot={"revision_type": "self_definition_revision"},
        identity_state_snapshot={"self_definition": "current", "revision_history_length": 0},
        governance_trace_summary={"total_deferred_traces": 0},
        recent_governance_trace_history=(),
        tick_id=1,
    )

    with pytest.raises(FrozenInstanceError):
        request.proposal_present = False

    with pytest.raises(TypeError):
        request.identity_state_snapshot["self_definition"] = "mutated"


def test_identity_governance_config_requires_fixed_learned_policy_surface() -> None:
    config = IdentityGovernanceConfig(
        legal_min_confidence=0.0,
        legal_max_confidence=1.0,
        governance_bootstrap_id="identity-governance-bootstrap:v1",
        mandatory_learned_parameters=(
            "governance_evaluation_policy",
            "pressure_interpretation_policy",
            "supported_revision_policy",
            "boundary_check_policy",
        ),
    )

    assert config.governance_bootstrap_id == "identity-governance-bootstrap:v1"

    with pytest.raises(IdentityGovernanceError, match="mandatory learned-parameter categories"):
        IdentityGovernanceConfig(
            legal_min_confidence=0.0,
            legal_max_confidence=1.0,
            governance_bootstrap_id="identity-governance-bootstrap:v1",
            mandatory_learned_parameters=("governance_evaluation_policy",),
        )


def test_result_distinguishes_monitoring_acceptance_from_rejected_outcome() -> None:
    pressure = GovernancePressureState(
        active=True,
        pressure_score=0.59,
        pressure_level="monitor",
        review_hint="review_identity_revision_carefully",
        recent_trace_count=4,
        source_consistency_ratio=1.0,
        recent_trigger_sources=("continuity",),
    )
    decision = RevisionDecision(
        revision_id="identity-revision:001",
        proposal_id="self-revision:001",
        origin_thought_id="thought:001",
        status="accepted_with_monitoring",
        requested_change={"self_definition": "updated"},
        applied_change={"self_definition": "updated"},
        rejection_reason=None,
        reason_trace=("proactive_governance_monitoring",),
    )
    applied = AppliedIdentityState(
        revision_id=decision.revision_id,
        current_revision=decision.revision_id,
        identity_state_snapshot={"self_definition": "updated", "current_revision": decision.revision_id},
        changed_fields=("self_definition", "current_revision"),
    )
    result = IdentityGovernanceResult(
        result_id="identity-governance-result:001",
        source_request_id="identity-governance-request:001",
        pressure_state=pressure,
        revision_decision=decision,
        applied_identity_state=applied,
        tick_id=1,
    )

    assert result.revision_decision.status == "accepted_with_monitoring"


def test_applied_identity_state_is_immutable() -> None:
    applied = AppliedIdentityState(
        revision_id="identity-revision:001",
        current_revision="identity-revision:001",
        identity_state_snapshot={"self_definition": "updated"},
        changed_fields=("self_definition",),
    )

    with pytest.raises(TypeError):
        applied.identity_state_snapshot["self_definition"] = "mutated"
