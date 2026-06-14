"""Owner: internal thought loop.

Ships two fired-path thought implementations:

1. `FirstVersionInternalThoughtPath` - deterministic content synthesis (test/default-off).
2. `LlmBackedInternalThoughtPath` - real cognition content from the `25` LLM gateway, now
   driven by a structured thought envelope the owner parses into evidence.

Both paths share one owner-private judgment helper (`_derive_thought_judgment`) so the
sufficiency, continuation, recall-intent, memory-handoff, and proposal decisions stay owned
by this owner and remain reproducible given fixed inputs. The model supplies content and
structured self-assessment evidence; it never owns the final judgment.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.llm import LlmGatewayAPI, LlmMessage, LlmRequest
from helios_v2.thought_gating import ContinuationPressureState, ThoughtGateResult

from .contracts import (
    ACTION_INTENT_NO_ACTION,
    ACTION_INTENT_REPLY,
    ACTION_INTENT_TOOL,
    REPLY_TEXT_MAX_CHARS,
    REPLY_TEXT_TRUNCATION_SUFFIX,
    InternalThoughtAPI,
    InternalThoughtConfig,
    InternalThoughtError,
    InternalThoughtRequest,
    InternalThoughtTrace,
    MemoryHandoffDirective,
    PublishThoughtCycleResultOp,
    RunInternalThoughtOp,
    SelfRevisionProposalCarrier,
    TARGET_USER_ID_MAX_CHARS,
    TARGET_USER_ID_TRUNCATION_SUFFIX,
    ThoughtActionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
    _ACTION_INTENT_VALUES,
    _HORMONE_PREDICTION_CHANNELS,
)

# Owner-level constant: how strongly the model's self-assessed sufficiency signal moves the
# final sufficiency relative to the retrieval-derived signal. Explicit and bounded; the
# owner still anchors on retrieval evidence so the model cannot claim sufficiency alone.
_MODEL_SIGNAL_WEIGHT = 0.6


def _validate_gate_result(gate_result: ThoughtGateResult) -> None:
    if not gate_result.result_id:
        raise InternalThoughtError("ThoughtGateResult must declare a non-empty result_id")
    if gate_result.decision != "fire":
        raise InternalThoughtError("Internal thought requires a fired ThoughtGateResult")


def _validate_retrieval_bundle(bundle: ThoughtWindowBundle, request: InternalThoughtRequest) -> None:
    if not bundle.bundle_id:
        raise InternalThoughtError("ThoughtWindowBundle must declare a non-empty bundle_id")
    if bundle.bundle_id != request.source_retrieval_bundle_id:
        raise InternalThoughtError(
            "InternalThoughtRequest must preserve the source retrieval-bundle id of the current cycle"
        )


def _validate_request(gate_result: ThoughtGateResult, request: InternalThoughtRequest) -> None:
    if request.source_gate_result_id != gate_result.result_id:
        raise InternalThoughtError(
            "InternalThoughtRequest must preserve the source gate-result id of the current cycle"
        )


def _validate_continuation_alignment(
    continuation_state: ContinuationPressureState,
    request: InternalThoughtRequest,
) -> None:
    if continuation_state.active != request.source_continuation_active:
        raise InternalThoughtError("InternalThoughtRequest must preserve the current continuation active flag")


class StructuredThoughtParseError(InternalThoughtError):
    """Owner-private failure raised when a model structured-thought envelope is invalid.

    This is a subclass of `InternalThoughtError` so it is caught explicitly by the
    LLM-backed path and mapped to an explicit non-success result, never silently coerced
    and never used as a retrieval-only fallback.
    """


@dataclass(frozen=True)
class StructuredThoughtEvidence:
    """Owner-private parsed evidence from the model's structured thought envelope.

    Owner: internal thought loop.

    This is model-supplied evidence, never the final decision. The owner validates and
    bounds every field here and then maps it into the final judgment. It is intentionally
    not a cross-owner public contract in this slice.

    Failure semantics:
        Built only by `_parse_structured_thought`, which raises `StructuredThoughtParseError`
        on malformed, missing-required, out-of-range, or wrong-typed fields.
    """

    thought_text: str
    model_sufficiency: float
    wants_to_continue: bool
    continue_reason: str
    intends_action: bool
    action_summary: str
    intends_self_revision: bool
    self_revision_summary: str
    # R81: optional model-supplied subjective hormone forecast (channel -> `[0, 1]`) or None. It is
    # carried content for the `04` corroborator, never an input to this owner's judgment.
    hormone_prediction: Mapping[str, float] | None = None
    # R85: optional model-supplied tool intent. `intends_tool_use`+`tool_op` name an op the model
    # wants to run; `tool_params` are its scalar arguments. Model-supplied content the owner maps
    # into an effector action proposal; a malformed/partial intent degrades to no tool intent here.
    intends_tool_use: bool = False
    tool_op: str = ""
    tool_params: Mapping[str, object] = MappingProxyType({})
    # R94: optional model-supplied direct reply text. The model declares `reply_text` as a
    # sub-detail of `action_intent="reply"` (the action class is the primary choice;
    # `reply_text` is the reply-specific content). This owner promotes it into an
    # `reply_message` tool intent in `_emit_proposal` ONLY when (a) `action_intent` is
    # explicitly set to "reply" AND (b) the resolved `target_user_id` is non-empty. The
    # legacy R93 "compat path" (filling `i_want_to_say` / `intended_reply_text` without
    # `action_intent`) is removed in R94; the model must pick an action class explicitly.
    # Default `None` preserves the honest absence semantics; an empty / whitespace-only
    # string folds to `None`. Length is bounded by `REPLY_TEXT_MAX_CHARS` with the explicit
    # `REPLY_TEXT_TRUNCATION_SUFFIX` (deterministic truncation).
    reply_text: str | None = None
    # R93 Phase 2: explicit action-class choice. The model picks one of "reply" / "tool" /
    # "no_action" (or omits the field for compat). The owner promotes this into a deterministic
    # emit_proposal precedence order; the legacy `model_intends_action` flag is no longer
    # sufficient to construct a reply. Default None preserves the pre-Phase-2 compat path.
    action_intent: str | None = None
    # R93 Phase 2: optional model-supplied target user id. When non-empty the owner uses it as
    # the reply / tool target; when empty the owner falls back to the composition-projected
    # `current_operator_id`. Default None preserves the pre-Phase-2 compat path.
    target_user_id: str | None = None


def _require_bool(payload: dict[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise StructuredThoughtParseError(
            f"Structured thought envelope field '{key}' must be a boolean"
        )
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise StructuredThoughtParseError(
            f"Structured thought envelope field '{key}' must be a string when present"
        )
    return value.strip()


def _optional_hormone_prediction(payload: dict[str, Any]) -> Mapping[str, float] | None:
    """Owner: internal thought loop (R81).

    Purpose:
        Parse the optional `hormone_response_i_predict` field into an owner-neutral channel->value
        mapping (or `None`). The model supplies it as a subjective forecast; this owner only
        validates and bounds it, then carries it as content.

    Returns:
        A `dict` of recognized channel names to floats in `[0, 1]`, or `None` when the field is
        absent, JSON `null`, or contains no recognized channel.

    Raises:
        StructuredThoughtParseError when present-but-not-an-object, or when a recognized channel
        carries a non-numeric or out-of-range value (consistent with the strict parse).

    Notes:
        Unrecognized keys are ignored (forward-compatible); a provided subset is allowed. The owner
        does not import the `04` contract; the nine channel names are a documented convention.
    """

    value = payload.get("hormone_response_i_predict")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'hormone_response_i_predict' must be an object or null"
        )
    prediction: dict[str, float] = {}
    for channel, level in value.items():
        if channel not in _HORMONE_PREDICTION_CHANNELS:
            continue
        if isinstance(level, bool) or not isinstance(level, (int, float)):
            raise StructuredThoughtParseError(
                f"Structured thought envelope hormone forecast '{channel}' must be numeric"
            )
        if level < 0.0 or level > 1.0:
            raise StructuredThoughtParseError(
                f"Structured thought envelope hormone forecast '{channel}' must be within [0, 1]"
            )
        prediction[channel] = float(level)
    return prediction or None


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def _optional_tool_intent(payload: dict[str, Any]) -> tuple[bool, str, Mapping[str, object]]:
    """Owner: internal thought loop (R85).

    Purpose:
        Parse the optional tool-intent fields (`i_want_to_use_tool`/`tool_op`/`tool_params`) into a
        bounded `(intends, op, params)` triple. The model supplies a tool intent as content; this
        owner only validates and bounds it, then maps it into an effector action proposal.

    Returns:
        `(True, op, params)` when a well-formed tool intent is present; otherwise
        `(False, "", {})`. A malformed/partial intent (flag set but no op; `tool_params` not an
        object; a non-scalar param value or empty key) degrades to no tool intent - it is NEVER
        raised, so a malformed tool intent closes the tick through the existing no-proposal path
        rather than failing the parse.

    Notes:
        Deliberately lenient (unlike the strict required-field parsing): the tool intent is optional
        model content, and the owner never fabricates an op or params from a malformed assertion.
    """

    if not isinstance(payload.get("i_want_to_use_tool"), bool) or not payload["i_want_to_use_tool"]:
        return False, "", MappingProxyType({})
    op = payload.get("tool_op")
    if not isinstance(op, str) or not op.strip():
        return False, "", MappingProxyType({})
    raw_params = payload.get("tool_params")
    params: dict[str, object] = {}
    if isinstance(raw_params, dict):
        for key, value in raw_params.items():
            if not isinstance(key, str) or not key:
                return False, "", MappingProxyType({})
            if isinstance(value, (str, int, float, bool)):
                params[key] = value
            elif isinstance(value, (list, tuple)) and all(
                isinstance(item, (str, int, float, bool)) for item in value
            ):
                # R86: a one-level list of scalars (e.g. a command's `args`) is allowed so a tool op
                # can carry argument vectors; deeper nesting (a dict/list value) still degrades.
                params[key] = tuple(value)
            else:
                return False, "", MappingProxyType({})
    elif raw_params is not None:
        return False, "", MappingProxyType({})
    return True, op.strip(), MappingProxyType(params)


def _optional_reply_text(payload: dict[str, Any]) -> str | None:
    """Owner: internal thought loop (R94).

    Purpose:
        Parse the optional top-level `reply_text` envelope field into a bounded reply-text
        string or `None`. The model declares `reply_text` as a sub-detail of
        `action_intent="reply"`; this owner promotes it into a `reply_message` tool intent
        in `_emit_proposal` ONLY when the explicit-reply path is taken. The legacy R93
        `i_want_to_say` field is silently ignored if present (forward-compat with in-flight
        model checkpoints that still produce the field).

    Failure semantics:
        - Field absent / null / empty / whitespace-only: return `None` (no reply text this
          cycle; honest absence, never a fabricated reply).
        - Field present but non-string: raise `StructuredThoughtParseError` (fail-fast, the
          owner never silently coerces a wrongly-typed reply field into a string).
        - Field present and non-empty: return the trimmed value, deterministically truncated
          with `REPLY_TEXT_TRUNCATION_SUFFIX` when over the `REPLY_TEXT_MAX_CHARS` cap.

    Notes:
        The returned string-or-None is the model's content offering. The owner's judgment
        on whether to actually emit a reply (action_intent == "reply" + resolved target +
        reply_text non-None) is performed by `_emit_proposal`, not here. The legacy
        `i_want_to_say` payload key is read-but-ignored so an in-flight model that still
        produces the field is not broken (its `i_want_to_say` content is simply not used;
        the model is expected to start producing `reply_text` once it has the R94 prompt).
    """

    if "reply_text" not in payload:
        return None
    raw = payload.get("reply_text")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'reply_text' must be a string when present"
        )
    stripped = raw.strip()
    if not stripped:
        return None
    if len(stripped) > REPLY_TEXT_MAX_CHARS:
        cap = REPLY_TEXT_MAX_CHARS - len(REPLY_TEXT_TRUNCATION_SUFFIX)
        return stripped[:cap] + REPLY_TEXT_TRUNCATION_SUFFIX
    return stripped


def _optional_action_intent(payload: dict[str, Any]) -> str | None:
    """Owner: internal thought loop (R93 Phase 2).

    Purpose:
        Parse the optional top-level `action_intent` envelope field into a bounded action-class
        string. The model picks one of `reply` / `tool` / `no_action`; `None` (absent or
        explicit JSON null) preserves the pre-Phase-2 compat path so existing fine-tunes still
        work.

    Failure semantics:
        - Field absent / null: return `None` (compat path).
        - Field present and a recognized string: return the string verbatim.
        - Field present but not a string or not in the recognized set: raise
          `StructuredThoughtParseError` (fail-fast; the owner never silently coerces a
          misspelled action class into a default).

    Notes:
        The owner-threaded taxonomy is `_ACTION_INTENT_VALUES` (a frozenset of the three valid
        string literals). The compat path `None` is intentionally NOT in that set; the parser
        distinguishes "absent" (compat) from "explicit no_action" (closes the cycle
        internal-only regardless of other signals).
    """

    if "action_intent" not in payload:
        return None
    raw = payload.get("action_intent")
    if raw is None:
        return None
    if not isinstance(raw, str) or raw not in _ACTION_INTENT_VALUES:
        raise StructuredThoughtParseError(
            "Structured thought envelope 'action_intent' must be one of "
            "reply/tool/no_action or null when present"
        )
    return raw


def _optional_target_user_id(payload: dict[str, Any]) -> str | None:
    """Owner: internal thought loop (R93 Phase 2).

    Purpose:
        Parse the optional top-level `target_user_id` envelope field into a bounded string. The
        model names a specific user it wants to address when the action class is reply or tool;
        the owner resolves this with priority over the composition-projected
        `current_operator_id`.

    Failure semantics:
        - Field absent / null: return `None` (the owner falls back to the prompt-contract
          default).
        - Field present and a string: return the trimmed value, or `None` for whitespace-only.
        - Field present but not a string: raise `StructuredThoughtParseError` (fail-fast).
        - Field present, non-empty, and over `TARGET_USER_ID_MAX_CHARS`: deterministically
          truncated with `TARGET_USER_ID_TRUNCATION_SUFFIX`.

    Notes:
        The owner's resolution priority (model-supplied > composition-projected) lives in
        `_emit_proposal`, not here. This helper is the pure parse + bound step.
    """

    if "target_user_id" not in payload:
        return None
    raw = payload.get("target_user_id")
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'target_user_id' must be a string when present"
        )
    stripped = raw.strip()
    if not stripped:
        return None
    if len(stripped) > TARGET_USER_ID_MAX_CHARS:
        cap = TARGET_USER_ID_MAX_CHARS - len(TARGET_USER_ID_TRUNCATION_SUFFIX)
        return stripped[:cap] + TARGET_USER_ID_TRUNCATION_SUFFIX
    return stripped


def _extract_structured_json(completion_text: str) -> str:
    """Owner: internal thought loop.

    Purpose:
        Extract the JSON object from a model completion that may wrap it in a reasoning
        `<think>...</think>` block and/or a markdown code fence, before strict parsing. This
        makes the structured-thought parse robust to reasoning models without changing the
        owner's judgment or weakening fail-fast.

    Inputs:
        `completion_text` - the raw completion text from the gateway.

    Returns:
        The extracted JSON-object substring (first `{` to last `}`), or `""` when none exists
        (including a reasoning-only or `length`-truncated completion with no JSON object).

    Notes:
        Identity-preserving on a clean bare JSON object (a model already returning bare JSON is
        unchanged). It never repairs or fabricates JSON; it only removes a reasoning block and
        code fence and slices to the outermost braces. The caller maps an empty result to an
        explicit non-success outcome.
    """

    if not completion_text:
        return ""
    text = _THINK_BLOCK_RE.sub("", completion_text)
    # Drop an unterminated <think> tail (reasoning truncated before the closing tag, no JSON).
    lowered = text.lower()
    if "<think>" in lowered and "</think>" not in lowered:
        text = text[: lowered.index("<think>")]
    # Remove markdown code fences, then slice to the outermost braces.
    text = text.replace("```json", "").replace("```JSON", "").replace("```", "")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return ""
    return text[start : end + 1].strip()


def _parse_structured_thought(completion_text: str) -> StructuredThoughtEvidence:
    """Owner: internal thought loop.

    Purpose:
        Parse and validate the model's JSON structured-thought envelope into bounded,
        typed owner-private evidence.

    Inputs:
        `completion_text` - the raw `json_object` completion text from the gateway.

    Returns:
        A `StructuredThoughtEvidence` value with a clamped sufficiency and validated fields.

    Raises:
        StructuredThoughtParseError on non-JSON, non-object, missing-required, out-of-range,
        or wrong-typed fields. The owner never silently coerces invalid evidence.

    Notes:
        An empty `thought` string is allowed through here (it parses), so the caller can map
        it to the existing empty-content non-success result; every other invalid shape is a
        parse error.
    """

    extracted = _extract_structured_json(completion_text)
    if not extracted:
        raise StructuredThoughtParseError(
            "No JSON object could be extracted from the completion"
        )
    try:
        payload = json.loads(extracted)
    except (json.JSONDecodeError, TypeError) as error:
        raise StructuredThoughtParseError(
            "Structured thought envelope is not valid JSON"
        ) from error
    if not isinstance(payload, dict):
        raise StructuredThoughtParseError("Structured thought envelope must be a JSON object")

    thought_value = payload.get("thought")
    if not isinstance(thought_value, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope must declare a string 'thought' field"
        )

    sufficiency_value = payload.get("sufficiency")
    if isinstance(sufficiency_value, bool) or not isinstance(sufficiency_value, (int, float)):
        raise StructuredThoughtParseError(
            "Structured thought envelope must declare a numeric 'sufficiency' field"
        )
    if sufficiency_value < 0.0 or sufficiency_value > 1.0:
        raise StructuredThoughtParseError(
            "Structured thought envelope 'sufficiency' must be within [0, 1]"
        )

    wants_to_continue = _require_bool(payload, "wants_to_continue")
    continue_reason = _optional_str(payload, "continue_reason")
    if wants_to_continue and not continue_reason:
        raise StructuredThoughtParseError(
            "Structured thought envelope must declare 'continue_reason' when wants_to_continue is true"
        )

    action_payload = payload.get("proposed_action", {})
    if not isinstance(action_payload, dict):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'proposed_action' must be an object when present"
        )
    intends_action = _require_bool(action_payload, "intends_action") if action_payload else False
    action_summary = _optional_str(action_payload, "summary") if action_payload else ""

    revision_payload = payload.get("self_revision", {})
    if not isinstance(revision_payload, dict):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'self_revision' must be an object when present"
        )
    intends_self_revision = (
        _require_bool(revision_payload, "intends_revision") if revision_payload else False
    )
    self_revision_summary = _optional_str(revision_payload, "summary") if revision_payload else ""

    hormone_prediction = _optional_hormone_prediction(payload)
    intends_tool_use, tool_op, tool_params = _optional_tool_intent(payload)
    reply_text = _optional_reply_text(payload)
    action_intent = _optional_action_intent(payload)
    target_user_id = _optional_target_user_id(payload)

    return StructuredThoughtEvidence(
        thought_text=thought_value.strip(),
        model_sufficiency=float(sufficiency_value),
        wants_to_continue=wants_to_continue,
        continue_reason=continue_reason,
        intends_action=intends_action,
        action_summary=action_summary,
        intends_self_revision=intends_self_revision,
        self_revision_summary=self_revision_summary,
        hormone_prediction=hormone_prediction,
        intends_tool_use=intends_tool_use,
        tool_op=tool_op,
        tool_params=tool_params,
        reply_text=reply_text,
        action_intent=action_intent,
        target_user_id=target_user_id,
    )


@dataclass(frozen=True)
class _ThoughtJudgment:
    """Owner-private judgment outcome shared by every internal-thought path.

    This is the single source of the owner's fired-cycle decisions. It is computed from the
    retrieval window, the continuation state, the request, and the produced thought content.
    It is deterministic given those inputs, so any path (deterministic or LLM-backed) yields
    reproducible judgment once content is fixed.
    """

    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    recall_intent: str
    continuation_pressure_delta: float
    memory_handoff: MemoryHandoffDirective | None
    action_proposal: ThoughtActionProposalCarrier | None
    self_revision_proposal: SelfRevisionProposalCarrier | None
    # R81: carried model hormone forecast (None for the deterministic path); pass-through content,
    # not a judgment input.
    hormone_prediction: Mapping[str, float] | None = None


def _derive_thought_judgment(
    retrieval_bundle: ThoughtWindowBundle,
    continuation_state: ContinuationPressureState,
    request: InternalThoughtRequest,
    thought: ThoughtContent,
    evidence: StructuredThoughtEvidence | None = None,
) -> _ThoughtJudgment:
    """Owner: internal thought loop.

    Purpose:
        Decide the owner-held fired-cycle judgment (sufficiency, continuation, recall intent,
        memory handoff, action proposal, self-revision proposal) from the retrieval window,
        continuation state, request, the produced thought content, and optional model-supplied
        structured evidence.

    Inputs:
        `retrieval_bundle` - the directed-retrieval thought window for the cycle.
        `continuation_state` - the current continuation-pressure state.
        `request` - the validated fired-path request.
        `thought` - the produced thought content (deterministic or LLM-derived).
        `evidence` - optional model-supplied structured evidence. When None, the helper uses
            the retrieval-only baseline (the deterministic path's exact prior behavior).

    Returns:
        A `_ThoughtJudgment` carrying every owner-held decision for the cycle.

    Notes:
        Judgment is owned here, never by the model or the gateway. When evidence is present,
        the model's signals influence the decision under explicit bounded rules, but the
        owner still enforces the runtime-carry and low-context floors and owns proposal
        scope/channels/intensity/governance. Deterministic given inputs.
    """

    short_term = retrieval_bundle.short_term_context
    mid_term = retrieval_bundle.mid_term_hits
    autobiographical = retrieval_bundle.autobiographical_hits
    long_term = retrieval_bundle.long_term_hits
    total_hits = len(short_term) + len(mid_term) + len(long_term) + len(autobiographical)
    retrieval_sufficiency = min(
        1.0,
        0.35 + 0.20 * len(short_term) + 0.15 * len(mid_term) + 0.10 * len(autobiographical),
    )

    # Owner floors that the model cannot override: a runtime-carried continuation forces
    # continuation, and an empty/near-empty window cannot be declared sufficient.
    runtime_forces_continue = continuation_state.active
    low_context_forces_continue = total_hits <= 1

    if evidence is None:
        sufficiency_level = round(retrieval_sufficiency, 4)
        model_wants_continue = False
        model_intends_self_revision = False
        model_continue_reason = ""
    else:
        # Bounded blend: the model's self-assessed sufficiency measurably moves the result
        # while the owner stays anchored on retrieval evidence.
        blended = (
            _MODEL_SIGNAL_WEIGHT * evidence.model_sufficiency
            + (1.0 - _MODEL_SIGNAL_WEIGHT) * retrieval_sufficiency
        )
        sufficiency_level = round(min(1.0, max(0.0, blended)), 4)
        model_wants_continue = evidence.wants_to_continue
        model_intends_self_revision = evidence.intends_self_revision
        model_continue_reason = evidence.continue_reason

    if runtime_forces_continue or low_context_forces_continue:
        continuation_requested = True
        continuation_reason = "need_more_context"
    elif evidence is None:
        # Retrieval-only baseline (deterministic path): exactly the prior behavior.
        continuation_requested = False
        continuation_reason = "sufficient_for_current_cycle"
    elif model_wants_continue:
        continuation_requested = True
        continuation_reason = model_continue_reason or "need_more_context"
    else:
        continuation_requested = False
        continuation_reason = "sufficient_for_current_cycle"

    recall_intent = (
        "continue retrieval around current unresolved thought"
        if continuation_requested
        else ""
    )
    continuation_pressure_delta = 0.35 if continuation_requested else 0.0

    memory_handoff = None
    action_proposal = None
    self_revision_proposal = None
    if continuation_requested:
        selected_memory_refs = tuple(hit.memory_id for hit in mid_term[:1] + autobiographical[:1])
        memory_handoff = MemoryHandoffDirective(
            recall_intent=recall_intent,
            selected_memory_refs=selected_memory_refs,
            saved_for_next_tick=True,
            source_thought_id=thought.thought_id,
        )
    else:
        # R94: emit an action proposal only when the cycle closes and one of the explicit
        # action paths fires. The legacy `model_intends_action` flag is no longer sufficient
        # by itself for the LLM path; the model must pick an action class (reply / tool /
        # no_action) through `action_intent`. The deterministic offline path (evidence is
        # None) keeps the prior Phase 1 behavior of emitting a reply with
        # `outbound_text=thought.content`; the offline path is the documented "byte-for-byte
        # unchanged" R93 acceptance criterion.
        tool_intent = (
            evidence is not None and evidence.intends_tool_use and bool(evidence.tool_op)
        )
        # R93 Phase 2 (preserved in R94): explicit no_action closes the cycle internal-only
        # regardless of every other signal. The owner never fabricates a reply, tool, or any
        # other action when the model asserts it is unmoved.
        explicit_no_action = (
            evidence is not None and evidence.action_intent == ACTION_INTENT_NO_ACTION
        )
        # Resolve target_user_id once: model-supplied > composition-projected
        # current_operator_id. Both may be empty; an empty resolved value suppresses reply
        # construction (honest absence — the owner never invents a target).
        target_user_id = ""
        if evidence is not None and evidence.target_user_id:
            target_user_id = evidence.target_user_id
        if not target_user_id:
            operator_value = request.prompt_contract_summary.get("current_operator_id", "")
            if isinstance(operator_value, str):
                target_user_id = operator_value.strip()
        # R94: the reply proposal path requires ALL three signals — the model must
        # (a) explicitly pick `action_intent="reply"`, (b) supply a non-None `reply_text`,
        # and (c) have a resolved non-empty `target_user_id`. The legacy R93 "compat path"
        # (`i_want_to_say` set without `action_intent`) is REMOVED in R94: setting
        # `reply_text` alone, or setting `action_intent="reply"` without `reply_text`, both
        # yield no proposal. The model must pick an action class explicitly AND supply the
        # reply content (when reply is the action class).
        reply_explicit_path = (
            evidence is not None
            and evidence.action_intent == ACTION_INTENT_REPLY
            and evidence.reply_text is not None
            and bool(target_user_id)
        )
        # R93 Phase 2 (preserved in R94): explicit tool intent via action_intent. When the
        # model asserts `action_intent="tool"` the owner builds the tool proposal directly
        # (preserves R85 shape; doesn't require `i_want_to_use_tool=true` + `tool_op` filled).
        explicit_tool_path_via_intent = (
            evidence is not None
            and evidence.action_intent == ACTION_INTENT_TOOL
        )
        tool_intent_resolved = tool_intent or explicit_tool_path_via_intent
        # The legacy `model_intends_action` flag is no longer sufficient to construct a reply;
        # it is recorded for the trace but does not drive a proposal on its own.
        if explicit_no_action:
            action_proposal = None
        elif tool_intent_resolved:
            # R85: a tool intent takes the action slot (deterministic precedence over a say). The
            # owner names the op + params (model content); the planner selects/binds/validates the
            # channel. preferred_channels is a non-authoritative hint sourced from the ready channels
            # the prompt exposed (real channel-state), never a hardcoded driver id; the planner routes
            # by op regardless. An op no driver offers becomes a formal planner rejection.
            ready_channels = request.prompt_contract_summary.get("ready_channels", ())
            preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
            # R93 Phase 2 (preserved in R94): when the model supplied a `target_user_id` (via
            # explicit `action_intent="tool"` or via the R85 `i_want_to_use_tool` path with
            # a target picked at compose time), thread it into op_params so the planner's
            # user-binding filter can route to the right driver. The owner never invents a
            # target; the model picks (or the composition default applies) and the owner
            # honors it.
            if target_user_id:
                tool_params_for_proposal = MappingProxyType(
                    {**dict(evidence.tool_params), "target_user_id": target_user_id}
                )
            else:
                tool_params_for_proposal = evidence.tool_params
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name=evidence.tool_op,
                requested_op=evidence.tool_op,
                preferred_channels=preferred_channels,
                outbound_text=None,
                outbound_intensity=0.75,
                reason_trace=("thought selected a tool op for the current cycle",),
                governance_hints={"requires_identity_review": False},
                op_params=tool_params_for_proposal,
            )
        elif reply_explicit_path:
            # R94: build a `reply_message` tool intent from the model's `reply_text` field
            # (a sub-detail of `action_intent="reply"`) and the resolved `target_user_id`
            # (model-supplied > composition-projected). This routes through the existing R85
            # planner-spine: `13` validates the op_params (`outbound_text` +
            # `target_user_id`) against the CLI driver's self-described `required_params`,
            # binds to the user-visible outbound channel, and dispatches the actual reply.
            ready_channels = request.prompt_contract_summary.get("ready_channels", ())
            preferred_channels = tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
            # R94: `evidence.reply_text` is `str | None` (the parser folds empty/whitespace
            # to `None`); the `reply_explicit_path` guard above already requires non-None.
            reply_text = evidence.reply_text  # type: ignore[assignment]
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name="reply_message",
                requested_op="reply_message",
                preferred_channels=preferred_channels,
                outbound_text=None,
                outbound_intensity=0.75,
                reason_trace=("thought intends to reply to the resolved target",),
                governance_hints={"requires_identity_review": False},
                op_params=MappingProxyType(
                    {
                        "outbound_text": reply_text,
                        "target_user_id": target_user_id,
                    }
                ),
            )
        elif evidence is None:
            # Phase 1 acceptance criterion (R93, preserved in R94): the legacy
            # `assemble_runtime()` deterministic offline path remains byte-for-byte
            # unchanged. The deterministic path passes `evidence=None`; the owner emits a
            # `reply_message` proposal with `outbound_text=thought.content` and
            # `preferred_channels=("cli",)` exactly as it did before R93. This branch is
            # unreachable for the LLM-backed path because `evidence` is always present
            # there.
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name="reply_message",
                requested_op="reply_message",
                preferred_channels=("cli",),
                outbound_text=thought.content,
                outbound_intensity=0.75,
                reason_trace=("thought judged sufficient for current cycle",),
                governance_hints={"requires_identity_review": False},
            )
        # No further fallback. When the LLM path closes without a tool intent and without
        # an explicit reply intent (e.g. model picked `action_intent="no_action"`, or
        # left `action_intent` unset, or set `action_intent="reply"` without `reply_text`),
        # `action_proposal` stays `None` and the cycle closes internal-only. The
        # deterministic path always falls into the `evidence is None` branch above.
    # Self-revision: the existing autobiographical/sufficiency constraint is necessary; when
    # evidence is present the model's revision intent is also required. The model's intent is
    # never sufficient on its own.
    self_revision_allowed_by_owner = bool(autobiographical) and sufficiency_level >= 0.75
    self_revision_requested = self_revision_allowed_by_owner and (
        evidence is None or model_intends_self_revision
    )
    if self_revision_requested:
        self_revision_proposal = SelfRevisionProposalCarrier(
            proposal_id=f"self-revision:{request.request_id}",
            revision_kind="identity_narrative_refinement",
            requested_change_summary="Refine autobiographical self-description using current continuity evidence",
            reason_trace="autobiographical continuity surfaced during internal thought",
        )
    return _ThoughtJudgment(
        sufficiency_level=sufficiency_level,
        continuation_requested=continuation_requested,
        continuation_reason=continuation_reason,
        recall_intent=recall_intent,
        continuation_pressure_delta=continuation_pressure_delta,
        memory_handoff=memory_handoff,
        action_proposal=action_proposal,
        self_revision_proposal=self_revision_proposal,
        hormone_prediction=(evidence.hormone_prediction if evidence is not None else None),
    )


def _assemble_completed_result(
    request: InternalThoughtRequest,
    gate_result: ThoughtGateResult,
    thought: ThoughtContent,
    judgment: _ThoughtJudgment,
) -> ThoughtCycleResult:
    """Owner-private assembly of a successful `completed` thought-cycle result."""

    return ThoughtCycleResult(
        result_id=f"thought-cycle-result:{request.request_id}",
        source_request_id=request.request_id,
        execution_status="completed",
        thought=thought,
        trigger_reason=gate_result.trigger_reason or gate_result.dominant_reason or "fired_gate",
        sufficiency_level=judgment.sufficiency_level,
        continuation_requested=judgment.continuation_requested,
        continuation_reason=judgment.continuation_reason,
        continuation_pressure_delta=judgment.continuation_pressure_delta,
        recall_intent=judgment.recall_intent,
        memory_handoff=judgment.memory_handoff,
        action_proposal=judgment.action_proposal,
        self_revision_proposal=judgment.self_revision_proposal,
        tick_id=request.tick_id,
        hormone_response_i_predict=judgment.hormone_prediction,
    )


def _assemble_trace(result: ThoughtCycleResult, *, llm_used: bool, fallback_used: bool) -> InternalThoughtTrace:
    """Owner-private assembly of the bounded trace from a published result."""

    return InternalThoughtTrace(
        triggered=True,
        trigger_reason=result.trigger_reason,
        llm_used=llm_used,
        fallback_used=fallback_used,
        execution_status=result.execution_status,
        sufficiency_level=result.sufficiency_level,
        continuation_requested=result.continuation_requested,
        continuation_reason=result.continuation_reason,
        recall_intent=result.recall_intent,
        action_explicit=result.action_proposal is not None,
        action_parse_status="action_explicit" if result.action_proposal is not None else "no_action",
    )


def _assemble_insufficient_result(
    request: InternalThoughtRequest,
    gate_result: ThoughtGateResult,
    *,
    continuation_reason: str,
    recall_intent: str,
) -> ThoughtCycleResult:
    """Owner-private assembly of an explicit non-success `insufficient_generation` result.

    Used when a path cannot produce usable thought content (for example an empty LLM
    completion). It publishes no `ThoughtContent` and no downstream proposals, consistent
    with the thought execution-status taxonomy. It never fabricates content.
    """

    return ThoughtCycleResult(
        result_id=f"thought-cycle-result:{request.request_id}",
        source_request_id=request.request_id,
        execution_status="insufficient_generation",
        thought=None,
        trigger_reason=gate_result.trigger_reason or gate_result.dominant_reason or "fired_gate",
        sufficiency_level=0.0,
        continuation_requested=True,
        continuation_reason=continuation_reason,
        continuation_pressure_delta=0.35,
        recall_intent=recall_intent,
        memory_handoff=None,
        action_proposal=None,
        self_revision_proposal=None,
        tick_id=request.tick_id,
    )


@runtime_checkable
class InternalThoughtPath(Protocol):
    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        """Return one thought-cycle result and one trace from validated fired-path input."""


@dataclass
class FirstVersionInternalThoughtPath(InternalThoughtPath):
    """Owner-private deterministic first-version thought path.

    Produces thought content by deterministic synthesis (`llm_used=False`). Retained for
    explicit test assembly and as a reproducible reference; it is no longer the default
    production path once an LLM-backed path is bound by composition.
    """

    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        del config
        thought = ThoughtContent(
            thought_id=f"thought:{request.request_id}",
            thought_type="reflective_retrieval_synthesis",
            content=self._render_content(request, retrieval_bundle),
            source_path="deterministic_first_version",
            llm_used=False,
            fallback_used=False,
        )
        judgment = _derive_thought_judgment(retrieval_bundle, continuation_state, request, thought)
        result = _assemble_completed_result(request, gate_result, thought, judgment)
        trace = _assemble_trace(result, llm_used=False, fallback_used=False)
        return result, trace

    def _render_content(self, request: InternalThoughtRequest, retrieval_bundle: ThoughtWindowBundle) -> str:
        fragments: list[str] = []
        # R91: when the additive `present_field_summary` is supplied, render it as the first
        # fragment so the deterministic-fallback content also exposes the current stimulus.
        if request.present_field_summary:
            fragments.append(f"Present field: {request.present_field_summary}")
        fragments.append(request.internal_state_summary)
        if retrieval_bundle.short_term_context:
            fragments.append(f"Current context: {retrieval_bundle.short_term_context[0].summary}")
        if retrieval_bundle.mid_term_hits:
            fragments.append(f"Mid-term memory: {retrieval_bundle.mid_term_hits[0].summary}")
        if retrieval_bundle.autobiographical_hits:
            fragments.append(f"Autobiographical anchor: {retrieval_bundle.autobiographical_hits[0].summary}")
        return " | ".join(fragments)


@dataclass
class LlmBackedInternalThoughtPath(InternalThoughtPath):
    """Owner-private LLM-backed thought path.

    Owner: internal thought loop.

    Purpose:
        Source thought content from the `25` LLM gateway through a neutral request, then run
        the shared owner-held judgment to produce the formal thought-cycle result. The model
        supplies content only; sufficiency, continuation, and proposal decisions stay owned
        by this owner.

    Failure semantics:
        A gateway failure (`LlmError`) propagates as a hard stop; this path never fabricates
        content and never falls back to deterministic synthesis. An empty completion yields
        an explicit `insufficient_generation` result with no `ThoughtContent`.

    Notes:
        Adapting the request and retrieval window into neutral `LlmMessage` values is owned
        here (the consumer), so the gateway stays ignorant of cognitive structure.
    """

    gateway: LlmGatewayAPI
    profile_name: str
    thought_source_path: str = "llm_backed_v1"

    def run(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
        config: InternalThoughtConfig,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        del config
        llm_request = LlmRequest(
            request_id=f"llm-thought:{request.request_id}",
            target_profile=self.profile_name,
            messages=self._build_messages(request, retrieval_bundle, continuation_state),
            response_format="json_object",
            metadata={"consumer": "internal_thought", "tick_id": request.tick_id},
        )
        # LlmError (unknown profile, missing key, provider failure) propagates as a hard stop.
        completion = self.gateway.complete(llm_request)
        # Parse + validate the structured envelope into owner-private evidence. A malformed,
        # missing-required, out-of-range, or wrong-typed envelope is an explicit non-success
        # result; the owner never silently coerces it or falls back to retrieval-only judgment.
        try:
            evidence = _parse_structured_thought(completion.output_text)
        except StructuredThoughtParseError:
            result = _assemble_insufficient_result(
                request,
                gate_result,
                continuation_reason="malformed_structured_thought",
                recall_intent="retry structured thought generation for current unresolved cycle",
            )
            trace = _assemble_trace(result, llm_used=True, fallback_used=False)
            return result, trace
        if not evidence.thought_text:
            result = _assemble_insufficient_result(
                request,
                gate_result,
                continuation_reason="empty_llm_completion",
                recall_intent="retry thought generation for current unresolved cycle",
            )
            trace = _assemble_trace(result, llm_used=True, fallback_used=False)
            return result, trace
        thought = ThoughtContent(
            thought_id=f"thought:{request.request_id}",
            thought_type="llm_reflective_synthesis",
            content=evidence.thought_text,
            source_path=self.thought_source_path,
            llm_used=True,
            fallback_used=False,
        )
        judgment = _derive_thought_judgment(
            retrieval_bundle,
            continuation_state,
            request,
            thought,
            evidence=evidence,
        )
        result = _assemble_completed_result(request, gate_result, thought, judgment)
        trace = _assemble_trace(result, llm_used=True, fallback_used=False)
        return result, trace

    def _build_messages(
        self,
        request: InternalThoughtRequest,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
    ) -> tuple[LlmMessage, ...]:
        """Adapt the fired-path inputs into neutral system/user messages (consumer-owned).

        The system message documents the structured JSON envelope the owner will parse. The
        envelope expresses self-assessment and intent only; channel, intensity, op, and
        governance decisions remain owner-owned and are not requested from the model.
        """

        summary = request.prompt_contract_summary
        layer_names = summary.get("layer_names", ())
        if isinstance(layer_names, (tuple, list)):
            layer_text = ", ".join(str(name) for name in layer_names) or "none"
        else:
            layer_text = str(layer_names)
        system_lines = [
            "You are the internal thought process of a continuous, brain-inspired runtime.",
            "Produce one concise internal thought for the current cycle.",
            "Do not perform theatrical self-narration; reflect the current state and context only.",
            f"Active prompt-contract layers: {layer_text}.",
            "Respond with a single JSON object only, no prose outside it, with this shape:",
            "{",
            '  "thought": "<concise internal thought>",',
            '  "sufficiency": <number 0..1, how complete this cycle\'s thinking is>,',
            '  "wants_to_continue": <true if more thinking is needed this line of thought>,',
            '  "continue_reason": "<why you want to continue, required if wants_to_continue is true>",',
            '  "proposed_action": {"intends_action": <true if an outward action is warranted>, "summary": "<optional>"},',
            '  "self_revision": {"intends_revision": <true if your self-model should change>, "summary": "<optional>"},',
            # R94: action_intent is the PRIMARY action-class field — the model picks one of
            # three values (reply / tool / no_action) every cycle. The legacy R93 P1
            # `i_want_to_say` field is REMOVED; reply text now lives on `reply_text`, a
            # sub-detail of `action_intent="reply"`. `action_intent` is REQUIRED (the
            # owner will not construct a reply proposal when the field is omitted).
            '  "action_intent": "reply" | "tool" | "no_action" (REQUIRED — pick one every cycle),',
            '  "reply_text": "<when action_intent is "reply", the text to send. Omit when action_intent is "tool" or "no_action">",',
            '  "target_user_id": "<optional override of the current operator id, used for reply/tool>",',
            '  "i_want_to_use_tool": <bool>, "tool_op": "<optional>", "tool_params": {<optional>},',
            "}",
            "Set wants_to_continue to false and intends_action to false when no action is warranted.",
            "You may optionally add a 'hormone_response_i_predict' field: an object forecasting your "
            "own neuromodulator response, with any of these keys set to a number 0..1 - "
            "dopamine, norepinephrine, serotonin, acetylcholine, cortisol, oxytocin, opioid_tone, "
            "excitation, inhibition. Omit it or set it to null if you have no such sense.",
            # R94: action class is a CHOICE, not a default — and it is the FIRST decision
            # the model makes on every cycle. `reply_text` is a sub-detail of the reply
            # action class, not an independent choice. The legacy R93 P1 `i_want_to_say`
            # field is REMOVED; the model must use `action_intent + reply_text` to declare
            # a reply.
            "Action class is a CHOICE, and it is the FIRST decision on every cycle. After thinking, decide whether to act and what class:",
            "  - reply: send a user-visible message. ALSO set 'reply_text' to the text to send and (optionally) 'target_user_id' to override the current operator.",
            "  - tool: invoke a bound effector. ALSO set 'tool_op' to the op name and 'tool_params' to its arguments.",
            "  - no_action: cycle closes as internal-only. No dispatch, no proposal.",
            "Do NOT reflexively reply just because an input arrived. Choose the action class that matches what this cycle actually warrants. A low-salience or 'ok' / acknowledgment stimulus may legitimately close as no_action.",
            # R94 transport clause: action_intent + reply_text + target_user_id, NOT
            # the legacy R93 P1 reply field (the R93 P1 field is retired; reply text now
            # lives on `reply_text` only). The clause intentionally avoids using the
            # legacy field name so the structural regression test (`test_internal_thought_
            # no_i_want_to_say_in_prompt.py`) does not flag this prompt text.
            "When you set 'action_intent' to 'reply' AND supply 'reply_text', the runtime will transport that text as a 'reply_message' to the resolved 'target_user_id' through the connected driver serving that user. 'reply_text' is a sub-detail of the reply action class, not an independent choice.",
        ]
        system_message = LlmMessage(role="system", content="\n".join(system_lines))

        user_lines: list[str] = []
        # R91: prepend the present-field line when the additive request field carries it (the
        # bridge projects same-frame `08` focal content + optional temporal pacing). When the
        # field is None this keeps the user message byte-for-byte identical to the pre-R91 form.
        if request.present_field_summary:
            user_lines.append(f"Present field: {request.present_field_summary}")
        user_lines.append(f"Internal state: {request.internal_state_summary}")
        if retrieval_bundle.short_term_context:
            user_lines.append(f"Current context: {retrieval_bundle.short_term_context[0].summary}")
        if retrieval_bundle.mid_term_hits:
            user_lines.append(f"Mid-term memory: {retrieval_bundle.mid_term_hits[0].summary}")
        if retrieval_bundle.autobiographical_hits:
            user_lines.append(
                f"Autobiographical anchor: {retrieval_bundle.autobiographical_hits[0].summary}"
            )
        user_lines.append(
            "Continuation pressure is "
            + ("active" if continuation_state.active else "inactive")
            + " for this cycle."
        )
        user_message = LlmMessage(role="user", content="\n".join(user_lines))
        return (system_message, user_message)


@dataclass
class InternalThoughtEngine(InternalThoughtAPI):
    """Execute one fired internal-thought cycle using an injected private thought path."""

    config: InternalThoughtConfig
    thought_path: InternalThoughtPath | None

    def run_thought_cycle(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        _validate_retrieval_bundle(retrieval_bundle, request)
        _validate_continuation_alignment(continuation_state, request)
        if self.thought_path is None:
            raise InternalThoughtError("Internal thought requires an explicit thought capability")
        result, trace = self.thought_path.run(
            gate_result,
            retrieval_bundle,
            continuation_state,
            request,
            self.config,
        )
        if result.source_request_id != request.request_id:
            raise InternalThoughtError("ThoughtCycleResult must preserve the source request id")
        if trace.execution_status != result.execution_status:
            raise InternalThoughtError("InternalThoughtTrace must preserve the published execution status")
        return result, trace

    def build_run_op(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        request: InternalThoughtRequest,
    ) -> RunInternalThoughtOp:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        _validate_retrieval_bundle(retrieval_bundle, request)
        return RunInternalThoughtOp(
            op_name="run_internal_thought",
            owner="internal_thought_loop_owner",
            request_id=request.request_id,
            gate_result_id=gate_result.result_id,
            retrieval_bundle_id=retrieval_bundle.bundle_id,
        )

    def build_publish_result_op(
        self,
        result: ThoughtCycleResult,
    ) -> PublishThoughtCycleResultOp:
        if not result.result_id:
            raise InternalThoughtError("ThoughtCycleResult contains incomplete publication identity")
        return PublishThoughtCycleResultOp(
            op_name="publish_thought_cycle_result",
            owner="internal_thought_loop_owner",
            result_id=result.result_id,
            execution_status=result.execution_status,
            continuation_requested=result.continuation_requested,
            has_action_proposal=result.action_proposal is not None,
            has_self_revision_proposal=result.self_revision_proposal is not None,
        )
