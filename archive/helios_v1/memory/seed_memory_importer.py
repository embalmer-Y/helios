"""Seed autobiographical memory import helpers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional


logger = logging.getLogger(__name__)


@dataclass
class SeedMoment:
    """A seed autobiographical moment imported from an external document."""

    summary: str
    timestamp: float
    valence: float = 0.0
    arousal: float = 0.0
    emotional_tag: str = "neutral"
    source: str = ""
    original_section: str = ""


class SeedMemoryImporter:
    """Import pre-dated autobiographical seed memories from markdown documents."""

    DEFAULT_SPACING_SECONDS = 3600.0

    def __init__(self, autobio_store, system_start_time: float):
        self._store = autobio_store
        self._system_start = system_start_time

    def import_document(
        self,
        content: str,
        source_label: str,
        base_date: Optional[float] = None,
    ) -> List[SeedMoment]:
        sections = self._parse_sections(content)
        if not sections:
            return []

        anchor = min(base_date if base_date is not None else self._system_start, self._system_start)
        imported: List[SeedMoment] = []

        for index, section in enumerate(sections):
            timestamp = anchor - ((len(sections) - index) * self.DEFAULT_SPACING_SECONDS)
            moment = SeedMoment(
                summary=section["text"],
                timestamp=timestamp,
                valence=section.get("valence", 0.0),
                arousal=section.get("arousal", 0.0),
                emotional_tag=section.get("emotion", "neutral"),
                source=source_label,
                original_section=section.get("heading", ""),
            )
            imported.append(moment)
            self._store.record(
                panksepp={moment.emotional_tag: 0.6} if moment.emotional_tag and moment.emotional_tag != "neutral" else {},
                valence=moment.valence,
                arousal=moment.arousal,
                dominant=moment.emotional_tag if moment.emotional_tag != "neutral" else "",
                phi=0.2,
                narrative=moment.summary,
                event_trigger=moment.original_section,
                timestamp_override=moment.timestamp,
                source=moment.source,
            )

        logger.info("Imported %d seed memories from %s", len(imported), source_label)
        return imported

    def import_inline_memories(
        self,
        memories: List[object],
        source_label: str,
        base_date: Optional[float] = None,
    ) -> List[SeedMoment]:
        normalized: List[dict[str, object]] = []
        for index, memory in enumerate(list(memories or [])):
            if isinstance(memory, str):
                summary = memory.strip()
                if not summary:
                    continue
                normalized.append(
                    {
                        "summary": summary,
                        "source": source_label,
                        "original_section": f"inline_seed_{index + 1}",
                    }
                )
                continue
            if isinstance(memory, dict):
                summary = str(memory.get("summary", "") or "").strip()
                if not summary:
                    continue
                normalized.append(
                    {
                        "summary": summary,
                        "source": str(memory.get("source", source_label) or source_label),
                        "emotional_tag": str(memory.get("emotional_tag", "") or ""),
                        "valence": float(memory.get("valence", 0.0) or 0.0),
                        "arousal": float(memory.get("arousal", 0.0) or 0.0),
                        "original_section": str(memory.get("original_section", f"inline_seed_{index + 1}") or f"inline_seed_{index + 1}"),
                    }
                )
        if not normalized:
            return []

        anchor = min(base_date if base_date is not None else self._system_start, self._system_start)
        imported: List[SeedMoment] = []
        for index, memory_payload in enumerate(normalized):
            memory_text = str(memory_payload.get("summary", "") or "").strip()
            timestamp = anchor - ((len(normalized) - index) * self.DEFAULT_SPACING_SECONDS)
            emotional_tag = str(memory_payload.get("emotional_tag", "") or "") or self._infer_emotion("", memory_text)
            moment = SeedMoment(
                summary=memory_text,
                timestamp=timestamp,
                valence=float(memory_payload.get("valence", self._infer_valence(memory_text)) or self._infer_valence(memory_text)),
                arousal=float(memory_payload.get("arousal", self._infer_arousal(memory_text)) or self._infer_arousal(memory_text)),
                emotional_tag=emotional_tag,
                source=str(memory_payload.get("source", source_label) or source_label),
                original_section=str(memory_payload.get("original_section", f"inline_seed_{index + 1}") or f"inline_seed_{index + 1}"),
            )
            imported.append(moment)
            self._store.record(
                panksepp={moment.emotional_tag: 0.6} if moment.emotional_tag and moment.emotional_tag != "neutral" else {},
                valence=moment.valence,
                arousal=moment.arousal,
                dominant=moment.emotional_tag if moment.emotional_tag != "neutral" else "",
                phi=0.2,
                narrative=moment.summary,
                event_trigger=moment.original_section,
                timestamp_override=moment.timestamp,
                source=moment.source,
            )

        logger.info("Imported %d inline seed memories from %s", len(imported), source_label)
        return imported

    def verify_seed_integrity(self, source_label: str = "") -> bool:
        for moment in getattr(self._store, "moments", []):
            if source_label and getattr(moment, "source", "") != source_label:
                continue
            if not getattr(moment, "source", ""):
                continue
            if moment.timestamp >= self._system_start:
                return False
        return True

    def _parse_sections(self, content: str) -> List[dict]:
        sections: List[dict] = []
        heading = ""
        buffer: List[str] = []

        def flush_section() -> None:
            raw_text = "\n".join(buffer)
            text = "\n".join(line.strip() for line in buffer if line.strip()).strip()
            if text or raw_text:
                section_text = text if text else raw_text.rstrip("\n")
                sections.append(
                    {
                        "heading": heading,
                        "text": section_text,
                        "emotion": self._infer_emotion(heading, section_text),
                        "valence": self._infer_valence(section_text),
                        "arousal": self._infer_arousal(section_text),
                    }
                )

        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            match = re.match(r"^#{1,6}\s+(.*)$", line)
            if match:
                flush_section()
                heading = match.group(1).strip()
                buffer = []
                continue
            buffer.append(raw_line)

        flush_section()
        if sections:
            return sections

        fallback = content.strip()
        if not fallback:
            return []
        return [{
            "heading": "",
            "text": fallback,
            "emotion": self._infer_emotion("", fallback),
            "valence": self._infer_valence(fallback),
            "arousal": self._infer_arousal(fallback),
        }]

    @staticmethod
    def _infer_emotion(heading: str, text: str) -> str:
        haystack = f"{heading} {text}".lower()
        rules = [
            ("CARE", ["care", "love", "温柔", "陪伴", "想你", "抱抱"]),
            ("PANIC", ["panic", "loss", "失去", "害怕", "分离", "不见"]),
            ("FEAR", ["fear", "担心", "不安", "危险", "焦虑"]),
            ("PLAY", ["play", "开心", "快乐", "有趣", "游戏"]),
            ("SEEKING", ["seek", "探索", "发现", "研究", "好奇"]),
            ("RAGE", ["rage", "愤怒", "生气", "恼火"]),
        ]
        for emotion, keywords in rules:
            if any(keyword in haystack for keyword in keywords):
                return emotion
        return "neutral"

    @staticmethod
    def _infer_valence(text: str) -> float:
        lowered = text.lower()
        positive = sum(word in lowered for word in ["love", "care", "happy", "warm", "开心", "喜欢", "温柔"])
        negative = sum(word in lowered for word in ["fear", "loss", "panic", "sad", "害怕", "难过", "不安"])
        return max(-1.0, min(1.0, (positive - negative) * 0.2))

    @staticmethod
    def _infer_arousal(text: str) -> float:
        emphasis = text.count("!") + text.count("！")
        length_factor = min(len(text.strip()) / 200.0, 0.4)
        return max(0.1, min(1.0, 0.2 + emphasis * 0.15 + length_factor))