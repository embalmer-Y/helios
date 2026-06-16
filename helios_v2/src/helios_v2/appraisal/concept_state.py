"""Owner: rapid salience appraisal.

R-PROTO-LEARN.5 (Layer 5 learning, Bayesian update).

This module owns the `EmotionConcept` taxonomy and the `ConceptPrior`
data structure that the appraisal owner maintains across ticks. The
prior encodes "how likely each emotion concept is, given past
observations of the appraisal owner's outputs".

Why this lives here:
- The appraisal owner already owns "what threat / reward mean" (R40).
- The R-PROTO-LEARN 6-layer architecture puts Bayesian concept update
  on the appraisal owner (Layer 5 = "concept prior + Bayesian update").
- A learned prior is the P5 surface for the appraisal dimension; the
  prior itself is the P5 state, the observation mapping is the P5
  update rule, and the read-back into appraisal inputs is the Layer 1
  interoception bridge (R-PROTO-LEARN.1, implemented separately).

Design (minimal viable, R-PROTO-LEARN.5 ship):
- `EmotionConcept`: a (name, description, dimension) triple.
- `ConceptPrior`: a frozen `counts: dict[str, float]` (concept -> accumulated
  weight) + `observations: int` (total observation count). The prior is
  mutable in the sense that we replace the dataclass on update (a new
  `ConceptPrior` instance with updated counts); the `GroundedDimensionEstimator`
  replaces its `concept_prior` field via a public method.
- `bayesian_update`: pure function — takes (prior, observation) -> new prior.
  Uses Laplace smoothing: `new_count(c) = count(c) + learning_rate * weight(c)`.
  The learning_rate defaults to 1.0; a higher rate makes the prior shift
  faster in response to observations.
- `normalize`: maps a `ConceptPrior` to a probability distribution
  (`counts / total`). The `total` is `sum(counts) + smoothing_mass`
  (Laplace smoothing prevents zero probabilities).

Failure semantics:
- All update functions are pure and deterministic. A zero-prior + zero-weight
  observation returns the same prior (no-op, avoids division by zero).
- Empty prior (no concepts) + an observation: prior absorbs the observation;
  the first observation is the only observation.
- `bayesian_update` and `normalize` never raise on valid `ConceptPrior` inputs.

Notes:
- Frozen dataclasses (immutable) -> updates create new instances.
- No I/O, no LLM, no embedding — pure data + arithmetic.
- Layer 5 (Bayesian update) is independent of Layer 6 (fallback); they compose.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping


@dataclass(frozen=True)
class EmotionConcept:
    """Owner: rapid salience appraisal (R-PROTO-LEARN.5).

    Purpose:
        Bind an abstract emotion concept (e.g. "anxiety", "joy", "shame") to a
        dimension ("threat" / "reward" / etc.) and an LLM-friendly description.

    Failure semantics:
        Construction is permissive — the appraisal owner decides which concepts
        are valid. `name` is the identity used by `ConceptPrior` (count key).

    Notes:
        Frozen. The mapping concept -> dimension is the appraisal owner's policy
        (a "shame" concept may map to "threat" with weight 0.7 and "social" with
        weight 0.3).
    """

    name: str
    dimension: str
    description: str
    base_weight: float = 1.0


# --------------------------------------------------------------------------- #
# Default concept taxonomy (R-PROTO-LEARN.5 first-version).                   #
# --------------------------------------------------------------------------- #


# Hand-authored starter set; cross-cultural emotion concept lexicon.
# Each concept is a (name, dimension, description, base_weight) tuple.
# Grounding: `C_engineering_hypothesis` — placeholder, same level as
# the R40 prototypes. P5 learning (or a real dataset) replaces these.
DEFAULT_CONCEPTS: tuple[EmotionConcept, ...] = (
    # threat dimension
    EmotionConcept(
        name="acute_fear",
        dimension="threat",
        description="acute fear response, panic-like arousal, danger present",
        base_weight=1.0,
    ),
    EmotionConcept(
        name="anxiety",
        dimension="threat",
        description="prolonged worry, anticipatory dread, somatic tension",
        base_weight=1.0,
    ),
    EmotionConcept(
        name="shame",
        dimension="threat",
        description="social threat, fear of judgment, self-worth attack",
        base_weight=0.8,
    ),
    EmotionConcept(
        name="sadness",
        dimension="threat",
        description="loss, grief, low arousal negative affect",
        base_weight=0.7,
    ),
    # reward dimension
    EmotionConcept(
        name="joy",
        dimension="reward",
        description="acute happiness, positive emotional peak",
        base_weight=1.0,
    ),
    EmotionConcept(
        name="pride",
        dimension="reward",
        description="sense of accomplishment, recognized achievement",
        base_weight=0.9,
    ),
    EmotionConcept(
        name="love",
        dimension="reward",
        description="secure attachment, deep care, belonging",
        base_weight=1.0,
    ),
    EmotionConcept(
        name="relief",
        dimension="reward",
        description="tension released, threat resolved, safety restored",
        base_weight=0.8,
    ),
)


# --------------------------------------------------------------------------- #
# ConceptPrior                                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ConceptPrior:
    """Owner: rapid salience appraisal (R-PROTO-LEARN.5).

    Purpose:
        Hold the per-concept accumulated weight across all observations.
        The prior is the P5 state for the appraisal owner's emotion concept
        distribution. Updates produce a new `ConceptPrior` (frozen).

    Fields:
        counts: concept name -> accumulated observation weight (non-negative).
        observations: total observation count (sum of weights across all
            observations). Used as a stability signal; not required for
            `normalize`.
        learning_rate: per-update gain. `bayesian_update` multiplies the
            observation weight by `learning_rate` before adding to counts.
            1.0 = full weight; 0.0 = effectively disabled (no learning).
        smoothing_mass: Laplace smoothing mass used in `normalize`. Defaults
            to 1.0 (add-one smoothing), which prevents zero-probability
            concepts without dominating the distribution.

    Failure semantics:
        Empty `counts` + empty `observations` is valid (an unused prior).
        `bayesian_update` accepts any `ConceptPrior` and any mapping.

    Notes:
        Frozen. `bayesian_update` and `normalize` are pure functions over this
        type; the `GroundedDimensionEstimator` keeps a `ConceptPrior` field
        and replaces it on observation.
    """

    counts: Mapping[str, float] = field(default_factory=dict)
    observations: int = 0
    learning_rate: float = 1.0
    smoothing_mass: float = 1.0

    @staticmethod
    def empty(*, learning_rate: float = 1.0, smoothing_mass: float = 1.0) -> "ConceptPrior":
        """Construct an empty prior (no observations yet)."""
        return ConceptPrior(
            counts={},
            observations=0,
            learning_rate=learning_rate,
            smoothing_mass=smoothing_mass,
        )

    @staticmethod
    def from_concepts(
        concepts: tuple[EmotionConcept, ...],
        *,
        learning_rate: float = 1.0,
        smoothing_mass: float = 1.0,
    ) -> "ConceptPrior":
        """Construct a prior seeded from a concept taxonomy (zero-count uniform start)."""
        counts: dict[str, float] = {c.name: 0.0 for c in concepts}
        return ConceptPrior(
            counts=counts,
            observations=0,
            learning_rate=learning_rate,
            smoothing_mass=smoothing_mass,
        )


# --------------------------------------------------------------------------- #
# Pure update + read functions                                              #
# --------------------------------------------------------------------------- #


def bayesian_update(
    prior: ConceptPrior,
    observation: Mapping[str, float],
) -> ConceptPrior:
    """Apply one Bayesian update step to `prior`.

    For each `(concept_name, weight)` in `observation`:
    - weight is multiplied by `prior.learning_rate` (so a higher rate
      accelerates concept convergence).
    - The result is added to `prior.counts[concept_name]` (creating a
      0-initialized entry if absent).

    Returns a new `ConceptPrior` with the updated counts and
    `observations` incremented by 1. The input `prior` is not mutated.

    Failure semantics:
        An empty observation returns a copy of the prior (no-op).
        Unknown concepts are silently added to `counts` (no validation here;
        the appraisal owner decides which concepts are legal).
    """
    if not observation:
        return prior
    rate = prior.learning_rate
    new_counts: dict[str, float] = dict(prior.counts)
    for concept_name, weight in observation.items():
        if not isinstance(weight, (int, float)) or weight < 0:
            # Negative weight is meaningless in this taxonomy; skip.
            continue
        new_counts[concept_name] = new_counts.get(concept_name, 0.0) + rate * float(weight)
    return replace(
        prior,
        counts=new_counts,
        observations=prior.observations + 1,
    )


def normalize(prior: ConceptPrior) -> Mapping[str, float]:
    """Return the Laplace-smoothed probability distribution over concepts.

    For each concept c in `prior.counts`:
        p(c) = (count(c) + smoothing_mass / N) / (total + smoothing_mass)
    where N = number of concepts and `total = sum(counts)`.

    If `prior.counts` is empty, returns an empty mapping.

    Failure semantics:
        Empty prior -> empty mapping. Single concept with zero count and
        smoothing_mass=1.0 -> that concept gets probability 1.0.
    """
    if not prior.counts:
        return {}
    n = len(prior.counts)
    smoothing_per_concept = prior.smoothing_mass / n
    total = sum(prior.counts.values()) + prior.smoothing_mass
    return {
        name: round((count + smoothing_per_concept) / total, 6)
        for name, count in prior.counts.items()
    }


def top_concepts(
    prior: ConceptPrior, k: int = 3
) -> tuple[tuple[str, float], ...]:
    """Return the top-k concepts by current probability (descending).

    Helper for downstream consumers (Layer 1 interoception, R-PROTO-LEARN.1).
    """
    dist = normalize(prior)
    return tuple(
        sorted(dist.items(), key=lambda item: (-item[1], item[0]))[:k]
    )


# --------------------------------------------------------------------------- #
# Heuristic observation mapping (R-PROTO-LEARN.5 owner-internal)            #
# --------------------------------------------------------------------------- #


def observe_dimension(
    estimate_threat: float,
    estimate_reward: float,
    concepts: tuple[EmotionConcept, ...] = DEFAULT_CONCEPTS,
) -> Mapping[str, float]:
    """Map a `RapidDimensionEstimate` to a concept observation.

    Pure function. Owner-internal: the appraisal owner is the only caller.

    Heuristic (first-version, R-PROTO-LEARN.5 ship):
    - threat > 0.5 -> all threat-dimension concepts activated, weight =
      `estimate_threat * concept.base_weight`.
    - reward > 0.5 -> all reward-dimension concepts activated, weight =
      `estimate_reward * concept.base_weight`.
    - both <= 0.5 -> empty observation (no concept activation).

    Returns a dict {concept_name: weight} for the activated concepts.
    An empty dict means "no observation to update on".
    """
    obs: dict[str, float] = {}
    if estimate_threat > 0.5:
        for c in concepts:
            if c.dimension == "threat":
                obs[c.name] = estimate_threat * c.base_weight
    if estimate_reward > 0.5:
        for c in concepts:
            if c.dimension == "reward":
                obs[c.name] = estimate_reward * c.base_weight
    return obs