"""Structured action proposal and execution decision models for Helios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Mapping


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class ThoughtActionProposal:
    origin_thought_id: str
    behavior_name: str
    preferred_op: str
    scope: Literal["internal", "external"] = "internal"
    thought_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    channel_constraints: Dict[str, Any] = field(default_factory=dict)
    outbound_intensity: float = 0.0
    score: float = 0.0
    reason_trace: List[str] = field(default_factory=list)
    governance_hints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "origin_thought_id": self.origin_thought_id,
            "thought_type": self.thought_type,
            "scope": self.scope,
            "behavior_name": self.behavior_name,
            "preferred_op": self.preferred_op,
            "params": dict(self.params),
            "channel_constraints": dict(self.channel_constraints),
            "outbound_intensity": _clamp_unit(self.outbound_intensity),
            "score": _clamp_unit(self.score),
            "reason_trace": [str(item) for item in list(self.reason_trace) if str(item)],
            "governance_hints": dict(self.governance_hints),
        }

    @classmethod
    def from_payload(cls, payload: "ThoughtActionProposal | Mapping[str, Any] | None") -> "ThoughtActionProposal | None":
        if payload is None:
            return None
        if isinstance(payload, cls):
            return payload
        data = dict(payload)
        origin_thought_id = str(data.get("origin_thought_id", "") or "").strip()
        behavior_name = str(data.get("behavior_name", "") or "").strip()
        preferred_op = str(data.get("preferred_op", "") or "").strip()
        if not origin_thought_id or not behavior_name or not preferred_op:
            return None
        return cls(
            origin_thought_id=origin_thought_id,
            thought_type=str(data.get("thought_type", "") or "").strip(),
            scope="external" if str(data.get("scope", "internal") or "internal").strip() == "external" else "internal",
            behavior_name=behavior_name,
            preferred_op=preferred_op,
            params=dict(data.get("params", {}) or {}),
            channel_constraints=dict(data.get("channel_constraints", {}) or {}),
            outbound_intensity=_clamp_unit(data.get("outbound_intensity", 0.0) or 0.0),
            score=_clamp_unit(data.get("score", 0.0) or 0.0),
            reason_trace=[str(item) for item in list(data.get("reason_trace", []) or []) if str(item)],
            governance_hints=dict(data.get("governance_hints", {}) or {}),
        )


@dataclass
class ActionProposal:
    proposal_id: str
    source_type: str
    source_module: str
    intent_type: str
    behavior_name: str
    origin_type: str = ""
    origin_id: str = ""
    op_name: str = ""
    op_params: Dict[str, Any] = field(default_factory=dict)
    outbound_intensity: float = 0.0
    reason_summary: str = ""
    score_bundle: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    suggested_modalities: List[str] = field(default_factory=list)
    candidate_channels: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)
    created_at_tick: int = 0
    created_at_ts: float = 0.0


@dataclass
class BehaviorSpec:
    behavior_id: str
    name: str
    display_name: str
    description: str
    category: str
    status: str = "active"
    version: str = "1.0"
    execution_mode: Literal["channel", "internal", "hybrid"] = "channel"
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    applicable_context: Dict[str, Any] = field(default_factory=dict)
    cooldown_policy: Dict[str, Any] = field(default_factory=dict)
    cost_policy: Dict[str, float] = field(default_factory=dict)
    allowed_channel_ids: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    supported_modalities: List[str] = field(default_factory=list)
    source_kind: str = "bootstrap"
    source_detail: Dict[str, Any] = field(default_factory=dict)
    review_state: str = "approved"

    def matches_behavior_name(self, behavior_name: str) -> bool:
        return behavior_name in {self.name, self.behavior_id, self.display_name}


@dataclass
class ActionDecision:
    decision_id: str
    proposal_id: str
    behavior_name: str
    selected_channel_id: str = ""
    selected_op: str = ""
    normalized_intensity: float = 0.0
    execution_priority: int = 0
    validated_params: Dict[str, Any] = field(default_factory=dict)
    rejection_reason: str = ""
    cost_estimate: Dict[str, float] = field(default_factory=dict)
    policy_trace: Dict[str, Any] = field(default_factory=dict)
    selected_modality: str = ""
    proposal_snapshot: Dict[str, Any] = field(default_factory=dict)
    behavior_snapshot: Dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return not self.rejection_reason


@dataclass
class ExecutionFeedback:
    proposal_id: str
    decision_id: str
    behavior_name: str
    success: bool
    channel_id: str = ""
    op_name: str = ""
    result_details: Dict[str, Any] = field(default_factory=dict)
    state_effects: Dict[str, Any] = field(default_factory=dict)
    observed_at_tick: int = 0
    observed_at_ts: float = 0.0
