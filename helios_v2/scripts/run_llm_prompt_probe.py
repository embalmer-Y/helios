"""Run real LLM prompt probes against one or more OpenAI-compatible targets.

This script is intended for prompt and model comparison work under the `helios_v2/scripts/` toolbox.
It does not participate in the Helios runtime. Instead, it lets you:

- send one real system/user prompt pair to one or more models
- compare outputs across targets
- assert basic expectations via must-contain / must-not-contain rules
- optionally persist a structured JSON report for later review

Examples:

    python helios_v2/scripts/run_llm_prompt_probe.py \
        --system-prompt "You are a concise assistant." \
        --user-prompt "Summarize the difference between focal and supporting context." \
        --model gpt-4.1-mini \
        --model deepseek/deepseek-v4-flash \
        --must-contain focal \
        --must-contain supporting

    python helios_v2/scripts/run_llm_prompt_probe.py --case-file helios_v2/scripts/prompt_case.json --save-json logs/prompt_probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "deepseek/deepseek-v4-flash"


@dataclass(frozen=True)
class PromptCase:
    system_prompt: str
    user_prompt: str
    must_contain: tuple[str, ...]
    must_not_contain: tuple[str, ...]
    temperature: float
    max_tokens: int
    timeout: float
    response_format_json: bool
    strip_reasoning: bool = False


@dataclass(frozen=True)
class TargetDefinition:
    name: str
    model: str
    api_key_env: str
    base_url_env: str
    base_url_override: str | None


@dataclass(frozen=True)
class ResolvedTarget:
    name: str
    model: str
    api_key_env: str
    base_url_env: str
    base_url: str
    api_key_present: bool


def _read_text_option(direct_value: str | None, file_path: str | None, label: str) -> str | None:
    if direct_value is not None and file_path is not None:
        raise SystemExit(f"Provide either --{label} or --{label}-file, not both.")
    if file_path is not None:
        return Path(file_path).read_text(encoding="utf-8")
    return direct_value


def _parse_case_file(case_file: Path) -> tuple[PromptCase, tuple[TargetDefinition, ...]]:
    payload = json.loads(case_file.read_text(encoding="utf-8"))
    prompt_case = PromptCase(
        system_prompt=str(payload["system_prompt"]),
        user_prompt=str(payload["user_prompt"]),
        must_contain=tuple(str(item) for item in payload.get("must_contain", [])),
        must_not_contain=tuple(str(item) for item in payload.get("must_not_contain", [])),
        temperature=float(payload.get("temperature", 0.2)),
        max_tokens=int(payload.get("max_tokens", 800)),
        timeout=float(payload.get("timeout", 30.0)),
        response_format_json=bool(payload.get("response_format_json", False)),
        strip_reasoning=bool(payload.get("strip_reasoning", False)),
    )
    target_definitions = tuple(
        TargetDefinition(
            name=str(item.get("name") or item["model"]),
            model=str(item["model"]),
            api_key_env=str(item.get("api_key_env", "OPENAI_API_KEY")),
            base_url_env=str(item.get("base_url_env", "OPENAI_BASE_URL")),
            base_url_override=(
                str(item["base_url"]) if item.get("base_url") is not None else None
            ),
        )
        for item in payload.get("targets", [])
    )
    return prompt_case, target_definitions


def _build_case_from_args(args: argparse.Namespace) -> PromptCase:
    system_prompt = _read_text_option(args.system_prompt, args.system_prompt_file, "system-prompt")
    user_prompt = _read_text_option(args.user_prompt, args.user_prompt_file, "user-prompt")
    if system_prompt is None or user_prompt is None:
        raise SystemExit(
            "A prompt case requires both system and user prompts. Use --case-file or provide both direct/file prompt inputs."
        )
    return PromptCase(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        must_contain=tuple(args.must_contain),
        must_not_contain=tuple(args.must_not_contain),
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
        response_format_json=args.response_format_json,
        strip_reasoning=args.strip_reasoning,
    )


def _build_targets_from_args(args: argparse.Namespace) -> tuple[TargetDefinition, ...]:
    models = tuple(args.model) if args.model else (os.getenv("HELIOS_LLM_MODEL", DEFAULT_MODEL),)
    return tuple(
        TargetDefinition(
            name=model,
            model=model,
            api_key_env=args.api_key_env,
            base_url_env=args.base_url_env,
            base_url_override=args.base_url,
        )
        for model in models
    )


def _resolve_target(target: TargetDefinition) -> tuple[ResolvedTarget, str]:
    api_key = os.getenv(target.api_key_env, "")
    env_base_url = os.getenv(target.base_url_env, "")
    base_url = target.base_url_override or env_base_url or DEFAULT_BASE_URL
    if not api_key:
        raise SystemExit(
            f"Environment variable {target.api_key_env} is required for target '{target.name}' ({target.model})."
        )
    return (
        ResolvedTarget(
            name=target.name,
            model=target.model,
            api_key_env=target.api_key_env,
            base_url_env=target.base_url_env,
            base_url=base_url,
            api_key_present=True,
        ),
        api_key,
    )


def _strip_reasoning(text: str) -> str:
    """Mirror the `11` internal-thought parser's robustness: strip a leading reasoning `<think>`
    block and surrounding ```json code fences before JSON parsing, so a reasoning model's output
    (e.g. MiniMax-M3) is evaluated the same way the real runtime parses it."""

    import re

    stripped = text.strip()
    # Remove a leading <think>...</think> block (reasoning models emit one before the answer).
    stripped = re.sub(r"^<think>.*?</think>", "", stripped, count=1, flags=re.DOTALL).strip()
    # Remove a surrounding markdown code fence (```json ... ``` or ``` ... ```).
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, flags=re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    return stripped


def _evaluate_expectations(text: str, prompt_case: PromptCase) -> dict[str, Any]:
    missing = [needle for needle in prompt_case.must_contain if needle not in text]
    forbidden = [needle for needle in prompt_case.must_not_contain if needle in text]
    json_parse_ok: bool | None = None
    json_error: str | None = None
    if prompt_case.response_format_json:
        candidate = _strip_reasoning(text) if prompt_case.strip_reasoning else text
        try:
            json.loads(candidate)
        except json.JSONDecodeError as exc:
            json_parse_ok = False
            json_error = str(exc)
        else:
            json_parse_ok = True
    passed = not missing and not forbidden and json_parse_ok is not False
    return {
        "passed": passed,
        "missing_must_contain": missing,
        "matched_must_not_contain": forbidden,
        "json_parse_ok": json_parse_ok,
        "json_error": json_error,
    }


def _extract_usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _call_target(
    target: ResolvedTarget,
    api_key: str,
    prompt_case: PromptCase,
) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit("The openai package is required. Install it in the active environment first.") from exc

    client = OpenAI(api_key=api_key, base_url=target.base_url)
    request_payload: dict[str, Any] = {
        "model": target.model,
        "messages": [
            {"role": "system", "content": prompt_case.system_prompt},
            {"role": "user", "content": prompt_case.user_prompt},
        ],
        "temperature": prompt_case.temperature,
        "max_tokens": prompt_case.max_tokens,
        "timeout": prompt_case.timeout,
    }
    if prompt_case.response_format_json:
        request_payload["response_format"] = {"type": "json_object"}

    started_at = time.perf_counter()
    response = client.chat.completions.create(**request_payload)
    elapsed_seconds = time.perf_counter() - started_at
    output_text = response.choices[0].message.content or ""
    return {
        "target": asdict(target),
        "elapsed_seconds": round(float(elapsed_seconds), 3),
        "finish_reason": response.choices[0].finish_reason,
        "output_text": output_text,
        "usage": _extract_usage(response),
        "expectations": _evaluate_expectations(output_text, prompt_case),
    }


def _print_result(result: dict[str, Any], preview_chars: int) -> None:
    target = result["target"]
    expectations = result["expectations"]
    status = "PASS" if expectations["passed"] else "FAIL"
    print(f"[{status}] {target['name']} ({target['model']})")
    print(f"  base_url: {target['base_url']}")
    print(f"  elapsed_seconds: {result['elapsed_seconds']}")
    print(f"  finish_reason: {result['finish_reason']}")
    if result["usage"] is not None:
        print(f"  usage: {json.dumps(result['usage'], ensure_ascii=False)}")
    if expectations["missing_must_contain"]:
        print(
            "  missing_must_contain: "
            + json.dumps(expectations["missing_must_contain"], ensure_ascii=False)
        )
    if expectations["matched_must_not_contain"]:
        print(
            "  matched_must_not_contain: "
            + json.dumps(expectations["matched_must_not_contain"], ensure_ascii=False)
        )
    if expectations["json_parse_ok"] is False:
        print(f"  json_error: {expectations['json_error']}")
    preview = result["output_text"][:preview_chars]
    if len(result["output_text"]) > preview_chars:
        preview = preview + "..."
    print("  output_preview:")
    for line in preview.splitlines() or [""]:
        print(f"    {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a real prompt probe against one or more OpenAI-compatible LLM targets.",
    )
    parser.add_argument(
        "--case-file",
        help="Optional JSON file containing the prompt case and optional target definitions.",
    )
    parser.add_argument("--system-prompt", help="System prompt text.")
    parser.add_argument("--system-prompt-file", help="Path to a UTF-8 file containing the system prompt.")
    parser.add_argument("--user-prompt", help="User prompt text.")
    parser.add_argument("--user-prompt-file", help="Path to a UTF-8 file containing the user prompt.")
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help="Model name to probe. Repeat to compare multiple models against the same endpoint config.",
    )
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the API key for CLI-defined targets.",
    )
    parser.add_argument(
        "--base-url-env",
        default="OPENAI_BASE_URL",
        help="Environment variable containing the base URL for CLI-defined targets.",
    )
    parser.add_argument(
        "--base-url",
        help="Explicit base URL override for CLI-defined targets. Defaults to the env value, then OpenAI public API.",
    )
    parser.add_argument(
        "--must-contain",
        action="append",
        default=[],
        help="Substring that must appear in the model output. Repeat for multiple checks.",
    )
    parser.add_argument(
        "--must-not-contain",
        action="append",
        default=[],
        help="Substring that must not appear in the model output. Repeat for multiple checks.",
    )
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature.")
    parser.add_argument("--max-tokens", type=int, default=800, help="Maximum completion tokens.")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds.")
    parser.add_argument(
        "--response-format-json",
        action="store_true",
        help="Request JSON object output and validate that the returned content parses as JSON.",
    )
    parser.add_argument(
        "--strip-reasoning",
        action="store_true",
        help="Before the JSON check, strip a leading <think>...</think> block and ```json fences, "
        "mirroring the `11` internal-thought parser. Use this for reasoning models (e.g. MiniMax-M3).",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=800,
        help="Maximum number of output characters to print per target.",
    )
    parser.add_argument(
        "--save-json",
        help="Optional path for a structured JSON report.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.case_file:
        prompt_case, case_targets = _parse_case_file(Path(args.case_file))
    else:
        prompt_case = _build_case_from_args(args)
        case_targets = ()

    targets = case_targets or _build_targets_from_args(args)
    if not targets:
        raise SystemExit("At least one target must be defined either in --case-file or via --model.")

    results: list[dict[str, Any]] = []
    for target_definition in targets:
        resolved_target, api_key = _resolve_target(target_definition)
        results.append(_call_target(resolved_target, api_key, prompt_case))

    print(
        f"Ran prompt probe across {len(results)} target(s). "
        f"must_contain={len(prompt_case.must_contain)} must_not_contain={len(prompt_case.must_not_contain)}"
    )
    for result in results:
        _print_result(result, preview_chars=args.preview_chars)

    if args.save_json:
        payload = {
            "prompt_case": asdict(prompt_case),
            "results": results,
        }
        output_path = Path(args.save_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved JSON report to {output_path}")

    return 0 if all(result["expectations"]["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())