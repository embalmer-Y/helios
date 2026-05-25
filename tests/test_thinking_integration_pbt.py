"""Property and focused tests for task-22 thinking integration."""

from __future__ import annotations

import os
import sys
import time
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cognition.thinking import ThoughtFragment, ThinkingManager
from cognition.thinking_integration import EMOTION_THOUGHT_BIAS, ThinkingEngineIntegration
from core.helios_state import ContinuationPressureState, HeliosState
from helios_main import Helios, HeliosConfig
from helios_io.action_models import ThoughtActionProposal
from helios_io.channel import ChannelDescriptor, ChannelOpDescriptor, ChannelStatus
from memory import DirectedMemoryBundle, MemorySearchHit
from personality_projection import build_personality_projection


class FakeAutobioStore:
    def __init__(self):
        self.records: list[dict] = []

    def record(self, **kwargs):
        self.records.append(kwargs)
        return kwargs


class FakeThinkingEngine:
    def __init__(self, mode: str = ThinkingManager.MODE_WANDERING):
        self.mode = mode

    def determine_mode(self, **kwargs):
        return self.mode

    def generate_thoughts(self, **kwargs):
        return [
            ThoughtFragment(
                content="一个还在扩散的念头",
                source="free_association",
                valence_bias=0.1,
                arousal_bias=0.2,
                novelty=0.4,
                phi_prediction=0.3,
            )
        ]


class FakeLLMClient:
    def __init__(self, content: str):
        self.content = content
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FailingLLMClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        raise RuntimeError("llm exploded")


def make_state(**overrides) -> HeliosState:
    state = HeliosState(
        tick=42,
        icri=0.5,
        valence=0.2,
        arousal=0.3,
        dominant_system="SEEKING",
        panksepp={"PLAY": 0.1, "SEEKING": 0.6},
        drive_dominant="curiosity",
        drive_urgency=0.1,
        cortisol=0.2,
        mood_label="curious",
    )
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def make_output_descriptor(channel_id: str) -> ChannelDescriptor:
    return ChannelDescriptor(
        channel_id=channel_id,
        display_name=channel_id.upper(),
        output_types=["text_message"],
        output_formats=["text/plain"],
        capabilities=["send", "text_output"],
        supported_ops=[
            ChannelOpDescriptor(
                name="send",
                direction="output",
                description=f"{channel_id} output",
            )
        ],
    )


def unwrap_thought(result):
    assert result is not None
    assert result.triggered is True
    assert result.thought is not None
    return result.thought


@settings(max_examples=20, deadline=None)
@given(dominant_system=st.sampled_from(sorted(EMOTION_THOUGHT_BIAS)))
def test_emotion_biased_thought_generation(dominant_system: str):
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    result = integration.generate(make_state(dominant_system=dominant_system))
    thought = unwrap_thought(result)

    assert thought.type in EMOTION_THOUGHT_BIAS[dominant_system]


def test_self_reflective_thought_emits_revision_proposal():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient("我需要更开放一些，才能更好地理解世界。"),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["self_question"], {}))

    result = integration.generate(make_state())
    thought = unwrap_thought(result)

    proposal = thought.metadata.get("self_revision_proposal")
    assert proposal is not None
    assert proposal["revision_type"] == "personality_adjustment"
    assert proposal["requested_change"]["personality_baseline"]["openness"] == 1.05


def test_self_reflective_thought_can_emit_identity_narrative_revision_proposal():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient("这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["rumination"], {}))

    result = integration.generate(make_state())
    thought = unwrap_thought(result)

    proposal = thought.metadata.get("self_revision_proposal")
    assert proposal is not None
    assert proposal["revision_type"] == "autobiographical_identity_narrative_revision"
    assert proposal["requested_change"]["narrative_summary"] == "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"


def test_external_stimulus_thought_can_emit_direct_action_proposal():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient("我想把这个判断直接告诉对方。"),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["rumination"], {}))

    state = make_state(
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.78,
                "payload": {"user_id": "user1", "text": "你在想什么？"},
            }
        ]
    )

    result = integration.generate(state)

    assert result.triggered is True
    assert result.action_proposal is not None
    assert isinstance(result.action_proposal, ThoughtActionProposal)
    assert result.action_proposal.behavior_name == "speak_share"
    assert result.action_proposal.preferred_op == "send"
    assert result.action_proposal.params["target_user_id"] == "user1"
    assert result.action_proposal.channel_constraints["candidate_channels"] == ["qq"]
    assert result.action_proposal.outbound_intensity >= 0.35
    assert state.last_internal_thought_trace["action_proposal"]["behavior_name"] == "speak_share"


def test_strong_external_stimulus_bypasses_internal_thought_cooldown():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    integration._last_generation = time.time()

    state = make_state(
        icri=0.3,
        current_stimuli=[
            {
                "source_channel_id": "cli",
                "source_kind": "local_terminal_input",
                "trigger_condition": "cli_text_input",
                "stimulus_intensity": 0.42,
                "payload": {"user_id": "local-user", "text": "聊聊现在的感受"},
            }
        ],
    )

    result = integration.generate(state)

    assert result.triggered is True
    assert result.thought is not None
    assert state.last_thought_gate_result["trigger_reason"] == "external_stimulus"


def test_structured_internal_thought_output_can_drive_action_and_memory_handoff():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient(
            '{"thought_text":"我想把刚才的判断直接告诉对方。","sufficiency_level":0.41,"continuation_requested":true,"continuation_reason":"reflective_open_loop","recall_intent":"继续回想刚才那段海边散步","selected_memory_refs":["mem-mid-1"],"action_proposal":{"scope":"external","behavior_name":"speak_share","preferred_op":"send","params":{"target_user_id":"user1"},"channel_constraints":{"candidate_channels":["qq"],"requires_target_user":true},"outbound_intensity":0.67,"reason_trace":["share_now"]}}'
        ),
        available_channels_provider=lambda: [make_output_descriptor("qq")],
        available_behavior_schema_provider=lambda: [
            {"behavior_name": "speak_share", "op_name": "send", "parameter_schema": {"target_user_id": "str"}}
        ],
    )
    integration.explain_ranked_types = MagicMock(return_value=(["rumination"], {}))

    state = make_state(
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.78,
                "payload": {"user_id": "user1", "text": "你在想什么？"},
            }
        ]
    )

    result = integration.generate(state)

    assert result.triggered is True
    assert result.action_proposal is not None
    assert result.action_proposal.preferred_op == "send"
    assert result.action_proposal.channel_constraints["candidate_channels"] == ["qq"]
    assert result.recall_intent == "继续回想刚才那段海边散步"
    assert result.memory_handoff["selected_memory_refs"] == ["mem-mid-1"]
    assert state.last_memory_handoff["saved_for_next_tick"] is True


def test_structured_internal_thought_trace_records_explicit_none_action():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient(
            '{"thought_text":"我先把这份感觉留在内部。","sufficiency_level":0.8,"continuation_requested":false,"action_proposal":null}'
        ),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["rumination"], {}))

    state = make_state()
    result = integration.generate(state)

    assert result.triggered is True
    assert result.action_proposal is None
    assert result.action_derivation_trace.action_explicit is True
    assert result.action_derivation_trace.parse_status == "explicit_none"
    assert state.last_internal_thought_trace["structured_output_valid"] is True
    assert state.last_internal_thought_trace["action_explicit"] is True
    assert state.last_internal_thought_trace["action_parse_status"] == "explicit_none"
    assert state.last_thought_cycle_result["action_derivation_trace"]["parse_status"] == "explicit_none"


def test_structured_internal_thought_trace_records_invalid_external_action_drop_reason():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient(
            '{"thought_text":"我想立刻回应她。","sufficiency_level":0.42,"continuation_requested":true,"action_proposal":{"scope":"external","behavior_name":"reply_message","params":{"target_user_id":"user1"},"channel_constraints":{"candidate_channels":[]},"outbound_intensity":0.73}}'
        ),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["rumination"], {}))

    state = make_state(
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.78,
                "payload": {"user_id": "user1", "text": "你在想什么？"},
            }
        ]
    )

    result = integration.generate(state)

    assert result.triggered is True
    assert result.action_proposal is None
    assert result.action_derivation_trace.action_explicit is True
    assert result.action_derivation_trace.parse_status == "invalid_schema"
    assert result.action_derivation_trace.drop_reason == "missing_behavior_or_op"
    assert state.last_internal_thought_trace["action_drop_reason"] == "missing_behavior_or_op"
    assert state.last_thought_cycle_result["action_derivation_trace"]["drop_reason"] == "missing_behavior_or_op"


def test_truncated_structured_internal_thought_can_be_partially_recovered():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FakeLLMClient(
            '{"thought_text":"我想告诉她我现在挺好的，也想问问她今天过得怎么样。","sufficiency_level":0.44,"continuation_requested":true,"continuation_reason":"reflective_open_loop","recall_intent":"记住这次被关心的感觉","action_proposal":{"scope":"external","behavior_name":"reply_message","preferred_op":"send","params":{"target_user_id":"user1","outbound_text":"我现在挺好的，你今天过得怎么样？"},"channel_constraints":{"candidate_channels":["qq"],"requires_target_user":true},"outbound_intensity":0.71'
        ),
    )
    integration.explain_ranked_types = MagicMock(return_value=(["future_projection"], {}))

    state = make_state(
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.82,
                "payload": {"user_id": "user1", "text": "你现在感觉怎么样？"},
            }
        ]
    )

    result = integration.generate(state)

    assert result.triggered is True
    assert result.action_proposal is not None
    assert result.action_proposal.behavior_name == "reply_message"
    assert result.action_proposal.preferred_op == "send"
    assert result.action_proposal.params["target_user_id"] == "user1"
    assert result.action_proposal.params["outbound_text"] == "我现在挺好的，你今天过得怎么样？"
    assert result.action_proposal.channel_constraints["candidate_channels"] == ["qq"]
    assert state.last_internal_thought_trace["structured_output_valid"] is True
    assert state.last_internal_thought_trace["action_parse_status"] == "parsed"
    assert state.last_thought_cycle_result["action_derivation_trace"]["parse_status"] == "parsed"


def test_internal_prompt_contract_includes_real_channel_ops_when_available():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        available_channels_provider=lambda: [make_output_descriptor("qq")],
        available_behavior_schema_provider=lambda: [
            {"behavior_name": "speak_share", "op_name": "send", "parameter_schema": {"target_user_id": "str"}}
        ],
    )
    state = make_state(
        current_stimuli=[
            {
                "source_channel_id": "qq",
                "source_kind": "external_message",
                "trigger_condition": "channel_input",
                "stimulus_intensity": 0.8,
                "payload": {"user_id": "user1"},
            }
        ]
    )
    trigger = integration.evaluate_trigger(state, now=time.time())
    context = integration.build_internal_context(state, "rumination", trigger)
    plan = integration._build_internal_prompt_contract(state, context)
    _system_prompt, user_prompt = integration._render_internal_prompts(plan, context)

    assert "channel_id=qq" in user_prompt
    assert "channel_op=send" in user_prompt
    assert "save_memory_handoff" in user_prompt
    assert '"action_proposal"' in user_prompt


@settings(max_examples=20, deadline=None)
@given(icri=st.floats(min_value=0.0, max_value=0.099, allow_nan=False, allow_infinity=False))
def test_thought_suppression_below_icri_threshold(icri: float):
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())

    assert integration.should_generate(icri, True, time.time() + 100.0) is False
    assert integration.should_generate(0.5, False, time.time() + 100.0) is False


def test_thought_type_cooldown_enforcement():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(dominant_system="PANIC")

    first = unwrap_thought(integration.generate(state))

    integration._last_generation = 0.0
    second = unwrap_thought(integration.generate(state))

    assert second.type != first.type


def test_personality_novelty_bias_prioritizes_exploratory_thought_types():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    projection = build_personality_projection(
        traits={
            "openness": 1.5,
            "extraversion": 1.3,
            "agreeableness": 1.0,
            "neuroticism": 0.9,
            "conscientiousness": 0.9,
        }
    )

    ranked = integration.get_ranked_types("SEEKING", projection)

    assert ranked[0] in {"self_question", "free_association"}
    assert ranked.index("self_question") < ranked.index("rumination")


def test_personality_persistence_bias_prioritizes_reflective_thought_types():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    projection = build_personality_projection(
        traits={
            "openness": 0.9,
            "extraversion": 0.8,
            "agreeableness": 1.0,
            "neuroticism": 1.4,
            "conscientiousness": 1.5,
        }
    )

    ranked = integration.get_ranked_types("PANIC", projection)

    assert ranked[0] == "rumination"
    assert ranked.index("counterfactual") < ranked.index("free_association")


def test_thinking_integration_exposes_personality_trace_on_state():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(
        dominant_system="SEEKING",
        personality_projection=build_personality_projection(
            traits={
                "openness": 1.5,
                "extraversion": 1.2,
                "agreeableness": 1.0,
                "neuroticism": 0.8,
                "conscientiousness": 0.9,
            }
        ),
    )

    thought = unwrap_thought(integration.generate(state))

    assert state.last_thought_personality_trace["selected_type"] == thought.type
    assert state.last_thought_personality_trace["novelty_bias"] > 0.0
    assert state.last_thought_personality_trace["ranked_types"][0] == thought.type


def test_internal_thought_llm_path_uses_dedicated_prompt_and_trace():
    client = FakeLLMClient("内部思考: 我在把零散线索重新拼起来。")
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=client,
    )
    state = make_state(
        directed_memory_bundle=DirectedMemoryBundle(
            short_term_context=(
                MemorySearchHit(memory_id="w1", memory_type="working", score=0.3, summary="短期线索"),
            ),
            mid_term_hits=(
                MemorySearchHit(memory_id="e1", memory_type="episodic", score=0.7, summary="最近的经历"),
            ),
            long_term_hits=(
                MemorySearchHit(memory_id="s1", memory_type="semantic", score=0.8, summary="稳定概念"),
            ),
        )
    )

    result = integration.generate(state)
    thought = unwrap_thought(result)

    assert thought.llm_used is True
    assert thought.fallback_used is False
    assert thought.source_path == "internal_thought_llm"
    assert state.last_internal_thought_trace["triggered"] is True
    assert state.last_internal_thought_trace["llm_used"] is True
    assert "continuation_requested" in state.last_internal_thought_trace
    assert "continuation_pressure" in state.last_internal_thought_trace
    call = client.calls[0]
    messages = call["messages"]
    assert "不要写成对用户的回复" in messages[0]["content"]
    assert "metrics:" in messages[0]["content"]
    assert "thought_type=" in messages[1]["content"]
    assert "directed_memory=" in messages[1]["content"]
    assert "最近的经历" in messages[1]["content"]
    assert "对方说" not in messages[1]["content"]
    assert "directed_memory_summary" in state.last_internal_thought_trace
    assert state.last_internal_thought_trace["prompt_contract"]["metric_descriptor_count"] >= 8


def test_internal_thought_llm_failure_falls_back_without_interrupting():
    integration = ThinkingEngineIntegration(
        FakeThinkingEngine(),
        FakeAutobioStore(),
        llm_enabled=True,
        api_key="test-key",
        llm_client=FailingLLMClient(),
    )
    state = make_state()

    result = integration.generate(state)
    thought = unwrap_thought(result)

    assert thought.llm_used is False
    assert thought.fallback_used is True
    assert thought.content
    assert state.last_internal_thought_trace["fallback_used"] is True
    assert state.last_internal_thought_trace["rejected_reason"] == "llm_error"


def test_internal_thought_trigger_suppresses_under_high_resource_pressure():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(allostatic_load=0.92)

    result = integration.generate(state)

    assert result.triggered is False
    assert result.thought is None
    assert state.last_internal_thought_trace["triggered"] is False
    assert state.last_internal_thought_trace["trigger_reason"] == "resource_pressure_too_high"


def test_external_stimulus_populates_structured_gate_result_and_can_trigger_thought():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(icri=0.02)
    state.current_stimuli = [
        {
            "source_channel_id": "qq",
            "stimulus_intensity": 0.78,
            "novelty_factor": 0.92,
            "sensitization_factor": 0.41,
            "trigger_condition": "channel_input",
        }
    ]

    result = integration.generate(state)

    assert result.triggered is True
    assert result.thought is not None
    assert state.last_thought_gate_result["should_think"] is True
    assert state.last_thought_gate_result["dominant_reason"] == "external_stimulus"
    assert state.last_thought_gate_result["selected_stimuli_count"] == 1
    assert state.last_thought_gate_result["selected_stimuli"][0]["source_channel_id"] == "qq"
    assert state.last_thought_gate_result["contributing_signals"]["sensitization"] == 0.41
    assert "temporal_dynamics" in state.last_thought_gate_result["contributing_signals"]


def test_gate_score_explicitly_accounts_for_sensitization_and_temporal_dynamics():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    baseline = make_state(icri=0.1)
    baseline.current_stimuli = [
        {
            "source_channel_id": "qq",
            "stimulus_intensity": 0.22,
            "novelty_factor": 0.18,
            "sensitization_factor": 0.0,
            "trigger_condition": "channel_input",
        }
    ]
    boosted = make_state(
        icri=0.1,
        boredom=0.6,
        novelty_hunger=0.7,
        restoration_level=0.2,
        fatigue_pressure=0.1,
    )
    boosted.current_stimuli = [
        {
            "source_channel_id": "qq",
            "stimulus_intensity": 0.22,
            "novelty_factor": 0.18,
            "sensitization_factor": 0.85,
            "trigger_condition": "channel_input",
        }
    ]

    baseline_trigger = integration.evaluate_trigger(baseline, now=time.time() + 10.0)
    boosted_trigger = integration.evaluate_trigger(boosted, now=time.time() + 10.0)

    assert boosted_trigger.gate_score > baseline_trigger.gate_score
    assert boosted_trigger.contributing_signals["sensitization"] == 0.85
    assert boosted_trigger.contributing_signals["temporal_dynamics"] > 0.0


def test_reflective_internal_thought_establishes_continuation_pressure():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore())
    state = make_state(dominant_system="PANIC")

    result = integration.generate(state)
    thought = unwrap_thought(result)

    assert thought.type == "rumination"
    assert state.continuation_requested is True
    assert state.continuation_pressure > 0.0
    assert state.continuation.active is True
    assert state.continuation.origin_thought_id == result.thought_id
    assert state.continuation.reason == "reflective_open_loop"
    assert state.last_thought_cycle_result["continuation"]["origin_thought_id"] == result.thought_id
    assert state.last_recall_intent == thought.content[:80]
    assert state.last_thought_cycle_result["continuation_requested"] is True


def test_quiet_tick_decays_structured_continuation_state():
    integration = ThinkingEngineIntegration(FakeThinkingEngine(), FakeAutobioStore(), internal_think_enabled=False)
    state = make_state(
        continuation=ContinuationPressureState(
            active=True,
            level=0.6,
            origin_thought_id="thought::carry",
            reason="reflective_open_loop",
            expires_at_tick=50,
            carry_count=1,
        ),
        continuation_pressure=0.6,
        continuation_reason="reflective_open_loop",
        last_recall_intent="未完成的问题",
    )

    result = integration.generate(state)

    assert result.triggered is False
    assert state.continuation.active is True
    assert state.continuation.level < 0.6
    assert state.continuation.origin_thought_id == "thought::carry"
    assert state.continuation.carry_count == 2
    assert state.last_thought_cycle_result["continuation"]["carry_count"] == 2


def test_tick_keeps_no_thought_state_without_parallel_reply_owner():
    with TemporaryDirectory() as temp_dir:
        config = HeliosConfig()
        config.LOG_DIR = temp_dir + "/logs"
        config.DATA_DIR = temp_dir + "/data"
        config.QQ_APP_ID = ""
        config.QQ_CLIENT_SECRET = ""
        config.LLM_API_KEY = ""
        config.LLM_SPEECH_ENABLED = False

        helios = Helios(config)
        try:
            helios.log.info = MagicMock()
            helios.log.warning = MagicMock()
            helios.daisy.cycle = MagicMock(
                return_value=SimpleNamespace(
                    panksepp_activation={"SEEKING": 0.7},
                    valence=0.4,
                    arousal=0.5,
                    dominant_system="SEEKING",
                )
            )
            helios.phi_engine = SimpleNamespace(
                label=SimpleNamespace(value="focused"),
                feed_sensory=lambda *args, **kwargs: None,
                feed_emotional=lambda *args, **kwargs: None,
                feed_ignition_from_panksepp=lambda *args, **kwargs: None,
                feed_self_model_from_personality=lambda *args, **kwargs: None,
                feed_dmn_from_thinking=lambda *args, **kwargs: None,
                aggregate=lambda: 0.55,
            )
            helios.sec_evaluator.evaluate = MagicMock(
                return_value={"goal_relevance": 0.8, "novelty": 0.4, "pleasantness": 0.2}
            )
            helios.response_pipeline.should_reply = MagicMock(return_value=True)
            helios.response_pipeline.generate_reply = MagicMock(return_value="reply")
            helios.response_pipeline.record_exchange = MagicMock()
            helios._channel_gateway.get_channel_descriptors = MagicMock(
                return_value={"qq": make_output_descriptor("qq")}
            )
            helios._channel_gateway.get_channel_status = MagicMock(
                return_value={"qq": ChannelStatus.CONNECTED}
            )
            helios._channel_gateway.route_outbound = MagicMock(return_value=True)
            helios.regulation.generate_action_proposals = MagicMock(return_value=[])
            helios.thinking_integration = MagicMock(
                generate=MagicMock(
                    side_effect=lambda state: (
                        setattr(state, "dmn_active", True),
                        setattr(state, "thought_generated_this_tick", False),
                        setattr(state, "last_thought_type", ""),
                        setattr(state, "last_thought_cycle_result", {"triggered": False, "trigger_reason": "test_no_thought"}),
                        SimpleNamespace(
                            triggered=False,
                            thought=None,
                        ),
                    )[-1]
                )
            )

            helios._msg_queue.put({"text": "聊聊你刚刚在想什么", "user_id": "user-a", "channel_id": "qq"})

            helios._tick()

            helios.response_pipeline.generate_reply.assert_not_called()
            assert helios.last_thought_cycle_result["triggered"] is False
            assert helios.last_thought_cycle_result["trigger_reason"] == "test_no_thought"
            assert helios.response_pipeline.record_exchange.call_args.kwargs["reply"] is None
        finally:
            for handler in list(helios.log.handlers):
                handler.close()
                helios.log.removeHandler(handler)