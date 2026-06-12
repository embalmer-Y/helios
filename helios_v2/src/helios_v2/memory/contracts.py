"""Owner: memory affect and replay layer.

Owns:
- affect-linked memory contracts
- replay-candidate contracts
- memory record and publication ops contracts

Does not own:
- feeling construction
- conscious workspace promotion
- identity writeback
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState, InteroceptiveFeelingVector


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(mapping))


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
]


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
        expected = {
            "memory_family_write_policy",
            "replay_priority_policy",
            "consolidation_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
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
        Represent one immutable memory-owner snapshot containing memory items and replay candidates.

    Failure semantics:
        Missing provenance or malformed state identity raise `MemoryAffectReplayError`.
    """

    state_id: str
    source_feeling_state_id: str
    memory_items: tuple[AffectTaggedMemoryItem, ...]
    replay_candidates: tuple[MemoryReplayCandidate, ...]
    tick_id: int | None

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
        tick_id: int | None = None,
    ) -> MemoryFormationState:
        """Owner: memory affect and replay layer.

        Purpose:
            Consume one feeling-state snapshot plus explicit optional evidence and return one memory-formation state snapshot.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`, and an optional runtime tick id.

        Returns:
            A `MemoryFormationState` owned by the memory affect and replay layer.

        Raises:
            MemoryAffectReplayError when required input or memory/replay invariants are violated.

        Notes:
            The returned state exposes candidate memory items only and does not claim conscious workspace promotion or identity writeback ownership.
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
# =============================================================================
# R85: Dual-Track Memory Architecture — Track A additions
# =============================================================================
# Owner: 06 memory (MemoryRecord + objective_importance)
# Reference: docs/requirements/85-r85-dual-track-memory-architecture/

import time as _time
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from helios_v2.persistence import PersistedExperienceRecord


MemoryLayer = Literal["L2_working", "L3_short", "L4_long", "L5_autobiographical"]
DoubleConfirmationClass = Literal["persist_full", "persist_low_priority", "skip"]
OutcomeClassWeight = Literal[
    "self_changed",
    "world_blocked",
    "world_changed",
    "world_failed",
    "self_blocked",
    "internal_only",
]

OUTCOME_CLASS_WEIGHTS: Mapping[str, float] = MappingProxyType({
    "self_changed": 0.95,
    "world_blocked": 0.80,
    "world_changed": 0.60,
    "world_failed": 0.50,
    "self_blocked": 0.40,
    "internal_only": 0.20,
})


@dataclass(frozen=True)
class MemoryRecord:
    """Owner: 06 memory (R85 Track A).

    Time-stratified memory record. Supersedes `PersistedExperienceRecord`
    for new writes; legacy records are auto-migrated on first read.

    Layer semantics:
        L2_working = current tick context (LLM context, ~30s TTL)
        L3_short = minutes to hours (default layer for new writes)
        L4_long = persistent, requires double-confirmation
        L5_autobiographical = recall_count >= 5 AND objective_importance >= 0.7

    Failure semantics:
        Construction raises MemoryAffectReplayError on out-of-range scores,
        missing required audit fields, or invalid layer name.
    """

    # Legacy fields (preserved)
    record_id: str
    tick_id: int
    continuity_kind: str
    outcome_class: str
    summary: str

    # Track A new
    layer: MemoryLayer
    objective_importance: float
    llm_remember_decision: bool
    double_confirmation_class: DoubleConfirmationClass
    hormone_snapshot: Mapping[str, float]
    feeling_snapshot: Mapping[str, float]

    # Time dimension
    created_at_tick: int
    created_at_wall: float
    last_recall_at_wall: float | None
    recall_count: int
    is_consolidated: bool
    soft_deleted_at: float | None
    memory_gc_after: float | None
    audit_trail: tuple[Mapping[str, str], ...]

    # Self-description (A-MEM style)
    tags: tuple[str, ...]
    context_keywords: tuple[str, ...]
    cross_links: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_unit_interval("objective_importance", self.objective_importance)
        if self.layer not in ("L2_working", "L3_short", "L4_long", "L5_autobiographical"):
            raise MemoryAffectReplayError(
                f"MemoryRecord.layer must be one of L2_working/L3_short/L4_long/L5_autobiographical, got {self.layer!r}"
            )
        if self.double_confirmation_class not in ("persist_full", "persist_low_priority", "skip"):
            raise MemoryAffectReplayError(
                f"MemoryRecord.double_confirmation_class must be persist_full/persist_low_priority/skip, got {self.double_confirmation_class!r}"
            )
        if self.recall_count < 0:
            raise MemoryAffectReplayError("recall_count must be >= 0")
        if self.soft_deleted_at is not None and self.memory_gc_after is None:
            raise MemoryAffectReplayError("soft_deleted_at is set but memory_gc_after is None")
        object.__setattr__(self, "hormone_snapshot", _freeze_mapping(self.hormone_snapshot))
        object.__setattr__(self, "feeling_snapshot", _freeze_mapping(self.feeling_snapshot))


def should_persist(llm_remember: bool, objective_score: float) -> DoubleConfirmationClass:
    """Owner: 06 memory (R85 Track A).

    Double-confirmation write rule (3-class):
        - llm_remember=True OR objective_score >= 0.5  -> "persist_full" (L4)
        - llm_remember=True AND 0.2 <= objective_score < 0.5
            -> "persist_low_priority" (L3) (LLM wants to keep, objective is lukewarm)
        - llm_remember=True AND objective_score < 0.2
            -> "persist_low_priority" (L3) (LLM wants to keep, but objective strongly disagrees)
        - llm_remember=False AND objective_score < 0.5  -> "skip"

    Note: when LLM=True and score is in [0.2, 0.5) OR (< 0.2), we degrade to
    `persist_low_priority` rather than full. This is the AND-fallback from
    the R85 design proposal: LLM subjective judgement is allowed, but objective
    importance modulates the persistence layer (L3 vs L4).

    Pure function. No side effects. Used by FirstVersionExperienceWritebackPath.
    """
    if not (0.0 <= objective_score <= 1.0):
        raise MemoryAffectReplayError(
            f"objective_score must be in [0.0, 1.0], got {objective_score!r}"
        )
    # Objective override: LLM False + score >= 0.5 -> persist_full
    if not llm_remember and objective_score >= 0.5:
        return "persist_full"
    # LLM True: degrade based on score
    if llm_remember and objective_score >= 0.5:
        return "persist_full"
    if llm_remember and 0.2 <= objective_score < 0.5:
        return "persist_low_priority"
    # AND-fallback: LLM True + score < 0.2 -> persist_low_priority (don't drop user's intent)
    if llm_remember and objective_score < 0.2:
        return "persist_low_priority"
    return "skip"


def effective_priority(record: MemoryRecord, current_wall: float) -> float:
    """Owner: 06 memory (R85 Track A).

    Ebbinghaus-style decay: 5% per day since creation, with recall rebound.

    - If `is_consolidated`, return `objective_importance` (no decay).
    - Otherwise: `objective_importance * 0.95**days_since_creation * (1.0 + 0.1/max(days_since_recall, 1))`
    - Clamp to [0.0, 1.0].
    """
    if record.is_consolidated:
        return record.objective_importance
    days_since_creation = max(0.0, (current_wall - record.created_at_wall) / 86400.0)
    if record.last_recall_at_wall is None:
        # No recall yet: use creation time, but guard against zero
        days_since_recall = max(1.0, days_since_creation)
    else:
        days_since_recall = max(1.0, (current_wall - record.last_recall_at_wall) / 86400.0)
    decay = 0.95 ** days_since_creation
    rebound = 1.0 + 0.1 / days_since_recall
    return min(1.0, max(0.0, record.objective_importance * decay * rebound))


def soft_delete_memory_record(
    record: MemoryRecord,
    reason: str,
    justification: str,
    audit_extra: Mapping[str, str] | None = None,
    current_wall: float | None = None,
) -> MemoryRecord:
    """Owner: 06 memory (R85 Track A).

    Return a new `MemoryRecord` with `soft_deleted_at` set, `memory_gc_after = now + 7 days`,
    and the audit entry appended to `audit_trail`.

    Pure function: never mutates `record`. Returns a new instance.
    """
    if not reason:
        raise MemoryAffectReplayError("soft_delete reason must be non-empty")
    if not justification:
        raise MemoryAffectReplayError("soft_delete justification must be non-empty")
    if current_wall is None:
        current_wall = _time.time()
    audit_entry: dict[str, str] = {
        "at": str(current_wall),
        "kind": "soft_delete",
        "reason": reason,
        "justification": justification,
    }
    if audit_extra:
        for k, v in audit_extra.items():
            audit_entry[k] = v
    new_audit_trail = record.audit_trail + (MappingProxyType(audit_entry),)
    return MemoryRecord(
        record_id=record.record_id,
        tick_id=record.tick_id,
        continuity_kind=record.continuity_kind,
        outcome_class=record.outcome_class,
        summary=record.summary,
        layer=record.layer,
        objective_importance=record.objective_importance,
        llm_remember_decision=record.llm_remember_decision,
        double_confirmation_class=record.double_confirmation_class,
        hormone_snapshot=record.hormone_snapshot,
        feeling_snapshot=record.feeling_snapshot,
        created_at_tick=record.created_at_tick,
        created_at_wall=record.created_at_wall,
        last_recall_at_wall=record.last_recall_at_wall,
        recall_count=record.recall_count,
        is_consolidated=record.is_consolidated,
        soft_deleted_at=current_wall,
        memory_gc_after=current_wall + 7 * 86400.0,
        audit_trail=new_audit_trail,
        tags=record.tags,
        context_keywords=record.context_keywords,
        cross_links=record.cross_links,
    )


def migrate_persisted_to_memory_v2(
    legacy: PersistedExperienceRecord,
    created_at_wall: float | None = None,
) -> MemoryRecord:
    """Owner: 06 memory (R85 Track A).

    One-shot migration from legacy `PersistedExperienceRecord` to new `MemoryRecord`.
    - Default layer = L4_long
    - Default objective_importance = 0.5
    - Default is_consolidated = False
    - audit_trail = ()
    - All other legacy fields preserved.
    """
    if created_at_wall is None:
        created_at_wall = _time.time()
    empty_hormone: dict[str, float] = {}
    empty_feeling: dict[str, float] = {}
    return MemoryRecord(
        record_id=legacy.record_id,
        tick_id=legacy.tick_id,
        continuity_kind=legacy.continuity_kind,
        outcome_class=legacy.outcome_class,
        summary=legacy.summary,
        layer="L4_long",
        objective_importance=0.5,
        llm_remember_decision=True,
        double_confirmation_class="persist_full",
        hormone_snapshot=empty_hormone,
        feeling_snapshot=empty_feeling,
        created_at_tick=legacy.tick_id,
        created_at_wall=created_at_wall,
        last_recall_at_wall=None,
        recall_count=0,
        is_consolidated=False,
        soft_deleted_at=None,
        memory_gc_after=None,
        audit_trail=(),
        tags=(),
        context_keywords=(),
        cross_links=(),
    )
