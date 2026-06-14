"""Owner: planner executor feedback bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from helios_v2.action_externalization import ThoughtExternalizationResult

from .contracts import (
    ActionDecision,
    EvaluatePlannerBridgeOp,
    ExecutionConsistencyFailure,
    NormalizedExecutionFeedback,
    PlannerBridgeAPI,
    PlannerBridgeConfig,
    PlannerBridgeError,
    PlannerBridgeRequest,
    PlannerBridgeResult,
    PublishActionDecisionOp,
    PublishExecutionFeedbackOp,
    PublishPlannerBridgeRejectionOp,
)


def _validate_externalization_result(externalization_result: ThoughtExternalizationResult) -> None:
    if not externalization_result.result_id:
        raise PlannerBridgeError("ThoughtExternalizationResult must declare a non-empty result_id")
    if externalization_result.status != "normalized" or externalization_result.normalized_proposal is None:
        raise PlannerBridgeError("Planner bridge requires a normalized ThoughtExternalizationResult")


def _validate_internal_only_externalization_result(
    externalization_result: ThoughtExternalizationResult,
) -> None:
    if not externalization_result.result_id:
        raise PlannerBridgeError("ThoughtExternalizationResult must declare a non-empty result_id")
    if externalization_result.status == "normalized" or externalization_result.normalized_proposal is not None:
        raise PlannerBridgeError(
            "Internal-only planner-bridge evaluation requires a non-normalized ThoughtExternalizationResult"
        )


def _validate_request(
    externalization_result: ThoughtExternalizationResult,
    request: PlannerBridgeRequest,
) -> None:
    if request.source_externalization_result_id != externalization_result.result_id:
        raise PlannerBridgeError(
            "PlannerBridgeRequest must preserve the source externalization-result id"
        )
    if request.normalized_proposal_present != (externalization_result.normalized_proposal is not None):
        raise PlannerBridgeError(
            "PlannerBridgeRequest must preserve whether the upstream normalized proposal is present"
        )


@runtime_checkable
class PlannerBridgePath(Protocol):
    def evaluate(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
        config: PlannerBridgeConfig,
    ) -> tuple[PlannerBridgeResult, NormalizedExecutionFeedback | None]:
        """Return one planner-bridge result and optional normalized execution feedback."""


@dataclass
class FirstVersionPlannerBridgePath(PlannerBridgePath):
    """Owner-private deterministic first-version bridge path."""

    def evaluate(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
        config: PlannerBridgeConfig,
    ) -> tuple[PlannerBridgeResult, NormalizedExecutionFeedback | None]:
        proposal = externalization_result.normalized_proposal
        assert proposal is not None
        behavior_name = proposal.behavior_name
        behavior_registered = bool(request.behavior_snapshot.get("registered", False))
        behavior_reviewed = bool(request.behavior_snapshot.get("reviewed", False))
        behavior_min_score = float(request.behavior_snapshot.get("minimum_score", 0.0))
        proposal_score = float(request.behavior_snapshot.get("proposal_score", 1.0))

        if not behavior_registered:
            return self._policy_rejected(request, "behavior_not_registered"), None
        if not behavior_reviewed:
            return self._policy_rejected(request, "behavior_unreviewed"), None
        if proposal_score < behavior_min_score:
            return self._policy_rejected(request, "score_below_threshold"), None
        if not proposal.preferred_op:
            return self._policy_rejected(request, "missing_requested_op"), None

        selected_channel_id = self._select_channel(request, proposal.preferred_op, proposal)
        if selected_channel_id is None:
            return self._policy_rejected(request, "no_channel_available"), None

        channel_descriptor = request.channel_descriptor_snapshot.get(selected_channel_id)
        if not isinstance(channel_descriptor, dict):
            return self._policy_rejected(request, "requested_op_unavailable"), None
        output_ops = channel_descriptor.get("output_ops", ())
        if proposal.preferred_op not in output_ops:
            return self._consistency_failed(
                request,
                proposal_id=proposal.proposal_id,
                behavior_name=behavior_name,
                selected_channel_id=selected_channel_id,
                selected_op=proposal.preferred_op,
                rejection_reason="missing_output_op",
                normalized_intensity=self._normalize_intensity(proposal.outbound_intensity, config),
            )

        # R86 enforced risk-class gate. For an op-level `unrestricted` op (reply, fs_*) this is a no-op
        # (effective risk is unrestricted, no command-policy lookup) so the path is byte-for-byte
        # unchanged. For a `governed`/`restricted` op-level op (the command op) the effective
        # per-invocation risk is the driver-projected per-command allowlist lookup; the planner owns the
        # gate, the driver owns the allowlist, and `14` owns the authorization (carried).
        gate = self._risk_class_gate(request, proposal, channel_descriptor)
        if gate is not None:
            return gate, None

        missing_input = self._missing_required_input(channel_descriptor, proposal)
        if missing_input is not None:
            return self._consistency_failed(
                request,
                proposal_id=proposal.proposal_id,
                behavior_name=behavior_name,
                selected_channel_id=selected_channel_id,
                selected_op=proposal.preferred_op,
                rejection_reason="missing_op_inputs",
                normalized_intensity=self._normalize_intensity(proposal.outbound_intensity, config),
            )

        channel_status = request.channel_status_snapshot.get(selected_channel_id)
        if not isinstance(channel_status, dict) or not channel_status.get("bound", False):
            return self._consistency_failed(
                request,
                proposal_id=proposal.proposal_id,
                behavior_name=behavior_name,
                selected_channel_id=selected_channel_id,
                selected_op=proposal.preferred_op,
                rejection_reason="missing_channel_binding",
                normalized_intensity=self._normalize_intensity(proposal.outbound_intensity, config),
            )

        normalized_intensity = self._normalize_intensity(proposal.outbound_intensity, config)
        decision = ActionDecision(
            decision_id=f"action-decision:{request.request_id}",
            proposal_id=proposal.proposal_id,
            selected_channel_id=selected_channel_id,
            selected_op=proposal.preferred_op,
            normalized_intensity=normalized_intensity,
            validated_params=proposal.params,
            execution_priority=int(request.behavior_snapshot.get("execution_priority", 1)),
            policy_trace={
                "behavior_name": behavior_name,
                "proposal_score": proposal_score,
                "minimum_score": behavior_min_score,
                "op_effect_class": self._op_class(channel_descriptor, proposal.preferred_op, "effect_class"),
                "op_risk_class": self._op_class(channel_descriptor, proposal.preferred_op, "risk_class"),
                "op_user_visible": self._op_user_visible(channel_descriptor, proposal.preferred_op),
            },
        )

        execute_now = bool(channel_status.get("execute_now", True))
        if not execute_now:
            result = PlannerBridgeResult(
                result_id=f"planner-bridge-result:{request.request_id}",
                source_request_id=request.request_id,
                status="accepted",
                action_decision=decision,
                rejection_reason=None,
                execution_consistency_failure=None,
                tick_id=request.tick_id,
            )
            return result, None

        execution_success = bool(channel_status.get("execution_success", True))
        feedback = NormalizedExecutionFeedback(
            proposal_id=proposal.proposal_id,
            decision_id=decision.decision_id,
            behavior_name=behavior_name,
            success=execution_success,
            channel_id=selected_channel_id,
            op_name=proposal.preferred_op,
            normalized_intensity=normalized_intensity,
            result_details={
                "transport_status": "ok" if execution_success else "failed",
            },
            state_effects={
                "visible_action_attempted": True,
            },
        )
        result = PlannerBridgeResult(
            result_id=f"planner-bridge-result:{request.request_id}",
            source_request_id=request.request_id,
            status="executed" if execution_success else "execution_failed",
            action_decision=decision,
            rejection_reason=None,
            execution_consistency_failure=None,
            tick_id=request.tick_id,
        )
        return result, feedback

    def _policy_rejected(
        self,
        request: PlannerBridgeRequest,
        reason: str,
        pending_governed_action: dict | None = None,
    ) -> PlannerBridgeResult:
        return PlannerBridgeResult(
            result_id=f"planner-bridge-result:{request.request_id}",
            source_request_id=request.request_id,
            status="policy_rejected",
            action_decision=None,
            rejection_reason=reason,
            execution_consistency_failure=None,
            tick_id=request.tick_id,
            pending_governed_action=pending_governed_action,
        )

    def _risk_class_gate(
        self,
        request: PlannerBridgeRequest,
        proposal,
        channel_descriptor: dict,
    ) -> PlannerBridgeResult | None:
        """Owner: planner-bridge (R86 enforced risk-class gate).

        Return a fail-closed `policy_rejected` result, or `None` to proceed. For an op-level
        `unrestricted` op this is a no-op (byte-for-byte unchanged). For a `governed`/`restricted`
        op-level op (the command op) the effective per-invocation risk is the driver-projected
        per-command allowlist lookup of `[command, *args]`: `unrestricted` proceeds, `restricted`
        (incl. no match) is `risk_class_restricted`, `governed` consults the carried `14` authorization
        (`governance_approval` keyed by the stable action key) and proceeds only when authorized, else
        `governance_denied` (carried denial) or `governance_required` (no carried decision, plus the
        pending action descriptor for `14` to authorize next).
        """

        op_risk = self._op_class(channel_descriptor, proposal.preferred_op, "risk_class")
        if op_risk is None or op_risk == "unrestricted":
            return None
        command = str(proposal.params.get("command", ""))
        raw_args = proposal.params.get("args", ())
        args = tuple(str(a) for a in raw_args) if isinstance(raw_args, (list, tuple)) else ()
        effective = self._match_command_policy(channel_descriptor.get("command_policy"), command, args)
        if effective == "unrestricted":
            return None
        if effective == "restricted":
            return self._policy_rejected(request, "risk_class_restricted")
        action_key = self._action_authorization_key(proposal.preferred_op, command, args)
        auth = request.governance_approval.get(action_key)
        if isinstance(auth, Mapping) and bool(auth.get("authorized", False)):
            return None
        if isinstance(auth, Mapping):
            return self._policy_rejected(request, "governance_denied")
        pending = {
            "action_authorization_key": action_key,
            "op": proposal.preferred_op,
            "command": command,
            "args": args,
        }
        return self._policy_rejected(request, "governance_required", pending_governed_action=pending)

    @staticmethod
    def _match_command_policy(command_policy: object, command: str, args: tuple[str, ...]) -> str:
        """Owner: planner-bridge. Return the effective per-invocation risk from the driver-projected
        per-command allowlist (argv-prefix match; no match -> `restricted`). Hardcodes no command name.
        """

        argv = (command, *args)
        if not isinstance(command_policy, (list, tuple)):
            return "restricted"
        for rule in command_policy:
            if not isinstance(rule, Mapping):
                continue
            prefix = tuple(str(token) for token in rule.get("argv_prefix", ()))
            if prefix and len(prefix) <= len(argv) and tuple(argv[: len(prefix)]) == prefix:
                risk = rule.get("risk_class")
                return risk if isinstance(risk, str) else "restricted"
        return "restricted"

    @staticmethod
    def _action_authorization_key(op: str, command: str, args: tuple[str, ...]) -> str:
        """Owner: planner-bridge. Deterministic stable key for one action (op + command + args),
        independent of tick-specific ids, so a re-proposed governed action matches its carried `14`
        authorization across ticks.
        """

        import hashlib

        payload = "|".join((op, command, *args))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _consistency_failed(
        self,
        request: PlannerBridgeRequest,
        proposal_id: str,
        behavior_name: str,
        selected_channel_id: str,
        selected_op: str,
        rejection_reason: str,
        normalized_intensity: float,
    ) -> tuple[PlannerBridgeResult, None]:
        decision = ActionDecision(
            decision_id=f"action-decision:{request.request_id}",
            proposal_id=proposal_id,
            selected_channel_id=selected_channel_id,
            selected_op=selected_op,
            normalized_intensity=normalized_intensity,
            validated_params={},
            execution_priority=int(request.behavior_snapshot.get("execution_priority", 1)),
            policy_trace={"consistency_check": rejection_reason},
        )
        failure = ExecutionConsistencyFailure(
            decision_id=decision.decision_id,
            proposal_id=proposal_id,
            behavior_name=behavior_name,
            rejection_reason=rejection_reason,
            selected_channel_id=selected_channel_id,
            selected_op=selected_op,
            policy_trace=decision.policy_trace,
        )
        result = PlannerBridgeResult(
            result_id=f"planner-bridge-result:{request.request_id}",
            source_request_id=request.request_id,
            status="execution_consistency_failed",
            action_decision=decision,
            rejection_reason=rejection_reason,
            execution_consistency_failure=failure,
            tick_id=request.tick_id,
        )
        return result, None

    def _missing_required_input(self, channel_descriptor: dict, proposal) -> str | None:
        """Owner: planner-bridge.

        Return the first required param key the proposal is missing for the selected op, validated
        generically against the driver's declared per-op spec (`op_specs[op].required_params`). When the
        op declares no spec (legacy shim descriptors), fall back to the prior reply-op `outbound_text`
        check so the default assembly is byte-for-byte unchanged. Returns `None` when inputs are complete.
        """

        op_specs = channel_descriptor.get("op_specs")
        spec = op_specs.get(proposal.preferred_op) if isinstance(op_specs, dict) else None
        if isinstance(spec, dict):
            for key in spec.get("required_params", ()):  # generic, driver-declared
                if key not in proposal.params:
                    return key
            return None
        # Legacy fallback: no declared spec for this op (shim descriptors).
        if proposal.preferred_op in {"reply_message", "send_message", "speak_text"} and "outbound_text" not in proposal.params:
            return "outbound_text"
        return None

    @staticmethod
    def _op_class(channel_descriptor: dict, op_name: str, key: str) -> str | None:
        """Owner: planner-bridge. Read the op's declared effect/risk class for the policy trace (R85).

        Read-through only: R85 records the class for observability; the `risk_class` becomes the R86
        enforced gate. Returns `None` when the op declares no spec.
        """

        op_specs = channel_descriptor.get("op_specs")
        spec = op_specs.get(op_name) if isinstance(op_specs, dict) else None
        if isinstance(spec, dict):
            value = spec.get(key)
            return value if isinstance(value, str) else None
        return None

    @staticmethod
    def _op_user_visible(channel_descriptor: dict, op_name: str) -> bool | None:
        """Owner: planner-bridge. Read the op's declared `user_visible` flag for the policy trace (R87).

        Recorded so the `17` evaluation owner can distinguish a user-visible relay reply (no
        `tool_result` reafference expected) from a non-user-visible effector op (produces one), for the
        real-delivery corroboration. Returns `None` when the op declares no spec.
        """

        op_specs = channel_descriptor.get("op_specs")
        spec = op_specs.get(op_name) if isinstance(op_specs, dict) else None
        if isinstance(spec, dict):
            value = spec.get("user_visible")
            return value if isinstance(value, bool) else None
        return None

    def _select_channel(
        self,
        request: PlannerBridgeRequest,
        requested_op: str,
        proposal,
    ) -> str | None:
        """Owner: planner-bridge (R93 Phase 2 priority rewrite).

        Select the channel for an accepted proposal, honoring a target_user -> preferred ->
        iteration-order priority. This is the same eligible-set test the R85 iteration-order
        path used, plus the new `bound_user_ids` user-binding filter (read off the
        composition-projected descriptor snapshot; the driver declares its `bound_user_ids`
        on its `ChannelOpSpec` and composition threads it through `op_specs[op]`).

        Priority:
            1. Filter to candidates whose `supported_ops` includes the requested op and whose
               status is `available`.
            2. If the proposal params carries a non-empty `target_user_id`:
               a. Filter to candidates whose `op_specs[op].bound_user_ids` either contains
                  that user OR is the wildcard (empty tuple).
               b. If the user-serving filter is non-empty: prefer candidates also in
                  `proposal.preferred_channels` (intersection); if any, return the first.
                  Otherwise return the first candidate in iteration order.
               c. If the user-serving filter is empty: fall through to step 3 (do not
                  reject the proposal; a wildcard driver may still be the right target).
            3. From the unfiltered candidate set: prefer candidates also in
               `proposal.preferred_channels`. If any, return the first. Otherwise return the
               first in iteration order.

        Notes:
            Preserves the R85 iteration-order fallback for the case where neither
            `target_user_id` nor `preferred_channels` are set. The legacy entry point at the
            top of `evaluate` still calls this through the same `requested_op` argument, so
            callers outside this path are unchanged.
        """

        descriptors = request.channel_descriptor_snapshot
        statuses = request.channel_status_snapshot

        def _is_candidate(channel_id: str) -> bool:
            descriptor = descriptors.get(channel_id)
            if not isinstance(descriptor, dict):
                return False
            supported_ops = descriptor.get("supported_ops", ())
            if requested_op not in supported_ops:
                return False
            status = statuses.get(channel_id)
            if not isinstance(status, dict) or not status.get("available", False):
                return False
            return True

        candidates: list[str] = [cid for cid in descriptors if _is_candidate(cid)]
        if not candidates:
            return None

        # Pull target_user_id and preferred_channels once. Both are optional signals; the
        # priority chain treats them as non-authoritative hints layered on top of the
        # eligible-set filter. The proposal is passed in by the caller (it lives on the
        # upstream `externalization_result`, not on the request snapshot).
        target_user = ""
        preferred: tuple[str, ...] = ()
        if proposal is not None:
            if isinstance(getattr(proposal, "params", None), Mapping):
                raw_target = proposal.params.get("target_user_id", "")
                if isinstance(raw_target, str):
                    target_user = raw_target.strip()
            raw_preferred = getattr(proposal, "preferred_channels", ())
            if isinstance(raw_preferred, (tuple, list)):
                preferred = tuple(raw_preferred)

        def _serves_user(channel_id: str) -> bool:
            if not target_user:
                return True
            descriptor = descriptors.get(channel_id, {})
            op_specs = descriptor.get("op_specs", {})
            spec = op_specs.get(requested_op) if isinstance(op_specs, dict) else None
            if not isinstance(spec, dict):
                # An op with no declared spec is treated as a wildcard (it predates the R85
                # spec contract and the R93 Phase 2 user-binding filter is best-effort).
                return True
            bound = spec.get("bound_user_ids", ())
            if not bound:
                return True  # wildcard
            return target_user in bound

        # Step 2: target_user filter (fail-soft: empty filter falls through).
        if target_user:
            user_serving = [cid for cid in candidates if _serves_user(cid)]
            if user_serving:
                if preferred:
                    intersection = [cid for cid in user_serving if cid in preferred]
                    if intersection:
                        return intersection[0]
                return user_serving[0]

        # Step 3: preferred_channels hint (from the unfiltered candidate set).
        if preferred:
            intersection = [cid for cid in candidates if cid in preferred]
            if intersection:
                return intersection[0]

        return candidates[0]

    def _normalize_intensity(self, intensity: float, config: PlannerBridgeConfig) -> float:
        return max(config.legal_min_intensity, min(config.legal_max_intensity, intensity))


@dataclass
class PlannerBridgeEngine(PlannerBridgeAPI):
    """Evaluate normalized externalization proposals into formal bridge outcomes."""

    config: PlannerBridgeConfig
    bridge_path: PlannerBridgePath | None

    def evaluate_proposal(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> tuple[PlannerBridgeResult, NormalizedExecutionFeedback | None]:
        _validate_externalization_result(externalization_result)
        _validate_request(externalization_result, request)
        if self.bridge_path is None:
            raise PlannerBridgeError("Planner bridge requires an explicit bridge capability")
        result, feedback = self.bridge_path.evaluate(externalization_result, request, self.config)
        if result.source_request_id != request.request_id:
            raise PlannerBridgeError("PlannerBridgeResult must preserve the source request id")
        return result, feedback

    def evaluate_internal_only(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> PlannerBridgeResult:
        """Produce the explicit internal-only (`no_actionable_proposal`) bridge result.

        This is a deterministic owner outcome with no policy path: there is no proposal to
        evaluate, so there is nothing for the bridge path to decide. The owner records the
        explicit absence of an action, preserving request provenance.
        """

        _validate_internal_only_externalization_result(externalization_result)
        _validate_request(externalization_result, request)
        if request.normalized_proposal_present:
            raise PlannerBridgeError(
                "Internal-only planner-bridge evaluation requires normalized_proposal_present to be False"
            )
        return PlannerBridgeResult(
            result_id=f"planner-bridge-result:{request.request_id}",
            source_request_id=request.request_id,
            status="no_actionable_proposal",
            action_decision=None,
            rejection_reason=None,
            execution_consistency_failure=None,
            tick_id=request.tick_id,
        )

    def build_evaluate_op(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> EvaluatePlannerBridgeOp:
        _validate_externalization_result(externalization_result)
        _validate_request(externalization_result, request)
        return EvaluatePlannerBridgeOp(
            op_name="evaluate_planner_bridge",
            owner="planner_executor_feedback_bridge",
            request_id=request.request_id,
            externalization_result_id=externalization_result.result_id,
            normalized_proposal_present=request.normalized_proposal_present,
        )

    def build_evaluate_op_internal_only(
        self,
        externalization_result: ThoughtExternalizationResult,
        request: PlannerBridgeRequest,
    ) -> EvaluatePlannerBridgeOp:
        """Return the request op describing an internal-only planner-bridge evaluation."""

        _validate_internal_only_externalization_result(externalization_result)
        _validate_request(externalization_result, request)
        return EvaluatePlannerBridgeOp(
            op_name="evaluate_planner_bridge_internal_only",
            owner="planner_executor_feedback_bridge",
            request_id=request.request_id,
            externalization_result_id=externalization_result.result_id,
            normalized_proposal_present=request.normalized_proposal_present,
        )

    def build_publish_decision_op(
        self,
        decision: ActionDecision,
    ) -> PublishActionDecisionOp:
        return PublishActionDecisionOp(
            op_name="publish_action_decision",
            owner="planner_executor_feedback_bridge",
            decision_id=decision.decision_id,
            proposal_id=decision.proposal_id,
            selected_channel_id=decision.selected_channel_id,
            selected_op=decision.selected_op,
        )

    def build_publish_rejection_op(
        self,
        result: PlannerBridgeResult,
    ) -> PublishPlannerBridgeRejectionOp:
        if result.status not in {"policy_rejected", "execution_consistency_failed"} or result.rejection_reason is None:
            raise PlannerBridgeError(
                "PublishPlannerBridgeRejectionOp requires a rejected or consistency-failed PlannerBridgeResult"
            )
        return PublishPlannerBridgeRejectionOp(
            op_name="publish_planner_bridge_rejection",
            owner="planner_executor_feedback_bridge",
            result_id=result.result_id,
            status=result.status,
            rejection_reason=result.rejection_reason,
        )

    def build_publish_execution_feedback_op(
        self,
        feedback: NormalizedExecutionFeedback,
    ) -> PublishExecutionFeedbackOp:
        return PublishExecutionFeedbackOp(
            op_name="publish_execution_feedback",
            owner="planner_executor_feedback_bridge",
            decision_id=feedback.decision_id,
            proposal_id=feedback.proposal_id,
            success=feedback.success,
        )
