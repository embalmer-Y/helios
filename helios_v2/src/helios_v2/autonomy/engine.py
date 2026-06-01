"""First-version path for proactive-drive integration and deferred continuity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .contracts import (
    AutonomyAPI,
    AutonomyConfig,
    AutonomyError,
    AutonomyResult,
    DeferredContinuityRecord,
    EvaluateProactiveDriveOp,
    ProactiveDriveRequest,
    ProactiveDriveState,
    PublishAutonomyResultOp,
)


def _read_float(summary: dict[str, object] | object, key: str) -> float:
    if not hasattr(summary, "get"):
        raise AutonomyError(f"Autonomy summaries must expose mapping semantics for {key}")
    value = summary.get(key)
    if not isinstance(value, float) and not isinstance(value, int):
        raise AutonomyError(f"Autonomy summary field '{key}' must be numeric")
    return float(value)


def _read_bool(summary: dict[str, object] | object, key: str) -> bool:
    if not hasattr(summary, "get"):
        raise AutonomyError(f"Autonomy summaries must expose mapping semantics for {key}")
    value = summary.get(key)
    if not isinstance(value, bool):
        raise AutonomyError(f"Autonomy summary field '{key}' must be boolean")
    return value


@runtime_checkable
class AutonomyPath(Protocol):
    """Owner-private path that assembles one autonomy result from a validated request."""

    def assemble_result(
        self,
        request: ProactiveDriveRequest,
        config: AutonomyConfig,
    ) -> AutonomyResult:
        """Return one deterministic autonomy result from validated inputs."""

        ...


@dataclass(frozen=True)
class _DeferredContinuitySnapshot:
    active_records: tuple[DeferredContinuityRecord, ...]
    merged_record_count: int
    expired_record_count: int


@dataclass(frozen=True)
class FirstVersionAutonomyPath:
    """First shipped autonomy path integrating pressure into a bounded disposition."""

    decay_factor: float = 0.82
    minimum_decayed_pressure: float = 0.15

    @staticmethod
    def _base_reason(carry_reason: str) -> str:
        reason = carry_reason
        while reason.startswith("carried_forward:") or reason.startswith("merged:"):
            reason = reason.split(":", 1)[1]
        return reason

    @classmethod
    def _continuity_key(cls, origin_ref: str, carry_reason: str) -> str:
        return f"{origin_ref}:{cls._base_reason(carry_reason)}"

    def _build_deferred_record(
        self,
        *,
        request_id: str,
        suffix: str,
        continuity_key: str,
        origin_ref: str,
        carry_reason: str,
        carry_count: int,
        decayed_pressure: float,
        expires_after_ticks: int | None,
    ) -> DeferredContinuityRecord:
        return DeferredContinuityRecord(
            record_id=f"deferred-continuity:{request_id}:{suffix}",
            continuity_key=continuity_key,
            origin_ref=origin_ref,
            carry_reason=carry_reason,
            carry_count=carry_count,
            decayed_pressure=round(decayed_pressure, 4),
            expires_after_ticks=expires_after_ticks,
        )

    def _merge_active_records(
        self,
        records: tuple[DeferredContinuityRecord, ...],
        *,
        request_id: str,
        suffix_prefix: str,
    ) -> _DeferredContinuitySnapshot:
        grouped: dict[str, list[DeferredContinuityRecord]] = {}
        for record in records:
            grouped.setdefault(record.continuity_key, []).append(record)

        merged_records: list[DeferredContinuityRecord] = []
        merged_record_count = 0
        for index, (continuity_key, group) in enumerate(grouped.items(), start=1):
            merged_record_count += max(0, len(group) - 1)
            first = group[0]
            base_reason = self._base_reason(first.carry_reason)
            carry_reason = first.carry_reason if len(group) == 1 else f"merged:{base_reason}"
            expires_candidates = [
                record.expires_after_ticks for record in group if record.expires_after_ticks is not None
            ]
            expires_after_ticks = max(expires_candidates) if expires_candidates else None
            merged_records.append(
                self._build_deferred_record(
                    request_id=request_id,
                    suffix=f"{suffix_prefix}:{index}",
                    continuity_key=continuity_key,
                    origin_ref=first.origin_ref,
                    carry_reason=carry_reason,
                    carry_count=max(record.carry_count for record in group),
                    decayed_pressure=min(1.0, sum(record.decayed_pressure for record in group)),
                    expires_after_ticks=expires_after_ticks,
                )
            )

        return _DeferredContinuitySnapshot(
            active_records=tuple(merged_records),
            merged_record_count=merged_record_count,
            expired_record_count=0,
        )

    def _carry_forward_records(
        self,
        records: tuple[DeferredContinuityRecord, ...],
        *,
        request_id: str,
    ) -> _DeferredContinuitySnapshot:
        carried: list[DeferredContinuityRecord] = []
        expired_record_count = 0
        for index, record in enumerate(records, start=1):
            if record.expires_after_ticks is None:
                next_expiry = None
            else:
                next_expiry = record.expires_after_ticks - 1
                if next_expiry <= 0:
                    expired_record_count += 1
                    continue
            next_pressure = round(record.decayed_pressure * self.decay_factor, 4)
            if next_pressure < self.minimum_decayed_pressure:
                expired_record_count += 1
                continue
            carried.append(
                self._build_deferred_record(
                    request_id=request_id,
                    suffix=f"carried:{index}",
                    continuity_key=record.continuity_key,
                    origin_ref=record.origin_ref,
                    carry_reason=f"carried_forward:{self._base_reason(record.carry_reason)}",
                    carry_count=record.carry_count + 1,
                    decayed_pressure=next_pressure,
                    expires_after_ticks=next_expiry,
                )
            )
        merged_snapshot = self._merge_active_records(
            tuple(carried),
            request_id=request_id,
            suffix_prefix="merged-carry",
        )
        return _DeferredContinuitySnapshot(
            active_records=merged_snapshot.active_records,
            merged_record_count=merged_snapshot.merged_record_count,
            expired_record_count=expired_record_count,
        )

    def assemble_result(
        self,
        request: ProactiveDriveRequest,
        config: AutonomyConfig,
    ) -> AutonomyResult:
        if config.autonomy_bootstrap_id != "autonomy-bootstrap:v1":
            raise AutonomyError(
                "FirstVersionAutonomyPath requires the confirmed autonomy bootstrap id"
            )

        continuation_pressure = _read_float(request.continuation_summary, "continuation_pressure")
        retrieval_pull = _read_float(request.retrieval_pull_summary, "retrieval_pull")
        temporal_pressure = _read_float(request.temporal_pressure_summary, "temporal_pressure")
        identity_unresolved = _read_float(
            request.identity_unresolved_summary,
            "identity_unresolved_pressure",
        )
        outward_ready = _read_bool(request.outward_readiness_summary, "outward_ready")
        externalization_blocked = _read_bool(
            request.outward_readiness_summary,
            "externalization_blocked",
        )

        reflective_drive = continuation_pressure + temporal_pressure
        exploratory_drive = retrieval_pull + (temporal_pressure * 0.5)
        outward_drive = continuation_pressure + temporal_pressure + identity_unresolved
        combined_pressure = continuation_pressure + retrieval_pull + temporal_pressure + identity_unresolved
        proactive_action_requested = outward_drive >= 1.6
        carry_snapshot = self._carry_forward_records(
            request.prior_deferred_records,
            request_id=request.request_id,
        )
        carried_records = carry_snapshot.active_records
        merged_record_count = carry_snapshot.merged_record_count
        expired_record_count = carry_snapshot.expired_record_count
        resolved_record_count = 0
        generated_record_count = 0

        deferred_records: list[DeferredContinuityRecord] = list(carried_records)
        dominant_disposition = "reflect"
        activity_mode = "inward_reflective"

        if externalization_blocked and proactive_action_requested:
            dominant_disposition = "defer"
            activity_mode = "deferred_continuity"
            deferred_records.append(
                self._build_deferred_record(
                    request_id=request.request_id,
                    suffix="blocked-outward",
                    continuity_key=self._continuity_key(
                        request.source_planner_bridge_result_id,
                        "blocked_outward_externalization",
                    ),
                    origin_ref=request.source_planner_bridge_result_id,
                    carry_reason="blocked_outward_externalization",
                    carry_count=1,
                    decayed_pressure=max(outward_drive, self.minimum_decayed_pressure),
                    expires_after_ticks=3,
                )
            )
            generated_record_count += 1
        elif outward_ready and proactive_action_requested:
            dominant_disposition = "externalize"
            activity_mode = "outward_proactive"
            resolved_record_count = len(carried_records)
            deferred_records = []
        elif carried_records:
            dominant_disposition = "defer"
            activity_mode = "deferred_continuity"
        elif exploratory_drive > reflective_drive and exploratory_drive >= 1.0:
            dominant_disposition = "explore"
            activity_mode = "inward_exploratory"
        elif reflective_drive >= 0.8:
            dominant_disposition = "reflect"
            activity_mode = "inward_reflective"
        else:
            dominant_disposition = "defer"
            activity_mode = "deferred_continuity"
            if combined_pressure >= 0.8:
                deferred_records.append(
                    self._build_deferred_record(
                        request_id=request.request_id,
                        suffix="carry-forward",
                        continuity_key=self._continuity_key(
                            request.source_thought_cycle_result_id,
                            "insufficient_outward_readiness",
                        ),
                        origin_ref=request.source_thought_cycle_result_id,
                        carry_reason="insufficient_outward_readiness",
                        carry_count=1,
                        decayed_pressure=max(combined_pressure, self.minimum_decayed_pressure),
                        expires_after_ticks=2,
                    )
                )
                generated_record_count += 1

        merge_snapshot = self._merge_active_records(
            tuple(deferred_records),
            request_id=request.request_id,
            suffix_prefix="merged-active",
        )
        deferred_records = list(merge_snapshot.active_records)
        merged_record_count += merge_snapshot.merged_record_count

        drive_state = ProactiveDriveState(
            state_id=f"proactive-drive-state:{request.request_id}",
            dominant_disposition=dominant_disposition,
            activity_mode=activity_mode,
            pressure_components={
                "continuation_pressure": continuation_pressure,
                "retrieval_pull": retrieval_pull,
                "temporal_pressure": temporal_pressure,
                "identity_unresolved_pressure": identity_unresolved,
                "combined_pressure": combined_pressure,
                "outward_drive": outward_drive,
                "prior_deferred_count": float(len(request.prior_deferred_records)),
                "active_deferred_count": float(len(deferred_records)),
                "generated_record_count": float(generated_record_count),
                "merged_record_count": float(merged_record_count),
                "expired_record_count": float(expired_record_count),
                "resolved_record_count": float(resolved_record_count),
            },
            deferred_active=bool(deferred_records),
            proactive_action_requested=proactive_action_requested,
        )
        return AutonomyResult(
            result_id=f"autonomy-result:{request.request_id}",
            source_request_id=request.request_id,
            drive_state=drive_state,
            deferred_records=tuple(deferred_records),
        )


@dataclass(frozen=True)
class AutonomyEngine(AutonomyAPI):
    """Public owner that integrates proactive drive into a bounded autonomy result."""

    config: AutonomyConfig
    autonomy_path: AutonomyPath | None

    def build_evaluate_op(
        self,
        request: ProactiveDriveRequest,
    ) -> EvaluateProactiveDriveOp:
        return EvaluateProactiveDriveOp(
            op_name="evaluate_proactive_drive",
            owner="subjective_autonomy_and_proactive_evolution",
            request_id=request.request_id,
            source_gate_result_id=request.source_gate_result_id,
            source_retrieval_bundle_id=request.source_retrieval_bundle_id,
        )

    def evaluate(
        self,
        request: ProactiveDriveRequest,
    ) -> AutonomyResult:
        if self.autonomy_path is None:
            raise AutonomyError("Autonomy evaluation requires an explicit autonomy capability")
        return self.autonomy_path.assemble_result(request, self.config)

    def build_publish_result_op(
        self,
        result: AutonomyResult,
    ) -> PublishAutonomyResultOp:
        return PublishAutonomyResultOp(
            op_name="publish_autonomy_result",
            owner="subjective_autonomy_and_proactive_evolution",
            result_id=result.result_id,
            state_id=result.drive_state.state_id,
            dominant_disposition=result.drive_state.dominant_disposition,
            deferred_count=len(result.deferred_records),
        )
