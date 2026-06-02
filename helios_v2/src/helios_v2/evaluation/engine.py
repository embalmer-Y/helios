"""First-version path for read-only evaluation artifact assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from .contracts import (
    EvaluateEvidenceBundleOp,
    EvaluationAPI,
    EvaluationArtifact,
    EvaluationConfig,
    EvaluationError,
    EvaluationEvidenceBundle,
    EvaluationRequest,
    FidelityWarning,
    PublishEvaluationArtifactOp,
)


def _bundle_ids(items: tuple[Mapping[str, object], ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for item in items:
        value = item.get("evidence_id")
        if isinstance(value, str) and value:
            refs.append(value)
    return tuple(refs)


def _warning(
    warning_id: str,
    warning_kind: str,
    summary: str,
    evidence_refs: tuple[str, ...],
) -> FidelityWarning:
    refs = evidence_refs or (warning_id,)
    return FidelityWarning(
        warning_id=warning_id,
        warning_kind=warning_kind,
        summary=summary,
        evidence_refs=refs,
    )


# Path outcomes for internal-to-visible consequence binding, ordered from no activation
# to full continuity-written consequence. These labels and scores are the formal
# consequence-binding vocabulary published in the evaluation artifact.
_CONSEQUENCE_BINDING_LABELS: dict[str, str] = {
    "no_activation": "no internal activation reached the chain",
    "internally_activated_only": "internal activation did not produce a normalized action",
    "blocked": "action was normalized but execution was blocked or failed",
    "rejected": "action was normalized but policy-rejected before execution",
    "executed": "action executed externally but was not yet written back to continuity",
    "continuity_written": "internal activation closed into executed action and continuity writeback",
}

_CONSEQUENCE_BINDING_SCORES: dict[str, float] = {
    "no_activation": 0.0,
    "internally_activated_only": 0.2,
    "blocked": 0.4,
    "rejected": 0.4,
    "executed": 0.8,
    "continuity_written": 1.0,
}

# Dimensions whose scores are currently derived from deterministic first-version shim
# evidence rather than from genuinely non-deterministic cognition. This annotation keeps
# the diagnostic honest while the cognition chain is still a shim.
_SHIM_DERIVED_DIMENSIONS: tuple[str, ...] = (
    "thought_fidelity",
    "action_fidelity",
    "continuity_fidelity",
    "governance_fidelity",
    "autonomy_fidelity",
    "outward_expression_artifact_fidelity",
    "internal_to_visible_consequence",
)


def _classify_consequence_outcome(
    *,
    has_thought: bool,
    action_status: object,
    planner_status: object,
    any_written: bool,
) -> str:
    """Map owner-published statuses into one explicit internal-to-visible path outcome.

    This uses only statuses already published by upstream owners (action normalization
    status, planner bridge status, and whether continuity was written). It performs no
    heuristic re-derivation of any owner's decision.
    """

    if not has_thought:
        return "no_activation"
    if action_status != "normalized":
        return "internally_activated_only"
    if planner_status == "executed":
        return "continuity_written" if any_written else "executed"
    if planner_status == "policy_rejected":
        return "rejected"
    if planner_status in {"execution_failed", "execution_consistency_failed"}:
        return "blocked"
    # accepted-but-not-executed, or any other normalized-yet-inconsequential path
    return "internally_activated_only"


@runtime_checkable
class EvaluationPath(Protocol):
    """Owner-private path that assembles one evaluation artifact from a request and evidence bundle."""

    def assemble_artifact(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
        config: EvaluationConfig,
    ) -> EvaluationArtifact:
        """Return one deterministic evaluation artifact from validated inputs."""

        ...


@dataclass(frozen=True)
class FirstVersionEvaluationPath:
    """First shipped evaluation path consuming explicit runtime evidence only."""

    def assemble_artifact(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
        config: EvaluationConfig,
    ) -> EvaluationArtifact:
        if config.evaluation_bootstrap_id != "evaluation-bootstrap:v1":
            raise EvaluationError(
                "FirstVersionEvaluationPath requires the confirmed evaluation bootstrap id"
            )

        thought_refs = _bundle_ids(bundle.thought_evidence)
        action_refs = _bundle_ids(bundle.action_evidence)
        planner_refs = _bundle_ids(bundle.planner_evidence)
        governance_refs = _bundle_ids(bundle.governance_evidence)
        writeback_refs = _bundle_ids(bundle.writeback_evidence)
        prompt_refs = _bundle_ids(bundle.prompt_evidence)
        outward_refs = _bundle_ids(bundle.outward_expression_evidence)
        outward_ext_refs = _bundle_ids(bundle.outward_expression_externalization_evidence)

        action_status = bundle.action_evidence[0].get("status") if bundle.action_evidence else None
        planner_status = bundle.planner_evidence[0].get("status") if bundle.planner_evidence else None
        writeback_statuses = tuple(item.get("status") for item in bundle.writeback_evidence)
        any_written = any(
            isinstance(status, str) and status.startswith("written") for status in writeback_statuses
        )

        thought_to_action_gap = (
            "missing_thought_evidence"
            if not bundle.thought_evidence
            else "missing_action_evidence"
            if not bundle.action_evidence
            else f"action_status:{action_status}"
            if action_status != "normalized"
            else "no_gap"
        )
        action_to_writeback_gap = (
            "missing_planner_evidence"
            if not bundle.planner_evidence
            else "missing_writeback_evidence"
            if not bundle.writeback_evidence
            else f"planner_status:{planner_status}"
            if planner_status not in {"executed", "execution_failed", "accepted", "policy_rejected", "execution_consistency_failed"}
            else "no_gap"
            if any_written
            else f"writeback_statuses:{','.join(str(status) for status in writeback_statuses)}"
        )
        outward_expression_gap = (
            "missing_prompt_evidence"
            if not bundle.prompt_evidence
            else "missing_outward_expression_draft"
            if not bundle.outward_expression_evidence
            else "missing_outward_expression_externalization_draft"
            if not bundle.outward_expression_externalization_evidence
            else "no_gap"
        )
        autonomy_gap = (
            "missing_autonomy_evidence"
            if not bundle.autonomy_evidence
            else "deferred_continuity_preserved"
            if bundle.autonomy_evidence[0].get("deferred_active") is True
            else "no_gap"
        )

        # Consequence-binding: map the chain into one explicit internal-to-visible path
        # outcome using owner-published statuses only (no heuristic re-derivation).
        consequence_path_outcome = _classify_consequence_outcome(
            has_thought=bool(bundle.thought_evidence),
            action_status=action_status,
            planner_status=planner_status,
            any_written=any_written,
        )
        consequence_binding = _CONSEQUENCE_BINDING_LABELS[consequence_path_outcome]
        internal_to_visible_score = _CONSEQUENCE_BINDING_SCORES[consequence_path_outcome]

        # Execution-timeline status: derived only from the prior-tick timeline evidence
        # provided by the observability owner. Absence is reported explicitly; fidelity is
        # never inferred from a missing timeline.
        timeline_evidence = bundle.execution_timeline_evidence
        if not timeline_evidence:
            execution_timeline_status = "absent_uninstrumented"
            timeline_tick_id: object = None
        else:
            entry = timeline_evidence[0]
            prior_tick = entry.get("tick_id")
            if prior_tick is None:
                execution_timeline_status = "no_prior_timeline"
                timeline_tick_id = None
            elif entry.get("completed") is True:
                execution_timeline_status = "observed"
                timeline_tick_id = prior_tick
            else:
                execution_timeline_status = "observed_incomplete"
                timeline_tick_id = prior_tick

        warnings: list[FidelityWarning] = []
        if not bundle.thought_evidence:
            warnings.append(
                _warning(
                    "warning:missing-thought-evidence",
                    "missing_evidence",
                    "Evaluation bundle is missing thought evidence.",
                    (bundle.bundle_id,),
                )
            )
        if not bundle.action_evidence:
            warnings.append(
                _warning(
                    "warning:missing-action-evidence",
                    "missing_evidence",
                    "Evaluation bundle is missing action externalization evidence.",
                    thought_refs or (bundle.bundle_id,),
                )
            )
        if not bundle.planner_evidence:
            warnings.append(
                _warning(
                    "warning:missing-planner-evidence",
                    "missing_evidence",
                    "Evaluation bundle is missing planner outcome evidence.",
                    action_refs or (bundle.bundle_id,),
                )
            )
        if not bundle.writeback_evidence:
            warnings.append(
                _warning(
                    "warning:missing-writeback-evidence",
                    "missing_evidence",
                    "Evaluation bundle is missing continuity writeback evidence.",
                    planner_refs or governance_refs or (bundle.bundle_id,),
                )
            )
        if not bundle.autonomy_evidence:
            warnings.append(
                _warning(
                    "warning:missing-autonomy-evidence",
                    "missing_evidence",
                    "Evaluation bundle is missing autonomy evidence.",
                    writeback_refs or (bundle.bundle_id,),
                )
            )
        if not bundle.execution_timeline_evidence:
            warnings.append(
                _warning(
                    "warning:missing-execution-timeline",
                    "missing_timeline",
                    "Evaluation bundle has no execution-timeline evidence; runtime may be uninstrumented.",
                    (bundle.bundle_id,),
                )
            )
        if outward_expression_gap != "no_gap":
            warnings.append(
                _warning(
                    "warning:outward-expression-chain-incomplete",
                    "artifact_gap",
                    "Outward-expression artifact chain is incomplete.",
                    prompt_refs + outward_refs + outward_ext_refs or (bundle.bundle_id,),
                )
            )
        if thought_to_action_gap != "no_gap":
            warnings.append(
                _warning(
                    "warning:thought-to-action-gap",
                    "chain_gap",
                    f"Thought-to-action gap detected: {thought_to_action_gap}.",
                    thought_refs + action_refs or (bundle.bundle_id,),
                )
            )
        if action_to_writeback_gap != "no_gap":
            warnings.append(
                _warning(
                    "warning:action-to-writeback-gap",
                    "chain_gap",
                    f"Action-to-writeback gap detected: {action_to_writeback_gap}.",
                    action_refs + planner_refs + writeback_refs or (bundle.bundle_id,),
                )
            )

        dimension_scores: dict[str, float] = {
            "thought_fidelity": 1.0 if bundle.thought_evidence else 0.0,
            "action_fidelity": 1.0 if action_status == "normalized" else 0.0,
            "continuity_fidelity": 1.0 if any_written else 0.0,
            "governance_fidelity": 1.0 if bundle.governance_evidence else 0.0,
            "autonomy_fidelity": 1.0 if bundle.autonomy_evidence else 0.0,
            "outward_expression_artifact_fidelity": 1.0 if outward_expression_gap == "no_gap" else 0.0,
            "internal_to_visible_consequence": internal_to_visible_score,
        }

        gap_summary: dict[str, object] = {
            "thought_to_action_gap": thought_to_action_gap,
            "action_to_writeback_gap": action_to_writeback_gap,
            "autonomy_continuity_gap": autonomy_gap,
            "outward_expression_artifact_gap": outward_expression_gap,
            "externally_consequential_activity": "present" if any_written else "not_confirmed",
            "continuity_written": any_written,
            "consequence_path_outcome": consequence_path_outcome,
            "consequence_binding": consequence_binding,
        }

        long_range_diagnostics: dict[str, object] = {
            "late_session_degradation_status": request.time_window_summary.get(
                "late_session_degradation_status",
                "not_evaluated",
            ),
            "continuity_carry_persistence_status": (
                "deferred_continuity_preserved"
                if autonomy_gap == "deferred_continuity_preserved"
                else "observed"
                if any_written
                else "not_observed"
            ),
            "specific_recall_persistence_status": request.time_window_summary.get(
                "specific_recall_persistence_status",
                "not_evaluated",
            ),
            "user_visible_anchoring_drift_status": request.time_window_summary.get(
                "user_visible_anchoring_drift_status",
                "not_evaluated",
            ),
            "comparison_window_label": request.time_window_summary.get(
                "comparison_window_label",
                request.scenario_kind,
            ),
            "execution_timeline_status": execution_timeline_status,
            "execution_timeline_tick_id": timeline_tick_id,
            "shim_derived_dimensions": _SHIM_DERIVED_DIMENSIONS,
        }

        return EvaluationArtifact(
            artifact_id=f"evaluation-artifact:{bundle.bundle_id}",
            source_bundle_id=bundle.bundle_id,
            dimension_scores=dimension_scores,
            gap_summary=gap_summary,
            fidelity_warnings=tuple(warnings),
            long_range_diagnostics=long_range_diagnostics,
        )


@dataclass(frozen=True)
class EvaluationEngine(EvaluationAPI):
    """Public owner that assembles read-only evaluation artifacts from explicit evidence."""

    config: EvaluationConfig
    evaluation_path: EvaluationPath | None

    def build_evaluate_op(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
    ) -> EvaluateEvidenceBundleOp:
        if bundle.source_request_id != request.request_id:
            raise EvaluationError(
                "EvaluationEvidenceBundle must preserve the source request id"
            )
        return EvaluateEvidenceBundleOp(
            op_name="evaluate_evidence_bundle",
            owner="evaluation_fidelity_and_diagnostic_provenance",
            request_id=request.request_id,
            bundle_id=bundle.bundle_id,
            scenario_kind=request.scenario_kind,
        )

    def evaluate(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
    ) -> EvaluationArtifact:
        if bundle.source_request_id != request.request_id:
            raise EvaluationError(
                "EvaluationEvidenceBundle must preserve the source request id"
            )
        if self.evaluation_path is None:
            raise EvaluationError("Evaluation requires an explicit evaluation capability")
        return self.evaluation_path.assemble_artifact(request, bundle, self.config)

    def build_publish_artifact_op(
        self,
        artifact: EvaluationArtifact,
    ) -> PublishEvaluationArtifactOp:
        return PublishEvaluationArtifactOp(
            op_name="publish_evaluation_artifact",
            owner="evaluation_fidelity_and_diagnostic_provenance",
            artifact_id=artifact.artifact_id,
            source_bundle_id=artifact.source_bundle_id,
            warning_count=len(artifact.fidelity_warnings),
        )