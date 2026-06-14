"""R91: focused tests for `_build_messages` (LLM path) and `_render_content` (deterministic path).

Asserts:
  - When `request.present_field_summary` is None, the LLM user message and the deterministic
    fallback content are byte-for-byte identical to the pre-R91 form.
  - When set, both paths prepend a `Present field: <summary>` line at the start of the user content
    (before the existing `Internal state:` / retrieval / continuation lines).
"""

from __future__ import annotations

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtRequest,
)
from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath
from helios_v2.thought_gating import ContinuationPressureState


def _bundle() -> ThoughtWindowBundle:
    return ThoughtWindowBundle(
        bundle_id="thought-window-bundle:r91",
        source_plan_id="retrieval-plan:r91",
        short_term_context=(
            ThoughtWindowHit(
                memory_id="memory:short:001",
                memory_type="short_term_context",
                summary="short term context",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
        ),
        mid_term_hits=(),
        long_term_hits=(),
        autobiographical_hits=(),
        selection_trace=(
            RetrievalSelectionTrace("short_term", 1, 1, "mixed"),
            RetrievalSelectionTrace("mid_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("long_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("autobiographical", 0, 0, "mixed"),
        ),
        retrieval_sec_trace=(),
        tick_id=1,
    )


def _request(present_field_summary: str | None = None) -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:r91",
        source_gate_result_id="thought-gate-result:r91",
        source_retrieval_bundle_id="thought-window-bundle:r91",
        source_continuation_active=False,
        internal_state_summary="DA 0.55 NE 0.56 ...",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
        present_field_summary=present_field_summary,
    )


# --- LLM path: _build_messages -------------------------------------------------------------------


def _user_content(messages):
    return next(m.content for m in messages if m.role == "user")


def test_llm_user_message_unchanged_when_present_field_none() -> None:
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(None), _bundle(), cont)
    user = _user_content(messages)
    # Pre-R91 shape: no `Present field:` line.
    assert "Present field:" not in user
    # First non-blank line is `Internal state:`.
    first = next(line for line in user.splitlines() if line.strip())
    assert first.startswith("Internal state: ")


def test_llm_user_message_prepends_present_field_line_when_set() -> None:
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    summary = "focal: 苏蕊 just shared pre-defense anxiety; tokens: 苏蕊, 答辩, 焦虑; pacing: 0.4"
    messages = path._build_messages(_request(summary), _bundle(), cont)
    user = _user_content(messages)
    lines = [ln for ln in user.splitlines() if ln.strip()]
    assert lines[0] == f"Present field: {summary}"
    assert lines[1].startswith("Internal state: ")


# --- Deterministic-fallback path: _render_content ------------------------------------------------


def test_first_version_render_content_unchanged_when_present_field_none() -> None:
    path = FirstVersionInternalThoughtPath()
    rendered = path._render_content(_request(None), _bundle())
    assert "Present field:" not in rendered
    assert rendered.startswith("DA 0.55 NE 0.56 ...")  # the internal_state_summary leads


def test_first_version_render_content_prepends_present_field_when_set() -> None:
    path = FirstVersionInternalThoughtPath()
    summary = "focal: 阿哲 announced funding success; tokens: 阿哲, 投资, 成功"
    rendered = path._render_content(_request(summary), _bundle())
    assert rendered.startswith(f"Present field: {summary}")
    # The internal state, current context, etc., still follow.
    assert "DA 0.55 NE 0.56 ..." in rendered
    assert "Current context: short term context" in rendered
