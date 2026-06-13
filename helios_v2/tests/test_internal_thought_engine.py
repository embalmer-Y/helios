from __future__ import annotations

from dataclasses import dataclass

import pytest

from helios_v2.directed_retrieval import RetrievalSelectionTrace, ThoughtWindowBundle, ThoughtWindowHit
from helios_v2.internal_thought import (
    FirstVersionInternalThoughtPath,
    InternalThoughtConfig,
    InternalThoughtEngine,
    InternalThoughtError,
    InternalThoughtRequest,
    InternalThoughtTrace,
    SelfRevisionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
)
from helios_v2.internal_thought.engine import InternalThoughtPath
from helios_v2.thought_gating import ContinuationPressureState, SelectedStimulusSummary, ThoughtGateResult


def _build_config() -> InternalThoughtConfig:
    return InternalThoughtConfig(
        legal_min_sufficiency=0.0,
        legal_max_sufficiency=1.0,
        thought_bootstrap_id="internal-thought-bootstrap:v1",
        mandatory_learned_parameters=(
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        ),
    )


def _stimulus() -> SelectedStimulusSummary:
    return SelectedStimulusSummary(
        stimulus_id="stimulus:001",
        source_kind="external_text",
        source_channel_id="cli",
        stimulus_intensity=0.8,
    )


def _gate_result(decision: str = "fire") -> ThoughtGateResult:
    return ThoughtGateResult(
        result_id="thought-gate-result:001",
        source_conscious_state_id="conscious-state:001",
        source_signal_snapshot_id="gate-snapshot:001",
        decision=decision,
        gate_score=0.8 if decision == "fire" else 0.2,
        trigger_reason="salient_stimulus" if decision == "fire" else None,
        dominant_reason="salient_stimulus" if decision == "fire" else "gate_score_too_low",
        blocked_reasons=() if decision == "fire" else ("gate_score_too_low",),
        contributing_signals={"stimulus_signal": 0.8},
        selected_stimuli=(_stimulus(),),
        no_fire_reason=None if decision == "fire" else "gate_score_too_low",
        tick_id=1,
    )


def _bundle() -> ThoughtWindowBundle:
    return ThoughtWindowBundle(
        bundle_id="thought-window-bundle:001",
        source_plan_id="retrieval-plan:001",
        short_term_context=(
            ThoughtWindowHit(
                memory_id="memory:short:001",
                memory_type="short_term_context",
                summary="current stimulus context",
                score=0.9,
                source="retrieval_request",
                tags=("current",),
            ),
        ),
        mid_term_hits=(
            ThoughtWindowHit(
                memory_id="memory:mid:001",
                memory_type="episodic",
                summary="mid term episodic memory",
                score=0.7,
                source="memory_affect_and_replay",
                tags=("episodic",),
            ),
        ),
        long_term_hits=(),
        autobiographical_hits=(
            ThoughtWindowHit(
                memory_id="memory:auto:001",
                memory_type="autobiographical",
                summary="autobiographical continuity memory",
                score=0.75,
                source="memory_affect_and_replay",
                tags=("continuity",),
            ),
        ),
        selection_trace=(
            RetrievalSelectionTrace("short_term", 1, 1, "mixed"),
            RetrievalSelectionTrace("mid_term", 1, 1, "mixed"),
            RetrievalSelectionTrace("long_term", 0, 0, "mixed"),
            RetrievalSelectionTrace("autobiographical", 1, 1, "mixed"),
        ),
        retrieval_sec_trace=(),
        tick_id=1,
    )


def _request(source_continuation_active: bool = False) -> InternalThoughtRequest:
    return InternalThoughtRequest(
        request_id="internal-thought-request:001",
        source_gate_result_id="thought-gate-result:001",
        source_retrieval_bundle_id="thought-window-bundle:001",
        source_continuation_active=source_continuation_active,
        internal_state_summary="current internal state summary",
        prompt_contract_summary={"mode": "internal_thought", "voice": "structured"},
        tick_id=1,
    )


@dataclass
class RecordingInternalThoughtPath(InternalThoughtPath):
    def run(
        self,
        gate_result,
        retrieval_bundle,
        continuation_state,
        request,
        config,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        assert gate_result.result_id == "thought-gate-result:001"
        assert retrieval_bundle.bundle_id == "thought-window-bundle:001"
        assert continuation_state.active is False
        assert config.thought_bootstrap_id == "internal-thought-bootstrap:v1"
        thought = ThoughtContent(
            thought_id="thought:001",
            thought_type="stimulus_response_thought",
            content="structured thought content",
            source_path="recording_test_path",
            llm_used=False,
            fallback_used=False,
        )
        result = ThoughtCycleResult(
            result_id="thought-cycle-result:001",
            source_request_id=request.request_id,
            execution_status="completed",
            thought=thought,
            trigger_reason="salient_stimulus",
            sufficiency_level=0.8,
            continuation_requested=False,
            continuation_reason="sufficient_current_cycle",
            continuation_pressure_delta=0.1,
            recall_intent="",
            memory_handoff=None,
            action_proposal=None,
            self_revision_proposal=SelfRevisionProposalCarrier(
                proposal_id="self-revision:001",
                revision_kind="identity_narrative",
                requested_change_summary="tighten autobiographical self-description",
                reason_trace="thought-origin self revision",
            ),
            tick_id=1,
        )
        trace = InternalThoughtTrace(
            triggered=True,
            trigger_reason="salient_stimulus",
            llm_used=False,
            fallback_used=False,
            execution_status="completed",
            sufficiency_level=0.8,
            continuation_requested=False,
            continuation_reason="sufficient_current_cycle",
            recall_intent="",
            action_explicit=False,
            action_parse_status="absent",
        )
        return result, trace


def test_engine_builds_completed_result_and_publish_op() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=RecordingInternalThoughtPath())

    run_op = engine.build_run_op(_gate_result(), _bundle(), _request())
    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )
    publish_op = engine.build_publish_result_op(result)

    assert run_op.op_name == "run_internal_thought"
    assert result.execution_status == "completed"
    assert result.self_revision_proposal is not None
    assert trace.execution_status == "completed"
    assert publish_op.has_self_revision_proposal is True


def test_first_version_path_returns_completed_result_and_optional_action_proposal() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=FirstVersionInternalThoughtPath())

    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )

    assert result.execution_status == "completed"
    assert result.thought is not None
    assert result.action_proposal is not None
    assert result.action_proposal.outbound_text == result.thought.content
    assert trace.action_explicit is True



def test_engine_rejects_no_fire_gate_result_without_fallback() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=FirstVersionInternalThoughtPath())

    with pytest.raises(InternalThoughtError, match="fired"):
        engine.run_thought_cycle(
            _gate_result(decision="no_fire"),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )


def test_engine_requires_explicit_thought_capability() -> None:
    engine = InternalThoughtEngine(config=_build_config(), thought_path=None)

    with pytest.raises(InternalThoughtError, match="explicit thought capability"):
        engine.run_thought_cycle(
            _gate_result(),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )


# --- Requirement 26: LLM-backed internal thought path ---


@dataclass
class FakeThoughtGateway:
    """Deterministic gateway double for the LLM-backed path; never touches the network.

    Returns a structured JSON thought envelope (R27). `output_text` becomes the envelope's
    `thought` field; the default envelope is "sufficient, no continue, intends action" so the
    owner externalizes, matching the pre-R27 behavioral expectation of these R26 cases.
    """

    output_text: str = "a concise model thought for the current cycle"
    finish_reason: str = "stop"
    sufficiency: float = 0.9
    wants_to_continue: bool = False
    continue_reason: str = ""
    intends_action: bool = True
    intends_revision: bool = False
    seen_profiles: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.seen_profiles = []

    def complete(self, request):
        import json

        from helios_v2.llm import LlmCompletion, LlmUsage

        self.seen_profiles.append(request.target_profile)
        envelope = {
            "thought": self.output_text,
            "sufficiency": self.sufficiency,
            "wants_to_continue": self.wants_to_continue,
            "continue_reason": self.continue_reason,
            "proposed_action": {"intends_action": self.intends_action, "summary": ""},
            "self_revision": {"intends_revision": self.intends_revision, "summary": ""},
        }
        return LlmCompletion(
            completion_id=f"llm-completion:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="fake-model",
            output_text=json.dumps(envelope),
            finish_reason=self.finish_reason,
            usage=LlmUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10),
            latency_ms=1.0,
        )

    def check_static_readiness(self, profile_names):  # pragma: no cover - not used here
        raise NotImplementedError

    def probe_live_readiness(self, profile_names):  # pragma: no cover - not used here
        raise NotImplementedError


@dataclass
class RaisingThoughtGateway:
    def complete(self, request):
        from helios_v2.llm import LlmError

        raise LlmError("provider unavailable")

    def check_static_readiness(self, profile_names):  # pragma: no cover
        raise NotImplementedError

    def probe_live_readiness(self, profile_names):  # pragma: no cover
        raise NotImplementedError


def _llm_path(gateway):
    from helios_v2.internal_thought import LlmBackedInternalThoughtPath

    return LlmBackedInternalThoughtPath(gateway=gateway, profile_name="thought-default")


def test_llm_backed_path_uses_completion_text_and_marks_llm_used() -> None:
    gateway = FakeThoughtGateway(output_text="model-produced thought")
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_llm_path(gateway))

    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )

    assert result.execution_status == "completed"
    assert result.thought is not None
    assert result.thought.content == "model-produced thought"
    assert result.thought.llm_used is True
    assert result.thought.fallback_used is False
    assert result.thought.source_path == "llm_backed_v1"
    assert trace.llm_used is True
    assert gateway.seen_profiles == ["thought-default"]


def test_llm_backed_judgment_is_owner_held_for_proposal_fields() -> None:
    # The model supplies content and intent only. The owner owns proposal scope, behavior,
    # channels, and intensity. With a "sufficient + intends_action" envelope the owner emits
    # an external reply proposal whose fields are owner-set, not model-set.
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_llm_path(FakeThoughtGateway()))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "completed"
    assert result.action_proposal is not None
    assert result.action_proposal.scope == "external"
    assert result.action_proposal.behavior_name == "reply_message"
    assert result.action_proposal.preferred_channels == ("cli",)
    assert result.action_proposal.outbound_intensity == 0.75
    # The owner blends the model sufficiency (0.9) with retrieval sufficiency (0.8):
    # 0.6*0.9 + 0.4*0.8 = 0.86.
    assert result.sufficiency_level == 0.86


def test_llm_backed_path_hard_stops_on_gateway_failure_without_fallback() -> None:
    from helios_v2.llm import LlmError

    engine = InternalThoughtEngine(
        config=_build_config(), thought_path=_llm_path(RaisingThoughtGateway())
    )

    with pytest.raises(LlmError):
        engine.run_thought_cycle(
            _gate_result(),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )


def test_llm_backed_path_empty_completion_yields_insufficient_generation() -> None:
    gateway = FakeThoughtGateway(output_text="   ")
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_llm_path(gateway))

    result, trace = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState.inactive(),
        _request(),
    )

    assert result.execution_status == "insufficient_generation"
    assert result.thought is None
    assert result.action_proposal is None
    assert result.self_revision_proposal is None
    assert trace.llm_used is True
    assert trace.execution_status == "insufficient_generation"


def test_llm_backed_path_preserves_fired_path_validation() -> None:
    engine = InternalThoughtEngine(
        config=_build_config(), thought_path=_llm_path(FakeThoughtGateway())
    )

    with pytest.raises(InternalThoughtError, match="fired"):
        engine.run_thought_cycle(
            _gate_result(decision="no_fire"),
            _bundle(),
            ContinuationPressureState.inactive(),
            _request(),
        )


# --- Requirement 27: structured thought output driving owner judgment ---

import json as _json


@dataclass
class JsonThoughtGateway:
    """Gateway double returning a configurable structured JSON envelope (network-free)."""

    payload: object = None
    raw_text: str | None = None
    seen_formats: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.seen_formats = []

    def complete(self, request):
        from helios_v2.llm import LlmCompletion, LlmUsage

        self.seen_formats.append(request.response_format)
        text = self.raw_text if self.raw_text is not None else _json.dumps(self.payload)
        return LlmCompletion(
            completion_id=f"llm-completion:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="fake-model",
            output_text=text,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=4, completion_tokens=6, total_tokens=10),
            latency_ms=1.0,
        )

    def check_static_readiness(self, profile_names):  # pragma: no cover
        raise NotImplementedError

    def probe_live_readiness(self, profile_names):  # pragma: no cover
        raise NotImplementedError


def _structured_path(gateway):
    from helios_v2.internal_thought.engine import LlmBackedInternalThoughtPath

    return LlmBackedInternalThoughtPath(gateway=gateway, profile_name="thought-default")


def _envelope(
    *,
    thought="model thought",
    sufficiency=0.9,
    wants_to_continue=False,
    continue_reason="",
    intends_action=False,
    intends_revision=False,
):
    return {
        "thought": thought,
        "sufficiency": sufficiency,
        "wants_to_continue": wants_to_continue,
        "continue_reason": continue_reason,
        "proposed_action": {"intends_action": intends_action, "summary": ""},
        "self_revision": {"intends_revision": intends_revision, "summary": ""},
    }


def test_structured_path_requests_json_object_format() -> None:
    gateway = JsonThoughtGateway(payload=_envelope())
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert gateway.seen_formats == ["json_object"]


def test_structured_sufficient_with_action_intent_externalizes() -> None:
    gateway = JsonThoughtGateway(
        payload=_envelope(sufficiency=0.9, wants_to_continue=False, intends_action=True)
    )
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "completed"
    assert result.continuation_requested is False
    assert result.action_proposal is not None
    assert result.thought.content == "model thought"


def test_structured_no_action_intent_does_not_externalize() -> None:
    # Model concludes the cycle is complete but warrants no action: a valid outcome the
    # retrieval-only baseline could not express.
    gateway = JsonThoughtGateway(
        payload=_envelope(sufficiency=0.9, wants_to_continue=False, intends_action=False)
    )
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "completed"
    assert result.continuation_requested is False
    assert result.action_proposal is None


def test_structured_insufficient_with_continue_intent_continues() -> None:
    gateway = JsonThoughtGateway(
        payload=_envelope(
            sufficiency=0.2,
            wants_to_continue=True,
            continue_reason="need to explore the prior context further",
            intends_action=False,
        )
    )
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "completed"
    assert result.continuation_requested is True
    assert result.action_proposal is None
    assert result.memory_handoff is not None
    assert result.continuation_reason == "need to explore the prior context further"


def test_structured_same_context_different_envelope_changes_decision() -> None:
    # Falsifiable behavioral influence: identical retrieval/continuation context, two
    # different envelopes produce different owner decisions.
    engine_ext = InternalThoughtEngine(
        config=_build_config(),
        thought_path=_structured_path(
            JsonThoughtGateway(payload=_envelope(sufficiency=0.9, wants_to_continue=False, intends_action=True))
        ),
    )
    engine_cont = InternalThoughtEngine(
        config=_build_config(),
        thought_path=_structured_path(
            JsonThoughtGateway(
                payload=_envelope(
                    sufficiency=0.1,
                    wants_to_continue=True,
                    continue_reason="unresolved",
                    intends_action=False,
                )
            )
        ),
    )

    ext_result, _ = engine_ext.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )
    cont_result, _ = engine_cont.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert ext_result.continuation_requested is False
    assert ext_result.action_proposal is not None
    assert cont_result.continuation_requested is True
    assert cont_result.action_proposal is None


def test_structured_model_sufficiency_blends_into_final() -> None:
    # _bundle() has short=1, mid=1, auto=1 -> retrieval sufficiency = 0.35+0.20+0.15+0.10 = 0.80.
    # With model_signal_weight=0.6 and model_sufficiency=0.5: 0.6*0.5 + 0.4*0.80 = 0.62.
    gateway = JsonThoughtGateway(
        payload=_envelope(sufficiency=0.5, wants_to_continue=False, intends_action=True)
    )
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.sufficiency_level == 0.62


def test_structured_continuation_carry_overrides_model_intent() -> None:
    # Runtime-carried continuation must force continuation regardless of model intent.
    gateway = JsonThoughtGateway(
        payload=_envelope(sufficiency=0.95, wants_to_continue=False, intends_action=True)
    )
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(),
        _bundle(),
        ContinuationPressureState(
            active=True,
            level=0.5,
            origin_thought_id="thought:prior",
            reason="prior_cycle_unfinished",
            expires_at_tick=5,
            carry_count=1,
        ),
        _request(source_continuation_active=True),
    )

    assert result.continuation_requested is True
    assert result.action_proposal is None


def test_structured_malformed_json_yields_insufficient() -> None:
    gateway = JsonThoughtGateway(raw_text="this is not json")
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, trace = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "insufficient_generation"
    assert result.thought is None
    assert result.action_proposal is None
    assert trace.llm_used is True


def test_structured_missing_required_field_yields_insufficient() -> None:
    gateway = JsonThoughtGateway(payload={"thought": "x"})  # missing sufficiency/booleans
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "insufficient_generation"
    assert result.thought is None


def test_structured_out_of_range_sufficiency_yields_insufficient() -> None:
    gateway = JsonThoughtGateway(payload=_envelope(sufficiency=1.7))
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "insufficient_generation"


def test_structured_wrong_typed_boolean_yields_insufficient() -> None:
    payload = _envelope()
    payload["wants_to_continue"] = "yes"  # wrong type
    gateway = JsonThoughtGateway(payload=payload)
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "insufficient_generation"


def test_structured_empty_thought_yields_insufficient() -> None:
    gateway = JsonThoughtGateway(payload=_envelope(thought="   "))
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))

    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )

    assert result.execution_status == "insufficient_generation"


def test_structured_gateway_failure_is_hard_stop() -> None:
    from helios_v2.llm import LlmError

    @dataclass
    class _Raising:
        def complete(self, request):
            raise LlmError("provider down")

        def check_static_readiness(self, profile_names):  # pragma: no cover
            raise NotImplementedError

        def probe_live_readiness(self, profile_names):  # pragma: no cover
            raise NotImplementedError

    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(_Raising()))

    with pytest.raises(LlmError):
        engine.run_thought_cycle(
            _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
        )


# --- Requirement 79: structured-thought parsing robustness (reasoning model <think>/fence) ---

from helios_v2.internal_thought.engine import (  # noqa: E402
    StructuredThoughtParseError as _R79ParseError,
    _extract_structured_json as _r79_extract,
    _parse_structured_thought as _r79_parse,
)


def test_r79_extract_clean_json_is_identity() -> None:
    text = '{"thought": "x", "sufficiency": 0.5}'
    assert _r79_extract(text) == text


def test_r79_extract_strips_think_block() -> None:
    assert _r79_extract('<think>reasoning here</think>\n{"a": 1}') == '{"a": 1}'


def test_r79_extract_strips_code_fence() -> None:
    assert _r79_extract('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_r79_extract_strips_think_and_fence() -> None:
    assert _r79_extract('<think>r</think>\n```json\n{"a": 1}\n```') == '{"a": 1}'


def test_r79_extract_no_json_returns_empty() -> None:
    assert _r79_extract('<think>only truncated reasoning, no json') == ''
    assert _r79_extract('no json here') == ''
    assert _r79_extract('') == ''


def test_r79_parse_handles_think_and_fence_wrapped_envelope() -> None:
    raw = '<think>let me think</think>\n```json\n' + _json.dumps(_envelope()) + '\n```'
    evidence = _r79_parse(raw)
    assert evidence.thought_text == "model thought"


def test_r79_parse_no_json_raises_parse_error() -> None:
    with pytest.raises(_R79ParseError):
        _r79_parse('<think>truncated reasoning with no json object</think>')


def test_r79_llm_path_parses_reasoning_model_output() -> None:
    raw = (
        '<think>weighing the state</think>\n```json\n'
        + _json.dumps(_envelope(sufficiency=0.9, wants_to_continue=False, intends_action=True))
        + '\n```'
    )
    gateway = JsonThoughtGateway(raw_text=raw)
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))
    result, _trace = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )
    assert result.execution_status == "completed"


# --- Requirement 81: optional hormone forecast parse + publish ---


def test_r81_parse_extracts_hormone_forecast() -> None:
    env = _envelope()
    env["hormone_response_i_predict"] = {"dopamine": 0.8, "cortisol": 0.1}
    evidence = _r79_parse(_json.dumps(env))
    assert evidence.hormone_prediction == {"dopamine": 0.8, "cortisol": 0.1}


def test_r81_parse_absent_forecast_is_none() -> None:
    evidence = _r79_parse(_json.dumps(_envelope()))
    assert evidence.hormone_prediction is None


def test_r81_parse_null_forecast_is_none() -> None:
    env = _envelope()
    env["hormone_response_i_predict"] = None
    evidence = _r79_parse(_json.dumps(env))
    assert evidence.hormone_prediction is None


def test_r81_parse_ignores_unknown_channel() -> None:
    env = _envelope()
    env["hormone_response_i_predict"] = {"dopamine": 0.5, "not_a_channel": 0.9}
    evidence = _r79_parse(_json.dumps(env))
    assert evidence.hormone_prediction == {"dopamine": 0.5}


def test_r81_parse_rejects_out_of_range_forecast() -> None:
    env = _envelope()
    env["hormone_response_i_predict"] = {"dopamine": 1.5}
    with pytest.raises(_R79ParseError):
        _r79_parse(_json.dumps(env))


def test_r81_parse_rejects_non_object_forecast() -> None:
    env = _envelope()
    env["hormone_response_i_predict"] = "high dopamine"
    with pytest.raises(_R79ParseError):
        _r79_parse(_json.dumps(env))


def test_r81_llm_path_publishes_forecast_on_result() -> None:
    env = _envelope(sufficiency=0.9, wants_to_continue=False, intends_action=True)
    env["hormone_response_i_predict"] = {"dopamine": 0.85}
    gateway = JsonThoughtGateway(payload=env)
    engine = InternalThoughtEngine(config=_build_config(), thought_path=_structured_path(gateway))
    result, _ = engine.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )
    assert result.execution_status == "completed"
    assert dict(result.hormone_response_i_predict) == {"dopamine": 0.85}


def test_r81_forecast_does_not_change_judgment() -> None:
    base = _envelope(sufficiency=0.9, wants_to_continue=False, intends_action=True)
    with_forecast = dict(base)
    with_forecast["hormone_response_i_predict"] = {"dopamine": 0.85, "cortisol": 0.2}

    engine_a = InternalThoughtEngine(
        config=_build_config(), thought_path=_structured_path(JsonThoughtGateway(payload=base))
    )
    engine_b = InternalThoughtEngine(
        config=_build_config(),
        thought_path=_structured_path(JsonThoughtGateway(payload=with_forecast)),
    )
    result_a, _ = engine_a.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )
    result_b, _ = engine_b.run_thought_cycle(
        _gate_result(), _bundle(), ContinuationPressureState.inactive(), _request()
    )
    # The forecast is carried content; it must not change any judgment field.
    assert result_a.sufficiency_level == result_b.sufficiency_level
    assert result_a.continuation_requested == result_b.continuation_requested
    assert (result_a.action_proposal is None) == (result_b.action_proposal is None)
    assert result_a.hormone_response_i_predict is None
    assert dict(result_b.hormone_response_i_predict) == {"dopamine": 0.85, "cortisol": 0.2}
