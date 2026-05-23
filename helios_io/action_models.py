"""Structured action proposal and execution decision models for Helios."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


@dataclass
class ActionProposal:
    proposal_id: str
    source_type: str
    source_module: str
    intent_type: str
    behavior_name: str
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
