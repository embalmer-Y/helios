from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtError,
    InternalThoughtRequest,
    InternalThoughtTrace,
    SelfRevisionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
)
from helios_v2.internal_thought.engine import InternalThoughtPath
from helios_v2.thought_gating import ContinuationPressureState, SelectedStimulusSummary, ThoughtGateResult


def _build_config() -> InternalThoughtConfig:
    return InternalThoughtConfig(
        legal_min_sufficiency=0.0,
        legal_max_sufficiency=1.0,
        thought_bootstrap_id="internal-thought-bootstrap:v1",
        mandatory_learned_parameters=(
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        ),
    )


def _stimulus() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.8,
    )


def _gate_result(decision: str = "fire") -> ThoughtGateResult:
    return ThoughtGateResult(
        result_id="thought-gate-result:001",
        source_conscious_state_id="conscious-state:001",
        source_signal_snapshot_id="gate-snapshot:001",
        decision=decision,
        gate_score=0.8 if decision == "fire" else 0.2,
        trigger_reason="salient_stimulus" if decision == "fire" else None,
        dominant_reason="salient_stimulus" if decision == "fire" else "gate_score_too_low",
        blocked_reasons=() if decision == "fire" else ("gate_score_too_low",),
        contributing_signals={"stimulus_signal": 0.8},
        selected_stimuli=(_stimulus(),),
        no_fire_reason=None if decision == "fire" else "gate_score_too_low",
        tick_id=1,
    )


def _bundle() -> ThoughtWindowBundle:
    return ThoughtWindowBundle(
        bundle_id="thought-window-bundle:001",
        source_plan_id="retrieval-plan:001",
        short_term_context=(
            ThoughtWindowHit(
                memory_id="memory:short:001",
                memory_type="short_term_context",
                summary="current stimulus context",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
        ),
        mid_term_hits=(
            ThoughtWindowHit(
                memory_id="memory:mid:001",
                memory_type="episodic",
                summary="mid term episodic memory",
                score=0.7,
                source="memory_affect_and_replay",
                tags=("episodic",),
            ),
        ),
        long_term_hits=(),
        autobiographical_hits=(
            ThoughtWindowHit(
                memory_id="memory:auto:001",
                memory_type="autobiographical",
                summary="autobiographical continuity memory",
                score=0.75,
                source="memory_affect_and_replay",
                tags=("continuity",),
            ),
        ),
        selection_trace=(
            RetrievalSelectionTrace("short_term", 1, 1, "mixed"),
            RetrievalSelectionTrace("mid_term", 1, 1, "mixed"),
            RetrievalSelectionTrace("long_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("autobiographical", 1, 1, "mixed"),
        ),
        retrieval_sec_trace=(),
        tick_id=1,
    )


def _request(source_continuation_active: bool = False) -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=source_continuation_active,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
    )


@dataclass
class RecordingInternalThoughtPath(InternalThoughtPath):
    def run(
        self,
        gate_result,
        retrieval_bundle,
        continuation_state,
        request,
        config,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        assert gate_result.result_id == "thought-gate-result:001"
        assert retrieval_bundle.bundle_id == "thought-window-bundle:001"
        assert continuation_state.active is False
        assert config.thought_bootstrap_id == "internal-thought-bootstrap:v1"
        thought = ThoughtContent(
            thought_id="thought:001",
            thought_type="stimulus_response_thought",
            content="structured thought content",
            source_path="recording_test_path",
            llm_used=False,
            fallback_used=False,
        )
        result = ThoughtCycleResult(
            result_id="thought-cycle-result:001",
            source_request_id=request.request_id,
            execution_status="completed",
            thought=thought,
            trigger_reason="salient_stimulus",
            sufficiency_level=0.8,
            continuation_requested=False,
            continuation_reason="sufficient_current_cycle",
            continuation_pressure_delta=0.1,
            recall_intent="",
            memory_handoff=None,
            action_proposal=None,
            self_revision_proposal=SelfRevisionProposalCarrier(
                proposal_id="self-revision:001",
                revision_kind="identity_narrative",
                requested_change_summary="tighten autobiographical self-description",
                reason_trace="thought-origin self revision",
            ),
            tick_id=1,
        )
        trace = InternalThoughtTrace(
            triggered=True,
            trigger_reason="salient_stimulus",
            llm_used=False,
            fallback_used=False,
            execution_status="completed",
            sufficiency_level=0.8,
            continuation_requested=False,
            continuation_reason="sufficient_current_cycle",
            recall_intent="",
            action_explicit=False,
            action_parse_status="absent",
        )
        return result, trace


def test_engine_builds_completed_result_and_publish_op() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=RecordingInternalThoughtPath())

    run_op = engine.build_run_op(_gate_result(), _bundle(), _request())
    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )
    publish_op = engine.build_publish_result_op(result)

    assert run_op.op_name == "run_internal_thought"
    assert result.execution_status == "completed"
    assert result.self_revision_proposal is not None
    assert trace.execution_status == "completed"
    assert publish_op.has_self_revision_proposal is True


def test_first_version_path_returns_completed_result_and_optional_action_proposal() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=FirstVersionInternalThoughtPath())

    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )

    assert result.execution_status == "completed"
    assert result.thought is not None
    assert result.action_proposal is not None
    assert result.action_proposal.outbound_text == result.thought.content
    assert trace.action_explicit is True



def test_engine_rejects_no_fire_gate_result_without_fallback() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=FirstVersionInternalThoughtPath())

    with pytest.raises(InternalThoughtError, match="fired"):
        engine.run_thought_cycle(
            _gate_result(decision="no_fire"),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )


def test_engine_requires_explicit_thought_capability() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=None)

    with pytest.raises(InternalThoughtError, match="explicit thought capability"):
        engine.run_thought_cycle(
            _gate_result(),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )
