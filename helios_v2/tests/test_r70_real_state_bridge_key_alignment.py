"""R78 verification: the R70 semantic bridges read real 04/05 state, not constant fallback.

Owner-neutral end-to-end test. Asserts that a default-assembly tick produces an LLM user
message whose 04 neuromodulator and 05 feeling projections contain real bounded values,
not the literal fallback strings "neuromodulators at tonic baseline" or
"feeling at baseline".

This test is the executable form of R78 §7 acceptance criteria #1, #2, and #4.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path("/root/project/helios/helios_v2")
sys.path.insert(0, str(ROOT / "src"))

import pytest

from helios_v2.composition import assemble_runtime
from helios_v2.llm import (
    LlmCompletion,
    LlmMessage,
    LlmProfileReadiness,
    LlmReadinessReport,
    LlmRequest,
    LlmUsage,
)
from helios_v2.sensory import RawSignal


@dataclass
class _CapturingGateway:
    """Mock LLM gateway that captures every LlmRequest and returns a minimal stub."""

    captured_requests: list[LlmRequest] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.captured_requests is None:
            self.captured_requests = []

    def check_static_readiness(self, profile_names):  # LLM seam
        return LlmReadinessReport(
            report_id="r78-verification",
            checked_live=False,
            entries=tuple(
                LlmProfileReadiness(
                    profile_name=name,
                    exists=True,
                    static_ready=True,
                    live_ready=None,
                    detail="r78-mock ready",
                )
                for name in profile_names
            ),
        )

    def complete(self, request: LlmRequest) -> LlmCompletion:
        self.captured_requests.append(request)
        body = json.dumps({
            "thought": "r78 verification thought",
            "sufficiency": 0.8,
            "wants_to_continue": False,
            "continue_reason": "",
            "proposed_action": {"intends_action": False, "summary": ""},
            "self_revision": {"intends_revision": False, "summary": ""},
        })
        return LlmCompletion(
            completion_id=f"r78:completion:{request.request_id}",
            source_request_id=request.request_id,
            profile_name=request.target_profile,
            model="r78-mock",
            output_text=body,
            finish_reason="stop",
            usage=LlmUsage(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            latency_ms=0.0,
        )


@dataclass
class _FakeCliSource:
    name: str = "r78-cli-source"
    content: str = ""

    @property
    def source_name(self) -> str:
        return self.name

    def emit_raw_signals(self) -> tuple[RawSignal, ...]:
        if not self.content:
            return ()
        return (
            RawSignal(
                signal_id="r78-sig-001",
                source_name=self.name,
                signal_type="text",
                content=self.content,
                channel="cli",
                metadata={"user_id": "user:r78-test"},
            ),
        )


def test_r78_real_state_bridge_projects_04_neuromodulator_levels_to_llm() -> None:
    """R78 §7.1: a default-assembly tick must project real 04 levels, not constant fallback."""
    mock = _CapturingGateway()
    handle = assemble_runtime(deterministic_thought=False, gateway=mock)
    cli = _FakeCliSource(content="Hello.")
    handle.ingress.register_source(cli)
    handle.startup()
    handle.tick()

    assert len(mock.captured_requests) == 1
    user_msg = next(
        msg for msg in mock.captured_requests[0].messages
        if isinstance(msg, LlmMessage) and msg.role == "user"
    )
    content = user_msg.content

    # The R70 internal_state_summary uses the prefix "DA " for real projection.
    assert "DA " in content, (
        f"R78 violation: 04 neuromodulator projection missing 'DA ' prefix. "
        f"Fallback '{('neuromodulators at tonic baseline' in content)=}'. "
        f"User message:\n{content}"
    )
    # The constant fallback must NOT appear.
    assert "neuromodulators at tonic baseline" not in content, (
        f"R78 violation: 04 neuromodulator projection is the constant fallback. "
        f"User message:\n{content}"
    )


def test_r78_real_state_bridge_projects_05_feeling_vector_to_llm() -> None:
    """R78 §7.2: a default-assembly tick must project real 05 feeling, not constant fallback."""
    mock = _CapturingGateway()
    handle = assemble_runtime(deterministic_thought=False, gateway=mock)
    cli = _FakeCliSource(content="Hello.")
    handle.ingress.register_source(cli)
    handle.startup()
    handle.tick()

    assert len(mock.captured_requests) == 1
    user_msg = next(
        msg for msg in mock.captured_requests[0].messages
        if isinstance(msg, LlmMessage) and msg.role == "user"
    )
    content = user_msg.content

    # The R70 internal_state_summary uses the prefix "arousal " for real projection.
    assert "arousal " in content, (
        f"R78 violation: 05 feeling projection missing 'arousal ' prefix. "
        f"Fallback '{('feeling at baseline' in content)=}'. "
        f"User message:\n{content}"
    )
    # The constant fallback must NOT appear.
    assert "feeling at baseline" not in content, (
        f"R78 violation: 05 feeling projection is the constant fallback. "
        f"User message:\n{content}"
    )


def test_r78_affective_summary_projection_uses_real_05_vector() -> None:
    """R78 §7.3: state_summary['affective_summary'] derives from real 05, not constant."""
    # The affective_summary path lives in the state_summary dict, rendered into the
    # prompt-contract layer "embodied_state". To verify it end-to-end, we can also
    # assert that no literal constant fallback appears anywhere in the rendered prompt.
    mock = _CapturingGateway()
    handle = assemble_runtime(deterministic_thought=False, gateway=mock)
    cli = _FakeCliSource(content="Tell me how you feel.")
    handle.ingress.register_source(cli)
    handle.startup()
    handle.tick()

    user_msg = next(
        msg for msg in mock.captured_requests[0].messages
        if isinstance(msg, LlmMessage) and msg.role == "user"
    )
    content = user_msg.content

    # The internal_state_text projection (which always embeds 04/05) covers both 04 and
    # 05 once R78 is in place. The earlier two tests assert each key individually; this
    # test asserts that the whole user message is grounded in real state.
    assert "Neuromodulators:" in content
    assert "Feeling:" in content
    assert "Salience:" in content
    # No literal fallback may appear in any of the three projection fields.
    assert "neuromodulators at tonic baseline" not in content
    assert "feeling at baseline" not in content


def test_r78_04_levels_vary_across_ticks_with_salience() -> None:
    """R78 §7.6: varying stimuli produce measurably different 04/05 projection text."""
    mock = _CapturingGateway()
    handle = assemble_runtime(deterministic_thought=False, gateway=mock)
    cli = _FakeCliSource(content="initial stimulus")
    handle.ingress.register_source(cli)
    handle.startup()
    handle.tick()
    cli.content = "URGENT WARNING: critical anomaly detected"
    handle.tick()
    cli.content = "calm and routine check"
    handle.tick()

    assert len(mock.captured_requests) == 3
    user_contents = [
        next(
            msg for msg in req.messages
            if isinstance(msg, LlmMessage) and msg.role == "user"
        ).content
        for req in mock.captured_requests
    ]
    # All three user messages must carry the real projection format.
    for i, c in enumerate(user_contents):
        assert "DA " in c, f"tick {i}: 04 projection missing"
        assert "arousal " in c, f"tick {i}: 05 projection missing"
    # The three projections should be distinct (we don't pin specific values because
    # the salience dynamics are emergent; we only assert that the text changes).
    projection_lines = [
        c.split("Salience:")[0] if "Salience:" in c else c
        for c in user_contents
    ]
    assert len(set(projection_lines)) >= 2, (
        f"Expected the 04/05 projection to differ across at least 2 of 3 ticks; "
        f"got identical text:\n{projection_lines[0]}"
    )
