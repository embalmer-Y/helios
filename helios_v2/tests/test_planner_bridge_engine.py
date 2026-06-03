from __future__ import annotations

import pytest

from helios_v2.action_externalization import (
    ActionExternalizationConfig,
    ActionExternalizationEngine,
    FirstVersionThoughtExternalizationPath,
    ThoughtExternalizationRequest,
)
from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtRequest,
)
from helios_v2.planner_bridge import (
    FirstVersionPlannerBridgePath,
    PlannerBridgeConfig,
    PlannerBridgeEngine,
    PlannerBridgeError,
    PlannerBridgeRequest,
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


def _build_externalization_config() -> ActionExternalizationConfig:
    return ActionExternalizationConfig(
        legal_min_outbound_intensity=0.0,
        legal_max_outbound_intensity=1.0,
        externalization_bootstrap_id="action-externalization-bootstrap:v1",
        mandatory_learned_parameters=(
            "normalization_policy",
            "bridge_evidence_policy",
            "bridge_rejection_policy",
        ),
    )


def _build_bridge_config() -> PlannerBridgeConfig:
    return PlannerBridgeConfig(
        legal_min_intensity=0.0,
        legal_max_intensity=1.0,
        bridge_bootstrap_id="planner-bridge-bootstrap:v1",
        mandatory_learned_parameters=(
            "policy_evaluation_policy",
            "channel_selection_policy",
            "feedback_normalization_policy",
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


def _externalization_request() -> ThoughtExternalizationRequest:
    return ThoughtExternalizationRequest(
        request_id="externalization-request:001",
        source_thought_cycle_result_id="thought-cycle-result:internal-thought-request:001",
        proposal_carrier_present=True,
        target_binding_context={"target_user_id": "user:001"},
        channel_hint_context={"channel_family": "cli"},
        tick_id=1,
    )


def _externalization_result():
    thought_engine = InternalThoughtEngine(
        config=_build_internal_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    thought_result, _ = thought_engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _internal_request(),
    )
    externalization_engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    return externalization_engine.externalize_action_proposal(thought_result, _externalization_request())


def _bridge_request() -> PlannerBridgeRequest:
    return PlannerBridgeRequest(
        request_id="planner-bridge-request:001",
        source_externalization_result_id="thought-externalization-result:externalization-request:001",
        normalized_proposal_present=True,
        behavior_snapshot={
            "registered": True,
            "reviewed": True,
            "minimum_score": 0.5,
            "proposal_score": 0.9,
            "execution_priority": 2,
        },
        channel_descriptor_snapshot={
            "cli": {
                "supported_ops": ("reply_message",),
                "output_ops": ("reply_message",),
            }
        },
        channel_status_snapshot={
            "cli": {
                "available": True,
                "bound": True,
                "execute_now": True,
                "execution_success": True,
            }
        },
        tick_id=1,
    )


def test_engine_publishes_executed_bridge_result_and_feedback() -> None:
    engine = PlannerBridgeEngine(
        config=_build_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )

    evaluate_op = engine.build_evaluate_op(_externalization_result(), _bridge_request())
    result, feedback = engine.evaluate_proposal(_externalization_result(), _bridge_request())
    decision_op = engine.build_publish_decision_op(result.action_decision)
    feedback_op = engine.build_publish_execution_feedback_op(feedback)

    assert evaluate_op.normalized_proposal_present is True
    assert result.status == "executed"
    assert result.action_decision is not None
    assert feedback is not None
    assert feedback.success is True
    assert decision_op.selected_channel_id == "cli"
    assert feedback_op.success is True


def test_engine_publishes_policy_rejection_without_execution() -> None:
    engine = PlannerBridgeEngine(
        config=_build_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    request = PlannerBridgeRequest(
        request_id="planner-bridge-request:reject",
        source_externalization_result_id="thought-externalization-result:externalization-request:001",
        normalized_proposal_present=True,
        behavior_snapshot={
            "registered": False,
            "reviewed": True,
            "minimum_score": 0.5,
            "proposal_score": 0.9,
            "execution_priority": 2,
        },
        channel_descriptor_snapshot={
            "cli": {"supported_ops": ("reply_message",), "output_ops": ("reply_message",)}
        },
        channel_status_snapshot={"cli": {"available": True, "bound": True, "execute_now": True}},
        tick_id=1,
    )

    result, feedback = engine.evaluate_proposal(_externalization_result(), request)
    rejection_op = engine.build_publish_rejection_op(result)

    assert result.status == "policy_rejected"
    assert result.rejection_reason == "behavior_not_registered"
    assert feedback is None
    assert rejection_op.rejection_reason == "behavior_not_registered"


def test_engine_publishes_execution_consistency_failure_distinct_from_policy_rejection() -> None:
    engine = PlannerBridgeEngine(
        config=_build_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    request = PlannerBridgeRequest(
        request_id="planner-bridge-request:consistency",
        source_externalization_result_id="thought-externalization-result:externalization-request:001",
        normalized_proposal_present=True,
        behavior_snapshot={
            "registered": True,
            "reviewed": True,
            "minimum_score": 0.5,
            "proposal_score": 0.9,
            "execution_priority": 2,
        },
        channel_descriptor_snapshot={
            "cli": {"supported_ops": ("reply_message",), "output_ops": ("reply_message",)}
        },
        channel_status_snapshot={"cli": {"available": True, "bound": False, "execute_now": True}},
        tick_id=1,
    )

    result, feedback = engine.evaluate_proposal(_externalization_result(), request)
    rejection_op = engine.build_publish_rejection_op(result)

    assert result.status == "execution_consistency_failed"
    assert result.execution_consistency_failure is not None
    assert result.rejection_reason == "missing_channel_binding"
    assert feedback is None
    assert rejection_op.status == "execution_consistency_failed"


def test_engine_requires_explicit_bridge_capability() -> None:
    engine = PlannerBridgeEngine(config=_build_bridge_config(), bridge_path=None)

    with pytest.raises(PlannerBridgeError, match="explicit bridge capability"):
        engine.evaluate_proposal(_externalization_result(), _bridge_request())


# --- Requirement 28: internal-only (no actionable proposal) bridge result ---


def _internal_request_continue() -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:continue",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=True,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
    )


def _non_normalized_externalization_result():
    # A continuation-active thought cycle emits no action proposal, so externalization
    # produces a non-normalized result (no proposal to route).
    thought_engine = InternalThoughtEngine(
        config=_build_internal_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    continuation = ContinuationPressureState(
        active=True,
        level=0.5,
        origin_thought_id="thought:prior",
        reason="prior_cycle_unfinished",
        expires_at_tick=5,
        carry_count=1,
    )
    thought_result, _ = thought_engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        continuation,
        _internal_request_continue(),
    )
    assert thought_result.action_proposal is None
    externalization_engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    request = ThoughtExternalizationRequest(
        request_id="externalization-request:continue",
        source_thought_cycle_result_id=thought_result.result_id,
        proposal_carrier_present=False,
        target_binding_context={"target_user_id": "user:001"},
        channel_hint_context={"channel_family": "cli"},
        tick_id=1,
    )
    return externalization_engine.externalize_action_proposal(thought_result, request)


def _internal_only_bridge_request(externalization_result_id: str) -> PlannerBridgeRequest:
    return PlannerBridgeRequest(
        request_id="planner-bridge-request:internal-only",
        source_externalization_result_id=externalization_result_id,
        normalized_proposal_present=False,
        behavior_snapshot={},
        channel_descriptor_snapshot={},
        channel_status_snapshot={},
        tick_id=1,
    )


def test_engine_produces_internal_only_result_for_no_proposal() -> None:
    engine = PlannerBridgeEngine(
        config=_build_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    externalization_result = _non_normalized_externalization_result()
    request = _internal_only_bridge_request(externalization_result.result_id)

    evaluate_op = engine.build_evaluate_op_internal_only(externalization_result, request)
    result = engine.evaluate_internal_only(externalization_result, request)

    assert evaluate_op.op_name == "evaluate_planner_bridge_internal_only"
    assert evaluate_op.normalized_proposal_present is False
    assert result.status == "no_actionable_proposal"
    assert result.action_decision is None
    assert result.rejection_reason is None
    assert result.execution_consistency_failure is None


def test_internal_only_rejects_normalized_result() -> None:
    engine = PlannerBridgeEngine(
        config=_build_bridge_config(),
        bridge_path=FirstVersionPlannerBridgePath(),
    )
    # A normalized externalization result must go through the externalizing path, not the
    # internal-only path.
    with pytest.raises(PlannerBridgeError):
        engine.evaluate_internal_only(_externalization_result(), _bridge_request())
