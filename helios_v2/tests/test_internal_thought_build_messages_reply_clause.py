"""R93: focused tests for the system-prompt schema/transport clause that tells the model
`i_want_to_say` is transported as a `reply_message` to the current operator through the
`cli` user-visible channel.

Asserts:
  - The system prompt now lists `i_want_to_say` as a schema entry (not buried in prose).
  - The system prompt contains the explicit transport clause explaining that filling the
    field will send that text as a `reply_message` to the current operator through `cli`.
  - The user-message shape is unchanged for the legacy path (no present field) — i.e. the
    new system-prompt text does not perturb the user message.
  - The user message remains unchanged when a present-field summary is provided (R91 still
    prepends; the system-prompt clause is additive).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle
from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath
from helios_v2.thought_gating import ContinuationPressureState


def _bundle() -> ThoughtWindowBundle:
    return ThoughtWindowBundle(
        bundle_id="bundle:1",
        source_plan_id="plan:1",
        short_term_context=(),
        mid_term_hits=(),
        long_term_hits=(),
        autobiographical_hits=(),
        selection_trace=(
            RetrievalSelectionTrace("short_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("mid_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("long_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("autobiographical", 0, 0, "mixed"),
        ),
        retrieval_sec_trace=(),
        tick_id=1,
    )


def _request(*, present_field: str | None = None) -> Any:
    from helios_v2.internal_thought import InternalThoughtRequest

    return InternalThoughtRequest(
        request_id="internal-thought-request:r93:prompt",
        source_gate_result_id="gate-result:1",
        source_retrieval_bundle_id="bundle:1",
        source_continuation_active=False,
        internal_state_summary="state",
        prompt_contract_summary=MappingProxyType(
            {
                "mode": "internal_thought",
                "voice": "structured",
                "ready_channels": ("cli",),
                "current_operator_id": "cli",
            }
        ),
        tick_id=1,
        present_field_summary=present_field,
    )


def _continuation() -> ContinuationPressureState:
    return ContinuationPressureState.inactive()


def _build_messages(*, present_field: str | None = None) -> tuple:
    """Call the owner-private `_build_messages` directly (the system-prompt projection is
    owned here, not in `run`, so a direct call is the cleanest test seam)."""
    path = LlmBackedInternalThoughtPath(
        gateway=None,  # type: ignore[arg-type]
        profile_name="test-profile",
    )
    return path._build_messages(_request(present_field=present_field), _bundle(), _continuation())


# ---------------------------------------------------------------------------
# System-prompt schema entry exists for i_want_to_say
# ---------------------------------------------------------------------------


def test_system_prompt_lists_i_want_to_say_as_schema_entry() -> None:
    system_text = _build_messages()[0].content
    # Schema line: `"i_want_to_say": "<optional words to say outward as a reply to the current operator>"`
    assert '"i_want_to_say"' in system_text
    assert "reply to the current operator" in system_text


def test_system_prompt_contains_transport_clause() -> None:
    system_text = _build_messages()[0].content
    # The transport clause: tells the model that filling i_want_to_say actually sends a reply.
    assert "reply_message" in system_text
    assert "current operator" in system_text
    assert "'cli'" in system_text
    # Tells the model that i_want_to_use_tool is for non-reply effectors only.
    assert "i_want_to_use_tool" in system_text


# ---------------------------------------------------------------------------
# User message unchanged: legacy path (no present field)
# ---------------------------------------------------------------------------


def test_user_message_unchanged_for_legacy_path() -> None:
    """When `present_field_summary` is None the user message should look like the pre-R93
    form: `Internal state: ...` then the continuation-pressure line."""
    user_text = _build_messages(present_field=None)[1].content
    assert user_text.startswith("Internal state: state")
    assert "Continuation pressure is inactive for this cycle." in user_text


# ---------------------------------------------------------------------------
# User message unchanged when present-field is set (R91 still prepends)
# ---------------------------------------------------------------------------


def test_user_message_with_present_field_still_prepends() -> None:
    """R91 present-field line is still the first line of the user message; the new system
    clause is additive and does not perturb the user-message shape."""
    user_text = _build_messages(present_field='cli via cli said: "hi"')[1].content
    assert user_text.startswith('Present field: cli via cli said: "hi"')
    assert "Internal state: state" in user_text