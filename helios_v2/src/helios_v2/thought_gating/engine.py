"""Owner: thought-gating and continuation-pressure layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.consciousness import ConsciousState

from .contracts import (
    ContinuationPressureState,
    EvaluateThoughtGateOp,
    PublishContinuationPressureOp,
    PublishThoughtGateResultOp,
    ThoughtGateResult,
    ThoughtGateSignalSnapshot,
    ThoughtGatingAPI,
    ThoughtGatingConfig,
    ThoughtGatingError,
)


def _clamp(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _validate_conscious_state(state: ConsciousState) -> None:
    if not state.state_id:
        raise ThoughtGatingError("ConsciousState must declare a non-empty state_id")
    if not state.source_workspace_candidate_set_id:
        raise ThoughtGatingError(
            "ConsciousState must declare a non-empty source_workspace_candidate_set_id"
        )
    if not state.source_working_state_id:
        raise ThoughtGatingError(
            "ConsciousState must declare a non-empty source_working_state_id"
        )


def _validate_signal_snapshot(
    signal_snapshot: ThoughtGateSignalSnapshot,
    conscious_state: ConsciousState,
) -> None:
    if signal_snapshot.source_conscious_state_id != conscious_state.state_id:
        raise ThoughtGatingError(
            "ThoughtGateSignalSnapshot must preserve the source conscious-state id of the current cycle"
        )


def _validate_result(
    result: ThoughtGateResult,
    conscious_state: ConsciousState,
    signal_snapshot: ThoughtGateSignalSnapshot,
) -> None:
    if result.source_conscious_state_id != conscious_state.state_id:
        raise ThoughtGatingError(
            "ThoughtGateResult must preserve the source conscious-state id of the current cycle"
        )
    if result.source_signal_snapshot_id != signal_snapshot.snapshot_id:
        raise ThoughtGatingError(
            "ThoughtGateResult must preserve the source signal-snapshot id of the current cycle"
        )
    if result.selected_stimuli != signal_snapshot.selected_stimuli:
        raise ThoughtGatingError(
            "ThoughtGateResult must preserve the bounded selected-stimulus summaries of the current cycle"
        )


@runtime_checkable
class ThoughtGatePath(Protocol):
    def evaluate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        config: ThoughtGatingConfig,
        tick_id: int | None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        """Return one gate result and one next continuation state derived only from validated inputs."""


@dataclass(frozen=True)
class _FirstVersionDecisionPolicy:
    fire_threshold: float = 0.55
    resource_pressure_block_threshold: float = 0.9
    idle_decay: float = 0.1


def _build_next_continuation_state(
    prior_continuation_state: ContinuationPressureState,
    policy: _FirstVersionDecisionPolicy,
    *,
    tick_id: int | None,
) -> ContinuationPressureState:
    if not prior_continuation_state.active:
        return ContinuationPressureState.inactive()
    if prior_continuation_state.expires_at_tick and tick_id is not None:
        if tick_id >= prior_continuation_state.expires_at_tick:
            return ContinuationPressureState.inactive()
    decayed_level = _clamp(prior_continuation_state.level - policy.idle_decay)
    if decayed_level <= 0.0:
        return ContinuationPressureState.inactive()
    return ContinuationPressureState(
        active=True,
        level=decayed_level,
        origin_thought_id=prior_continuation_state.origin_thought_id,
        reason=prior_continuation_state.reason,
        expires_at_tick=prior_continuation_state.expires_at_tick,
        carry_count=prior_continuation_state.carry_count + 1,
    )


def _evaluate_first_version_gate(
    conscious_state: ConsciousState,
    signal_snapshot: ThoughtGateSignalSnapshot,
    prior_continuation_state: ContinuationPressureState,
    policy: _FirstVersionDecisionPolicy,
    tick_id: int | None,
    *,
    arousal_gain: float,
) -> tuple[ThoughtGateResult, ContinuationPressureState]:
    """Shared deterministic gate evaluation.

    The first-version path passes ``arousal_gain=0.0`` (no neuromodulatory coupling, identical
    to the original behavior). The arousal-aware path passes a positive bounded ``arousal_gain``;
    when the snapshot carries a ``neuromodulatory_arousal`` fact, a single non-negative term
    ``arousal_gain * arousal`` is added to the gate score (the existing terms, including
    ``global_activation_level``, are untouched) and the raw fact is recorded as a contributing
    signal. The term cannot solely force a fire (its weight is below the fire threshold) and,
    being additive and non-negative, cannot suppress a fire other signals already justify.
    """

    next_continuation = _build_next_continuation_state(prior_continuation_state, policy, tick_id=tick_id)
    continuation_signal = next_continuation.level if next_continuation.active else 0.0
    stimulus_signal = max(
        (summary.stimulus_intensity for summary in signal_snapshot.selected_stimuli),
        default=0.0,
    )
    arousal = signal_snapshot.neuromodulatory_arousal
    arousal_active = arousal is not None and arousal_gain > 0.0
    arousal_contribution = arousal_gain * arousal if arousal_active else 0.0
    gate_score = _clamp(
        stimulus_signal * 0.30
        + continuation_signal * 0.30
        + signal_snapshot.global_activation_level * 0.20
        + signal_snapshot.drive_urgency_signal * 0.10
        + signal_snapshot.temporal_signal * 0.10
        + (0.10 if signal_snapshot.dmn_available else 0.0)
        - signal_snapshot.workload_pressure * 0.45
        + arousal_contribution
    )
    contributing_signals = {
        "stimulus_signal": stimulus_signal,
        "continuation_signal": continuation_signal,
        "global_activation_level": signal_snapshot.global_activation_level,
        "drive_urgency_signal": signal_snapshot.drive_urgency_signal,
        "temporal_signal": signal_snapshot.temporal_signal,
        "workload_pressure": signal_snapshot.workload_pressure,
    }
    if arousal_active:
        contributing_signals["neuromodulatory_arousal"] = arousal

    decision = "fire"
    no_fire_reason = None
    trigger_reason = None
    dominant_reason = None
    blocked_reasons: tuple[str, ...] = ()
    if conscious_state.commit_status != "committed":
        decision = "no_fire"
        no_fire_reason = "conscious_content_not_eligible"
        dominant_reason = "conscious_content_not_eligible"
        blocked_reasons = ("conscious_content_not_eligible",)
    elif (
        signal_snapshot.workload_pressure >= policy.resource_pressure_block_threshold
        and continuation_signal < 0.25
    ):
        decision = "no_fire"
        no_fire_reason = "resource_pressure_too_high"
        dominant_reason = "resource_pressure_too_high"
        blocked_reasons = ("resource_pressure_too_high",)
    elif not signal_snapshot.selected_stimuli and continuation_signal <= 0.0:
        decision = "no_fire"
        no_fire_reason = "continuation_absent_and_no_stimulus"
        dominant_reason = "continuation_absent_and_no_stimulus"
        blocked_reasons = ("continuation_absent_and_no_stimulus",)
    elif gate_score < policy.fire_threshold:
        decision = "no_fire"
        no_fire_reason = "gate_score_too_low"
        dominant_reason = "gate_score_too_low"
        blocked_reasons = ("gate_score_too_low",)
    else:
        if continuation_signal >= stimulus_signal and continuation_signal > 0.0:
            trigger_reason = "continuation_pressure"
            dominant_reason = "continuation_pressure"
        elif stimulus_signal > 0.0:
            trigger_reason = "salient_stimulus"
            dominant_reason = "salient_stimulus"
        else:
            trigger_reason = "mixed_signal"
            dominant_reason = "mixed_signal"

    return (
        ThoughtGateResult(
            result_id=f"thought-gate-result:{signal_snapshot.snapshot_id}",
            source_conscious_state_id=conscious_state.state_id,
            source_signal_snapshot_id=signal_snapshot.snapshot_id,
            decision=decision,
            gate_score=gate_score,
            trigger_reason=trigger_reason,
            dominant_reason=dominant_reason,
            blocked_reasons=blocked_reasons,
            contributing_signals=contributing_signals,
            selected_stimuli=signal_snapshot.selected_stimuli,
            no_fire_reason=no_fire_reason,
            tick_id=tick_id,
        ),
        next_continuation,
    )


@dataclass
class FirstVersionThoughtGatePath(ThoughtGatePath):
    """Owner-private deterministic first-version thought-gate path."""

    policy: _FirstVersionDecisionPolicy = _FirstVersionDecisionPolicy()

    def evaluate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        config: ThoughtGatingConfig,
        tick_id: int | None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        del config
        return _evaluate_first_version_gate(
            conscious_state,
            signal_snapshot,
            prior_continuation_state,
            self.policy,
            tick_id,
            arousal_gain=0.0,
        )


@dataclass
class ArousalAwareThoughtGatePath(ThoughtGatePath):
    """Owner-private deterministic arousal-aware thought-gate path (R37).

    Identical to the first-version path except that, when the gate-signal snapshot carries a
    `neuromodulatory_arousal` fact (the real `04` norepinephrine level forwarded by composition),
    a single non-negative bounded term `arousal_gain * arousal` is added to the gate score. The
    mapping from the raw arousal fact to gate influence is owned here, in the `09` owner, not in
    composition glue. `arousal_gain` is an explicit bounded first-version constant under the
    `gate_policy` learned-parameter category (P5-learnable later); it is small enough that arousal
    alone can neither cross the fire threshold nor suppress a fire other signals justify. The path
    reads no prior-tick state (stateless).
    """

    policy: _FirstVersionDecisionPolicy = _FirstVersionDecisionPolicy()
    arousal_gain: float = 0.15

    def evaluate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        config: ThoughtGatingConfig,
        tick_id: int | None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        del config
        return _evaluate_first_version_gate(
            conscious_state,
            signal_snapshot,
            prior_continuation_state,
            self.policy,
            tick_id,
            arousal_gain=self.arousal_gain,
        )


@dataclass
class ThoughtGatingEngine(ThoughtGatingAPI):
    """Execute one current-cycle thought-gate evaluation using an injected private gate path."""

    config: ThoughtGatingConfig
    gate_path: ThoughtGatePath

    def evaluate_gate(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
        tick_id: int | None = None,
    ) -> tuple[ThoughtGateResult, ContinuationPressureState]:
        _validate_conscious_state(conscious_state)
        _validate_signal_snapshot(signal_snapshot, conscious_state)
        result, continuation_state = self.gate_path.evaluate(
            conscious_state,
            signal_snapshot,
            prior_continuation_state,
            self.config,
            tick_id,
        )
        _validate_result(result, conscious_state, signal_snapshot)
        return result, continuation_state

    def build_evaluate_op(
        self,
        conscious_state: ConsciousState,
        signal_snapshot: ThoughtGateSignalSnapshot,
        prior_continuation_state: ContinuationPressureState,
    ) -> EvaluateThoughtGateOp:
        _validate_conscious_state(conscious_state)
        _validate_signal_snapshot(signal_snapshot, conscious_state)
        return EvaluateThoughtGateOp(
            op_name="evaluate_thought_gate",
            owner="thought_gating_and_continuation_pressure",
            conscious_state_id=conscious_state.state_id,
            signal_snapshot_id=signal_snapshot.snapshot_id,
            prior_continuation_active=prior_continuation_state.active,
        )

    def build_publish_gate_result_op(
        self,
        result: ThoughtGateResult,
    ) -> PublishThoughtGateResultOp:
        if not result.result_id:
            raise ThoughtGatingError("ThoughtGateResult contains incomplete publication identity")
        return PublishThoughtGateResultOp(
            op_name="publish_thought_gate_result",
            owner="thought_gating_and_continuation_pressure",
            result_id=result.result_id,
            decision=result.decision,
            no_fire_reason=result.no_fire_reason,
        )

    def build_publish_continuation_op(
        self,
        continuation_state: ContinuationPressureState,
    ) -> PublishContinuationPressureOp:
        return PublishContinuationPressureOp(
            op_name="publish_continuation_pressure",
            owner="thought_gating_and_continuation_pressure",
            active=continuation_state.active,
            level=continuation_state.level,
            origin_thought_id=continuation_state.origin_thought_id,
        )
