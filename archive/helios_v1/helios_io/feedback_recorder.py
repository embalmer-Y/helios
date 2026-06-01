"""Unified recorder for structured execution, channel, user, and memory feedback."""

from __future__ import annotations

import time
from typing import Any, Mapping
from uuid import uuid4

from behavior_registry import BehaviorExecutionRecord, FeedbackEventRecord, RuntimeBehaviorCatalog

from .action_models import ExecutionFeedback
from .limb import BehaviorCommand


class FeedbackRecorder:
    """Convert runtime events into structured feedback and persist them."""

    def __init__(self, behavior_catalog: RuntimeBehaviorCatalog):
        self._behavior_catalog = behavior_catalog

    @staticmethod
    def _normalize_trace_payload(
        *,
        provenance: Mapping[str, Any] | None = None,
        op_name: str = "",
        channel_id: str = "",
        normalized_intensity: float = 0.0,
    ) -> dict[str, Any]:
        provenance_dict = dict(provenance or {})
        nested_provenance = dict(provenance_dict.get("provenance", {}) or {})
        return {
            "origin_id": str(provenance_dict.get("origin_id", nested_provenance.get("origin_id", "")) or ""),
            "origin_type": str(provenance_dict.get("origin_type", nested_provenance.get("origin_type", "")) or ""),
            "owner_path": str(provenance_dict.get("owner_path", nested_provenance.get("owner_path", "")) or ""),
            "source_type": str(provenance_dict.get("source_type", nested_provenance.get("source_type", "")) or ""),
            "session_kind": str(provenance_dict.get("session_kind", nested_provenance.get("session_kind", "")) or ""),
            "dominant_disposition": str(
                provenance_dict.get("dominant_disposition", nested_provenance.get("dominant_disposition", "")) or ""
            ),
            "trigger_sources": [
                str(item)
                for item in list(provenance_dict.get("trigger_sources", nested_provenance.get("trigger_sources", [])) or [])
                if str(item)
            ],
            "op_name": op_name,
            "requested_op": str(provenance_dict.get("requested_op", provenance_dict.get("op_name", nested_provenance.get("requested_op", op_name))) or op_name or ""),
            "candidate_channels": [str(item) for item in list(provenance_dict.get("candidate_channels", [] ) or []) if str(item)],
            "selected_channel_id": channel_id,
            "selected_op": op_name,
            "normalized_intensity": float(normalized_intensity),
            "provenance": provenance_dict,
        }

    def record_command_result(
        self,
        command: BehaviorCommand,
        result: Mapping[str, Any],
        *,
        observed_at_tick: int = 0,
        observed_at_ts: float | None = None,
    ) -> ExecutionFeedback:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        result_details = dict(result)
        state_effects = dict(result_details.pop("state_effects", {}) or {})
        feedback = ExecutionFeedback(
            proposal_id=command.proposal_id,
            decision_id=command.decision_id,
            behavior_name=command.action,
            success=bool(result.get("success", False)),
            channel_id=command.channel_id,
            op_name=command.op_name,
            result_details=result_details,
            state_effects=state_effects,
            observed_at_tick=int(observed_at_tick),
            observed_at_ts=observed_ts,
        )

        behavior_id = command.behavior_id or str(command.behavior_snapshot.get("behavior_id", "") or "")
        if not behavior_id:
            spec = self._behavior_catalog.get_behavior(command.action, status="", review_state="")
            behavior_id = spec.behavior_id if spec is not None else ""

        if behavior_id:
            self._behavior_catalog.registry.record_execution_feedback(
                BehaviorExecutionRecord(
                    execution_id=f"execution::{command.decision_id or uuid4().hex}",
                    behavior_id=behavior_id,
                    proposal_id=command.proposal_id,
                    decision_id=command.decision_id,
                    channel_id=command.channel_id,
                    op_name=command.op_name,
                    success=feedback.success,
                    result_details=dict(feedback.result_details),
                    feedback_details={
                        "state_effects": dict(feedback.state_effects),
                        "modality": command.modality,
                        "normalized_intensity": command.normalized_intensity,
                        "owner_path": self._normalize_trace_payload(
                            provenance=command.provenance,
                            op_name=command.op_name,
                            channel_id=command.channel_id,
                            normalized_intensity=command.normalized_intensity,
                        )["owner_path"],
                        "provenance": dict(command.provenance),
                        "policy_trace": dict(command.policy_trace),
                    },
                    created_at=observed_ts,
                )
            )

        self._behavior_catalog.registry.record_feedback_event(
            FeedbackEventRecord(
                event_id=f"feedback::execution::{command.decision_id or uuid4().hex}",
                event_kind="execution_result",
                source_path=str(command.provenance.get("source_type", "execution")),
                proposal_id=command.proposal_id,
                decision_id=command.decision_id,
                behavior_id=behavior_id,
                channel_id=command.channel_id,
                payload={
                    "behavior_name": command.action,
                    "success": feedback.success,
                    "result_details": dict(feedback.result_details),
                    "state_effects": dict(feedback.state_effects),
                    "policy_trace": dict(command.policy_trace),
                    **self._normalize_trace_payload(
                        provenance=command.provenance,
                        op_name=command.op_name,
                        channel_id=command.channel_id,
                        normalized_intensity=command.normalized_intensity,
                    ),
                },
                created_at=observed_ts,
            )
        )

        return feedback

    def record_user_feedback(
        self,
        *,
        source_path: str,
        channel_id: str,
        user_id: str,
        text: str,
        sec_result: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::user::{uuid4().hex}",
            event_kind="user_feedback",
            source_path=source_path,
            channel_id=channel_id,
            payload={
                "user_id": user_id,
                "text": text,
                "sec_result": dict(sec_result or {}),
                "metadata": dict(metadata or {}),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record

    def record_channel_receipt(
        self,
        *,
        source_path: str,
        channel_id: str,
        action_name: str,
        success: bool,
        proposal_id: str = "",
        decision_id: str = "",
        behavior_id: str = "",
        op_name: str = "",
        normalized_intensity: float = 0.0,
        provenance: Mapping[str, Any] | None = None,
        original_text: str = "",
        rendered_text: str = "",
        expression_profile: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::channel::{decision_id or uuid4().hex}",
            event_kind="channel_receipt",
            source_path=source_path,
            proposal_id=proposal_id,
            decision_id=decision_id,
            behavior_id=behavior_id,
            channel_id=channel_id,
            payload={
                "action_name": action_name,
                "success": bool(success),
                "original_text": str(original_text or ""),
                "rendered_text": str(rendered_text or ""),
                "expression_profile": dict(expression_profile or {}),
                "metadata": dict(metadata or {}),
                **self._normalize_trace_payload(
                    provenance=provenance,
                    op_name=op_name,
                    channel_id=channel_id,
                    normalized_intensity=normalized_intensity,
                ),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record

    def record_policy_rejection(
        self,
        *,
        source_path: str,
        proposal_id: str,
        behavior_name: str,
        rejection_reason: str,
        decision_id: str = "",
        behavior_id: str = "",
        channel_id: str = "",
        op_name: str = "",
        normalized_intensity: float = 0.0,
        provenance: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::rejection::{decision_id or proposal_id or uuid4().hex}",
            event_kind="policy_rejection",
            source_path=source_path,
            proposal_id=proposal_id,
            decision_id=decision_id,
            behavior_id=behavior_id,
            channel_id=channel_id,
            payload={
                "behavior_name": behavior_name,
                "rejection_reason": rejection_reason,
                **self._normalize_trace_payload(
                    provenance=provenance,
                    op_name=op_name,
                    channel_id=channel_id,
                    normalized_intensity=normalized_intensity,
                ),
                **dict(payload or {}),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record

    def record_memory_write(
        self,
        *,
        source_path: str,
        memory_type: str,
        memory_id: str,
        summary: str,
        payload: Mapping[str, Any] | None = None,
        proposal_id: str = "",
        decision_id: str = "",
        behavior_id: str = "",
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::memory::{memory_type}::{memory_id}",
            event_kind="memory_write",
            source_path=source_path,
            proposal_id=proposal_id,
            decision_id=decision_id,
            behavior_id=behavior_id,
            memory_id=memory_id,
            payload={
                "memory_type": memory_type,
                "summary": summary,
                **dict(payload or {}),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record

    def record_execution_consistency_failure(
        self,
        *,
        source_path: str,
        behavior_name: str,
        proposal_id: str = "",
        decision_id: str = "",
        behavior_id: str = "",
        channel_id: str = "",
        op_name: str = "",
        normalized_intensity: float = 0.0,
        provenance: Mapping[str, Any] | None = None,
        payload: Mapping[str, Any] | None = None,
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::consistency::{decision_id or proposal_id or uuid4().hex}",
            event_kind="execution_consistency_failure",
            source_path=source_path,
            proposal_id=proposal_id,
            decision_id=decision_id,
            behavior_id=behavior_id,
            channel_id=channel_id,
            payload={
                "behavior_name": behavior_name,
                **self._normalize_trace_payload(
                    provenance=provenance,
                    op_name=op_name,
                    channel_id=channel_id,
                    normalized_intensity=normalized_intensity,
                ),
                **dict(payload or {}),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record

    def record_identity_revision(
        self,
        *,
        source_path: str,
        revision_id: str,
        origin_thought_id: str,
        result: str,
        payload: Mapping[str, Any] | None = None,
        observed_at_ts: float | None = None,
    ) -> FeedbackEventRecord:
        observed_ts = time.time() if observed_at_ts is None else float(observed_at_ts)
        record = FeedbackEventRecord(
            event_id=f"feedback::identity::{revision_id}",
            event_kind="identity_revision",
            source_path=source_path,
            payload={
                "revision_id": revision_id,
                "origin_thought_id": origin_thought_id,
                "result": result,
                **dict(payload or {}),
            },
            created_at=observed_ts,
        )
        self._behavior_catalog.registry.record_feedback_event(record)
        return record


__all__ = ["FeedbackRecorder"]