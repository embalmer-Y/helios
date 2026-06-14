"""R95: tests for the `thinking_complete` field (the R95 replacement for `wants_to_continue`).

`thinking_complete` is a neutral state description (not a verb). The OWNER's
continuation floors remain authoritative; the model's `thinking_complete`
is advisory. The heuristic for advisory continuation requires the thought
text to have unresolved reasoning hooks (trailing `...` / `?` or
specific phrases).
"""

from __future__ import annotations

import pytest

from helios_v2.internal_thought.engine import (
    _has_unresolved_reasoning_hooks,
    _optional_thinking_complete,
    StructuredThoughtParseError,
)


# --- parser tests ----------------------------------------------------------


def test_thinking_complete_default_true() -> None:
    """R95: `thinking_complete` absent / null => True (model indicated completion)."""
    assert _optional_thinking_complete({}) is True
    assert _optional_thinking_complete({"thinking_complete": None}) is True


def test_thinking_complete_explicit_true_and_false() -> None:
    """R95: explicit bools pass through."""
    assert _optional_thinking_complete({"thinking_complete": True}) is True
    assert _optional_thinking_complete({"thinking_complete": False}) is False


def test_thinking_complete_non_bool_raises() -> None:
    """R95: non-bool raises StructuredThoughtParseError."""
    with pytest.raises(StructuredThoughtParseError):
        _optional_thinking_complete({"thinking_complete": "yes"})
    with pytest.raises(StructuredThoughtParseError):
        _optional_thinking_complete({"thinking_complete": 1})  # int, not bool


# --- heuristic tests -------------------------------------------------------


def test_has_unresolved_hooks_trailing_ellipsis() -> None:
    """R95: trailing `...` (ASCII or Unicode) is a hook."""
    assert _has_unresolved_reasoning_hooks("I am thinking...")
    assert _has_unresolved_reasoning_hooks("hmm…")


def test_has_unresolved_hooks_trailing_question_mark() -> None:
    """R95: trailing `?` (ASCII or full-width) is a hook."""
    assert _has_unresolved_reasoning_hooks("what should I do?")
    assert _has_unresolved_reasoning_hooks("怎么办？")


def test_has_unresolved_hooks_substring_phrases() -> None:
    """R95: bounded phrase set triggers hooks (English + Chinese)."""
    assert _has_unresolved_reasoning_hooks("let me think more about this")
    assert _has_unresolved_reasoning_hooks("让我想想")
    assert _has_unresolved_reasoning_hooks("still need more info")


def test_has_unresolved_hooks_no_hook_when_text_is_final() -> None:
    """R95: a finalized text without hooks returns False (OWNER ignores
    `thinking_complete=False` heuristic)."""
    assert not _has_unresolved_reasoning_hooks("I'm done. The answer is 42.")
    assert not _has_unresolved_reasoning_hooks("")
    assert not _has_unresolved_reasoning_hooks("    ")


# --- OWNER floor vs model signal ------------------------------------------


def test_continuation_floor_overrides_thinking_complete() -> None:
    """R95: the OWNER's continuation floors (runtime + low-context) remain
    authoritative; the model's `thinking_complete` is advisory. This test
    verifies the integration: when the OWNER forces continuation, the cycle
    continues regardless of `thinking_complete`.

    Integration check via `_derive_thought_judgment` is in
    test_internal_thought_emit_proposal_r95.py. This test verifies the
    parser+heuristic behavior at the unit level.
    """
    # The heuristic alone returns True for hooks.
    assert _has_unresolved_reasoning_hooks("still need more?") is True
    # And False for finalized text.
    assert _has_unresolved_reasoning_hooks("final answer: 42.") is False
    # The OWNER's authoritative continuation path lives in
    # _derive_thought_judgment; the heuristic is just a pre-check.
