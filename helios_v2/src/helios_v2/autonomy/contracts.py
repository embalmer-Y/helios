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


@dataclass(frozen=True)
class AutonomyResult:
    """Immutable autonomy result published from one proactive-drive request."""

    result_id: str
    source_request_id: str
    drive_state: ProactiveDriveState
    deferred_records: tuple[DeferredContinuityRecord, ...]

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
