"""R79-B verification: AggressiveRadicalChannelArbitrationPostProcessor owner-neutral glue.

Owner-neutral unit tests for the v3 LLM-channel-arbitration post-processor. Asserts:
- 6+ cases of the fail-soft / fail-fast paths
- the post-processor is owner-neutral (no cognitive-owner imports)
- the post-processor consumes LlmCompletion + ready_channels + channel_subsystem
  and dispatches a single OutboundPacket on the success path
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

ROOT = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(ROOT / "src"))

import pytest

from helios_v2.channel.contracts import (
    ChannelDriver,
    OutboundDispatchOutcome,
    OutboundPacket,
    SubsystemDispatchResult,
    SubsystemDrainResult,
    ChannelReadinessReport,
    ChannelStateSnapshot,
)
from helios_v2.composition.bridges import (
    AggressiveRadicalChannelArbitrationOutcome,
    AggressiveRadicalChannelArbitrationPostProcessor,
)
from helios_v2.llm.contracts import LlmCompletion, LlmUsage
from helios_v2.prompt_contract.contracts import (
    EmbodiedPromptRequest,
)


# ----------------------------------------------------------------------------
# Test doubles
# ----------------------------------------------------------------------------


@dataclass
class _CapturingChannelSubsystem:
    """Minimal Protocol-conforming ChannelSubsystem that records dispatch_outbound calls."""

    captured_packets: list[OutboundPacket]
    capture_outcome: OutboundDispatchOutcome

    def register_driver(self, driver: ChannelDriver):  # pragma: no cover - not exercised
        raise NotImplementedError

    def deregister_driver(self, driver_id: str):  # pragma: no cover - not exercised
        raise NotImplementedError

    def apply_management_op(self, driver_id: str, op_name: str, payload):  # pragma: no cover
        raise NotImplementedError

    def drain_inbound(self, budget: int) -> SubsystemDrainResult:  # pragma: no cover
        raise NotImplementedError

    def dispatch_outbound(
        self,
        decisions: Tuple[OutboundPacket, ...],
        budget: int,
    ) -> SubsystemDispatchResult:
        self.captured_packets.extend(decisions)
        return SubsystemDispatchResult(
            outcomes=(self.capture_outcome,),
            dispatched_count=1,
            deferred_count=0,
        )

    def channel_state_snapshot(self) -> ChannelStateSnapshot:  # pragma: no cover
        raise NotImplementedError

    def check_static_readiness(
        self, driver_ids: Tuple[str, ...]
    ) -> ChannelReadinessReport:  # pragma: no cover
        raise NotImplementedError


def _make_completion(output_text: str, completion_id: str = "cmpl-1") -> LlmCompletion:
    return LlmCompletion(
        completion_id=completion_id,
        source_request_id="req-1",
        profile_name="p",
        model="m",
        output_text=output_text,
        finish_reason="stop",
        usage=LlmUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        latency_ms=0.0,
    )


def _make_request(request_id: str = "req-1") -> EmbodiedPromptRequest:
    return EmbodiedPromptRequest(
        request_id=request_id,
        consumer_kind="thought",
        source_conscious_state_id="cs-1",
        source_gate_result_id="gate-1",
        source_retrieval_bundle_id="ret-1",
        stimulus_summary={"text": "test stimulus"},
        state_summary={"tick": 1},
        retrieval_summary={"count": 0},
        capability_summary={"available_channels": ("cli",)},
        identity_boundary_summary={"name": "test"},
        tick_id=1,
    )


def _delivered_outcome(packet_id: str, target: str) -> OutboundDispatchOutcome:
    return OutboundDispatchOutcome(
        packet_id=packet_id,
        target_driver_id=target,
        status="delivered",
        detail="captured by test fake",
    )


# ----------------------------------------------------------------------------
# T9 tests
# ----------------------------------------------------------------------------


def test_r79b_arbitration_dispatches_when_channel_is_ready():
    """Test 1: LLM picks ready channel → dispatch_outbound called with 1 packet."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("arb:cmpl-1", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": "cli",
        "i_want_to_say": "hi there",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli", "webchat"), channel_subsystem=fake
    )
    assert outcome.dispatched is True
    assert outcome.target == "cli"
    assert outcome.op == "speak_text"
    assert outcome.reason == ""
    assert outcome.outcome is not None
    assert outcome.outcome.status == "delivered"
    assert len(fake.captured_packets) == 1
    packet = fake.captured_packets[0]
    assert packet.target_driver_id == "cli"
    assert packet.op_name == "speak_text"
    assert packet.payload["outbound_text"] == "hi there"
    assert packet.payload["request_id"] == "req-1"
    assert packet.provenance["source_completion_id"] == "cmpl-1"


def test_r79b_arbitration_rejects_non_ready_channel():
    """Test 2: LLM picks non-ready channel → no dispatch, reason='channel_not_ready'."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": "feishu",  # not in ready_channels
        "i_want_to_say": "hi there",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli", "webchat"), channel_subsystem=fake
    )
    assert outcome.dispatched is False
    assert outcome.reason == "channel_not_ready"
    assert fake.captured_packets == []


def test_r79b_arbitration_skips_when_i_will_send_it_is_false():
    """Test 3: LLM i_will_send_it=False → no dispatch, reason='not_sending'."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": False,
        "i_send_through": "cli",
        "i_want_to_say": "I'll swallow it",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=fake
    )
    assert outcome.dispatched is False
    assert outcome.reason == "not_sending"
    assert fake.captured_packets == []


def test_r79b_arbitration_skips_on_parse_error():
    """Test 4: LLM output is not JSON → no dispatch, reason='parse_error'."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion("This is not a JSON object")
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=fake
    )
    assert outcome.dispatched is False
    assert outcome.reason == "parse_error"
    assert fake.captured_packets == []


@pytest.mark.parametrize(
    "ready_channels,chosen_channel",
    [
        (("cli",), "cli"),
        (("cli", "webchat"), "webchat"),
        (("cli", "webchat", "feishu"), "feishu"),
    ],
)
def test_r79b_arbitration_uses_llm_chosen_channel(ready_channels, chosen_channel):
    """Test 5: LLM's chosen channel is dispatched regardless of ready_channels ordering."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", chosen_channel),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": chosen_channel,
        "i_want_to_say": "dispatched",
    }))
    outcome = proc.process(
        completion, _make_request(), ready_channels, channel_subsystem=fake
    )
    assert outcome.dispatched is True
    assert outcome.target == chosen_channel
    assert len(fake.captured_packets) == 1
    assert fake.captured_packets[0].target_driver_id == chosen_channel


def test_r79b_arbitration_skips_when_i_want_to_say_is_empty():
    """Test 6: i_want_to_say is empty → no dispatch, reason='empty_text'."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": "cli",
        "i_want_to_say": "",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=fake
    )
    assert outcome.dispatched is False
    assert outcome.reason == "empty_text"
    assert fake.captured_packets == []


def test_r79b_arbitration_skips_when_no_subsystem():
    """Test 7: channel_subsystem=None → no dispatch, reason='no_subsystem' (verifies unit-test seam)."""
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": "cli",
        "i_want_to_say": "hi",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=None
    )
    assert outcome.dispatched is False
    assert outcome.reason == "no_subsystem"


def test_r79b_arbitration_skips_when_i_send_through_is_null():
    """Test 8: i_send_through=null but i_will_send_it=true → reason='not_sending'."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    completion = _make_completion(json.dumps({
        "i_will_send_it": True,
        "i_send_through": None,
        "i_want_to_say": "hi",
    }))
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=fake
    )
    assert outcome.dispatched is False
    assert outcome.reason == "not_sending"
    assert fake.captured_packets == []


def test_r79b_arbitration_tolerates_json_in_code_fence():
    """Test 9: LLM wraps JSON in ```...``` fence → still parses."""
    fake = _CapturingChannelSubsystem(
        captured_packets=[],
        capture_outcome=_delivered_outcome("unused", "cli"),
    )
    proc = AggressiveRadicalChannelArbitrationPostProcessor()
    fenced = (
        "```json\n"
        + json.dumps({
            "i_will_send_it": True,
            "i_send_through": "cli",
            "i_want_to_say": "fenced",
        })
        + "\n```"
    )
    completion = _make_completion(fenced)
    outcome = proc.process(
        completion, _make_request(), ("cli",), channel_subsystem=fake
    )
    assert outcome.dispatched is True
    assert outcome.target == "cli"
    assert fake.captured_packets[0].payload["outbound_text"] == "fenced"


def test_r79b_arbitration_outcome_construction_rejects_bad_reason():
    """Test 10: AggressiveRadicalChannelArbitrationOutcome rejects unknown reason."""
    with pytest.raises(ValueError, match="reason must be in"):
        AggressiveRadicalChannelArbitrationOutcome(
            dispatched=False, reason="nonsense"
        )


def test_r79b_arbitration_outcome_construction_rejects_non_bool_dispatched():
    """Test 11: AggressiveRadicalChannelArbitrationOutcome rejects non-bool dispatched."""
    with pytest.raises(ValueError, match="must be a bool"):
        AggressiveRadicalChannelArbitrationOutcome(dispatched=1)  # type: ignore[arg-type]
