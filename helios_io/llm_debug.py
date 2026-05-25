from __future__ import annotations

import json
import logging
import os
from typing import Mapping


def _is_enabled(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def prompt_debug_enabled() -> bool:
    return _is_enabled(os.getenv("HELIOS_LLM_DEBUG_PROMPTS"), True)


def prompt_debug_limit() -> int:
    raw = os.getenv("HELIOS_LLM_DEBUG_PROMPT_MAX_CHARS", "4000")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 4000
    return max(200, value)


def trim_for_log(text: str, limit: int | None = None) -> str:
    normalized = str(text).replace("\n", "\\n").strip()
    max_chars = prompt_debug_limit() if limit is None else max(80, int(limit))
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 3] + "..."


def _format_metadata(metadata: Mapping[str, object] | None) -> str:
    payload = dict(metadata or {})
    if not payload:
        return "{}"
    return trim_for_log(json.dumps(payload, ensure_ascii=False, sort_keys=True), 800)


def log_llm_request(
    logger: logging.Logger,
    *,
    path: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
    timeout: float | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    logger.debug(
        "LLM call: path=%s model=%s system_len=%d user_len=%d temperature=%s timeout=%s metadata=%s",
        path,
        model,
        len(system_prompt),
        len(user_prompt),
        "" if temperature is None else f"{float(temperature):.3f}",
        "" if timeout is None else f"{float(timeout):.3f}",
        _format_metadata(metadata),
    )
    if prompt_debug_enabled():
        logger.debug(
            "LLM prompt dump: path=%s system_prompt=%r user_prompt=%r",
            path,
            trim_for_log(system_prompt),
            trim_for_log(user_prompt),
        )


def log_llm_response(
    logger: logging.Logger,
    *,
    path: str,
    raw_text: str,
    clean_text: str | None = None,
    metadata: Mapping[str, object] | None = None,
) -> None:
    logger.debug(
        "LLM response: path=%s raw=%r clean=%r metadata=%s",
        path,
        trim_for_log(raw_text, 500),
        trim_for_log(clean_text, 320) if clean_text is not None else "",
        _format_metadata(metadata),
    )
