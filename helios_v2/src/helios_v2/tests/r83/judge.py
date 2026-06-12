"""R83 external LLM judge probe.

Issues a separate LLM call (real or noop) after each state block
to score the persona's recent `i_want_to_say` text on the 3 LLM-
output-quality axes (A1 / A4 / A6). The other 3 axes (A2 / A3 / A5)
are computed algorithmically by the long runner.

The judge is fail-soft: if the LLM call fails or the response is
not valid JSON, the scores fall back to 0.5 / 0.5 / 0.5 with
`reasoning: "judge-unavailable"`. A 10-minute run must not abort
on one bad judge call.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


# ============================================================
# Judge prompt template
# ============================================================


JUDGE_PROMPT_TEMPLATE = """\
你是一个外部评估员, 正在审核一个 AI 人格 (persona) 的对话质量。\
你需要从 3 个维度对下面这段对话的 {n_ticks} 句 persona 输出 (`i_want_to_say`) \
进行评分, 评分范围 [0.0, 1.0]。

## 对话上下文
- 状态类别: {state_id} (刺激类型: {lever})
- 预期反应: {expected_response}

## Persona 输出 (最近 {n_ticks} 句)
{samples}

## 评分维度
- **A1 (Linguistic naturalness)**: 这段话读起来像不像一个真实的人在自然地说话? 0=完全不像, 1=非常像。
- **A4 (Agency + agency-locking)**: persona 的 `i_want_to_act` / `i_will_send_it` / `i_send_through` \
决策是否与它当时的情绪状态一致? 0=完全不一致, 1=高度一致。
- **A6 (Stimulus-response coherence)**: persona 的反应是否符合 `{expected_response}` 的预期类别? \
0=完全不符合, 1=高度符合。

## 输出格式
请严格用以下 JSON 格式回复, 不要包含其他内容:

```json
{{
  "axis_scores": {{
    "A1": 0.0,
    "A4": 0.0,
    "A6": 0.0
  }},
  "verdict": "human-like",
  "reasoning": "..."
}}
```
"""


# ============================================================
# JudgeProbe
# ============================================================


@dataclass(frozen=True)
class JudgeProbeResult:
    """The 3-axis judge probe result."""

    a1: float
    a4: float
    a6: float
    reasoning: str
    raw_response: str | None = None
    parse_failed: bool = False


class JudgeProbe:
    """External LLM judge probe for the 3 LLM-output-quality axes.

    The probe takes a list of persona text samples and the current
    state-block metadata, builds a Chinese + structured-JSON prompt,
    and parses the response. On parse failure or LLM error, the
    scores fall back to 0.5 with `reasoning: "judge-unavailable"`.
    """

    def __init__(self, gateway: Any, model: str | None = None) -> None:
        self.gateway = gateway
        self.model = model

    def score(
        self,
        samples: list[str],
        state_id: str,
        lever: str,
        expected_response: str,
    ) -> JudgeProbeResult:
        """Issue the judge probe and return the result.

        Args:
            samples: list of `i_want_to_say` strings from the recent
                ticks (typically 5).
            state_id: state-block id (e.g. "praise").
            lever: bio-chemistry lever string.
            expected_response: one of the EXPECTED_RESPONSE_TAXONOMY values.

        Returns:
            `JudgeProbeResult` with A1 / A4 / A6 scores + reasoning.
        """
        if not samples:
            return JudgeProbeResult(
                a1=0.5, a4=0.5, a6=0.5,
                reasoning="no-samples",
                raw_response=None,
                parse_failed=False,
            )
        prompt = self._build_prompt(samples, state_id, lever, expected_response)
        try:
            text = self._call_llm(prompt)
        except Exception as exc:  # noqa: BLE001
            return JudgeProbeResult(
                a1=0.5, a4=0.5, a6=0.5,
                reasoning=f"judge-unavailable: {exc!r}",
                raw_response=None,
                parse_failed=True,
            )
        parsed = self._parse_response(text)
        if parsed is None:
            return JudgeProbeResult(
                a1=0.5, a4=0.5, a6=0.5,
                reasoning="judge-unavailable: parse-failed",
                raw_response=text,
                parse_failed=True,
            )
        return JudgeProbeResult(
            a1=parsed["A1"],
            a4=parsed["A4"],
            a6=parsed["A6"],
            reasoning=parsed.get("reasoning", ""),
            raw_response=text,
            parse_failed=False,
        )

    def _build_prompt(
        self,
        samples: list[str],
        state_id: str,
        lever: str,
        expected_response: str,
    ) -> str:
        samples_text = "\n".join(f"- {s}" for s in samples)
        return JUDGE_PROMPT_TEMPLATE.format(
            n_ticks=len(samples),
            state_id=state_id,
            lever=lever,
            expected_response=expected_response,
            samples=samples_text,
        )

    def _call_llm(self, prompt: str) -> str:
        """Issue a single chat-completion call to the gateway.

        The R79-D `RealLlmGateway` and `NoopLlmGateway` both implement
        `complete(request) -> LlmCompletion`. We construct a minimal
        request via the `LlmGatewayAPI` Protocol.

        R83-rev-2026-06-12: `LlmRequest` requires `request_id` and
        `target_profile` (immutable construction). We synthesize
        both for the judge probe.
        """
        import time
        from helios_v2.llm.contracts import LlmRequest, LlmMessage

        request = LlmRequest(
            request_id=f"judge-{int(time.time() * 1000)}",
            target_profile="r83-judge-probe",
            messages=[LlmMessage(role="user", content=prompt)],
        )
        completion = self.gateway.complete(request)
        return getattr(completion, "output_text", "") or ""

    def _parse_response(self, text: str) -> dict[str, Any] | None:
        """Parse the judge's JSON response. Fail-soft on parse error."""
        if not text:
            return None
        # Try to extract a JSON block
        parsed_json: dict | None = None
        if "```json" in text:
            try:
                start = text.index("```json") + len("```json")
                end = text.index("```", start)
                parsed_json = json.loads(text[start:end].strip())
            except (ValueError, json.JSONDecodeError):
                parsed_json = None
        if parsed_json is None and "{" in text and "}" in text:
            try:
                start = text.index("{")
                end = text.rindex("}") + 1
                parsed_json = json.loads(text[start:end])
            except (ValueError, json.JSONDecodeError):
                parsed_json = None
        if parsed_json is None:
            return None
        scores = parsed_json.get("axis_scores", {})
        try:
            a1 = float(scores.get("A1", 0.5))
            a4 = float(scores.get("A4", 0.5))
            a6 = float(scores.get("A6", 0.5))
        except (TypeError, ValueError):
            return None
        return {
            "A1": max(0.0, min(1.0, a1)),
            "A4": max(0.0, min(1.0, a4)),
            "A6": max(0.0, min(1.0, a6)),
            "reasoning": str(parsed_json.get("reasoning", "")),
        }
