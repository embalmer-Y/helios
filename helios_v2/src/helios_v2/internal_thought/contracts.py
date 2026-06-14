"""Owner: internal thought loop.

Owns:
- fired-path internal-thought contracts
- thought-cycle result, trace, and optional proposal carrier contracts
- internal-thought API and publication ops

Does not own:
- thought gating
- directed retrieval
- memory persistence
- planner, executor, or governance acceptance
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable

from helios_v2.directed_retrieval import ThoughtWindowBundle
from helios_v2.thought_gating import ContinuationPressureState, ThoughtGateResult


class InternalThoughtError(RuntimeError):
    """Hard-stop error raised when internal-thought owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise InternalThoughtError(f"{name} must be within [0.0, 1.0]")


ThoughtExecutionStatus = Literal[
    "completed",
    "insufficient_generation",
    "capability_rejected_cycle",
    "request_invalid",
]
InternalThoughtLearnedParameterCategory = Literal[
    "thought_generation_policy",
    "sufficiency_policy",
    "proposal_emission_policy",
]

_THOUGHT_EXECUTION_STATUSES = {
    "completed",
    "insufficient_generation",
    "capability_rejected_cycle",
    "request_invalid",
}
_ACTION_PROPOSAL_SCOPES = {"internal", "external"}

# R81: the nine neuromodulator channel names the model may forecast in `hormone_response_i_predict`.
# Owner-local convention (a documented mirror of the `04` `NeuromodulatorLevels` shape); `11` keeps
# the forecast an owner-neutral channel->value mapping and imports no `04` contract, so the affect
# owner stays upstream-independent of the thought owner.
_HORMONE_PREDICTION_CHANNELS = (
    "dopamine",
    "norepinephrine",
    "serotonin",
    "acetylcholine",
    "cortisol",
    "oxytocin",
    "opioid_tone",
    "excitation",
    "inhibition",
)


# R91: bounded length cap and explicit truncation suffix for the additive `present_field_summary`.
# Empirical R91 probe runs (`scripts/r91_probes/`) show the model engages content well within ~600
# chars of present-field text plus the existing internal-state line; truncation is deterministic and
# carries an explicit suffix so any over-cap input is honestly visible rather than silently clipped.
PRESENT_FIELD_SUMMARY_MAX_CHARS = 600
PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX = "…(truncated)"


# R93: bounded length cap and explicit truncation suffix for the additive `intended_reply_text` slot
# on `StructuredThoughtEvidence`. The model fills `i_want_to_say` with operator-addressed reply text
# (e.g. one to a few short paragraphs); 2000 chars is well below any transport driver's outbound
# buffer while still allowing richer reply paragraphs than the much-shorter present-field cap.
# Truncation is deterministic and carries the same explicit suffix so over-cap input is honestly
# visible rather than silently clipped.
INTENDED_REPLY_TEXT_MAX_CHARS = 2000
INTENDED_REPLY_TEXT_TRUNCATION_SUFFIX = "…(truncated)"


@dataclass(frozen=True)
class InternalThoughtConfig:
    """Expose the confirmed initialization and learned-policy surface for internal thought."""

    legal_min_sufficiency: float
    legal_max_sufficiency: float
    thought_bootstrap_id: str
    mandatory_learned_parameters: tuple[InternalThoughtLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "thought_generation_policy",
            "sufficiency_policy",
            "proposal_emission_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise InternalThoughtError(
                "Internal-thought config must declare the confirmed mandatory learned-parameter categories"
            )
        _validate_unit_interval("InternalThoughtConfig.legal_min_sufficiency", self.legal_min_sufficiency)
        _validate_unit_interval("InternalThoughtConfig.legal_max_sufficiency", self.legal_max_sufficiency)
        if self.legal_min_sufficiency > self.legal_max_sufficiency:
            raise InternalThoughtError("Internal-thought config sufficiency range is inverted")
        if not self.thought_bootstrap_id:
            raise InternalThoughtError("InternalThoughtConfig must declare a non-empty thought_bootstrap_id")


@dataclass(frozen=True)
class InternalThoughtRequest:
    """Explicit normalized fired-path thought input for one cycle."""

    request_id: str
    source_gate_result_id: str
    source_retrieval_bundle_id: str
    source_continuation_active: bool
    internal_state_summary: str
    prompt_contract_summary: Mapping[str, object]
    tick_id: int | None
    # R91: additive optional present-field text projected from the same-frame `08`
    # `ReportableConsciousContent` (focal_summary + salient_tokens) plus the optional temporal
    # source's elapsed-rest pacing. When None the request is byte-for-byte the pre-R91 shape;
    # `11._build_messages` only renders the `Present field:` line when this is non-None.
    present_field_summary: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise InternalThoughtError("InternalThoughtRequest must declare a non-empty request_id")
        if not self.source_gate_result_id:
            raise InternalThoughtError("InternalThoughtRequest must declare a non-empty source_gate_result_id")
        if not self.source_retrieval_bundle_id:
            raise InternalThoughtError(
                "InternalThoughtRequest must declare a non-empty source_retrieval_bundle_id"
            )
        if not self.internal_state_summary:
            raise InternalThoughtError("InternalThoughtRequest must declare a non-empty internal_state_summary")
        summary = MappingProxyType(dict(self.prompt_contract_summary))
        if not summary:
            raise InternalThoughtError("InternalThoughtRequest must declare non-empty prompt_contract_summary")
        for key in summary:
            if not key:
                raise InternalThoughtError(
                    "InternalThoughtRequest prompt_contract_summary must not contain empty keys"
                )
        object.__setattr__(self, "prompt_contract_summary", summary)
        # R91: validate + bound the additive present-field text. None preserves prior behavior;
        # a non-None value must be non-blank, and is deterministically truncated with an explicit
        # suffix when over the owner-defined character cap. Truncation is honest (never silent).
        if self.present_field_summary is not None:
            value = self.present_field_summary
            if not value or not value.strip():
                raise InternalThoughtError(
                    "InternalThoughtRequest.present_field_summary must not be blank when set"
                )
            if len(value) > PRESENT_FIELD_SUMMARY_MAX_CHARS:
                cap = PRESENT_FIELD_SUMMARY_MAX_CHARS - len(PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX)
                truncated = value[:cap] + PRESENT_FIELD_SUMMARY_TRUNCATION_SUFFIX
                object.__setattr__(self, "present_field_summary", truncated)


@dataclass(frozen=True)
class ThoughtContent:
    """Successful internal-thought payload for one fired cycle."""

    thought_id: str
    thought_type: str
    content: str
    source_path: str
    llm_used: bool
    fallback_used: bool

    def __post_init__(self) -> None:
        if not self.thought_id:
            raise InternalThoughtError("ThoughtContent must declare a non-empty thought_id")
        if not self.thought_type:
            raise InternalThoughtError("ThoughtContent must declare a non-empty thought_type")
        if not self.content:
            raise InternalThoughtError("ThoughtContent must declare non-empty content")
        if not self.source_path:
            raise InternalThoughtError("ThoughtContent must declare a non-empty source_path")


@dataclass(frozen=True)
class MemoryHandoffDirective:
    """Retrieval-facing carry contract published by the thought owner for later cycles."""

    recall_intent: str
    selected_memory_refs: tuple[str, ...]
    saved_for_next_tick: bool
    source_thought_id: str

    def __post_init__(self) -> None:
        if self.saved_for_next_tick and not self.recall_intent:
            raise InternalThoughtError(
                "MemoryHandoffDirective saved_for_next_tick requires non-empty recall_intent"
            )
        if self.saved_for_next_tick and not self.source_thought_id:
            raise InternalThoughtError(
                "MemoryHandoffDirective saved_for_next_tick requires non-empty source_thought_id"
            )
        if any(not ref for ref in self.selected_memory_refs):
            raise InternalThoughtError("MemoryHandoffDirective selected_memory_refs must not contain empty values")


@dataclass(frozen=True)
class ThoughtActionProposalCarrier:
    """Optional action-proposal carrier emitted by the thought owner only as a proposal."""

    proposal_id: str
    scope: Literal["internal", "external"]
    behavior_name: str
    requested_op: str
    preferred_channels: tuple[str, ...]
    outbound_text: str | None
    outbound_intensity: float
    reason_trace: tuple[str, ...]
    governance_hints: Mapping[str, object]
    # R85: generic bounded tool-op parameters (e.g. a file path/content). Model-supplied content
    # carried verbatim to `12`; the owning driver's per-op spec, read by `13`, decides which keys are
    # required. Defaults to empty so the reply path is byte-for-byte unchanged.
    op_params: Mapping[str, object] = MappingProxyType({})

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise InternalThoughtError("ThoughtActionProposalCarrier must declare a non-empty proposal_id")
        if self.scope not in _ACTION_PROPOSAL_SCOPES:
            raise InternalThoughtError(
                "ThoughtActionProposalCarrier scope must use the fixed taxonomy"
            )
        if not self.behavior_name:
            raise InternalThoughtError("ThoughtActionProposalCarrier must declare a non-empty behavior_name")
        if not self.requested_op:
            raise InternalThoughtError("ThoughtActionProposalCarrier must declare a non-empty requested_op")
        if self.scope == "external" and self.outbound_text is not None and not self.outbound_text:
            raise InternalThoughtError("ThoughtActionProposalCarrier outbound_text must not be empty")
        _validate_unit_interval("ThoughtActionProposalCarrier.outbound_intensity", self.outbound_intensity)
        if not self.reason_trace or any(not item for item in self.reason_trace):
            raise InternalThoughtError(
                "ThoughtActionProposalCarrier must declare non-empty reason_trace items"
            )
        if any(not channel for channel in self.preferred_channels):
            raise InternalThoughtError(
                "ThoughtActionProposalCarrier preferred_channels must not contain empty values"
            )
        hints = MappingProxyType(dict(self.governance_hints))
        for key in hints:
            if not key:
                raise InternalThoughtError(
                    "ThoughtActionProposalCarrier governance_hints must not contain empty keys"
                )
        object.__setattr__(self, "governance_hints", hints)
        op_params = MappingProxyType(dict(self.op_params))
        for key, value in op_params.items():
            if not key:
                raise InternalThoughtError(
                    "ThoughtActionProposalCarrier op_params must not contain empty keys"
                )
            if isinstance(value, (str, int, float, bool)):
                continue
            # R86: a one-level tuple of scalars (e.g. a command's `args`) is allowed so a tool op can
            # carry an argument vector; deeper nesting is rejected.
            if isinstance(value, tuple) and all(
                isinstance(item, (str, int, float, bool)) for item in value
            ):
                continue
            raise InternalThoughtError(
                f"ThoughtActionProposalCarrier op_params['{key}'] must be a scalar (str/number/bool) "
                "or a tuple of scalars"
            )
        object.__setattr__(self, "op_params", op_params)


@dataclass(frozen=True)
class SelfRevisionProposalCarrier:
    """Optional self-revision proposal carrier emitted by the thought owner only as a proposal."""

    proposal_id: str
    revision_kind: str
    requested_change_summary: str
    reason_trace: str

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise InternalThoughtError("SelfRevisionProposalCarrier must declare a non-empty proposal_id")
        if not self.revision_kind:
            raise InternalThoughtError("SelfRevisionProposalCarrier must declare a non-empty revision_kind")
        if not self.requested_change_summary:
            raise InternalThoughtError(
                "SelfRevisionProposalCarrier must declare a non-empty requested_change_summary"
            )
        if not self.reason_trace:
            raise InternalThoughtError("SelfRevisionProposalCarrier must declare a non-empty reason_trace")


@dataclass(frozen=True)
class InternalThoughtTrace:
    """Bounded observability contract for one fired-path thought cycle."""

    triggered: bool
    trigger_reason: str
    llm_used: bool
    fallback_used: bool
    execution_status: ThoughtExecutionStatus
    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    recall_intent: str
    action_explicit: bool
    action_parse_status: str

    def __post_init__(self) -> None:
        if not self.triggered:
            raise InternalThoughtError("InternalThoughtTrace must represent a fired-path cycle")
        if not self.trigger_reason:
            raise InternalThoughtError("InternalThoughtTrace must declare a non-empty trigger_reason")
        if self.execution_status not in _THOUGHT_EXECUTION_STATUSES:
            raise InternalThoughtError("InternalThoughtTrace execution_status must use the fixed taxonomy")
        _validate_unit_interval("InternalThoughtTrace.sufficiency_level", self.sufficiency_level)
        if self.continuation_requested and not self.continuation_reason:
            raise InternalThoughtError(
                "InternalThoughtTrace continuation_requested requires non-empty continuation_reason"
            )
        if self.continuation_requested and not self.recall_intent:
            raise InternalThoughtError(
                "InternalThoughtTrace continuation_requested requires non-empty recall_intent"
            )
        if not self.action_parse_status:
            raise InternalThoughtError("InternalThoughtTrace must declare a non-empty action_parse_status")


@dataclass(frozen=True)
class ThoughtCycleResult:
    """Immutable formal thought-cycle result for one fired-thought cycle."""

    result_id: str
    source_request_id: str
    execution_status: ThoughtExecutionStatus
    thought: ThoughtContent | None
    trigger_reason: str
    sufficiency_level: float
    continuation_requested: bool
    continuation_reason: str
    continuation_pressure_delta: float
    recall_intent: str
    memory_handoff: MemoryHandoffDirective | None
    action_proposal: ThoughtActionProposalCarrier | None
    self_revision_proposal: SelfRevisionProposalCarrier | None
    tick_id: int | None
    # R81: optional model-supplied subjective hormone forecast (channel name -> `[0, 1]`), carried
    # to the next tick's `04` corroborator. Model-supplied content, never an owner judgment; it
    # changes no sufficiency/continuation/recall/proposal decision.
    hormone_response_i_predict: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        if not self.result_id:
            raise InternalThoughtError("ThoughtCycleResult must declare a non-empty result_id")
        if not self.source_request_id:
            raise InternalThoughtError("ThoughtCycleResult must declare a non-empty source_request_id")
        if self.execution_status not in _THOUGHT_EXECUTION_STATUSES:
            raise InternalThoughtError("ThoughtCycleResult execution_status must use the fixed taxonomy")
        if not self.trigger_reason:
            raise InternalThoughtError("ThoughtCycleResult must declare a non-empty trigger_reason")
        _validate_unit_interval("ThoughtCycleResult.sufficiency_level", self.sufficiency_level)
        _validate_unit_interval(
            "ThoughtCycleResult.continuation_pressure_delta",
            self.continuation_pressure_delta,
        )
        self._validate_hormone_prediction()
        if self.execution_status == "completed":
            if self.thought is None:
                raise InternalThoughtError(
                    "ThoughtCycleResult with execution_status='completed' must publish thought"
                )
        else:
            if self.thought is not None:
                raise InternalThoughtError(
                    "Non-success ThoughtCycleResult must not publish successful ThoughtContent"
                )
            if self.action_proposal is not None or self.self_revision_proposal is not None:
                raise InternalThoughtError(
                    "Non-success ThoughtCycleResult must not publish optional downstream proposals"
                )
        if self.continuation_requested and not self.continuation_reason:
            raise InternalThoughtError(
                "ThoughtCycleResult continuation_requested requires non-empty continuation_reason"
            )
        if self.continuation_requested and not self.recall_intent:
            raise InternalThoughtError(
                "ThoughtCycleResult continuation_requested requires non-empty recall_intent"
            )
        if self.memory_handoff is not None and self.thought is not None:
            if self.memory_handoff.source_thought_id != self.thought.thought_id:
                raise InternalThoughtError(
                    "MemoryHandoffDirective must preserve the source thought id of the published ThoughtContent"
                )

    def _validate_hormone_prediction(self) -> None:
        """Owner: internal thought loop (R81). Validate/normalize the optional hormone forecast.

        `None` is allowed (no forecast). When present it must be a mapping whose recognized channel
        keys (`_HORMONE_PREDICTION_CHANNELS`) carry numeric `[0, 1]` values; unrecognized keys are
        rejected so the forecast cannot smuggle arbitrary content. The normalized forecast is frozen
        as a `MappingProxyType`. It is model-supplied content carried to `04`; it is not validated as
        an owner decision.
        """

        forecast = self.hormone_response_i_predict
        if forecast is None:
            return
        if not isinstance(forecast, Mapping):
            raise InternalThoughtError(
                "ThoughtCycleResult.hormone_response_i_predict must be a mapping or None"
            )
        normalized: dict[str, float] = {}
        for key, value in forecast.items():
            if key not in _HORMONE_PREDICTION_CHANNELS:
                raise InternalThoughtError(
                    f"ThoughtCycleResult.hormone_response_i_predict has unknown channel '{key}'"
                )
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InternalThoughtError(
                    f"ThoughtCycleResult.hormone_response_i_predict['{key}'] must be numeric"
                )
            if value < 0.0 or value > 1.0:
                raise InternalThoughtError(
                    f"ThoughtCycleResult.hormone_response_i_predict['{key}'] must be within [0, 1]"
                )
            normalized[key] = float(value)
        object.__setattr__(self, "hormone_response_i_predict", MappingProxyType(normalized))


@dataclass(frozen=True)
class RunInternalThoughtOp:
    """Runtime-visible request op for one fired thought cycle."""

    op_name: str
    owner: str
    request_id: str
    gate_result_id: str
    retrieval_bundle_id: str


@dataclass(frozen=True)
class PublishThoughtCycleResultOp:
    """Runtime-visible publication op for one formal thought-cycle result."""

    op_name: str
    owner: str
    result_id: str
    execution_status: ThoughtExecutionStatus
    continuation_requested: bool
    has_action_proposal: bool
    has_self_revision_proposal: bool


@runtime_checkable
class InternalThoughtAPI(Protocol):
    """Owner: internal thought loop API."""

    def run_thought_cycle(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        continuation_state: ContinuationPressureState,
        request: InternalThoughtRequest,
    ) -> tuple[ThoughtCycleResult, InternalThoughtTrace]:
        """Return one formal thought-cycle result and one bounded trace for a fired cycle."""

    def build_run_op(
        self,
        gate_result: ThoughtGateResult,
        retrieval_bundle: ThoughtWindowBundle,
        request: InternalThoughtRequest,
    ) -> RunInternalThoughtOp:
        """Return one request op describing internal-thought execution."""

    def build_publish_result_op(
        self,
        result: ThoughtCycleResult,
    ) -> PublishThoughtCycleResultOp:
        """Return one publication op describing thought-cycle result publication."""
