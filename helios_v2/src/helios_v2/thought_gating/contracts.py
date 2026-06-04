"""Owner: thought-gating and continuation-pressure layer.

Owns:
- normalized thought-gate input contracts
- formal gate-result and continuation-pressure contracts
- gate evaluation and publication ops contracts

Does not own:
- directed retrieval
- internal thought execution
- planner or executor routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.consciousness import ConsciousState


class ThoughtGatingError(RuntimeError):
    """Hard-stop error raised when thought-gating owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ThoughtGatingError(f"{name} must be within [0.0, 1.0]")


ThoughtGateDecision = Literal["fire", "no_fire"]
NoFireReason = Literal[
    "gate_score_too_low",
    "resource_pressure_too_high",
    "continuation_absent_and_no_stimulus",
    "conscious_content_not_eligible",
    "capability_rejected_cycle",
]
ThoughtGatingLearnedParameterCategory = Literal[
    "gate_policy",
    "continuation_policy",
    "signal_normalization_policy",
]

_THOUGHT_GATE_DECISIONS = {"fire", "no_fire"}
_NO_FIRE_REASONS = {
    "gate_score_too_low",
    "resource_pressure_too_high",
    "continuation_absent_and_no_stimulus",
    "conscious_content_not_eligible",
    "capability_rejected_cycle",
}


@dataclass(frozen=True)
class SelectedStimulusSummary:
    """Represent one bounded current-cycle stimulus summary used only for gate provenance."""

    stimulus_id: str
    source_kind: str
    source_channel_id: str | None
    stimulus_intensity: float
    novelty_signal: float | None = None
    sensitization_signal: float | None = None

    def __post_init__(self) -> None:
        if not self.stimulus_id:
            raise ThoughtGatingError("SelectedStimulusSummary must declare a non-empty stimulus_id")
        if not self.source_kind:
            raise ThoughtGatingError("SelectedStimulusSummary must declare a non-empty source_kind")
        _validate_unit_interval("SelectedStimulusSummary.stimulus_intensity", self.stimulus_intensity)
        if self.novelty_signal is not None:
            _validate_unit_interval("SelectedStimulusSummary.novelty_signal", self.novelty_signal)
        if self.sensitization_signal is not None:
            _validate_unit_interval(
                "SelectedStimulusSummary.sensitization_signal",
                self.sensitization_signal,
            )


@dataclass(frozen=True)
class ThoughtGateSignalSnapshot:
    """Represent one immutable normalized gate-input snapshot for one runtime cycle."""

    snapshot_id: str
    source_conscious_state_id: str
    workload_pressure: float
    global_activation_level: float
    temporal_signal: float
    drive_urgency_signal: float
    dmn_available: bool
    selected_stimuli: tuple[SelectedStimulusSummary, ...] = ()
    tick_id: int | None = None
    neuromodulatory_arousal: float | None = None

    def __post_init__(self) -> None:
        if not self.snapshot_id:
            raise ThoughtGatingError("ThoughtGateSignalSnapshot must declare a non-empty snapshot_id")
        if not self.source_conscious_state_id:
            raise ThoughtGatingError(
                "ThoughtGateSignalSnapshot must declare a non-empty source_conscious_state_id"
            )
        _validate_unit_interval("ThoughtGateSignalSnapshot.workload_pressure", self.workload_pressure)
        _validate_unit_interval(
            "ThoughtGateSignalSnapshot.global_activation_level",
            self.global_activation_level,
        )
        _validate_unit_interval("ThoughtGateSignalSnapshot.temporal_signal", self.temporal_signal)
        _validate_unit_interval(
            "ThoughtGateSignalSnapshot.drive_urgency_signal",
            self.drive_urgency_signal,
        )
        if self.neuromodulatory_arousal is not None:
            _validate_unit_interval(
                "ThoughtGateSignalSnapshot.neuromodulatory_arousal",
                self.neuromodulatory_arousal,
            )


@dataclass(frozen=True)
class ContinuationPressureState:
    """Represent one immutable structured continuation-pressure snapshot."""

    active: bool
    level: float
    origin_thought_id: str = ""
    reason: str = ""
    expires_at_tick: int = 0
    carry_count: int = 0

    def __post_init__(self) -> None:
        _validate_unit_interval("ContinuationPressureState.level", self.level)
        if self.expires_at_tick < 0:
            raise ThoughtGatingError("ContinuationPressureState.expires_at_tick must be >= 0")
        if self.carry_count < 0:
            raise ThoughtGatingError("ContinuationPressureState.carry_count must be >= 0")
        if self.active:
            if self.level <= 0.0:
                raise ThoughtGatingError(
                    "ContinuationPressureState active states must declare a positive level"
                )
            if not self.origin_thought_id:
                raise ThoughtGatingError(
                    "ContinuationPressureState active states must declare origin_thought_id"
                )
            if not self.reason:
                raise ThoughtGatingError("ContinuationPressureState active states must declare reason")
            if self.expires_at_tick <= 0:
                raise ThoughtGatingError(
                    "ContinuationPressureState active states must declare expires_at_tick > 0"
                )
        elif self.level != 0.0:
            raise ThoughtGatingError(
                "ContinuationPressureState inactive states must carry zero continuation level"
            )

    @classmethod
    def inactive(cls) -> "ContinuationPressureState":
        return cls(active=False, level=0.0)


@dataclass(frozen=True)
class ThoughtGatingConfig:
    """Expose the confirmed initialization and learned-policy surface for thought gating."""

    legal_min_score: float
    legal_max_score: float
    continuation_state_bootstrap_id: str
    mandatory_learned_parameters: tuple[ThoughtGatingLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "gate_policy",
            "continuation_policy",
            "signal_normalization_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise ThoughtGatingError(
                "Thought-gating config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("ThoughtGatingConfig.legal_min_score", self.legal_min_score)
        _validate_unit_interval("ThoughtGatingConfig.legal_max_score", self.legal_max_score)
        if self.legal_min_score > self.legal_max_score:
            raise ThoughtGatingError("Thought-gating config score range is inverted")
        if not self.continuation_state_bootstrap_id:
            raise ThoughtGatingError(
                "Thought-gating config must declare a non-empty continuation_state_bootstrap_id"
            )


@dataclass(frozen=True)
class EvaluateThoughtGateOp:
    """Describe one thought-gate evaluation request."""

    op_name: str
    owner: str
    conscious_state_id: str
    signal_snapshot_id: str
    prior_continuation_active: bool


@dataclass(frozen=True)
class ThoughtGateResult:
    """Represent one immutable formal gate result for one runtime cycle."""

    result_id: str
    source_conscious_state_id: str
    source_signal_snapshot_id: str
    decision: ThoughtGateDecision
    gate_score: float
    trigger_reason: str | None
    dominant_reason: str | None
    blocked_reasons: tuple[str, ...]
    contributing_signals: dict[str, float]
    selected_stimuli: tuple[SelectedStimulusSummary, ...]
    no_fire_reason: NoFireReason | None
    tick_id: int | None = None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise ThoughtGatingError("ThoughtGateResult must declare a non-empty result_id")
        if not self.source_conscious_state_id:
            raise ThoughtGatingError(
                "ThoughtGateResult must declare a non-empty source_conscious_state_id"
            )
        if not self.source_signal_snapshot_id:
            raise ThoughtGatingError(
                "ThoughtGateResult must declare a non-empty source_signal_snapshot_id"
            )
        if self.decision not in _THOUGHT_GATE_DECISIONS:
            raise ThoughtGatingError("ThoughtGateResult must use the fixed decision taxonomy")
        _validate_unit_interval("ThoughtGateResult.gate_score", self.gate_score)
        if any(not reason for reason in self.blocked_reasons):
            raise ThoughtGatingError("ThoughtGateResult blocked_reasons must not contain empty values")
        for name, value in self.contributing_signals.items():
            if not name:
                raise ThoughtGatingError(
                    "ThoughtGateResult contributing_signals must not contain empty signal names"
                )
            _validate_unit_interval(f"ThoughtGateResult.contributing_signals[{name}]", value)
        if self.decision == "fire" and self.no_fire_reason is not None:
            raise ThoughtGatingError(
                "ThoughtGateResult fire decisions must not carry a no_fire_reason"
            )
        if self.decision == "no_fire" and self.no_fire_reason not in _NO_FIRE_REASONS:
            raise ThoughtGatingError(
                "ThoughtGateResult no-fire decisions must use the fixed no_fire taxonomy"
            )


@dataclass(frozen=True)
class PublishThoughtGateResultOp:
    """Describe publication of one thought-gate result."""

    op_name: str
    owner: str
    result_id: str
    decision: str
    no_fire_reason: str | None


@dataclass(frozen=True)
class PublishContinuationPressureOp:
    """Describe publication of one continuation-pressure snapshot."""

    op_name: str
    owner: str
    active: bool
    level: float
    origin_thought_id: str


@runtime_checkable
class ThoughtGatingAPI(Protocol):
    """Public owner-facing API from conscious-state plus normalized gate signals into gate evaluation."""

    def evaluate_gate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        tick_id: int | None = None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        """Return one gate result and one next continuation state."""

    def build_evaluate_op(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
    ) -> EvaluateThoughtGateOp:
        """Return one request op describing a thought-gate evaluation cycle."""

    def build_publish_gate_result_op(
        self,
        result: ThoughtGateResult,
    ) -> PublishThoughtGateResultOp:
        """Return one publication op describing gate-result publication."""

    def build_publish_continuation_op(
        self,
        continuation_state: ContinuationPressureState,
    ) -> PublishContinuationPressureOp:
        """Return one publication op describing continuation-state publication."""
