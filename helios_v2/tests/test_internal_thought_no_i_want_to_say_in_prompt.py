"""R94: structural regression guard — the legacy `i_want_to_say` field is gone.

Owner: internal thought loop.

The R93 Phase 1 field `i_want_to_say` is structurally biased: the verb "say" in
the field name primes the model to fill it, even when its primary action class
is `no_action` or `tool`. R94 removes the field entirely; reply text now lives
on `reply_text` and is read only when `action_intent="reply"`. This test
enforces the absence of the legacy field in three layers:

1. **System prompt**: drive `LlmBackedInternalThoughtPath._build_messages`
   on a sample request and assert the system + user message contents do not
   contain the literal `i_want_to_say`. The model cannot see a field that
   does not exist in the prompt.
2. **Parser surface**: assert `_parse_structured_thought` does not read
   the `i_want_to_say` payload key. Even if a model checkpoint still produces
   the field, the parser silently ignores it (forward-compat); the test
   enforces that the parser does not promote the legacy value to a reply
   proposal.
3. **Test fixture surface**: assert the shared `_internal_thought_test_fixtures.envelope`
   helper does not accept a `i_want_to_say` kwarg. Test code cannot
   accidentally drive the legacy path.

A future R that reintroduces the `i_want_to_say` field is caught at test
time, before the regression reaches a real-LLM evaluation.
"""

from __future__ import annotations

import inspect
import json
from types import MappingProxyType

import pytest

from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.internal_thought.engine import (
    LlmBackedInternalThoughtPath,
    _parse_structured_thought,
)


# ---------------------------------------------------------------------------
# Layer 1: system prompt does not contain the legacy field
# ---------------------------------------------------------------------------


def _build_sample_messages() -> tuple:
    """Build a sample request and exercise the path's `_build_messages`."""
    from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle
    from helios_v2.thought_gating import ContinuationPressureState

    bundle = ThoughtWindowBundle(
        bundle_id="bundle:r94:structural",
        source_plan_id="plan:r94:structural",
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
    request = InternalThoughtRequest(
        request_id="internal-thought-request:r94:structural",
        source_gate_result_id="gate-result:r94:structural",
        source_retrieval_bundle_id="bundle:r94:structural",
        source_continuation_active=False,
        internal_state_summary="current internal state",
        prompt_contract_summary=MappingProxyType(
            {
                "mode": "internal_thought",
                "voice": "structured",
                "ready_channels": ("cli",),
                "current_operator_id": "operator:r94",
            }
        ),
        tick_id=1,
    )
    path = LlmBackedInternalThoughtPath(
        gateway=None,  # type: ignore[arg-type]
        profile_name="test-profile",
    )
    return path._build_messages(request, bundle, ContinuationPressureState.inactive())


def test_system_prompt_does_not_contain_legacy_field_literal() -> None:
    """The system message must not contain the literal `i_want_to_say` string.

    A future R that reintroduces the field is caught here before the
    regression reaches a real-LLM evaluation.
    """
    messages = _build_sample_messages()
    system_message = messages[0]
    assert system_message.role == "system"
    assert "i_want_to_say" not in system_message.content, (
        "R94 removed the legacy `i_want_to_say` field. The system prompt must not "
        "reference it. The reply text is now declared on `reply_text` (a sub-detail "
        "of `action_intent=\"reply\"`)."
    )


def test_user_prompt_does_not_contain_legacy_field_literal() -> None:
    """The user message must not contain the literal `i_want_to_say` string either.

    The user message renders the internal state + retrieval + present field;
    the legacy field name should not appear in any layer.
    """
    messages = _build_sample_messages()
    user_message = messages[1]
    assert user_message.role == "user"
    assert "i_want_to_say" not in user_message.content, (
        "R94 removed the legacy `i_want_to_say` field. The user message must not "
        "reference it."
    )


# ---------------------------------------------------------------------------
# Layer 2: parser does not promote the legacy field
# ---------------------------------------------------------------------------


def test_parser_does_not_promote_legacy_field_to_reply_text() -> None:
    """An envelope with only `i_want_to_say` (legacy) yields `reply_text is None`.

    The parser silently ignores the `i_want_to_say` payload key. The model's
    legacy `i_want_to_say` value is NOT promoted to `reply_text` (R94 has no
    compat path); the model is expected to start producing `reply_text` once
    it has the R94 prompt.
    """
    payload = {
        "thought": "a thought",
        "sufficiency": 0.9,
        "wants_to_continue": False,
        "continue_reason": "",
        "proposed_action": {"intends_action": False, "summary": ""},
        "self_revision": {"intends_revision": False, "summary": ""},
        # R93 P1 legacy field, R94 silently ignored:
        "i_want_to_say": "operator-addressed reply",
    }
    evidence = _parse_structured_thought(json.dumps(payload, ensure_ascii=False))
    assert evidence.reply_text is None, (
        "R94: the legacy `i_want_to_say` payload key must not be promoted to "
        "`reply_text`. The model must use `action_intent + reply_text` to "
        "declare a reply; the legacy field is silently ignored."
    )


# ---------------------------------------------------------------------------
# Layer 3: test fixture surface
# ---------------------------------------------------------------------------


def test_envelope_fixture_does_not_accept_legacy_kwarg() -> None:
    """The shared `envelope()` helper must not accept `i_want_to_say` as a kwarg.

    Test code cannot accidentally drive the legacy compat path. The R94
    explicit-reply path requires `action_intent="reply" + reply_text` to
    construct a reply proposal; `i_want_to_say` is not expressible via the
    fixture.
    """
    from _internal_thought_test_fixtures import envelope

    sig = inspect.signature(envelope)
    assert "i_want_to_say" not in sig.parameters, (
        "R94: the shared `envelope()` helper must not accept `i_want_to_say` "
        "as a kwarg. The R93 P1 field is retired; reply text is now declared "
        "via the `reply_text` kwarg (paired with `action_intent=\"reply\"`)."
    )
    assert "reply_text" in sig.parameters, (
        "R94: the `envelope()` helper must accept `reply_text` as a kwarg "
        "(the R94 replacement for `i_want_to_say`)."
    )
