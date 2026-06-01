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


def _build_bundle(*, include_outward_externalization: bool = True) -> EvaluationEvidenceBundle:
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
    assert publish_op.warning_count == 0


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