"""First-version path for proactive-drive integration and deferred continuity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .contracts import (
    AutonomyAPI,
    AutonomyConfig,
    AutonomyError,
    AutonomyResult,
    ContinuityThread,
    DeferredContinuityRecord,
    EvaluateProactiveDriveOp,
    LongHorizonContinuityState,
    ProactiveCognitionFacts,
    ProactiveDriveRequest,
    ProactiveDriveState,
    PublishAutonomyResultOp,
)


# The owner's action threshold: a fired tick is treated as proactively action-requesting when
# its outward drive (continuation + temporal + identity pressure) reaches this value. Owned by
# the `18` autonomy owner; the drive-input projection's action pressures are calibrated so an
# action-bearing tick reaches it. `FirstVersionAutonomyPath` uses the same constant for its
# `proactive_action_requested` decision.
OUTWARD_ACTION_THRESHOLD: float = 1.6


def _bounded(value: float) -> float:
    """Owner: autonomy. Clamp a drive-input pressure into [0, 1] and round for determinism."""

    return round(min(1.0, max(0.0, value)), 4)


@dataclass(frozen=True)
class AutonomyDriveInputProjection:
    """Owner-owned projection from raw cognition facts to the autonomy drive-input summaries.

    Owner: subjective autonomy and proactive evolution.

    Purpose:
        Map `ProactiveCognitionFacts` (the raw upstream cognition facts composition forwards)
        into the five drive-input summaries the autonomy path consumes
        (`continuation_summary`, `retrieval_pull_summary`, `temporal_pressure_summary`,
        `identity_unresolved_summary`, `outward_readiness_summary`). This is the `18` owner's
        cognitive policy: how strong a proactive drive a given cognition outcome produces,
        relative to the owner's own `OUTWARD_ACTION_THRESHOLD`. It was previously mislocated in
        the composition autonomy bridge and recovered to the owner in R57.

    Failure semantics:
        Total deterministic function of the facts; every pressure is bounded into `[0, 1]`. It
        never branches into a degraded mode and raises nothing of its own (the facts contract
        validates its own inputs).

    Notes:
        The constants are calibrated so an action-bearing fired tick yields
        `outward_drive = continuation + temporal + identity = 0.9 + 0.4 + 0.4 = 1.7`, at or
        above `OUTWARD_ACTION_THRESHOLD = 1.6`, while a continue/no-action tick stays below it.
        The constants are explicit bounded first-version values under the owner's declared
        `drive_integration_policy` learned-parameter category (P5-learnable later).
    """

    # Action-bearing tick pressures (chosen so outward_drive = 0.9+0.4+0.4 = 1.7 >= 1.6).
    action_continuation_pressure: float = 0.9
    action_temporal_pressure: float = 0.4
    action_identity_pressure: float = 0.4
    # Non-action tick pressures (kept below the action threshold).
    continue_continuation_pressure: float = 0.8
    concluded_continuation_pressure: float = 0.3
    baseline_temporal_pressure: float = 0.3
    unresolved_identity_pressure: float = 0.6
    resolved_identity_pressure: float = 0.2
    # Retrieval pull normalization divisor.
    retrieval_pull_divisor: float = 4.0

    planner_executed_statuses: tuple[str, ...] = ("executed", "accepted")
    planner_blocked_statuses: tuple[str, ...] = (
        "policy_rejected",
        "execution_consistency_failed",
        "execution_failed",
    )

    def derive_drive_inputs(self, facts: ProactiveCognitionFacts) -> dict[str, dict[str, object]]:
        """Owner: autonomy.

        Purpose:
            Return the five drive-input summaries for one tick from the raw cognition facts.

        Inputs:
            A `ProactiveCognitionFacts` carrying the upstream cognition outcome.

        Returns:
            A dict with keys `continuation_summary`, `retrieval_pull_summary`,
            `temporal_pressure_summary`, `identity_unresolved_summary`,
            `outward_readiness_summary`, each a plain dict matching the `ProactiveDriveRequest`
            summary shape.

        Notes:
            Deterministic and bounded. The no-fire tick (R54: `activated is False`) yields no
            outward readiness, baseline temporal pressure, resolved identity pressure, zero
            retrieval pull, and a continuation pressure that follows `continuation_active`, so a
            no-fire tick still forms/reinforces deferred continuity like a continue tick.
        """

        if not facts.activated:
            continuation_pressure = (
                self.continue_continuation_pressure
                if facts.continuation_active
                else self.concluded_continuation_pressure
            )
            return {
                "continuation_summary": {"continuation_pressure": _bounded(continuation_pressure)},
                "retrieval_pull_summary": {"retrieval_pull": 0.0},
                "temporal_pressure_summary": {"temporal_pressure": self.baseline_temporal_pressure},
                "identity_unresolved_summary": {
                    "identity_unresolved_pressure": self.resolved_identity_pressure
                },
                "outward_readiness_summary": {
                    "outward_ready": False,
                    "externalization_blocked": False,
                },
            }

        retrieval_pull = float(facts.retrieval_hit_count) / self.retrieval_pull_divisor
        planner_executed = facts.planner_status in self.planner_executed_statuses
        planner_blocked = facts.planner_status in self.planner_blocked_statuses
        wants_continue = facts.continuation_requested or facts.continuation_active

        # Outward readiness derives only from whether the thought owner produced an action
        # proposal and how the planner handled it. No action proposal -> neither ready nor
        # blocked, so the autonomy owner cannot externalize this tick.
        outward_ready = facts.has_action_proposal and planner_executed
        externalization_blocked = facts.has_action_proposal and planner_blocked

        if facts.has_action_proposal:
            continuation_pressure = self.action_continuation_pressure
            temporal_pressure = self.action_temporal_pressure
            identity_unresolved_pressure = self.action_identity_pressure
        else:
            continuation_pressure = (
                self.continue_continuation_pressure
                if wants_continue
                else self.concluded_continuation_pressure
            )
            temporal_pressure = self.baseline_temporal_pressure
            identity_unresolved_pressure = (
                self.unresolved_identity_pressure
                if facts.has_self_revision
                else self.resolved_identity_pressure
            )

        return {
            "continuation_summary": {"continuation_pressure": _bounded(continuation_pressure)},
            "retrieval_pull_summary": {"retrieval_pull": _bounded(retrieval_pull)},
            "temporal_pressure_summary": {"temporal_pressure": _bounded(temporal_pressure)},
            "identity_unresolved_summary": {
                "identity_unresolved_pressure": _bounded(identity_unresolved_pressure)
            },
            "outward_readiness_summary": {
                "outward_ready": outward_ready,
                "externalization_blocked": externalization_blocked,
            },
        }


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


@dataclass(frozen=True)
class _DeferredContinuitySnapshot:
    active_records: tuple[DeferredContinuityRecord, ...]
    merged_record_count: int
    expired_record_count: int


@dataclass(frozen=True)
class FirstVersionAutonomyPath:
    """First shipped autonomy path integrating pressure into a bounded disposition.

    R-PROTO-LEARN.P-TEMPORAL: when `continuous_state_owner` is bound, the
    carry-forward step applies wall-clock half-life decay (default 600s)
    so the pressure decays in real seconds, not just tick-count units.
    `decay_factor` (per-tick) is retained for legacy tick-step behavior;
    `half_life_seconds` (per-second) is the P5 surface for time-aware decay.
    """

    decay_factor: float = 0.82
    minimum_decayed_pressure: float = 0.15
    reinforcement_gain: float = 0.25
    # R-PROTO-LEARN.P-TEMPORAL: wall-clock half-life for deferred pressure
    # (default 600s = 10min; P5 surface under continuity_carry_policy).
    half_life_seconds: float = 600.0
    continuous_state_owner: object | None = None
    # R-PROTO-LEARN.P-TEMPORAL: P5 surface mapping
    p5_parameter_mapping: dict[str, str] = field(default_factory=lambda: {
        "decay_factor": "continuity_carry_policy",
        "half_life_seconds": "continuity_carry_policy",
    })
    _p5_learner_binding: object | None = None

    def apply_p5_policy(self, snapshot: object) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface override.

        Maps snapshot.policy_output[0] -> decay_factor (clipped to [0.5, 1.0])
        and policy_output[1] -> half_life_seconds (clipped to [10.0, 7200.0]).
        """
        if snapshot is None or not getattr(snapshot, "policy_output", None):
            return
        out = snapshot.policy_output
        if len(out) < 1:
            return
        self.decay_factor = max(0.5, min(1.0, float(out[0])))
        if len(out) >= 2:
            self.half_life_seconds = max(10.0, min(7200.0, float(out[1])))

    @staticmethod
    def _base_reason(carry_reason: str) -> str:
        reason = carry_reason
        while reason.startswith("carried_forward:") or reason.startswith("merged:"):
            reason = reason.split(":", 1)[1]
        return reason

    @classmethod
    def _continuity_key(cls, carry_reason: str) -> str:
        """Derive a tick-stable continuity key from the carry reason only.

        The key is the base reason stripped of any carry-forward/merge prefix,
        making it identical across ticks for the same deferral motive. The
        tick-specific provenance reference lives on ``origin_ref`` separately.
        """

        return cls._base_reason(carry_reason)

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
        delta_seconds: float | None = None,
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
            # R-PROTO-LEARN.P-TEMPORAL: when delta_seconds provided, apply
            # wall-clock half-life decay: pressure *= 2^(-delta/hl)
            if delta_seconds is not None and delta_seconds > 0.0:
                decay_multiplier = pow(2.0, -delta_seconds / self.half_life_seconds)
            else:
                decay_multiplier = self.decay_factor
            next_pressure = round(record.decayed_pressure * decay_multiplier, 4)
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

    def _build_long_horizon_state(
        self,
        *,
        request: ProactiveDriveRequest,
        active_records: tuple[DeferredContinuityRecord, ...],
    ) -> LongHorizonContinuityState:
        """Form, reinforce, and arbitrate long-horizon continuity threads.

        Threads are computed from the prior carried threads plus the active deferred records
        for the current tick. A key present in both prior threads and current records is
        reinforced; a key present only in current records forms a fresh thread; a prior
        thread whose key has no active record this tick is retired (it is not carried).
        Per-record decay is unchanged: reinforcement is a thread-level signal layered on top.
        """

        prior_by_key: dict[str, ContinuityThread] = {
            thread.continuity_key: thread for thread in request.prior_continuity_threads
        }
        records_by_key: dict[str, DeferredContinuityRecord] = {}
        for record in active_records:
            # The first active record per key anchors the thread's origin and reason.
            records_by_key.setdefault(record.continuity_key, record)

        threads: list[ContinuityThread] = []
        for index, (continuity_key, record) in enumerate(records_by_key.items(), start=1):
            prior = prior_by_key.get(continuity_key)
            if prior is None:
                thread_strength = min(1.0, max(0.0, float(record.decayed_pressure)))
                threads.append(
                    ContinuityThread(
                        thread_id=f"continuity-thread:{request.request_id}:{index}",
                        continuity_key=continuity_key,
                        origin_ref=record.origin_ref,
                        age_ticks=1,
                        reinforcement_count=0,
                        thread_strength=round(thread_strength, 4),
                        thread_state="forming",
                        last_carry_reason=record.carry_reason,
                    )
                )
            else:
                reinforced_strength = min(
                    1.0,
                    float(prior.thread_strength) + self.reinforcement_gain * float(record.decayed_pressure),
                )
                threads.append(
                    ContinuityThread(
                        thread_id=f"continuity-thread:{request.request_id}:{index}",
                        continuity_key=continuity_key,
                        origin_ref=prior.origin_ref,
                        age_ticks=prior.age_ticks + 1,
                        reinforcement_count=prior.reinforcement_count + 1,
                        thread_strength=round(reinforced_strength, 4),
                        thread_state="reinforced",
                        last_carry_reason=record.carry_reason,
                    )
                )

        if not threads:
            return LongHorizonContinuityState(
                state_id=f"long-horizon-continuity:{request.request_id}",
                active_thread_count=0,
                dominant_thread_id=None,
                suppressed_thread_ids=(),
                max_thread_age=0,
                aggregate_reinforcement=0,
                threads=(),
            )

        # Deterministic arbitration: highest (strength, age, continuity_key) dominates.
        dominant = max(
            threads,
            key=lambda thread: (thread.thread_strength, thread.age_ticks, thread.continuity_key),
        )
        arbitrated: list[ContinuityThread] = []
        suppressed_ids: list[str] = []
        for thread in threads:
            if thread.thread_id == dominant.thread_id:
                arbitrated.append(thread)
                continue
            suppressed_ids.append(thread.thread_id)
            arbitrated.append(
                ContinuityThread(
                    thread_id=thread.thread_id,
                    continuity_key=thread.continuity_key,
                    origin_ref=thread.origin_ref,
                    age_ticks=thread.age_ticks,
                    reinforcement_count=thread.reinforcement_count,
                    thread_strength=thread.thread_strength,
                    thread_state="suppressed",
                    last_carry_reason=thread.last_carry_reason,
                )
            )

        return LongHorizonContinuityState(
            state_id=f"long-horizon-continuity:{request.request_id}",
            active_thread_count=len(arbitrated),
            dominant_thread_id=dominant.thread_id,
            suppressed_thread_ids=tuple(suppressed_ids),
            max_thread_age=max(thread.age_ticks for thread in arbitrated),
            aggregate_reinforcement=sum(thread.reinforcement_count for thread in arbitrated),
            threads=tuple(arbitrated),
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
        proactive_action_requested = outward_drive >= OUTWARD_ACTION_THRESHOLD
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
        long_horizon_state = self._build_long_horizon_state(
            request=request,
            active_records=tuple(deferred_records),
        )
        return AutonomyResult(
            result_id=f"autonomy-result:{request.request_id}",
            source_request_id=request.request_id,
            drive_state=drive_state,
            deferred_records=tuple(deferred_records),
            long_horizon_state=long_horizon_state,
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
