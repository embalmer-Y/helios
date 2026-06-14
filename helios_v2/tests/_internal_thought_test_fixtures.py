"""Shared fixture helpers reused by the R95 tests.

Mirrors the proven helpers in `test_internal_thought_engine.py` so the R95 tests do not
duplicate non-trivial gate-result / retrieval-bundle / config / structured-path construction.
This module name does NOT start with `test_`, so pytest does not collect it as a test module.

R95 evolution: the `envelope()` helper is reduced to the 5 R95 envelope fields
(`thought`, `sufficiency`, `tool_op`, `tool_params`, `thinking_complete`, plus the
R81 `hormone_response_i_predict` and the new R95 `channel_request`). The 11
R93-R94 behavior-suggestive fields (`reply_text`, `i_want_to_use_tool`,
`wants_to_continue`, `continue_reason`, `proposed_action`, `self_revision`,
`action_intent`, `target_user_id`, plus 3 companion sub-fields) are REMOVED.
Call sites that previously drove the R93 compat path / R94 explicit-reply
path are updated to use the R95 `tool_op` + `tool_params` single-point
decision.
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
    tool_op: Any = None,
    tool_params: Any = None,
    thinking_complete: bool = True,
    channel_request: Any = None,
    hormone_response_i_predict: Any = None,
) -> dict:
    """Build a R95 structured thought envelope.

    The R95 envelope has 5 user-facing fields: `thought`, `sufficiency`,
    `tool_op`, `tool_params`, `thinking_complete`, plus the R81
    `hormone_response_i_predict` and the new R95 `channel_request`.

    `None` is a sentinel for "omit from payload" (the caller wants to
    exercise the absent-field path); a string value emits the field.
    The R95 `tool_op` is the single primary action-class field: empty
    / missing means "no action"; non-empty means "the model picked this
    op" and the LLM is free to include `target_user_id` (or anything
    else) inside `tool_params`.
    """
    payload: dict[str, Any] = {
        "thought": thought,
        "sufficiency": sufficiency,
        "thinking_complete": thinking_complete,
    }
    if tool_op is not None:
        payload["tool_op"] = tool_op
    if tool_params is not None:
        payload["tool_params"] = tool_params
    if channel_request is not None:
        payload["channel_request"] = channel_request
    if hormone_response_i_predict is not None:
        payload["hormone_response_i_predict"] = hormone_response_i_predict
    return payload
