from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.thought_gating import (
    ContinuationPressureState,
    SelectedStimulusSummary,
    ThoughtGateResult,
    ThoughtGatingConfig,
    ThoughtGatingError,
)


def _build_selected_stimulus() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.7,
        novelty_signal=0.6,
        sensitization_signal=0.2,
    )


def test_selected_stimulus_summary_is_immutable_and_range_checked() -> None:
    summary = _build_selected_stimulus()

    with pytest.raises(FrozenInstanceError):
        summary.source_kind = "changed"

    with pytest.raises(ThoughtGatingError, match="stimulus_intensity"):
        SelectedStimulusSummary(
            stimulus_id="stimulus:bad",
            source_kind="external_text",
            source_channel_id="cli",
            stimulus_intensity=1.2,
        )


def test_thought_gating_config_requires_fixed_learned_policy_surface() -> None:
    config = ThoughtGatingConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        continuation_state_bootstrap_id="continuation-bootstrap:v1",
        mandatory_learned_parameters=(
            "gate_policy",
            "continuation_policy",
            "signal_normalization_policy",
        ),
    )

    assert config.continuation_state_bootstrap_id == "continuation-bootstrap:v1"

    with pytest.raises(ThoughtGatingError, match="mandatory learned-parameter categories"):
        ThoughtGatingConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            continuation_state_bootstrap_id="continuation-bootstrap:v1",
            mandatory_learned_parameters=(
                "gate_policy",
                "continuation_policy",
            ),
        )


def test_thought_gate_result_requires_fixed_no_fire_taxonomy() -> None:
    result = ThoughtGateResult(
        result_id="thought-gate-result:001",
        source_conscious_state_id="conscious-state:001",
        source_signal_snapshot_id="gate-snapshot:001",
        decision="no_fire",
        gate_score=0.3,
        trigger_reason=None,
        dominant_reason="gate_score_too_low",
        blocked_reasons=("gate_score_too_low",),
        contributing_signals={"stimulus_signal": 0.2},
        selected_stimuli=(_build_selected_stimulus(),),
        no_fire_reason="gate_score_too_low",
        tick_id=9,
    )

    assert result.no_fire_reason == "gate_score_too_low"

    with pytest.raises(ThoughtGatingError, match="fixed no_fire taxonomy"):
        ThoughtGateResult(
            result_id="thought-gate-result:bad",
            source_conscious_state_id="conscious-state:001",
            source_signal_snapshot_id="gate-snapshot:001",
            decision="no_fire",
            gate_score=0.2,
            trigger_reason=None,
            dominant_reason="bad",
            blocked_reasons=("bad",),
            contributing_signals={"stimulus_signal": 0.2},
            selected_stimuli=(_build_selected_stimulus(),),
            no_fire_reason="free_text_reason",
            tick_id=9,
        )


def test_active_continuation_pressure_requires_origin_reason_and_expiry() -> None:
    state = ContinuationPressureState(
        active=True,
        level=0.7,
        origin_thought_id="thought:001",
        reason="unfinished_reflection",
        expires_at_tick=12,
        carry_count=1,
    )

    assert state.origin_thought_id == "thought:001"

    with pytest.raises(ThoughtGatingError, match="origin_thought_id"):
        ContinuationPressureState(
            active=True,
            level=0.4,
            reason="unfinished_reflection",
            expires_at_tick=12,
            carry_count=1,
        )
