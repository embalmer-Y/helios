"""R93: focused tests for the additive `intended_reply_text` field on
`StructuredThoughtEvidence` and its bounded-length constants.

Asserts: default-empty preserves the pre-R93 shape; non-empty values pass through; the
length-cap and explicit truncation suffix constants are stable; the dataclass remains frozen.
"""

from __future__ import annotations

import pytest

from helios_v2.internal_thought.contracts import (
    INTENDED_REPLY_TEXT_MAX_CHARS,
    INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX,
)
from helios_v2.internal_thought.engine import StructuredThoughtEvidence


def _kwargs(**overrides) -> dict:
    """Build a minimal valid evidence kwargs dict for tests."""
    defaults = dict(
        thought_text="a thought",
        model_sufficiency=0.8,
        wants_to_continue=False,
        continue_reason="",
        intends_action=False,
        action_summary="",
        intends_self_revision=False,
        self_revision_summary="",
    )
    defaults.update(overrides)
    return defaults


def test_evidence_default_intended_reply_text_is_empty() -> None:
    ev = StructuredThoughtEvidence(**_kwargs())
    assert ev.intended_reply_text == ""


def test_evidence_accepts_explicit_intended_reply_text() -> None:
    ev = StructuredThoughtEvidence(**_kwargs(intended_reply_text="hello operator"))
    assert ev.intended_reply_text == "hello operator"


def test_evidence_remains_frozen_after_r93_field_added() -> None:
    ev = StructuredThoughtEvidence(**_kwargs(intended_reply_text="hi"))
    with pytest.raises(Exception):
        ev.intended_reply_text = "mutated"  # type: ignore[misc]


def test_intended_reply_text_constants_are_stable() -> None:
    """Cross-owner contract: composition / planner / future tests rely on the cap shape."""
    assert INTENDED_REPLY_TEXT_MAX_CHARS == 2000
    assert INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX == "…(truncated)"


def test_evidence_default_keeps_pre_r93_shape_byte_for_byte() -> None:
    """A pre-R93 caller that never sets `intended_reply_text` produces an evidence whose
    new field defaults to '' — so existing evidence-construction code paths in tests and
    fakes continue to work without modification."""
    ev = StructuredThoughtEvidence(**_kwargs())
    # Spot-check legacy fields are unchanged.
    assert ev.thought_text == "a thought"
    assert ev.model_sufficiency == 0.8
    assert ev.wants_to_continue is False
    assert ev.intends_action is False
    assert ev.intends_tool_use is False
    assert ev.tool_op == ""
    assert dict(ev.tool_params) == {}
    # And the new R93 field defaults to empty.
    assert ev.intended_reply_text == ""
