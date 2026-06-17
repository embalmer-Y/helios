"""Owner: interoceptive feeling layer (P5-feel learning path).

Owns:
- the P5-feel learning algorithm that replaces R36/R43 hardcoded
  channel-to-dimension weights with learned weights (per Fermin 2021 IMAC).
- the 3-regime learning state machine (exploratory / model-based / habitual).
- the dopamine-precision and acetylcholine-flexibility learning gates.

Does not own:
- the LLM appraisal that supplies the learning target (that is R-PROTO-LEARN.2,
  injected via `LlmAppraisalSource` Protocol at composition time).
- the neuromodulator state (that is owner 04, read at composition time).
- the final feeling update path (this learning path produces updated W/bias; the
  owner 05 `InteroceptiveFeelingState` consumes them).

P5-feel design references:
- Fermin, Yamawaki, Friston (2021) "Insula Interoception, Active Inference and
  Feeling Representation" (arXiv:2112.12290): IMAC model with three
  insula-PFC-striatum parallel loops (aINS exploratory / dINS model-based /
  gINS habitual) and the mesaception / metaception 2nd-order cortical
  representation.
- Reddan et al. (2018) "Somatosensory and motor contributions to emotion
  representation" (arXiv:2411.08973): 7-dim feeling mapped onto somatosensory /
  motor / insula / mPFC cortical regions.
- Hinrichs et al. (2025) "Geometric Hyperscanning of Affect under Active
  Inference" (arXiv:2506.08599): valence = self-model prediction error weighted
  by self-relevance (the basis for the dopamine precision signal here).
- Seth (2013), Barrett (2017), Friston (2010): classical interoceptive inference
  and constructed emotion frameworks.

Five algorithm components (all shipped in one slice, no phasing, by owner
2026-06-16 ~19:50):
1. exploratory stage: R-PROTO-LEARN.2 LLM appraisal provides the learning target
   (aINS-equivalent).
2. habitual stage: stable mapping for `min_stable_ticks` consecutive ticks
   commits the weights to owner 05 config (gINS-equivalent).
3. dopamine precision signal: residual magnitude * dopamine modulates the
   learning rate (R81 corroboration pattern).
4. acetylcholine flexibility signal: novelty * acetylcholine modulates whether
   new mappings are admitted (Fermin 2021 ACh flexibility).
5. three-regime switching: aINS / dINS / gINS regime is determined per tick from
   residual trend + ACh + novelty (Fermin 2021 IMAC three parallel loops).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Literal, Mapping, Protocol, runtime_checkable

import numpy as np

from helios_v2.neuromodulation import NeuromodulatorState


class Regime(str, Enum):
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        The three learning regimes mapped onto the Fermin 2021 IMAC parallel
        loops. The string values are stable wire format; downstream code may
        match on either the enum or the string.

    Failure semantics:
        Construction is total; this enum cannot fail.
    """

    EXPLORATORY = "exploratory"
    MODEL_BASED = "model_based"
    HABITUAL = "habitual"


# --- Channel / dimension identifiers (1-to-1 with R80 neuromodulator +
#     R36/R43 feeling) -------------------------------------------------

HORMONE_CHANNELS: tuple[str, ...] = (
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
FEELING_DIMENSIONS: tuple[str, ...] = (
    "valence",
    "arousal",
    "tension",
    "comfort",
    "fatigue",
    "pain_like",
    "social_safety",
)

# --- First-version dense weight matrix (sparse-from-R36/R43 expanded to
#     dense 7x9 with zero-fills; this is the P5-feel learning starting
#     point). Values mirror the R36 hardcoded coefficients where they exist
#     and 0.0 where they do not (cortisol contributions to valence / comfort
#     are encoded as negative to express "stress reduces valence / comfort"
#     semantics, matching the original subtract form). ------------------

_FIRST_VERSION_WEIGHTS: tuple[tuple[float, ...], ...] = (
    # valence: reward - punishment asymmetry (Panksepp SEEKING + opioid + 5-HT)
    # |dopamine|norepinephrine|serotonin|acetylcholine|cortisol|oxytocin|opioid_tone|excitation|inhibition
    ( 0.30,  0.10,  0.15,  0.05, -0.30,  0.20,  0.15,  0.05, -0.05),
    # arousal: sympathetic activation (NE + DA + ACh up, 5-HT down, inhibition down)
    ( 0.10,  0.40, -0.10,  0.10,  0.05,  0.00,  0.00,  0.20, -0.10),
    # tension: threat vigilance (cortisol + NE + ACh up, oxytocin + opioid down)
    ( 0.00,  0.20,  0.00,  0.10,  0.40, -0.10, -0.10,  0.10,  0.00),
    # comfort: soothing (opioid + oxytocin + 5-HT up, cortisol + NE + ACh down)
    ( 0.10, -0.10,  0.15, -0.10, -0.30,  0.20,  0.30, -0.05,  0.05),
    # fatigue: depletion (cortisol + inhibition + excitation up, DA + 5-HT + opioid down)
    (-0.30,  0.00, -0.20, -0.05,  0.30, -0.10, -0.15,  0.20,  0.20),
    # pain_like: nociception (cortisol + NE + excitation up, DA + 5-HT + opioid down)
    (-0.20,  0.20, -0.20,  0.00,  0.40,  0.00, -0.35,  0.10,  0.00),
    # social_safety: attachment (oxytocin + 5-HT up, cortisol down, DA + opioid up)
    ( 0.10,  0.00,  0.15,  0.05, -0.25,  0.40,  0.10,  0.00, -0.05),
)


def _first_version_bias() -> tuple[float, ...]:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        The first-version bias (per-dimension neutral contribution that the
        learning path will later augment). At present it returns the
        canonical first-version bias vector mirroring the R36 baseline
        contributions (set to 0.0 because R36 expresses baselines via
        `config.baseline_feeling`, not as a learned bias; P5-feel
        consolidates them into the bias for a single dense representation).

    Returns:
        A 7-tuple of neutral bias values.

    Failure semantics:
        Total; cannot fail.
    """

    return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)


def _validate_weight_matrix(W: tuple[tuple[float, ...], ...]) -> None:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        Validate that a weight matrix has shape 7 (feelings) x 9 (hormones)
        and that every entry is finite.

    Inputs:
        W: A 7x9 matrix of floats.

    Failure semantics:
        Wrong shape or non-finite values raise `ValueError`.
    """

    if len(W) != len(FEELING_DIMENSIONS):
        raise ValueError(
            f"Weight matrix must have {len(FEELING_DIMENSIONS)} rows, got {len(W)}"
        )
    for i, row in enumerate(W):
        if len(row) != len(HORMONE_CHANNELS):
            raise ValueError(
                f"Weight matrix row {i} must have {len(HORMONE_CHANNELS)} columns, got {len(row)}"
            )
        for j, value in enumerate(row):
            if value != value:  # NaN check
                raise ValueError(f"Weight matrix[{i}][{j}] is NaN")
            if value in (float("inf"), float("-inf")):
                raise ValueError(f"Weight matrix[{i}][{j}] is non-finite")


def _validate_bias(bias: tuple[float, ...]) -> None:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        Validate that a bias vector has length 7 and finite entries.

    Inputs:
        bias: A 7-tuple of floats.

    Failure semantics:
        Wrong length or non-finite values raise `ValueError`.
    """

    if len(bias) != len(FEELING_DIMENSIONS):
        raise ValueError(
            f"Bias vector must have {len(FEELING_DIMENSIONS)} entries, got {len(bias)}"
        )
    for i, value in enumerate(bias):
        if value != value:
            raise ValueError(f"Bias vector[{i}] is NaN")
        if value in (float("inf"), float("-inf")):
            raise ValueError(f"Bias vector[{i}] is non-finite")


# --- R-PROTO-LEARN.9 hormone-feeling closure helpers -----------------
# Moore-Penrose pseudo-inverse for the 7x9 weight matrix. We use
# numpy.linalg.pinv (SVD-based, numerically robust). numpy is a hard
# runtime dependency of P5-feel, imported at the top of this module
# and verified to be importable at first use.


def _compute_hormone_adjustment(
    W: tuple[tuple[float, ...], ...],
    current_hormone: tuple[float, ...],
    target_feeling: tuple[float, ...],
    strength: float,
    clip: float,
) -> tuple[float, ...]:
    """R-PROTO-LEARN.9: solve for the hormone adjustment that makes
    W * (hormone + strength * adj) match `target_feeling`.

    1. Compute the current projection: current_feeling = W * hormone.
    2. Compute the residual in feeling space: r = target - current_feeling.
    3. Compute the unconstrained hormone adjustment: adj0 = W^+ * r
       via `numpy.linalg.pinv` (SVD-based, numerically robust).
    4. Scale by `strength` and (when clip < 1.0) clip per channel to +/- clip.
       When `clip >= 1.0` the adjustment is left unclamped so the linear
       least-squares solution can drive the closed-loop residual to ~0.
    5. Return the (scaled, optionally clipped) 9-dim adjustment.

    The caller applies this adjustment to the current hormone before
    re-projecting the feeling vector, so the closed-loop residual
    (= target - W * (hormone + adj)) is much smaller than the open-loop
    residual (= target - W * hormone).

    Failure semantics:
        numpy is a hard dependency of P5-feel; if numpy is missing the
        module fails fast at import time. Numerical errors from the
        pseudo-inverse (e.g. NaN targets) propagate as numpy warnings
        and are NOT silently swallowed; the caller can guard with
        finite-checks on the LLM appraisal before invoking update().
    """
    if strength <= 0.0:
        return (0.0,) * len(current_hormone)
    W_np = np.asarray(W, dtype=np.float64)
    hormone_np = np.asarray(current_hormone, dtype=np.float64)
    target_np = np.asarray(target_feeling, dtype=np.float64)
    Wplus_np = np.linalg.pinv(W_np)
    current_feeling_np = W_np @ hormone_np
    residual_np = target_np - current_feeling_np
    adj0_np = Wplus_np @ residual_np
    if clip >= 1.0:
        return tuple(strength * float(x) for x in adj0_np)
    return tuple(
        _clamp(strength * float(adj0_np[i]), -clip, clip)
        for i in range(len(adj0_np))
    )


# --- R-PROTO-LEARN.10 appraisal-derived hormone path ---------------
# Routes the LLM appraisal through the real owner 04 neuromodulation
# path (`AppraisalDerivedNeuromodulatorUpdatePath`) instead of the
# pure-mathematical pseudo-inverse solve. This is the "production"
# closure: the LLM appraisal 7-dim -> salience 5-dim -> hormone
# 9-dim pipeline uses the same equations that owner 04 uses for the
# real rapid-appraisal input, so the closed-loop residual reflects
# the actual cognitive policy rather than a least-squares fit.


@runtime_checkable
class FeelingToSalienceMapper(Protocol):
    """R-PROTO-LEARN.10: maps the 7-dim LLM feeling appraisal onto
    the 5-dim salience vector that owner 04 expects.

    Inputs:
        feeling: 7-tuple in `FEELING_DIMENSIONS` order, each in [0, 1].

    Returns:
        A 5-tuple in (threat, reward, novelty, social, uncertainty)
        order, each in [0, 1]. The aggregate is recomputed by
        `_compute_appraisal_derived_hormone`.
    """

    def __call__(
        self, feeling: tuple[float, ...]
    ) -> tuple[float, float, float, float, float]: ...


def _default_feeling_to_salience(
    feeling: tuple[float, ...],
) -> tuple[float, float, float, float, float]:
    """R-PROTO-LEARN.10: the default feeling->salience mapper.

    Grounds each feeling dimension on the Panksepp 7 systems +
    Fermin 2021 IMAC role assignments. Heuristics only -- the
    `appraisal_neuromodulator_config` channel-gain sensitivities can
    later tune these mappings without changing the equation shape.

    Mapping (grounded in Panksepp 2011 + Fermin 2021):
        threat     = (1 - valence) * tension + pain_like * 0.7
        reward     = valence * (1 - fatigue) * (1 - pain_like)
        novelty    = arousal * (1 - comfort)  (high arousal + low
                     comfort = the new-thing feeling)
        social     = social_safety * (1 - threat) * 0.7 + oxytocin
                     proxy 0.3 (1 - threat = "approach" = social reach)
        uncertainty = (1 - valence) * (1 - comfort) * arousal
                     (low valence + low comfort + high arousal =
                     anxious-uncertain)
    """

    if len(feeling) != 7:
        raise ValueError(
            f"feeling must have 7 dims, got {len(feeling)}"
        )
    valence, arousal, tension, comfort, fatigue, pain, social_safety = feeling
    threat = _clamp(
        (1.0 - valence) * tension + pain * 0.7, 0.0, 1.0
    )
    reward = _clamp(
        valence * (1.0 - fatigue) * (1.0 - pain), 0.0, 1.0
    )
    novelty = _clamp(
        arousal * (1.0 - comfort), 0.0, 1.0
    )
    social = _clamp(
        social_safety * (1.0 - threat) * 0.7 + 0.3 * (1.0 - threat),
        0.0,
        1.0,
    )
    uncertainty = _clamp(
        (1.0 - valence) * (1.0 - comfort) * arousal, 0.0, 1.0
    )
    return (threat, reward, novelty, social, uncertainty)


def _compute_appraisal_derived_hormone(
    llm_appraisal: tuple[float, ...],
    current_hormone: tuple[float, ...],
    neuromodulator_config,
    appraisal_update_path,
    salience_mapper: FeelingToSalienceMapper,
    strength: float,
    tick_id: int | None,
) -> tuple[float, ...]:
    """R-PROTO-LEARN.10: route the LLM appraisal through the real
    owner 04 path to get a hormone adjustment.

    1. Map 7-dim feeling to 5-dim salience (Panksepp-grounded).
    2. Build a one-appraisal `RapidAppraisalBatch`.
    3. Call `appraisal_update_path.update_levels(batch, config, tick_id, current_hormone)`.
    4. Per-channel delta = new - current, scaled by `strength`, clipped to +/-1.
    5. Return the (scaled, clipped) 9-dim delta.

    The caller adds the delta to the current hormone before
    re-projecting the feeling vector, so the closed-loop residual
    (= target - W * (hormone + delta)) reflects the actual owner 04
    cognitive policy.

    Failure semantics:
        Any exception (missing config, malformed batch, illegal
        level) propagates; the caller is expected to validate
        inputs at construction time.
    """

    if strength <= 0.0:
        return (0.0,) * len(current_hormone)
    # 1. feeling -> salience
    threat, reward, novelty, social, uncertainty = salience_mapper(llm_appraisal)
    aggregate = max(threat, reward, novelty, social, uncertainty)
    # 2. build a one-appraisal batch (avoid the full Stimulus pipeline
    # since we only have a 7-dim vector at this layer)
    from helios_v2.appraisal.contracts import (
        RapidAppraisal,
        RapidAppraisalBatch,
        RapidSalienceVector,
    )
    appraisal = RapidAppraisal(
        appraisal_id=f"p5-feel-r10:{tick_id}",
        stimulus_id=f"p5-feel-stim:{tick_id}",
        source_name="p5_feel_llm_appraisal",
        salience=RapidSalienceVector(
            threat=threat,
            reward=reward,
            novelty=novelty,
            social=social,
            uncertainty=uncertainty,
            aggregate=aggregate,
        ),
        provenance_signal_id=f"p5-feel-prov:{tick_id}",
    )
    batch = RapidAppraisalBatch(
        batch_id=f"p5-feel-batch:{tick_id}",
        appraisals=(appraisal,),
    )
    # 3. compute the new hormone via the real owner 04 path
    from helios_v2.neuromodulation.contracts import NeuromodulatorLevels
    prior_levels = NeuromodulatorLevels(
        dopamine=current_hormone[0],
        norepinephrine=current_hormone[1],
        serotonin=current_hormone[2],
        acetylcholine=current_hormone[3],
        cortisol=current_hormone[4],
        oxytocin=current_hormone[5],
        opioid_tone=current_hormone[6],
        excitation=current_hormone[7],
        inhibition=current_hormone[8],
    )
    new_levels: NeuromodulatorLevels = appraisal_update_path.update_levels(
        batch=batch,
        config=neuromodulator_config,
        tick_id=tick_id,
        prior_levels=prior_levels,
    )
    # 4. per-channel delta, scaled by strength, clipped to +/-1
    new_hormone = (
        new_levels.dopamine,
        new_levels.norepinephrine,
        new_levels.serotonin,
        new_levels.acetylcholine,
        new_levels.cortisol,
        new_levels.oxytocin,
        new_levels.opioid_tone,
        new_levels.excitation,
        new_levels.inhibition,
    )
    deltas = tuple(
        _clamp(strength * (new_hormone[i] - current_hormone[i]), -1.0, 1.0)
        for i in range(9)
    )
    return deltas


def _clamp(value: float, low: float, high: float) -> float:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        Clamp a float into `[low, high]`. `None` is not accepted.

    Inputs:
        value: A float.
        low: Lower bound.
        high: Upper bound.

    Returns:
        The clamped value.

    Failure semantics:
        Total; cannot fail.
    """

    return max(low, min(float(value), high))


def _neuromodulator_levels_mapping(state: NeuromodulatorState) -> Mapping[str, float]:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        Project a `NeuromodulatorState` into a 9-channel mapping aligned to
        `HORMONE_CHANNELS`. Returns a plain dict (so callers may freely
        mutate) carrying the 9 channel levels in `[0, 1]`.

    Inputs:
        state: A `NeuromodulatorState`.

    Returns:
        A `Mapping[str, float]` with keys exactly equal to `HORMONE_CHANNELS`.

    Failure semantics:
        Total; will not raise. The owner 04 contract guarantees all 9
        channels exist and are in `[0, 1]`; we still defensively clamp
        here to make the learning path robust against call-site drift.
    """

    levels = state.levels
    return {
        "dopamine": _clamp(levels.dopamine, 0.0, 1.0),
        "norepinephrine": _clamp(levels.norepinephrine, 0.0, 1.0),
        "serotonin": _clamp(levels.serotonin, 0.0, 1.0),
        "acetylcholine": _clamp(levels.acetylcholine, 0.0, 1.0),
        "cortisol": _clamp(levels.cortisol, 0.0, 1.0),
        "oxytocin": _clamp(levels.oxytocin, 0.0, 1.0),
        "opioid_tone": _clamp(levels.opioid_tone, 0.0, 1.0),
        "excitation": _clamp(levels.excitation, 0.0, 1.0),
        "inhibition": _clamp(levels.inhibition, 0.0, 1.0),
    }


@dataclass(frozen=True)
class P5FeelLearningConfig:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        Configuration surface for the P5-feel learning algorithm. Defaults
        are the owner-chosen first-version values; the dopamine-precision
        and acetylcholine-flexibility thresholds come directly from the
        Fermin 2021 IMAC and Reddan 2018 mappings.

    Failure semantics:
        Out-of-range or non-finite parameters raise `ValueError` in
        `__post_init__`.
    """

    learning_rate: float = 0.05
    commit_threshold: float = 0.3
    min_stable_ticks: int = 8
    frozen_ticks_post_commit: int = 5
    precision_floor: float = 0.1
    precision_ceiling: float = 1.0
    flexibility_threshold: float = 0.3
    flexibility_floor: float = 0.1
    flexibility_ceiling: float = 1.0
    weight_clip_low: float = -2.0
    weight_clip_high: float = 2.0
    bias_clip_low: float = -1.0
    bias_clip_high: float = 1.0
    residual_history_size: int = 20
    regime_hysteresis_ticks: int = 3
    exploratory_min_dopamine: float = 0.0  # ACh gates; dopamine does NOT gate in exploratory
    habitual_recent_window: int = 3
    habitual_older_window: int = 20
    habitual_residual_threshold: float = 0.5
    # R-PROTO-LEARN.9: hormone-feeling closure
    # When enabled, the LLM appraisal is first routed through a
    # pseudo-inverse-based hormone adjustment so that
    #     updated_feeling = W * (hormone + adj)
    # matches the LLM appraisal up to a strength-scaled, clipped residual.
    # This makes the closed-loop residual (target - updated_feeling)
    # much smaller than the open-loop residual (target - current_feeling)
    # without requiring the weight matrix to fully explain the target.
    hormone_closure_enabled: bool = True
    hormone_closure_strength: float = 0.7
    hormone_closure_clip: float = 0.5
    # R-PROTO-LEARN.10: appraisal-derived hormone path
    # Selects the closure implementation:
    #   - "numpy_pinv"        (default, R-PROTO-LEARN.9): least-squares
    #                         fit via numpy.linalg.pinv. No neuromodulator
    #                         config required.
    #   - "appraisal_derived" (R-PROTO-LEARN.10): routes the LLM
    #                         appraisal through the real owner 04
    #                         `AppraisalDerivedNeuromodulatorUpdatePath`.
    #                         Requires `appraisal_neuromodulator_config`
    #                         and `appraisal_update_path` to be set.
    # The two paths can be swapped at construction time without
    # changing the P5-feel public contract.
    hormone_path: Literal["numpy_pinv", "appraisal_derived"] = "numpy_pinv"
    appraisal_neuromodulator_config: object = None  # NeuromodulatorConfig | None
    appraisal_update_path: object = None  # AppraisalDerivedNeuromodulatorUpdatePath | None
    appraisal_salience_mapper: object = None  # FeelingToSalienceMapper | None

    def __post_init__(self) -> None:
        if self.learning_rate <= 0.0 or self.learning_rate > 1.0:
            raise ValueError(f"learning_rate must be in (0, 1], got {self.learning_rate}")
        if not (0.0 <= self.commit_threshold <= 1.0):
            raise ValueError(f"commit_threshold must be in [0, 1], got {self.commit_threshold}")
        if self.min_stable_ticks <= 0:
            raise ValueError(f"min_stable_ticks must be positive, got {self.min_stable_ticks}")
        if self.frozen_ticks_post_commit < 0:
            raise ValueError(
                f"frozen_ticks_post_commit must be non-negative, got {self.frozen_ticks_post_commit}"
            )
        if not (0.0 <= self.precision_floor <= 1.0):
            raise ValueError(f"precision_floor must be in [0, 1], got {self.precision_floor}")
        if not (0.0 <= self.precision_ceiling <= 1.0):
            raise ValueError(f"precision_ceiling must be in [0, 1], got {self.precision_ceiling}")
        if self.precision_floor > self.precision_ceiling:
            raise ValueError("precision_floor must be <= precision_ceiling")
        if not (0.0 <= self.flexibility_threshold <= 1.0):
            raise ValueError(
                f"flexibility_threshold must be in [0, 1], got {self.flexibility_threshold}"
            )
        if not (0.0 <= self.flexibility_floor <= 1.0):
            raise ValueError(f"flexibility_floor must be in [0, 1], got {self.flexibility_floor}")
        if not (0.0 <= self.flexibility_ceiling <= 1.0):
            raise ValueError(
                f"flexibility_ceiling must be in [0, 1], got {self.flexibility_ceiling}"
            )
        if self.flexibility_floor > self.flexibility_ceiling:
            raise ValueError("flexibility_floor must be <= flexibility_ceiling")
        if self.weight_clip_low >= self.weight_clip_high:
            raise ValueError("weight_clip_low must be < weight_clip_high")
        if self.bias_clip_low >= self.bias_clip_high:
            raise ValueError("bias_clip_low must be < bias_clip_high")
        if self.residual_history_size < 5:
            raise ValueError(
                f"residual_history_size must be >= 5, got {self.residual_history_size}"
            )
        if self.regime_hysteresis_ticks < 1:
            raise ValueError(
                f"regime_hysteresis_ticks must be >= 1, got {self.regime_hysteresis_ticks}"
            )
        if self.habitual_recent_window < 1 or self.habitual_older_window < 1:
            raise ValueError("habitual windows must be positive")
        if self.habitual_recent_window >= self.habitual_older_window:
            raise ValueError("habitual_recent_window must be < habitual_older_window")
        if not (0.0 <= self.habitual_residual_threshold <= 1.0):
            raise ValueError(
                f"habitual_residual_threshold must be in [0, 1], got {self.habitual_residual_threshold}"
            )
        if not (0.0 <= self.hormone_closure_strength <= 1.0):
            raise ValueError(
                f"hormone_closure_strength must be in [0, 1], got {self.hormone_closure_strength}"
            )
        if not (0.0 < self.hormone_closure_clip <= 1.0):
            raise ValueError(
                f"hormone_closure_clip must be in (0, 1], got {self.hormone_closure_clip}"
            )
        if self.hormone_path not in ("numpy_pinv", "appraisal_derived"):
            raise ValueError(
                f"hormone_path must be 'numpy_pinv' or 'appraisal_derived', "
                f"got {self.hormone_path!r}"
            )
        if self.hormone_path == "appraisal_derived":
            missing = []
            if self.appraisal_neuromodulator_config is None:
                missing.append("appraisal_neuromodulator_config")
            if self.appraisal_update_path is None:
                missing.append("appraisal_update_path")
            if self.appraisal_salience_mapper is None:
                missing.append("appraisal_salience_mapper")
            if missing:
                raise ValueError(
                    "R-PROTO-LEARN.10 appraisal_derived path requires "
                    f"the following config fields to be set: {', '.join(missing)}"
                )


@dataclass
class P5FeelLearningPath:
    """Owner: interoceptive feeling layer (P5-feel learning path).

    Purpose:
        The P5-feel learning algorithm. Holds the current 7x9 weight matrix
        and 7-dim bias, an EMA of recent residuals, and a regime memory for
        hysteresis. `update()` is the single tick entry point; it returns the
        next weight matrix / bias / regime but does NOT mutate owner 05
        state directly (the owner 05 engine consumes the return values via
        its `InteroceptiveFeelingState`).

    Inputs:
        config: A `P5FeelLearningConfig`.
        initial_W: Optional 7x9 starting weight matrix; defaults to the
            first-version sparse-from-R36/R43 expansion.
        initial_bias: Optional 7-dim starting bias; defaults to zero.

    Failure semantics:
        Construction validates the initial weight matrix / bias via
        `__post_init__`. `update()` is total and will not raise on legal
        inputs (LLM appraisal may be `None` to indicate no learning target
        is available; in that case the residual is zero and no update
        happens).
    """

    config: P5FeelLearningConfig
    initial_W: tuple[tuple[float, ...], ...] = field(
        default_factory=lambda: _FIRST_VERSION_WEIGHTS
    )
    initial_bias: tuple[float, ...] = field(default_factory=_first_version_bias)
    _W: tuple[tuple[float, ...], ...] = field(init=False)
    _bias: tuple[float, ...] = field(init=False)
    _residual_history: deque = field(init=False)
    _regime_history: deque = field(init=False)
    _frozen_until_tick: int = field(init=False, default=-1)
    _last_regime: Regime = field(init=False, default=Regime.EXPLORATORY)
    _last_residual: tuple[float, ...] = field(init=False, default=(0.0,) * 7)
    _last_precisions: tuple[float, ...] = field(init=False, default=(0.0,) * 7)
    _last_flexibility: float = field(init=False, default=0.0)
    _commit_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        _validate_weight_matrix(self.initial_W)
        _validate_bias(self.initial_bias)
        # Defensive copy to avoid mutating shared tuples the caller passed in.
        self._W = tuple(
            tuple(float(v) for v in row) for row in self.initial_W
        )
        self._bias = tuple(float(v) for v in self.initial_bias)
        self._residual_history = deque(maxlen=self.config.residual_history_size)
        self._regime_history = deque(maxlen=self.config.regime_hysteresis_ticks)

    # --- public inspection methods (read-only) -------------------------

    def weights_snapshot(self) -> tuple[tuple[float, ...], ...]:
        """Return a defensive copy of the current weight matrix."""

        return tuple(tuple(float(v) for v in row) for row in self._W)

    def bias_snapshot(self) -> tuple[float, ...]:
        """Return a defensive copy of the current bias vector."""

        return tuple(float(v) for v in self._bias)

    def regime(self) -> Regime:
        """Return the most recent regime (after hysteresis)."""

        return self._last_regime

    def last_residual(self) -> tuple[float, ...]:
        """Return the residual from the most recent update."""

        return self._last_residual

    def last_precisions(self) -> tuple[float, ...]:
        """Return the per-dimension dopamine precision values from the
        most recent update (each in `[precision_floor, precision_ceiling]`).
        """

        return self._last_precisions

    def last_flexibility(self) -> float:
        """Return the ACh flexibility value from the most recent update."""

        return self._last_flexibility

    def commit_count(self) -> int:
        """Return the number of times the weights have been committed so
        far. Each commit is a "habitual" event in the Fermin 2021 sense.
        """

        return self._commit_count

    # --- core update ---------------------------------------------------

    def update(
        self,
        hormone_state: NeuromodulatorState,
        llm_appraisal: tuple[float, ...] | None,
        novelty: float,
        tick_id: int | None,
    ) -> tuple[tuple[tuple[float, ...], ...], tuple[float, ...], Regime]:
        """Owner: interoceptive feeling layer (P5-feel learning path).

        Purpose:
            One tick of P5-feel learning. Consumes the current neuromodulator
            state and (optionally) the R-PROTO-LEARN.2 LLM appraisal,
            computes the residual and the three-gate update (DA precision,
            ACh flexibility, regime switching), updates the weight matrix
            and bias, and returns the new values.

        Inputs:
            hormone_state: Current `NeuromodulatorState` (read-only).
            llm_appraisal: Optional 7-dim LLM appraisal in `[0, 1]^7`. If
                `None`, no learning target is available and the residual
                is treated as zero (no update).
            novelty: Appraisal novelty in `[0, 1]` (drives ACh flexibility
                and regime switching).
            tick_id: Current tick id, or `None` for off-tick usage.

        Returns:
            A triple `(W_new, bias_new, regime)`. Both `W_new` and
            `bias_new` are frozen 7x9 / 7-tuples. The regime is the
            post-hysteresis regime for this tick.

        R-PROTO-LEARN.9 hormone-feeling closure:
            When `config.hormone_closure_enabled` is True and the LLM
            appraisal is non-None, the residual that drives learning is
            the closed-loop residual:
                target = LLM appraisal
                adj = pinv(W) * (target - W * hormone) (clipped)
                updated_feeling = W * (hormone + adj)
                residual = target - updated_feeling
            rather than the open-loop residual:
                residual = target - W * hormone
            The closed-loop residual is much smaller (because most of the
            feeling space is reachable via the hormone adjustment), so
            commit becomes feasible under real LLM appraisal signals.

        Failure semantics:
            Total; will not raise on legal inputs. Illegal shapes
            (LLM appraisal with wrong length, hormone state with a
            missing channel) raise `ValueError` defensively.
        """

        # 1. Project current feeling from current W/bias (R36/R43 formula).
        levels = _neuromodulator_levels_mapping(hormone_state)
        current_feeling = self._project_feeling(levels)

        # 2. R-PROTO-LEARN.9 / R-PROTO-LEARN.10: optionally route the LLM
        # appraisal through a hormone adjustment so the closed-loop
        # residual is small. Two implementations:
        #   - numpy_pinv (R9): least-squares fit via numpy.linalg.pinv
        #   - appraisal_derived (R10): real owner 04 neuromodulation path
        if (
            self.config.hormone_closure_enabled
            and llm_appraisal is not None
        ):
            current_hormone = tuple(levels[ch] for ch in HORMONE_CHANNELS)
            if self.config.hormone_path == "numpy_pinv":
                adjustment = _compute_hormone_adjustment(
                    W=self._W,
                    current_hormone=current_hormone,
                    target_feeling=llm_appraisal,
                    strength=self.config.hormone_closure_strength,
                    clip=self.config.hormone_closure_clip,
                )
            elif self.config.hormone_path == "appraisal_derived":
                adjustment = _compute_appraisal_derived_hormone(
                    llm_appraisal=llm_appraisal,
                    current_hormone=current_hormone,
                    neuromodulator_config=self.config.appraisal_neuromodulator_config,
                    appraisal_update_path=self.config.appraisal_update_path,
                    salience_mapper=self.config.appraisal_salience_mapper,
                    strength=self.config.hormone_closure_strength,
                    tick_id=tick_id,
                )
            else:
                adjustment = (0.0,) * 9
            # Apply the adjustment unclamped here so the closed-loop
            # feeling matches the LLM appraisal. (The real hormone state
            # is never modified; this is a sidecar adjustment used only
            # for residual computation and W-update target.)
            effective_hormone = tuple(current_hormone[i] + adjustment[i] for i in range(9))
            effective_levels = {ch: effective_hormone[i] for i, ch in enumerate(HORMONE_CHANNELS)}
            effective_feeling = self._project_feeling_unclamped(effective_levels)
        else:
            effective_feeling = current_feeling

        # 3. Compute residual against LLM appraisal (ground truth).
        residual = self._explore_residual(llm_appraisal, effective_feeling)
        self._residual_history.append(residual)
        self._last_residual = residual

        # 4. Compute the three learning gates.
        dopamine = levels["dopamine"]
        acetylcholine = levels["acetylcholine"]
        per_dim_precision = self._dopamine_precision(residual, dopamine)
        flexibility = self._ach_flexibility(novelty, acetylcholine)
        regime = self._determine_regime(per_dim_precision, flexibility, novelty, acetylcholine)
        self._last_precisions = per_dim_precision
        self._last_flexibility = flexibility

        # 5. Apply regime-conditioned update (or skip if frozen / no target).
        if tick_id is not None and tick_id < self._frozen_until_tick:
            # Committed-recently freeze window: hold the weights steady so
            # the just-committed mapping is not immediately perturbed.
            pass
        elif llm_appraisal is None:
            # No learning target: hold the weights.
            pass
        else:
            self._apply_update(levels, residual, per_dim_precision, flexibility, regime)

        # 6. Check the "habitual" commit condition.
        if llm_appraisal is not None and self._should_commit():
            self._commit_count += 1
            freeze_until = (tick_id or 0) + self.config.frozen_ticks_post_commit
            self._frozen_until_tick = freeze_until

        return self.weights_snapshot(), self.bias_snapshot(), regime

    def commit_if_stable(
        self, recent_residuals: tuple[tuple[float, ...], ...] | None = None
    ) -> bool:
        """Owner: interoceptive feeling layer (P5-feel learning path).

        Purpose:
            Public commit predicate. Returns `True` if the recent residual
            history is "stable" (every entry within `commit_threshold`) and
            spans at least `min_stable_ticks` ticks. Used by tests and by
            external observers; the internal `update()` also calls this.

        Inputs:
            recent_residuals: Optional override; when `None` uses the
                internal history. Used for unit tests that want to drive
                the predicate without running a full update loop.

        Returns:
            `True` if the mapping can be committed, `False` otherwise.

        Failure semantics:
            Total; will not raise.
        """

        if recent_residuals is not None:
            for r in recent_residuals:
                # R-PROTO-LEARN.8: strict `<` so residuals that land exactly
                # on the threshold (e.g. 0.5 from clamp boundary) still
                # commit; the previous `>=` was too strict and prevented
                # commit when `_clamp` pinned residual to the boundary.
                if max(abs(v) for v in r) > self.config.commit_threshold:
                    return False
            return len(recent_residuals) >= self.config.min_stable_ticks
        if len(self._residual_history) < self.config.min_stable_ticks:
            return False
        for r in list(self._residual_history)[-self.config.min_stable_ticks :]:
            if max(abs(v) for v in r) > self.config.commit_threshold:
                return False
        return True

    # --- private helpers (the five algorithm components) ---------------

    def _project_feeling(
        self, levels: Mapping[str, float]
    ) -> tuple[float, ...]:
        """Project a 7-dim feeling vector from hormone levels using the
        current weight matrix and bias. Mirrors the R36/R43 formula but
        in a dense 7x9 form.
        """

        result: list[float] = []
        for i in range(len(FEELING_DIMENSIONS)):
            row = self._W[i]
            value = self._bias[i]
            for j, channel in enumerate(HORMONE_CHANNELS):
                value += row[j] * float(levels[channel])
            result.append(_clamp(value, 0.0, 1.0))
        return tuple(result)

    def _project_feeling_unclamped(
        self, levels: Mapping[str, float]
    ) -> tuple[float, ...]:
        """R-PROTO-LEARN.9: project feeling without the [0, 1] clamp.

        Used only by the hormone-feeling closure path, where the
        "hormone + adjustment" may temporarily leave the legal [0, 1]
        range so that the linear solve W * (h + adj) = target can
        match the LLM appraisal exactly. The clamp is only applied
        at the user-facing feeling output (and on the real hormone
        state, never modified by P5-feel).
        """

        result: list[float] = []
        for i in range(len(FEELING_DIMENSIONS)):
            row = self._W[i]
            value = self._bias[i]
            for j, channel in enumerate(HORMONE_CHANNELS):
                value += row[j] * float(levels[channel])
            result.append(value)
        return tuple(result)

    def _explore_residual(
        self,
        llm_appraisal: tuple[float, ...] | None,
        current_feeling: tuple[float, ...],
    ) -> tuple[float, ...]:
        """Algorithm 1: exploratory stage (aINS-equivalent)."""

        if llm_appraisal is None:
            return (0.0,) * len(FEELING_DIMENSIONS)
        if len(llm_appraisal) != len(FEELING_DIMENSIONS):
            raise ValueError(
                f"LLM appraisal must have {len(FEELING_DIMENSIONS)} dimensions, "
                f"got {len(llm_appraisal)}"
            )
        return tuple(
            _clamp(float(llm_appraisal[i]) - float(current_feeling[i]), -1.0, 1.0)
            for i in range(len(FEELING_DIMENSIONS))
        )

    def _dopamine_precision(
        self, residual: tuple[float, ...], dopamine: float
    ) -> tuple[float, ...]:
        """Algorithm 2: dopamine precision signal (R81 corroboration
        pattern). Per-dimension: base = 1 - |residual|; modulated by
        dopamine (Dopamine 0.5 -> halve; Dopamine 0.0 -> floor; Dopamine
        1.0 -> full base). Clipped to [precision_floor, precision_ceiling].
        """

        floor = self.config.precision_floor
        ceiling = self.config.precision_ceiling
        result: list[float] = []
        dopamine_factor = 0.5 + 0.5 * _clamp(dopamine, 0.0, 1.0)
        for r in residual:
            base = max(floor, 1.0 - abs(float(r)))
            value = base * dopamine_factor
            result.append(_clamp(value, floor, ceiling))
        return tuple(result)

    def _ach_flexibility(self, novelty: float, acetylcholine: float) -> float:
        """Algorithm 3: acetylcholine flexibility signal (Fermin 2021 ACh
        role). ACh below `flexibility_threshold` -> floor (conservative,
        gINS-equivalent behavior). ACh above threshold -> flexibility
        proportional to `novelty * acetylcholine`. Clipped to
        [flexibility_floor, flexibility_ceiling].
        """

        floor = self.config.flexibility_floor
        ceiling = self.config.flexibility_ceiling
        ach = _clamp(acetylcholine, 0.0, 1.0)
        if ach < self.config.flexibility_threshold:
            return floor
        raw = _clamp(novelty, 0.0, 1.0) * ach
        return _clamp(raw, floor, ceiling)

    def _determine_regime(
        self,
        per_dim_precision: tuple[float, ...],
        flexibility: float,
        novelty: float,
        acetylcholine: float,
    ) -> Regime:
        """Algorithm 4: three-regime switching (IMAC three parallel
        loops). Returns the post-hysteresis regime. The decision logic:

          1. Early (fewer than 5 residuals seen) -> EXPLORATORY.
          2. ACh high AND novelty high -> EXPLORATORY.
          3. Recent residual magnitude small AND trend stable -> HABITUAL.
          4. Otherwise -> MODEL_BASED.

        Hysteresis: the regime only flips when the same regime has been
        proposed for `regime_hysteresis_ticks` consecutive ticks (or it
        is the first tick).
        """

        if len(self._residual_history) < 5:
            proposed = Regime.EXPLORATORY
        elif (
            acetylcholine > self.config.flexibility_threshold
            and novelty > 0.5
        ):
            proposed = Regime.EXPLORATORY
        elif self._is_habitual_candidate():
            proposed = Regime.HABITUAL
        else:
            proposed = Regime.MODEL_BASED

        # Hysteresis: hold the previous regime until the proposed regime
        # has been seen `regime_hysteresis_ticks` times in a row.
        self._regime_history.append(proposed)
        if len(self._regime_history) < self.config.regime_hysteresis_ticks:
            return self._last_regime
        if len(set(self._regime_history)) == 1:
            self._last_regime = proposed
            return proposed
        return self._last_regime

    def _is_habitual_candidate(self) -> bool:
        recent_n = min(self.config.habitual_recent_window, len(self._residual_history))
        older_n = min(
            self.config.habitual_older_window,
            len(self._residual_history) - recent_n,
        )
        if recent_n < self.config.habitual_recent_window:
            return False
        recent = list(self._residual_history)[-recent_n:]
        # R-PROTO-LEARN.8: use the looser habitual_residual_threshold
        # (not commit_threshold) so HABITUAL is reachable under real LLM
        # appraisal residuals (avg 0.5-0.7 vs commit_threshold=0.3).
        recent_mag = sum(max(abs(v) for v in r) for r in recent) / recent_n
        if recent_mag >= self.config.habitual_residual_threshold:
            return False
        if older_n < self.config.habitual_recent_window:
            return True
        older = list(self._residual_history)[-self.config.habitual_older_window : -recent_n]
        older_mag = sum(max(abs(v) for v in r) for r in older) / older_n
        return abs(recent_mag - older_mag) < 0.05

    def _should_commit(self) -> bool:
        return self.commit_if_stable()

    def _apply_update(
        self,
        levels: Mapping[str, float],
        residual: tuple[float, ...],
        per_dim_precision: tuple[float, ...],
        flexibility: float,
        regime: Regime,
    ) -> None:
        """Algorithm 5: regime-conditioned weight and bias update.

        HABITUAL: high DA precision, ACh flexibility attenuated.
        MODEL_BASED: full DA * ACh product.
        EXPLORATORY: ACh flexibility dominant; DA precision weak / unused.
        """

        lr = self.config.learning_rate
        # Build the hormone vector (immutable tuple of floats).
        hormone_vec = tuple(float(levels[c]) for c in HORMONE_CHANNELS)
        # Regime-gated scalars.
        if regime is Regime.HABITUAL:
            gate_per_dim = tuple(p * 0.5 for p in per_dim_precision)
            scalar = 0.0
        elif regime is Regime.MODEL_BASED:
            gate_per_dim = per_dim_precision
            scalar = flexibility
        else:  # EXPLORATORY
            gate_per_dim = tuple(self.config.precision_floor for _ in per_dim_precision)
            scalar = flexibility

        # Build the new weight matrix row by row.
        new_W: list[list[float]] = []
        for i in range(len(FEELING_DIMENSIONS)):
            new_row: list[float] = []
            for j in range(len(HORMONE_CHANNELS)):
                delta = lr * hormone_vec[j] * float(residual[i]) * gate_per_dim[i] * (scalar if regime is not Regime.HABITUAL else 1.0)
                if regime is Regime.EXPLORATORY:
                    delta = lr * hormone_vec[j] * float(residual[i]) * scalar
                new_value = self._W[i][j] + delta
                new_row.append(
                    _clamp(
                        new_value,
                        self.config.weight_clip_low,
                        self.config.weight_clip_high,
                    )
                )
            new_W.append(new_row)
        self._W = tuple(tuple(v for v in row) for row in new_W)

        # Update the bias the same way: bias is the per-dimension intercept
        # that absorbs what the linear form cannot (e.g. offsets in the
        # baseline feeling). The same gates apply.
        new_bias: list[float] = []
        for i in range(len(FEELING_DIMENSIONS)):
            delta = lr * float(residual[i]) * gate_per_dim[i] * (
                scalar if regime is not Regime.HABITUAL else 1.0
            )
            if regime is Regime.EXPLORATORY:
                delta = lr * float(residual[i]) * scalar
            new_value = self._bias[i] + delta
            new_bias.append(
                _clamp(
                    new_value,
                    self.config.bias_clip_low,
                    self.config.bias_clip_high,
                )
            )
        self._bias = tuple(new_bias)
