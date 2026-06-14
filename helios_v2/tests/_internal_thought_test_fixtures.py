"""Shared fixture helpers reused by the R93 implicit-reply tests.

Mirrors the proven helpers in `test_internal_thought_engine.py` so the R93 tests do not
duplicate non-trivial gate-result / retrieval-bundle / config / structured-path construction.
This module name does NOT start with `test_`, so pytest does not collect it as a test module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from helios_v2.directed_retrieval import (
    RetrievalSelectionTrace,
    ThoughtWindowBundle,
    ThoughtWindowHit,
)
from helios_v2.internal_thought import InternalThoughtConfig
from helios_v2.internal_thought.engine import InternalThoughtPath, LlmBackedInternalThoughtPath
from helios_v2.thought_gating import SelectedStimulusSummary, ThoughtGateResult


def build_test_config() -> InternalThoughtConfig:
    return InternalThoughtConfig(
        legal_min_sufficiency=0.0,
        legal_max_sufficiency=1.0,
        thought_bootstrap_id="internal-thought-bootstrap:r93",
        mandatory_learned_parameters=(
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        ),
    )


def _selected_stimulus() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.8,
    )


def fired_gate_result() -> ThoughtGateResult:
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
        selected_stimuli=(_selected_stimulus(),),
        no_fire_reason=None,
        tick_id=1,
    )


def populated_bundle() -> ThoughtWindowBundle:
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


@dataclass
class JsonReplyGateway:
    """Network-free gateway returning a fixed JSON envelope for R93 implicit-reply tests."""

    payload: dict
    seen_formats: list[str] = field(default_factory=list)

    def complete(self, request) -> Any:
        from helios_v2.llm import LlmCompletion, LlmUsage

        self.seen_formats.append(getattr(request, "response_format", "") or "")
        return LlmCompletion(
            completion_id=f"llm-completion:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="fake-model",
            output_text=json.dumps(self.payload, ensure_ascii=False),
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
            latency_ms=1.0,
        )

    def is_profile_ready(self, profile_name: str) -> bool:
        return True

    def list_profile_names(self) -> tuple[str, ...]:
        return ("test-profile",)


def structured_path(gateway: Any) -> InternalThoughtPath:
    return LlmBackedInternalThoughtPath(
        gateway=gateway,
        profile_name="test-profile",
    )


def envelope(
    *,
    thought: str = "model thought",
    sufficiency: float = 0.9,
    wants_to_continue: bool = False,
    continue_reason: str = "",
    intends_action: bool = False,
    intends_revision: bool = False,
    i_want_to_say: Any = None,
    i_want_to_use_tool: Any = None,
    tool_op: Any = None,
    tool_params: Any = None,
) -> dict:
    payload = {
        "thought": thought,
        "sufficiency": sufficiency,
        "wants_to_continue": wants_to_continue,
        "continue_reason": continue_reason,
        "proposed_action": {"intends_action": intends_action, "summary": ""},
        "self_revision": {"intends_revision": intends_revision, "summary": ""},
    }
    if i_want_to_say is not None:
        payload["i_want_to_say"] = i_want_to_say
    if i_want_to_use_tool is not None:
        payload["i_want_to_use_tool"] = i_want_to_use_tool
    if tool_op is not None:
        payload["tool_op"] = tool_op
    if tool_params is not None:
        payload["tool_params"] = tool_params
    return payload
