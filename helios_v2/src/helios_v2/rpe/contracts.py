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

from dataclasses import dataclass, field
from typing import ClassVar, Tuple


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


@dataclass(frozen=False)
class RealRPEConfig:
    """Configuration for the RPE computer.

    Purpose:
        Hold the coefficient weights for combining ExecutionOutcome,
        ContinuityMetric, and ConflictResolution into the 4-channel
        signal. Defaults follow the design doc §3.

    R-PROTO-LEARN.P-TEMPORAL: this dataclass was `frozen=True`; it is
    unfrozen now so P5 learners can override the 13 weights via
    `update_*_weights(...)` methods. Each method enforces the original
    sum-to-1.0 invariant internally by **renormalizing** the candidate
    triple (clipped to [0, 1], then re-normalized to sum=1.0). The
    sum-to-1.0 invariant is preserved at all times (post-update).
    Reward shaping scalars are clipped to their declared range without
    renormalization. The previous frozen-with-__post_init__ check is
    preserved as `_validate_sum_to_one()` and called from each
    `update_*_weights` method after renormalization.
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

    # R-PROTO-LEARN.P-TEMPORAL: P5 surface mapping (ClassVar so the
    # mutable dataclass keeps its per-instance fields independent).
    p5_parameter_mapping: ClassVar[dict[str, str]] = {
        # 13 weights organized under the 4-channel categories.
        # RealRPEConfig has no LearnedParameterCategory Literal of its
        # own (RPE is the producer, not consumer); categories match the
        # 4-channel signal types so the downstream LearnerABC.update
        # rpe_signal validation aligns.
        "w_success": "dopamine",
        "w_response_accepted": "dopamine",
        "w_latency": "dopamine",
        "w_ne_executed": "norepinephrine",
        "w_ne_failure": "norepinephrine",
        "w_ne_latency": "norepinephrine",
        "w_ser_alignment": "serotonin",
        "w_ser_consecutive": "serotonin",
        "w_cor_unresolved": "cortisol",
        "w_cor_candidate": "cortisol",
        "w_cor_suppressed": "cortisol",
        "success_value": "dopamine",
        "failure_value": "dopamine",
        "accepted_value": "dopamine",
        "rejected_value": "dopamine",
        "latency_max_ticks": "dopamine",
        "consecutive_normalize_ticks": "serotonin",
        "candidate_normalize": "cortisol",
    }
    # R-PROTO-LEARN.P-TEMPORAL: optional P5 learner binding (set by
    # wire_learner_to_owner).
    _p5_learner_binding: object | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._validate_sum_to_one()
        self._validate_reward_shaping()

    def _validate_sum_to_one(self) -> None:
        # R-PROTO-LEARN.P-TEMPORAL: tolerance widened to 1e-4 because
        # the new P5 renormalize-then-round path introduces 6-digit
        # rounding that can accumulate to ~6e-7 per term (3-term sum:
        # up to ~1.8e-6). Original 1e-6 was too tight for the post-
        # P5-override path; 1e-4 is still well within signal-precision
        # for the downstream RPE 4-channel computation.
        if abs((self.w_success + self.w_response_accepted + self.w_latency) - 1.0) > 1e-4:
            raise RealRPEError("dopamine weights must sum to 1.0")
        if abs((self.w_ne_executed + self.w_ne_failure + self.w_ne_latency) - 1.0) > 1e-4:
            raise RealRPEError("norepinephrine weights must sum to 1.0")
        if abs((self.w_ser_alignment + self.w_ser_consecutive) - 1.0) > 1e-4:
            raise RealRPEError("serotonin weights must sum to 1.0")
        if abs((self.w_cor_unresolved + self.w_cor_candidate + self.w_cor_suppressed) - 1.0) > 1e-4:
            raise RealRPEError("cortisol weights must sum to 1.0")

    def _validate_reward_shaping(self) -> None:
        if not (-1.0 <= self.success_value <= 1.0):
            raise RealRPEError(f"success_value out of [-1, 1]: {self.success_value}")
        if not (-1.0 <= self.failure_value <= 1.0):
            raise RealRPEError(f"failure_value out of [-1, 1]: {self.failure_value}")
        if not (-1.0 <= self.accepted_value <= 1.0):
            raise RealRPEError(f"accepted_value out of [-1, 1]: {self.accepted_value}")
        if not (-1.0 <= self.rejected_value <= 1.0):
            raise RealRPEError(f"rejected_value out of [-1, 1]: {self.rejected_value}")
        if self.latency_max_ticks < 1:
            raise RealRPEError(f"latency_max_ticks must be >= 1: {self.latency_max_ticks}")
        if self.consecutive_normalize_ticks < 1:
            raise RealRPEError(
                f"consecutive_normalize_ticks must be >= 1: {self.consecutive_normalize_ticks}"
            )
        if self.candidate_normalize < 1:
            raise RealRPEError(f"candidate_normalize must be >= 1: {self.candidate_normalize}")

    @staticmethod
    def _renormalize_to_unit_triple(
        a: float, b: float, c: float,
    ) -> tuple[float, float, float]:
        """Clip each weight to [0, 1] then renormalize so they sum to 1.0.

        Empty-input or all-zero edge case: fall back to (1/3, 1/3, 1/3).
        This preserves the sum-to-1.0 invariant under any learner-supplied
        raw triple (P5 policy output is in [0, 1]).
        """
        a = max(0.0, min(1.0, a))
        b = max(0.0, min(1.0, b))
        c = max(0.0, min(1.0, c))
        total = a + b + c
        if total <= 1e-9:
            return (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
        return (a / total, b / total, c / total)

    @staticmethod
    def _renormalize_to_unit_pair(
        a: float, b: float,
    ) -> tuple[float, float]:
        a = max(0.0, min(1.0, a))
        b = max(0.0, min(1.0, b))
        total = a + b
        if total <= 1e-9:
            return (0.5, 0.5)
        return (a / total, b / total)

    def update_dopamine_weights(
        self, w_success: float, w_response_accepted: float, w_latency: float,
    ) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface for dopamine reward weights.

        Accepts any real values, clips each to [0, 1], renormalizes to
        sum=1.0, and writes to the three fields. Invariant preserved.
        """
        a, b, c = self._renormalize_to_unit_triple(w_success, w_response_accepted, w_latency)
        self.w_success = round(a, 6)
        self.w_response_accepted = round(b, 6)
        self.w_latency = round(c, 6)
        self._validate_sum_to_one()

    def update_ne_weights(
        self, w_ne_executed: float, w_ne_failure: float, w_ne_latency: float,
    ) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface for NE effort weights."""
        a, b, c = self._renormalize_to_unit_triple(w_ne_executed, w_ne_failure, w_ne_latency)
        self.w_ne_executed = round(a, 6)
        self.w_ne_failure = round(b, 6)
        self.w_ne_latency = round(c, 6)
        self._validate_sum_to_one()

    def update_ser_weights(
        self, w_ser_alignment: float, w_ser_consecutive: float,
    ) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface for serotonin stability weights."""
        a, b = self._renormalize_to_unit_pair(w_ser_alignment, w_ser_consecutive)
        self.w_ser_alignment = round(a, 6)
        self.w_ser_consecutive = round(b, 6)
        self._validate_sum_to_one()

    def update_cor_weights(
        self, w_cor_unresolved: float, w_cor_candidate: float, w_cor_suppressed: float,
    ) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface for cortisol threat weights."""
        a, b, c = self._renormalize_to_unit_triple(
            w_cor_unresolved, w_cor_candidate, w_cor_suppressed,
        )
        self.w_cor_unresolved = round(a, 6)
        self.w_cor_candidate = round(b, 6)
        self.w_cor_suppressed = round(c, 6)
        self._validate_sum_to_one()

    def update_reward_shaping(
        self,
        success_value: float | None = None,
        failure_value: float | None = None,
        accepted_value: float | None = None,
        rejected_value: float | None = None,
        latency_max_ticks: int | None = None,
        consecutive_normalize_ticks: int | None = None,
        candidate_normalize: int | None = None,
    ) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface for reward shaping scalars.

        All args optional; only the supplied ones are updated. Clipped to
        declared range. Sum-to-1.0 invariant not affected (these are
        scalars, not weights).
        """
        if success_value is not None:
            self.success_value = round(max(-1.0, min(1.0, success_value)), 6)
        if failure_value is not None:
            self.failure_value = round(max(-1.0, min(1.0, failure_value)), 6)
        if accepted_value is not None:
            self.accepted_value = round(max(-1.0, min(1.0, accepted_value)), 6)
        if rejected_value is not None:
            self.rejected_value = round(max(-1.0, min(1.0, rejected_value)), 6)
        if latency_max_ticks is not None:
            self.latency_max_ticks = max(1, int(latency_max_ticks))
        if consecutive_normalize_ticks is not None:
            self.consecutive_normalize_ticks = max(1, int(consecutive_normalize_ticks))
        if candidate_normalize is not None:
            self.candidate_normalize = max(1, int(candidate_normalize))
        self._validate_reward_shaping()

    def apply_p5_policy(self, snapshot: object) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface override.

        Maps snapshot.policy_output (18-dim, one per p5_parameter_mapping
        field in alphabetical order) to update_*_weights methods. The
        snapshot's policy_output is normalized to [0, 1]; reward shaping
        fields are unclipped (success/failure/accepted/rejected are
        in [-1, 1], latency/normalize are ints >= 1). We split policy_output
        into the 5 update_*_windows according to p5_parameter_mapping.
        """
        if snapshot is None or not getattr(snapshot, "policy_output", None):
            return
        out = snapshot.policy_output
        mapping = self.p5_parameter_mapping
        # Walk in declaration order; field index = sorted order isn't
        # required — we use a positional layout matching update_*_weights.
        # Layout (must match caller contract): indices 0-2 dopamine,
        # 3-5 NE, 6-7 serotonin, 8-10 cortisol, 11-12 success/failure,
        # 13-14 accepted/rejected, 15 latency, 16 consecutive_norm,
        # 17 candidate_norm. Total = 18.
        if len(out) < 18:
            # Fallback: short policy_output only updates the prefix.
            self.update_dopamine_weights(out[0], out[1], out[2]) if len(out) >= 3 else None
            return
        self.update_dopamine_weights(out[0], out[1], out[2])
        self.update_ne_weights(out[3], out[4], out[5])
        self.update_ser_weights(out[6], out[7])
        self.update_cor_weights(out[8], out[9], out[10])
        # Reward shaping: success/failure/accepted/rejected are signed [-1, 1]
        # in policy_output (interpret as raw values; update clips).
        self.update_reward_shaping(
            success_value=2.0 * out[11] - 1.0,
            failure_value=2.0 * out[12] - 1.0,
            accepted_value=2.0 * out[13] - 1.0,
            rejected_value=2.0 * out[14] - 1.0,
            latency_max_ticks=max(1, int(round(out[15] * 100))),
            consecutive_normalize_ticks=max(1, int(round(out[16] * 100))),
            candidate_normalize=max(1, int(round(out[17] * 100))),
        )