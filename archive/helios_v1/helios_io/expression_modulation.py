"""Shared outbound expression modulation for text and speech channels."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _has_explicit_intensity(metadata: Mapping[str, Any]) -> bool:
    return "outbound_intensity" in metadata or "normalized_intensity" in metadata


def _looks_cjk(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def _punctuation_family(text: str) -> tuple[str, str, str]:
    if _looks_cjk(text):
        return "。", "！", "？"
    return ".", "!", "?"


def _collapse_runs(text: str) -> str:
    collapsed = re.sub(r"[ \t]+", " ", text).strip()
    collapsed = re.sub(r"([,，;；:：])\1+", r"\1", collapsed)
    collapsed = re.sub(r"([!！?？])\1{1,}", r"\1", collapsed)
    collapsed = re.sub(r"(?:\.{3,}|…{2,})", "…" if _looks_cjk(collapsed) else "...", collapsed)
    return collapsed


def _soften_terminal(text: str) -> str:
    period, _exclaim, question = _punctuation_family(text)
    if text.endswith(("?", "？")):
        return text[:-1].rstrip("!！。.,，;；:：…") + question
    stem = text.rstrip("!！。.,，;；:：…")
    return f"{stem}{period}" if stem else text


def _intensify_terminal(text: str) -> str:
    _period, exclaim, question = _punctuation_family(text)
    if text.endswith(("?", "？")):
        return text[:-1].rstrip("!！。.,，;；:：…") + question
    stem = text.rstrip("!！。.,，;；:：…")
    return f"{stem}{exclaim}" if stem else text


@dataclass(frozen=True)
class ExpressionModulationResult:
    rendered_text: str
    normalized_intensity: float
    applied: bool
    tone: str
    compactness: str

    def to_metadata(self) -> dict[str, Any]:
        return {
            "rendered_text": self.rendered_text,
            "normalized_intensity": self.normalized_intensity,
            "applied": self.applied,
            "tone": self.tone,
            "compactness": self.compactness,
        }


def modulate_outbound_expression(text: str, metadata: Mapping[str, Any] | None = None) -> ExpressionModulationResult:
    payload = dict(metadata or {})
    normalized_text = _collapse_runs(text or "")
    if not normalized_text or not _has_explicit_intensity(payload):
        return ExpressionModulationResult(
            rendered_text=text,
            normalized_intensity=_clamp(float(payload.get("outbound_intensity", payload.get("normalized_intensity", 0.0)) or 0.0)),
            applied=False,
            tone="unchanged",
            compactness="unchanged",
        )

    intensity = _clamp(float(payload.get("outbound_intensity", payload.get("normalized_intensity", 0.0)) or 0.0))
    if intensity < 0.34:
        return ExpressionModulationResult(
            rendered_text=_soften_terminal(normalized_text),
            normalized_intensity=intensity,
            applied=True,
            tone="measured",
            compactness="compact",
        )
    if intensity < 0.67:
        return ExpressionModulationResult(
            rendered_text=normalized_text,
            normalized_intensity=intensity,
            applied=True,
            tone="steady",
            compactness="preserved",
        )
    return ExpressionModulationResult(
        rendered_text=_intensify_terminal(normalized_text),
        normalized_intensity=intensity,
        applied=True,
        tone="direct",
        compactness="compact",
    )