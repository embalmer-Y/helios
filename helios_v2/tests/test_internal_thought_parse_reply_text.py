"""R93: focused tests for `_parse_structured_thought` reading the top-level
`i_want_to_say` field into `StructuredThoughtEvidence.reply_text`.

Asserts: absent / null / empty / whitespace-only -> `""`; non-empty trimmed string preserved;
non-string raises `StructuredThoughtParseError`; over-cap input deterministically truncated with
the explicit suffix.
"""

from __future__ import annotations

import json

import pytest

from helios_v2.internal_thought.contracts import (
    REPLY_TEXT_MAX_CHARS,
    REPLY_TEXT_TRUNCATION_SUFFIX,
)
from helios_v2.internal_thought.engine import (
    StructuredThoughtParseError,
    _parse_structured_thought,
)


def _envelope(**overrides) -> str:
    """Build a minimal valid structured-thought envelope JSON string for tests."""
    payload = dict(
        thought="a thought",
        sufficiency=0.9,
        wants_to_continue=False,
        continue_reason="",
        proposed_action={"intends_action": False, "summary": ""},
        self_revision={"intends_revision": False, "summary": ""},
    )
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Honest absence: field absent / null / empty / whitespace-only -> ""
# ---------------------------------------------------------------------------


def test_field_absent_yields_empty_reply_text() -> None:
    ev = _parse_structured_thought(_envelope())
    assert ev.reply_text is None


def test_field_null_yields_empty_reply_text() -> None:
    ev = _parse_structured_thought(_envelope(reply_text=None))
    assert ev.reply_text is None


def test_field_empty_string_yields_empty_reply_text() -> None:
    ev = _parse_structured_thought(_envelope(reply_text=""))
    assert ev.reply_text is None


def test_field_whitespace_only_yields_empty_reply_text() -> None:
    ev = _parse_structured_thought(_envelope(reply_text="   \t  \n  "))
    assert ev.reply_text is None


# ---------------------------------------------------------------------------
# Non-empty: trimmed and preserved
# ---------------------------------------------------------------------------


def test_field_non_empty_string_preserved_after_strip() -> None:
    ev = _parse_structured_thought(
        _envelope(reply_text="  小林，听到这些，心里一下子沉了一下。  ")
    )
    assert ev.reply_text == "小林，听到这些，心里一下子沉了一下。"


def test_field_short_chinese_paragraph_preserved_verbatim() -> None:
    text = "苏蕊，谢谢你愿意来找我聊聊。后天就要答辩了。"
    ev = _parse_structured_thought(_envelope(reply_text=text))
    assert ev.reply_text == text


# ---------------------------------------------------------------------------
# Length cap: deterministic truncation with explicit suffix
# ---------------------------------------------------------------------------


def test_field_over_cap_is_deterministically_truncated() -> None:
    big = "a" * (REPLY_TEXT_MAX_CHARS + 200)
    ev = _parse_structured_thought(_envelope(reply_text=big))
    assert len(ev.reply_text) == REPLY_TEXT_MAX_CHARS
    assert ev.reply_text.endswith(REPLY_TEXT_TRUNCATION_SUFFIX)
    # Deterministic: same input -> same output.
    ev2 = _parse_structured_thought(_envelope(reply_text=big))
    assert ev2.reply_text == ev.reply_text


def test_field_at_exact_cap_is_preserved_unchanged() -> None:
    exact = "x" * REPLY_TEXT_MAX_CHARS
    ev = _parse_structured_thought(_envelope(reply_text=exact))
    assert ev.reply_text == exact
    assert REPLY_TEXT_TRUNCATION_SUFFIX not in ev.reply_text


# ---------------------------------------------------------------------------
# Non-string -> raise (fail-fast, no silent coercion)
# ---------------------------------------------------------------------------


def test_field_as_number_raises() -> None:
    with pytest.raises(StructuredThoughtParseError):
        _parse_structured_thought(_envelope(reply_text=42))


def test_field_as_object_raises() -> None:
    with pytest.raises(StructuredThoughtParseError):
        _parse_structured_thought(_envelope(reply_text={"text": "hi"}))


def test_field_as_list_raises() -> None:
    with pytest.raises(StructuredThoughtParseError):
        _parse_structured_thought(_envelope(reply_text=["hi", "there"]))


def test_field_as_bool_raises() -> None:
    with pytest.raises(StructuredThoughtParseError):
        _parse_structured_thought(_envelope(reply_text=True))


# ---------------------------------------------------------------------------
# Backward compatibility: legacy envelope that omits the field still parses
# ---------------------------------------------------------------------------


def test_legacy_envelope_without_i_want_to_say_still_parses() -> None:
    """A pre-R93 envelope (just the legacy fields) must continue to parse and produce an
    evidence whose `reply_text` defaults to '' — so existing R85/R91 tests pass."""
    legacy = json.dumps(
        {
            "thought": "legacy narration",
            "sufficiency": 0.85,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": True, "summary": "legacy action"},
            "self_revision": {"intends_revision": False, "summary": ""},
        }
    )
    ev = _parse_structured_thought(legacy)
    assert ev.thought_text == "legacy narration"
    assert ev.intends_action is True
    assert ev.reply_text is None
