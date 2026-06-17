"""Tests for helios_v2.rpe — Real-RPE signal layer (R-PROTO-LEARN.P5-A).

Coverage:
- contract validation (in-bounds, clip, error raising)
- dopamine RPE math (Schultz 1997: positive surprise positive dip)
- norepinephrine / serotonin / cortisol channels
- provenance always populated
- deterministic behaviour under identical inputs
"""

from __future__ import annotations

import pytest

from helios_v2.rpe import (
    ConflictResolution,
    ContinuityMetric,
    ExecutionOutcome,
    RealRPEConfig,
    RealRPEError,
    RPESignal,
    compute_rpe,
)


def _success_outcome(latency: int = 1) -> ExecutionOutcome:
    return ExecutionOutcome(
        action_id="a0",
        executed=True,
        succeeded=True,
        response_received=True,
        response_accepted=True,
        latency_ticks=latency,
    )


def _failure_outcome() -> ExecutionOutcome:
    return ExecutionOutcome(
        action_id="a0",
        executed=True,
        succeeded=False,
        response_received=False,
        response_accepted=False,
        latency_ticks=5,
    )


def _good_continuity() -> ContinuityMetric:
    return ContinuityMetric(
        long_term_goal=(0.5,) * 5,
        short_term_actions=(0.5,) * 7,
        alignment_score=0.8,
        consecutive_ticks=15,
    )


def _bad_continuity() -> ContinuityMetric:
    return ContinuityMetric(
        long_term_goal=(0.5,) * 5,
        short_term_actions=(0.5,) * 7,
        alignment_score=-0.5,
        consecutive_ticks=0,
    )


def _good_conflict() -> ConflictResolution:
    return ConflictResolution(
        candidate_count=3,
        accepted_count=3,
        suppressed_count=0,
        resolution_efficiency=1.0,
    )


def _bad_conflict() -> ConflictResolution:
    return ConflictResolution(
        candidate_count=10,
        accepted_count=1,
        suppressed_count=9,
        resolution_efficiency=0.1,
    )


def _rpe(predicted: float = 0.5, tick: int = 0) -> RPESignal:
    return compute_rpe(
        predicted_reward=predicted,
        actual_outcome=_success_outcome(),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=tick,
    )


# ===== contract validation =====


def test_execution_outcome_rejects_negative_latency():
    with pytest.raises(RealRPEError):
        ExecutionOutcome("a", True, True, True, True, latency_ticks=-1)


def test_continuity_rejects_out_of_range_alignment():
    with pytest.raises(RealRPEError):
        ContinuityMetric((0.5,) * 5, (0.5,) * 7, alignment_score=1.5, consecutive_ticks=1)


def test_continuity_rejects_negative_consecutive():
    with pytest.raises(RealRPEError):
        ContinuityMetric((0.5,) * 5, (0.5,) * 7, alignment_score=0.0, consecutive_ticks=-1)


def test_conflict_rejects_invalid_efficiency():
    with pytest.raises(RealRPEError):
        ConflictResolution(3, 3, 0, resolution_efficiency=1.5)


def test_conflict_rejects_negative_counts():
    with pytest.raises(RealRPEError):
        ConflictResolution(-1, 0, 0, resolution_efficiency=1.0)
    with pytest.raises(RealRPEError):
        ConflictResolution(3, -1, 0, resolution_efficiency=1.0)
    with pytest.raises(RealRPEError):
        ConflictResolution(3, 3, -1, resolution_efficiency=1.0)


def test_rpe_signal_rejects_out_of_range_dopamine():
    with pytest.raises(RealRPEError):
        RPESignal(dopamine=2.0, norepinephrine=0.5, serotonin=0.5, cortisol=0.5,
                  tick_id=0, provenance=())


def test_rpe_signal_rejects_out_of_range_ne():
    with pytest.raises(RealRPEError):
        RPESignal(dopamine=0.0, norepinephrine=-0.1, serotonin=0.5, cortisol=0.5,
                  tick_id=0, provenance=())


def test_rpe_signal_rejects_negative_tick():
    with pytest.raises(RealRPEError):
        RPESignal(dopamine=0.0, norepinephrine=0.5, serotonin=0.5, cortisol=0.5,
                  tick_id=-1, provenance=())


def test_config_rejects_unbalanced_dopamine_weights():
    with pytest.raises(RealRPEError):
        RealRPEConfig(w_success=0.5, w_response_accepted=0.3, w_latency=0.3)


# ===== dopamine RPE math (Schultz 1997) =====


def test_dopamine_is_positive_when_actual_worse_than_predicted():
    # predicted=0.9 but actual is failure -> big positive RPE
    sig = compute_rpe(
        predicted_reward=0.9,
        actual_outcome=_failure_outcome(),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert sig.dopamine > 0.0


def test_dopamine_is_negative_when_actual_better_than_predicted():
    # predicted=0.1 but actual is success -> negative RPE (better than expected)
    sig = compute_rpe(
        predicted_reward=0.1,
        actual_outcome=_success_outcome(),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert sig.dopamine < 0.0


def test_dopamine_clip_to_signed_range():
    sig = compute_rpe(
        predicted_reward=10.0,
        actual_outcome=_failure_outcome(),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert -1.0 <= sig.dopamine <= 1.0


def test_dopamine_is_zero_when_predicted_equals_actual():
    # success outcome with predicted_reward=actual_reward=0.5
    # actual = 0.4*1.0 + 0.3*0.8 + 0.3*(1-1/10) = 0.4+0.24+0.27 = 0.91
    # too high; try predicted = 0.91
    sig = compute_rpe(
        predicted_reward=0.91,
        actual_outcome=_success_outcome(latency=1),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert abs(sig.dopamine) < 0.05


# ===== norepinephrine effort =====


def test_norepinephrine_higher_for_failure_than_success():
    sig_success = compute_rpe(0.5, _success_outcome(), _good_continuity(),
                              _good_conflict(), RealRPEConfig())
    sig_failure = compute_rpe(0.5, _failure_outcome(), _good_continuity(),
                              _good_conflict(), RealRPEConfig())
    assert sig_failure.norepinephrine > sig_success.norepinephrine


def test_norepinephrine_clip_to_unit_interval():
    sig = _rpe()
    assert 0.0 <= sig.norepinephrine <= 1.0


# ===== serotonin stability =====


def test_serotonin_higher_for_good_continuity_than_bad():
    sig_good = compute_rpe(0.5, _success_outcome(), _good_continuity(),
                           _good_conflict(), RealRPEConfig())
    sig_bad = compute_rpe(0.5, _success_outcome(), _bad_continuity(),
                          _good_conflict(), RealRPEConfig())
    assert sig_good.serotonin > sig_bad.serotonin


def test_serotonin_clip_to_unit_interval():
    sig = _rpe()
    assert 0.0 <= sig.serotonin <= 1.0


# ===== cortisol threat =====


def test_cortisol_higher_for_bad_conflict_than_good():
    sig_good = compute_rpe(0.5, _success_outcome(), _good_continuity(),
                           _good_conflict(), RealRPEConfig())
    sig_bad = compute_rpe(0.5, _success_outcome(), _good_continuity(),
                          _bad_conflict(), RealRPEConfig())
    assert sig_bad.cortisol > sig_good.cortisol


def test_cortisol_clip_to_unit_interval():
    sig = _rpe()
    assert 0.0 <= sig.cortisol <= 1.0


# ===== provenance =====


def test_provenance_always_populated_with_6_owners():
    sig = _rpe()
    assert len(sig.provenance) == 6
    assert "12" in sig.provenance
    assert "16b" in sig.provenance
    assert "14" in sig.provenance
    assert "15" in sig.provenance
    assert "07" in sig.provenance
    assert "11" in sig.provenance


# ===== determinism =====


def test_same_inputs_produce_same_signal():
    sig1 = _rpe()
    sig2 = _rpe()
    assert sig1 == sig2


def test_different_tick_produces_different_provenance_timestamp():
    sig1 = _rpe(tick=5)
    sig2 = _rpe(tick=10)
    assert sig1.tick_id == 5
    assert sig2.tick_id == 10


# ===== ownership semantics (P5-A sub-rule 2: real consequences) =====


def test_scenario_easy_success_low_cortisol_high_serotonin():
    """Easy success scenario should have low cortisol and high serotonin."""
    sig = compute_rpe(
        predicted_reward=0.5,
        actual_outcome=_success_outcome(latency=1),
        continuity=_good_continuity(),
        conflict=_good_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert sig.cortisol < 0.2
    assert sig.serotonin > 0.5


def test_scenario_hard_failure_high_cortisol_low_serotonin():
    """Hard failure scenario should have high cortisol and low serotonin."""
    sig = compute_rpe(
        predicted_reward=0.5,
        actual_outcome=_failure_outcome(),
        continuity=_bad_continuity(),
        conflict=_bad_conflict(),
        config=RealRPEConfig(),
        tick_id=0,
    )
    assert sig.cortisol > 0.5
    assert sig.serotonin < 0.5


def test_scenario_unexecuted_action_low_ne():
    """Action not executed + no failure -> low norepinephrine (no effort)."""
    no_execute_no_fail = ExecutionOutcome("a", False, True, True, True, 0)
    sig = compute_rpe(0.5, no_execute_no_fail, _good_continuity(),
                      _good_conflict(), RealRPEConfig())
    # executed=False gives 0.2 base + 0.0 failure + 0.0 latency = 0.2
    assert sig.norepinephrine <= 0.25


# ===== P5-A sub-rule 2 alignment (real consequences vs LLM appraisal) =====


def test_signal_varies_with_real_outcomes_not_constant():
    """P5-A core: signal must vary with real outcomes (not constant noise)."""
    sigs = []
    for tick in range(20):
        outcome = (_success_outcome() if tick % 3 != 0 else _failure_outcome())
        sig = compute_rpe(0.5, outcome, _good_continuity(),
                          _good_conflict(), RealRPEConfig(), tick_id=tick)
        sigs.append(sig.dopamine)
    # dopamine must have variance > 0.05 across real outcomes
    assert max(sigs) - min(sigs) > 0.1


def test_cortisol_tracks_unresolved_conflict():
    """P5-A core: cortisol must correlate with conflict resolution (not noise)."""
    sigs = []
    efficiencies = [1.0, 0.5, 0.0]
    candidates = 4
    for eff in efficiencies:
        accepted = int(round(candidates * eff))
        suppressed = candidates - accepted
        conflict = ConflictResolution(candidates, accepted, suppressed, eff)
        sig = compute_rpe(0.5, _success_outcome(), _good_continuity(),
                          conflict, RealRPEConfig())
        sigs.append(sig.cortisol)
    # cortisol must strictly rise as efficiency drops (more unresolved)
    assert sigs[0] < sigs[1] < sigs[2]