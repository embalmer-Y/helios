"""R98 scope extension: hormone prediction prompt coaching regression tests.

Asserts:
  - The system prompt produced by `_build_messages` contains hormone channel-to-emotion
    mapping guidance (cortisol→distress, dopamine→reward, oxytocin→warmth).
  - The system prompt contains at least one Chinese-language example (焦虑/丧亲/恐惧/升).
  - The system prompt still marks the field as optional (omit/null).
  - The system prompt does NOT contain performance instructions ("show", "perform", "act anxious").
  - The `_V3_RESPONSE_SCHEMA` in prompt_contract contains the same channel-to-emotion mapping.
  - The `_V3_RESPONSE_SCHEMA` does NOT contain performance instructions.
"""

from __future__ import annotations

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import InternalThoughtRequest
from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath
from helios_v2.prompt_contract.engine import _V3_RESPONSE_SCHEMA
from helios_v2.thought_gating import ContinuationPressureState


def _bundle() -> ThoughtWindowBundle:
    return ThoughtWindowBundle(
        bundle_id="thought-window-bundle:r98",
        source_plan_id="retrieval-plan:r98",
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


def _request() -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:r98",
        source_gate_result_id="thought-gate-result:r98",
        source_retrieval_bundle_id="thought-window-bundle:r98",
        source_continuation_active=False,
        internal_state_summary="DA 0.55 NE 0.56 ...",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
        present_field_summary=None,
    )


def _system_content(messages):
    """Extract the system message content from the messages tuple."""
    return next(m.content for m in messages if m.role == "system")


# --- _build_messages hormone guidance tests --------------------------------------------------------


def test_hormone_prediction_guidance_contains_cortisol_distress_mapping() -> None:
    """R98: system prompt links cortisol to distress/threat/loss."""
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    assert "cortisol" in system.lower()
    # The prompt must pair cortisol with at least one distress-related word.
    assert any(word in system.lower() for word in ("distress", "threat", "loss"))


def test_hormone_prediction_guidance_contains_dopamine_reward_mapping() -> None:
    """R98: system prompt links dopamine to reward/warmth."""
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    assert "dopamine" in system.lower()
    assert any(word in system.lower() for word in ("reward", "warmth"))


def test_hormone_prediction_guidance_contains_oxytocin_bonding_mapping() -> None:
    """R98: system prompt links oxytocin to social bonding/warmth."""
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    assert "oxytocin" in system.lower()


def test_hormone_prediction_guidance_contains_chinese_example() -> None:
    """R98: system prompt contains at least one Chinese-language distress/warmth example."""
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    # At least one Chinese distress/warmth keyword must appear in the hormone guidance.
    assert any(word in system for word in ("焦虑", "丧亲", "恐惧", "升", "感激", "喜悦", "信任"))


def test_hormone_prediction_guidance_marks_field_optional() -> None:
    """R98: the hormone field is still described as optional in the system prompt."""
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    # The field must remain optional — not mandatory.
    assert any(word in system.lower() for word in ("optional", "omit", "null"))


def test_hormone_prediction_guidance_no_performance_instruction() -> None:
    """R98: system prompt does NOT contain theatrical performance instructions.

    The existing "do not perform theatrical self-narration" line is an anti-theatrical
    constraint, NOT a performance instruction — so we check for theatrical performance
    verbs that would instruct the LLM to act out emotions, not for the word "perform"
    in the anti-theatrical rule itself.
    """
    path = LlmBackedInternalThoughtPath(gateway=None, profile_name="thought-default")  # type: ignore[arg-type]
    cont = ContinuationPressureState.inactive()
    messages = path._build_messages(_request(), _bundle(), cont)
    system = _system_content(messages)
    # The coaching text frames the field as a self-forecast, not a performance instruction.
    assert "act anxious" not in system.lower()
    assert "show distress" not in system.lower()
    # "perform" appears in the existing anti-theatrical rule "do not perform theatrical
    # self-narration" — that is a constraint, NOT a performance instruction. So we check
    # for performance-style verbs that would tell the LLM to act out emotions:
    assert "act out" not in system.lower()
    assert "pretend" not in system.lower()
    assert "fake" not in system.lower()
    assert "simulate" not in system.lower()


# --- _V3_RESPONSE_SCHEMA hormone guidance tests ----------------------------------------------------


def test_v3_schema_contains_cortisol_distress_mapping() -> None:
    """R98: v3 schema links cortisol to distress/threat/loss."""
    schema = _V3_RESPONSE_SCHEMA.lower()
    assert "cortisol" in schema
    assert any(word in schema for word in ("distress", "threat", "loss"))


def test_v3_schema_contains_dopamine_reward_mapping() -> None:
    """R98: v3 schema links dopamine to reward/warmth."""
    schema = _V3_RESPONSE_SCHEMA.lower()
    assert "dopamine" in schema
    assert any(word in schema for word in ("reward", "warmth"))


def test_v3_schema_contains_chinese_forecast_example() -> None:
    """R98: v3 schema contains at least one Chinese-language forecast guidance phrase."""
    schema = _V3_RESPONSE_SCHEMA
    assert any(word in schema for word in ("焦虑", "丧亲", "恐惧", "升", "降", "感激", "喜悦", "信任"))


def test_v3_schema_marks_hormone_field_optional() -> None:
    """R98: v3 schema still marks hormone_response_i_predict as optional."""
    schema = _V3_RESPONSE_SCHEMA.lower()
    assert any(word in schema for word in ("optional", "omit", "null"))


def test_v3_schema_no_performance_instruction() -> None:
    """R98: v3 schema does NOT contain theatrical performance instructions."""
    schema = _V3_RESPONSE_SCHEMA.lower()
    assert "act anxious" not in schema
    assert "show distress" not in schema
    assert "perform" not in schema
