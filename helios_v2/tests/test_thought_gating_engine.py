from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.consciousness import ConsciousState, ReportableConsciousContent
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.thought_gating import (
    ContinuationPressureState,
    FirstVersionThoughtGatePath,
    SelectedStimulusSummary,
    ThoughtGateResult,
    ThoughtGateSignalSnapshot,
    ThoughtGatingConfig,
    ThoughtGatingEngine,
    ThoughtGatingError,
)
from helios_v2.thought_gating.engine import ThoughtGatePath


def _build_config() -> ThoughtGatingConfig:
    return ThoughtGatingConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        continuation_state_bootstrap_id="continuation-bootstrap:v1",
        mandatory_learned_parameters=(
            "gate_policy",
            "continuation_policy",
            "signal_normalization_policy",
        ),
    )


def _build_conscious_state(commit_status: str = "committed") -> ConsciousState:
    focal_content = None
    if commit_status == "committed":
        focal_content = ReportableConsciousContent(
            content_id="conscious-content:001",
            source_material_id="conscious-material:001",
            source_workspace_candidate_id="workspace-candidate:001",
            source_memory_candidate_id="memory-candidate:001",
            source_feeling_state_id="feeling-state:001",
            content_kind="situational-summary",
            focal_summary="Current focal content from test fixture",
            affect_trace=InteroceptiveFeelingVector(
                valence=0.4,
                arousal=0.6,
                tension=0.3,
                comfort=0.2,
                fatigue=0.1,
                pain_like=0.0,
                social_safety=0.5,
            ),
            salient_tokens=("fixture",),
            tick_id=9,
        )
    return ConsciousState(
        state_id="conscious-state:001",
        commit_status=commit_status,
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        focal_content=focal_content,
        supporting_context=(),
        no_commit_reason="semantic_conflict_unresolved" if commit_status == "no_commit" else None,
        tick_id=9,
    )


def _build_signal_snapshot() -> ThoughtGateSignalSnapshot:
    return ThoughtGateSignalSnapshot(
        snapshot_id="gate-snapshot:001",
        source_conscious_state_id="conscious-state:001",
        workload_pressure=0.2,
        global_activation_level=0.8,
        temporal_signal=0.5,
        drive_urgency_signal=0.6,
        dmn_available=True,
        selected_stimuli=(
            SelectedStimulusSummary(
                stimulus_id="stimulus:001",
                source_kind="external_text",
                source_channel_id="cli",
                stimulus_intensity=0.8,
                novelty_signal=0.6,
                sensitization_signal=0.1,
            ),
        ),
        tick_id=9,
    )


@dataclass
class RecordingThoughtGatePath(ThoughtGatePath):
    recorded_tick_id: int | None = None

    def evaluate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        config: ThoughtGatingConfig,
        tick_id: int | None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        assert conscious_state.state_id == "conscious-state:001"
        assert signal_snapshot.snapshot_id == "gate-snapshot:001"
        assert prior_continuation_state.active is False
        assert config.continuation_state_bootstrap_id == "continuation-bootstrap:v1"
        self.recorded_tick_id = tick_id
        return (
            ThoughtGateResult(
                result_id="thought-gate-result:001",
                source_conscious_state_id=conscious_state.state_id,
                source_signal_snapshot_id=signal_snapshot.snapshot_id,
                decision="fire",
                gate_score=0.9,
                trigger_reason="salient_stimulus",
                dominant_reason="salient_stimulus",
                blocked_reasons=(),
                contributing_signals={"stimulus_signal": 0.8},
                selected_stimuli=signal_snapshot.selected_stimuli,
                no_fire_reason=None,
                tick_id=tick_id,
            ),
            ContinuationPressureState.inactive(),
        )


def test_thought_gating_engine_validates_inputs_and_builds_ops() -> None:
    path = RecordingThoughtGatePath()
    engine = ThoughtGatingEngine(config=_build_config(), gate_path=path)
    conscious_state = _build_conscious_state()
    signal_snapshot = _build_signal_snapshot()
    prior_continuation = ContinuationPressureState.inactive()

    evaluate_op = engine.build_evaluate_op(conscious_state, signal_snapshot, prior_continuation)
    result, continuation_state = engine.evaluate_gate(
        conscious_state,
        signal_snapshot,
        prior_continuation,
        tick_id=9,
    )
    publish_result_op = engine.build_publish_gate_result_op(result)
    publish_continuation_op = engine.build_publish_continuation_op(continuation_state)

    assert evaluate_op.op_name == "evaluate_thought_gate"
    assert path.recorded_tick_id == 9
    assert publish_result_op.decision == "fire"
    assert publish_continuation_op.active is False


def test_first_version_thought_gate_path_returns_no_fire_for_ineligible_conscious_state() -> None:
    engine = ThoughtGatingEngine(
        config=_build_config(),
        gate_path=FirstVersionThoughtGatePath(),
    )

    result, continuation_state = engine.evaluate_gate(
        _build_conscious_state(commit_status="no_commit"),
        _build_signal_snapshot(),
        ContinuationPressureState.inactive(),
        tick_id=9,
    )

    assert result.decision == "no_fire"
    assert result.no_fire_reason == "conscious_content_not_eligible"
    assert continuation_state.active is False


def test_first_version_thought_gate_path_decays_prior_continuation_when_no_fire() -> None:
    engine = ThoughtGatingEngine(
        config=_build_config(),
        gate_path=FirstVersionThoughtGatePath(),
    )
    signal_snapshot = ThoughtGateSignalSnapshot(
        snapshot_id="gate-snapshot:idle",
        source_conscious_state_id="conscious-state:001",
        workload_pressure=0.1,
        global_activation_level=0.2,
        temporal_signal=0.2,
        drive_urgency_signal=0.1,
        dmn_available=True,
        selected_stimuli=(),
        tick_id=9,
    )
    prior_continuation = ContinuationPressureState(
        active=True,
        level=0.4,
        origin_thought_id="thought:carry",
        reason="unfinished_reflection",
        expires_at_tick=12,
        carry_count=1,
    )

    result, continuation_state = engine.evaluate_gate(
        _build_conscious_state(),
        signal_snapshot,
        prior_continuation,
        tick_id=9,
    )

    assert result.decision == "no_fire"
    assert result.no_fire_reason == "gate_score_too_low"
    assert continuation_state.active is True
    assert continuation_state.level < prior_continuation.level
    assert continuation_state.carry_count == 2


def test_engine_rejects_mismatched_signal_snapshot_provenance() -> None:
    engine = ThoughtGatingEngine(config=_build_config(), gate_path=FirstVersionThoughtGatePath())
    bad_snapshot = ThoughtGateSignalSnapshot(
        snapshot_id="gate-snapshot:bad",
        source_conscious_state_id="conscious-state:other",
        workload_pressure=0.1,
        global_activation_level=0.2,
        temporal_signal=0.2,
        drive_urgency_signal=0.1,
        dmn_available=True,
    )

    with pytest.raises(ThoughtGatingError, match="source conscious-state id"):
        engine.evaluate_gate(
            _build_conscious_state(),
            bad_snapshot,
            ContinuationPressureState.inactive(),
            tick_id=9,
        )
