"""R94: focused tests for the system-prompt schema/transport clause that tells the model
`action_intent="reply" + reply_text` is transported as a `reply_message` to the resolved
`target_user_id` through the connected driver serving that user.

Asserts:
  - The system prompt now lists `action_intent` (R94, REQUIRED) and `reply_text` (R94,
    when action_intent=reply) as schema entries — NOT the legacy R93 P1 `i_want_to_say`
    field.
  - The system prompt contains the explicit transport clause explaining that setting
    `action_intent="reply"` AND `reply_text` will send that text as a `reply_message` to
    the resolved `target_user_id` through the connected driver.
  - The user-message shape is unchanged for the legacy path (no present field) — i.e. the
    new system-prompt text does not perturb the user message.
  - The user message remains unchanged when a present-field summary is provided (R91 still
    prepends; the system-prompt clause is additive).

R94 evolution: this file replaces the R93 P1 `test_internal_thought_build_messages_
reply_clause.py` (which tested the legacy `i_want_to_say` schema line and the legacy
`cli` transport clause). The legacy field name is removed from the schema; the transport
clause is rewritten to be `action_intent + reply_text + target_user_id` led.
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
        request_id="internal-thought-request:r94:prompt",
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


def _build_messages(*, present_field: str | None = None) -> Any:
    path = LlmBackedInternalThoughtPath(
        gateway=None,  # type: ignore[arg-type]
        profile_name="test-profile",
    )
    return path._build_messages(_request(present_field=present_field), _bundle(), _continuation())


# ---------------------------------------------------------------------------
# System-prompt schema entry: R94 leads with action_intent + reply_text
# ---------------------------------------------------------------------------


def test_system_prompt_lists_action_intent_as_schema_entry() -> None:
    """R94: `action_intent` is the primary action-class schema entry (REQUIRED)."""
    system_text = _build_messages()[0].content
    assert '"action_intent"' in system_text
    # The schema line tells the model the action_intent is required.
    assert "REQUIRED" in system_text or "reply" in system_text


def test_system_prompt_lists_reply_text_as_schema_entry() -> None:
    """R94: `reply_text` is the sub-detail schema entry for the reply action class."""
    system_text = _build_messages()[0].content
    assert '"reply_text"' in system_text


def test_system_prompt_does_not_mention_legacy_field_name() -> None:
    """R94: the legacy `i_want_to_say` field name is REMOVED from the schema line.

    The structural test (`test_internal_thought_no_i_want_to_say_in_prompt.py`) is the
    strict version of this check; this is the friendlier assertion for the
    build-messages test.
    """
    system_text = _build_messages()[0].content
    assert "i_want_to_say" not in system_text


def test_system_prompt_contains_transport_clause() -> None:
    """The transport clause is rewritten: action_intent + reply_text + target_user_id."""
    system_text = _build_messages()[0].content
    # The transport clause: tells the model that action_intent=reply + reply_text
    # actually sends a reply_message.
    assert "reply_message" in system_text
    assert "action_intent" in system_text
    assert "reply_text" in system_text
    assert "target_user_id" in system_text
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
    user_text = _build_messages(present_field="cli said: \"hi\"")[1].content
    assert user_text.startswith("Present field: cli said: \"hi\"")
    assert "Internal state: state" in user_text
