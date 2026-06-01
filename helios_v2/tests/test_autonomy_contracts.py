from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.autonomy import (
    AutonomyConfig,
    DeferredContinuityRecord,
    AutonomyError,
    ProactiveDriveRequest,
    ProactiveDriveState,
)


def test_autonomy_config_requires_confirmed_categories() -> None:
    with pytest.raises(AutonomyError, match="mandatory learned-parameter"):
        AutonomyConfig(
            autonomy_bootstrap_id="autonomy-bootstrap:v1",
            mandatory_learned_parameters=("drive_integration_policy",),
        )


def test_proactive_drive_request_is_immutable() -> None:
    request = ProactiveDriveRequest(
        request_id="autonomy-request:001",
        source_gate_result_id="gate-result:001",
        source_retrieval_bundle_id="bundle:001",
        source_thought_cycle_result_id="thought-result:001",
        source_planner_bridge_result_id="planner-result:001",
        source_identity_governance_result_id="governance-result:001",
        source_writeback_result_ids=("writeback-result:001",),
        source_outward_expression_draft_id="outward-expression-draft:001",
        source_outward_expression_externalization_draft_id="outward-expression-externalization-draft:001",
        continuation_summary={"continuation_pressure": 0.8},
        retrieval_pull_summary={"retrieval_pull": 0.4},
        temporal_pressure_summary={"temporal_pressure": 0.3},
        identity_unresolved_summary={"identity_unresolved_pressure": 0.2},
        outward_readiness_summary={"outward_ready": True, "externalization_blocked": False},
    )

    with pytest.raises(FrozenInstanceError):
        request.request_id = "changed"
    with pytest.raises(TypeError):
        request.continuation_summary["continuation_pressure"] = 0.1


def test_proactive_drive_state_requires_known_taxonomy() -> None:
    with pytest.raises(AutonomyError, match="dominant_disposition"):
        ProactiveDriveState(
            state_id="drive-state:001",
            dominant_disposition="unknown",
            activity_mode="inward_reflective",
            pressure_components={"continuation_pressure": 0.5},
            deferred_active=False,
            proactive_action_requested=False,
        )


def test_deferred_continuity_record_requires_positive_decay_and_carry() -> None:
    with pytest.raises(AutonomyError, match="carry_count"):
        DeferredContinuityRecord(
            record_id="deferred:001",
            continuity_key="planner-result:001:blocked_outward_externalization",
            origin_ref="planner-result:001",
            carry_reason="blocked_outward_externalization",
            carry_count=0,
            decayed_pressure=0.5,
            expires_after_ticks=2,
        )

    with pytest.raises(AutonomyError, match="decayed_pressure"):
        DeferredContinuityRecord(
            record_id="deferred:002",
            continuity_key="planner-result:001:blocked_outward_externalization",
            origin_ref="planner-result:001",
            carry_reason="blocked_outward_externalization",
            carry_count=1,
            decayed_pressure=0.0,
            expires_after_ticks=2,
        )
