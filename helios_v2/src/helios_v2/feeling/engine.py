"""Owner: interoceptive feeling layer.

Owns:
- batch-level feeling update orchestration
- construction-path invocation order
- request and publication op construction

Does not own:
- permanent feeling strategy semantics
- memory tagging
- action gating
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.neuromodulation import NeuromodulatorState
from helios_v2.sensory import Stimulus

from .contracts import (
    InteroceptiveFeelingAPI,
    InteroceptiveFeelingConfig,
    InteroceptiveFeelingError,
    InteroceptiveFeelingState,
    InteroceptiveFeelingVector,
    PublishInteroceptiveFeelingStateOp,
    UpdateInteroceptiveFeelingOp,
    validate_internal_body_signal,
)


def _validate_neuromodulator_state(state: NeuromodulatorState) -> None:
    if not state.state_id:
        raise InteroceptiveFeelingError("NeuromodulatorState must declare a non-empty state_id")
    if not state.source_appraisal_batch_id:
        raise InteroceptiveFeelingError("NeuromodulatorState must declare a non-empty source_appraisal_batch_id")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(float(value), high))


@runtime_checkable
class FeelingConstructionPath(Protocol):
    """Owner: interoceptive feeling layer.

    Purpose:
        Produce the next feeling vector from validated upstream state and owner config.
    """

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        """Owner: interoceptive feeling layer.

        Purpose:
            Produce the next dimensional feeling vector.

        Inputs:
            One validated `NeuromodulatorState`, optional validated internal signals, one owner config, and an optional tick id.

        Returns:
            One `InteroceptiveFeelingVector` within contract range.

        Raises:
            InteroceptiveFeelingError if the required construction capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved construction semantics are not guessed here.
        """


@runtime_checkable
class DominantDimensionReporter(Protocol):
    """Owner: interoceptive feeling layer.

    Purpose:
        Report dominant dimensions for publication diagnostics without hardcoding ranking or threshold semantics.
    """

    def report_dominant_dimensions(
        self,
        state: InteroceptiveFeelingState,
        config: InteroceptiveFeelingConfig,
    ) -> tuple[str, ...]:
        """Owner: interoceptive feeling layer.

        Purpose:
            Report the dimension names that should appear as dominant in publication diagnostics.

        Inputs:
            One `InteroceptiveFeelingState` and the owner config used to construct it.

        Returns:
            A stable tuple of dominant dimension names.

        Raises:
            InteroceptiveFeelingError if dominant-dimension reporting cannot proceed safely.

        Notes:
            This interface keeps unresolved reporting semantics out of the public owner skeleton.
        """


@dataclass
class InteroceptiveFeelingEngine(InteroceptiveFeelingAPI):
    """Owner: interoceptive feeling layer.

    Purpose:
        Execute feeling-state updates using injected construction and reporting collaborators.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: InteroceptiveFeelingConfig
    construction_path: FeelingConstructionPath
    dominant_dimension_reporter: DominantDimensionReporter

    def update_state(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...] = (),
        tick_id: int | None = None,
    ) -> InteroceptiveFeelingState:
        """Owner: interoceptive feeling layer.

        Purpose:
            Consume one neuromodulator state snapshot and optional internal signals and return one feeling-state snapshot.

        Inputs:
            One `NeuromodulatorState`, optional body/interoceptive `Stimulus` values, and an optional runtime tick id.

        Returns:
            An `InteroceptiveFeelingState` containing the owner-produced dimensional feeling vector.

        Raises:
            InteroceptiveFeelingError when input invariants or construction-path outputs are invalid.

        Notes:
            Remaining unresolved feeling semantics stay inside the injected construction path.
        """

        _validate_neuromodulator_state(neuromodulator_state)
        for signal in internal_signals:
            validate_internal_body_signal(signal)
        feeling = self.construction_path.construct_feeling(
            neuromodulator_state,
            internal_signals,
            self.config,
            tick_id,
        )
        return InteroceptiveFeelingState(
            state_id=f"interoceptive-feeling-state:{neuromodulator_state.state_id}:{tick_id if tick_id is not None else 'na'}",
            source_neuromodulator_state_id=neuromodulator_state.state_id,
            feeling=feeling,
            tick_id=tick_id,
        )

    def build_update_op(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...] = (),
    ) -> UpdateInteroceptiveFeelingOp:
        """Owner: interoceptive feeling layer.

        Purpose:
            Build the request op describing one feeling update request.

        Inputs:
            One `NeuromodulatorState` and optional internal body signals.

        Returns:
            An `UpdateInteroceptiveFeelingOp` summarizing request identity and optional internal-signal count.

        Raises:
            InteroceptiveFeelingError if the request is malformed.

        Notes:
            This method validates upstream provenance and input eligibility before creating the request op.
        """

        _validate_neuromodulator_state(neuromodulator_state)
        for signal in internal_signals:
            validate_internal_body_signal(signal)
        return UpdateInteroceptiveFeelingOp(
            op_name="update_interoceptive_feeling",
            owner="interoceptive_feeling_layer",
            neuromodulator_state_id=neuromodulator_state.state_id,
            internal_signal_count=len(internal_signals),
        )

    def build_publish_state_op(self, state: InteroceptiveFeelingState) -> PublishInteroceptiveFeelingStateOp:
        """Owner: interoceptive feeling layer.

        Purpose:
            Build the publication op for one feeling-state snapshot.

        Inputs:
            An `InteroceptiveFeelingState` produced by this owner.

        Returns:
            A `PublishInteroceptiveFeelingStateOp` summarizing publication metadata.

        Raises:
            InteroceptiveFeelingError if the state is malformed.

        Notes:
            Dominant-dimension reporting stays injectable until the unresolved semantics are confirmed.
        """

        if not state.state_id or not state.source_neuromodulator_state_id:
            raise InteroceptiveFeelingError("InteroceptiveFeelingState contains incomplete provenance")
        dominant_dimensions = self.dominant_dimension_reporter.report_dominant_dimensions(state, self.config)
        return PublishInteroceptiveFeelingStateOp(
            op_name="publish_interoceptive_feeling_state",
            owner="interoceptive_feeling_layer",
            state_id=state.state_id,
            source_neuromodulator_state_id=state.source_neuromodulator_state_id,
            dominant_dimensions=tuple(sorted(dominant_dimensions)),
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(float(value), high))


@dataclass
class NeuromodulatorDerivedFeelingConstructionPath(FeelingConstructionPath):
    """Owner: interoceptive feeling layer (R38).

    Purpose:
        Derive the next subjective body-feeling vector from the real `04` neuromodulator state
        around the configured baseline, replacing the constant first-version shim so the real
        modulatory state shapes feeling. This is the owner's core semantic (subjectivizing
        neuromodulator state into feeling), so the mapping lives here, in the `05` owner, not in
        composition glue.

    Failure semantics:
        A malformed neuromodulator state is rejected by the `05` engine before this path runs.
        This path is a total deterministic function of the state + config; it never branches into
        a degraded mode and never diverges outside the legal range (every dimension is clamped).

    Notes:
        Stateless by design: it reads no prior-tick feeling (true dual-timescale feeling
        persistence is a later slice). It derives from the neuromodulator levels only and ignores
        `internal_signals`/`tick_id` this slice (integrating real interoceptive signals is a later
        slice). The per-dimension coupling coefficients are explicit bounded first-version
        constants organized under the config's declared learned-parameter categories
        (`feeling_mapping_strength` for the direct level->dimension gains, `feeling_coupling_strength`
        for the cross-channel up/down combinations); a later P5 slice tunes them without changing
        the equation shape. The mapping is a fixed linear combination plus clamp -- no NN, no
        hidden branch.
    """

    # valence: reward/pleasure/well-being up; stress down
    dopamine_to_valence: float = 0.30
    opioid_to_valence: float = 0.15
    serotonin_to_valence: float = 0.15
    cortisol_to_valence: float = 0.30
    # arousal: alerting/excitation up
    norepinephrine_to_arousal: float = 0.40
    excitation_to_arousal: float = 0.20
    # tension: stress/alerting up
    cortisol_to_tension: float = 0.40
    norepinephrine_to_tension: float = 0.20
    # comfort: analgesia/bonding/calm up; stress down
    opioid_to_comfort: float = 0.30
    oxytocin_to_comfort: float = 0.20
    serotonin_to_comfort: float = 0.15
    cortisol_to_comfort: float = 0.30
    # pain_like: stress up; opioid analgesia down
    cortisol_to_pain_like: float = 0.40
    opioid_to_pain_like: float = 0.35
    # social_safety: bonding up; stress down
    oxytocin_to_social_safety: float = 0.40
    serotonin_to_social_safety: float = 0.15
    cortisol_to_social_safety: float = 0.25
    # fatigue: weak first-version coupling (real fatigue needs cross-tick accumulation, deferred)
    inhibition_to_fatigue: float = 0.20
    excitation_to_fatigue: float = 0.20

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        del internal_signals, tick_id
        levels = neuromodulator_state.levels
        base = config.baseline_feeling
        low = config.legal_min
        high = config.legal_max
        return InteroceptiveFeelingVector(
            valence=_clamp(
                base.valence
                + self.dopamine_to_valence * levels.dopamine
                + self.opioid_to_valence * levels.opioid_tone
                + self.serotonin_to_valence * levels.serotonin
                - self.cortisol_to_valence * levels.cortisol,
                low.valence,
                high.valence,
            ),
            arousal=_clamp(
                base.arousal
                + self.norepinephrine_to_arousal * levels.norepinephrine
                + self.excitation_to_arousal * levels.excitation,
                low.arousal,
                high.arousal,
            ),
            tension=_clamp(
                base.tension
                + self.cortisol_to_tension * levels.cortisol
                + self.norepinephrine_to_tension * levels.norepinephrine,
                low.tension,
                high.tension,
            ),
            comfort=_clamp(
                base.comfort
                + self.opioid_to_comfort * levels.opioid_tone
                + self.oxytocin_to_comfort * levels.oxytocin
                + self.serotonin_to_comfort * levels.serotonin
                - self.cortisol_to_comfort * levels.cortisol,
                low.comfort,
                high.comfort,
            ),
            fatigue=_clamp(
                base.fatigue
                + self.inhibition_to_fatigue * levels.inhibition
                - self.excitation_to_fatigue * levels.excitation,
                low.fatigue,
                high.fatigue,
            ),
            pain_like=_clamp(
                base.pain_like
                + self.cortisol_to_pain_like * levels.cortisol
                - self.opioid_to_pain_like * levels.opioid_tone,
                low.pain_like,
                high.pain_like,
            ),
            social_safety=_clamp(
                base.social_safety
                + self.oxytocin_to_social_safety * levels.oxytocin
                + self.serotonin_to_social_safety * levels.serotonin
                - self.cortisol_to_social_safety * levels.cortisol,
                low.social_safety,
                high.social_safety,
            ),
        )


@dataclass
class NeuromodulatorDerivedFeelingConstructionPath(FeelingConstructionPath):
    """Owner: interoceptive feeling layer (R38).

    Purpose:
        Derive the next interoceptive feeling vector from the real `04` neuromodulator state
        around the configured baseline feeling, replacing the constant first-version shim so the
        real neuromodulator state (the R36 appraisal-derived levels) measurably shapes subjective
        body feeling.

    Failure semantics:
        A malformed neuromodulator state is rejected by the `05` engine before this path runs.
        This path is a total deterministic function of the neuromodulator levels + config; it
        never branches into a degraded mode and never diverges outside the configured legal range
        (every dimension is clamped).

    Notes:
        The channel-to-dimension mapping is the feeling-subjectivation semantic and is owned here,
        inside the `05` owner, not in composition glue. Stateless by design: it reads no prior-tick
        feeling (true dual-timescale `feeling_persistence` is a later slice) and does not consume
        `internal_signals` in this slice (real interoceptive-signal integration is a later slice).
        The per-dimension coupling coefficients are explicit bounded first-version constants
        organized under the config's declared learned-parameter categories
        (`feeling_mapping_strength`/`feeling_coupling_strength`); a later P5 slice tunes them
        without changing the equation shape. The mapping is a fixed linear combination plus clamp --
        no NN, no hidden branch. Each channel contributes via its level relative to a neutral
        reference of 0.0 in this first version.
    """

    # valence: positive affect from reward/opioid/serotonergic tone, lowered by stress
    valence_from_dopamine: float = 0.30
    valence_from_opioid_tone: float = 0.15
    valence_from_serotonin: float = 0.15
    valence_from_cortisol: float = 0.30
    # arousal: alertness/activation
    arousal_from_norepinephrine: float = 0.40
    arousal_from_excitation: float = 0.20
    # tension: stress/alertness load
    tension_from_cortisol: float = 0.40
    tension_from_norepinephrine: float = 0.20
    # comfort: analgesic/affiliative/calm tone, lowered by stress
    comfort_from_opioid_tone: float = 0.30
    comfort_from_oxytocin: float = 0.20
    comfort_from_serotonin: float = 0.15
    comfort_from_cortisol: float = 0.30
    # pain_like: stress-driven, lowered by opioid analgesia
    pain_like_from_cortisol: float = 0.40
    pain_like_from_opioid_tone: float = 0.35
    # social_safety: affiliative bonding, lowered by stress
    social_safety_from_oxytocin: float = 0.40
    social_safety_from_serotonin: float = 0.15
    social_safety_from_cortisol: float = 0.25
    # fatigue: weak first-version coupling (real fatigue needs cross-tick accumulation; deferred)
    fatigue_from_inhibition: float = 0.20
    fatigue_from_excitation: float = 0.20

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
    ) -> InteroceptiveFeelingVector:
        del internal_signals, tick_id
        levels = neuromodulator_state.levels
        base = config.baseline_feeling
        low = config.legal_min
        high = config.legal_max
        return InteroceptiveFeelingVector(
            valence=_clamp(
                base.valence
                + self.valence_from_dopamine * levels.dopamine
                + self.valence_from_opioid_tone * levels.opioid_tone
                + self.valence_from_serotonin * levels.serotonin
                - self.valence_from_cortisol * levels.cortisol,
                low.valence,
                high.valence,
            ),
            arousal=_clamp(
                base.arousal
                + self.arousal_from_norepinephrine * levels.norepinephrine
                + self.arousal_from_excitation * levels.excitation,
                low.arousal,
                high.arousal,
            ),
            tension=_clamp(
                base.tension
                + self.tension_from_cortisol * levels.cortisol
                + self.tension_from_norepinephrine * levels.norepinephrine,
                low.tension,
                high.tension,
            ),
            comfort=_clamp(
                base.comfort
                + self.comfort_from_opioid_tone * levels.opioid_tone
                + self.comfort_from_oxytocin * levels.oxytocin
                + self.comfort_from_serotonin * levels.serotonin
                - self.comfort_from_cortisol * levels.cortisol,
                low.comfort,
                high.comfort,
            ),
            fatigue=_clamp(
                base.fatigue
                + self.fatigue_from_inhibition * levels.inhibition
                - self.fatigue_from_excitation * levels.excitation,
                low.fatigue,
                high.fatigue,
            ),
            pain_like=_clamp(
                base.pain_like
                + self.pain_like_from_cortisol * levels.cortisol
                - self.pain_like_from_opioid_tone * levels.opioid_tone,
                low.pain_like,
                high.pain_like,
            ),
            social_safety=_clamp(
                base.social_safety
                + self.social_safety_from_oxytocin * levels.oxytocin
                + self.social_safety_from_serotonin * levels.serotonin
                - self.social_safety_from_cortisol * levels.cortisol,
                low.social_safety,
                high.social_safety,
            ),
        )
