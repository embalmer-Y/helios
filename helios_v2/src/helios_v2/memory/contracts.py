"""Owner: memory affect and replay layer.

Owns:
- affect-linked memory contracts
- replay-candidate contracts
- memory record and publication ops contracts
- R101: 6-dim objective importance vector + double-confirmation gate result
- R101: cross-tick utility tracking fields + promotion event log

Does not own:
- feeling construction
- conscious workspace promotion
- identity writeback
- objective importance aggregation (R101 protocol owned separately)
- loss function implementations (R101 protocol declared, P5 owns)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise MemoryAffectReplayError(f"{name} must be within [0.0, 1.0]")


MemoryFamily = Literal["episodic", "semantic", "autobiographical"]
ReplayReason = Literal[
    "high_affect_intensity",
    "unresolved_tension_or_discomfort",
    "prediction_mismatch_or_surprise",
]
MemoryLearnedParameterCategory = Literal[
    "memory_family_write_policy",
    "replay_priority_policy",
    "consolidation_policy",
    "layer_assignment_policy",
    "objective_importance_weights",   # R101: aggregator weights + gate thresholds + resolver thresholds
]

MemoryLayer = Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]

VALID_MEMORY_LAYERS = frozenset({"L2_working", "L3_short", "L4_long", "L5_autobiographical"})

# R101: outcome-class weights for 6-dim objective importance vector.
# Covers the full `15` outcome taxonomy at write time.
# Unknown outcome_class falls back to 0.5 (neutral; honest absence).
OUTCOME_CLASS_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "self_changed": 0.95,
    "world_changed": 0.80,
    "continuity_written": 0.70,
    "executed": 0.55,
    "rejected": 0.40,
    "blocked": 0.35,
    "internal_only_decision": 0.25,
    "no_outcome": 0.20,
})

OUTCOME_CLASS_WEIGHTS_NEUTRAL_DEFAULT = 0.5


# =============================================================================
# R101: Double-confirmation gate taxonomy (objective vs subjective AND-gate)
# =============================================================================

DoubleConfirmationClass = Literal["both_pass", "objective_only", "subjective_only", "skip"]


# =============================================================================
# R101: 6-dimensional objective importance vector + JSON serialization
# =============================================================================


@dataclass(frozen=True)
class ObjectiveImportanceVector:
    """Owner: memory affect and replay layer (R101).

    Purpose:
        One immutable 6-dimensional objective importance vector capturing
        independent cognitive signals that determine whether a memory should be
        persisted as L4_long / L5_autobiographical or demoted to L2_working.

    Fields:
        stimulus_intensity: text/stimulus length + complexity proxy (0..1)
        cortisol_response: HPA axis response (R80 neuromodulator cortisol, [0, 1])
        arousal_response: felt arousal (R44 feeling, [0, 1])
        outcome_class_weight: mapped from OUTCOME_CLASS_WEIGHTS ([0.20, 0.95])
        novelty_score: 1 - max cosine to stored memory (R96 embedding, [0, 1])
        relationship_risk: 1 - social_safety ([0, 1])

    Failure semantics:
        Construction raises MemoryAffectReplayError on any field outside [0, 1].

    P5 hook:
        Aggregation is via ObjectiveAggregator protocol (NOT a method here).
        JSON serialization enables P5 SQL extraction via SqlBackedTrainingDatasetExtractor.
    """

    stimulus_intensity: float
    cortisol_response: float
    arousal_response: float
    outcome_class_weight: float
    novelty_score: float
    relationship_risk: float

    def __post_init__(self) -> None:
        for name in (
            "stimulus_intensity",
            "cortisol_response",
            "arousal_response",
            "outcome_class_weight",
            "novelty_score",
            "relationship_risk",
        ):
            _validate_unit_interval(f"ObjectiveImportanceVector.{name}", getattr(self, name))

    def to_json(self) -> str:
        """Deterministic JSON serialization for SQLite persistence."""
        return json.dumps(
            {
                "stimulus_intensity": self.stimulus_intensity,
                "cortisol_response": self.cortisol_response,
                "arousal_response": self.arousal_response,
                "outcome_class_weight": self.outcome_class_weight,
                "novelty_score": self.novelty_score,
                "relationship_risk": self.relationship_risk,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def from_json(s: str) -> ObjectiveImportanceVector:
        """Deserialize from JSON. Raises MemoryAffectReplayError on malformed input."""
        try:
            d = json.loads(s)
        except (TypeError, ValueError) as exc:
            raise MemoryAffectReplayError(
                f"ObjectiveImportanceVector.from_json: malformed JSON: {exc}"
            ) from exc
        required = {
            "stimulus_intensity",
            "cortisol_response",
            "arousal_response",
            "outcome_class_weight",
            "novelty_score",
            "relationship_risk",
        }
        missing = required - set(d.keys())
        if missing:
            raise MemoryAffectReplayError(
                f"ObjectiveImportanceVector.from_json: missing fields: {sorted(missing)}"
            )
        return ObjectiveImportanceVector(
            stimulus_intensity=float(d["stimulus_intensity"]),
            cortisol_response=float(d["cortisol_response"]),
            arousal_response=float(d["arousal_response"]),
            outcome_class_weight=float(d["outcome_class_weight"]),
            novelty_score=float(d["novelty_score"]),
            relationship_risk=float(d["relationship_risk"]),
        )


# =============================================================================
# R101: Double-confirmation gate result
# =============================================================================


@dataclass(frozen=True)
class DoubleConfirmationResult:
    """Owner: memory affect and replay layer (R101).

    Purpose:
        Immutable outcome of a DoubleConfirmationGate evaluation: the joint verdict
        of the 6-dim objective score and the R81 hormone-prediction subjective signal.

    Fields:
        classification: one of four AND-gate outcomes (both_pass / objective_only /
                       subjective_only / skip).
        objective_score: aggregator.aggregate(vector) ∈ [0, 1].
        subjective_score: max R81 hormone_prediction value ∈ [0, 1]; 0.0 when absent.
        confidence: subjective signal confidence ∈ [0, 1]; 0.0 when subjective absent.

    Failure semantics:
        Construction raises MemoryAffectReplayError on out-of-range scores or
        invalid classification.
    """

    classification: DoubleConfirmationClass
    objective_score: float
    subjective_score: float
    confidence: float

    def __post_init__(self) -> None:
        if self.classification not in ("both_pass", "objective_only", "subjective_only", "skip"):
            raise MemoryAffectReplayError(
                f"DoubleConfirmationResult.classification must be a DoubleConfirmationClass literal, got: {self.classification}"
            )
        _validate_unit_interval("DoubleConfirmationResult.objective_score", self.objective_score)
        _validate_unit_interval("DoubleConfirmationResult.subjective_score", self.subjective_score)
        _validate_unit_interval("DoubleConfirmationResult.confidence", self.confidence)


# =============================================================================
# R101: Promotion event log entry (used by R102; declared in R101 for schema readiness)
# =============================================================================


@dataclass(frozen=True)
class PromotionEvent:
    """Owner: memory affect and replay layer (R101).

    Purpose:
        One immutable log entry recording a layer promotion (L3→L4, L4→L5, etc.)
        that R102 will append. Declared in R101 so the schema is stable; logic
        arrives in R102.

    Fields:
        event_id: unique identifier.
        from_layer: layer before promotion.
        to_layer: layer after promotion.
        tick_id: tick of promotion.
        wall_seconds: R92 wall-time at promotion.
        reason: short string identifying the trigger ("recall_count_threshold",
                "objective_score_threshold", "decay_rebalance", ...).
    """

    event_id: str
    from_layer: MemoryLayer
    to_layer: MemoryLayer
    tick_id: int
    wall_seconds: float | None
    reason: str

    def __post_init__(self) -> None:
        if not self.event_id:
            raise MemoryAffectReplayError("PromotionEvent must declare a non-empty event_id")
        if self.from_layer not in VALID_MEMORY_LAYERS:
            raise MemoryAffectReplayError(
                f"PromotionEvent.from_layer must use the 4-layer taxonomy, got: {self.from_layer}"
            )
        if self.to_layer not in VALID_MEMORY_LAYERS:
            raise MemoryAffectReplayError(
                f"PromotionEvent.to_layer must use the 4-layer taxonomy, got: {self.to_layer}"
            )
        if not self.reason:
            raise MemoryAffectReplayError("PromotionEvent must declare a non-empty reason")


@dataclass(frozen=True)
class PredictionMismatchEvidence:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent the minimal explicit upstream evidence contract used for prediction-mismatch replay triggers.

    Failure semantics:
        Missing provenance or out-of-range evidence values raise `MemoryAffectReplayError`.
    """

    evidence_id: str
    source_reference_id: str
    mismatch_score: float
    anomaly_score: float
    confidence: float

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise MemoryAffectReplayError("PredictionMismatchEvidence must declare a non-empty evidence_id")
        if not self.source_reference_id:
            raise MemoryAffectReplayError(
                "PredictionMismatchEvidence must declare a non-empty source_reference_id"
            )
        _validate_unit_interval("PredictionMismatchEvidence.mismatch_score", self.mismatch_score)
        _validate_unit_interval("PredictionMismatchEvidence.anomaly_score", self.anomaly_score)
        _validate_unit_interval("PredictionMismatchEvidence.confidence", self.confidence)


@dataclass(frozen=True)
class MemoryContentPacket:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent the minimal content payload attached to one memory item without claiming full event-snapshot ownership.

    Failure semantics:
        Missing content identity or an empty payload raise `MemoryAffectReplayError`.
    """

    content_kind: str
    summary_ref: str | None
    context_ref: str | None
    salient_tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.content_kind:
            raise MemoryAffectReplayError("MemoryContentPacket must declare a non-empty content_kind")
        if not self.summary_ref and not self.context_ref and not self.salient_tokens:
            raise MemoryAffectReplayError(
                "MemoryContentPacket must carry at least one summary_ref, context_ref, or salient token"
            )
        if any(not token for token in self.salient_tokens):
            raise MemoryAffectReplayError("MemoryContentPacket salient_tokens must not contain empty values")


@dataclass(frozen=True)
class MemoryBindingContext:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent explicit upstream binding context supplied to memory formation.

    Failure semantics:
        Missing identity or malformed content packets raise `MemoryAffectReplayError`.
    """

    context_id: str
    source_kind: str
    content: MemoryContentPacket

    def __post_init__(self) -> None:
        if not self.context_id:
            raise MemoryAffectReplayError("MemoryBindingContext must declare a non-empty context_id")
        if not self.source_kind:
            raise MemoryAffectReplayError("MemoryBindingContext must declare a non-empty source_kind")


@dataclass(frozen=True)
class MemoryAffectReplayConfig:
    """Owner: memory affect and replay layer.

    Purpose:
        Expose the confirmed initialization and learned-policy surface for memory affect and replay.

    Failure semantics:
        Invalid legal ranges, storage bootstrap identity, or unsupported learned-parameter policy raise `MemoryAffectReplayError`.
    """

    legal_min_priority: float
    legal_max_priority: float
    storage_bootstrap_state_id: str
    mandatory_learned_parameters: tuple[MemoryLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected_base = {
            "memory_family_write_policy",
            "replay_priority_policy",
            "consolidation_policy",
        }
        expected_with_layer = expected_base | {"layer_assignment_policy"}
        actual = set(self.mandatory_learned_parameters)
        if actual not in (expected_base, expected_with_layer):
            raise MemoryAffectReplayError(
                "Memory config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("MemoryAffectReplayConfig.legal_min_priority", self.legal_min_priority)
        _validate_unit_interval("MemoryAffectReplayConfig.legal_max_priority", self.legal_max_priority)
        if self.legal_min_priority > self.legal_max_priority:
            raise MemoryAffectReplayError("Memory config priority range is inverted")
        if not self.storage_bootstrap_state_id:
            raise MemoryAffectReplayError(
                "Memory config must declare a non-empty storage_bootstrap_state_id"
            )


@dataclass(frozen=True)
class AffectTaggedMemoryItem:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent one immutable affect-linked memory item with provenance and minimal content.

    Failure semantics:
        Missing provenance or malformed content raise `MemoryAffectReplayError`.
    """

    memory_id: str
    family: MemoryFamily
    source_feeling_state_id: str
    affect_tag: InteroceptiveFeelingVector
    content: MemoryContentPacket
    binding_context_id: str | None
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise MemoryAffectReplayError("AffectTaggedMemoryItem must declare a non-empty memory_id")
        if not self.source_feeling_state_id:
            raise MemoryAffectReplayError(
                "AffectTaggedMemoryItem must declare a non-empty source_feeling_state_id"
            )


@dataclass(frozen=True)
class MemoryReplayCandidate:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent one immutable replay candidate with replay reasons and optional bounded continuous priority.

    Failure semantics:
        Missing identity, unsupported replay reasons, or out-of-range priority raise `MemoryAffectReplayError`.
    """

    candidate_id: str
    memory_id: str
    family: MemoryFamily
    source_feeling_state_id: str
    replay_reasons: tuple[ReplayReason, ...]
    forced_consolidation: bool
    priority_hint: float | None

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise MemoryAffectReplayError("MemoryReplayCandidate must declare a non-empty candidate_id")
        if not self.memory_id:
            raise MemoryAffectReplayError("MemoryReplayCandidate must declare a non-empty memory_id")
        if not self.source_feeling_state_id:
            raise MemoryAffectReplayError(
                "MemoryReplayCandidate must declare a non-empty source_feeling_state_id"
            )
        if not self.replay_reasons:
            raise MemoryAffectReplayError("MemoryReplayCandidate must declare at least one replay reason")
        if self.priority_hint is not None:
            _validate_unit_interval("MemoryReplayCandidate.priority_hint", self.priority_hint)


@dataclass(frozen=True)
class RecalledMemoryFact:
    """Owner: memory affect and replay layer (R52).

    Purpose:
        One bounded raw fact about a recalled prior affect-memory, supplied to the `06` owner by
        an injected `RecalledMemoryProvider`. It is the input from which the owner re-forms a
        replayed `AffectTaggedMemoryItem` and a non-forced replay candidate; it carries no
        priority and no item/candidate identity (the owner computes those).

    Failure semantics:
        Construction raises `MemoryAffectReplayError` on an empty `memory_id`/`summary`, a family
        outside the taxonomy, or a `recall_similarity` outside `[0, 1]`.

    Notes:
        `affect` is the recalled memory's ORIGINAL felt affect (reconstructed from durable
        storage by the provider), not the current tick's feeling. `recall_similarity` is the
        cosine relevance of the recalled memory to the current context. The owner never reads
        these as a salience mapping by themselves; it owns how they map into a replay priority.
    """

    memory_id: str
    family: MemoryFamily
    summary: str
    recall_similarity: float
    affect: InteroceptiveFeelingVector

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise MemoryAffectReplayError("RecalledMemoryFact must declare a non-empty memory_id")
        if not self.summary:
            raise MemoryAffectReplayError("RecalledMemoryFact must declare a non-empty summary")
        if self.family not in ("episodic", "semantic", "autobiographical"):
            raise MemoryAffectReplayError("RecalledMemoryFact family must use the fixed MemoryFamily taxonomy")
        _validate_unit_interval("RecalledMemoryFact.recall_similarity", self.recall_similarity)


@dataclass(frozen=True)
class MemoryFormationState:
    """Owner: memory affect and replay layer.

    Purpose:
        Represent one immutable memory-owner snapshot containing memory items, replay candidates, and memory records.

    Failure semantics:
        Missing provenance or malformed state identity raise `MemoryAffectReplayError`.
    """

    state_id: str
    source_feeling_state_id: str
    memory_items: tuple[AffectTaggedMemoryItem, ...]
    replay_candidates: tuple[MemoryReplayCandidate, ...]
    tick_id: int | None
    memory_records: tuple[MemoryRecord, ...] = ()   # R100 additive: layer-assigned cognitive records

    def __post_init__(self) -> None:
        if not self.state_id:
            raise MemoryAffectReplayError("MemoryFormationState must declare a non-empty state_id")
        if not self.source_feeling_state_id:
            raise MemoryAffectReplayError(
                "MemoryFormationState must declare a non-empty source_feeling_state_id"
            )
        memory_ids = {item.memory_id for item in self.memory_items}
        for candidate in self.replay_candidates:
            if candidate.memory_id not in memory_ids:
                raise MemoryAffectReplayError(
                    "MemoryFormationState replay candidates must reference published memory_items"
                )
            if candidate.source_feeling_state_id != self.source_feeling_state_id:
                raise MemoryAffectReplayError(
                    "MemoryFormationState replay candidates must preserve the source_feeling_state_id of the owner state"
                )
        # R100: memory_records provenance and referential integrity
        for record in self.memory_records:
            if record.source_feeling_state_id != self.source_feeling_state_id:
                raise MemoryAffectReplayError(
                    "MemoryFormationState memory records must preserve the source_feeling_state_id of the owner state"
                )
            if record.memory_id not in memory_ids:
                raise MemoryAffectReplayError(
                    "MemoryFormationState memory records must reference published memory_items"
                )


@dataclass(frozen=True)
class MemoryRecord:
    """Owner: memory affect and replay layer.

    Purpose:
        One immutable cognitive memory record carrying the layer assignment
        determined at write time by the injected classifier. This is the `06`
        cognitive contract; `33` stores its projection on PersistedExperienceRecord.

    R101 P5-ready extensions:
        The 9 additive fields below (objective_importance / objective_score /
        subjective_score / double_confirmation / recall_count /
        last_recall_at_tick / recall_utility_score / last_updated_at_wall /
        promotion_history) provide the cross-tick utility tracking + objective 6-dim
        vector + double-confirmation verdict that the P5 learning loop will consume.
        All fields are additive and default to safe values so legacy callers
        (R100 path) see byte-for-byte unchanged behavior.

    Failure semantics:
        Construction raises MemoryAffectReplayError on empty required fields,
        out-of-range affect_intensity, invalid MemoryLayer, or invalid R101
        field values.
    """

    memory_id: str
    layer: MemoryLayer
    affect_intensity_at_write: float          # frozen fact, [0, 1]
    outcome_class_at_write: str               # the 15 outcome taxonomy
    source_feeling_state_id: str
    family: MemoryFamily
    content: MemoryContentPacket
    binding_context_id: str | None
    tick_id: int | None
    created_at_wall: float | None             # R92 wall-time at write
    memory_metadata: Mapping[str, str] = field(default_factory=dict)

    # R101: P5-ready additive fields (all default-safe; legacy path unaffected)
    objective_importance: ObjectiveImportanceVector | None = None
    objective_score: float | None = None
    subjective_score: float | None = None
    double_confirmation: DoubleConfirmationResult | None = None
    recall_count: int = 0
    last_recall_at_tick: int | None = None
    recall_utility_score: float | None = None
    last_updated_at_wall: float | None = None
    promotion_history: tuple[PromotionEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise MemoryAffectReplayError("MemoryRecord must declare a non-empty memory_id")
        if not self.source_feeling_state_id:
            raise MemoryAffectReplayError(
                "MemoryRecord must declare a non-empty source_feeling_state_id"
            )
        if self.layer not in VALID_MEMORY_LAYERS:
            raise MemoryAffectReplayError(
                f"MemoryRecord layer must use the 4-layer taxonomy, got: {self.layer}"
            )
        _validate_unit_interval("MemoryRecord.affect_intensity_at_write", self.affect_intensity_at_write)
        if not self.outcome_class_at_write:
            raise MemoryAffectReplayError("MemoryRecord must declare a non-empty outcome_class_at_write")
        metadata = dict(self.memory_metadata)
        for key, value in metadata.items():
            if not key or not isinstance(value, str):
                raise MemoryAffectReplayError(
                    "MemoryRecord memory_metadata must map non-empty keys to string values"
                )
        object.__setattr__(self, "memory_metadata", MappingProxyType(metadata))

        # R101: validate additive fields (None-allowed + range checks when present)
        if self.objective_score is not None:
            _validate_unit_interval("MemoryRecord.objective_score", self.objective_score)
        if self.subjective_score is not None:
            _validate_unit_interval("MemoryRecord.subjective_score", self.subjective_score)
        if self.recall_count < 0:
            raise MemoryAffectReplayError(
                f"MemoryRecord.recall_count must be >= 0, got: {self.recall_count}"
            )
        if self.recall_utility_score is not None:
            _validate_unit_interval(
                "MemoryRecord.recall_utility_score", self.recall_utility_score
            )


@dataclass(frozen=True)
class RecordMemoryOp:
    """Owner: memory affect and replay layer.

    Purpose:
        Describe one request to record affect-linked memory state from feeling and explicit binding context.

    Failure semantics:
        Malformed request summaries must be rejected explicitly.
    """

    op_name: str
    owner: str
    feeling_state_id: str
    binding_context_id: str | None
    mismatch_evidence_id: str | None


@dataclass(frozen=True)
class PublishReplayCandidatesOp:
    """Owner: memory affect and replay layer.

    Purpose:
        Describe publication of replay candidates owned by the memory affect and replay layer.

    Failure semantics:
        Publication must not occur if the replay-candidate set is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    candidate_count: int
    families: tuple[str, ...]


@dataclass(frozen=True)
class PublishMemoryFormationStateOp:
    """Owner: memory affect and replay layer.

    Purpose:
        Describe publication of one immutable memory-formation state snapshot.

    Failure semantics:
        Publication must not occur if the state snapshot is malformed.
    """

    op_name: str
    owner: str
    state_id: str
    source_feeling_state_id: str
    memory_count: int
    candidate_count: int


class MemoryAffectReplayError(RuntimeError):
    """Hard-stop error raised when memory affect and replay owner invariants fail."""


def validate_prediction_mismatch_evidence(
    evidence: PredictionMismatchEvidence | None,
) -> PredictionMismatchEvidence | None:
    """Validate the optional mismatch evidence contract used by the replay owner."""

    if evidence is None:
        return None
    if not isinstance(evidence, PredictionMismatchEvidence):
        raise MemoryAffectReplayError(
            "Prediction mismatch evidence must use the explicit PredictionMismatchEvidence contract"
        )
    return evidence


@runtime_checkable
class RecalledMemoryProvider(Protocol):
    """Owner: memory affect and replay layer (R52).

    Purpose:
        The injected boundary behind which prior affect-memories are recalled for replay into the
        workspace. The `06` owner uses it to surface recalled memories as additional replay
        candidates alongside the current-tick formed memory, giving the `07` workspace a genuine
        multiplicity to arbitrate.

    Notes:
        Implementations return raw `RecalledMemoryFact`s only (no priority, no item/candidate
        construction); the `06` owner owns the replay-priority mapping and the re-forming. The
        `06` owner reaches durable storage and embeddings only through this protocol, so it
        imports neither the persistence nor the embedding owner. A cold store or no similar
        memory yields an empty tuple; an outright storage/embedding failure must propagate (no
        fabricated recall).
    """

    def recall(
        self,
        binding_context: MemoryBindingContext,
        feeling_state: InteroceptiveFeelingState,
    ) -> tuple[RecalledMemoryFact, ...]:
        """Owner: memory affect and replay layer.

        Purpose:
            Return bounded recalled prior-affect-memory facts relevant to the current context.

        Inputs:
            The current tick's `MemoryBindingContext` (the surfacing/query context) and the
            current `InteroceptiveFeelingState`.

        Returns:
            A bounded tuple of `RecalledMemoryFact` (possibly empty). Raw facts only.

        Raises:
            May propagate an outright storage/embedding failure as a hard stop; a cold store or
            absence of a similar memory must instead return an empty tuple.

        Notes:
            Must be bounded and deterministic for a fixed store state and query.
        """

        ...


@runtime_checkable
class MemoryAffectReplayAPI(Protocol):
    """Owner: memory affect and replay layer API.

    Purpose:
        Define the public owner-facing API from feeling state into affect-linked memory formation and replay publication.
    """

    def record_state(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None = None,
        mismatch_evidence: PredictionMismatchEvidence | None = None,
        outcome_class: str = "no_outcome",         # R100: 15 outcome taxonomy at write time
        tick_id: int | None = None,
    ) -> MemoryFormationState:
        """Owner: memory affect and replay layer.

        Purpose:
            Consume one feeling-state snapshot plus explicit optional evidence and return one memory-formation state snapshot.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`,
            an optional `outcome_class` (default "no_outcome"), and an optional runtime tick id.

        Returns:
            A `MemoryFormationState` owned by the memory affect and replay layer.

        Raises:
            MemoryAffectReplayError when required input or memory/replay invariants are violated.

        Notes:
            The returned state exposes candidate memory items only and does not claim conscious workspace promotion or identity writeback ownership.
            The `outcome_class` parameter carries the 15 outcome taxonomy at write time; it is used by the injected
            `MemoryLayerClassifier` (if present) to determine the initial layer assignment. When the classifier is
            absent, `outcome_class` is ignored and the legacy path runs byte-for-byte unchanged.
        """

        ...

    def build_record_op(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None = None,
        mismatch_evidence: PredictionMismatchEvidence | None = None,
    ) -> RecordMemoryOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the request op describing one affect-linked memory recording request.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, and optional `PredictionMismatchEvidence`.

        Returns:
            A `RecordMemoryOp` summarizing the request.

        Raises:
            MemoryAffectReplayError if the request cannot be represented safely.

        Notes:
            This op does not execute memory formation by itself.
        """

        ...

    def build_publish_replay_candidates_op(self, state: MemoryFormationState) -> PublishReplayCandidatesOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the publication op for replay candidates contained in one memory-formation state.

        Inputs:
            One `MemoryFormationState` produced by this owner.

        Returns:
            A `PublishReplayCandidatesOp` summarizing replay-candidate publication.

        Raises:
            MemoryAffectReplayError if the state is malformed.

        Notes:
            This op keeps candidate publication separate from workspace promotion ownership.
        """

        ...

    def build_publish_state_op(self, state: MemoryFormationState) -> PublishMemoryFormationStateOp:
        """Owner: memory affect and replay layer.

        Purpose:
            Build the publication op for one memory-formation state snapshot.

        Inputs:
            One `MemoryFormationState` produced by this owner.

        Returns:
            A `PublishMemoryFormationStateOp` summarizing owner-state publication.

        Raises:
            MemoryAffectReplayError if the state is malformed.

        Notes:
            This op is for orchestration visibility and diagnostics rather than transport execution.
        """

        ...