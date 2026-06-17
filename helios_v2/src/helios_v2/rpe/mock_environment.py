"""helios_v2.rpe.mock_environment — deterministic mock environment for ablation study.

Owner: R-PROTO-LEARN.P5-A experimental harness.

Purpose:
    Provide a deterministic mock that emits ExecutionOutcome +
    ContinuityMetric + ConflictResolution triples across a 30-tick
    3-phase cycle (easy / medium / hard) so the P5-A ablation study
    can compare LLM-appraisal-driven learning against Real-RPE-driven
    learning without requiring real network/tool calls.

Phase cycle (per 30 ticks, repeating):
    [0, 10): easy success
        - executed=True, succeeded=True, response_accepted=True, latency=1
        - alignment=0.8, consecutive_ticks = phase + 1
        - 3 candidates all accepted, resolution_efficiency=1.0
    [10, 20): medium mixed
        - executed=True, succeeded=True, response_accepted=False, latency=3
        - alignment=0.3, consecutive_ticks reset to phase-10
        - 5 candidates, 3 accepted, resolution_efficiency=0.6
    [20, 30): hard failure
        - executed=True, succeeded=False, response_accepted=False, latency=8
        - alignment=-0.5, consecutive_ticks=0
        - 10 candidates, 2 accepted, resolution_efficiency=0.2
"""

from __future__ import annotations

from helios_v2.rpe.contracts import (
    ConflictResolution,
    ContinuityMetric,
    ExecutionOutcome,
)


def _phase(tick: int) -> int:
    return tick % 30


def mock_environment_tick(tick: int, owner_id: str) -> tuple[ExecutionOutcome, ContinuityMetric, ConflictResolution]:
    phase = _phase(tick)
    if phase < 10:
        # Phase A — easy success
        outcome = ExecutionOutcome(
            action_id=f"{owner_id}-a{tick}",
            executed=True,
            succeeded=True,
            response_received=True,
            response_accepted=True,
            latency_ticks=1,
        )
        continuity = ContinuityMetric(
            long_term_goal=(0.5,) * 5,
            short_term_actions=(0.5,) * 7,
            alignment_score=0.8,
            consecutive_ticks=phase + 1,
        )
        conflict = ConflictResolution(
            candidate_count=3,
            accepted_count=3,
            suppressed_count=0,
            resolution_efficiency=1.0,
        )
    elif phase < 20:
        # Phase B — medium mixed
        outcome = ExecutionOutcome(
            action_id=f"{owner_id}-b{tick}",
            executed=True,
            succeeded=True,
            response_received=True,
            response_accepted=False,
            latency_ticks=3,
        )
        continuity = ContinuityMetric(
            long_term_goal=(0.5,) * 5,
            short_term_actions=(0.5,) * 7,
            alignment_score=0.3,
            consecutive_ticks=max(0, phase - 10),
        )
        conflict = ConflictResolution(
            candidate_count=5,
            accepted_count=3,
            suppressed_count=2,
            resolution_efficiency=0.6,
        )
    else:
        # Phase C — hard failure
        outcome = ExecutionOutcome(
            action_id=f"{owner_id}-c{tick}",
            executed=True,
            succeeded=False,
            response_received=False,
            response_accepted=False,
            latency_ticks=8,
        )
        continuity = ContinuityMetric(
            long_term_goal=(0.5,) * 5,
            short_term_actions=(0.5,) * 7,
            alignment_score=-0.5,
            consecutive_ticks=0,
        )
        conflict = ConflictResolution(
            candidate_count=10,
            accepted_count=2,
            suppressed_count=8,
            resolution_efficiency=0.2,
        )
    return outcome, continuity, conflict


def phase_label(tick: int) -> str:
    p = _phase(tick)
    if p < 10:
        return "easy"
    if p < 20:
        return "medium"
    return "hard"