from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.evaluation import (
    ConsequenceClaim,
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


def test_consequence_claim_rejects_empty_id() -> None:
    with pytest.raises(EvaluationError, match="claim_id"):
        ConsequenceClaim(
            claim_id="",
            tick_id=1,
            consequence_path_outcome="continuity_written",
            planner_status="executed",
            action_status="normalized",
            continuity_written=True,
        )


def test_consequence_claim_rejects_unknown_outcome() -> None:
    with pytest.raises(EvaluationError, match="outcome vocabulary"):
        ConsequenceClaim(
            claim_id="consequence-claim:001",
            tick_id=1,
            consequence_path_outcome="invented_outcome",
            planner_status="executed",
            action_status="normalized",
            continuity_written=True,
        )


def test_consequence_claim_projects_to_evidence() -> None:
    claim = ConsequenceClaim(
        claim_id="consequence-claim:001",
        tick_id=4,
        consequence_path_outcome="executed",
        planner_status="executed",
        action_status="normalized",
        continuity_written=False,
    )

    evidence = claim.to_evidence("prior-consequence-claim:tick:4")

    assert evidence["evidence_id"] == "prior-consequence-claim:tick:4"
    assert evidence["tick_id"] == 4
    assert evidence["consequence_path_outcome"] == "executed"
    assert evidence["planner_status"] == "executed"
    assert evidence["continuity_written"] is False

    with pytest.raises(EvaluationError, match="non-empty evidence_id"):
        claim.to_evidence("")


def test_evaluation_bundle_freezes_prior_consequence_claim_evidence() -> None:
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
        prior_consequence_claim_evidence=(
            (
                {
                    "evidence_id": "prior-consequence-claim:tick:1",
                    "tick_id": 1,
                    "consequence_path_outcome": "continuity_written",
                }
            ),
        ),
    )

    with pytest.raises(TypeError):
        bundle.prior_consequence_claim_evidence[0]["tick_id"] = 2


def test_evaluation_bundle_rejects_prior_claim_evidence_without_evidence_id() -> None:
    with pytest.raises(EvaluationError, match="prior_consequence_claim_evidence"):
        EvaluationEvidenceBundle(
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
            prior_consequence_claim_evidence=(({"tick_id": 1}),),
        )