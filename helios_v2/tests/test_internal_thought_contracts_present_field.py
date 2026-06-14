"""R91: focused tests for the additive `present_field_summary` field on `InternalThoughtRequest`.

Asserts: default-None preserves prior behavior; non-blank rule rejects blank/whitespace; values up
to the cap pass through verbatim; over-cap values are deterministically truncated with the documented
suffix; the rest of the contract is byte-for-byte unchanged.
"""

from __future__ import annotations

import pytest

from helios_v2.internal_thought import (
    InternalThoughtError,
    InternalThoughtRequest,
)
from helios_v2.internal_thought.contracts import (
    PRESENT_FIELD_SUMMARY_MAX_CHARS,
    PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX,
)


def _kwargs(**overrides):
    base = dict(
        request_id="internal-thought-request:r91",
        source_gate_result_id="thought-gate-result:r91",
        source_retrieval_bundle_id="thought-window-bundle:r91",
        source_continuation_active=False,
        internal_state_summary="DA 0.55 NE 0.56 ...",
        prompt_contract_summary={"mode": "internal_thought"},
        tick_id=42,
    )
    base.update(overrides)
    return base


def test_default_is_none_and_preserves_pre_r91_shape() -> None:
    req = InternalThoughtRequest(**_kwargs())
    assert req.present_field_summary is None
    # The rest of the contract is byte-for-byte unchanged.
    assert req.internal_state_summary == "DA 0.55 NE 0.56 ..."


def test_non_none_value_is_accepted_verbatim_when_within_cap() -> None:
    summary = "focal: 苏蕊 just shared pre-defense anxiety; tokens: 苏蕊, 答辩, 焦虑; pacing: 0.4"
    req = InternalThoughtRequest(**_kwargs(present_field_summary=summary))
    assert req.present_field_summary == summary
    assert len(req.present_field_summary) <= PRESENT_FIELD_SUMMARY_MAX_CHARS


def test_blank_or_whitespace_value_raises() -> None:
    with pytest.raises(InternalThoughtError):
        InternalThoughtRequest(**_kwargs(present_field_summary=""))
    with pytest.raises(InternalThoughtError):
        InternalThoughtRequest(**_kwargs(present_field_summary="   \t  "))


def test_over_cap_value_is_deterministically_truncated_with_suffix() -> None:
    big = "a" * (PRESENT_FIELD_SUMMARY_MAX_CHARS + 200)
    req = InternalThoughtRequest(**_kwargs(present_field_summary=big))
    assert len(req.present_field_summary) == PRESENT_FIELD_SUMMARY_MAX_CHARS
    assert req.present_field_summary.endswith(PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX)
    # Deterministic: same input -> same output.
    req2 = InternalThoughtRequest(**_kwargs(present_field_summary=big))
    assert req2.present_field_summary == req.present_field_summary


def test_value_at_exact_cap_is_preserved_unchanged() -> None:
    # Edge case: value exactly equal to the cap must NOT be truncated.
    exact = "x" * PRESENT_FIELD_SUMMARY_MAX_CHARS
    req = InternalThoughtRequest(**_kwargs(present_field_summary=exact))
    assert req.present_field_summary == exact
    assert PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX not in req.present_field_summary
