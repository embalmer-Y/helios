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
    InternalThoughtAPI,
    InternalThoughtConfig,
    InternalThoughtError,
    InternalThoughtRequest,
    InternalThoughtTrace,
    MemoryHandoffDirective,
    PublishThoughtCycleResultOp,
    RunInternalThoughtOp,
    SelfRevisionProposalCarrier,
    ThoughtActionProposalCarrier,
    ThoughtContent,
    ThoughtCycleResult,
    _HORMONE_PREDICTION_CHANNELS,
)

# Owner-level constant: how strongly the model's self-assessed sufficiency signal moves the
# final sufficiency relative to the retrieval-derived signal. Explicit and bounded; the
# owner still anchors on retrieval evidence so the model cannot claim sufficiency alone.
_MODEL_SIGNAL_WEIGHT = 0.6

# R95 followup (C3): the channel subsystem is the SOLE source of truth for
# op names. The engine never hardcodes an op name; even the offline
# deterministic default derives the op from the request's
# `prompt_contract_summary["available_channel_ops"]` projection. The
# first-version (shim) assembly bridges inject a synthetic one-op projection
# for the offline assembly; production (semantic) assembly projects the
# real `frame.channel_state` into the same key.
_DEFAULT_OFFLINE_PREFERRED_CHANNELS: tuple[str, ...] = ("cli",)
_DEFAULT_OFFLINE_OUTBOUND_INTENSITY = 0.75


def _default_op_from_request(request: InternalThoughtRequest) -> str | None:
    """R95 followup (C3): derive the offline deterministic default op
    from the request's available channel ops projection.

    The OWNER does not name ops. It reads the first op's `op_name` from
    `request.prompt_contract_summary["available_channel_ops"]` (a tuple of
    dicts produced by the composition `_available_channel_ops(frame)`
    projection in production, or by the first-version shim bridges in
    offline assembly). Returns `None` when no op is available — the
    caller should then leave `action_proposal` as `None` (cycle closes
    internal-only).

    This helper is the data-driven replacement for the R93 P1 byte-for-byte
    `behavior_name="reply_message"` hardcode.
    """
    available_channel_ops = request.prompt_contract_summary.get("available_channel_ops")
    if not isinstance(available_channel_ops, (tuple, list)) or not available_channel_ops:
        return None
    first = available_channel_ops[0]
    if isinstance(first, dict):
        op_name = first.get("op_name")
        if isinstance(op_name, str) and op_name:
            return op_name
        return None
    if isinstance(first, str) and first:
        return first
    return None


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

    R95: 14 fields (R94) → 5 user-facing fields. The 11 R93-R94 behavior-suggestive
    envelope fields (`reply_text`, `i_want_to_use_tool`, `wants_to_continue`,
    `continue_reason`, `proposed_action`, `self_revision`, `action_intent`,
    `target_user_id`, plus 3 companion sub-fields) are all REMOVED. The
    remaining 5 fields are:

    - `thought_text` — the model's internal thought (required).
    - `model_sufficiency` — the model's self-assessed sufficiency in [0, 1].
    - `thinking_complete` — replaces `wants_to_continue` with a neutral
      state description. The OWNER's continuation floors remain
      authoritative; this is advisory.
    - `hormone_prediction` — unchanged from R81.
    - `tool_op` — the single primary action-class field. Empty/missing
      means "no action"; non-empty means "the model picked this op".
    - `tool_params` — the model's op parameters (passed through verbatim
      to the planner; the engine does NOT auto-inject `target_user_id`
      from any source).
    - `channel_request` — NEW. The LLM may describe a channel/op it
      wishes existed but doesn't. Carried for forward-compat with a
      future gap-tracker (R96+ / P4); the OWNER does not act on it in R95.

    This is model-supplied evidence, never the final decision. The owner
    validates and bounds every field here and then maps it into the final
    judgment. It is intentionally not a cross-owner public contract in
    this slice.

    Failure semantics:
        Built only by `_parse_structured_thought`, which raises
        `StructuredThoughtParseError` on malformed, missing-required,
        out-of-range, or wrong-typed fields.
    """

    thought_text: str
    model_sufficiency: float
    # R95: replaces wants_to_continue. OWNER floors remain authoritative;
    # the model's signal is advisory.
    thinking_complete: bool = True
    # R95: NEW. The model describes a channel/op it wishes existed but
    # doesn't. Carried for forward-compat; OWNER does not act on it.
    channel_request: Mapping[str, object] | None = None
    # R81: optional subjective hormone forecast (unchanged).
    hormone_prediction: Mapping[str, float] | None = None
    # R85/R95: tool intent (now the single primary action-class field).
    # Empty tool_op ≡ no action; non-empty tool_op ≡ the model picked
    # this op. tool_params is passed through verbatim (no auto-injection).
    tool_op: str = ""
    tool_params: Mapping[str, object] = MappingProxyType({})


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


def _optional_thinking_complete(payload: dict[str, Any]) -> bool:
    """Owner: internal thought loop (R95).

    Purpose:
        Parse the optional `thinking_complete` envelope field into a bool. Replaces the R81
        `wants_to_continue` with a neutral state description (not a verb). The OWNER's
        continuation floors remain authoritative; this is advisory.

    Returns:
        `True` when the field is absent or null (the model did not explicitly indicate
        mid-thought). `True`/`False` when the field is a recognized bool. Raises
        `StructuredThoughtParseError` when the field is present but not a bool.

    Notes:
        The default-True semantics match the conservative interpretation: a missing signal
        is treated as "the model is done with this line of thought"; the OWNER's continuation
        floors still apply independently and may override this.
    """

    if "thinking_complete" not in payload:
        return True
    raw = payload.get("thinking_complete")
    if raw is None:
        return True
    if not isinstance(raw, bool):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'thinking_complete' must be a boolean when present"
        )
    return raw


def _optional_channel_request(payload: dict[str, Any]) -> Mapping[str, object] | None:
    """Owner: internal thought loop (R95).

    Purpose:
        Parse the optional `channel_request` envelope field into a bounded mapping or `None`.
        The model uses this to describe a channel/op it wishes existed but doesn't. The OWNER
        carries it as content but does NOT act on it in R95 (no gap-tracker exists yet; a
        future R96+ / P4 requirement will decide routing).

    Returns:
        `None` when the field is absent or null. A `MappingProxyType` of the object when
        the field is a recognized dict. Raises `StructuredThoughtParseError` when the
        field is present but not an object.

    Notes:
        The owner does not inspect the keys/values; the field is opaque to the engine in R95.
        This is a forward-compat carrier only.
    """

    if "channel_request" not in payload:
        return None
    raw = payload.get("channel_request")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'channel_request' must be an object or null when present"
        )
    return MappingProxyType(dict(raw))


def _optional_tool_op(payload: dict[str, Any]) -> str:
    """Owner: internal thought loop (R95).

    Purpose:
        Parse the optional `tool_op` envelope field into a bounded string. `tool_op` is the
        single primary action-class field in R95: empty/missing means "no action";
        non-empty means "the model picked this op".

    Returns:
        Empty string when the field is absent, null, or whitespace-only. The trimmed
        non-empty string otherwise. Raises `StructuredThoughtParseError` when the field
        is present but not a string.

    Notes:
        No length cap on the op name itself; the cap is the planner's domain. R95 does not
        validate that the op is one the available channels offer — the planner does that
        at dispatch time.
    """

    if "tool_op" not in payload:
        return ""
    raw = payload.get("tool_op")
    if raw is None:
        return ""
    if not isinstance(raw, str):
        raise StructuredThoughtParseError(
            "Structured thought envelope 'tool_op' must be a string when present"
        )
    return raw.strip()


def _optional_tool_params(payload: dict[str, Any]) -> Mapping[str, object]:
    """Owner: internal thought loop (R85/R95).

    Purpose:
        Parse the optional `tool_params` envelope field into a bounded mapping. The R95
        engine does NOT auto-inject `target_user_id` from any source — the LLM's content
        is passed through verbatim (or, when malformed, degrades to an empty mapping).

    Returns:
        A `MappingProxyType` of the parsed object when the field is a dict with
        scalar/list-of-scalar values. `MappingProxyType({})` when the field is absent,
        null, or malformed (non-scalar value, empty key, nested dict). A non-object
        non-null value also degrades to empty.

    Notes:
        R86: a one-level list of scalars (e.g. a command's `args`) is allowed. Deeper
        nesting still degrades. R95 keeps the R85/R86 lenient parse: the tool_params
        is optional model content, and the owner never fabricates params from a
        malformed assertion.
    """

    if "tool_params" not in payload:
        return MappingProxyType({})
    raw = payload.get("tool_params")
    if raw is None:
        return MappingProxyType({})
    if not isinstance(raw, dict):
        return MappingProxyType({})
    params: dict[str, object] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not key:
            return MappingProxyType({})
        if isinstance(value, (str, int, float, bool)):
            params[key] = value
        elif isinstance(value, (list, tuple)) and all(
            isinstance(item, (str, int, float, bool)) for item in value
        ):
            params[key] = tuple(value)
        else:
            return MappingProxyType({})
    return MappingProxyType(params)


_UNRESOLVED_REASONING_HOOKS = (
    # English-style mid-thought indicators.
    "let me think",
    "still need",
    "need to think",
    "on the other hand",
    "but also",
    "need more",
    # Chinese-style mid-thought indicators.
    "让我想想",
    "还需要",
    "仍然需要",
    "再想想",
)


def _has_unresolved_reasoning_hooks(thought_text: str) -> bool:
    """Owner: internal thought loop (R95).

    Purpose:
        Bounded advisory heuristic for the OWNER's continuation decision. Returns True
        when the thought text contains a trailing ellipsis or question mark, or any of
        a small set of mid-thought phrases (English + Chinese). Returns False otherwise
        (including on empty text).

    Notes:
        This is intentionally bounded and conservative. The heuristic is ADVISORY ONLY
        — the OWNER's `runtime_forces_continue` and `low_context_forces_continue`
        floors are authoritative and override this. The model's `thinking_complete=False`
        is consulted in combination with this heuristic; if either is missing, the
        OWNER does not extend the cycle.
    """

    if not thought_text:
        return False
    stripped = thought_text.rstrip()
    if not stripped:
        return False
    # Trailing ellipsis (ASCII or Unicode) or question mark (ASCII or full-width) ⇒ hook.
    if stripped.endswith(("...", "…", "?", "？")):
        return True
    # Substring match (case-insensitive for English phrases) for the bounded set.
    lowered = stripped.lower()
    return any(hook in lowered for hook in _UNRESOLVED_REASONING_HOOKS)


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

    # R95: parse the 5 R95 fields (plus the R81 hormone forecast).
    # The 11 R93-R94 behavior-suggestive fields (`reply_text`,
    # `i_want_to_use_tool`, `wants_to_continue`, `continue_reason`,
    # `proposed_action`, `self_revision`, `action_intent`, `target_user_id`,
    # plus 3 companion sub-fields) are silently ignored if present in the
    # payload (forward-compat with in-flight model checkpoints that still
    # produce them).
    thinking_complete = _optional_thinking_complete(payload)
    channel_request = _optional_channel_request(payload)
    hormone_prediction = _optional_hormone_prediction(payload)
    tool_op = _optional_tool_op(payload)
    tool_params = _optional_tool_params(payload)

    return StructuredThoughtEvidence(
        thought_text=thought_value.strip(),
        model_sufficiency=float(sufficiency_value),
        thinking_complete=thinking_complete,
        channel_request=channel_request,
        hormone_prediction=hormone_prediction,
        tool_op=tool_op,
        tool_params=tool_params,
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
        model_thinking_complete = True
    else:
        # Bounded blend: the model's self-assessed sufficiency measurably moves the result
        # while the owner stays anchored on retrieval evidence.
        blended = (
            _MODEL_SIGNAL_WEIGHT * evidence.model_sufficiency
            + (1.0 - _MODEL_SIGNAL_WEIGHT) * retrieval_sufficiency
        )
        sufficiency_level = round(min(1.0, max(0.0, blended)), 4)
        # R95: the model's `thinking_complete` is the replacement for `wants_to_continue`
        # and is ADVISORY only; the OWNER's continuation floors are authoritative.
        model_thinking_complete = evidence.thinking_complete

    # R95: continuation decision. The OWNER's two floors
    # (`runtime_forces_continue`, `low_context_forces_continue`) are authoritative. The
    # model's `thinking_complete=False` signal is ADVISORY — the OWNER consults it but
    # does not blindly follow it. The heuristic for "unresolved reasoning hooks" is a
    # bounded string check on the thought text (trailing `...` / `?`, or specific
    # English/Chinese phrases indicating mid-thought). The heuristic is documented as
    # advisory-only and is intentionally bounded to avoid over-interpretation.
    if runtime_forces_continue or low_context_forces_continue:
        continuation_requested = True
        continuation_reason = "need_more_context"
    elif evidence is None:
        # Retrieval-only baseline (deterministic path): exactly the prior behavior.
        continuation_requested = False
        continuation_reason = "sufficient_for_current_cycle"
    elif not model_thinking_complete and _has_unresolved_reasoning_hooks(
        evidence.thought_text
    ):
        # Advisory path: the model says it's mid-thought AND the thought text has
        # unresolved reasoning hooks. OWNER accepts the signal as a soft continuation
        # trigger. When the model says thinking_complete=True (or the text has no
        # hooks), the OWNER closes the cycle regardless of the signal.
        continuation_requested = True
        continuation_reason = "model_thinking_incomplete"
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
        # R95: single-point action decision. `tool_op` is the sole primary action-class
        # field: empty/missing ⇒ no action (cycle closes internal-only, `action_proposal`
        # stays None); non-empty ⇒ the model picked this op and the OWNER builds a tool
        # proposal. The LLM's `tool_params` is passed through verbatim — the engine does
        # NOT auto-inject `target_user_id` from any source (no `current_operator_id`
        # projection, no channel-derived `source_user_id`, no static default).
        # The deterministic offline path (evidence is None) is data-driven (R95 followup
        # C3): the OWNER derives the default op from
        # `request.prompt_contract_summary["available_channel_ops"]` — the channel
        # subsystem (or its shim projection) is the sole source of truth. When no
        # channel op is available, the cycle closes internal-only (R93-era
        # `behavior_name="reply_message"` hardcode REMOVED).
        if evidence is None:
            default_op = _default_op_from_request(request)
            if default_op is None:
                action_proposal = None
            else:
                # R95 followup (C3): the offline default op is now data-driven from
                # the channel subsystem projection. The proposal carries
                # `outbound_text=thought.content` so the deterministic offline
                # assembly's end-to-end rendering is preserved (the rendered text is
                # the OWNER's thought, not a literal "reply_message" hardcode).
                action_proposal = ThoughtActionProposalCarrier(
                    proposal_id=f"thought-action:{request.request_id}",
                    scope="external",
                    behavior_name=default_op,
                    requested_op=default_op,
                    preferred_channels=_DEFAULT_OFFLINE_PREFERRED_CHANNELS,
                    outbound_text=thought.content,
                    outbound_intensity=_DEFAULT_OFFLINE_OUTBOUND_INTENSITY,
                    reason_trace=("thought judged sufficient for current cycle",),
                    governance_hints={"requires_identity_review": False},
                )
        elif evidence.tool_op:
            # The model picked an op. Build a tool proposal with that op + params.
            # The LLM's tool_params is passed through verbatim. The planner (R85/R86)
            # validates tool_params against the op's required_params (e.g.
            # `cli.reply_message` requires `outbound_text` and `target_user_id`;
            # `fs_read` requires `path`; etc.). If the LLM omitted a required
            # param, the planner rejects — this is a real LLM error, not a
            # system design issue. R95 makes no attempt to populate the field.
            ready_channels = request.prompt_contract_summary.get("ready_channels", ())
            preferred_channels = (
                tuple(ready_channels) if isinstance(ready_channels, tuple) else ()
            )
            action_proposal = ThoughtActionProposalCarrier(
                proposal_id=f"thought-action:{request.request_id}",
                scope="external",
                behavior_name=evidence.tool_op,
                requested_op=evidence.tool_op,
                preferred_channels=preferred_channels,
                outbound_text=None,
                outbound_intensity=0.75,
                reason_trace=("thought picked a tool op for the current cycle",),
                governance_hints={"requires_identity_review": False},
                op_params=evidence.tool_params,
            )
        # else: tool_op empty/missing ⇒ action_proposal stays None (no_action).
    # Self-revision: R95 OWNER-only. The autobiographical + sufficiency floor is the
    # ONLY gate. The model has no say in self-revision (no `intends_self_revision`
    # field, no `self_revision` envelope object). The OWNER constructs a
    # `SelfRevisionProposalCarrier` when the floor is met, regardless of any model
    # field. This is consistent with the R95 principle: behavioral decisions belong
    # to the OWNER, not the LLM.
    self_revision_allowed_by_owner = bool(autobiographical) and sufficiency_level >= 0.75
    self_revision_requested = self_revision_allowed_by_owner
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
        ]
        # R95: render the "Available channels" section when the composition
        # projects ready channels × ops. The section enumerates each driver and
        # each op it offers (op_name, required_params, effect_class, risk_class,
        # bound_user_ids). The LLM is free to pick any op; the runtime
        # validates `tool_params` against the op's `required_params` and routes
        # to the matching channel automatically. `reply_message` is NOT
        # special-cased — it appears as one of the `cli` driver's ops
        # alongside any other op the driver offers, and the LLM autonomously
        # decides when to use it (e.g. if a message came from `qq`, the LLM
        # picks `qq`'s send op, not `cli.reply_message`).
        available_channel_ops = summary.get("available_channel_ops")
        if isinstance(available_channel_ops, (tuple, list)) and available_channel_ops:
            system_lines.append("")
            system_lines.append(
                "Available channels (you may pick any one tool op per cycle, or pick none):"
            )
            # Group by driver_id for readability.
            grouped: dict[str, list[dict[str, object]]] = {}
            for op_info in available_channel_ops:
                if not isinstance(op_info, dict):
                    continue
                driver_id = str(op_info.get("driver_id", ""))
                if not driver_id:
                    continue
                grouped.setdefault(driver_id, []).append(op_info)
            for index, (driver_id, ops) in enumerate(grouped.items(), start=1):
                system_lines.append(f"  {index}. {driver_id}")
                for op in ops:
                    op_name = str(op.get("op_name", ""))
                    required_params = op.get("required_params", [])
                    required_str = (
                        ", ".join(str(p) for p in required_params) if required_params else "none"
                    )
                    effect_class = str(op.get("effect_class", ""))
                    risk_class = str(op.get("risk_class", ""))
                    bound_user_ids = op.get("bound_user_ids", ("*",))
                    if isinstance(bound_user_ids, (tuple, list)) and bound_user_ids:
                        if bound_user_ids == ("*",):
                            bound_str = "any user"
                        else:
                            bound_str = ", ".join(str(u) for u in bound_user_ids)
                    else:
                        bound_str = "any user"
                    system_lines.append(f"     - {op_name}:")
                    system_lines.append(
                        f"         required_params=[{required_str}]"
                    )
                    if effect_class or risk_class:
                        system_lines.append(
                            f"         effect_class={effect_class}, risk_class={risk_class}"
                        )
                    if bound_str != "any user":
                        system_lines.append(f"         bound_user_ids=[{bound_str}]")
            system_lines.append("")
            system_lines.append(
                "You may pick any one op from this list, or pick none (the cycle closes"
                " internal-only). When you do pick an op, fill `tool_op` with the op name"
                " and `tool_params` with the required params."
            )
        # R95: the JSON envelope has 5 user-facing fields. The 11 R93-R94
        # behavior-suggestive fields (`reply_text`, `i_want_to_use_tool`,
        # `wants_to_continue`, `continue_reason`, `proposed_action`,
        # `self_revision`, `action_intent`, `target_user_id`, plus 3
        # companion sub-fields) are all REMOVED. `tool_op` is the single
        # primary action-class field: empty/missing means "no action";
        # non-empty means "the model picked this op".
        system_lines.append("")
        system_lines.append("Respond with a single JSON object only, no prose outside it, with this shape:")
        system_lines.append("{")
        system_lines.append('  "thought": "<concise internal thought>",')
        system_lines.append('  "sufficiency": <number 0..1, how complete this cycle\'s thinking is>,')
        system_lines.append('  "tool_op": "<op name from the Available channels list, or omit/empty for no action>",')
        system_lines.append('  "tool_params": {<params for the chosen op, or omit/empty>},')
        system_lines.append('  "thinking_complete": <bool, default true; false only if you want the owner to consider continuing>,')
        system_lines.append('  "channel_request": {<optional; describe a channel/op you wish existed but doesn\'t>},')
        system_lines.append('  "hormone_response_i_predict": {<optional forecast>},')
        system_lines.append("}")
        system_lines.append("")
        system_lines.append("Decision guidance:")
        system_lines.append(
            "  - For each cycle, decide whether to act. If you do not act, leave"
        )
        system_lines.append(
            "    `tool_op` empty/missing; the cycle closes internal-only."
        )
        system_lines.append(
            "  - If you do act, pick one op from the Available channels list. The"
        )
        system_lines.append(
            "    runtime validates `tool_params` against the op's `required_params`"
        )
        system_lines.append(
            "    and routes to the matching channel automatically."
        )
        system_lines.append(
            "  - Identity is your content decision, not the runtime's: the runtime"
        )
        system_lines.append(
            "    does NOT auto-fill any user identifier. If the op you pick"
        )
        system_lines.append(
            "    declares a user-id field in its `required_params` list and you"
        )
        system_lines.append(
            "    have a value for it (e.g. it appears in the inbound message"
        )
        system_lines.append(
            "    context), include it under the matching key in `tool_params`."
        )
        system_lines.append(
            "    The runtime does not verify or trust this value; it is a label"
        )
        system_lines.append(
            "    for the receiving channel, not an authentication claim."
        )
        system_lines.append(
            "  - Do NOT reflexively reply. A low-salience or acknowledgment stimulus"
        )
        system_lines.append(
            "    may legitimately close with no action."
        )
        system_lines.append(
            "  - If you find yourself wanting an op that no channel offers, fill"
        )
        system_lines.append(
            "    `channel_request` so a future iteration can track the gap."
        )
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
