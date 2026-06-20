"""Owner: neuromodulator system.

Owns:
- batch-level neuromodulator update orchestration
- update-path invocation order
- request and publication op construction

Does not own:
- permanent modulation strategy semantics
- subjective feeling construction
- action routing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from helios_v2.appraisal import RapidAppraisalBatch

from .contracts import (
    NeuromodulatorConfig,
    NeuromodulatorError,
    NeuromodulatorLevels,
    NeuromodulatorState,
    NeuromodulatorSystemAPI,
    PublishNeuromodulatorStateOp,
    UpdateNeuromodulatorsOp,
)


_NEUROMODULATOR_CHANNELS: tuple[str, ...] = (
    "dopamine",
    "norepinephrine",
    "serotonin",
    "acetylcholine",
    "cortisol",
    "oxytocin",
    "opioid_tone",
    "excitation",
    "inhibition",
)


def _validate_appraisal_batch(batch: RapidAppraisalBatch) -> None:
    if not batch.batch_id:
        raise NeuromodulatorError("RapidAppraisalBatch must declare a non-empty batch_id")
    for appraisal in batch.appraisals:
        if not appraisal.appraisal_id or not appraisal.source_name or not appraisal.provenance_signal_id:
            raise NeuromodulatorError("RapidAppraisalBatch contains appraisal with incomplete provenance")


@runtime_checkable
class NeuromodulatorUpdatePath(Protocol):
    """Owner: neuromodulator system.

    Purpose:
        Produce the next neuromodulator levels from a validated appraisal batch and owner config.
    """

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: "NeuromodulatorLevels | None" = None,
    ) -> NeuromodulatorLevels:
        """Owner: neuromodulator system.

        Purpose:
            Produce the next independently modeled neuromodulator levels.

        Inputs:
            A validated `RapidAppraisalBatch`, one owner `NeuromodulatorConfig`, an optional runtime
            tick id, and the optional prior-tick `NeuromodulatorLevels` (`None` on a cold start or
            for a stateless path).

        Returns:
            One `NeuromodulatorLevels` value within contract range.

        Raises:
            NeuromodulatorError if the required update capability is unavailable or unsafe.

        Notes:
            `prior_levels` is additive (default `None`). A stateless path (constant or
            instantaneous-drive) must ignore it and reproduce its prior behavior byte-for-byte; a
            temporal (dual-timescale) path uses it as the integrator's prior state, treating `None`
            as a cold start (the tonic baseline).
        """


@runtime_checkable
class ActiveChannelReporter(Protocol):
    """Owner: neuromodulator system.

    Purpose:
        Report active channels for publication diagnostics without hardcoding threshold heuristics in the owner skeleton.
    """

    def report_active_channels(
        self,
        state: NeuromodulatorState,
        config: NeuromodulatorConfig,
    ) -> tuple[str, ...]:
        """Owner: neuromodulator system.

        Purpose:
            Report the channel names that should appear as active in publication diagnostics.

        Inputs:
            One `NeuromodulatorState` and the owner config used to construct it.

        Returns:
            A stable tuple of active channel names.

        Raises:
            NeuromodulatorError if active-channel reporting cannot proceed safely.

        Notes:
            This interface keeps unresolved activity semantics out of the public owner skeleton.
        """


@dataclass
class NeuromodulatorEngine(NeuromodulatorSystemAPI):
    """Owner: neuromodulator system.

    Purpose:
        Execute neuromodulator state updates using injected update and reporting collaborators.

    Failure semantics:
        Malformed appraisal batches fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: NeuromodulatorConfig
    update_path: NeuromodulatorUpdatePath
    active_channel_reporter: ActiveChannelReporter

    def update_state(
        self,
        batch: RapidAppraisalBatch,
        tick_id: int | None = None,
        prior_state: NeuromodulatorState | None = None,
    ) -> NeuromodulatorState:
        """Owner: neuromodulator system.

        Purpose:
            Consume one rapid appraisal batch and return one neuromodulator state snapshot.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal, an optional runtime tick
            id, and the optional prior-tick `NeuromodulatorState` (`None` on a cold start or for a
            stateless path).

        Returns:
            A `NeuromodulatorState` containing independently modeled channel levels.

        Raises:
            NeuromodulatorError when batch invariants or update-path outputs are invalid.

        Notes:
            `prior_state` is additive (default `None`). The engine forwards `prior_state.levels`
            (or `None`) to the injected update path; a stateless path ignores it and a
            dual-timescale path uses it as the integrator's prior. Remaining unresolved modulation
            semantics stay inside the injected update path.
        """

        _validate_appraisal_batch(batch)
        prior_levels = prior_state.levels if prior_state is not None else None
        levels = self.update_path.update_levels(batch, self.config, tick_id, prior_levels)
        return NeuromodulatorState(
            state_id=f"neuromodulator-state:{batch.batch_id}:{tick_id if tick_id is not None else 'na'}",
            source_appraisal_batch_id=batch.batch_id,
            levels=levels,
            tick_id=tick_id,
        )

    def build_update_op(self, batch: RapidAppraisalBatch) -> UpdateNeuromodulatorsOp:
        """Owner: neuromodulator system.

        Purpose:
            Build the request op describing one neuromodulator update request.

        Inputs:
            A `RapidAppraisalBatch` emitted by rapid salience appraisal.

        Returns:
            An `UpdateNeuromodulatorsOp` summarizing batch identity and source coverage.

        Raises:
            NeuromodulatorError if the batch is malformed.

        Notes:
            This method validates provenance before creating the request op.
        """

        _validate_appraisal_batch(batch)
        return UpdateNeuromodulatorsOp(
            op_name="update_neuromodulators",
            owner="neuromodulator_system",
            appraisal_batch_id=batch.batch_id,
            appraisal_count=len(batch.appraisals),
            source_names=tuple(sorted({appraisal.source_name for appraisal in batch.appraisals})),
        )

    def build_publish_state_op(self, state: NeuromodulatorState) -> PublishNeuromodulatorStateOp:
        """Owner: neuromodulator system.

        Purpose:
            Build the publication op for one neuromodulator state snapshot.

        Inputs:
            A `NeuromodulatorState` produced by this owner.

        Returns:
            A `PublishNeuromodulatorStateOp` summarizing publication metadata.

        Raises:
            NeuromodulatorError if the state is malformed.

        Notes:
            Active channel reporting stays injectable until the unresolved semantics are confirmed.
        """

        if not state.state_id or not state.source_appraisal_batch_id:
            raise NeuromodulatorError("NeuromodulatorState contains incomplete provenance")
        active_channels = self.active_channel_reporter.report_active_channels(state, self.config)
        return PublishNeuromodulatorStateOp(
            op_name="publish_neuromodulator_state",
            owner="neuromodulator_system",
            state_id=state.state_id,
            source_appraisal_batch_id=state.source_appraisal_batch_id,
            active_channels=tuple(sorted(active_channels)),
        )


def _clamp(value: float, low: float, high: float) -> float:
    """Owner: neuromodulator system. Clamp a value into [low, high]."""

    return round(min(high, max(low, value)), 4)


@dataclass
class DualTimescaleNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: neuromodulator system (R43).

    Purpose:
        Add the temporal (dual-timescale) layer the `04` contract already reserves
        (`decay_family = "dual_timescale_tonic_phasic"`, `decay_speed_persistence`). It wraps an
        inner `drive_path` (the R36 appraisal-derived instantaneous drive) and applies a
        leaky-integrator step against the prior-tick levels, so the neuromodulator state evolves
        across ticks instead of being recomputed from baseline each tick (advancing FG-2).

    Failure semantics:
        Construction raises `NeuromodulatorError` unless `0 < alpha_tonic < alpha_phasic <= 1`, so
        an unstable or non-decaying integrator cannot be assembled. The update itself is a total
        deterministic function; every channel is clamped to the legal range, so it never diverges.

    Notes:
        The instantaneous drive stays owned by the injected inner path; this owner-owned wrapper
        owns only the cross-tick carry/decay semantic. Per channel:
        `next = clamp(prior + alpha_phasic * (drive - prior) + alpha_tonic * (baseline - prior))`.
        `alpha_phasic` is the fast stimulus-tracking rate; `alpha_tonic` is the slow
        baseline-regression rate. A `None` `prior_levels` is a cold start: the prior defaults to the
        tonic baseline, so the first tick is one integrator step from baseline (no fabricated
        history). The coefficients are explicit bounded first-version constants under the config's
        declared `decay_speed_persistence` learned-parameter category; a later P5 slice tunes them
        without changing the integrator shape. Cross-channel coupling remains a later slice.
    """

    drive_path: NeuromodulatorUpdatePath
    alpha_phasic: float = 0.6
    alpha_tonic: float = 0.1
    # R-PROTO-LEARN.P-TEMPORAL: per-channel wall-clock half-life seconds.
    # Default values are first-version C_engineering_hypothesis constants
    # (cortisol ~60min, dopamine ~30s, NE/serotonin/OXT/opioid ~5min, ACh ~2min,
    # excitation/inhibition tracked via damped integrator).
    # These are P5 surfaces under LearnedParameterCategory "decay_speed_persistence".
    half_life_seconds: tuple[float, ...] = (
        30.0,    # dopamine
        300.0,   # norepinephrine
        300.0,   # serotonin
        120.0,   # acetylcholine
        3600.0,  # cortisol
        300.0,   # oxytocin
        300.0,   # opioid_tone
        60.0,    # excitation
        60.0,    # inhibition
    )
    # R-PROTO-LEARN.P-TEMPORAL: optional ContinuousStateOwner binding.
    # When set, the integrator applies wall-clock half-life decay between
    # ticks (delta_seconds read from ContinuousStateReading). When None,
    # the legacy tick-step integrator (alpha_phasic + alpha_tonic only) is
    # used, preserving P-PROTO-LEARN pre-temporal behaviour for tests
    # that don't bind a clock.
    continuous_state_owner: object | None = None
    # R-PROTO-LEARN.P-TEMPORAL: per-tick observed cumulative wall-elapsed
    # seconds from the bound continuous_state_owner. Used to derive
    # per-tick delta_seconds when caller does not supply one. Updated
    # internally by `update_levels`; do not set from outside.
    _last_observed_wall_elapsed: float | None = field(default=None, init=False, repr=False)

    # R-PROTO-LEARN.P-TEMPORAL: P5 surface. Maps hardcoded field -> LearnedParameterCategory.
    p5_parameter_mapping: dict[str, str] = field(default_factory=lambda: {
        "alpha_phasic": "decay_speed_persistence",
        "alpha_tonic": "decay_speed_persistence",
    })
    _p5_learner_binding: object | None = None

    def __post_init__(self) -> None:
        if not (0.0 < self.alpha_tonic < self.alpha_phasic <= 1.0):
            raise NeuromodulatorError(
                "DualTimescaleNeuromodulatorUpdatePath requires 0 < alpha_tonic < alpha_phasic <= 1"
            )
        if len(self.half_life_seconds) != len(_NEUROMODULATOR_CHANNELS):
            raise NeuromodulatorError(
                f"half_life_seconds must have {len(_NEUROMODULATOR_CHANNELS)} entries "
                f"(one per channel), got {len(self.half_life_seconds)}"
            )
        for i, hl in enumerate(self.half_life_seconds):
            if hl <= 0.0:
                raise NeuromodulatorError(
                    f"half_life_seconds[{i}] ({_NEUROMODULATOR_CHANNELS[i]}) "
                    f"must be > 0, got {hl}"
                )

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: NeuromodulatorLevels | None = None,
        delta_seconds: float | None = None,
    ) -> NeuromodulatorLevels:
        """Return the next levels as one leaky-integrator step from the prior toward the drive.

        R-PROTO-LEARN.P-TEMPORAL: when `delta_seconds` is provided (read from
        `ContinuousStateReading`), a wall-clock half-life decay is applied
        first: each channel is pulled toward its baseline by `1 - exp(-delta / hl)`
        before the phasic step. This is the time dimension the prior
        architecture lacked: hormone levels now decay in real seconds,
        not in tick-count units.

        Auto-wire from `continuous_state_owner`: when the caller does not
        supply `delta_seconds` but a `continuous_state_owner` is bound,
        the per-tick delta is derived from the difference between the
        current `sample().wall_clock_elapsed_seconds` and the
        previously-observed value. Cold start (no prior observation)
        yields `delta_seconds = None` and the legacy tick-step path runs.

        The inner drive path produces the instantaneous appraisal-derived target; this method
        moves the prior levels a phasic step toward that drive and a tonic step toward the
        baseline, clamping each channel. `prior_levels is None` is a cold start (prior = baseline).
        """

        # R-PROTO-LEARN.P-TEMPORAL: auto-derive delta_seconds from
        # `continuous_state_owner` when caller didn't supply one.
        if delta_seconds is None and self.continuous_state_owner is not None:
            try:
                reading = self.continuous_state_owner.sample()
                if reading.wall_clock_present and reading.wall_clock_elapsed_seconds > 0.0:
                    if self._last_observed_wall_elapsed is not None:
                        candidate = reading.wall_clock_elapsed_seconds - self._last_observed_wall_elapsed
                        if candidate > 0.0:
                            delta_seconds = float(candidate)
                    self._last_observed_wall_elapsed = reading.wall_clock_elapsed_seconds
            except Exception:
                # Wall-clock read failure is non-fatal; fall through to legacy tick-step.
                delta_seconds = None

        drive = self.drive_path.update_levels(batch, config, tick_id, None)
        prior = prior_levels if prior_levels is not None else config.tonic_baseline
        baseline = config.tonic_baseline
        low = config.legal_min
        high = config.legal_max
        next_values: dict[str, float] = {}
        for idx, channel in enumerate(_NEUROMODULATOR_CHANNELS):
            prior_value = getattr(prior, channel)
            drive_value = getattr(drive, channel)
            baseline_value = getattr(baseline, channel)
            # P-TEMPORAL: wall-clock half-life decay (skipped when delta_seconds None)
            if delta_seconds is not None and delta_seconds > 0.0:
                hl = self.half_life_seconds[idx]
                decay = 1.0 - pow(2.718281828459045, -delta_seconds / hl)
                prior_value = prior_value + decay * (baseline_value - prior_value)
            stepped = (
                prior_value
                + self.alpha_phasic * (drive_value - prior_value)
                + self.alpha_tonic * (baseline_value - prior_value)
            )
            next_values[channel] = _clamp(stepped, getattr(low, channel), getattr(high, channel))
        return NeuromodulatorLevels(**next_values)

    def apply_p5_policy(self, snapshot: object) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface override.

        Maps snapshot.policy_output[0] (decay_speed_persistence index) to
        `alpha_phasic` (clipped to (alpha_tonic, 1.0]) and policy_output[1]
        to `alpha_tonic` (clipped to (0, alpha_phasic)). This is a
        non-default mapping (one category -> two fields with non-trivial
        relationship), so we override the default 1-to-1 helper.
        """

        if snapshot is None or not getattr(snapshot, "policy_output", None):
            return
        out = snapshot.policy_output
        if len(out) < 1:
            return
        # P5 surface: alpha_phasic (decay_speed_persistence)
        new_phasic = max(self.alpha_tonic + 1e-6, min(1.0, float(out[0])))
        self.alpha_phasic = new_phasic
        if len(out) >= 2:
            new_tonic = max(1e-6, min(self.alpha_phasic - 1e-6, float(out[1])))
            self.alpha_tonic = new_tonic


@dataclass(frozen=True)
class _AggregatedSalience:
    """Owner: neuromodulator system. Per-dimension max salience aggregated across a batch."""

    threat: float
    reward: float
    novelty: float
    social: float
    uncertainty: float


def _aggregate_salience(batch: RapidAppraisalBatch) -> _AggregatedSalience:
    """Owner: neuromodulator system. Aggregate a rapid-appraisal batch into one salience vector.

    Per-dimension maximum across the batch's appraisals (the most salient stimulus drives
    modulation). An empty batch yields all-zero salience, so derivation reduces to the tonic
    baseline. Reads only the public `RapidSalienceVector` fields.
    """

    appraisals = batch.appraisals
    if not appraisals:
        return _AggregatedSalience(0.0, 0.0, 0.0, 0.0, 0.0)
    vectors = [appraisal.salience for appraisal in appraisals]
    return _AggregatedSalience(
        threat=max(vector.threat for vector in vectors),
        reward=max(vector.reward for vector in vectors),
        novelty=max(vector.novelty for vector in vectors),
        social=max(vector.social for vector in vectors),
        uncertainty=max(vector.uncertainty for vector in vectors),
    )


@dataclass
class AppraisalDerivedNeuromodulatorUpdatePath(NeuromodulatorUpdatePath):
    """Owner: neuromodulator system (R36, recovered to the owner in R56).

    Purpose:
        Derive the next neuromodulator levels from the real rapid-appraisal batch around the
        configured tonic baseline, replacing the constant first-version path so real `03`
        salience (especially the R35 novelty signal) shapes the `04` state. This is the `04`
        owner's defining cognitive policy: which appraisal salience drives which neuromodulator
        channel and how strongly.

    Failure semantics:
        A malformed batch is rejected by the `04` engine before this path runs. This path is a
        total deterministic function of the batch + config; it never branches into a degraded
        mode and never diverges outside the legal range (every channel is clamped).

    Notes:
        Conforms to the owner's own `NeuromodulatorUpdatePath` protocol; the `04` engine is
        unchanged and composition only constructs/injects/wraps this path (it no longer authors
        the mapping). Stateless by design: it reads no prior-tick levels (true dual-timescale
        decay is the R43 `DualTimescaleNeuromodulatorUpdatePath` wrapper). The per-channel
        sensitivity coefficients are explicit bounded first-version constants organized under the
        config's declared learned-parameter categories; a later P5 slice tunes them without
        changing the equation shape. The mapping is a fixed linear combination plus clamp -- no
        NN, no hidden branch.
    """

    novelty_to_norepinephrine: float = 0.5
    uncertainty_to_norepinephrine: float = 0.3
    reward_to_dopamine: float = 0.5
    novelty_to_dopamine: float = 0.15
    threat_to_cortisol: float = 0.5
    # R80: appraisal-derived drives for the four affective channels (C_engineering_hypothesis
    # grounding from brain.mmd roles). Bounded first-version constants under the config's
    # channel_gain_sensitivity learned-parameter category (P5-learnable).
    serotonin_social_safety: float = 0.4
    oxytocin_social: float = 0.4
    opioid_reward: float = 0.3
    opioid_social: float = 0.2
    acetylcholine_novelty: float = 0.4

    def update_levels(
        self,
        batch: RapidAppraisalBatch,
        config: NeuromodulatorConfig,
        tick_id: int | None,
        prior_levels: NeuromodulatorLevels | None = None,
    ) -> NeuromodulatorLevels:
        del tick_id, prior_levels
        salience = _aggregate_salience(batch)
        base = config.tonic_baseline
        low = config.legal_min
        high = config.legal_max
        return NeuromodulatorLevels(
            dopamine=_clamp(
                base.dopamine
                + self.reward_to_dopamine * salience.reward
                + self.novelty_to_dopamine * salience.novelty,
                low.dopamine,
                high.dopamine,
            ),
            norepinephrine=_clamp(
                base.norepinephrine
                + self.novelty_to_norepinephrine * salience.novelty
                + self.uncertainty_to_norepinephrine * salience.uncertainty,
                low.norepinephrine,
                high.norepinephrine,
            ),
            cortisol=_clamp(
                base.cortisol + self.threat_to_cortisol * salience.threat,
                low.cortisol,
                high.cortisol,
            ),
            # R80: serotonin/oxytocin/opioid_tone/acetylcholine are now appraisal-derived
            # (C_engineering_hypothesis grounding from brain.mmd roles): mood stability from
            # social safety under low threat, social bonding from social presence, reward
            # satisfaction + social comfort, and attention/encoding gain from novelty.
            # excitation/inhibition remain at the tonic baseline (their drivers are a later slice).
            serotonin=_clamp(
                base.serotonin
                + self.serotonin_social_safety * salience.social * (1.0 - salience.threat),
                low.serotonin,
                high.serotonin,
            ),
            acetylcholine=_clamp(
                base.acetylcholine + self.acetylcholine_novelty * salience.novelty,
                low.acetylcholine,
                high.acetylcholine,
            ),
            oxytocin=_clamp(
                base.oxytocin + self.oxytocin_social * salience.social,
                low.oxytocin,
                high.oxytocin,
            ),
            opioid_tone=_clamp(
                base.opioid_tone
                + self.opioid_reward * salience.reward
                + self.opioid_social * salience.social,
                low.opioid_tone,
                high.opioid_tone,
            ),
            excitation=_clamp(base.excitation, low.excitation, high.excitation),
            inhibition=_clamp(base.inhibition, low.inhibition, high.inhibition),
        )
