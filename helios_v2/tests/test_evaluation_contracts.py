from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.evaluation import (
    EvaluationArtifact,
    EvaluationConfig,
    EvaluationError,
    EvaluationEvidenceBundle,
    EvaluationRequest,
    FidelityWarning,
)


def test_evaluation_config_requires_confirmed_categories() -> None:
    with pytest.raises(EvaluationError, match="mandatory learned-parameter"):
        EvaluationConfig(
            evaluation_bootstrap_id="evaluation-bootstrap:v1",
            mandatory_learned_parameters=("fidelity_scoring_policy",),
        )


def test_evaluation_bundle_is_immutable() -> None:
    bundle = EvaluationEvidenceBundle(
        bundle_id="evaluation-bundle:001",
        source_request_id="evaluation-request:001",
        thought_evidence=(({"evidence_id": "thought:001", "status": "completed"}),),
        action_evidence=(({"evidence_id": "action:001", "status": "normalized"}),),
        planner_evidence=(({"evidence_id": "planner:001", "status": "executed"}),),
        governance_evidence=(({"evidence_id": "governance:001", "status": "accepted"}),),
        writeback_evidence=(({"evidence_id": "writeback:001", "status": "written"}),),
        autonomy_evidence=(({"evidence_id": "autonomy:001", "deferred_active": False}),),
        prompt_evidence=(({"evidence_id": "prompt:001", "status": "published"}),),
        outward_expression_evidence=(({"evidence_id": "outward:001", "status": "prepared"}),),
        outward_expression_externalization_evidence=(
            ({"evidence_id": "outward-ext:001", "status": "prepared"}),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        bundle.bundle_id = "changed"
    with pytest.raises(TypeError):
        bundle.thought_evidence[0]["status"] = "changed"


def test_evaluation_artifact_requires_non_empty_gap_summary() -> None:
    with pytest.raises(EvaluationError, match="gap_summary"):
        EvaluationArtifact(
            artifact_id="evaluation-artifact:001",
            source_bundle_id="evaluation-bundle:001",
            dimension_scores={"thought_fidelity": 1.0},
            gap_summary={},
            fidelity_warnings=(
                FidelityWarning(
                    warning_id="warning:001",
                    warning_kind="missing_evidence",
                    summary="missing writeback",
                    evidence_refs=("writeback:001",),
                ),
            ),
            long_range_diagnostics={"late_session_degradation_status": "not_evaluated"},
        )


def test_evaluation_request_requires_known_scenario_kind() -> None:
    with pytest.raises(EvaluationError, match="scenario_kind"):
        EvaluationRequest(
            request_id="evaluation-request:001",
            scenario_kind="unknown",
            time_window_summary={"window_label": "tick-1"},
        )