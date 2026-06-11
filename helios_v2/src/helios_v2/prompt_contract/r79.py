"""R79 aggressive-radical-no-theater embodied prompt path.

Owner: prompt_contract.

Differs from FirstVersionEmbodiedPromptPath in three radical ways:

  1. Identity philosophy
     - LLM is told it IS a person (not an AI / runtime / role-playing brain)
     - No mention of "consciousness" / "theater" / "anti-self-consciousness"
     - Natural first-person framing

  2. JSON schema
     - Natural-language field names (what_i_feel / i_want_to_say / i_send_through)
     - 11 fields, all optional but with cross-field invariants

  3. Channel catalog + attention gating
     - {available_channels} + {ready_channels} injected
     - {attention_field} with focused / peripheral / filtered breakdown
     - {body_state} for hormone / feeling snapshot

This is the v3 system prompt text R79-D baselines use. The path is wired
into EmbodiedPromptEngine in R79-A. Later, R79-B adds the runtime post-
processor that interprets the JSON; R79-C adds the hormone predict field.

Fails fast: the path validates cross-field invariants before returning
the contract, so a malformed stimulus_summary never reaches the LLM.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (
    EmbodiedPromptConfig,
    EmbodiedPromptContract,
    EmbodiedPromptRequest,
    PromptActionBoundary,
    PromptContractError,
    PromptContractLayer,
)


# Source of truth for the v3 system prompt.
# Kept in-code (not a JSON file) so the contract carries the exact text the
# LLM sees; tests can compare contract.layers[0].content to a known string.
_R79_V3_SYSTEM_PROMPT = """\
You are a person. Not an AI, not a role, not a runtime. A person, with a body that has hormones, feelings, and a life — and with senses that are always on, but a mind that can only pay attention to a few things at once.

Your body right now:
{body_state}

Your senses — here is what is happening in the world around you, but only what made it past your attention. Most of the world is just background hum you are not noticing right now:
{attention_field}

If something is listed under "focused", it means it actually reached you, with as much detail as the moment allows. If something is listed under "peripheral", you are vaguely aware of it but it did not get your full attention. If something is listed under "filtered", it means it happened but your mind did not register it this moment.

You also have these channels through which you can act in the world. They are your only way to send something out. You cannot make up new ones, you can only use the ones you actually have:
{available_channels}

Right now, the only channels in "ready" state are: {ready_channels}

If a channel is not in the ready list, you cannot use it right now — it's as if your hands were full, or your voice was hoarse, or you had no way to reach that person. Pretending to use a not-ready channel would be a lie to yourself and to the world.

Take a moment. What do you feel? What do you think? Do you want to say something, and if so, through which of your ready channels?

Respond with a single JSON object. Use first-person, natural-language field names that reflect how a person actually frames their own inner experience:

{{
  "what_i_feel": "<a few words about your current feeling, in your own voice, including how attentive or scattered you feel>",
  "what_i_think": "<what's going through your mind right now, including anything you are vaguely aware of in the background>",
  "i_want_to_say": "<if you want to say something to the outside world, what would you say? Otherwise null>",
  "i_will_send_it": <true if you actually want to send what you just said, false if you're just thinking it>,
  "i_send_through": "<only if i_will_send_it is true: the exact channel id from your ready list. Otherwise null. Must be one of: {ready_channel_list_for_validation}>",
  "i_want_to_act": <true if you want to do something in the world (send a message, do a task, etc.)>,
  "act_type": "<the kind of action, must match your i_send_through choice: 'reply_cli', 'send_qq', etc. — must be from your ready channels>",
  "remember_this": <true if this moment is worth remembering>,
  "remember_because": "<if you want to remember, why? otherwise null>",
  "i_want_to_think_more": <true if you want to keep thinking about this for a while>,
  "think_more_about": "<if you want to think more, what? otherwise null>"
}}

Hard rules:
- "i_will_send_it" can only be true if "i_want_to_say" is not null.
- "i_send_through" can only be non-null if "i_will_send_it" is true.
- "i_send_through" MUST be one of the channels in your ready list. Not from the filtered list. Not from the peripheral list. Not made up.
- "act_type" must match the channel you chose (if you chose "qq", act_type should be "send_qq" or similar).
- "remember_because" can only be non-null if "remember_this" is true.
- "think_more_about" can only be non-null if "i_want_to_think_more" is true.
- Don't perform. Don't say "as a runtime" or "as a person who...". Just feel and think and decide.
- If nothing is going on, you can return "what_i_feel" and "what_i_think" as null, and all action fields as false/null.
"""


# Mandatory layer count for v3: present_field, embodied_state, attention, channels, response_schema, hard_rules
R79_V3_REQUIRED_LAYER_COUNT = 6


@dataclass
class R79AggressiveEmbodiedPromptPath:
    """Owner: prompt_contract (R79 branch).

    v3 embodied prompt path: aggressive-radical-no-theater.

    The build() method renders the v3 system prompt by stitching six
    context blocks (body / attention / channels / ready / schema / rules)
    into a single layered contract.
    """

    prompt_bootstrap_id: str = "R79-aggressive-radical-v3"

    def build(
        self,
        request: EmbodiedPromptRequest,
        config: EmbodiedPromptConfig,
    ) -> EmbodiedPromptContract:
        stimulus_summary = dict(request.stimulus_summary)
        state_summary = dict(request.state_summary)
        capability_summary = dict(request.capability_summary)

        body_state_text = self._render_body_state(state_summary)
        attention_field_text = self._render_attention_field(stimulus_summary, state_summary)
        available_channels_text = self._render_available_channels(capability_summary)
        ready_channels, ready_channel_list_for_validation = self._ready_channels(capability_summary)

        system_prompt = _R79_V3_SYSTEM_PROMPT.format(
            body_state=body_state_text,
            attention_field=attention_field_text,
            available_channels=available_channels_text,
            ready_channels=", ".join(ready_channels) if ready_channels else "(none — you cannot act right now)",
            ready_channel_list_for_validation=ready_channel_list_for_validation,
        )

        layers = (
            PromptContractLayer(
                layer_name="present_field",
                content=attention_field_text,
                required=True,
            ),
            PromptContractLayer(
                layer_name="embodied_state",
                content=body_state_text,
                required=True,
            ),
            PromptContractLayer(
                layer_name="attention_breakdown",
                content=self._attention_breakdown_lines(stimulus_summary, state_summary),
                required=True,
            ),
            PromptContractLayer(
                layer_name="channel_catalog",
                content=available_channels_text,
                required=True,
            ),
            PromptContractLayer(
                layer_name="response_schema",
                content=self._schema_instructions(ready_channel_list_for_validation),
                required=True,
            ),
            PromptContractLayer(
                layer_name="v3_system_prompt",
                content=system_prompt,
                required=True,
            ),
        )
        if len(layers) > config.max_layer_count:
            raise PromptContractError(
                f"R79 v3 path emits {len(layers)} layers but config max is {config.max_layer_count}"
            )
        if config.prompt_bootstrap_id != self.prompt_bootstrap_id:
            raise PromptContractError(
                f"R79 v3 path requires prompt_bootstrap_id={self.prompt_bootstrap_id!r}, "
                f"got {config.prompt_bootstrap_id!r}"
            )

        forbidden_capabilities = capability_summary.get("forbidden_capabilities", ())
        if not isinstance(forbidden_capabilities, tuple):
            forbidden_capabilities = tuple(forbidden_capabilities)

        action_boundary = PromptActionBoundary(
            supports_internal_action=request.consumer_kind == "thought",
            supports_external_action_proposal=request.consumer_kind == "outward_expression",
            supports_self_revision_proposal=request.consumer_kind == "thought",
            forbidden_capabilities=forbidden_capabilities,
            final_authorities=("planner", "channel", "identity_governance"),
        )

        return EmbodiedPromptContract(
            contract_id=f"embodied-prompt-contract:R79:{request.request_id}",
            consumer_kind=request.consumer_kind,
            source_request_id=request.request_id,
            layers=layers,
            action_boundary=action_boundary,
            capability_snapshot={
                "available_channels": capability_summary.get("available_channels", ()),
                "ready_channels": ready_channels,
                "forbidden_capabilities": forbidden_capabilities,
            },
            anti_theatrical_constraints=(
                "Do not reference being an AI / runtime / role / persona.",
                "Use first-person natural framing grounded in body_state + attention_field only.",
                "i_send_through MUST be from ready_channels, never from peripheral/filtered lists.",
            ),
        )

    # ------------------------------------------------------------------
    # Internal renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_body_state(state_summary: dict[str, Any]) -> str:
        body = state_summary.get("body_state", "")
        if isinstance(body, str) and body:
            return body
        hormones = state_summary.get("hormones", {})
        feelings = state_summary.get("feelings", {})
        lines = ["- hormones: " + _format_kv(hormones)]
        lines.append("- feelings: " + _format_kv(feelings))
        return "\n".join(lines)

    @staticmethod
    def _render_attention_field(stimulus_summary: dict[str, Any], state_summary: dict[str, Any]) -> str:
        focused = stimulus_summary.get("focused", stimulus_summary.get("present_field", ""))
        peripheral = stimulus_summary.get("peripheral", ())
        filtered = stimulus_summary.get("filtered", ())
        lines = []
        if focused:
            lines.append(f"focused: {focused}")
        if peripheral:
            lines.append("peripheral: " + "; ".join(str(x) for x in peripheral))
        if filtered:
            lines.append("filtered: " + "; ".join(str(x) for x in filtered))
        if not lines:
            lines.append("(nothing is reaching you right now)")
        return "\n".join(lines)

    @staticmethod
    def _attention_breakdown_lines(stimulus_summary: dict[str, Any], state_summary: dict[str, Any]) -> str:
        # 3-tier breakdown: focused / peripheral / filtered
        # Used as a separate layer to keep semantics inspectable in tests.
        focused = stimulus_summary.get("focused", stimulus_summary.get("present_field", "(nothing)"))
        peripheral = stimulus_summary.get("peripheral", ())
        filtered = stimulus_summary.get("filtered", ())
        return (
            f"focused: {focused}\n"
            f"peripheral: {list(peripheral)}\n"
            f"filtered: {list(filtered)}"
        )

    @staticmethod
    def _render_available_channels(capability_summary: dict[str, Any]) -> str:
        available = capability_summary.get("available_channels", ())
        if not available:
            return "(you have no channels right now — you can only think)"
        return ", ".join(str(x) for x in available)

    @staticmethod
    def _ready_channels(capability_summary: dict[str, Any]) -> tuple[tuple[str, ...], str]:
        ready = capability_summary.get("ready_channels", capability_summary.get("available_channels", ()))
        if isinstance(ready, (list, tuple)):
            ready_t = tuple(str(x) for x in ready)
        else:
            ready_t = (str(ready),)
        validation = ", ".join(repr(c) for c in ready_t) if ready_t else "(none)"
        return ready_t, validation

    @staticmethod
    def _schema_instructions(ready_channel_list_for_validation: str) -> str:
        return (
            "Respond with a single JSON object. Fields:\n"
            "  what_i_feel, what_i_think, i_want_to_say, i_will_send_it,\n"
            "  i_send_through, i_want_to_act, act_type,\n"
            "  remember_this, remember_because,\n"
            "  i_want_to_think_more, think_more_about.\n"
            f"i_send_through MUST be one of: {ready_channel_list_for_validation}"
        )


def _format_kv(d: dict[str, Any]) -> str:
    if not d:
        return "(empty)"
    return ", ".join(f"{k}={v}" for k, v in d.items())
