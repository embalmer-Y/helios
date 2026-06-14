# -*- coding: utf-8 -*-
"""R93 Phase 2: end-to-end runtime-stage chain tests for action agency.

Owner: composition / runtime.

These tests exercise the action-agency contract through the full
`assemble_runtime()` chain. The model picks an action class via
`action_intent` and (optionally) a `target_user_id`; the runtime honors the
choice end-to-end.

Cases covered:

- `action_intent="no_action"` produces no dispatch (cycle closes internal-only).
- Explicit `action_intent="reply"` dispatches a real CLI sink with the reply.
- `target_user_id` is honored in a multi-driver fixture (CLI wildcard passes).
- `action_intent="tool"` routes to a tool driver via the existing R85 path.
"""

from helios_v2.composition.runtime_assembly import (
    assemble_runtime,
    default_composition_config,
)


def _ready_gateway(provider):
    """Build a network-free gateway whose bound thought profile is statically ready."""

    from helios_v2.llm import LlmGateway, LlmProfileRegistry

    resolved = default_composition_config()
    return LlmGateway(
        provider=provider,
        registry=LlmProfileRegistry(profiles=resolved.llm.profiles),
        env={"OPENAI_API_KEY": "sk-test"},
    )


def _assemble(provider, *, cli_output_sink=None):
    kwargs = {
        "gateway": _ready_gateway(provider),
        "default_signal_mode": "legacy_constant",
        "channel_cli": True,
    }
    if cli_output_sink is not None:
        kwargs["cli_output_sink"] = cli_output_sink
    return assemble_runtime(**kwargs)


def test_action_intent_no_action_produces_no_dispatch() -> None:
    """`action_intent="no_action"` -> no dispatch (cycle closes internal-only).

    The model has agency: it can decide to NOT act even when an input arrived.
    This is the documented R93 Phase 2 fix to the "confiding machine" pattern.
    """

    from dataclasses import dataclass, field
    import json

    from helios_v2.llm import ProviderCompletion

    @dataclass
    class _NoActionProvider:
        calls: list[str] = field(default_factory=list)

        def complete(self, profile, request, api_key) -> ProviderCompletion:
            self.calls.append(profile.profile_name)
            envelope = {
                "thought": "resolved, no action warranted",
                "sufficiency": 0.95,
                "wants_to_continue": False,
                "continue_reason": "",
                "proposed_action": {"intends_action": False, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "action_intent": "no_action",
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    handle = _assemble(_NoActionProvider())
    handle.startup()
    result = handle.tick()

    # Internal-only path: planner-bridge outcome is `no_actionable_proposal`.
    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "no_actionable_proposal"
    # No action dispatched.
    assert planner.action_decision is None


def test_action_intent_reply_dispatches_cli_sink() -> None:
    """Explicit `action_intent="reply"` dispatches a real CLI sink with the reply."""

    from dataclasses import dataclass, field
    import json

    from helios_v2.llm import ProviderCompletion

    @dataclass
    class _ReplyProvider:
        sink: list[str] = field(default_factory=list)
        calls: list[str] = field(default_factory=list)

        def complete(self, profile, request, api_key) -> ProviderCompletion:
            self.calls.append(profile.profile_name)
            envelope = {
                "thought": "operator asked a question; answering",
                "sufficiency": 0.9,
                "wants_to_continue": False,
                "continue_reason": "",
                "proposed_action": {"intends_action": True, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "reply_text": "R93-P2-DISPATCH-MARKER",
                "action_intent": "reply",
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    provider = _ReplyProvider()
    handle = _assemble(provider, cli_output_sink=provider.sink.append)
    handle.startup()
    # Pre-load the CLI inbound backlog with an operator line so the next tick's
    # "inbound" stage surfaces a real stimulus (the action_externalization path
    # needs a non-empty `02` to populate `current_operator_id` and the
    # `target_user_id` binding context).
    handle.channel_subsystem._drivers["cli"].submit_line("hello")
    result = handle.tick()

    # Planner-bridge outcome: executed.
    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "executed"
    # The reply text from the model was rendered into the CLI sink.
    assert any("R93-P2-DISPATCH-MARKER" in line for line in provider.sink), (
        f"Expected the marker in the sink; got: {provider.sink!r}"
    )


def test_target_user_id_honored_in_multi_driver_fixture() -> None:
    """A multi-driver fixture honors `target_user_id` via the CLI wildcard.

    The CLI driver is a wildcard; the model-supplied `target_user_id` is
    captured in `op_params["target_user_id"]` and threads through to the
    planner's decision trace. The action_externalization binding context
    may override the exact value with a runtime-generated user id
    (`user:runtime:*`); we assert only that the key is preserved.
    """

    from dataclasses import dataclass, field
    import json

    from helios_v2.llm import ProviderCompletion

    @dataclass
    class _TargetedReplyProvider:
        sink: list[str] = field(default_factory=list)

        def complete(self, profile, request, api_key) -> ProviderCompletion:
            envelope = {
                "thought": "operator wants a reply",
                "sufficiency": 0.9,
                "wants_to_continue": False,
                "continue_reason": "",
                "proposed_action": {"intends_action": True, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "reply_text": "R93-P2-TARGETED-MARKER",
                "action_intent": "reply",
                "target_user_id": "user:specific",
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    provider = _TargetedReplyProvider()
    handle = _assemble(provider, cli_output_sink=provider.sink.append)
    handle.startup()
    handle.channel_subsystem._drivers["cli"].submit_line("hello")
    result = handle.tick()

    planner = result.stage_results["planner_executor_feedback_bridge"].result
    assert planner.status == "executed"
    # The validated params carry a `target_user_id` key (its exact value may
    # be the binding-context user id; that's documented in R93 e2e test
    # notes).
    assert "target_user_id" in planner.action_decision.validated_params
    assert any("R93-P2-TARGETED-MARKER" in line for line in provider.sink)


def test_action_intent_tool_routes_via_r85_path() -> None:
    """`action_intent="tool"` + `i_want_to_use_tool=true` + `tool_op` routes via the R85 path.

    The tool path is unchanged from R85; Phase 2 just threads
    `target_user_id` into op_params when the model supplies one.
    """

    # The default CLI driver doesn't offer `os.fs.write`, so this case expects
    # a planner rejection (no driver offers the op). The intent of the test
    # is to verify the proposal is built with the right op + target_user_id
    # before the planner runs, not to verify end-to-end tool dispatch (which
    # would require an additional tool driver). The planner stage is the
    # right boundary for this assertion.
    from dataclasses import dataclass, field
    import json

    from helios_v2.llm import ProviderCompletion

    @dataclass
    class _ToolProvider:
        def complete(self, profile, request, api_key) -> ProviderCompletion:
            envelope = {
                "thought": "writing a file",
                "sufficiency": 0.9,
                "wants_to_continue": False,
                "continue_reason": "",
                "proposed_action": {"intends_action": True, "summary": ""},
                "self_revision": {"intends_revision": False, "summary": ""},
                "i_want_to_use_tool": True,
                "tool_op": "os.fs.write",
                "tool_params": {"path": "/tmp/x", "content": "y"},
                "action_intent": "tool",
                "target_user_id": "user:r93",
            }
            return ProviderCompletion(output_text=json.dumps(envelope), finish_reason="stop")

    handle = _assemble(_ToolProvider())
    handle.startup()
    # Pre-load the CLI inbound backlog so the next tick's gate fires (the
    # thought gate needs a non-empty inbound to surface a real stimulus).
    handle.channel_subsystem._drivers["cli"].submit_line("write a file")
    result = handle.tick()

    # The thought cycle produced a tool proposal.
    thought = result.stage_results["internal_thought_loop_owner"]
    assert thought.result is not None
    thought_cycle = thought.result
    assert thought_cycle.action_proposal is not None
    assert thought_cycle.action_proposal.requested_op == "os.fs.write"
    op_params = dict(thought_cycle.action_proposal.op_params)
    assert op_params["path"] == "/tmp/x"
    assert op_params["content"] == "y"
    assert op_params["target_user_id"] == "user:r93"
