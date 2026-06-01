from __future__ import annotations

import pytest

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.identity_governance import (
    FirstVersionIdentityGovernancePath,
    IdentityGovernanceConfig,
    IdentityGovernanceEngine,
    IdentityGovernanceError,
    IdentityGovernanceRequest,
)
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtRequest,
)
from helios_v2.thought_gating import ContinuationPressureState, SelectedStimulusSummary, ThoughtGateResult


def _build_internal_config() -> InternalThoughtConfig:
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


def _build_governance_config() -> IdentityGovernanceConfig:
    return IdentityGovernanceConfig(
        legal_min_confidence=0.0,
        legal_max_confidence=1.0,
        governance_bootstrap_id="identity-governance-bootstrap:v1",
        mandatory_learned_parameters=(
            "governance_evaluation_policy",
            "pressure_interpretation_policy",
            "supported_revision_policy",
            "boundary_check_policy",
        ),
    )


def _stimulus() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.8,
    )


def _gate_result() -> ThoughtGateResult:
    return ThoughtGateResult(
        result_id="thought-gate-result:001",
        source_conscious_state_id="conscious-state:001",
        source_signal_snapshot_id="gate-snapshot:001",
        decision="fire",
        gate_score=0.8,
        trigger_reason="salient_stimulus",
        dominant_reason="salient_stimulus",
        blocked_reasons=(),
        contributing_signals={"stimulus_signal": 0.8},
        selected_stimuli=(_stimulus(),),
        no_fire_reason=None,
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


def _internal_request() -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
    )


def _thought_result():
    thought_engine = InternalThoughtEngine(
        config=_build_internal_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    return thought_engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _internal_request(),
    )[0]


def _identity_state_snapshot() -> dict[str, object]:
    return {
        "self_definition": "Existing self definition",
        "personality_baseline": {"openness": 1.0, "agreeableness": 1.0},
        "identity_metadata": {},
        "current_revision": "bootstrap",
        "revision_history_length": 0,
    }


def _monitor_history() -> tuple[dict[str, object], ...]:
    return (
        {"recorded_at_ts": 0.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 10.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 20.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 30.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
    )


def _stabilize_history() -> tuple[dict[str, object], ...]:
    return (
        {"recorded_at_ts": 0.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 10.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 20.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 30.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
        {"recorded_at_ts": 40.0, "dominant_disposition": "defer", "source_type": "thought", "trigger_sources": ["continuity"]},
    )


def _request(
    proposal_snapshot: dict[str, object],
    *,
    history: tuple[dict[str, object], ...] = (),
) -> IdentityGovernanceRequest:
    thought_result = _thought_result()
    carrier = thought_result.self_revision_proposal
    assert carrier is not None
    return IdentityGovernanceRequest(
        request_id="identity-governance-request:001",
        source_thought_cycle_result_id=thought_result.result_id,
        source_proposal_id=carrier.proposal_id,
        proposal_present=True,
        proposal_snapshot=proposal_snapshot,
        identity_state_snapshot=_identity_state_snapshot(),
        governance_trace_summary={},
        recent_governance_trace_history=history,
        tick_id=1,
    )


def test_engine_publishes_accepted_identity_mutation_and_applied_state() -> None:
    engine = IdentityGovernanceEngine(
        config=_build_governance_config(),
        governance_path=FirstVersionIdentityGovernancePath(),
    )
    thought_result = _thought_result()
    request = _request(
        {
            "owner_path": "self_revision_governance_bridge",
            "revision_type": "autobiographical_identity_narrative_revision",
            "requested_change": {"narrative_summary": "Continuity memory refines current self story"},
            "confidence": 0.78,
            "reason_trace": ("autobiographical continuity surfaced during internal thought",),
        }
    )

    result = engine.evaluate_self_revision(thought_result, request)
    pressure_op = engine.build_publish_pressure_op(request, result.pressure_state)
    decision_op = engine.build_publish_revision_decision_op(result.revision_decision)
    applied_state_op = engine.build_publish_applied_identity_state_op(result.applied_identity_state)

    assert result.revision_decision.status == "accepted"
    assert result.applied_identity_state is not None
    assert result.applied_identity_state.identity_state_snapshot["current_revision"] == result.revision_decision.revision_id
    assert pressure_op.pressure_level == "none"
    assert decision_op.status == "accepted"
    assert applied_state_op.current_revision == result.revision_decision.revision_id


def test_engine_publishes_monitoring_acceptance_distinct_from_rejection() -> None:
    engine = IdentityGovernanceEngine(
        config=_build_governance_config(),
        governance_path=FirstVersionIdentityGovernancePath(),
    )
    thought_result = _thought_result()
    request = _request(
        {
            "owner_path": "self_revision_governance_bridge",
            "revision_type": "self_definition_revision",
            "requested_change": {"self_definition": "Helios understands itself through ongoing continuity"},
            "confidence": 0.9,
            "reason_trace": ("reflective self-definition update",),
        },
        history=_monitor_history(),
    )

    result = engine.evaluate_self_revision(thought_result, request)

    assert result.pressure_state.pressure_level == "monitor"
    assert result.revision_decision.status == "accepted_with_monitoring"
    assert result.applied_identity_state is not None


def test_engine_publishes_governance_backpressure_rejection() -> None:
    engine = IdentityGovernanceEngine(
        config=_build_governance_config(),
        governance_path=FirstVersionIdentityGovernancePath(),
    )
    thought_result = _thought_result()
    request = _request(
        {
            "owner_path": "self_revision_governance_bridge",
            "revision_type": "personality_adjustment",
            "requested_change": {"personality_baseline": {"openness": 1.4}},
            "confidence": 0.4,
            "reason_trace": ("low-confidence trait adjustment",),
        },
        history=_stabilize_history(),
    )

    result = engine.evaluate_self_revision(thought_result, request)

    assert result.pressure_state.pressure_level == "stabilize"
    assert result.revision_decision.status == "rejected"
    assert result.revision_decision.rejection_reason == "governance_backpressure"
    assert result.applied_identity_state is None


def test_engine_requires_explicit_governance_capability() -> None:
    engine = IdentityGovernanceEngine(config=_build_governance_config(), governance_path=None)

    with pytest.raises(IdentityGovernanceError, match="explicit governance capability"):
        engine.evaluate_self_revision(
            _thought_result(),
            _request(
                {
                    "owner_path": "self_revision_governance_bridge",
                    "revision_type": "autobiographical_identity_narrative_revision",
                    "requested_change": {"narrative_summary": "Continuity memory refines current self story"},
                    "confidence": 0.78,
                    "reason_trace": ("autobiographical continuity surfaced during internal thought",),
                }
            ),
        )