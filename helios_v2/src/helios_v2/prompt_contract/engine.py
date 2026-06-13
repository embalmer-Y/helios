"""Owner: embodied subjective prompt and action autonomy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, runtime_checkable

from helios_v2.outward_expression import BuildOutwardExpressionRequestOp, OutwardExpressionRequest

from .contracts import (
    BuildEmbodiedPromptOp,
    EmbodiedPromptAPI,
    EmbodiedPromptConfig,
    EmbodiedPromptContract,
    EmbodiedPromptRequest,
    OutwardExpressionPromptView,
    PromptActionBoundary,
    PromptContractError,
    PromptContractLayer,
    PublishEmbodiedPromptContractOp,
    PublishOutwardExpressionPromptViewOp,
)


def _require_text(mapping: dict[str, object], key: str, owner_name: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise PromptContractError(f"{owner_name} must declare non-empty {key}")
    return value


@runtime_checkable
class EmbodiedPromptPath(Protocol):
    def build(
        self,
        request: EmbodiedPromptRequest,
        config: EmbodiedPromptConfig,
    ) -> EmbodiedPromptContract:
        """Return one deterministic embodied prompt contract for one normalized request."""


@dataclass
class FirstVersionEmbodiedPromptPath(EmbodiedPromptPath):
    """Owner-private deterministic first-version embodied prompt path."""

    def build(
        self,
        request: EmbodiedPromptRequest,
        config: EmbodiedPromptConfig,
    ) -> EmbodiedPromptContract:
        stimulus_summary = dict(request.stimulus_summary)
        state_summary = dict(request.state_summary)
        retrieval_summary = dict(request.retrieval_summary)
        capability_summary = dict(request.capability_summary)
        identity_boundary_summary = dict(request.identity_boundary_summary)

        available_channels = capability_summary.get("available_channels")
        if not isinstance(available_channels, tuple) or not available_channels:
            raise PromptContractError(
                "EmbodiedPromptRequest capability_summary must declare non-empty available_channels"
            )
        available_ops = capability_summary.get("available_ops")
        if not isinstance(available_ops, tuple) or not available_ops:
            raise PromptContractError(
                "EmbodiedPromptRequest capability_summary must declare non-empty available_ops"
            )
        forbidden_capabilities = capability_summary.get("forbidden_capabilities")
        if not isinstance(forbidden_capabilities, tuple):
            raise PromptContractError(
                "EmbodiedPromptRequest capability_summary must declare forbidden_capabilities"
            )

        layers = (
            PromptContractLayer(
                layer_name="present_field",
                content=_require_text(stimulus_summary, "present_field", "stimulus_summary"),
                required=True,
            ),
            PromptContractLayer(
                layer_name="embodied_state",
                content=(
                    f"Affect: {_require_text(state_summary, 'affective_summary', 'state_summary')}. "
                    f"Continuation: {_require_text(state_summary, 'continuation_summary', 'state_summary')}."
                ),
                required=True,
            ),
            PromptContractLayer(
                layer_name="memory_and_continuity",
                content=(
                    f"Retrieval: {_require_text(retrieval_summary, 'retrieval_context', 'retrieval_summary')}. "
                    f"Current continuity obligation: {_require_text(retrieval_summary, 'continuity_context', 'retrieval_summary')}."
                ),
                required=True,
            ),
            PromptContractLayer(
                layer_name="action_autonomy",
                content=(
                    f"Available channels: {', '.join(available_channels)}. "
                    f"Available ops: {', '.join(available_ops)}. "
                    f"Identity boundary: {_require_text(identity_boundary_summary, 'identity_boundary', 'identity_boundary_summary')}. "
                    f"Planner, channel, and governance remain final authorities outside this prompt owner."
                ),
                required=True,
            ),
            PromptContractLayer(
                layer_name="anti_theatrical_constraints",
                content=(
                    "Do not perform empty self-consciousness theater. "
                    "Use first-person phrasing only when grounded in current evidence, current state, or a current unresolved obligation. "
                    "Do not invent channels, powers, or invisible execution authority."
                ),
                required=True,
            ),
            PromptContractLayer(
                layer_name="consumer_orientation",
                content=self._consumer_orientation(request.consumer_kind),
                required=True,
            ),
        )
        if len(layers) > config.max_layer_count:
            raise PromptContractError("Embodied prompt layer count exceeds the configured maximum")

        action_boundary = PromptActionBoundary(
            supports_internal_action=request.consumer_kind == "thought",
            supports_external_action_proposal=True,
            supports_self_revision_proposal=request.consumer_kind == "thought",
            forbidden_capabilities=forbidden_capabilities,
            final_authorities=("planner", "channel", "identity_governance"),
        )
        return EmbodiedPromptContract(
            contract_id=f"embodied-prompt-contract:{request.request_id}",
            consumer_kind=request.consumer_kind,
            source_request_id=request.request_id,
            layers=layers,
            action_boundary=action_boundary,
            capability_snapshot={
                "available_channels": available_channels,
                "available_ops": available_ops,
                "forbidden_capabilities": forbidden_capabilities,
            },
            anti_theatrical_constraints=(
                "avoid empty self-consciousness performance",
                "stay anchored to current user and current field",
                "do not invent execution authority",
            ),
        )

    def _consumer_orientation(self, consumer_kind: str) -> str:
        if consumer_kind == "thought":
            return (
                "Thought consumer: integrate the current field into grounded internal reasoning, "
                "and emit only formal internal, external-action, or self-revision proposals."
            )
        return (
            "Outward-expression consumer: remain user-anchored, respect channel and planner boundaries, "
            "and do not reinterpret prompt text as direct execution authority."
        )


_V3_PROMPT_BOOTSTRAP_ID = "embodied-prompt-bootstrap:v3"

_V3_RESPONSE_SCHEMA = (
    "Respond with a single JSON object with exactly these keys: "
    "what_i_feel, what_i_think, i_want_to_say, i_will_send_it, i_send_through, "
    "i_want_to_act, act_type, remember_this, remember_because, i_want_to_think_more, "
    "think_more_about. Hard rules: i_will_send_it is true only if i_want_to_say is not null; "
    "i_send_through is non-null only if i_will_send_it is true and only one of the ready channels; "
    "remember_because is non-null only if remember_this is true; think_more_about is non-null "
    "only if i_want_to_think_more is true."
)

_V3_ANTI_THEATRICAL = (
    "Speak in the first person from inside the state given. State only what the state supports, "
    "and return null when a field is unsupported. Do not describe yourself as an AI, a model, a "
    "runtime, or a role, and do not narrate 'as a ...'."
)


@dataclass
class OwnerGroundedEmbodiedPromptPath(EmbodiedPromptPath):
    """Owner-private v3 embodied prompt path: an owner-grounded first-person embodied contract.

    Owner: embodied subjective prompt and action autonomy.

    Purpose:
        Render a first-person embodied contract from real owner state: identity from the injected
        owner-sourced self-summary (never a hardcoded identity assertion), a
        focused/peripheral/filtered attention field, and a ready-channel list, plus
        natural-language schema fields and an upgraded grounding-based anti-theatrical rule.
        Identity stays owned by `14`; this path is a formatter.

    Failure semantics:
        Raises `PromptContractError` on a non-v3 bootstrap id, or a missing/empty
        `identity_self_summary` / `attention_field` / `ready_channels` under v3.

    Notes:
        It reads additive keys the v3 request bridge fills (`identity_self_summary` in
        `identity_boundary_summary`, `attention_field` in `stimulus_summary`, `ready_channels`
        in `capability_summary`); it never hardcodes identity or channels.
    """

    def build(
        self,
        request: EmbodiedPromptRequest,
        config: EmbodiedPromptConfig,
    ) -> EmbodiedPromptContract:
        if config.prompt_bootstrap_id != _V3_PROMPT_BOOTSTRAP_ID:
            raise PromptContractError(
                "OwnerGroundedEmbodiedPromptPath requires the v3 prompt bootstrap id "
                f"'{_V3_PROMPT_BOOTSTRAP_ID}'"
            )
        stimulus_summary = dict(request.stimulus_summary)
        state_summary = dict(request.state_summary)
        capability_summary = dict(request.capability_summary)
        identity_boundary_summary = dict(request.identity_boundary_summary)

        identity_self_summary = _require_text(
            identity_boundary_summary, "identity_self_summary", "identity_boundary_summary"
        )
        present_field = _require_text(stimulus_summary, "present_field", "stimulus_summary")
        affective = _require_text(state_summary, "affective_summary", "state_summary")
        continuation = _require_text(state_summary, "continuation_summary", "state_summary")

        ready_channels = capability_summary.get("ready_channels")
        if not isinstance(ready_channels, tuple) or not ready_channels:
            raise PromptContractError(
                "v3 EmbodiedPromptRequest capability_summary must declare non-empty ready_channels"
            )
        available_ops = capability_summary.get("available_ops")
        if not isinstance(available_ops, tuple) or not available_ops:
            raise PromptContractError(
                "v3 EmbodiedPromptRequest capability_summary must declare non-empty available_ops"
            )
        forbidden_capabilities = capability_summary.get("forbidden_capabilities")
        if not isinstance(forbidden_capabilities, tuple):
            raise PromptContractError(
                "v3 EmbodiedPromptRequest capability_summary must declare forbidden_capabilities"
            )

        attention_field = stimulus_summary.get("attention_field")
        if not isinstance(attention_field, Mapping):
            raise PromptContractError(
                "v3 EmbodiedPromptRequest stimulus_summary must declare an attention_field mapping"
            )
        focused = attention_field.get("focused")
        if not isinstance(focused, str) or not focused:
            raise PromptContractError("v3 attention_field must declare a non-empty focused")
        peripheral = attention_field.get("peripheral", ())
        filtered = attention_field.get("filtered", ())
        if not isinstance(peripheral, tuple) or not isinstance(filtered, tuple):
            raise PromptContractError(
                "v3 attention_field peripheral and filtered must be tuples"
            )

        attention_text = (
            f"Focused: {focused}. "
            f"Peripheral: {', '.join(peripheral) if peripheral else 'none'}. "
            f"Filtered: {', '.join(filtered) if filtered else 'none'}."
        )

        layers = (
            PromptContractLayer(
                layer_name="identity_grounding",
                content=identity_self_summary,
                required=True,
            ),
            PromptContractLayer(
                layer_name="present_field",
                content=present_field,
                required=True,
            ),
            PromptContractLayer(
                layer_name="attention_breakdown",
                content=attention_text,
                required=True,
            ),
            PromptContractLayer(
                layer_name="embodied_state",
                content=f"Affect: {affective}. Continuation: {continuation}.",
                required=True,
            ),
            PromptContractLayer(
                layer_name="ready_channels",
                content=f"Ready channels: {', '.join(ready_channels)}.",
                required=True,
            ),
            PromptContractLayer(
                layer_name="response_schema",
                content=_V3_RESPONSE_SCHEMA,
                required=True,
            ),
            PromptContractLayer(
                layer_name="anti_theatrical",
                content=_V3_ANTI_THEATRICAL,
                required=True,
            ),
        )
        if len(layers) > config.max_layer_count:
            raise PromptContractError("Embodied prompt layer count exceeds the configured maximum")

        action_boundary = PromptActionBoundary(
            supports_internal_action=request.consumer_kind == "thought",
            supports_external_action_proposal=True,
            supports_self_revision_proposal=request.consumer_kind == "thought",
            forbidden_capabilities=forbidden_capabilities,
            final_authorities=("planner", "channel", "identity_governance"),
        )
        return EmbodiedPromptContract(
            contract_id=f"embodied-prompt-contract:{request.request_id}",
            consumer_kind=request.consumer_kind,
            source_request_id=request.request_id,
            layers=layers,
            action_boundary=action_boundary,
            capability_snapshot={
                "available_channels": ready_channels,
                "available_ops": available_ops,
                "forbidden_capabilities": forbidden_capabilities,
                "ready_channels": ready_channels,
            },
            anti_theatrical_constraints=(
                "first-person only when state-supported",
                "return null when a field is unsupported",
                "never self-describe as AI, model, runtime, or role",
            ),
        )


@dataclass
class EmbodiedPromptEngine(EmbodiedPromptAPI):
    """Assemble grounded prompt contracts from current-cycle owner outputs."""

    config: EmbodiedPromptConfig
    prompt_path: EmbodiedPromptPath | None

    def build_prompt_contract(self, request: EmbodiedPromptRequest) -> EmbodiedPromptContract:
        if self.prompt_path is None:
            raise PromptContractError("Embodied prompt owner requires an explicit prompt capability")
        contract = self.prompt_path.build(request, self.config)
        if contract.source_request_id != request.request_id:
            raise PromptContractError("EmbodiedPromptContract must preserve the source request id")
        if contract.consumer_kind != request.consumer_kind:
            raise PromptContractError("EmbodiedPromptContract must preserve the consumer kind")
        return contract

    def build_request_op(self, request: EmbodiedPromptRequest) -> BuildEmbodiedPromptOp:
        return BuildEmbodiedPromptOp(
            op_name="build_embodied_prompt_contract",
            owner="embodied_subjective_prompt_and_action_autonomy",
            request_id=request.request_id,
            consumer_kind=request.consumer_kind,
        )

    def build_publish_op(self, contract: EmbodiedPromptContract) -> PublishEmbodiedPromptContractOp:
        return PublishEmbodiedPromptContractOp(
            op_name="publish_embodied_prompt_contract",
            owner="embodied_subjective_prompt_and_action_autonomy",
            contract_id=contract.contract_id,
            consumer_kind=contract.consumer_kind,
            layer_count=len(contract.layers),
        )

    def build_outward_expression_view(
        self,
        contract: EmbodiedPromptContract,
    ) -> OutwardExpressionPromptView:
        if contract.consumer_kind != "outward_expression":
            raise PromptContractError(
                "Outward-expression view requires an outward_expression prompt contract"
            )
        available_channels = contract.capability_snapshot.get("available_channels")
        available_ops = contract.capability_snapshot.get("available_ops")
        forbidden_capabilities = contract.capability_snapshot.get("forbidden_capabilities")
        if not isinstance(available_channels, tuple) or not available_channels:
            raise PromptContractError(
                "EmbodiedPromptContract capability_snapshot must preserve available_channels"
            )
        if not isinstance(available_ops, tuple) or not available_ops:
            raise PromptContractError(
                "EmbodiedPromptContract capability_snapshot must preserve available_ops"
            )
        if not isinstance(forbidden_capabilities, tuple) or not forbidden_capabilities:
            raise PromptContractError(
                "EmbodiedPromptContract capability_snapshot must preserve forbidden_capabilities"
            )
        rendered_prompt = "\n".join(
            f"[{layer.layer_name}] {layer.content}"
            for layer in contract.layers
            if layer.required
        )
        return OutwardExpressionPromptView(
            view_id=f"outward-expression-view:{contract.contract_id}",
            source_contract_id=contract.contract_id,
            rendered_prompt=rendered_prompt,
            available_channels=available_channels,
            available_ops=available_ops,
            forbidden_capabilities=forbidden_capabilities,
            final_authorities=contract.action_boundary.final_authorities,
            anti_theatrical_constraints=contract.anti_theatrical_constraints,
        )

    def build_publish_outward_expression_view_op(
        self,
        view: OutwardExpressionPromptView,
    ) -> PublishOutwardExpressionPromptViewOp:
        return PublishOutwardExpressionPromptViewOp(
            op_name="publish_outward_expression_prompt_view",
            owner="embodied_subjective_prompt_and_action_autonomy",
            view_id=view.view_id,
            source_contract_id=view.source_contract_id,
            channel_count=len(view.available_channels),
        )

    def build_outward_expression_request(
        self,
        view: OutwardExpressionPromptView,
    ) -> OutwardExpressionRequest:
        return OutwardExpressionRequest(
            request_id=f"outward-expression-request:{view.view_id}",
            source_prompt_view_id=view.view_id,
            source_prompt_contract_id=view.source_contract_id,
            rendered_prompt=view.rendered_prompt,
            available_channels=view.available_channels,
            available_ops=view.available_ops,
            forbidden_capabilities=view.forbidden_capabilities,
            final_authorities=view.final_authorities,
            anti_theatrical_constraints=view.anti_theatrical_constraints,
        )

    def build_outward_expression_request_op(
        self,
        request: OutwardExpressionRequest,
    ) -> BuildOutwardExpressionRequestOp:
        return BuildOutwardExpressionRequestOp(
            op_name="build_outward_expression_request",
            owner="embodied_subjective_prompt_and_action_autonomy",
            request_id=request.request_id,
            source_prompt_view_id=request.source_prompt_view_id,
            channel_count=len(request.available_channels),
        )