"""Owner: 06 memory affect and replay layer (R101 P5-ready foundation).

Provides:
- ObjectiveAggregator protocol + ConvexWeightedObjectiveAggregator (T2)
- ObjectiveImportanceEstimator protocol + FirstVersionObjectiveImportanceEstimator (T3)
- DoubleConfirmationGate protocol + FirstVersionDoubleConfirmationGate (T4)
- ObjectiveImportanceLayerResolver (T5)
- RecallUtilityTracker protocol + FirstVersionRecallUtilityTracker (T5)
- MemoryImportanceLoss protocol (T6; declared only, no first-version)
- MemoryTrainingDatasetExtractor protocol + SqlBackedTrainingDatasetExtractor (T6)
- MiningRecord (T6)

Owns:
- Aggregation policy (which weights to apply to the 6-dim vector)
- Gate decision policy (when is a memory worth L4_long vs L2_working)
- Layer upgrade/downgrade policy (resolver over R100's initial layer)
- Cross-tick recall utility tracking (recall count + EMA utility)
- Training dataset extraction seam (P5 plug-in point)

Does not own:
- Actual weight learning (P5 scope; R110+)
- Loss function implementations (P5 scope)
- R100's AffectOutcomeMemoryLayerClassifier (R100 contract preserved; resolver overrides its output)
- Persistence (uses ExperienceStore facade only)
- LLM (uses R81 hormone_prediction projection; never reads raw LLM output)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Literal, Mapping, Protocol, Sequence, runtime_checkable

from helios_v2.memory.contracts import (
    DoubleConfirmationClass,
    DoubleConfirmationResult,
    MemoryAffectReplayError,
    MemoryLayer,
    MemoryRecord,
    OUTCOME_CLASS_WEIGHTS,
    OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT,
    PromotionEvent,
)


# =============================================================================
# Module-level constants (C_engineering_hypothesis first-version)
# =============================================================================

# DoubleConfirmationGate thresholds
OBJECTIVE_PASS_THRESHOLD: float = 0.50
SUBJECTIVE_PASS_THRESHOLD: float = 0.60

# ObjectiveImportanceLayerResolver thresholds
PROMOTE_THRESHOLD: float = 0.70   # L3 + obj >= 0.70 -> L4 (both_pass)
DEMOTE_THRESHOLD: float = 0.85    # L5 + obj < 0.85 -> L4 (objective_only); L4 + obj < 0.70 -> L3

# RecallUtilityTracker EMA alpha
RECALL_EMA_ALPHA: float = 0.3

# Default 6-dim aggregator weights (β-branch R85-A pre-research; C_engineering_hypothesis)
DEFAULT_OBJECTIVE_WEIGHTS: tuple[float, ...] = (0.25, 0.20, 0.15, 0.15, 0.15, 0.10)


# =============================================================================
# Helpers
# =============================================================================


def _safe_get(mapping: Mapping[str, float] | None, key: str, default: float = 0.5) -> float:
    """Read a bounded float from a mapping with safe default. Non-numeric values -> default."""
    if mapping is None:
        return default
    val = mapping.get(key, default)
    if not isinstance(val, (int, float)):
        return default
    return min(1.0, max(0.0, float(val)))


def _novelty_cosine(
    stimulus_text: str,
    recent_summaries: Sequence[str],
    embed_callable: Callable[[str], Sequence[float]] | None,
) -> float:
    """Compute novelty = 1 - max cosine similarity to recent records.

    When embed_callable is None or recent_summaries is empty, returns 0.5 (neutral).
    When embed_callable raises, propagates (no fabricated novelty).
    """
    if not recent_summaries or embed_callable is None:
        return 0.5
    if not stimulus_text:
        return 0.5
    try:
        v = list(embed_callable(stimulus_text))
        if not v:
            return 0.5
        sims = []
        for summary in recent_summaries:
            if not summary:
                continue
            v2 = list(embed_callable(summary))
            if not v2 or len(v) != len(v2):
                continue
            dot = sum(a * b for a, b in zip(v, v2))
            n1 = sum(a * a for a in v) ** 0.5
            n2 = sum(b * b for b in v2) ** 0.5
            if n1 == 0 or n2 == 0:
                continue
            sims.append(dot / (n1 * n2))
        if not sims:
            return 0.5
        max_sim = max(sims)
        novelty = 1.0 - max_sim
        return min(1.0, max(0.0, novelty))
    except Exception:
        # Embed failure: propagate, don't fabricate (per R34 hard-stop semantics).
        raise


# =============================================================================
# T2: ObjectiveAggregator protocol + ConvexWeightedObjectiveAggregator
# =============================================================================


@runtime_checkable
class ObjectiveAggregator(Protocol):
    """Owner: 06 memory affect and replay layer (R101).

    Purpose:
        Aggregate the 6-dim ObjectiveImportanceVector into a single scalar [0, 1].
        Declared as a Protocol so P5 can plug in learned weights / neural net /
        decision tree without schema changes.

    P5 hook:
        declared_weights() returns the current weights for introspection /
        explainability. P5 training reads it, computes update, and produces
        a new ObjectiveAggregator instance.
    """

    def aggregate(self, vector: object) -> float:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Aggregate the 6-dim vector into [0, 1].

        Inputs:
            An ObjectiveImportanceVector instance (declared as object to avoid
            circular import at Protocol declaration time).

        Returns:
            A float in [0, 1].
        """
        ...

    def declared_weights(self) -> tuple[float, ...]:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Return the current 6-dim weights (or analogous parameters) for
            P5 introspection. Length must equal vector dimensionality.

        Returns:
            A tuple of floats (length = vector dimensionality).
        """
        ...


@dataclass(frozen=True)
class ConvexWeightedObjectiveAggregator:
    """Owner: 06 memory affect and replay layer (R101 first-version).

    Purpose:
        First-version convex-combination aggregator. Weights must sum to 1.0
        (with float epsilon 1e-6) and have length 6 to match the 6-dim vector.

    P5 hook:
        Weights are declared in objective_importance_weights learned-parameter
        category. P5 can produce a new instance with updated weights.
    """

    weights: tuple[float, ...] = DEFAULT_OBJECTIVE_WEIGHTS

    def __post_init__(self) -> None:
        if len(self.weights) != 6:
            raise MemoryAffectReplayError(
                f"ConvexWeightedObjectiveAggregator weights must have length 6, got: {len(self.weights)}"
            )
        total = sum(self.weights)
        if abs(total - 1.0) > 1e-6:
            raise MemoryAffectReplayError(
                f"ConvexWeightedObjectiveAggregator weights must sum to 1.0, got: {total}"
            )
        for w in self.weights:
            if w < 0.0:
                raise MemoryAffectReplayError(
                    f"ConvexWeightedObjectiveAggregator weights must be >= 0, got: {w}"
                )

    def aggregate(self, vector: object) -> float:
        from helios_v2.memory.contracts import ObjectiveImportanceVector  # local import
        if not isinstance(vector, ObjectiveImportanceVector):
            raise MemoryAffectReplayError(
                f"ConvexWeightedObjectiveAggregator.aggregate expects ObjectiveImportanceVector, got: {type(vector).__name__}"
            )
        score = (
            self.weights[0] * vector.stimulus_intensity
            + self.weights[1] * vector.cortisol_response
            + self.weights[2] * vector.arousal_response
            + self.weights[3] * vector.outcome_class_weight
            + self.weights[4] * vector.novelty_score
            + self.weights[5] * vector.relationship_risk
        )
        return min(1.0, max(0.0, score))

    def declared_weights(self) -> tuple[float, ...]:
        return tuple(self.weights)


# =============================================================================
# T3: ObjectiveImportanceEstimator protocol + FirstVersionObjectiveImportanceEstimator
# =============================================================================


@runtime_checkable
class ObjectiveImportanceEstimator(Protocol):
    """Owner: 06 memory affect and replay layer (R101).

    Purpose:
        Compute the 6-dim ObjectiveImportanceVector from one tick's stimuli +
        internal state + outcome class. The estimator is a stateless function
        (modulo the injected embed_callable).

    P5 hook:
        P5 can plug in a learned estimator (e.g., a small neural net) without
        changing the MemoryRecord schema.
    """

    def estimate(
        self,
        *,
        stimulus_text: str,
        hormone_snapshot: Mapping[str, float] | None,
        feeling_snapshot: Mapping[str, float] | None,
        outcome_class: str,
        recent_summaries: Sequence[str] = (),
        embed_callable: Callable[[str], Sequence[float]] | None = None,
    ) -> object:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Compute the 6-dim vector.

        Inputs:
            stimulus_text: raw stimulus text (may be empty).
            hormone_snapshot: R80 9-channel hormone mapping (may be None).
            feeling_snapshot: R44 7-dim feeling mapping (may be None).
            outcome_class: 15 outcome taxonomy value.
            recent_summaries: bounded sequence of recent summary strings.
            embed_callable: optional callable for novelty cosine.

        Returns:
            An ObjectiveImportanceVector.
        """
        ...


@dataclass(frozen=True)
class FirstVersionObjectiveImportanceEstimator:
    """Owner: 06 memory affect and replay layer (R101 first-version).

    Purpose:
        Stateless 6-dim vector computation. Uses β-branch R85-A formula
        as the first-version policy. All missing-field paths return
        honest absence (0.5 for most dims, 0.0 for cortisol/arousal
        absent in extreme cases handled by _safe_get default).

    Fields:
        stimulus_length_cap: text length (chars) for normalizing stimulus_intensity to 1.0.
        embed_callable is injected per-tick by composition.
    """

    stimulus_length_cap: int = 200

    def estimate(
        self,
        *,
        stimulus_text: str,
        hormone_snapshot: Mapping[str, float] | None,
        feeling_snapshot: Mapping[str, float] | None,
        outcome_class: str,
        recent_summaries: Sequence[str] = (),
        embed_callable: Callable[[str], Sequence[float]] | None = None,
    ) -> object:
        from helios_v2.memory.contracts import ObjectiveImportanceVector  # local import

        if not stimulus_text:
            intensity = 0.0
        else:
            intensity = min(1.0, len(stimulus_text) / float(self.stimulus_length_cap))

        cortisol = _safe_get(hormone_snapshot, "cortisol", 0.5)
        arousal = _safe_get(feeling_snapshot, "arousal", 0.5)
        oc_weight = OUTCOME_CLASS_WEIGHTS.get(outcome_class, OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT)
        novelty = _novelty_cosine(stimulus_text, recent_summaries, embed_callable)
        social_safety = _safe_get(feeling_snapshot, "social_safety", 0.5)
        relationship_risk = 1.0 - social_safety

        return ObjectiveImportanceVector(
            stimulus_intensity=intensity,
            cortisol_response=cortisol,
            arousal_response=arousal,
            outcome_class_weight=oc_weight,
            novelty_score=novelty,
            relationship_risk=relationship_risk,
        )


# =============================================================================
# T4: DoubleConfirmationGate protocol + FirstVersionDoubleConfirmationGate
# =============================================================================


@runtime_checkable
class DoubleConfirmationGate(Protocol):
    """Owner: 06 memory affect and replay layer (R101).

    Purpose:
        Evaluate the AND-gate between objective 6-dim aggregate and subjective
        R81 hormone prediction. Returns one of four classifications.

    P5 hook:
        P5 can plug in a learned gate (e.g., trained classifier on the same
        objective/subjective inputs) without changing the MemoryRecord schema.
    """

    def evaluate(
        self,
        *,
        objective_score: float,
        subjective_score: float,
        subjective_confidence: float,
        outcome_class: str,
    ) -> DoubleConfirmationResult:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Decide the gate classification.

        Inputs:
            objective_score: aggregator.aggregate(vector) ∈ [0, 1].
            subjective_score: R81 max hormone prediction ∈ [0, 1]; 0.0 when absent.
            subjective_confidence: confidence of subjective signal ∈ [0, 1]; 0.0 when absent.
            outcome_class: 15 outcome taxonomy (reserved for future use).

        Returns:
            A DoubleConfirmationResult (frozen dataclass).
        """
        ...


@dataclass(frozen=True)
class FirstVersionDoubleConfirmationGate:
    """Owner: 06 memory affect and replay layer (R101 first-version).

    Purpose:
        AND-gate with two thresholds. First-version thresholds are constants;
        P5 can produce a new instance with learned thresholds.
    """

    threshold_objective: float = OBJECTIVE_PASS_THRESHOLD
    threshold_subjective: float = SUBJECTIVE_PASS_THRESHOLD

    def evaluate(
        self,
        *,
        objective_score: float,
        subjective_score: float,
        subjective_confidence: float,
        outcome_class: str,
    ) -> DoubleConfirmationResult:
        obj_pass = objective_score >= self.threshold_objective
        subj_pass = subjective_score >= self.threshold_subjective
        if obj_pass and subj_pass:
            cls: DoubleConfirmationClass = "both_pass"
        elif obj_pass and not subj_pass:
            cls = "objective_only"
        elif not obj_pass and subj_pass:
            cls = "subjective_only"
        else:
            cls = "skip"
        return DoubleConfirmationResult(
            classification=cls,
            objective_score=objective_score,
            subjective_score=subjective_score,
            confidence=subjective_confidence,
        )


# =============================================================================
# T5: ObjectiveImportanceLayerResolver
# =============================================================================


@dataclass(frozen=True)
class ObjectiveImportanceLayerResolver:
    """Owner: 06 memory affect and replay layer (R101).

    Purpose:
        Adjust the R100 initial layer based on R101's double-confirmation
        verdict and objective score. Implements upgrade (L3→L4, L2→L5) and
        downgrade (L5→L4, L4→L3) rules per design §3.6.

    P5 hook:
        Promote/demote thresholds are C_engineering_hypothesis first-version
        constants under objective_importance_weights category.
    """

    promote_threshold: float = PROMOTE_THRESHOLD
    demote_threshold: float = DEMOTE_THRESHOLD
    identity_outcome_classes: tuple[str, ...] = ("self_changed",)

    def resolve(
        self,
        *,
        initial_layer: MemoryLayer,
        objective_score: float | None,
        double_confirmation_class: DoubleConfirmationClass | None,
        outcome_class: str,
    ) -> MemoryLayer:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Compute the final layer.

        Inputs:
            initial_layer: layer from R100's AffectOutcomeMemoryLayerClassifier.
            objective_score: aggregator output; None if R101 path absent.
            double_confirmation_class: gate verdict; None if R101 path absent.
            outcome_class: 15 outcome taxonomy.

        Returns:
            A MemoryLayer (4-tier taxonomy).
        """
        # Skip -> L2_working (conservative; record retained as negative training data)
        if double_confirmation_class == "skip":
            return "L2_working"

        # If no R101 signals (None), preserve R100 initial layer (byte-for-byte).
        if objective_score is None or double_confirmation_class is None:
            return initial_layer

        # Both_pass: keep or promote
        if double_confirmation_class == "both_pass":
            if initial_layer == "L5_autobiographical":
                return "L5_autobiographical"
            if initial_layer == "L4_long":
                return "L4_long"
            if initial_layer == "L3_short" and objective_score >= self.promote_threshold:
                return "L4_long"
            if (
                initial_layer == "L2_working"
                and objective_score >= self.demote_threshold
                and outcome_class in self.identity_outcome_classes
            ):
                return "L5_autobiographical"
            return initial_layer

        # Objective_only: demote L4/L5 if objective_score below threshold
        if double_confirmation_class == "objective_only":
            if initial_layer == "L5_autobiographical" and objective_score < self.demote_threshold:
                return "L4_long"
            if initial_layer == "L4_long" and objective_score < self.promote_threshold:
                return "L3_short"
            return initial_layer

        # Subjective_only: preserve R100 initial layer (conservative)
        return initial_layer


# =============================================================================
# T5: RecallUtilityTracker protocol + FirstVersionRecallUtilityTracker
# =============================================================================


@runtime_checkable
class RecallUtilityTracker(Protocol):
    """Owner: 06 memory affect and replay layer (R101).

    Purpose:
        Track cross-tick recall + utility signals on MemoryRecord. R101 only
        implements the protocol + EMA update; utility semantic judgment
        ("was this recall useful?") is R102 + P5 scope.

    P5 hook:
        EMA alpha is C_engineering_hypothesis first-version constant under
        objective_importance_weights category; P5 can plug in a learned update rule.
    """

    def record_recall(self, record: MemoryRecord, current_tick: int) -> MemoryRecord:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Return a new MemoryRecord with recall_count incremented and
            last_recall_at_tick updated.

        Inputs:
            record: the recalled MemoryRecord.
            current_tick: tick where the recall happened.

        Returns:
            A new MemoryRecord with updated fields.
        """
        ...

    def record_utility(self, record: MemoryRecord, utility: float, current_tick: int) -> MemoryRecord:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Return a new MemoryRecord with recall_utility_score updated via EMA.

        Inputs:
            record: the recalled MemoryRecord.
            utility: utility signal in [0, 1] (R102 + P5 provide semantics).
            current_tick: tick where the utility observation happened.

        Returns:
            A new MemoryRecord with updated fields.
        """
        ...


@dataclass(frozen=True)
class FirstVersionRecallUtilityTracker:
    """Owner: 06 memory affect and replay layer (R101 first-version).

    Purpose:
        EMA-based utility tracker. Alpha is first-version constant.
    """

    ema_alpha: float = RECALL_EMA_ALPHA

    def record_recall(self, record: MemoryRecord, current_tick: int) -> MemoryRecord:
        from dataclasses import replace
        return replace(
            record,
            recall_count=record.recall_count + 1,
            last_recall_at_tick=current_tick,
        )

    def record_utility(self, record: MemoryRecord, utility: float, current_tick: int) -> MemoryRecord:
        from dataclasses import replace
        if not (0.0 <= utility <= 1.0):
            raise MemoryAffectReplayError(
                f"RecallUtilityTracker.record_utility: utility must be in [0, 1], got: {utility}"
            )
        old = record.recall_utility_score
        if old is None:
            new = utility
        else:
            new = self.ema_alpha * utility + (1.0 - self.ema_alpha) * old
        return replace(
            record,
            recall_utility_score=min(1.0, max(0.0, new)),
            last_recall_at_tick=current_tick,
        )


# =============================================================================
# T6: MemoryImportanceLoss protocol (declared only; P5 implements)
# =============================================================================


@runtime_checkable
class MemoryImportanceLoss(Protocol):
    """Owner: 06 memory affect and replay layer (R101 P5 hook).

    Purpose:
        Compute a loss value given a memory's predicted objective score and
        observed recall utility. R101 does NOT provide a first-version
        implementation — P5 scope (R110+) will provide MSE / Huber / Contrastive
        variants.

    P5 hook:
        This protocol is the central contract for P5 training. P5 will produce
        implementations that consume extracted MiningRecord datasets.
    """

    def loss(
        self,
        *,
        predicted_objective_score: float,
        observed_recall_utility: float | None,
        recall_count: int,
        record: MemoryRecord,
    ) -> float:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Compute the loss value.

        Inputs:
            predicted_objective_score: aggregator output.
            observed_recall_utility: cross-tick utility observation; None when absent.
            recall_count: how many times this memory was recalled.
            record: the full MemoryRecord for context.

        Returns:
            A non-negative float (loss value).
        """
        ...


# =============================================================================
# T6: MemoryTrainingDatasetExtractor protocol + MiningRecord + SqlBackedTrainingDatasetExtractor
# =============================================================================


@dataclass(frozen=True)
class MiningRecord:
    """Owner: 06 memory affect and replay layer (R101 P5 hook).

    Purpose:
        Training-data projection of a MemoryRecord for P5 learning.
        Captures all objective / subjective / utility / layer / outcome fields
        so P5 can compute loss and update aggregator / gate / resolver
        without re-querying the persistence layer.
    """

    memory_id: str
    objective_vector: object   # ObjectiveImportanceVector; declared as object to avoid circular import
    objective_score: float
    subjective_score: float | None
    double_confirmation_class: DoubleConfirmationClass
    recall_count: int
    recall_utility_score: float | None
    last_updated_at_wall: float | None
    layer: MemoryLayer
    outcome_class: str
    tick_id: int | None


@runtime_checkable
class MemoryTrainingDatasetExtractor(Protocol):
    """Owner: 06 memory affect and replay layer (R101 P5 hook).

    Purpose:
        Extract a filtered subset of MemoryRecords for P5 training. P5 calls
        this to build its training dataset each epoch.

    P5 hook:
        Filters cover all major training-subset patterns (positive vs negative
        examples, high-recall memories, recent memories, layer-specific).
    """

    def extract_mining_dataset(
        self,
        *,
        min_recall_count: int = 0,
        min_objective_score: float = 0.0,
        layer_filter: tuple[MemoryLayer, ...] | None = None,
        double_confirmation_filter: tuple[DoubleConfirmationClass, ...] | None = None,
        since_wall_seconds: float | None = None,
        limit: int | None = None,
    ) -> tuple[MiningRecord, ...]:
        """Owner: 06 memory affect and replay layer.

        Purpose:
            Extract a filtered tuple of MiningRecord.

        Inputs:
            min_recall_count: only include records with recall_count >= N.
            min_objective_score: only include records with objective_score >= N.
            layer_filter: only include records in these layers.
            double_confirmation_filter: only include records in these classes.
            since_wall_seconds: only include records with last_updated_at_wall >= T.
            limit: maximum number of records to return (None = no cap).

        Returns:
            A tuple of MiningRecord (possibly empty).
        """
        ...


@dataclass(frozen=True)
class SqlBackedTrainingDatasetExtractor:
    """Owner: 06 memory affect and replay layer (R101 P5 first-version).

    Purpose:
        First-version extractor that pulls from ExperienceStore facade. Uses
        read_recent with layer_filter, then applies remaining filters in-memory.

    P5 hook:
        P5 can replace this with a streaming / batched extractor that avoids
        loading all records into memory.
    """

    experience_store: object  # ExperienceStore facade; declared as object to avoid circular import

    def extract_mining_dataset(
        self,
        *,
        min_recall_count: int = 0,
        min_objective_score: float = 0.0,
        layer_filter: tuple[MemoryLayer, ...] | None = None,
        double_confirmation_filter: tuple[DoubleConfirmationClass, ...] | None = None,
        since_wall_seconds: float | None = None,
        limit: int | None = None,
    ) -> tuple[MiningRecord, ...]:
        from helios_v2.memory.contracts import ObjectiveImportanceVector  # local import

        store = self.experience_store
        if store is None:
            return ()

        # Fetch a bounded window; P5 may tune this.
        fetch_limit = limit if limit is not None else 10000
        try:
            records = store.read_recent(limit=fetch_limit, layer_filter=layer_filter[0] if layer_filter and len(layer_filter) == 1 else None)
        except Exception:
            return ()

        out: list[MiningRecord] = []
        for r in records:
            # Filter on objective_score / recall_count / double_confirmation / since_wall
            obj_score = getattr(r, "objective_score", None)
            if obj_score is not None and obj_score < min_objective_score:
                continue
            recall_count = getattr(r, "recall_count", None) or 0
            if recall_count < min_recall_count:
                continue
            dc_class = getattr(r, "double_confirmation_class", None)
            if double_confirmation_filter is not None and dc_class not in double_confirmation_filter:
                continue
            last_updated = getattr(r, "last_updated_at_wall", None)
            if since_wall_seconds is not None and (last_updated is None or last_updated < since_wall_seconds):
                continue
            if layer_filter is not None and len(layer_filter) > 1 and r.layer not in layer_filter:
                continue

            # Deserialize objective_importance JSON
            obj_json = getattr(r, "objective_importance_json", None)
            try:
                obj_vector = ObjectiveImportanceVector.from_json(obj_json) if obj_json else ObjectiveImportanceVector(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
            except MemoryAffectReplayError:
                continue

            out.append(
                MiningRecord(
                    memory_id=r.record_id,
                    objective_vector=obj_vector,
                    objective_score=obj_score if obj_score is not None else 0.5,
                    subjective_score=getattr(r, "subjective_score", None),
                    double_confirmation_class=dc_class if dc_class is not None else "skip",
                    recall_count=recall_count,
                    recall_utility_score=getattr(r, "recall_utility_score", None),
                    last_updated_at_wall=last_updated,
                    layer=r.layer if r.layer is not None else "L2_working",
                    outcome_class=getattr(r, "outcome_class", "no_outcome") or "no_outcome",
                    tick_id=getattr(r, "tick_id", None),
                )
            )
            if limit is not None and len(out) >= limit:
                break
        return tuple(out)