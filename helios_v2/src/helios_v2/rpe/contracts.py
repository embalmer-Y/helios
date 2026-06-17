"""helios_v2.rpe.contracts — Real-RPE signal contracts.

Owner: R-PROTO-LEARN.P5-A signal layer.

Purpose:
    Define the contracts for translating *real runtime consequences*
    (execution outcomes / continuity progress / goal conflict resolution)
    into a 4-channel neuromodulator RPE signal. Per ROADMAP 13.3 P5-A
    sub-rule 2, the learning signal must be anchored on dopamine RPE
    defined by *real* runtime consequences — not LLM appraisal.

Failure semantics:
    Channel values outside the contract range raise `RealRPEError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


class RealRPEError(ValueError):
    """Raised when real-RPE signal inputs or outputs violate the contract."""


def _validate_unit(name: str, value: float) -> None:
    if not (0.0 <= value <= 1.0):
        raise RealRPEError(f"{name} must be in [0, 1]: {value}")


def _validate_signed(name: str, value: float) -> None:
    if not (-1.0 <= value <= 1.0):
        raise RealRPEError(f"{name} must be in [-1, 1]: {value}")


def _validate_probability(name: str, value: float) -> None:
    if not (0.0 <= value <= 1.0):
        raise RealRPEError(f"{name} must be a probability in [0, 1]: {value}")


@dataclass(frozen=True)
class ExecutionOutcome:
    """Owner: 12 / 16b — real externalization consequence.

    Purpose:
        Capture whether a real-world action (draft sent / tool invoked)
        was executed, succeeded, received a response, and whether the
        response was accepted by the recipient.
    """

    action_id: str
    executed: bool
    succeeded: bool
    response_received: bool
    response_accepted: bool
    latency_ticks: int

    def __post_init__(self) -> None:
        if self.latency_ticks < 0:
            raise RealRPEError(f"latency_ticks must be >= 0: {self.latency_ticks}")


@dataclass(frozen=True)
class ContinuityMetric:
    """Owner: 14 / 15 — long-term goal vs short-term action alignment."""

    long_term_goal: Tuple[float, ...]
    short_term_actions: Tuple[float, ...]
    alignment_score: float
    consecutive_ticks: int

    def __post_init__(self) -> None:
        _validate_signed("alignment_score", self.alignment_score)
        if self.consecutive_ticks < 0:
            raise RealRPEError(
                f"consecutive_ticks must be >= 0: {self.consecutive_ticks}"
            )


@dataclass(frozen=True)
class ConflictResolution:
    """Owner: 07 / 11 — workspace candidate selection efficiency."""

    candidate_count: int
    accepted_count: int
    suppressed_count: int
    resolution_efficiency: float

    def __post_init__(self) -> None:
        if self.candidate_count < 0:
            raise RealRPEError(
                f"candidate_count must be >= 0: {self.candidate_count}"
            )
        if self.accepted_count < 0 or self.suppressed_count < 0:
            raise RealRPEError("accepted/suppressed counts must be >= 0")
        _validate_probability("resolution_efficiency", self.resolution_efficiency)


@dataclass(frozen=True)
class RPESignal:
    """Owner: P5-A signal layer.

    Purpose:
        4-channel neuromodulator signal anchored on dopamine RPE
        (Schultz 1997), plus effort (norepinephrine), stability
        (serotonin), threat (cortisol).
    """

    dopamine: float
    norepinephrine: float
    serotonin: float
    cortisol: float
    tick_id: int
    provenance: Tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_signed("dopamine", self.dopamine)
        _validate_unit("norepinephrine", self.norepinephrine)
        _validate_unit("serotonin", self.serotonin)
        _validate_unit("cortisol", self.cortisol)
        if self.tick_id < 0:
            raise RealRPEError(f"tick_id must be >= 0: {self.tick_id}")


@dataclass(frozen=True)
class RealRPEConfig:
    """Configuration for the RPE computer.

    Purpose:
        Hold the coefficient weights for combining ExecutionOutcome,
        ContinuityMetric, and ConflictResolution into the 4-channel
        signal. Defaults follow the design doc §3.
    """

    # dopamine reward weights (must sum to 1.0)
    w_success: float = 0.4
    w_response_accepted: float = 0.3
    w_latency: float = 0.3
    # norepinephrine effort weights
    w_ne_executed: float = 0.5
    w_ne_failure: float = 0.3
    w_ne_latency: float = 0.2
    # serotonin stability weights
    w_ser_alignment: float = 0.6
    w_ser_consecutive: float = 0.4
    consecutive_normalize_ticks: int = 20
    # cortisol threat weights
    w_cor_unresolved: float = 0.5
    w_cor_candidate: float = 0.3
    w_cor_suppressed: float = 0.2
    candidate_normalize: int = 10
    # reward shaping
    success_value: float = 1.0
    failure_value: float = -0.3
    accepted_value: float = 0.8
    rejected_value: float = -0.5
    latency_max_ticks: int = 10

    def __post_init__(self) -> None:
        if abs((self.w_success + self.w_response_accepted + self.w_latency) - 1.0) > 1e-6:
            raise RealRPEError("dopamine weights must sum to 1.0")
        if abs((self.w_ne_executed + self.w_ne_failure + self.w_ne_latency) - 1.0) > 1e-6:
            raise RealRPEError("norepinephrine weights must sum to 1.0")
        if abs((self.w_ser_alignment + self.w_ser_consecutive) - 1.0) > 1e-6:
            raise RealRPEError("serotonin weights must sum to 1.0")
        if abs((self.w_cor_unresolved + self.w_cor_candidate + self.w_cor_suppressed) - 1.0) > 1e-6:
            raise RealRPEError("cortisol weights must sum to 1.0")