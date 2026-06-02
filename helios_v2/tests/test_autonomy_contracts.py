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


def test_continuity_thread_validates_strength_and_state() -> None:
    from helios_v2.autonomy import ContinuityThread

    thread = ContinuityThread(
        thread_id="continuity-thread:001",
        continuity_key="origin:reason",
        origin_ref="origin",
        age_ticks=2,
        reinforcement_count=1,
        thread_strength=0.6,
        thread_state="reinforced",
        last_carry_reason="blocked_outward_externalization",
    )
    assert thread.age_ticks == 2

    with pytest.raises(AutonomyError, match="thread_strength must be within"):
        ContinuityThread(
            thread_id="continuity-thread:002",
            continuity_key="k",
            origin_ref="o",
            age_ticks=1,
            reinforcement_count=0,
            thread_strength=1.5,
            thread_state="forming",
            last_carry_reason="r",
        )

    with pytest.raises(AutonomyError, match="thread_state must use the fixed taxonomy"):
        ContinuityThread(
            thread_id="continuity-thread:003",
            continuity_key="k",
            origin_ref="o",
            age_ticks=1,
            reinforcement_count=0,
            thread_strength=0.5,
            thread_state="unknown",
            last_carry_reason="r",
        )


def test_long_horizon_state_enforces_dominant_and_suppressed_invariants() -> None:
    from helios_v2.autonomy import ContinuityThread, LongHorizonContinuityState

    thread_a = ContinuityThread(
        thread_id="thread:a",
        continuity_key="ka",
        origin_ref="oa",
        age_ticks=3,
        reinforcement_count=2,
        thread_strength=0.9,
        thread_state="reinforced",
        last_carry_reason="ra",
    )
    thread_b = ContinuityThread(
        thread_id="thread:b",
        continuity_key="kb",
        origin_ref="ob",
        age_ticks=1,
        reinforcement_count=0,
        thread_strength=0.4,
        thread_state="suppressed",
        last_carry_reason="rb",
    )
    state = LongHorizonContinuityState(
        state_id="long-horizon:001",
        active_thread_count=2,
        dominant_thread_id="thread:a",
        suppressed_thread_ids=("thread:b",),
        max_thread_age=3,
        aggregate_reinforcement=2,
        threads=(thread_a, thread_b),
    )
    evidence = state.to_evidence()
    assert evidence["dominant_thread_id"] == "thread:a"
    assert evidence["dominant_reinforcement_count"] == 2
    assert evidence["active_thread_count"] == 2

    with pytest.raises(AutonomyError, match="must declare a dominant thread when threads exist"):
        LongHorizonContinuityState(
            state_id="long-horizon:002",
            active_thread_count=1,
            dominant_thread_id=None,
            suppressed_thread_ids=(),
            max_thread_age=1,
            aggregate_reinforcement=0,
            threads=(thread_a,),
        )

    with pytest.raises(AutonomyError, match="suppressed_thread_ids must exclude the dominant thread"):
        LongHorizonContinuityState(
            state_id="long-horizon:003",
            active_thread_count=2,
            dominant_thread_id="thread:a",
            suppressed_thread_ids=("thread:a",),
            max_thread_age=3,
            aggregate_reinforcement=2,
            threads=(thread_a, thread_b),
        )


def test_empty_long_horizon_state_rejects_dominant_thread() -> None:
    from helios_v2.autonomy import LongHorizonContinuityState

    with pytest.raises(AutonomyError, match="must not declare a dominant thread when no threads exist"):
        LongHorizonContinuityState(
            state_id="long-horizon:empty",
            active_thread_count=0,
            dominant_thread_id="ghost",
            suppressed_thread_ids=(),
            max_thread_age=0,
            aggregate_reinforcement=0,
            threads=(),
        )
