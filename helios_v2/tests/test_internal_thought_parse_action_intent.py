# -*- coding: utf-8 -*-
"""R93 Phase 2: parser tests for the additive `action_intent` and `target_user_id` envelope fields.

Owner: internal thought loop.

These tests exercise the two new parser helpers (`_optional_action_intent` and
`_optional_target_user_id`) added in R93 Phase 2. They are pure parse + bound tests; the
emit_proposal precedence tests in `test_internal_thought_emit_proposal_phase2.py` cover
the integrated end-to-end behavior.

Failure semantics covered:

- Field absent / null -> None (compat path preserved).
- Field present and a recognized string -> the string verbatim.
- Field present but non-string or out-of-taxonomy -> StructuredThoughtParseError.
- Field present and over the owner-defined length cap -> deterministic truncation.
"""

import pytest

from helios_v2.internal_thought.engine import (
    StructuredThoughtParseError,
    _optional_action_intent,
    _optional_target_user_id,
)


# ---------------------------------------------------------------------------
# _optional_action_intent
# ---------------------------------------------------------------------------


def test_action_intent_absent_returns_none() -> None:
    """Field absent from the envelope: return None (compat path)."""

    assert _optional_action_intent({}) is None


def test_action_intent_explicit_null_returns_none() -> None:
    """Field present as JSON null: return None (compat path)."""

    assert _optional_action_intent({"action_intent": None}) is None


def test_action_intent_reply_accepted() -> None:
    """Field present with the recognized "reply" value: returned verbatim."""

    assert _optional_action_intent({"action_intent": "reply"}) == "reply"


def test_action_intent_tool_accepted() -> None:
    """Field present with the recognized "tool" value: returned verbatim."""

    assert _optional_action_intent({"action_intent": "tool"}) == "tool"


def test_action_intent_no_action_accepted() -> None:
    """Field present with the recognized "no_action" value: returned verbatim.

    R93 Phase 2 contract: "no_action" is distinct from None. None is the compat
    path; "no_action" is the explicit close-internal-only signal and overrides
    every other reply/tool signal in the emit_proposal precedence.
    """

    assert _optional_action_intent({"action_intent": "no_action"}) == "no_action"


def test_action_intent_unknown_string_raises_parse_error() -> None:
    """Field present with an unrecognized string: fail-fast (no silent coercion)."""

    with pytest.raises(StructuredThoughtParseError):
        _optional_action_intent({"action_intent": "shutdown"})


def test_action_intent_non_string_raises_parse_error() -> None:
    """Field present with a non-string value: fail-fast (no silent coercion)."""

    with pytest.raises(StructuredThoughtParseError):
        _optional_action_intent({"action_intent": 42})


# ---------------------------------------------------------------------------
# _optional_target_user_id
# ---------------------------------------------------------------------------


def test_target_user_id_absent_returns_none() -> None:
    """Field absent from the envelope: return None (owner falls back to operator)."""

    assert _optional_target_user_id({}) is None


def test_target_user_id_explicit_null_returns_none() -> None:
    """Field present as JSON null: return None."""

    assert _optional_target_user_id({"target_user_id": None}) is None


def test_target_user_id_string_returned_verbatim() -> None:
    """Field present with a normal string: returned verbatim (whitespace-stripped)."""

    assert _optional_target_user_id({"target_user_id": "user:001"}) == "user:001"


def test_target_user_id_whitespace_only_normalized_to_none() -> None:
    """Field present but whitespace-only: normalized to None (honest absence)."""

    assert _optional_target_user_id({"target_user_id": "   "}) is None


def test_target_user_id_stripped() -> None:
    """Field present with surrounding whitespace: stripped."""

    assert _optional_target_user_id({"target_user_id": "  user:001  "}) == "user:001"


def test_target_user_id_non_string_raises_parse_error() -> None:
    """Field present with a non-string value: fail-fast (no silent coercion)."""

    with pytest.raises(StructuredThoughtParseError):
        _optional_target_user_id({"target_user_id": 42})


def test_target_user_id_over_cap_truncates() -> None:
    """Field over `TARGET_USER_ID_MAX_CHARS`: deterministic truncation with explicit suffix."""

    long_id = "x" * 1000
    result = _optional_target_user_id({"target_user_id": long_id})
    assert result is not None
    assert result.endswith("…(truncated)")
    # Truncated length must equal the cap (256 chars).
    assert len(result) == 256


def test_target_user_id_exactly_at_cap_not_truncated() -> None:
    """Field exactly at the cap: no truncation (the cap is inclusive)."""

    from helios_v2.internal_thought.contracts import TARGET_USER_ID_MAX_CHARS

    at_cap = "y" * TARGET_USER_ID_MAX_CHARS
    result = _optional_target_user_id({"target_user_id": at_cap})
    assert result == at_cap


# ---------------------------------------------------------------------------
# End-to-end: parse through _parse_structured_thought
# ---------------------------------------------------------------------------


def test_parse_full_envelope_threads_both_fields() -> None:
    """A complete envelope with both new fields carries them into the evidence."""

    from helios_v2.internal_thought.engine import _parse_structured_thought

    import json

    envelope = {
        "thought": "model thought",
        "sufficiency": 0.9,
        "wants_to_continue": False,
        "proposed_action": {"intends_action": False, "summary": ""},
        "self_revision": {"intends_revision": False, "summary": ""},
        "i_want_to_say": "operator-addressed reply",
        "action_intent": "reply",
        "target_user_id": "user:001",
    }
    evidence = _parse_structured_thought(json.dumps(envelope))
    assert evidence.action_intent == "reply"
    assert evidence.target_user_id == "user:001"
    assert evidence.intended_reply_text == "operator-addressed reply"


def test_parse_minimal_envelope_has_none_values() -> None:
    """A minimal envelope (no new fields): `action_intent` and `target_user_id` are None."""

    from helios_v2.internal_thought.engine import _parse_structured_thought

    import json

    envelope = {
        "thought": "model thought",
        "sufficiency": 0.9,
        "wants_to_continue": False,
        "proposed_action": {"intends_action": False, "summary": ""},
        "self_revision": {"intends_revision": False, "summary": ""},
    }
    evidence = _parse_structured_thought(json.dumps(envelope))
    assert evidence.action_intent is None
    assert evidence.target_user_id is None
