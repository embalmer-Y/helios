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
        prior_feeling: "InteroceptiveFeelingVector | None" = None,
    ) -> InteroceptiveFeelingVector:
        """Owner: interoceptive feeling layer.

        Purpose:
            Produce the next dimensional feeling vector.

        Inputs:
            One validated `NeuromodulatorState`, optional validated internal signals, one owner
            config, an optional tick id, and the optional prior-tick `InteroceptiveFeelingVector`
            (`None` on a cold start or for a stateless path).

        Returns:
            One `InteroceptiveFeelingVector` within contract range.

        Raises:
            InteroceptiveFeelingError if the required construction capability is unavailable or unsafe.

        Notes:
            `prior_feeling` is additive (default `None`). A stateless path (constant or
            neuromodulator-derived target) must ignore it and reproduce its prior behavior
            byte-for-byte; a persistence (dual-timescale) path uses it as the integrator's prior,
            treating `None` as a cold start (the baseline feeling).
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
        prior_state: InteroceptiveFeelingState | None = None,
    ) -> InteroceptiveFeelingState:
        """Owner: interoceptive feeling layer.

        Purpose:
            Consume one neuromodulator state snapshot and optional internal signals and return one feeling-state snapshot.

        Inputs:
            One `NeuromodulatorState`, optional body/interoceptive `Stimulus` values, an optional
            runtime tick id, and the optional prior-tick `InteroceptiveFeelingState` (`None` on a
            cold start or for a stateless path).

        Returns:
            An `InteroceptiveFeelingState` containing the owner-produced dimensional feeling vector.

        Raises:
            InteroceptiveFeelingError when input invariants or construction-path outputs are invalid.

        Notes:
            `prior_state` is additive (default `None`); the engine forwards `prior_state.feeling`
            (or `None`) to the construction path. A stateless path ignores it; a dual-timescale
            persistence path uses it as the integrator's prior. Remaining unresolved feeling
            semantics stay inside the injected construction path.
        """

        _validate_neuromodulator_state(neuromodulator_state)
        for signal in internal_signals:
            validate_internal_body_signal(signal)
        prior_feeling = prior_state.feeling if prior_state is not None else None
        feeling = self.construction_path.construct_feeling(
            neuromodulator_state,
            internal_signals,
            self.config,
            tick_id,
            prior_feeling,
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
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        del internal_signals, tick_id, prior_feeling
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


# Reserved interoceptive-afferent metadata keys the `50` runtime interoceptive source sets on
# each interoceptive `RawSignal` (preserved verbatim by sensory normalization onto the `Stimulus`).
# These are owner-read keys for `05`: the feeling owner reads the bounded numeric pressure fact
# rather than parsing the human-readable content string. They mirror the `30` QoS reserved-key
# pattern (a string-keyed metadata fact, not a typed cross-owner contract field).
_PRESSURE_CHANNEL_METADATA_KEY = "pressure_channel"
_PRESSURE_VALUE_METADATA_KEY = "pressure_value"


_FEELING_DIMENSIONS: tuple[str, ...] = (
    "valence",
    "arousal",
    "tension",
    "comfort",
    "fatigue",
    "pain_like",
    "social_safety",
)


@dataclass
class PersistentFeelingConstructionPath(FeelingConstructionPath):
    """Owner: interoceptive feeling layer (R44).

    Purpose:
        Add the temporal (dual-timescale) layer the `05` contract already reserves
        (`feeling_persistence`). It wraps an inner `target_path` (the R38 neuromodulator-derived
        instantaneous target feeling) and applies a leaky-integrator step against the prior-tick
        feeling, so the felt body-state evolves across ticks instead of being recomputed from
        baseline each tick (the `05` mirror of R43's `04` dynamics; advancing FG-2).

    Failure semantics:
        Construction raises `InteroceptiveFeelingError` unless `0 < alpha_tonic < alpha_phasic <= 1`,
        so an unstable or non-decaying integrator cannot be assembled. The update itself is a total
        deterministic function; every dimension is clamped to the legal range, so it never diverges.

    Notes:
        The instantaneous target stays owned by the injected inner path; this owner-owned wrapper
        owns only the cross-tick carry/decay semantic. Per dimension:
        `next = clamp(prior + alpha_phasic * (target - prior) + alpha_tonic * (baseline - prior))`.
        A `None` `prior_feeling` is a cold start: the prior defaults to the baseline feeling, so the
        first tick is one integrator step from baseline (no fabricated history). The coefficients
        are explicit bounded first-version constants under the config's declared
        `feeling_persistence` learned-parameter category (P5-learnable later); they match R43's
        defaults so the two affect owners share one decay timescale. `internal_signals`/`tick_id`
        are forwarded to the inner path; real interoceptive-signal integration remains a later slice.
    """

    target_path: FeelingConstructionPath
    alpha_phasic: float = 0.6
    alpha_tonic: float = 0.1

    def __post_init__(self) -> None:
        if not (0.0 < self.alpha_tonic < self.alpha_phasic <= 1.0):
            raise InteroceptiveFeelingError(
                "PersistentFeelingConstructionPath requires 0 < alpha_tonic < alpha_phasic <= 1"
            )

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        """Return the next feeling as one leaky-integrator step from the prior toward the target.

        The inner target path produces the instantaneous neuromodulator-derived feeling; this
        method moves the prior feeling a phasic step toward that target and a tonic step toward the
        baseline, clamping each dimension. `prior_feeling is None` is a cold start (prior = baseline).
        """

        target = self.target_path.construct_feeling(
            neuromodulator_state, internal_signals, config, tick_id, None
        )
        prior = prior_feeling if prior_feeling is not None else config.baseline_feeling
        baseline = config.baseline_feeling
        low = config.legal_min
        high = config.legal_max
        next_values: dict[str, float] = {}
        for dimension in _FEELING_DIMENSIONS:
            prior_value = getattr(prior, dimension)
            target_value = getattr(target, dimension)
            baseline_value = getattr(baseline, dimension)
            stepped = (
                prior_value
                + self.alpha_phasic * (target_value - prior_value)
                + self.alpha_tonic * (baseline_value - prior_value)
            )
            next_values[dimension] = _clamp(
                round(stepped, 4), getattr(low, dimension), getattr(high, dimension)
            )
        return InteroceptiveFeelingVector(**next_values)


@dataclass
class InteroceptiveSignalModulatedFeelingConstructionPath(FeelingConstructionPath):
    """Owner: interoceptive feeling layer (R51).

    Purpose:
        Make the real interoceptive afferent shape the felt body-state. It wraps an inner
        `target_path` (the R38 neuromodulator-derived instantaneous feeling) and adds a bounded,
        non-negative, stress-directional per-dimension contribution derived from the real
        compute/runtime-pressure signals the `50` interoceptive source produces (delivered to `05`
        as `internal_signals` since R50), so the runtime's real internal condition measurably and
        traceably changes feeling in addition to the top-down `04`-derived target. This closes the
        consumption half of `gap_interoceptive_signal_source` and forms the first end-to-end FG-2
        causal chain (real machine condition -> `05` feeling -> `07` workspace competition).

    Failure semantics:
        Total deterministic function. An interoceptive stimulus without a recognized string
        `pressure_channel` or a numeric `pressure_value` in `[0,1]` contributes nothing (skipped),
        never raising and never fabricating a body condition. Every dimension is clamped to the
        configured legal range, so it never diverges.

    Notes:
        The body-signal-to-feeling mapping is owned here, inside the `05` owner (as the
        channel-to-dimension neuromodulator mapping already is); this path imports no interoception,
        appraisal, neuromodulation, or workspace owner and reads only the already-normalized
        `Stimulus` values it is handed. The contribution is additive over the inner target and never
        replaces it. The inner target path still owns the neuromodulator-derived component and still
        ignores `internal_signals`; this wrapper is the sole consumer of the afferent. When nested
        inside `PersistentFeelingConstructionPath` (the R44 carry), the body contribution flows
        through the same dual-timescale integrator as the neuromodulator component -- there is no
        second persistence mechanism. On empty/unrecognized `internal_signals` the result is the
        inner target byte-for-byte, so an assembly without an interoceptive source is unchanged.
        valence/comfort/social_safety are intentionally untouched in this first version, keeping the
        claim narrow and monotone (pressure can only push toward stress/load). The per-channel
        coefficients are explicit bounded first-version constants under the config's declared
        `feeling_coupling_strength` learned-parameter category (P5-learnable later).
    """

    target_path: FeelingConstructionPath
    # cpu pressure -> alertness/activation load
    cpu_to_arousal: float = 0.30
    cpu_to_tension: float = 0.20
    # memory pressure -> sustained load / fatigue
    memory_to_fatigue: float = 0.30
    memory_to_tension: float = 0.15
    # latency pressure -> sluggishness / fatigue
    latency_to_fatigue: float = 0.20
    latency_to_tension: float = 0.10
    # error pressure -> distress
    error_to_pain_like: float = 0.30
    error_to_tension: float = 0.20

    def construct_feeling(
        self,
        neuromodulator_state: NeuromodulatorState,
        internal_signals: tuple[Stimulus, ...],
        config: InteroceptiveFeelingConfig,
        tick_id: int | None,
        prior_feeling: InteroceptiveFeelingVector | None = None,
    ) -> InteroceptiveFeelingVector:
        """Return the inner neuromodulator-derived target plus the bounded interoceptive contribution.

        The inner target path produces the instantaneous neuromodulator-derived feeling (it ignores
        `internal_signals`); this method adds a non-negative stress-directional contribution from the
        recognized interoceptive pressure facts and clamps each dimension. Empty or unrecognized
        afferent reproduces the inner target byte-for-byte.
        """

        target = self.target_path.construct_feeling(
            neuromodulator_state, internal_signals, config, tick_id, prior_feeling
        )
        pressures = self._read_pressures(internal_signals)
        if not pressures:
            return target
        cpu = pressures.get("cpu", 0.0)
        memory = pressures.get("memory", 0.0)
        latency = pressures.get("latency", 0.0)
        error = pressures.get("error", 0.0)
        low = config.legal_min
        high = config.legal_max
        return InteroceptiveFeelingVector(
            valence=target.valence,
            arousal=_clamp(
                round(target.arousal + self.cpu_to_arousal * cpu, 4),
                low.arousal,
                high.arousal,
            ),
            tension=_clamp(
                round(
                    target.tension
                    + self.cpu_to_tension * cpu
                    + self.memory_to_tension * memory
                    + self.latency_to_tension * latency
                    + self.error_to_tension * error,
                    4,
                ),
                low.tension,
                high.tension,
            ),
            comfort=target.comfort,
            fatigue=_clamp(
                round(
                    target.fatigue
                    + self.memory_to_fatigue * memory
                    + self.latency_to_fatigue * latency,
                    4,
                ),
                low.fatigue,
                high.fatigue,
            ),
            pain_like=_clamp(
                round(target.pain_like + self.error_to_pain_like * error, 4),
                low.pain_like,
                high.pain_like,
            ),
            social_safety=target.social_safety,
        )

    def _read_pressures(self, internal_signals: tuple[Stimulus, ...]) -> dict[str, float]:
        """Read bounded interoceptive pressure facts from the stimuli metadata (max per channel).

        Reads only the reserved metadata keys the `50` producer sets (`pressure_channel`,
        `pressure_value`); a signal whose channel is not a string, or whose value is not a numeric
        in `[0,1]` (booleans excluded), contributes nothing. Never parses the content string and
        never raises for an unrecognized fact (no fabricated condition).
        """

        pressures: dict[str, float] = {}
        for signal in internal_signals:
            metadata = signal.metadata or {}
            channel = metadata.get(_PRESSURE_CHANNEL_METADATA_KEY)
            value = metadata.get(_PRESSURE_VALUE_METADATA_KEY)
            if not isinstance(channel, str):
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            numeric = float(value)
            if numeric < 0.0 or numeric > 1.0:
                continue
            pressures[channel] = max(pressures.get(channel, 0.0), numeric)
        return pressures
