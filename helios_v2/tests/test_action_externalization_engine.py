from __future__ import annotations

import pytest

from helios_v2.action_externalization import (
    ActionExternalizationConfig,
    ActionExternalizationEngine,
    ActionExternalizationError,
    FirstVersionThoughtExternalizationPath,
    ThoughtExternalizationRequest,
)
from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtRequest,
    ThoughtActionProposalCarrier,
)
from helios_v2.thought_gating import ContinuationPressureState
from helios_v2.thought_gating import SelectedStimulusSummary, ThoughtGateResult


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


def _request() -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={
            "mode": "internal_thought",
            "voice": "structured",
            # R95 followup (C3): the offline deterministic default op is
            # data-driven from `available_channel_ops` (see engine.py
            # `_default_op_from_request`). The shim's literal
            # `reply_message` lives only in the test fixture; the engine
            # no longer names ops.
            "available_channel_ops": (
                {
                    "driver_id": "cli",
                    "op_name": "reply_message",
                    "required_params": ("outbound_text", "target_user_id"),
                    "effect_class": "external_world",
                    "risk_class": "unrestricted",
                    "bound_user_ids": ("*",),
                },
            ),
        },
        tick_id=1,
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


def _thought_result():
    engine = InternalThoughtEngine(
        config=_build_internal_config(),
        thought_path=FirstVersionInternalThoughtPath(),
    )
    result, _ = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )
    return result


def _externalization_request(proposal_present: bool = True) -> ThoughtExternalizationRequest:
    return ThoughtExternalizationRequest(
        request_id="externalization-request:001",
        source_thought_cycle_result_id="thought-cycle-result:internal-thought-request:001",
        proposal_carrier_present=proposal_present,
        target_binding_context={"target_user_id": "user:001"},
        channel_hint_context={"channel_family": "cli"},
        tick_id=1,
    )


def test_engine_normalizes_explicit_action_proposal_and_builds_publish_op() -> None:
    engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    thought_result = _thought_result()
    request = _externalization_request()

    request_op = engine.build_request_op(thought_result, request)
    result = engine.externalize_action_proposal(thought_result, request)
    publish_op = engine.build_publish_externalization_op(result)

    assert request_op.proposal_carrier_present is True
    assert result.status == "normalized"
    assert result.normalized_proposal is not None
    assert result.normalized_proposal.params["outbound_text"] == thought_result.thought.content
    assert publish_op.behavior_name == "reply_message"


def test_engine_normalizes_structurally_when_outbound_text_absent() -> None:
    # R85/D2a: `12` no longer rejects a missing reply text - that op-aware check moved to `13`
    # (the planner validates required_params from the driver's per-op spec). `12` normalizes
    # structurally; the resulting params simply omit outbound_text.
    engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    thought_result = _thought_result()
    thought_result = thought_result.__class__(
        result_id=thought_result.result_id,
        source_request_id=thought_result.source_request_id,
        execution_status=thought_result.execution_status,
        thought=thought_result.thought,
        trigger_reason=thought_result.trigger_reason,
        sufficiency_level=thought_result.sufficiency_level,
        continuation_requested=thought_result.continuation_requested,
        continuation_reason=thought_result.continuation_reason,
        continuation_pressure_delta=thought_result.continuation_pressure_delta,
        recall_intent=thought_result.recall_intent,
        memory_handoff=thought_result.memory_handoff,
        action_proposal=ThoughtActionProposalCarrier(
            proposal_id="thought-action:no-text",
            scope="external",
            behavior_name="reply_message",
            requested_op="reply_message",
            preferred_channels=("cli",),
            outbound_text=None,
            outbound_intensity=0.7,
            reason_trace=("no outbound text",),
            governance_hints={"requires_identity_review": False},
        ),
        self_revision_proposal=thought_result.self_revision_proposal,
        tick_id=thought_result.tick_id,
    )
    request = _externalization_request()

    result = engine.externalize_action_proposal(thought_result, request)

    assert result.status == "normalized"
    assert result.normalized_proposal is not None
    assert "outbound_text" not in result.normalized_proposal.params


def test_engine_carries_op_params_for_effector_proposal() -> None:
    # R85: a tool/effector proposal carries its op_params (e.g. path/content) into the normalized
    # proposal's params, without a reply-specific outbound_text.
    engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    thought_result = _thought_result()
    thought_result = thought_result.__class__(
        result_id=thought_result.result_id,
        source_request_id=thought_result.source_request_id,
        execution_status=thought_result.execution_status,
        thought=thought_result.thought,
        trigger_reason=thought_result.trigger_reason,
        sufficiency_level=thought_result.sufficiency_level,
        continuation_requested=thought_result.continuation_requested,
        continuation_reason=thought_result.continuation_reason,
        continuation_pressure_delta=thought_result.continuation_pressure_delta,
        recall_intent=thought_result.recall_intent,
        memory_handoff=thought_result.memory_handoff,
        action_proposal=ThoughtActionProposalCarrier(
            proposal_id="thought-action:tool",
            scope="external",
            behavior_name="fs_write",
            requested_op="fs_write",
            preferred_channels=("os_fs",),
            outbound_text=None,
            outbound_intensity=0.7,
            reason_trace=("tool op",),
            governance_hints={"requires_identity_review": False},
            op_params={"path": "notes/a.txt", "content": "hi"},
        ),
        self_revision_proposal=thought_result.self_revision_proposal,
        tick_id=thought_result.tick_id,
    )
    request = _externalization_request()

    result = engine.externalize_action_proposal(thought_result, request)

    assert result.status == "normalized"
    assert result.normalized_proposal.preferred_op == "fs_write"
    assert result.normalized_proposal.params["path"] == "notes/a.txt"
    assert result.normalized_proposal.params["content"] == "hi"
    assert "outbound_text" not in result.normalized_proposal.params


def test_engine_emits_equivalent_evidence_when_completed_thought_has_no_explicit_action() -> None:
    engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=FirstVersionThoughtExternalizationPath(),
    )
    thought_result = _thought_result()
    thought_result = thought_result.__class__(
        result_id=thought_result.result_id,
        source_request_id=thought_result.source_request_id,
        execution_status=thought_result.execution_status,
        thought=thought_result.thought,
        trigger_reason=thought_result.trigger_reason,
        sufficiency_level=thought_result.sufficiency_level,
        continuation_requested=thought_result.continuation_requested,
        continuation_reason=thought_result.continuation_reason,
        continuation_pressure_delta=thought_result.continuation_pressure_delta,
        recall_intent=thought_result.recall_intent,
        memory_handoff=thought_result.memory_handoff,
        action_proposal=None,
        self_revision_proposal=thought_result.self_revision_proposal,
        tick_id=thought_result.tick_id,
    )
    request = _externalization_request(proposal_present=False)

    result = engine.externalize_action_proposal(thought_result, request)

    assert result.status == "equivalent_evidence_only"
    assert result.equivalent_evidence is not None
    assert result.equivalent_evidence.origin_thought_id == thought_result.thought.thought_id


def test_engine_requires_explicit_bridge_capability() -> None:
    engine = ActionExternalizationEngine(
        config=_build_externalization_config(),
        externalization_path=None,
    )

    with pytest.raises(ActionExternalizationError, match="explicit bridge capability"):
        engine.externalize_action_proposal(_thought_result(), _externalization_request())
