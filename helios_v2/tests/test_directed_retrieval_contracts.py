from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.directed_retrieval import (
    DirectedRetrievalConfig,
    DirectedRetrievalError,
    MemoryRetrievalCandidate,
    RetrievalRequest,
    RetrievalSelectionTrace,
    ThoughtWindowBundle,
    ThoughtWindowHit,
)
from helios_v2.thought_gating import SelectedStimulusSummary


def _stimulus_summary() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.7,
    )


def _hit(memory_id: str) -> ThoughtWindowHit:
    return ThoughtWindowHit(
        memory_id=memory_id,
        memory_type="episodic",
        summary="bounded selected memory",
        score=0.8,
        source="memory_affect_and_replay",
        tags=("salient",),
    )


def _selection_trace() -> tuple[RetrievalSelectionTrace, ...]:
    return (
        RetrievalSelectionTrace("short_term", 1, 1, "compact_stimuli"),
        RetrievalSelectionTrace("mid_term", 0, 0, "compact_stimuli"),
        RetrievalSelectionTrace("long_term", 0, 0, "compact_stimuli"),
        RetrievalSelectionTrace("autobiographical", 0, 0, "compact_stimuli"),
    )


def test_retrieval_request_is_immutable_and_requires_explicit_demand() -> None:
    request = RetrievalRequest(
        request_id="retrieval-request:001",
        source_gate_result_id="gate-result:001",
        source_continuation_active=False,
        compact_stimuli=(_stimulus_summary(),),
        recall_intent=None,
        selected_memory_refs=(),
        target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
        limit=2,
        tick_id=1,
    )

    with pytest.raises(FrozenInstanceError):
        request.limit = 3

    with pytest.raises(DirectedRetrievalError, match="compact stimuli"):
        RetrievalRequest(
            request_id="retrieval-request:empty",
            source_gate_result_id="gate-result:001",
            source_continuation_active=False,
            compact_stimuli=(),
            recall_intent=None,
            selected_memory_refs=(),
            target_tiers=("short_term",),
            limit=1,
            tick_id=1,
        )


def test_directed_retrieval_config_requires_fixed_learned_policy_surface() -> None:
    config = DirectedRetrievalConfig(
        max_hits_per_tier=2,
        max_short_term_context=1,
        retrieval_bootstrap_id="directed-retrieval-bootstrap:v1",
        mandatory_learned_parameters=(
            "retrieval_planning_policy",
            "tier_selection_policy",
            "thought_window_shaping_policy",
        ),
    )

    assert config.max_hits_per_tier == 2

    with pytest.raises(DirectedRetrievalError, match="mandatory learned-parameter categories"):
        DirectedRetrievalConfig(
            max_hits_per_tier=2,
            max_short_term_context=1,
            retrieval_bootstrap_id="directed-retrieval-bootstrap:v1",
            mandatory_learned_parameters=("retrieval_planning_policy",),
        )


def test_memory_candidate_and_hit_are_bounded_public_projections() -> None:
    candidate = MemoryRetrievalCandidate(
        candidate_id="candidate:001",
        tier="mid_term",
        memory_id="memory:001",
        memory_type="episodic",
        summary="bounded candidate summary",
        score=0.8,
        source="memory_affect_and_replay",
        tags=("affective",),
    )

    assert candidate.summary == "bounded candidate summary"

    with pytest.raises(DirectedRetrievalError, match="score"):
        ThoughtWindowHit(
            memory_id="memory:bad",
            memory_type="episodic",
            summary="bad score",
            score=1.2,
            source="memory_affect_and_replay",
            tags=(),
        )


def test_thought_window_bundle_requires_all_tier_traces_and_tiny_short_term_context() -> None:
    bundle = ThoughtWindowBundle(
        bundle_id="thought-window-bundle:001",
        source_plan_id="retrieval-plan:001",
        short_term_context=(_hit("memory:short:001"),),
        mid_term_hits=(),
        long_term_hits=(),
        autobiographical_hits=(),
        selection_trace=_selection_trace(),
        retrieval_sec_trace=(),
        tick_id=1,
    )

    assert len(bundle.selection_trace) == 4

    with pytest.raises(DirectedRetrievalError, match="selection_trace"):
        ThoughtWindowBundle(
            bundle_id="thought-window-bundle:bad",
            source_plan_id="retrieval-plan:001",
            short_term_context=(_hit("memory:short:001"),),
            mid_term_hits=(),
            long_term_hits=(),
            autobiographical_hits=(),
            selection_trace=_selection_trace()[:3],
            retrieval_sec_trace=(),
            tick_id=1,
        )
