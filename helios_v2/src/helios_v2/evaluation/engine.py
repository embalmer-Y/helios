"""First-version path for read-only evaluation artifact assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from .contracts import (
    ConsequenceClaim,
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
    "internal_only_decision": "the system fired a thought and explicitly chose not to act this cycle",
    "blocked": "action was normalized but execution was blocked or failed",
    "rejected": "action was normalized but policy-rejected before execution",
    "executed": "action executed externally but was not yet written back to continuity",
    "continuity_written": "internal activation closed into executed action and continuity writeback",
}

_CONSEQUENCE_BINDING_SCORES: dict[str, float] = {
    "no_activation": 0.0,
    "internally_activated_only": 0.2,
    "internal_only_decision": 0.5,
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

# Canonical kernel stage names the corroboration mapping checks against the execution
# timeline. These are execution-timing facts only; the corroboration never reads an owner's
# semantic decision payload (the timeline carries none).
_PLANNER_BRIDGE_STAGE = "planner_executor_feedback_bridge"
_WRITEBACK_STAGE = "execution_writeback_and_autobiographical_consolidation"
_THOUGHT_STAGE = "internal_thought_loop_owner"

# The corroboration verdict vocabulary published as a first-class artifact field.
_CORROBORATION_CORROBORATED = "corroborated"
_CORROBORATION_DISCREPANT = "discrepant"
_CORROBORATION_UNVERIFIABLE = "unverifiable_no_timeline"

# R87: the real-delivery verdict vocabulary, published additively alongside (never replacing) the
# `32` stage-completion corroboration verdict. It upgrades an executed effector action's corroboration
# from "flow-completed" to "really-delivered" by matching the prior claim against the actual
# `tool_result` reafference observed this tick.
_DELIVERY_REALLY = "really_delivered"
_DELIVERY_FAILED = "delivered_failed"
_DELIVERY_UNVERIFIED = "delivery_unverified"
_DELIVERY_NOT_APPLICABLE = "delivery_not_applicable"


def _corroborate_delivery(
    prior_claim_evidence: tuple[Mapping[str, object], ...],
    delivered_tool_result_evidence: tuple[Mapping[str, object], ...],
) -> tuple[str, str]:
    """Owner: evaluation fidelity and diagnostic provenance (R87).

    Purpose:
        Corroborate the prior completed tick's executed-effector consequence claim against the actual
        `tool_result` reafference observed this tick, returning a delivery verdict + bounded detail.
        This is the "really-delivered" upgrade to the `32` "flow-completed" corroboration; it is strictly
        additive and never changes the `32` verdict or the scoring.

    Inputs:
        `prior_claim_evidence` - at most one projected `ConsequenceClaim` (the prior tick's), carrying
            the executed action's `decision_id`/`op_effect_class`/`op_user_visible`.
        `delivered_tool_result_evidence` - the `tool_result` reafferences drained this tick (each with a
            `decision_id` and an `ok` fact).

    Returns:
        A `(verdict, detail)` pair. `verdict` is one of `really_delivered`, `delivered_failed`,
        `delivery_unverified`, `delivery_not_applicable`.

    Notes:
        Read-only and never optimistic: a missing reafference for an effector action is
        `delivery_unverified` (e.g. a still-running async op), never `really_delivered`. A non-executed
        outcome, a non-effector (user-visible relay reply / internal) action, or a claim without a
        decision id is `delivery_not_applicable` (the `32` stage-completion corroboration stands). It
        matches by `decision_id` and reads the `ok` fact only; it re-derives no owner decision.
    """

    if not prior_claim_evidence:
        return _DELIVERY_NOT_APPLICABLE, "no_prior_claim"
    claim = prior_claim_evidence[0]
    outcome = claim.get("consequence_path_outcome")
    if outcome not in ("executed", "continuity_written"):
        return _DELIVERY_NOT_APPLICABLE, f"outcome:{outcome}"
    decision_id = claim.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id:
        return _DELIVERY_NOT_APPLICABLE, "no_decision_id"
    # Delivery corroboration applies only to a KNOWN non-user-visible effector op whose effect lands on
    # the host/world (it produces a `tool_result` reafference). An unknown op (no declared spec, e.g. a
    # legacy/shim reply), a user-visible relay reply (rendered to a sink, no reafference), or an internal
    # op is not applicable - the `32` stage-completion corroboration stands.
    if claim.get("op_user_visible") is not False:
        return _DELIVERY_NOT_APPLICABLE, "non_effector_op"
    if claim.get("op_effect_class") not in ("local_host", "external_world"):
        return _DELIVERY_NOT_APPLICABLE, "non_effector_op"
    match: Mapping[str, object] | None = None
    for item in delivered_tool_result_evidence:
        if item.get("decision_id") == decision_id:
            match = item
            break
    if match is None:
        return _DELIVERY_UNVERIFIED, "no_reafference_observed"
    if match.get("ok") is True:
        return _DELIVERY_REALLY, "reafference_ok"
    return _DELIVERY_FAILED, "effector_reported_failure"


def _timeline_stage_status_map(timeline_entry: Mapping[str, object]) -> dict[str, str]:
    """Project one timeline evidence entry into a {stage_name: status} map.

    Reads only the compact per-stage status list produced by
    `ExecutionTimelineView.to_evidence`. It interprets execution-timing facts only and never
    an owner decision. A stage absent from the timeline is simply absent from the map.
    """

    statuses: dict[str, str] = {}
    stages = timeline_entry.get("stages")
    if not isinstance(stages, (list, tuple)):
        return statuses
    for stage in stages:
        if not isinstance(stage, Mapping):
            continue
        stage_name = stage.get("stage_name")
        status = stage.get("status")
        if isinstance(stage_name, str) and stage_name and isinstance(status, str) and status:
            statuses[stage_name] = status
    return statuses


def _corroborate_consequence(
    prior_claim_evidence: tuple[Mapping[str, object], ...],
    timeline_evidence: tuple[Mapping[str, object], ...],
) -> tuple[str, str]:
    """Owner: evaluation fidelity and diagnostic provenance.

    Purpose:
        Corroborate the previous completed tick's self-reported consequence outcome against
        that same tick's kernel execution timeline, returning an explicit verdict and a
        bounded detail.

    Inputs:
        `prior_claim_evidence` - at most one projected `ConsequenceClaim` (the prior tick's).
        `timeline_evidence` - at most one projected `ExecutionTimelineView` (the prior tick's).

    Returns:
        A `(verdict, detail)` pair. `verdict` is one of `corroborated`, `discrepant`, or
        `unverifiable_no_timeline`. `detail` names the contradicted stage fact for a
        discrepancy, or the reason a pair could not be verified.

    Notes:
        Absence is never contradiction: a missing timeline, missing claim, tick mismatch, or
        a complete timeline that simply omits an implied stage yields `unverifiable_no_timeline`.
        A `discrepant` verdict is only returned when the timeline is present and an implied
        stage is recorded as failed, or the timeline is complete and an implied stage is
        affirmatively absent while another consequential stage is present. The mapping reads
        only kernel stage-completion facts; it re-derives no owner decision.
    """

    if not prior_claim_evidence:
        return _CORROBORATION_UNVERIFIABLE, "no_prior_claim"
    if not timeline_evidence:
        return _CORROBORATION_UNVERIFIABLE, "timeline_absent"

    claim = prior_claim_evidence[0]
    timeline = timeline_evidence[0]

    claim_tick = claim.get("tick_id")
    timeline_tick = timeline.get("tick_id")
    if timeline_tick is None:
        return _CORROBORATION_UNVERIFIABLE, "timeline_absent"
    if claim_tick is None or claim_tick != timeline_tick:
        return _CORROBORATION_UNVERIFIABLE, "tick_mismatch"
    if timeline.get("completed") is not True:
        return _CORROBORATION_UNVERIFIABLE, "timeline_incomplete"

    outcome = claim.get("consequence_path_outcome")
    statuses = _timeline_stage_status_map(timeline)

    def stage_completed(stage_name: str) -> bool:
        return statuses.get(stage_name) == "completed"

    def stage_failed(stage_name: str) -> bool:
        return statuses.get(stage_name) == "failed"

    def stage_present(stage_name: str) -> bool:
        return stage_name in statuses

    if outcome == "continuity_written":
        if stage_failed(_PLANNER_BRIDGE_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:planner_bridge_failed"
        if stage_failed(_WRITEBACK_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:writeback_failed"
        if not stage_completed(_PLANNER_BRIDGE_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:planner_bridge_not_completed"
        if not stage_completed(_WRITEBACK_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:writeback_not_completed"
        return _CORROBORATION_CORROBORATED, "all_implied_stages_present"

    if outcome in ("executed", "rejected"):
        if stage_failed(_PLANNER_BRIDGE_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:planner_bridge_failed"
        if not stage_completed(_PLANNER_BRIDGE_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:planner_bridge_not_completed"
        return _CORROBORATION_CORROBORATED, "all_implied_stages_present"

    if outcome == "blocked":
        # Blocked implies the planner segment did not cleanly complete: either a stage failed
        # somewhere, or the planner-bridge stage did not complete. A complete timeline that
        # shows the planner-bridge completed and no failed stage contradicts a blocked claim.
        any_failed = any(status == "failed" for status in statuses.values())
        if any_failed or not stage_completed(_PLANNER_BRIDGE_STAGE):
            return _CORROBORATION_CORROBORATED, "all_implied_stages_present"
        return _CORROBORATION_DISCREPANT, f"{outcome}:no_failed_stage_but_planner_completed"

    if outcome in ("internal_only_decision", "internally_activated_only"):
        if stage_failed(_THOUGHT_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:thought_failed"
        if not stage_completed(_THOUGHT_STAGE):
            return _CORROBORATION_DISCREPANT, f"{outcome}:thought_not_completed"
        return _CORROBORATION_CORROBORATED, "all_implied_stages_present"

    # `no_activation` (and any outcome without implied stage facts) is vacuously corroborated
    # once a complete prior timeline is present.
    del stage_present
    return _CORROBORATION_CORROBORATED, "no_implied_stage_facts"


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
        # An explicit internal-only decision (the planner recorded no actionable proposal)
        # is distinct from an activation that simply failed to normalize an action.
        if planner_status == "no_actionable_proposal":
            return "internal_only_decision"
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

        # Long-horizon continuity: read the autonomy owner's published thread summary if
        # present. Absence is reported explicitly rather than inferred.
        autonomy_entry = bundle.autonomy_evidence[0] if bundle.autonomy_evidence else None
        if autonomy_entry is not None and "active_thread_count" in autonomy_entry:
            active_thread_count = autonomy_entry.get("active_thread_count")
            dominant_thread_id = autonomy_entry.get("dominant_thread_id")
            dominant_reinforcement = autonomy_entry.get("dominant_reinforcement_count")
            if isinstance(active_thread_count, int) and active_thread_count > 0:
                if isinstance(dominant_reinforcement, int) and dominant_reinforcement > 0:
                    long_horizon_continuity = "reinforced_dominant_thread"
                else:
                    long_horizon_continuity = "forming_dominant_thread"
            else:
                long_horizon_continuity = "no_active_thread"
            long_horizon_continuity_detail = {
                "active_thread_count": active_thread_count,
                "dominant_thread_id": dominant_thread_id,
                "dominant_thread_age": autonomy_entry.get("dominant_thread_age"),
                "dominant_reinforcement_count": dominant_reinforcement,
                "max_thread_age": autonomy_entry.get("max_thread_age"),
                "aggregate_reinforcement": autonomy_entry.get("aggregate_reinforcement"),
            }
        else:
            long_horizon_continuity = "absent"
            long_horizon_continuity_detail = {}

        dimension_scores: dict[str, float] = {
            "thought_fidelity": 1.0 if bundle.thought_evidence else 0.0,
            "action_fidelity": 1.0 if action_status == "normalized" else 0.0,
            "continuity_fidelity": 1.0 if any_written else 0.0,
            "governance_fidelity": 1.0 if bundle.governance_evidence else 0.0,
            "autonomy_fidelity": 1.0 if bundle.autonomy_evidence else 0.0,
            "outward_expression_artifact_fidelity": 1.0 if outward_expression_gap == "no_gap" else 0.0,
            "internal_to_visible_consequence": internal_to_visible_score,
        }

        # Publish this tick's self-reported consequence claim so the next tick can corroborate
        # it against this tick's execution timeline. The claim carries only owner-published
        # statuses; it re-derives nothing. The current tick id arrives through the request's
        # time-window summary as an explicit owner-neutral field.
        current_tick_id = request.time_window_summary.get("current_tick_id")
        current_tick_id = current_tick_id if isinstance(current_tick_id, int) else None
        planner_entry = bundle.planner_evidence[0] if bundle.planner_evidence else {}
        claim_decision_id = planner_entry.get("decision_id")
        claim_selected_op = planner_entry.get("selected_op")
        claim_op_effect_class = planner_entry.get("op_effect_class")
        claim_op_user_visible = planner_entry.get("op_user_visible")
        consequence_claim = ConsequenceClaim(
            claim_id=f"consequence-claim:{bundle.bundle_id}",
            tick_id=current_tick_id,
            consequence_path_outcome=consequence_path_outcome,
            planner_status=planner_status if isinstance(planner_status, str) else None,
            action_status=action_status if isinstance(action_status, str) else None,
            continuity_written=any_written,
            decision_id=claim_decision_id if isinstance(claim_decision_id, str) else None,
            selected_op=claim_selected_op if isinstance(claim_selected_op, str) else None,
            op_effect_class=claim_op_effect_class if isinstance(claim_op_effect_class, str) else None,
            op_user_visible=claim_op_user_visible if isinstance(claim_op_user_visible, bool) else None,
        )

        # Corroborate the PRIOR completed tick's self-reported outcome against that same tick's
        # execution timeline. Both arrive carried-forward and tick-aligned by composition.
        corroboration_verdict, corroboration_detail = _corroborate_consequence(
            bundle.prior_consequence_claim_evidence,
            bundle.execution_timeline_evidence,
        )
        if corroboration_verdict == _CORROBORATION_DISCREPANT:
            prior_claim_refs = _bundle_ids(bundle.prior_consequence_claim_evidence)
            timeline_refs = _bundle_ids(bundle.execution_timeline_evidence)
            prior_outcome = bundle.prior_consequence_claim_evidence[0].get(
                "consequence_path_outcome"
            )
            warnings.append(
                _warning(
                    "warning:consequence-discrepancy",
                    "consequence_discrepancy",
                    "Prior-tick self-reported consequence outcome "
                    f"'{prior_outcome}' is contradicted by execution truth: {corroboration_detail}.",
                    (prior_claim_refs + timeline_refs) or (bundle.bundle_id,),
                )
            )

        # R87: corroborate the PRIOR tick's executed-effector claim against the actual `tool_result`
        # reafference drained this tick (matched by decision id), upgrading "flow-completed" to a
        # really-delivered verdict. Strictly additive: it never changes the `32` verdict or scoring.
        delivery_verdict, delivery_detail = _corroborate_delivery(
            bundle.prior_consequence_claim_evidence,
            bundle.delivered_tool_result_evidence,
        )
        if delivery_verdict == _DELIVERY_FAILED:
            prior_claim_refs = _bundle_ids(bundle.prior_consequence_claim_evidence)
            delivered_refs = _bundle_ids(bundle.delivered_tool_result_evidence)
            warnings.append(
                _warning(
                    "warning:consequence-delivery-discrepancy",
                    "consequence_delivery_discrepancy",
                    "Prior-tick executed effector action was not really delivered: the effector "
                    f"reported failure ({delivery_detail}).",
                    (prior_claim_refs + delivered_refs) or (bundle.bundle_id,),
                )
            )

        gap_summary: dict[str, object] = {
            "thought_to_action_gap": thought_to_action_gap,
            "action_to_writeback_gap": action_to_writeback_gap,
            "autonomy_continuity_gap": autonomy_gap,
            "outward_expression_artifact_gap": outward_expression_gap,
            "externally_consequential_activity": "present" if any_written else "not_confirmed",
            "continuity_written": any_written,
            "consequence_path_outcome": consequence_path_outcome,
            "consequence_binding": consequence_binding,
            "consequence_corroboration": corroboration_verdict,
            "consequence_corroboration_detail": corroboration_detail,
            "consequence_delivery": delivery_verdict,
            "consequence_delivery_detail": delivery_detail,
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
            "long_horizon_continuity": long_horizon_continuity,
            "long_horizon_continuity_detail": long_horizon_continuity_detail,
            "consequence_claim": consequence_claim.to_evidence(consequence_claim.claim_id),
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