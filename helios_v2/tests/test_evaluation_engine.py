from __future__ import annotations

import pytest

from helios_v2.evaluation import (
    EvaluationConfig,
    EvaluationEngine,
    EvaluationError,
    EvaluationEvidenceBundle,
    EvaluationRequest,
    FirstVersionEvaluationPath,
)


def _build_config() -> EvaluationConfig:
    return EvaluationConfig(
        evaluation_bootstrap_id="evaluation-bootstrap:v1",
        mandatory_learned_parameters=(
            "fidelity_scoring_policy",
            "gap_analysis_policy",
            "long_range_diagnostic_policy",
        ),
    )


def _build_request() -> EvaluationRequest:
    return EvaluationRequest(
        request_id="evaluation-request:001",
        scenario_kind="runtime_tick",
        time_window_summary={
            "window_label": "tick-1",
            "late_session_degradation_status": "not_evaluated",
            "specific_recall_persistence_status": "not_evaluated",
            "user_visible_anchoring_drift_status": "not_evaluated",
            "comparison_window_label": "runtime_tick:1",
        },
    )


def _build_bundle(
    *,
    include_outward_externalization: bool = True,
    include_timeline: bool = True,
) -> EvaluationEvidenceBundle:
    return EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:001",
        source_request_id="evaluation-request:001",
        thought_evidence=(({"evidence_id": "thought-result:001", "execution_status": "completed"}),),
        action_evidence=(({"evidence_id": "externalization-result:001", "status": "normalized"}),),
        planner_evidence=(({"evidence_id": "planner-result:001", "status": "executed"}),),
        governance_evidence=(({"evidence_id": "governance-result:001", "status": "accepted"}),),
        writeback_evidence=(
            ({"evidence_id": "writeback-result:001", "status": "written"}),
            ({"evidence_id": "writeback-result:002", "status": "written_identity_change"}),
        ),
        autonomy_evidence=(({"evidence_id": "autonomy-result:001", "deferred_active": False}),),
        prompt_evidence=(({"evidence_id": "prompt-contract:001", "status": "published"}),),
        outward_expression_evidence=(({"evidence_id": "outward-expression-draft:001", "status": "prepared"}),),
        outward_expression_externalization_evidence=(
            ({"evidence_id": "outward-expression-externalization-draft:001", "status": "prepared"}),
        )
        if include_outward_externalization
        else (),
        execution_timeline_evidence=(
            (
                {
                    "evidence_id": "execution-timeline-evidence:tick:1",
                    "tick_id": 1,
                    "completed": True,
                    "stage_count": 19,
                    "stages": [],
                },
            )
            if include_timeline
            else ()
        ),
    )


def test_engine_assembles_read_only_artifact_from_explicit_evidence() -> None:
    engine = EvaluationEngine(
        config=_build_config(),
        evaluation_path=FirstVersionEvaluationPath(),
    )

    request = _build_request()
    bundle = _build_bundle()
    evaluate_op = engine.build_evaluate_op(request, bundle)
    artifact = engine.evaluate(request, bundle)
    publish_op = engine.build_publish_artifact_op(artifact)

    assert evaluate_op.bundle_id == bundle.bundle_id
    assert artifact.source_bundle_id == bundle.bundle_id
    assert artifact.dimension_scores["thought_fidelity"] == 1.0
    assert artifact.dimension_scores["autonomy_fidelity"] == 1.0
    assert artifact.dimension_scores["outward_expression_artifact_fidelity"] == 1.0
    assert artifact.gap_summary["thought_to_action_gap"] == "no_gap"
    assert artifact.gap_summary["autonomy_continuity_gap"] == "no_gap"
    assert artifact.gap_summary["outward_expression_artifact_gap"] == "no_gap"
    assert artifact.long_range_diagnostics["comparison_window_label"] == "runtime_tick:1"
    assert artifact.long_range_diagnostics["execution_timeline_status"] == "observed"
    assert artifact.long_range_diagnostics["execution_timeline_tick_id"] == 1
    assert artifact.gap_summary["consequence_path_outcome"] == "continuity_written"
    assert artifact.dimension_scores["internal_to_visible_consequence"] == 1.0
    assert "internal_to_visible_consequence" in artifact.long_range_diagnostics["shim_derived_dimensions"]
    assert publish_op.warning_count == 0


def test_engine_consequence_binding_distinguishes_path_outcomes() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())

    def _bundle_with(planner_status: str, writeback: tuple, action_status: str = "normalized"):
        return EvaluationEvidenceBundle(
            bundle_id="evaluation-bundle:cb",
            source_request_id="evaluation-request:001",
            thought_evidence=(({"evidence_id": "thought:cb", "execution_status": "completed"}),),
            action_evidence=(({"evidence_id": "action:cb", "status": action_status}),),
            planner_evidence=(({"evidence_id": "planner:cb", "status": planner_status}),),
            governance_evidence=(({"evidence_id": "gov:cb", "status": "accepted"}),),
            writeback_evidence=writeback,
            autonomy_evidence=(({"evidence_id": "autonomy:cb", "deferred_active": False}),),
            prompt_evidence=(({"evidence_id": "prompt:cb", "status": "published"}),),
            outward_expression_evidence=(({"evidence_id": "oe:cb", "status": "prepared"}),),
            outward_expression_externalization_evidence=(({"evidence_id": "oee:cb", "status": "prepared"}),),
            execution_timeline_evidence=(),
        )

    request = _build_request()
    written = (({"evidence_id": "wb:cb", "status": "written"}),)

    executed_written = engine.evaluate(request, _bundle_with("executed", written))
    assert executed_written.gap_summary["consequence_path_outcome"] == "continuity_written"
    assert executed_written.dimension_scores["internal_to_visible_consequence"] == 1.0

    executed_only = engine.evaluate(request, _bundle_with("executed", ()))
    assert executed_only.gap_summary["consequence_path_outcome"] == "executed"
    assert executed_only.dimension_scores["internal_to_visible_consequence"] == 0.8

    rejected = engine.evaluate(request, _bundle_with("policy_rejected", ()))
    assert rejected.gap_summary["consequence_path_outcome"] == "rejected"

    blocked = engine.evaluate(request, _bundle_with("execution_failed", ()))
    assert blocked.gap_summary["consequence_path_outcome"] == "blocked"

    internally_only = engine.evaluate(request, _bundle_with("accepted", (), action_status="rejected"))
    assert internally_only.gap_summary["consequence_path_outcome"] == "internally_activated_only"


def test_engine_warns_explicitly_when_execution_timeline_evidence_is_absent() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())

    artifact = engine.evaluate(_build_request(), _build_bundle(include_timeline=False))

    warning_ids = {warning.warning_id for warning in artifact.fidelity_warnings}
    assert "warning:missing-execution-timeline" in warning_ids
    assert artifact.long_range_diagnostics["execution_timeline_status"] == "absent_uninstrumented"


def test_engine_reports_long_horizon_continuity_from_autonomy_evidence() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())

    bundle = EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:lh",
        source_request_id="evaluation-request:001",
        thought_evidence=(({"evidence_id": "thought:lh", "execution_status": "completed"}),),
        action_evidence=(({"evidence_id": "action:lh", "status": "normalized"}),),
        planner_evidence=(({"evidence_id": "planner:lh", "status": "executed"}),),
        governance_evidence=(({"evidence_id": "gov:lh", "status": "accepted"}),),
        writeback_evidence=(({"evidence_id": "wb:lh", "status": "written"}),),
        autonomy_evidence=(
            {
                "evidence_id": "autonomy:lh",
                "dominant_disposition": "defer",
                "deferred_active": True,
                "proactive_action_requested": True,
                "active_thread_count": 1,
                "dominant_thread_id": "continuity-thread:lh:1",
                "dominant_thread_age": 3,
                "dominant_reinforcement_count": 2,
                "max_thread_age": 3,
                "aggregate_reinforcement": 2,
            },
        ),
        prompt_evidence=(({"evidence_id": "prompt:lh", "status": "published"}),),
        outward_expression_evidence=(({"evidence_id": "oe:lh", "status": "prepared"}),),
        outward_expression_externalization_evidence=(({"evidence_id": "oee:lh", "status": "prepared"}),),
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.long_range_diagnostics["long_horizon_continuity"] == "reinforced_dominant_thread"
    detail = artifact.long_range_diagnostics["long_horizon_continuity_detail"]
    assert detail["dominant_thread_id"] == "continuity-thread:lh:1"
    assert detail["aggregate_reinforcement"] == 2


def test_engine_reports_absent_long_horizon_continuity_without_thread_fields() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())

    artifact = engine.evaluate(_build_request(), _build_bundle())

    # The baseline bundle's autonomy evidence carries no thread fields.
    assert artifact.long_range_diagnostics["long_horizon_continuity"] == "absent"


def test_engine_publishes_explicit_warning_when_outward_expression_chain_is_incomplete() -> None:
    engine = EvaluationEngine(
        config=_build_config(),
        evaluation_path=FirstVersionEvaluationPath(),
    )

    artifact = engine.evaluate(_build_request(), _build_bundle(include_outward_externalization=False))

    warning_kinds = {warning.warning_kind for warning in artifact.fidelity_warnings}
    assert "artifact_gap" in warning_kinds
    assert artifact.gap_summary["outward_expression_artifact_gap"] == (
        "missing_outward_expression_externalization_draft"
    )
    assert artifact.dimension_scores["outward_expression_artifact_fidelity"] == 0.0


def test_engine_requires_explicit_evaluation_capability() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=None)

    with pytest.raises(EvaluationError, match="explicit evaluation capability"):
        engine.evaluate(_build_request(), _build_bundle())


# ---------------------------------------------------------------------------
# R32: execution-truth-corroborated consequence binding.
# ---------------------------------------------------------------------------


def _timeline_evidence(tick_id: int, stage_statuses: tuple[tuple[str, str], ...], *, completed: bool = True):
    """Build one execution-timeline evidence entry projecting the given stage statuses."""

    stages = [
        {
            "stage_name": name,
            "stage_index": index,
            "status": status,
            "duration_ms": 0.1,
            "error_type": None if status == "completed" else "StageError",
        }
        for index, (name, status) in enumerate(stage_statuses)
    ]
    return (
        {
            "evidence_id": f"execution-timeline-evidence:tick:{tick_id}",
            "tick_id": tick_id,
            "completed": completed,
            "stage_count": len(stages),
            "stages": stages,
        },
    )


def _prior_claim_evidence(tick_id: int, outcome: str):
    return (
        {
            "evidence_id": f"prior-consequence-claim:tick:{tick_id}",
            "tick_id": tick_id,
            "consequence_path_outcome": outcome,
            "planner_status": "executed",
            "action_status": "normalized",
            "continuity_written": outcome == "continuity_written",
        },
    )


def _bundle_with_corroboration(
    *,
    prior_claim_evidence=(),
    timeline_evidence=(),
):
    return EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:corr",
        source_request_id="evaluation-request:001",
        thought_evidence=(({"evidence_id": "thought:corr", "execution_status": "completed"}),),
        action_evidence=(({"evidence_id": "action:corr", "status": "normalized"}),),
        planner_evidence=(({"evidence_id": "planner:corr", "status": "executed"}),),
        governance_evidence=(({"evidence_id": "gov:corr", "status": "accepted"}),),
        writeback_evidence=(({"evidence_id": "wb:corr", "status": "written"}),),
        autonomy_evidence=(({"evidence_id": "autonomy:corr", "deferred_active": False}),),
        prompt_evidence=(({"evidence_id": "prompt:corr", "status": "published"}),),
        outward_expression_evidence=(({"evidence_id": "oe:corr", "status": "prepared"}),),
        outward_expression_externalization_evidence=(({"evidence_id": "oee:corr", "status": "prepared"}),),
        execution_timeline_evidence=timeline_evidence,
        prior_consequence_claim_evidence=prior_claim_evidence,
    )


def _engine() -> EvaluationEngine:
    return EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())


def test_engine_publishes_consequence_claim_for_evaluated_tick() -> None:
    engine = _engine()
    request = EvaluationRequest(
        request_id="evaluation-request:001",
        scenario_kind="runtime_tick",
        time_window_summary={"window_label": "tick-7", "current_tick_id": 7},
    )

    artifact = engine.evaluate(request, _build_bundle())

    claim = artifact.long_range_diagnostics["consequence_claim"]
    assert claim["consequence_path_outcome"] == "continuity_written"
    assert claim["tick_id"] == 7
    assert claim["planner_status"] == "executed"
    assert claim["continuity_written"] is True


def test_engine_corroborates_continuity_written_against_complete_timeline() -> None:
    engine = _engine()
    timeline = _timeline_evidence(
        3,
        (
            ("internal_thought_loop_owner", "completed"),
            ("planner_executor_feedback_bridge", "completed"),
            ("execution_writeback_and_autobiographical_consolidation", "completed"),
        ),
    )
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=_prior_claim_evidence(3, "continuity_written"),
        timeline_evidence=timeline,
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "corroborated"
    warning_kinds = {w.warning_kind for w in artifact.fidelity_warnings}
    assert "consequence_discrepancy" not in warning_kinds


def test_engine_flags_discrepancy_when_implied_stage_missing() -> None:
    engine = _engine()
    # continuity_written claimed, but the writeback stage never ran in a complete timeline.
    timeline = _timeline_evidence(
        3,
        (
            ("internal_thought_loop_owner", "completed"),
            ("planner_executor_feedback_bridge", "completed"),
        ),
    )
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=_prior_claim_evidence(3, "continuity_written"),
        timeline_evidence=timeline,
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "discrepant"
    assert "writeback_not_completed" in artifact.gap_summary["consequence_corroboration_detail"]
    discrepancy = [w for w in artifact.fidelity_warnings if w.warning_kind == "consequence_discrepancy"]
    assert len(discrepancy) == 1
    refs = set(discrepancy[0].evidence_refs)
    assert "prior-consequence-claim:tick:3" in refs
    assert "execution-timeline-evidence:tick:3" in refs


def test_engine_flags_discrepancy_when_implied_stage_failed() -> None:
    engine = _engine()
    timeline = _timeline_evidence(
        3,
        (
            ("internal_thought_loop_owner", "completed"),
            ("planner_executor_feedback_bridge", "failed"),
        ),
    )
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=_prior_claim_evidence(3, "executed"),
        timeline_evidence=timeline,
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "discrepant"
    assert "planner_bridge_failed" in artifact.gap_summary["consequence_corroboration_detail"]


def test_engine_corroboration_unverifiable_without_timeline() -> None:
    engine = _engine()
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=_prior_claim_evidence(3, "continuity_written"),
        timeline_evidence=(),
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "unverifiable_no_timeline"
    assert artifact.gap_summary["consequence_corroboration_detail"] == "timeline_absent"
    warning_kinds = {w.warning_kind for w in artifact.fidelity_warnings}
    assert "consequence_discrepancy" not in warning_kinds


def test_engine_corroboration_unverifiable_without_prior_claim() -> None:
    engine = _engine()
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=(),
        timeline_evidence=_timeline_evidence(
            3, (("planner_executor_feedback_bridge", "completed"),)
        ),
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "unverifiable_no_timeline"
    assert artifact.gap_summary["consequence_corroboration_detail"] == "no_prior_claim"


def test_engine_corroboration_unverifiable_on_tick_mismatch() -> None:
    engine = _engine()
    bundle = _bundle_with_corroboration(
        prior_claim_evidence=_prior_claim_evidence(2, "continuity_written"),
        timeline_evidence=_timeline_evidence(
            3,
            (
                ("planner_executor_feedback_bridge", "completed"),
                ("execution_writeback_and_autobiographical_consolidation", "completed"),
            ),
        ),
    )

    artifact = engine.evaluate(_build_request(), bundle)

    assert artifact.gap_summary["consequence_corroboration"] == "unverifiable_no_timeline"
    assert artifact.gap_summary["consequence_corroboration_detail"] == "tick_mismatch"


def test_engine_corroboration_is_strictly_additive_to_existing_scoring() -> None:
    engine = _engine()
    bundle = _build_bundle()

    artifact = engine.evaluate(_build_request(), bundle)

    # Existing scoring and outcome taxonomy are unchanged by R32.
    assert artifact.gap_summary["consequence_path_outcome"] == "continuity_written"
    assert artifact.dimension_scores["internal_to_visible_consequence"] == 1.0
    assert artifact.dimension_scores["thought_fidelity"] == 1.0
    # The corroboration verdict is published additively; with no prior claim it is unverifiable.
    assert artifact.gap_summary["consequence_corroboration"] == "unverifiable_no_timeline"


# --- Requirement 87: real-delivery corroboration ---

from helios_v2.evaluation.engine import _corroborate_delivery  # noqa: E402


def _prior_claim(
    *,
    outcome: str = "executed",
    decision_id: str | None = "action-decision:1",
    op_effect_class: str | None = "local_host",
    op_user_visible: bool | None = False,
) -> dict:
    return {
        "evidence_id": "prior-consequence-claim:1",
        "tick_id": 1,
        "consequence_path_outcome": outcome,
        "planner_status": "executed",
        "action_status": "normalized",
        "continuity_written": False,
        "decision_id": decision_id,
        "selected_op": "fs_write",
        "op_effect_class": op_effect_class,
        "op_user_visible": op_user_visible,
    }


def _delivered(decision_id: str, ok: bool) -> dict:
    return {"evidence_id": f"tool-result:{decision_id}", "decision_id": decision_id, "ok": ok}


def test_delivery_not_applicable_without_prior_claim() -> None:
    verdict, _ = _corroborate_delivery((), ())
    assert verdict == "delivery_not_applicable"


def test_delivery_not_applicable_for_non_executed_outcome() -> None:
    verdict, detail = _corroborate_delivery((_prior_claim(outcome="internal_only_decision"),), ())
    assert verdict == "delivery_not_applicable"
    assert "outcome" in detail


def test_delivery_not_applicable_for_user_visible_relay() -> None:
    verdict, detail = _corroborate_delivery((_prior_claim(op_user_visible=True),), ())
    assert verdict == "delivery_not_applicable"
    assert detail == "non_effector_op"


def test_delivery_not_applicable_without_decision_id() -> None:
    verdict, _ = _corroborate_delivery((_prior_claim(decision_id=None),), ())
    assert verdict == "delivery_not_applicable"


def test_delivery_unverified_when_no_reafference() -> None:
    verdict, _ = _corroborate_delivery((_prior_claim(),), ())
    assert verdict == "delivery_unverified"


def test_really_delivered_on_matching_ok_reafference() -> None:
    verdict, _ = _corroborate_delivery(
        (_prior_claim(decision_id="action-decision:7"),),
        (_delivered("action-decision:7", ok=True),),
    )
    assert verdict == "really_delivered"


def test_delivered_failed_on_matching_failure_reafference() -> None:
    verdict, detail = _corroborate_delivery(
        (_prior_claim(decision_id="action-decision:7"),),
        (_delivered("action-decision:7", ok=False),),
    )
    assert verdict == "delivered_failed"
    assert detail == "effector_reported_failure"


def test_really_delivered_integration_keeps_32_verdict_unchanged() -> None:
    # An executed effector claim + its matching ok reafference -> really_delivered, while the
    # existing R32 consequence_corroboration verdict and scoring are untouched.
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())
    bundle = EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:deliv",
        source_request_id="evaluation-request:001",
        thought_evidence=({"evidence_id": "t1", "execution_status": "completed"},),
        action_evidence=({"evidence_id": "a1", "status": "normalized"},),
        planner_evidence=({"evidence_id": "p1", "status": "executed"},),
        governance_evidence=({"evidence_id": "g1", "status": "accepted"},),
        writeback_evidence=({"evidence_id": "w1", "status": "written"},),
        autonomy_evidence=({"evidence_id": "au1", "deferred_active": False},),
        prompt_evidence=({"evidence_id": "pr1", "status": "published"},),
        outward_expression_evidence=({"evidence_id": "oe1", "status": "prepared"},),
        outward_expression_externalization_evidence=({"evidence_id": "oee1", "status": "prepared"},),
        execution_timeline_evidence=(),
        prior_consequence_claim_evidence=(_prior_claim(decision_id="action-decision:9"),),
        delivered_tool_result_evidence=(_delivered("action-decision:9", ok=True),),
    )
    artifact = engine.evaluate(_build_request(), bundle)
    assert artifact.gap_summary["consequence_delivery"] == "really_delivered"
    # R32 verdict is unverifiable here (no timeline) and unchanged by R87.
    assert artifact.gap_summary["consequence_corroboration"] == "unverifiable_no_timeline"


def test_delivered_failed_integration_raises_warning() -> None:
    engine = EvaluationEngine(config=_build_config(), evaluation_path=FirstVersionEvaluationPath())
    bundle = EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:delivfail",
        source_request_id="evaluation-request:001",
        thought_evidence=({"evidence_id": "t1", "execution_status": "completed"},),
        action_evidence=({"evidence_id": "a1", "status": "normalized"},),
        planner_evidence=({"evidence_id": "p1", "status": "executed"},),
        governance_evidence=({"evidence_id": "g1", "status": "accepted"},),
        writeback_evidence=({"evidence_id": "w1", "status": "written"},),
        autonomy_evidence=({"evidence_id": "au1", "deferred_active": False},),
        prompt_evidence=({"evidence_id": "pr1", "status": "published"},),
        outward_expression_evidence=({"evidence_id": "oe1", "status": "prepared"},),
        outward_expression_externalization_evidence=({"evidence_id": "oee1", "status": "prepared"},),
        prior_consequence_claim_evidence=(_prior_claim(decision_id="action-decision:9"),),
        delivered_tool_result_evidence=(_delivered("action-decision:9", ok=False),),
    )
    artifact = engine.evaluate(_build_request(), bundle)
    assert artifact.gap_summary["consequence_delivery"] == "delivered_failed"
    assert any(w.warning_kind == "consequence_delivery_discrepancy" for w in artifact.fidelity_warnings)
