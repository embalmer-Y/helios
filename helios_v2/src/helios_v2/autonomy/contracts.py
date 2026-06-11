"""Owner: subjective autonomy and proactive evolution.

Owns:
- proactive-drive integration request and result contracts
- deferred continuity publication contracts
- autonomy owner API

Does not own:
- prompt assembly
- planner authority
- channel execution
- governance judgment
- storage writes
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable


class AutonomyError(RuntimeError):
    """Hard-stop error raised when autonomy owner invariants fail."""


ProactiveDisposition = Literal["reflect", "explore", "externalize", "defer"]
ProactiveActivityMode = Literal[
    "inward_reflective",
    "inward_exploratory",
    "outward_proactive",
    "deferred_continuity",
]
AutonomyLearnedParameterCategory = Literal[
    "drive_integration_policy",
    "continuity_carry_policy",
    "proactive_externalization_policy",
]

_DISPOSITIONS = {"reflect", "explore", "externalize", "defer"}
_ACTIVITY_MODES = {
    "inward_reflective",
    "inward_exploratory",
    "outward_proactive",
    "deferred_continuity",
}
_LEARNED_PARAMETER_CATEGORIES = {
    "drive_integration_policy",
    "continuity_carry_policy",
    "proactive_externalization_policy",
}

ContinuityThreadState = Literal["forming", "reinforced", "suppressed", "retiring"]
_THREAD_STATES = {"forming", "reinforced", "suppressed", "retiring"}


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(mapping))
    for key in frozen:
        if not key:
            raise AutonomyError("Autonomy mappings must not contain empty keys")
    return frozen


@dataclass(frozen=True)
class AutonomyConfig:
    """Expose the confirmed initialization and learned-policy surface for autonomy."""

    autonomy_bootstrap_id: str
    mandatory_learned_parameters: tuple[AutonomyLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        if set(self.mandatory_learned_parameters) != _LEARNED_PARAMETER_CATEGORIES:
            raise AutonomyError(
                "AutonomyConfig must declare the confirmed mandatory learned-parameter categories"
            )
        if not self.autonomy_bootstrap_id:
            raise AutonomyError("AutonomyConfig must declare a non-empty autonomy_bootstrap_id")


@dataclass(frozen=True)
class ProactiveCognitionFacts:
    """Immutable raw cognition facts the autonomy owner projects into its drive inputs.

    Owner: subjective autonomy and proactive evolution.

    Purpose:
        Carry the bounded set of already-published upstream cognition facts (whether the
        thought path activated, whether it produced an action proposal, whether it requested
        continuation, whether continuation is active, whether it proposed self-revision, the
        planner status, and the retrieval hit count) so the `18` owner can derive its drive
        inputs from them. Composition forwards these raw facts; the owner owns the mapping
        from facts to drive-input pressures (see `AutonomyDriveInputProjection`).

    Failure semantics:
        Construction raises `AutonomyError` on an empty `planner_status` or a negative
        `retrieval_hit_count`.
    """

    activated: bool
    has_action_proposal: bool
    continuation_requested: bool
    continuation_active: bool
    has_self_revision: bool
    planner_status: str
    retrieval_hit_count: int

    def __post_init__(self) -> None:
        if not self.planner_status:
            raise AutonomyError("ProactiveCognitionFacts must declare a non-empty planner_status")
        if not isinstance(self.retrieval_hit_count, int) or self.retrieval_hit_count < 0:
            raise AutonomyError(
                "ProactiveCognitionFacts retrieval_hit_count must be a non-negative integer"
            )


@dataclass(frozen=True)
class ProactiveDriveRequest:
    """Immutable request contract for one proactive-drive integration cycle."""

    request_id: str
    source_gate_result_id: str
    source_retrieval_bundle_id: str
    source_thought_cycle_result_id: str
    source_planner_bridge_result_id: str
    source_identity_governance_result_id: str
    source_writeback_result_ids: tuple[str, ...]
    source_outward_expression_draft_id: str
    source_outward_expression_externalization_draft_id: str
    continuation_summary: Mapping[str, object]
    retrieval_pull_summary: Mapping[str, object]
    temporal_pressure_summary: Mapping[str, object]
    identity_unresolved_summary: Mapping[str, object]
    outward_readiness_summary: Mapping[str, object]
    prior_deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    prior_continuity_threads: tuple["ContinuityThread", ...] = ()
    # R81: the prior tick's internal-monologue envelope. When set, the autonomy engine
    # emits an extra `source_kind="internal_monologue"` deferred record so the carry can
    # affect the next tick's `proactive_drive_urgency` (0.5x multiplier).
    internal_monologue_envelope: "Mapping[str, object] | None" = None

    def __post_init__(self) -> None:
        for attr_name in (
            "request_id",
            "source_gate_result_id",
            "source_retrieval_bundle_id",
            "source_thought_cycle_result_id",
            "source_planner_bridge_result_id",
            "source_identity_governance_result_id",
            "source_outward_expression_draft_id",
            "source_outward_expression_externalization_draft_id",
        ):
            if not getattr(self, attr_name):
                raise AutonomyError(f"ProactiveDriveRequest must declare non-empty {attr_name}")
        if not self.source_writeback_result_ids or any(not item for item in self.source_writeback_result_ids):
            raise AutonomyError(
                "ProactiveDriveRequest must declare non-empty source_writeback_result_ids"
            )
        for record in self.prior_deferred_records:
            if not isinstance(record, DeferredContinuityRecord):
                raise AutonomyError(
                    "ProactiveDriveRequest prior_deferred_records must contain deferred continuity records only"
                )
        for thread in self.prior_continuity_threads:
            if not isinstance(thread, ContinuityThread):
                raise AutonomyError(
                    "ProactiveDriveRequest prior_continuity_threads must contain continuity threads only"
                )
        for attr_name in (
            "continuation_summary",
            "retrieval_pull_summary",
            "temporal_pressure_summary",
            "identity_unresolved_summary",
            "outward_readiness_summary",
        ):
            frozen = _freeze_mapping(getattr(self, attr_name))
            if not frozen:
                raise AutonomyError(f"ProactiveDriveRequest must declare non-empty {attr_name}")
            object.__setattr__(self, attr_name, frozen)


@dataclass(frozen=True)
class ProactiveDriveState:
    """Immutable state snapshot describing one autonomy decision."""

    state_id: str
    dominant_disposition: ProactiveDisposition
    activity_mode: ProactiveActivityMode
    pressure_components: Mapping[str, float]
    deferred_active: bool
    proactive_action_requested: bool
    # R81: post-multiplier outward-drive urgency, in [0, 1]. When any carried record has
    # source_kind="internal_monologue", the autonomy engine scales the raw outward_drive by 0.5x.
    proactive_drive_urgency: float = 0.0

    def __post_init__(self) -> None:
        if not self.state_id:
            raise AutonomyError("ProactiveDriveState must declare a non-empty state_id")
        if self.dominant_disposition not in _DISPOSITIONS:
            raise AutonomyError(
                "ProactiveDriveState dominant_disposition must use the fixed taxonomy"
            )
        if self.activity_mode not in _ACTIVITY_MODES:
            raise AutonomyError("ProactiveDriveState activity_mode must use the fixed taxonomy")
        components = _freeze_mapping(self.pressure_components)
        if not components:
            raise AutonomyError("ProactiveDriveState must declare non-empty pressure_components")
        for key, value in components.items():
            if not isinstance(value, float) and not isinstance(value, int):
                raise AutonomyError(
                    f"ProactiveDriveState pressure_components[{key}] must be numeric"
                )
        object.__setattr__(self, "pressure_components", components)
        if not (0.0 <= self.proactive_drive_urgency <= 1.0):
            raise AutonomyError(
                f"ProactiveDriveState.proactive_drive_urgency must be in [0, 1]; got {self.proactive_drive_urgency}"
            )


@dataclass(frozen=True)
class DeferredContinuityRecord:
    """Immutable deferred-continuity record published when proactive activity cannot close."""

    record_id: str
    continuity_key: str
    origin_ref: str
    carry_reason: str
    carry_count: int
    decayed_pressure: float
    expires_after_ticks: int | None
    # R81: source_kind categorizes the origin of the deferred record. The R18 autonomy owner
    # applies a multiplier of 0.5 to the proactive_drive_urgency when the carried record is
    # internal_monologue-sourced (so internal self-talk should not override the gate weight).
    source_kind: str = "external_stimulus"  # Literal["external_stimulus", "retrieval", "internal_monologue"]

    def __post_init__(self) -> None:
        if not self.record_id:
            raise AutonomyError("DeferredContinuityRecord must declare a non-empty record_id")
        if not self.continuity_key:
            raise AutonomyError("DeferredContinuityRecord must declare a non-empty continuity_key")
        if not self.origin_ref:
            raise AutonomyError("DeferredContinuityRecord must declare a non-empty origin_ref")
        if not self.carry_reason:
            raise AutonomyError("DeferredContinuityRecord must declare a non-empty carry_reason")
        if self.carry_count <= 0:
            raise AutonomyError("DeferredContinuityRecord carry_count must be positive")
        if not isinstance(self.decayed_pressure, float) and not isinstance(self.decayed_pressure, int):
            raise AutonomyError("DeferredContinuityRecord decayed_pressure must be numeric")
        if float(self.decayed_pressure) <= 0.0:
            raise AutonomyError("DeferredContinuityRecord decayed_pressure must be positive")
        if self.expires_after_ticks is not None and self.expires_after_ticks <= 0:
            raise AutonomyError(
                "DeferredContinuityRecord expires_after_ticks must be positive when present"
            )
        valid_kinds = ("external_stimulus", "retrieval", "internal_monologue")
        if self.source_kind not in valid_kinds:
            raise AutonomyError(
                f"DeferredContinuityRecord source_kind must be one of {valid_kinds}; got {self.source_kind!r}"
            )


@dataclass(frozen=True)
class ContinuityThread:
    """Immutable long-horizon continuity thread aggregating one recurring tendency.

    Owner: subjective autonomy and proactive evolution.

    A thread aggregates the carry history of one continuity key across ticks. It layers a
    thread-level recurrence signal (age, reinforcement, strength, arbitration state) on top
    of the per-record decay semantics; it does not replace deferred-continuity records.

    Failure semantics:
        Construction raises `AutonomyError` on empty ids/keys, non-positive age, negative
        reinforcement, out-of-range strength, or an unknown thread state.
    """

    thread_id: str
    continuity_key: str
    origin_ref: str
    age_ticks: int
    reinforcement_count: int
    thread_strength: float
    thread_state: ContinuityThreadState
    last_carry_reason: str

    def __post_init__(self) -> None:
        if not self.thread_id:
            raise AutonomyError("ContinuityThread must declare a non-empty thread_id")
        if not self.continuity_key:
            raise AutonomyError("ContinuityThread must declare a non-empty continuity_key")
        if not self.origin_ref:
            raise AutonomyError("ContinuityThread must declare a non-empty origin_ref")
        if not isinstance(self.age_ticks, int) or self.age_ticks < 1:
            raise AutonomyError("ContinuityThread age_ticks must be a positive integer")
        if not isinstance(self.reinforcement_count, int) or self.reinforcement_count < 0:
            raise AutonomyError("ContinuityThread reinforcement_count must be a non-negative integer")
        if not isinstance(self.thread_strength, (int, float)):
            raise AutonomyError("ContinuityThread thread_strength must be numeric")
        if not 0.0 <= float(self.thread_strength) <= 1.0:
            raise AutonomyError("ContinuityThread thread_strength must be within [0, 1]")
        if self.thread_state not in _THREAD_STATES:
            raise AutonomyError("ContinuityThread thread_state must use the fixed taxonomy")
        if not self.last_carry_reason:
            raise AutonomyError("ContinuityThread must declare a non-empty last_carry_reason")


@dataclass(frozen=True)
class LongHorizonContinuityState:
    """Immutable owner-owned summary of the active long-horizon continuity threads.

    Owner: subjective autonomy and proactive evolution.

    Failure semantics:
        Construction raises `AutonomyError` on negative counts, a thread-count that
        disagrees with the number of threads, a dominant id that is absent when threads
        exist (or present when none do), or a suppressed-id set that is not a strict subset
        of thread ids excluding the dominant id.
    """

    state_id: str
    active_thread_count: int
    dominant_thread_id: str | None
    suppressed_thread_ids: tuple[str, ...]
    max_thread_age: int
    aggregate_reinforcement: int
    threads: tuple[ContinuityThread, ...]

    def __post_init__(self) -> None:
        if not self.state_id:
            raise AutonomyError("LongHorizonContinuityState must declare a non-empty state_id")
        if self.active_thread_count != len(self.threads):
            raise AutonomyError(
                "LongHorizonContinuityState active_thread_count must equal the number of threads"
            )
        if self.max_thread_age < 0 or self.aggregate_reinforcement < 0:
            raise AutonomyError(
                "LongHorizonContinuityState counts must be non-negative"
            )
        thread_ids = {thread.thread_id for thread in self.threads}
        if self.threads:
            if self.dominant_thread_id is None:
                raise AutonomyError(
                    "LongHorizonContinuityState must declare a dominant thread when threads exist"
                )
            if self.dominant_thread_id not in thread_ids:
                raise AutonomyError(
                    "LongHorizonContinuityState dominant_thread_id must reference a known thread"
                )
        elif self.dominant_thread_id is not None:
            raise AutonomyError(
                "LongHorizonContinuityState must not declare a dominant thread when no threads exist"
            )
        for suppressed_id in self.suppressed_thread_ids:
            if suppressed_id not in thread_ids:
                raise AutonomyError(
                    "LongHorizonContinuityState suppressed_thread_ids must reference known threads"
                )
            if suppressed_id == self.dominant_thread_id:
                raise AutonomyError(
                    "LongHorizonContinuityState suppressed_thread_ids must exclude the dominant thread"
                )

    def to_evidence(self) -> dict[str, object]:
        """Owner: autonomy.

        Purpose:
            Return a compact projection of the long-horizon continuity state for the
            read-only evaluation owner.

        Returns:
            A plain dict with the dominant thread summary plus aggregate thread facts. The
            dict carries only owner-published continuity facts, never a decision the
            evaluation owner should re-own.
        """

        dominant = None
        if self.dominant_thread_id is not None:
            dominant = next(
                (thread for thread in self.threads if thread.thread_id == self.dominant_thread_id),
                None,
            )
        return {
            "active_thread_count": self.active_thread_count,
            "dominant_thread_id": self.dominant_thread_id,
            "dominant_thread_strength": float(dominant.thread_strength) if dominant else 0.0,
            "dominant_thread_age": dominant.age_ticks if dominant else 0,
            "dominant_reinforcement_count": dominant.reinforcement_count if dominant else 0,
            "suppressed_thread_count": len(self.suppressed_thread_ids),
            "max_thread_age": self.max_thread_age,
            "aggregate_reinforcement": self.aggregate_reinforcement,
        }


@dataclass(frozen=True)
class AutonomyResult:
    """Immutable autonomy result published from one proactive-drive request."""

    result_id: str
    source_request_id: str
    drive_state: ProactiveDriveState
    deferred_records: tuple[DeferredContinuityRecord, ...]
    long_horizon_state: LongHorizonContinuityState

    def __post_init__(self) -> None:
        if not self.result_id:
            raise AutonomyError("AutonomyResult must declare a non-empty result_id")
        if not self.source_request_id:
            raise AutonomyError("AutonomyResult must declare a non-empty source_request_id")


@dataclass(frozen=True)
class EvaluateProactiveDriveOp:
    """Runtime-visible request op for one proactive-drive evaluation cycle."""

    op_name: str
    owner: str
    request_id: str
    source_gate_result_id: str
    source_retrieval_bundle_id: str


@dataclass(frozen=True)
class PublishAutonomyResultOp:
    """Runtime-visible publication op for one autonomy result."""

    op_name: str
    owner: str
    result_id: str
    state_id: str
    dominant_disposition: ProactiveDisposition
    deferred_count: int


@runtime_checkable
class AutonomyAPI(Protocol):
    """Public API for proactive-drive integration and deferred continuity publication."""

    def build_evaluate_op(
        self,
        request: ProactiveDriveRequest,
    ) -> EvaluateProactiveDriveOp:
        """Return one request op describing proactive-drive integration."""

        ...

    def evaluate(
        self,
        request: ProactiveDriveRequest,
    ) -> AutonomyResult:
        """Return one deterministic autonomy result from validated inputs."""

        ...

    def build_publish_result_op(
        self,
        result: AutonomyResult,
    ) -> PublishAutonomyResultOp:
        """Return one publication op describing autonomy-result publication."""

        ...
