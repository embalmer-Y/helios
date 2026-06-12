"""Owner: memory affect and replay layer.

Owns:
- memory-record orchestration
- memory/replay collaborator invocation order
- record and publication op construction

Does not own:
- permanent replay strategy semantics
- conscious workspace promotion
- identity writeback
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.feeling import InteroceptiveFeelingState

from .contracts import (
    AffectTaggedMemoryItem,
    MemoryAffectReplayAPI,
    MemoryAffectReplayConfig,
    MemoryAffectReplayError,
    MemoryBindingContext,
    MemoryContentPacket,
    MemoryFamily,
    MemoryFormationState,
    MemoryReplayCandidate,
    PredictionMismatchEvidence,
    PublishMemoryFormationStateOp,
    PublishReplayCandidatesOp,
    RecalledMemoryFact,
    RecalledMemoryProvider,
    RecordMemoryOp,
    ReplayReason,
    validate_prediction_mismatch_evidence,
)


def _clamp_unit(value: float) -> float:
    """Owner: memory affect and replay layer. Clamp a value into [0.0, 1.0], rounded for determinism."""

    return round(min(1.0, max(0.0, value)), 4)


def _validate_feeling_state(state: InteroceptiveFeelingState) -> None:
    if not state.state_id:
        raise MemoryAffectReplayError("InteroceptiveFeelingState must declare a non-empty state_id")
    if not state.source_neuromodulator_state_id:
        raise MemoryAffectReplayError(
            "InteroceptiveFeelingState must declare a non-empty source_neuromodulator_state_id"
        )


def _validate_memory_items(
    memory_items: tuple[AffectTaggedMemoryItem, ...],
    feeling_state: InteroceptiveFeelingState,
    binding_context: MemoryBindingContext | None,
) -> None:
    expected_binding_context_id = binding_context.context_id if binding_context is not None else None
    for item in memory_items:
        if item.source_feeling_state_id != feeling_state.state_id:
            raise MemoryAffectReplayError(
                "Memory items must preserve the source feeling state provenance used for formation"
            )
        if item.binding_context_id != expected_binding_context_id:
            raise MemoryAffectReplayError(
                "Memory items must preserve the binding_context_id of the explicit binding context"
            )


def _validate_replay_candidates(
    replay_candidates: tuple[MemoryReplayCandidate, ...],
    memory_items: tuple[AffectTaggedMemoryItem, ...],
    feeling_state: InteroceptiveFeelingState,
) -> None:
    published_memory_ids = {item.memory_id for item in memory_items}
    for candidate in replay_candidates:
        if candidate.memory_id not in published_memory_ids:
            raise MemoryAffectReplayError(
                "Replay candidates must reference memory items published in the same owner state"
            )
        if candidate.source_feeling_state_id != feeling_state.state_id:
            raise MemoryAffectReplayError(
                "Replay candidates must preserve the source feeling state provenance used for formation"
            )


@runtime_checkable
class MemoryFormationPath(Protocol):
    """Owner: memory affect and replay layer.

    Purpose:
        Produce the next affect-tagged memory items from validated upstream feeling state and explicit binding inputs.
    """

    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        """Owner: memory affect and replay layer.

        Purpose:
            Produce one immutable tuple of affect-tagged memory items.

        Inputs:
            One validated `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`, one owner config, and an optional tick id.

        Returns:
            A tuple of `AffectTaggedMemoryItem` values.

        Raises:
            MemoryAffectReplayError if required memory-formation capability is unavailable or unsafe.

        Notes:
            This interface is injected into the owner skeleton so unresolved write semantics are not guessed here.
        """


@runtime_checkable
class ReplayCandidateSelector(Protocol):
    """Owner: memory affect and replay layer.

    Purpose:
        Select replay candidates and bounded continuous priority hints without hardcoding replay thresholds into the owner skeleton.
    """

    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        """Owner: memory affect and replay layer.

        Purpose:
            Produce replay candidates from owner-produced memory items.

        Inputs:
            One tuple of `AffectTaggedMemoryItem`, one validated `InteroceptiveFeelingState`, optional `PredictionMismatchEvidence`, and one owner config.

        Returns:
            A tuple of `MemoryReplayCandidate` values.

        Raises:
            MemoryAffectReplayError if required replay-selection capability is unavailable or unsafe.

        Notes:
            This interface keeps unresolved replay-trigger scoring semantics out of the public owner skeleton.
        """


@dataclass
class MemoryAffectReplayEngine(MemoryAffectReplayAPI):
    """Owner: memory affect and replay layer.

    Purpose:
        Execute affect-linked memory formation and replay-candidate publication using injected collaborators.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: MemoryAffectReplayConfig
    formation_path: MemoryFormationPath
    replay_selector: ReplayCandidateSelector
    recalled_memory_provider: RecalledMemoryProvider | None = None
    # First-version recalled-replay priority weights (R52), under the owner config's declared
    # `replay_priority_policy` learned-parameter category (P5-learnable later). The replayed
    # priority is a bounded convex blend of recall relevance and recalled affect intensity.
    recalled_relevance_weight: float = 0.6
    recalled_affect_weight: float = 0.4
    recalled_arousal_weight: float = 0.5
    recalled_tension_weight: float = 0.3
    recalled_pain_weight: float = 0.2

    def record_state(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None = None,
        mismatch_evidence: PredictionMismatchEvidence | None = None,
        tick_id: int | None = None,
    ) -> MemoryFormationState:
        """Owner: memory affect and replay layer.

        Purpose:
            Consume one feeling-state snapshot and return one owner state containing memory items and replay candidates.

        Inputs:
            One `InteroceptiveFeelingState`, optional `MemoryBindingContext`, optional `PredictionMismatchEvidence`, and an optional runtime tick id.

        Returns:
            A `MemoryFormationState` containing owner-produced memory items and replay candidates.

        Raises:
            MemoryAffectReplayError when input invariants or collaborator outputs are invalid.

        Notes:
            Remaining unresolved retrieval, workspace-promotion, and identity-writeback semantics stay outside this owner skeleton.
        """

        _validate_feeling_state(feeling_state)
        validate_prediction_mismatch_evidence(mismatch_evidence)
        memory_items = self.formation_path.form_memory_items(
            feeling_state,
            binding_context,
            mismatch_evidence,
            self.config,
            tick_id,
        )
        _validate_memory_items(tuple(memory_items), feeling_state, binding_context)
        replay_candidates = self.replay_selector.select_candidates(
            memory_items,
            feeling_state,
            mismatch_evidence,
            self.config,
        )
        _validate_replay_candidates(tuple(replay_candidates), tuple(memory_items), feeling_state)
        # R52: surface recalled prior affect-memories as additional, non-forced replay candidates
        # so the `07` workspace has a genuine multiplicity to arbitrate. This is strictly additive:
        # the current-tick formed memory and its salience-gated candidate above are unchanged.
        memory_items, replay_candidates = self._surface_recalled_memories(
            tuple(memory_items),
            tuple(replay_candidates),
            feeling_state,
            binding_context,
        )
        return MemoryFormationState(
            state_id=f"memory-formation-state:{feeling_state.state_id}:{tick_id if tick_id is not None else 'na'}",
            source_feeling_state_id=feeling_state.state_id,
            memory_items=tuple(memory_items),
            replay_candidates=tuple(replay_candidates),
            tick_id=tick_id,
        )

    def _surface_recalled_memories(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        replay_candidates: tuple[MemoryReplayCandidate, ...],
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
    ) -> tuple[tuple[AffectTaggedMemoryItem, ...], tuple[MemoryReplayCandidate, ...]]:
        """Owner: memory affect and replay layer (R52).

        Re-form recalled prior affect-memories into additive, non-forced replay candidates.

        Returns the combined (current + recalled) memory items and replay candidates. When there
        is no provider or no binding context, or the provider returns nothing, returns the inputs
        unchanged (byte-for-byte the pre-R52 single-candidate state). A recalled fact whose
        `memory_id` collides with an already-present item is skipped (the current-tick memory is
        never shadowed). The combined set still satisfies every existing owner invariant: each
        recalled item carries the current binding-context id and feeling-state id, and each
        recalled candidate references a published recalled item.
        """

        if self.recalled_memory_provider is None or binding_context is None:
            return memory_items, replay_candidates
        recalled_facts = self.recalled_memory_provider.recall(binding_context, feeling_state)
        if not recalled_facts:
            return memory_items, replay_candidates
        taken_memory_ids = {item.memory_id for item in memory_items}
        extra_items: list[AffectTaggedMemoryItem] = []
        extra_candidates: list[MemoryReplayCandidate] = []
        for fact in recalled_facts:
            if fact.memory_id in taken_memory_ids:
                continue
            taken_memory_ids.add(fact.memory_id)
            extra_items.append(
                AffectTaggedMemoryItem(
                    memory_id=fact.memory_id,
                    family=fact.family,
                    source_feeling_state_id=feeling_state.state_id,
                    affect_tag=fact.affect,
                    content=MemoryContentPacket(
                        content_kind="recalled_affect_memory",
                        summary_ref=fact.summary,
                        context_ref=None,
                        salient_tokens=(),
                    ),
                    binding_context_id=binding_context.context_id,
                    tick_id=feeling_state.tick_id,
                )
            )
            extra_candidates.append(
                MemoryReplayCandidate(
                    candidate_id=f"recalled-candidate:runtime:{feeling_state.tick_id}:{fact.memory_id}",
                    memory_id=fact.memory_id,
                    family=fact.family,
                    source_feeling_state_id=feeling_state.state_id,
                    replay_reasons=self._recalled_reasons(fact),
                    forced_consolidation=False,
                    priority_hint=self._recalled_priority(fact),
                )
            )
        if not extra_items:
            return memory_items, replay_candidates
        return memory_items + tuple(extra_items), replay_candidates + tuple(extra_candidates)

    def _recalled_priority(self, fact: RecalledMemoryFact) -> float:
        """Owner: memory affect and replay layer (R52). Map a recalled fact to a bounded priority.

        A bounded convex blend of recall relevance and recalled affect intensity, so a recalled
        memory that is both relevant to the current context and emotionally charged competes
        strongly for the workspace. Deterministic and clamped to `[0, 1]`.
        """

        affect = fact.affect
        affect_intensity = _clamp_unit(
            self.recalled_arousal_weight * affect.arousal
            + self.recalled_tension_weight * affect.tension
            + self.recalled_pain_weight * affect.pain_like
        )
        return _clamp_unit(
            self.recalled_relevance_weight * fact.recall_similarity
            + self.recalled_affect_weight * affect_intensity
        )

    def _recalled_reasons(self, fact: RecalledMemoryFact) -> tuple[ReplayReason, ...]:
        """Owner: memory affect and replay layer (R52). Derive replay reasons for a recalled memory.

        Always reports at least one reason (the contract requires it): high affect intensity.
        Adds unresolved tension/discomfort when the recalled affect's tension or pain dominates.
        Reasons stay within the fixed `ReplayReason` taxonomy.
        """

        affect = fact.affect
        reasons: list[ReplayReason] = ["high_affect_intensity"]
        if affect.tension >= affect.arousal or affect.pain_like > 0.0:
            reasons.append("unresolved_tension_or_discomfort")
        return tuple(reasons)

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
            A `RecordMemoryOp` summarizing request identity and explicit optional evidence.

        Raises:
            MemoryAffectReplayError if the request is malformed.

        Notes:
            This method validates upstream provenance and optional mismatch-evidence eligibility before creating the request op.
        """

        _validate_feeling_state(feeling_state)
        mismatch_evidence = validate_prediction_mismatch_evidence(mismatch_evidence)
        return RecordMemoryOp(
            op_name="record_memory_affect_state",
            owner="memory_affect_and_replay",
            feeling_state_id=feeling_state.state_id,
            binding_context_id=binding_context.context_id if binding_context is not None else None,
            mismatch_evidence_id=mismatch_evidence.evidence_id if mismatch_evidence is not None else None,
        )

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
            Candidate publication remains separate from later workspace promotion and competition ownership.
        """

        if not state.state_id or not state.source_feeling_state_id:
            raise MemoryAffectReplayError("MemoryFormationState contains incomplete provenance")
        families = tuple(sorted({candidate.family for candidate in state.replay_candidates}))
        return PublishReplayCandidatesOp(
            op_name="publish_memory_replay_candidates",
            owner="memory_affect_and_replay",
            state_id=state.state_id,
            candidate_count=len(state.replay_candidates),
            families=families,
        )

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

        if not state.state_id or not state.source_feeling_state_id:
            raise MemoryAffectReplayError("MemoryFormationState contains incomplete provenance")
        return PublishMemoryFormationStateOp(
            op_name="publish_memory_formation_state",
            owner="memory_affect_and_replay",
            state_id=state.state_id,
            source_feeling_state_id=state.source_feeling_state_id,
            memory_count=len(state.memory_items),
            candidate_count=len(state.replay_candidates),
        )


@dataclass
class AffectGroundedMemoryFormationPath(MemoryFormationPath):
    """Owner: memory affect and replay layer.

    Purpose:
        Form one affect-tagged memory item from the real `05` interoceptive feeling state and
        the explicit binding context, replacing the constant first-version shim so the formed
        memory's affect tag is the genuine felt body-state of the tick, not a fixed vector.

    Failure semantics:
        Returns no item when there is no binding context (a defined outcome, nothing to bind a
        memory to). Otherwise the engine validates the produced item's provenance.

    Notes:
        Owned by `06`. It reads only the feeling state, binding context, and optional mismatch
        evidence; it imports neither the persistence nor the embedding owner and performs no
        durability. The episodic-vs-autobiographical family is an owner-owned first-version
        mapping: a tick carrying explicit prediction-mismatch evidence (genuine surprise) forms
        an autobiographical memory; every other tick forms an episodic memory. Richer
        feeling-driven family/content shaping is deferred (a later slice), so this mapping is
        deliberately minimal and not over-claimed.
    """

    def form_memory_items(
        self,
        feeling_state: InteroceptiveFeelingState,
        binding_context: MemoryBindingContext | None,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
        tick_id: int | None,
    ) -> tuple[AffectTaggedMemoryItem, ...]:
        del config
        if binding_context is None:
            return ()
        family: MemoryFamily = "autobiographical" if mismatch_evidence is not None else "episodic"
        return (
            AffectTaggedMemoryItem(
                memory_id=f"memory:runtime:{tick_id}",
                family=family,
                source_feeling_state_id=feeling_state.state_id,
                # The affect tag is the REAL 05 feeling vector for this tick, not a constant.
                affect_tag=feeling_state.feeling,
                content=binding_context.content,
                binding_context_id=binding_context.context_id,
                tick_id=tick_id,
            ),
        )


@dataclass
class SalienceGatedReplayCandidateSelector(ReplayCandidateSelector):
    """Owner: memory affect and replay layer.

    Purpose:
        Decide which formed memory items are consolidation-worthy through an owner-owned
        salience gate computed from the real feeling signal and optional prediction-mismatch
        evidence, replacing the constant first-version selector that marked every item
        forced-consolidation with a fixed priority. The gate sets each candidate's
        `forced_consolidation` flag and bounded `priority_hint` from that real salience, so a
        flat low-affect tick with no mismatch consolidates nothing and is not durably stored.

    Failure semantics:
        Pure deterministic function of its inputs. Output `priority_hint` is clamped to the
        `MemoryReplayCandidate` `[0, 1]` contract and `replay_reasons` stays within the fixed
        `ReplayReason` taxonomy.

    Notes:
        Owned by `06`. The salience is `max(affect_intensity, mismatch_weight * mismatch_score)`
        where `affect_intensity` is a bounded weighted sum of the felt arousal/tension/pain. The
        threshold and weights are explicit bounded first-version constants organized under the
        owner config's declared learned-parameter categories (`consolidation_policy` for the
        threshold, `replay_priority_policy` for the weights); a later `P5` slice learns them
        without changing the gate shape. Deterministic, bounded, stateless.
    """

    consolidation_threshold: float = 0.5
    arousal_weight: float = 0.5
    tension_weight: float = 0.3
    pain_weight: float = 0.2
    mismatch_weight: float = 0.6

    def select_candidates(
        self,
        memory_items: tuple[AffectTaggedMemoryItem, ...],
        feeling_state: InteroceptiveFeelingState,
        mismatch_evidence: PredictionMismatchEvidence | None,
        config: MemoryAffectReplayConfig,
    ) -> tuple[MemoryReplayCandidate, ...]:
        del config
        feeling = feeling_state.feeling
        affect_intensity = _clamp_unit(
            self.arousal_weight * feeling.arousal
            + self.tension_weight * feeling.tension
            + self.pain_weight * feeling.pain_like
        )
        mismatch_score = mismatch_evidence.mismatch_score if mismatch_evidence is not None else 0.0
        mismatch_term = _clamp_unit(self.mismatch_weight * mismatch_score)
        salience = max(affect_intensity, mismatch_term)
        forced = salience >= self.consolidation_threshold
        reasons = self._derive_reasons(affect_intensity, mismatch_term, feeling)
        candidates: list[MemoryReplayCandidate] = []
        for index, item in enumerate(memory_items):
            candidates.append(
                MemoryReplayCandidate(
                    candidate_id=f"candidate:runtime:{feeling_state.tick_id}:{index}",
                    memory_id=item.memory_id,
                    family=item.family,
                    source_feeling_state_id=feeling_state.state_id,
                    replay_reasons=reasons,
                    forced_consolidation=forced,
                    priority_hint=salience,
                )
            )
        return tuple(candidates)

    def _derive_reasons(
        self,
        affect_intensity: float,
        mismatch_term: float,
        feeling,
    ) -> tuple[ReplayReason, ...]:
        """Owner: memory affect and replay layer. Derive replay reasons from the gate signal.

        Always reports at least one reason (the `MemoryReplayCandidate` contract requires it):
        the dominant salience contributor. Tension/discomfort is reported in addition when the
        felt tension or pain is the affect driver, and mismatch is reported when surprise drove
        the gate. Reasons stay within the fixed `ReplayReason` taxonomy.
        """

        reasons: list[ReplayReason] = []
        if mismatch_term >= affect_intensity and mismatch_term > 0.0:
            reasons.append("prediction_mismatch_or_surprise")
        if feeling.tension >= feeling.arousal or feeling.pain_like > 0.0:
            reasons.append("unresolved_tension_or_discomfort")
        if not reasons or affect_intensity >= mismatch_term:
            if "high_affect_intensity" not in reasons:
                reasons.insert(0, "high_affect_intensity")
        return tuple(reasons)
# =============================================================================
# R85: objective_importance + promote_layer implementations
# =============================================================================
# Owner: 06 memory

from helios_v2.memory.contracts import (
    MemoryRecord,
    OUTCOME_CLASS_WEIGHTS,
    DoubleConfirmationClass,
)


def _safe_get(mapping: Mapping[str, float], key: str, default: float = 0.5) -> float:
    """Read a float from a mapping with bounds checking; default to 0.5 (mid)."""
    val = mapping.get(key, default)
    if not isinstance(val, (int, float)):
        return default
    return min(1.0, max(0.0, float(val)))


def _novelty_cosine(
    stimulus_text: str,
    recent_summaries: Sequence[str],
    embed_callable: Callable[[str], Sequence[float]] | None = None,
) -> float:
    """Compute novelty as 1 - cosine similarity to recent records.

    If `embed_callable` is None, falls back to length-based proxy.
    """
    if not recent_summaries:
        return 0.5  # neutral novelty for empty history
    if embed_callable is None:
        # Recency proxy: longer stimulus = more novel
        return min(1.0, len(stimulus_text) / 200.0)
    try:
        v = embed_callable(stimulus_text)
        if not v:
            return 0.5
        sims = []
        for r in recent_summaries[-20:]:
            rv = embed_callable(r)
            if not rv:
                continue
            dot = sum(a * b for a, b in zip(v, rv))
            norm_v = sum(a * a for a in v) ** 0.5
            norm_rv = sum(a * a for a in rv) ** 0.5
            if norm_v == 0 or norm_rv == 0:
                continue
            sims.append(dot / (norm_v * norm_rv))
        if not sims:
            return 0.5
        max_sim = max(sims)
        return min(1.0, max(0.0, 1.0 - max_sim))
    except Exception:
        return 0.5


def objective_importance(
    stimulus_text: str,
    hormone_snapshot: Mapping[str, float],
    feeling_snapshot: Mapping[str, float],
    outcome_class: str,
    recent_summaries: Sequence[str] = (),
    embed_callable: Callable[[str], Sequence[float]] | None = None,
) -> float:
    """Owner: 06 memory (R85 Track A).

    Compute objective importance of a stimulus independently of LLM judgment.

    Formula (6 dimensions, weights sum to 1.0):
        0.25 * stimulus_intensity       (length proxy, 0..1)
      + 0.20 * cortisol                  (stress response, [0,1])
      + 0.15 * arousal                   (feeling, [0,1])
      + 0.15 * outcome_class_weight      ([0.20..0.95])
      + 0.15 * novelty                   (1 - max cosine, [0,1])
      + 0.10 * (1 - social_safety)       (relationship risk, [0,1])

    Returns a value in [0.0, 1.0].
    """
    if not stimulus_text:
        return 0.0
    # 1. stimulus_intensity (length proxy: 0 chars -> 0, 200+ chars -> 1.0)
    intensity = min(1.0, len(stimulus_text) / 200.0)
    # 2. cortisol (stress)
    cortisol = _safe_get(hormone_snapshot, "cortisol", 0.5)
    # 3. arousal
    arousal = _safe_get(feeling_snapshot, "arousal", 0.5)
    # 4. outcome_class_weight
    oc_weight = OUTCOME_CLASS_WEIGHTS.get(outcome_class, 0.5)
    # 5. novelty
    novelty = _novelty_cosine(stimulus_text, recent_summaries, embed_callable)
    # 6. (1 - social_safety)
    social_safety = _safe_get(feeling_snapshot, "social_safety", 0.5)
    relationship_risk = 1.0 - social_safety

    score = (
        0.25 * intensity
        + 0.20 * cortisol
        + 0.15 * arousal
        + 0.15 * oc_weight
        + 0.15 * novelty
        + 0.10 * relationship_risk
    )
    return min(1.0, max(0.0, score))


def promote_layer(record: MemoryRecord) -> MemoryRecord:
    """Owner: 06 memory (R85 Track A).

    Apply layer promotion rules per R85 design:
        L3_short -> L4_long when recall_count >= 2 (synaptic tagging)
        L4_long -> L5_autobiographical when recall_count >= 5 AND objective_importance >= 0.7
        (Other transitions are no-ops.)

    Returns a new MemoryRecord with the promoted layer and (for L5) `is_consolidated=True`.
    """
    new_layer = record.layer
    new_consolidated = record.is_consolidated
    if record.layer == "L3_short" and record.recall_count >= 2:
        new_layer = "L4_long"
        new_consolidated = True
    elif (
        record.layer == "L4_long"
        and record.recall_count >= 5
        and record.objective_importance >= 0.7
    ):
        new_layer = "L5_autobiographical"
        new_consolidated = True
    if new_layer == record.layer and new_consolidated == record.is_consolidated:
        return record  # no-op
    return MemoryRecord(
        record_id=record.record_id,
        tick_id=record.tick_id,
        continuity_kind=record.continuity_kind,
        outcome_class=record.outcome_class,
        summary=record.summary,
        layer=new_layer,
        objective_importance=record.objective_importance,
        llm_remember_decision=record.llm_remember_decision,
        double_confirmation_class=record.double_confirmation_class,
        hormone_snapshot=record.hormone_snapshot,
        feeling_snapshot=record.feeling_snapshot,
        created_at_tick=record.created_at_tick,
        created_at_wall=record.created_at_wall,
        last_recall_at_wall=record.last_recall_at_wall,
        recall_count=record.recall_count,
        is_consolidated=new_consolidated,
        soft_deleted_at=record.soft_deleted_at,
        memory_gc_after=record.memory_gc_after,
        audit_trail=record.audit_trail,
        tags=record.tags,
        context_keywords=record.context_keywords,
        cross_links=record.cross_links,
    )
