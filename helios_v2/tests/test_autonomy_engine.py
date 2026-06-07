from __future__ import annotations

import pytest

from helios_v2.autonomy import (
    AutonomyConfig,
    AutonomyEngine,
    AutonomyError,
    DeferredContinuityRecord,
    FirstVersionAutonomyPath,
    ProactiveDriveRequest,
)


def _build_config() -> AutonomyConfig:
    return AutonomyConfig(
        autonomy_bootstrap_id="autonomy-bootstrap:v1",
        mandatory_learned_parameters=(
            "drive_integration_policy",
            "continuity_carry_policy",
            "proactive_externalization_policy",
        ),
    )


def _build_request(
    *,
    outward_ready: bool,
    externalization_blocked: bool,
    continuation_pressure: float = 0.8,
    retrieval_pull: float = 0.4,
    temporal_pressure: float = 0.5,
    identity_unresolved_pressure: float = 0.4,
    prior_deferred_records: tuple[DeferredContinuityRecord, ...] = (),
    prior_continuity_threads: tuple = (),
    request_id: str = "autonomy-request:001",
) -> ProactiveDriveRequest:
    return ProactiveDriveRequest(
        request_id=request_id,
        source_gate_result_id="gate-result:001",
        source_retrieval_bundle_id="bundle:001",
        source_thought_cycle_result_id="thought-result:001",
        source_planner_bridge_result_id="planner-result:001",
        source_identity_governance_result_id="governance-result:001",
        source_writeback_result_ids=("writeback-result:001", "writeback-result:002"),
        source_outward_expression_draft_id="outward-expression-draft:001",
        source_outward_expression_externalization_draft_id="outward-expression-externalization-draft:001",
        continuation_summary={"continuation_pressure": continuation_pressure},
        retrieval_pull_summary={"retrieval_pull": retrieval_pull},
        temporal_pressure_summary={"temporal_pressure": temporal_pressure},
        identity_unresolved_summary={"identity_unresolved_pressure": identity_unresolved_pressure},
        outward_readiness_summary={
            "outward_ready": outward_ready,
            "externalization_blocked": externalization_blocked,
        },
        prior_deferred_records=prior_deferred_records,
        prior_continuity_threads=prior_continuity_threads,
    )


def test_engine_preserves_blocked_outward_tendency_as_deferred_continuity() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    request = _build_request(outward_ready=True, externalization_blocked=True)
    evaluate_op = engine.build_evaluate_op(request)
    result = engine.evaluate(request)
    publish_op = engine.build_publish_result_op(result)

    assert evaluate_op.request_id == request.request_id
    assert result.drive_state.dominant_disposition == "defer"
    assert result.drive_state.activity_mode == "deferred_continuity"
    assert result.drive_state.proactive_action_requested is True
    assert result.drive_state.deferred_active is True
    assert len(result.deferred_records) == 1
    assert result.deferred_records[0].carry_reason == "blocked_outward_externalization"
    assert publish_op.deferred_count == 1


def test_engine_externalizes_when_outward_path_is_ready() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(_build_request(outward_ready=True, externalization_blocked=False))

    assert result.drive_state.dominant_disposition == "externalize"
    assert result.drive_state.activity_mode == "outward_proactive"
    assert result.drive_state.deferred_active is False
    assert result.deferred_records == ()


def test_engine_requires_explicit_autonomy_capability() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=None)

    with pytest.raises(AutonomyError, match="explicit autonomy capability"):
        engine.evaluate(_build_request(outward_ready=True, externalization_blocked=False))


def test_engine_carries_forward_prior_deferred_records_across_ticks() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(
        _build_request(
            outward_ready=False,
            externalization_blocked=False,
            continuation_pressure=0.1,
            retrieval_pull=0.1,
            temporal_pressure=0.1,
            identity_unresolved_pressure=0.1,
            prior_deferred_records=(
                DeferredContinuityRecord(
                    record_id="deferred-continuity:prior:001",
                    continuity_key="planner-result:001:blocked_outward_externalization",
                    origin_ref="planner-result:001",
                    carry_reason="blocked_outward_externalization",
                    carry_count=1,
                    decayed_pressure=0.8,
                    expires_after_ticks=3,
                ),
            ),
        )
    )

    assert result.drive_state.dominant_disposition == "defer"
    assert result.drive_state.activity_mode == "deferred_continuity"
    assert result.drive_state.deferred_active is True
    assert result.drive_state.pressure_components["prior_deferred_count"] == 1.0
    assert result.drive_state.pressure_components["generated_record_count"] == 0.0
    assert len(result.deferred_records) == 1
    assert result.deferred_records[0].carry_reason == "carried_forward:blocked_outward_externalization"
    assert result.deferred_records[0].carry_count == 2
    assert result.deferred_records[0].decayed_pressure == pytest.approx(0.656, rel=1e-6)
    assert result.deferred_records[0].expires_after_ticks == 2


def test_engine_merges_matching_prior_records_and_reports_merge_count() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(
        _build_request(
            outward_ready=False,
            externalization_blocked=False,
            continuation_pressure=0.1,
            retrieval_pull=0.1,
            temporal_pressure=0.1,
            identity_unresolved_pressure=0.1,
            prior_deferred_records=(
                DeferredContinuityRecord(
                    record_id="deferred-continuity:prior:001",
                    continuity_key="planner-result:001:blocked_outward_externalization",
                    origin_ref="planner-result:001",
                    carry_reason="blocked_outward_externalization",
                    carry_count=1,
                    decayed_pressure=0.5,
                    expires_after_ticks=3,
                ),
                DeferredContinuityRecord(
                    record_id="deferred-continuity:prior:002",
                    continuity_key="planner-result:001:blocked_outward_externalization",
                    origin_ref="planner-result:001",
                    carry_reason="blocked_outward_externalization",
                    carry_count=2,
                    decayed_pressure=0.4,
                    expires_after_ticks=2,
                ),
            ),
        )
    )

    assert len(result.deferred_records) == 1
    assert result.deferred_records[0].carry_reason == "merged:blocked_outward_externalization"
    assert result.deferred_records[0].carry_count == 3
    assert result.deferred_records[0].decayed_pressure == pytest.approx(0.738, rel=1e-6)
    assert result.drive_state.pressure_components["merged_record_count"] == 1.0


def test_engine_resolves_prior_deferred_records_when_outward_path_recovers() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(
        _build_request(
            outward_ready=True,
            externalization_blocked=False,
            prior_deferred_records=(
                DeferredContinuityRecord(
                    record_id="deferred-continuity:prior:003",
                    continuity_key="planner-result:001:blocked_outward_externalization",
                    origin_ref="planner-result:001",
                    carry_reason="blocked_outward_externalization",
                    carry_count=1,
                    decayed_pressure=0.8,
                    expires_after_ticks=3,
                ),
            ),
        )
    )

    assert result.drive_state.dominant_disposition == "externalize"
    assert result.drive_state.deferred_active is False
    assert result.deferred_records == ()
    assert result.drive_state.pressure_components["resolved_record_count"] == 1.0


def test_engine_expires_weak_prior_deferred_records() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(
        _build_request(
            outward_ready=False,
            externalization_blocked=False,
            continuation_pressure=0.1,
            retrieval_pull=0.1,
            temporal_pressure=0.1,
            identity_unresolved_pressure=0.1,
            prior_deferred_records=(
                DeferredContinuityRecord(
                    record_id="deferred-continuity:prior:004",
                    continuity_key="planner-result:002:blocked_outward_externalization",
                    origin_ref="planner-result:002",
                    carry_reason="blocked_outward_externalization",
                    carry_count=1,
                    decayed_pressure=0.1,
                    expires_after_ticks=3,
                ),
            ),
        )
    )

    assert result.deferred_records == ()
    assert result.drive_state.pressure_components["expired_record_count"] == 1.0


def test_blocked_tendency_forms_a_continuity_thread() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    result = engine.evaluate(_build_request(outward_ready=True, externalization_blocked=True))

    state = result.long_horizon_state
    assert state.active_thread_count == 1
    thread = state.threads[0]
    assert thread.thread_state == "forming"
    assert thread.age_ticks == 1
    assert thread.reinforcement_count == 0
    assert state.dominant_thread_id == thread.thread_id


def test_recurring_tendency_reinforces_its_thread_across_ticks() -> None:
    path = FirstVersionAutonomyPath()
    engine = AutonomyEngine(config=_build_config(), autonomy_path=path)

    first = engine.evaluate(
        _build_request(outward_ready=True, externalization_blocked=True, request_id="autonomy-request:t1")
    )
    second = engine.evaluate(
        _build_request(
            outward_ready=True,
            externalization_blocked=True,
            request_id="autonomy-request:t2",
            prior_deferred_records=first.deferred_records,
            prior_continuity_threads=first.long_horizon_state.threads,
        )
    )

    first_thread = first.long_horizon_state.threads[0]
    second_thread = second.long_horizon_state.threads[0]
    assert first_thread.reinforcement_count == 0
    assert second_thread.reinforcement_count == 1
    assert second_thread.age_ticks == first_thread.age_ticks + 1
    assert second_thread.thread_state == "reinforced"
    assert second_thread.thread_strength >= first_thread.thread_strength


def test_no_deferred_continuity_yields_empty_long_horizon_state() -> None:
    engine = AutonomyEngine(config=_build_config(), autonomy_path=FirstVersionAutonomyPath())

    # An outward-ready, unblocked, high-pressure request externalizes and defers nothing.
    result = engine.evaluate(_build_request(outward_ready=True, externalization_blocked=False))

    assert result.drive_state.dominant_disposition == "externalize"
    assert result.long_horizon_state.active_thread_count == 0
    assert result.long_horizon_state.dominant_thread_id is None


# --- Requirement 57: owner-owned cognition-to-drive-input projection ---


from helios_v2.autonomy import (
    AutonomyDriveInputProjection,
    OUTWARD_ACTION_THRESHOLD,
    ProactiveCognitionFacts,
)


def _facts(
    *,
    activated: bool = True,
    has_action_proposal: bool = False,
    continuation_requested: bool = False,
    continuation_active: bool = False,
    has_self_revision: bool = False,
    planner_status: str = "no_actionable_proposal",
    retrieval_hit_count: int = 0,
) -> ProactiveCognitionFacts:
    return ProactiveCognitionFacts(
        activated=activated,
        has_action_proposal=has_action_proposal,
        continuation_requested=continuation_requested,
        continuation_active=continuation_active,
        has_self_revision=has_self_revision,
        planner_status=planner_status,
        retrieval_hit_count=retrieval_hit_count,
    )


def _outward_drive(summaries: dict[str, dict[str, object]]) -> float:
    return (
        summaries["continuation_summary"]["continuation_pressure"]
        + summaries["temporal_pressure_summary"]["temporal_pressure"]
        + summaries["identity_unresolved_summary"]["identity_unresolved_pressure"]
    )


def test_projection_action_executed_reaches_action_threshold_and_is_ready() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(
        _facts(has_action_proposal=True, planner_status="executed", retrieval_hit_count=2)
    )
    # Action-bearing tick: 0.9 + 0.4 + 0.4 = 1.7 >= 1.6.
    assert _outward_drive(summaries) >= OUTWARD_ACTION_THRESHOLD
    assert summaries["continuation_summary"]["continuation_pressure"] == 0.9
    assert summaries["temporal_pressure_summary"]["temporal_pressure"] == 0.4
    assert summaries["identity_unresolved_summary"]["identity_unresolved_pressure"] == 0.4
    assert summaries["outward_readiness_summary"]["outward_ready"] is True
    assert summaries["outward_readiness_summary"]["externalization_blocked"] is False
    # retrieval_pull = 2 / 4.0 = 0.5.
    assert summaries["retrieval_pull_summary"]["retrieval_pull"] == 0.5


def test_projection_action_blocked_marks_externalization_blocked() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(
        _facts(has_action_proposal=True, planner_status="policy_rejected")
    )
    assert summaries["outward_readiness_summary"]["outward_ready"] is False
    assert summaries["outward_readiness_summary"]["externalization_blocked"] is True
    # Still an action-bearing tick: outward_drive reaches the threshold.
    assert _outward_drive(summaries) >= OUTWARD_ACTION_THRESHOLD


def test_projection_continue_no_action_stays_below_threshold() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(
        _facts(has_action_proposal=False, continuation_requested=True, planner_status="no_actionable_proposal")
    )
    assert summaries["continuation_summary"]["continuation_pressure"] == 0.8
    assert _outward_drive(summaries) < OUTWARD_ACTION_THRESHOLD
    assert summaries["outward_readiness_summary"]["outward_ready"] is False
    assert summaries["outward_readiness_summary"]["externalization_blocked"] is False


def test_projection_concluded_no_continue_uses_low_continuation() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(_facts(has_action_proposal=False))
    assert summaries["continuation_summary"]["continuation_pressure"] == 0.3


def test_projection_self_revision_raises_identity_pressure() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(_facts(has_action_proposal=False, has_self_revision=True))
    assert summaries["identity_unresolved_summary"]["identity_unresolved_pressure"] == 0.6


def test_projection_no_fire_tick_has_no_outward_readiness() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(
        _facts(activated=False, continuation_active=True, planner_status="no_actionable_proposal")
    )
    # No-fire carries continuation from the active continuation state, no outward readiness.
    assert summaries["continuation_summary"]["continuation_pressure"] == 0.8
    assert summaries["retrieval_pull_summary"]["retrieval_pull"] == 0.0
    assert summaries["temporal_pressure_summary"]["temporal_pressure"] == 0.3
    assert summaries["identity_unresolved_summary"]["identity_unresolved_pressure"] == 0.2
    assert summaries["outward_readiness_summary"]["outward_ready"] is False
    assert summaries["outward_readiness_summary"]["externalization_blocked"] is False


def test_projection_no_fire_concluded_uses_low_continuation() -> None:
    projection = AutonomyDriveInputProjection()
    summaries = projection.derive_drive_inputs(_facts(activated=False, continuation_active=False))
    assert summaries["continuation_summary"]["continuation_pressure"] == 0.3


def test_projection_is_deterministic() -> None:
    projection = AutonomyDriveInputProjection()
    facts = _facts(has_action_proposal=True, planner_status="executed", retrieval_hit_count=3)
    assert projection.derive_drive_inputs(facts) == projection.derive_drive_inputs(facts)


def test_cognition_facts_reject_empty_planner_status() -> None:
    with pytest.raises(AutonomyError, match="planner_status"):
        _facts(planner_status="")


def test_cognition_facts_reject_negative_hit_count() -> None:
    with pytest.raises(AutonomyError, match="retrieval_hit_count"):
        _facts(retrieval_hit_count=-1)
