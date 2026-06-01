from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.directed_retrieval import (
    DirectedMemoryCandidateProvider,
    DirectedRetrievalConfig,
    DirectedRetrievalEngine,
    DirectedRetrievalError,
    FirstVersionDirectedRetrievalPath,
    MemoryRetrievalCandidate,
    RetrievalQueryPlan,
    RetrievalRequest,
)
from helios_v2.thought_gating import (
    ContinuationPressureState,
    SelectedStimulusSummary,
    ThoughtGateResult,
)


def _build_config() -> DirectedRetrievalConfig:
    return DirectedRetrievalConfig(
        max_hits_per_tier=2,
        max_short_term_context=1,
        retrieval_bootstrap_id="directed-retrieval-bootstrap:v1",
        mandatory_learned_parameters=(
            "retrieval_planning_policy",
            "tier_selection_policy",
            "thought_window_shaping_policy",
        ),
    )


def _build_gate_result(decision: str = "fire") -> ThoughtGateResult:
    return ThoughtGateResult(
        result_id="thought-gate-result:001",
        source_conscious_state_id="conscious-state:001",
        source_signal_snapshot_id="gate-snapshot:001",
        decision=decision,
        gate_score=0.9 if decision == "fire" else 0.1,
        trigger_reason="salient_stimulus" if decision == "fire" else None,
        dominant_reason="salient_stimulus" if decision == "fire" else "gate_score_too_low",
        blocked_reasons=() if decision == "fire" else ("gate_score_too_low",),
        contributing_signals={"stimulus_signal": 0.8},
        selected_stimuli=(_stimulus_summary(),),
        no_fire_reason=None if decision == "fire" else "gate_score_too_low",
        tick_id=1,
    )


def _stimulus_summary() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.8,
    )


def _build_request() -> RetrievalRequest:
    return RetrievalRequest(
        request_id="retrieval-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_continuation_active=False,
        compact_stimuli=(_stimulus_summary(),),
        recall_intent="remember the current exchange",
        selected_memory_refs=("memory:preferred",),
        target_tiers=("short_term", "mid_term", "long_term", "autobiographical"),
        limit=2,
        tick_id=1,
    )


@dataclass
class FixedCandidateProvider(DirectedMemoryCandidateProvider):
    def collect_candidates(self, plan: RetrievalQueryPlan) -> tuple[MemoryRetrievalCandidate, ...]:
        assert plan.query_text
        return (
            MemoryRetrievalCandidate(
                candidate_id="candidate:short:001",
                tier="short_term",
                memory_id="memory:short:001",
                memory_type="short_term_context",
                summary="current compact stimulus",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
            MemoryRetrievalCandidate(
                candidate_id="candidate:mid:001",
                tier="mid_term",
                memory_id="memory:mid:001",
                memory_type="episodic",
                summary="strong mid term memory",
                score=0.8,
                source="memory_affect_and_replay",
                tags=("affective",),
            ),
            MemoryRetrievalCandidate(
                candidate_id="candidate:mid:002",
                tier="mid_term",
                memory_id="memory:mid:002",
                memory_type="episodic",
                summary="weaker mid term memory",
                score=0.3,
                source="memory_affect_and_replay",
                tags=("affective",),
            ),
            MemoryRetrievalCandidate(
                candidate_id="candidate:auto:001",
                tier="autobiographical",
                memory_id="memory:auto:001",
                memory_type="autobiographical",
                summary="autobiographical continuity memory",
                score=0.7,
                source="memory_affect_and_replay",
                tags=("continuity",),
            ),
        )


def test_engine_builds_plan_bundle_and_publication_ops() -> None:
    engine = DirectedRetrievalEngine(
        config=_build_config(),
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=FixedCandidateProvider(),
    )
    gate_result = _build_gate_result()
    request = _build_request()
    continuation = ContinuationPressureState.inactive()

    plan_op = engine.build_plan_op(gate_result, request)
    plan, bundle = engine.retrieve_for_thought_window(gate_result, continuation, request)
    publish_op = engine.build_publish_bundle_op(bundle)

    assert plan_op.op_name == "plan_directed_retrieval"
    assert plan.source_request_id == request.request_id
    assert plan.query_source == "mixed"
    assert len(bundle.short_term_context) == 1
    assert len(bundle.mid_term_hits) == 2
    assert len(bundle.long_term_hits) == 0
    assert len(bundle.autobiographical_hits) == 1
    assert {trace.tier_name for trace in bundle.selection_trace} == {
        "short_term",
        "mid_term",
        "long_term",
        "autobiographical",
    }
    assert any(item.selected is False for item in bundle.retrieval_sec_trace) is False
    assert publish_op.bundle_id == bundle.bundle_id


def test_engine_rejects_no_fire_gate_result_without_fallback_bundle() -> None:
    engine = DirectedRetrievalEngine(
        config=_build_config(),
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=FixedCandidateProvider(),
    )

    with pytest.raises(DirectedRetrievalError, match="fired"):
        engine.retrieve_for_thought_window(
            _build_gate_result(decision="no_fire"),
            ContinuationPressureState.inactive(),
            _build_request(),
        )


def test_engine_requires_explicit_public_memory_candidate_provider() -> None:
    engine = DirectedRetrievalEngine(
        config=_build_config(),
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=None,
    )

    with pytest.raises(DirectedRetrievalError, match="candidate provider"):
        engine.retrieve_for_thought_window(
            _build_gate_result(),
            ContinuationPressureState.inactive(),
            _build_request(),
        )


def test_engine_rejects_mismatched_continuation_handoff() -> None:
    engine = DirectedRetrievalEngine(
        config=_build_config(),
        retrieval_path=FirstVersionDirectedRetrievalPath(),
        candidate_provider=FixedCandidateProvider(),
    )
    continuation = ContinuationPressureState(
        active=True,
        level=0.5,
        origin_thought_id="thought:001",
        reason="unfinished_reflection",
        expires_at_tick=3,
        carry_count=1,
    )

    with pytest.raises(DirectedRetrievalError, match="continuation active flag"):
        engine.retrieve_for_thought_window(_build_gate_result(), continuation, _build_request())
