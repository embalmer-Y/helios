"""Structured records persisted by the behavior registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BehaviorSourceRecord:
    source_id: str
    behavior_id: str
    source_kind: str
    source_uri: str = ""
    source_summary: str = ""
    captured_at: float = 0.0


@dataclass(frozen=True)
class BehaviorExecutionRecord:
    execution_id: str
    behavior_id: str
    proposal_id: str
    decision_id: str
    channel_id: str = ""
    op_name: str = ""
    success: bool = False
    result_details: dict[str, Any] = field(default_factory=dict)
    feedback_details: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


@dataclass(frozen=True)
class FeedbackEventRecord:
    event_id: str
    event_kind: str
    source_path: str
    proposal_id: str = ""
    decision_id: str = ""
    behavior_id: str = ""
    channel_id: str = ""
    memory_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0


__all__ = ["BehaviorExecutionRecord", "BehaviorSourceRecord", "FeedbackEventRecord"]