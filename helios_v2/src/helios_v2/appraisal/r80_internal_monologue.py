"""Owner: rapid salience appraisal — internal-monologue dimension estimator.

Provides the `InternalMonologueAppraisalEstimator`, a fixed-dimension estimator used by the
`RapidSalienceAppraisalEngine` per-modality dispatch when a stimulus arrives with
`modality == "internal_monologue"`. The estimator returns a hand-authored, owner-owned
constant `RapidDimensionEstimate`:

- `threat = 0.0` — self-talk carries no external threat content.
- `reward = 0.0` — self-talk is not a primary reward surface.
- `novelty = 0.3` — a self-generated thought is familiar-but-not-fully-redundant; a small
  novelty floor reflects that even rumination is a partially novel re-framing of prior
  experience.
- `social = 0.0` — self-talk is internal; the social channel is not engaged.
- `uncertainty = 0.7` — self-talk is high in categorization uncertainty: the system is
  not deciding, it is re-considering.

These constants are explicitly hand-authored. The mapping is owned by the `03` appraisal
owner. A later P5 learning slice, R81 calibration slice, or `06` memory-affect grounding
slice can revise them. They must not be over-claimed as a calibrated affective model.
Grounding is `C_engineering_hypothesis`.

The estimator is stateless and never raises: `RapidDimensionEstimate` itself enforces
the `[0.0, 1.0]` validation in its `__post_init__` (shared with all `RapidDimensionEstimator`
implementations).
"""

from __future__ import annotations

from dataclasses import dataclass

from helios_v2.appraisal.engine import (
    RapidDimensionEstimate,
    RapidDimensionEstimator,
)
from helios_v2.sensory import Stimulus


@dataclass(frozen=True)
class InternalMonologueAppraisalEstimator(RapidDimensionEstimator):
    """Owner: rapid salience appraisal — internal-monologue fixed-dimension estimator.

    Purpose:
        Map an `internal_monologue` `Stimulus` to a fixed `RapidDimensionEstimate`
        regardless of content. The R80 design is that an active internal monologue
        is "familiar but not social, not threatening, mildly novel, mildly uncertain".

    Failure semantics:
        Stateless; no failure modes beyond the `RapidDimensionEstimate` validation
        which the dataclass `__post_init__` enforces. A non-internal-monologue
        stimulus is still appraised (the `RapidSalienceAppraisalEngine` dispatch
        is responsible for routing).

    Notes:
        Owns the dimension mapping for `modality == "internal_monologue"`. The
        dispatch happens in `RapidSalienceAppraisalEngine._estimate_dimensions`.
        Constants are explicitly hand-authored and documented in the R80
        requirement as the starting anchor — a later slice can revise them.
    """

    novelty: float = 0.3
    uncertainty: float = 0.7
    social: float = 0.0
    threat: float = 0.0
    reward: float = 0.0

    def estimate_dimensions(self, stimulus: Stimulus) -> RapidDimensionEstimate:
        """Owner: rapid salience appraisal.

        Purpose:
            Return the hand-authored fixed dimensions for an `internal_monologue`
            `Stimulus`. The `stimulus` argument is not inspected (this estimator
            is content-independent by design); it is accepted only to satisfy
            the `RapidDimensionEstimator` protocol.

        Inputs:
            One normalized `Stimulus` (its `modality` should be
            `"internal_monologue"`, but the estimator does not assert that
            because the engine dispatch already filters).

        Returns:
            A `RapidDimensionEstimate(threat=0.0, reward=0.0, novelty=0.3,
            social=0.0, uncertainty=0.7)`.

        Raises:
            No direct error contract. The dataclass `__post_init__` validates
            the `[0.0, 1.0]` range on every field.
        """

        del stimulus
        return RapidDimensionEstimate(
            threat=self.threat,
            reward=self.reward,
            novelty=self.novelty,
            social=self.social,
            uncertainty=self.uncertainty,
        )


__all__ = [
    "InternalMonologueAppraisalEstimator",
]
