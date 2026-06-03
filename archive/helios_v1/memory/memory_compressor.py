"""Active-view autobiographical memory compression utilities."""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import List, Tuple


logger = logging.getLogger(__name__)


@dataclass
class CompressedSummary:
    """A summary narrative replacing multiple old moments in active memory."""

    date: str
    summary: str
    emotional_arc: str
    moment_count: int
    key_events: List[str]
    source_ids: List[str]


class MemoryCompressor:
    """Compresses old autobiographical moments into summary narratives."""

    AGE_THRESHOLD_DAYS = 7
    COUNT_THRESHOLD = 100

    def __init__(self, autobio_store, llm_bridge=None):
        self._store = autobio_store
        self._llm = llm_bridge

    def find_compressible_days(self) -> List[Tuple[str, int]]:
        counts: dict[str, int] = {}
        cutoff = time.time() - self.AGE_THRESHOLD_DAYS * 86400

        for moment in getattr(self._store, "moments", []):
            if moment.timestamp >= cutoff:
                continue
            date_string = self._store._date_string(moment.timestamp)
            counts[date_string] = counts.get(date_string, 0) + 1

        return sorted(
            [
                (date_string, count)
                for date_string, count in counts.items()
                if count > self.COUNT_THRESHOLD
            ],
            key=lambda item: item[0],
        )

    def compress_day(self, date: str, moments: List[object]) -> CompressedSummary:
        arc = self._build_emotional_arc(moments)
        key_events = self._extract_key_events(moments)
        if self._llm is not None:
            summary_text = self._summarize_with_llm(date, arc, key_events, len(moments))
        else:
            summary_text = self._summarize_with_template(date, arc, key_events, len(moments))

        return CompressedSummary(
            date=date,
            summary=summary_text,
            emotional_arc=arc,
            moment_count=len(moments),
            key_events=key_events,
            source_ids=[moment.moment_id for moment in moments],
        )

    def execute_compression(self) -> dict:
        compressible = self.find_compressible_days()
        stats = {
            "days_compressed": 0,
            "moments_compressed": 0,
            "summaries_produced": 0,
        }

        for date_string, count in compressible:
            moments = self._store.get_moments_for_date(date_string)
            if len(moments) <= self.COUNT_THRESHOLD:
                continue

            summary = self.compress_day(date_string, moments)
            replaced = self._store.replace_with_summary(date_string, summary)
            if replaced is None:
                continue

            stats["days_compressed"] += 1
            stats["moments_compressed"] += count
            stats["summaries_produced"] += 1

        if stats["days_compressed"] > 0:
            logger.info(
                "Memory compression: %d moments -> %d summaries across %d days",
                stats["moments_compressed"],
                stats["summaries_produced"],
                stats["days_compressed"],
            )

        return stats

    def _build_emotional_arc(self, moments: List[object]) -> str:
        phases: List[str] = []
        for moment in moments:
            dominant = getattr(moment, "dominant", "") or "neutral"
            if not phases or phases[-1] != dominant:
                phases.append(dominant)
        return " -> ".join(phases[:5]) if phases else "neutral"

    def _extract_key_events(self, moments: List[object]) -> List[str]:
        ranked = sorted(
            moments,
            key=lambda moment: (
                getattr(moment, "phi", 0.0),
                math.fabs(getattr(moment, "valence", 0.0)),
                getattr(moment, "significance", 0.0),
            ),
            reverse=True,
        )
        events: List[str] = []
        seen = set()
        for moment in ranked:
            label = (getattr(moment, "narrative", "") or getattr(moment, "dominant", "") or "moment").strip()
            if not label or label in seen:
                continue
            seen.add(label)
            events.append(label)
            if len(events) >= 3:
                break
        return events

    def _summarize_with_template(self, date: str, arc: str, key_events: List[str], moment_count: int) -> str:
        if key_events:
            event_text = "; ".join(key_events[:3])
        else:
            event_text = "no standout events"
        return (
            f"Compressed {moment_count} autobiographical moments from {date}. "
            f"Emotional arc: {arc}. Key events: {event_text}."
        )

    def _summarize_with_llm(self, date: str, arc: str, key_events: List[str], moment_count: int) -> str:
        prompt = (
            f"Summarize {moment_count} autobiographical moments from {date}. "
            f"Emotional arc: {arc}. Key events: {key_events}."
        )
        try:
            result = self._llm.generate(prompt)
            text = str(result).strip()
            if text:
                return text
        except Exception:
            logger.warning("LLM compression summary failed for %s; falling back to template", date)
        return self._summarize_with_template(date, arc, key_events, moment_count)