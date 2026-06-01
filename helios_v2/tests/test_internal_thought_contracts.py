from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.internal_thought import (
    InternalThoughtConfig,
    InternalThoughtError,
    InternalThoughtRequest,
    MemoryHandoffDirective,
    ThoughtActionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
)


def _request() -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=False,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
    )


def _thought_content() -> ThoughtContent:
    return ThoughtContent(
        thought_id="thought:001",
        thought_type="stimulus_response_thought",
        content="structured current-cycle thought",
        source_path="deterministic_first_version",
        llm_used=False,
        fallback_used=False,
    )


def test_internal_thought_request_is_immutable_and_mapping_is_read_only() -> None:
    request = _request()

    with pytest.raises(FrozenInstanceError):
        request.internal_state_summary = "changed"

    with pytest.raises(TypeError):
        request.prompt_contract_summary["mode"] = "changed"


def test_internal_thought_config_requires_fixed_learned_policy_surface() -> None:
    config = InternalThoughtConfig(
        legal_min_sufficiency=0.0,
        legal_max_sufficiency=1.0,
        thought_bootstrap_id="internal-thought-bootstrap:v1",
        mandatory_learned_parameters=(
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        ),
    )

    assert config.thought_bootstrap_id == "internal-thought-bootstrap:v1"

    with pytest.raises(InternalThoughtError, match="mandatory learned-parameter categories"):
        InternalThoughtConfig(
            legal_min_sufficiency=0.0,
            legal_max_sufficiency=1.0,
            thought_bootstrap_id="internal-thought-bootstrap:v1",
            mandatory_learned_parameters=("thought_generation_policy",),
        )


def test_memory_handoff_requires_source_thought_and_saved_intent() -> None:
    handoff = MemoryHandoffDirective(
        recall_intent="remember this context",
        selected_memory_refs=("memory:001",),
        saved_for_next_tick=True,
        source_thought_id="thought:001",
    )

    assert handoff.source_thought_id == "thought:001"

    with pytest.raises(InternalThoughtError, match="recall_intent"):
        MemoryHandoffDirective(
            recall_intent="",
            selected_memory_refs=("memory:001",),
            saved_for_next_tick=True,
            source_thought_id="thought:001",
        )


def test_thought_cycle_result_requires_completed_thought_for_completed_status() -> None:
    result = ThoughtCycleResult(
        result_id="thought-cycle-result:001",
        source_request_id="internal-thought-request:001",
        execution_status="completed",
        thought=_thought_content(),
        trigger_reason="salient_stimulus",
        sufficiency_level=0.7,
        continuation_requested=False,
        continuation_reason="sufficient_current_cycle",
        continuation_pressure_delta=0.1,
        recall_intent="",
        memory_handoff=None,
        action_proposal=ThoughtActionProposalCarrier(
            proposal_id="action-proposal:001",
            scope="external",
            behavior_name="reply_message",
            requested_op="reply_message",
            preferred_channels=("cli",),
            outbound_text="structured response",
            outbound_intensity=0.8,
            reason_trace=("structured response",),
            governance_hints={"requires_identity_review": False},
        ),
        self_revision_proposal=None,
        tick_id=1,
    )

    assert result.execution_status == "completed"

    with pytest.raises(InternalThoughtError, match="must publish thought"):
        ThoughtCycleResult(
            result_id="thought-cycle-result:bad",
            source_request_id="internal-thought-request:001",
            execution_status="completed",
            thought=None,
            trigger_reason="salient_stimulus",
            sufficiency_level=0.6,
            continuation_requested=False,
            continuation_reason="sufficient_current_cycle",
            continuation_pressure_delta=0.1,
            recall_intent="",
            memory_handoff=None,
            action_proposal=None,
            self_revision_proposal=None,
            tick_id=1,
        )
