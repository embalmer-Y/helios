"""helios_v2.rpe.rpe_computer — compute dopamine RPE from real outcomes.

Owner: R-PROTO-LEARN.P5-A signal layer.

Purpose:
    Translate ExecutionOutcome + ContinuityMetric + ConflictResolution
    into a 4-channel RPESignal, anchored on the dopamine reward
    prediction error (Schultz 1997) and 3 auxiliary channels for
    effort / stability / threat (Einhauser 2018, Bhatt 2019).

Failure semantics:
    Inputs already validated by contracts. clip() guarantees outputs
    stay within contract bounds. Provenance is always populated.
"""

from __future__ import annotations

from helios_v2.rpe.contracts import (
    ConflictResolution,
    ContinuityMetric,
    ExecutionOutcome,
    RealRPEConfig,
    RPESignal,
)


def _clip_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _clip_signed(value: float) -> float:
    if value < -1.0:
        return -1.0
    if value > 1.0:
        return 1.0
    return value


def compute_rpe(
    predicted_reward: float,
    actual_outcome: ExecutionOutcome,
    continuity: ContinuityMetric,
    conflict: ConflictResolution,
    config: RealRPEConfig,
    tick_id: int = 0,
) -> RPESignal:
    """Compute the 4-channel RPE signal from real runtime consequences.

    dopamine = predicted_reward - actual_outcome_reward
        (Schultz 1997 RPE: positive surprise = phasic burst,
         negative surprise = phasic dip)

    norepinephrine = effort / arousal from execution difficulty
        (Einhauser 2018 pupil dilation = cognitive effort)

    serotonin = long-term stability from continuity alignment
        (continuous aligned action = stable mood)

    cortisol = threat from unresolved goal conflict
        (high unresolved conflicts raise stress)
    """
    # 1. dopamine RPE
    success_term = (
        config.success_value if actual_outcome.succeeded else config.failure_value
    )
    response_term = (
        config.accepted_value
        if actual_outcome.response_accepted
        else config.rejected_value
    )
    latency_term = max(0.0, 1.0 - actual_outcome.latency_ticks / config.latency_max_ticks)
    actual_reward = (
        config.w_success * success_term
        + config.w_response_accepted * response_term
        + config.w_latency * latency_term
    )
    dopamine = predicted_reward - actual_reward

    # 2. norepinephrine effort
    executed_term = 0.5 if actual_outcome.executed else 0.2
    failure_term = 1.0 if not actual_outcome.succeeded else 0.0
    ne_latency_term = actual_outcome.latency_ticks / config.latency_max_ticks
    norepinephrine = (
        config.w_ne_executed * executed_term
        + config.w_ne_failure * failure_term
        + config.w_ne_latency * ne_latency_term
    )

    # 3. serotonin stability
    alignment_term = (continuity.alignment_score + 1.0) / 2.0
    consecutive_term = min(
        1.0, continuity.consecutive_ticks / config.consecutive_normalize_ticks
    )
    serotonin = (
        config.w_ser_alignment * alignment_term
        + config.w_ser_consecutive * consecutive_term
    )

    # 4. cortisol threat
    unresolved_ratio = 1.0 - conflict.resolution_efficiency
    candidate_term = min(
        1.0, conflict.candidate_count / config.candidate_normalize
    )
    suppressed_ratio = (
        conflict.suppressed_count / max(1, conflict.candidate_count)
    )
    cortisol = (
        config.w_cor_unresolved * unresolved_ratio
        + config.w_cor_candidate * candidate_term
        + config.w_cor_suppressed * suppressed_ratio
    )

    return RPESignal(
        dopamine=_clip_signed(dopamine),
        norepinephrine=_clip_unit(norepinephrine),
        serotonin=_clip_unit(serotonin),
        cortisol=_clip_unit(cortisol),
        tick_id=tick_id,
        provenance=("12", "16b", "14", "15", "07", "11"),
    )