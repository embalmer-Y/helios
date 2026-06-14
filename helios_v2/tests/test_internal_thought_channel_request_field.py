"""R95: tests for the `channel_request` field (forward-compat gap-tracker carrier).

`channel_request` lets the LLM describe a channel/op it wishes existed
but doesn't. In R95 the OWNER does not act on it (no gap-tracker exists
yet); a future R96+ / P4 requirement will decide routing. The field
must be parsed, validated (non-object raises), and passed through
to the trace.
"""

from __future__ import annotations

import pytest

from helios_v2.internal_thought.engine import (
    _optional_channel_request,
    StructuredThoughtParseError,
)


def test_channel_request_absent_or_null_is_none() -> None:
    """R95: `channel_request` absent / null => None; no gap-tracker in R95."""
    assert _optional_channel_request({}) is None
    assert _optional_channel_request({"channel_request": None}) is None


def test_channel_request_object_is_carried() -> None:
    """R95: `channel_request` as an object is parsed and passed through."""
    raw = {
        "needed_capability": "send_qq_message",
        "would_use_when_available": {"op": "qq.send_message", "params": {"text": "hi"}},
    }
    parsed = _optional_channel_request({"channel_request": raw})
    assert parsed is not None
    assert parsed["needed_capability"] == "send_qq_message"
    assert parsed["would_use_when_available"]["op"] == "qq.send_message"


def test_channel_request_non_object_raises() -> None:
    """R95: non-object `channel_request` raises StructuredThoughtParseError."""
    with pytest.raises(StructuredThoughtParseError):
        _optional_channel_request({"channel_request": "qq.send"})
    with pytest.raises(StructuredThoughtParseError):
        _optional_channel_request({"channel_request": ["qq.send"]})
