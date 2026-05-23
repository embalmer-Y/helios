"""Policy evaluation and execution planning for structured Helios actions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from .action_models import ActionDecision, ActionProposal, BehaviorSpec
from .channel import ChannelDescriptor, ChannelOpDescriptor, ChannelStatus


@dataclass
class PolicyViolation:
    code: str
    message: str
    severity: str = "error"
    details: Dict[str, object] = field(default_factory=dict)


@dataclass
class PolicyEvaluation:
    accepted: bool
    resolved_score: float
    allowed_channels: List[str] = field(default_factory=list)
    allowed_modalities: List[str] = field(default_factory=list)
    violations: List[PolicyViolation] = field(default_factory=list)
    trace: Dict[str, object] = field(default_factory=dict)


class PolicyEvaluator:
    """Validate an action proposal against behavior specs, channels, and runtime constraints."""

    def __init__(
        self,
        *,
        min_score: float = 0.15,
        require_connected_channel: bool = True,
        allowed_behavior_statuses: Optional[Iterable[str]] = None,
        allowed_review_states: Optional[Iterable[str]] = None,
    ):
        self._min_score = min_score
        self._require_connected_channel = require_connected_channel
        self._allowed_behavior_statuses = set(allowed_behavior_statuses or {"active"})
        self._allowed_review_states = set(allowed_review_states or {"approved"})

    def evaluate(
        self,
        proposal: ActionProposal,
        behavior_spec: BehaviorSpec,
        channel_descriptors: Mapping[str, ChannelDescriptor],
        channel_statuses: Optional[Mapping[str, ChannelStatus]] = None,
    ) -> PolicyEvaluation:
        violations: List[PolicyViolation] = []
        score = self._resolve_score(proposal)
        candidate_channels = self._resolve_candidate_channels(proposal, behavior_spec, channel_descriptors)
        allowed_modalities = self._resolve_modalities(proposal, behavior_spec)
        trace: Dict[str, object] = {
            "resolved_score": score,
            "candidate_channels": list(candidate_channels),
            "allowed_modalities": list(allowed_modalities),
        }

        internal_only = bool(proposal.constraints.get("internal_only", False))
        trace["internal_only"] = internal_only

        if internal_only and behavior_spec.execution_mode != "internal":
            violations.append(
                PolicyViolation(
                    code="internal_only_constraint",
                    message="Preconscious internal-only proposals cannot bind to external channel behaviors.",
                    details={
                        "source_type": proposal.source_type,
                        "execution_mode": behavior_spec.execution_mode,
                        "behavior_name": behavior_spec.name,
                    },
                )
            )

        if behavior_spec.status not in self._allowed_behavior_statuses:
            violations.append(
                PolicyViolation(
                    code="behavior_inactive",
                    message=f"Behavior {behavior_spec.name} is not active.",
                    details={"status": behavior_spec.status},
                )
            )

        if behavior_spec.review_state not in self._allowed_review_states:
            violations.append(
                PolicyViolation(
                    code="behavior_unreviewed",
                    message=f"Behavior {behavior_spec.name} is not approved for execution.",
                    details={"review_state": behavior_spec.review_state},
                )
            )

        if score < self._min_score:
            violations.append(
                PolicyViolation(
                    code="score_below_threshold",
                    message="Proposal score is below the execution threshold.",
                    details={"score": score, "min_score": self._min_score},
                )
            )

        required_capabilities = set(behavior_spec.required_capabilities)
        required_capabilities.update(proposal.constraints.get("required_capabilities", []))
        if required_capabilities:
            trace["required_capabilities"] = sorted(required_capabilities)

        allowed_channels: List[str] = []
        for channel_id in candidate_channels:
            descriptor = channel_descriptors.get(channel_id)
            if descriptor is None:
                continue
            if required_capabilities.difference(descriptor.capabilities):
                continue
            if self._require_connected_channel and channel_statuses is not None:
                status = channel_statuses.get(channel_id, ChannelStatus.ERROR)
                if status != ChannelStatus.CONNECTED:
                    continue
            allowed_channels.append(channel_id)

        if behavior_spec.execution_mode == "channel" and not allowed_channels:
            violations.append(
                PolicyViolation(
                    code="no_channel_available",
                    message="No channel satisfies proposal and behavior constraints.",
                    details={"candidate_channels": list(candidate_channels)},
                )
            )

        if proposal.constraints.get("max_cost") is not None:
            max_cost = float(proposal.constraints["max_cost"])
            estimated_cost = float(behavior_spec.cost_policy.get("cost", 0.0))
            trace["estimated_cost"] = estimated_cost
            if estimated_cost > max_cost:
                violations.append(
                    PolicyViolation(
                        code="cost_exceeds_budget",
                        message="Behavior cost exceeds the proposal budget.",
                        details={"cost": estimated_cost, "max_cost": max_cost},
                    )
                )

        return PolicyEvaluation(
            accepted=not any(v.severity == "error" for v in violations),
            resolved_score=score,
            allowed_channels=allowed_channels,
            allowed_modalities=allowed_modalities,
            violations=violations,
            trace=trace,
        )

    @staticmethod
    def _resolve_score(proposal: ActionProposal) -> float:
        if not proposal.score_bundle:
            return 0.0
        if "final" in proposal.score_bundle:
            return float(proposal.score_bundle["final"])
        if "priority" in proposal.score_bundle:
            return float(proposal.score_bundle["priority"])
        return max(float(value) for value in proposal.score_bundle.values())

    @staticmethod
    def _resolve_candidate_channels(
        proposal: ActionProposal,
        behavior_spec: BehaviorSpec,
        channel_descriptors: Mapping[str, ChannelDescriptor],
    ) -> List[str]:
        blocked = set(proposal.constraints.get("blocked_channels", []))
        requested = list(proposal.candidate_channels)
        if requested:
            return [channel_id for channel_id in requested if channel_id not in blocked]

        if behavior_spec.allowed_channel_ids:
            return [channel_id for channel_id in behavior_spec.allowed_channel_ids if channel_id not in blocked]

        if behavior_spec.execution_mode == "internal":
            return []

        return [channel_id for channel_id in channel_descriptors.keys() if channel_id not in blocked]

    @staticmethod
    def _resolve_modalities(proposal: ActionProposal, behavior_spec: BehaviorSpec) -> List[str]:
        if proposal.suggested_modalities:
            return list(proposal.suggested_modalities)
        if behavior_spec.supported_modalities:
            return list(behavior_spec.supported_modalities)
        if behavior_spec.execution_mode == "internal":
            return ["internal"]
        return ["text"]


class ExecutionPlanner:
    """Turn accepted action proposals into executable decisions."""

    PRIORITY_THRESHOLDS = [
        (0.8, 100),
        (0.6, 75),
        (0.4, 50),
        (0.2, 25),
        (0.0, 10),
    ]

    def __init__(self, policy_evaluator: Optional[PolicyEvaluator] = None):
        self._policy_evaluator = policy_evaluator or PolicyEvaluator()

    def plan(
        self,
        proposal: ActionProposal,
        behavior_specs: Mapping[str, BehaviorSpec] | Iterable[BehaviorSpec],
        channel_descriptors: Mapping[str, ChannelDescriptor],
        channel_statuses: Optional[Mapping[str, ChannelStatus]] = None,
    ) -> ActionDecision:
        behavior_spec = self._resolve_behavior_spec(proposal.behavior_name, behavior_specs)
        if behavior_spec is None:
            return ActionDecision(
                decision_id=f"decision::{proposal.proposal_id}",
                proposal_id=proposal.proposal_id,
                behavior_name=proposal.behavior_name,
                rejection_reason="behavior_not_registered",
                proposal_snapshot=asdict(proposal),
            )

        evaluation = self._policy_evaluator.evaluate(proposal, behavior_spec, channel_descriptors, channel_statuses)
        if not evaluation.accepted:
            return ActionDecision(
                decision_id=f"decision::{proposal.proposal_id}",
                proposal_id=proposal.proposal_id,
                behavior_name=behavior_spec.name,
                rejection_reason=self._join_violation_codes(evaluation.violations),
                cost_estimate=dict(behavior_spec.cost_policy),
                policy_trace={
                    **evaluation.trace,
                    "violations": [asdict(item) for item in evaluation.violations],
                },
                proposal_snapshot=asdict(proposal),
                behavior_snapshot=asdict(behavior_spec),
            )

        selected_channel_id = ""
        selected_op = "internal_execute"
        if behavior_spec.execution_mode != "internal":
            selected_channel_id = self._select_channel(proposal, behavior_spec, evaluation.allowed_channels, channel_descriptors)
            selected_op = self._select_output_op(channel_descriptors.get(selected_channel_id))

        score = evaluation.resolved_score
        return ActionDecision(
            decision_id=f"decision::{proposal.proposal_id}",
            proposal_id=proposal.proposal_id,
            behavior_name=behavior_spec.name,
            selected_channel_id=selected_channel_id,
            selected_op=selected_op,
            execution_priority=self._score_to_priority(score),
            validated_params=self._validate_params(proposal.parameters, behavior_spec),
            cost_estimate=dict(behavior_spec.cost_policy),
            policy_trace=evaluation.trace,
            selected_modality=evaluation.allowed_modalities[0] if evaluation.allowed_modalities else "",
            proposal_snapshot=asdict(proposal),
            behavior_snapshot=asdict(behavior_spec),
        )

    @staticmethod
    def _resolve_behavior_spec(
        behavior_name: str,
        behavior_specs: Mapping[str, BehaviorSpec] | Iterable[BehaviorSpec],
    ) -> Optional[BehaviorSpec]:
        if isinstance(behavior_specs, Mapping):
            if behavior_name in behavior_specs:
                return behavior_specs[behavior_name]
            for spec in behavior_specs.values():
                if spec.matches_behavior_name(behavior_name):
                    return spec
            return None

        for spec in behavior_specs:
            if spec.matches_behavior_name(behavior_name):
                return spec
        return None

    @staticmethod
    def _join_violation_codes(violations: List[PolicyViolation]) -> str:
        return ",".join(item.code for item in violations) or "rejected"

    @staticmethod
    def _select_channel(
        proposal: ActionProposal,
        behavior_spec: BehaviorSpec,
        allowed_channels: List[str],
        channel_descriptors: Mapping[str, ChannelDescriptor],
    ) -> str:
        if not allowed_channels:
            return ""

        preferred = list(proposal.candidate_channels)
        if not preferred:
            preferred = list(behavior_spec.allowed_channel_ids)

        for channel_id in preferred:
            if channel_id in allowed_channels:
                return channel_id

        ranked = sorted(
            allowed_channels,
            key=lambda channel_id: (
                0 if channel_id in proposal.candidate_channels else 1,
                0 if channel_id in behavior_spec.allowed_channel_ids else 1,
                0 if "send" in [op.name for op in channel_descriptors[channel_id].supported_ops] else 1,
                channel_id,
            ),
        )
        return ranked[0]

    @staticmethod
    def _select_output_op(descriptor: Optional[ChannelDescriptor]) -> str:
        if descriptor is None:
            return "send"
        for op in descriptor.supported_ops:
            if op.direction in {"output", "bidirectional"}:
                return op.name
        return "send"

    @staticmethod
    def _validate_params(parameters: Dict[str, object], behavior_spec: BehaviorSpec) -> Dict[str, object]:
        if not behavior_spec.parameter_schema:
            return dict(parameters)

        validated: Dict[str, object] = {}
        for name, schema in behavior_spec.parameter_schema.items():
            schema_dict = schema if isinstance(schema, dict) else {}
            required = bool(schema_dict.get("required", False))
            if name in parameters:
                validated[name] = parameters[name]
                continue
            if "default" in schema_dict:
                validated[name] = schema_dict["default"]
                continue
            if required:
                raise ValueError(f"Missing required parameter: {name}")

        for name, value in parameters.items():
            validated.setdefault(name, value)
        return validated

    @classmethod
    def _score_to_priority(cls, score: float) -> int:
        for threshold, priority in cls.PRIORITY_THRESHOLDS:
            if score >= threshold:
                return priority
        return 10