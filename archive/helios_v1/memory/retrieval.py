"""Structured retrieval contracts for cross-layer memory search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Protocol


MemoryScope = Literal["working", "episodic", "semantic", "autobiographical"]
MemoryStrategy = Literal["keyword", "affect", "related", "vector"]
PublicMemoryTierName = Literal["short-term", "mid-term", "long-term", "autobiographical"]


@dataclass(frozen=True)
class PublicMemoryTier:
    tier_name: PublicMemoryTierName
    implementation_scopes: tuple[MemoryScope, ...]
    capacity_limit: int | None
    decay_policy: str
    primary_use: str
    retrieval_role: str
    boundary_rule: str


@dataclass(frozen=True)
class PublicMemoryTierSnapshot:
    tier_name: PublicMemoryTierName
    item_count: int
    capacity_limit: int | None
    boundary_ok: bool
    implementation_scopes: tuple[MemoryScope, ...]


@dataclass(frozen=True)
class RetrievalQueryPlan:
    current_stimulus: tuple[dict[str, object], ...] = ()
    recall_intent: str = ""
    query_text: str = ""
    target_tiers: tuple[PublicMemoryTierName, ...] = ("mid-term", "long-term", "autobiographical")
    limit: int = 5
    retrieval_strategy: str = "directed_retrieval_v1"
    metadata: dict[str, object] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class RetrievalSelectionTrace:
    tier_name: PublicMemoryTierName
    candidate_count: int
    selected_count: int
    query_source: str

    def to_dict(self) -> dict[str, object]:
        return {
            "tier_name": self.tier_name,
            "candidate_count": int(self.candidate_count),
            "selected_count": int(self.selected_count),
            "query_source": self.query_source,
        }


@dataclass(frozen=True)
class RetrievalSECResult:
    candidate_id: str
    candidate_type: str
    score: float
    reason: str
    selected: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "score": round(float(self.score), 4),
            "reason": self.reason,
            "selected": bool(self.selected),
        }


@dataclass(frozen=True)
class DirectedMemoryBundle:
    short_term_context: tuple[MemorySearchHit, ...] = ()
    mid_term_hits: tuple[MemorySearchHit, ...] = ()
    long_term_hits: tuple[MemorySearchHit, ...] = ()
    autobiographical_hits: tuple[MemorySearchHit, ...] = ()
    selection_trace: tuple[RetrievalSelectionTrace, ...] = ()
    retrieval_sec_trace: tuple[RetrievalSECResult, ...] = ()

    def to_observability_payload(self) -> dict[str, object]:
        return {
            "short_term_count": len(self.short_term_context),
            "mid_term_count": len(self.mid_term_hits),
            "long_term_count": len(self.long_term_hits),
            "autobiographical_count": len(self.autobiographical_hits),
            "selection_trace": [trace.to_dict() for trace in self.selection_trace],
            "retrieval_sec_trace": [result.to_dict() for result in self.retrieval_sec_trace],
            "retrieval_sec_trace_count": len(self.retrieval_sec_trace),
        }


@dataclass(frozen=True)
class MemorySearchQuery:
    text: str = ""
    user_id: str = ""
    history_texts: tuple[str, ...] = ()
    valence: float = 0.0
    arousal: float = 0.0
    limit: int = 5
    scopes: tuple[MemoryScope, ...] = ("working", "episodic", "semantic", "autobiographical")
    strategies: tuple[MemoryStrategy, ...] = ("keyword", "affect", "related")
    metadata: dict[str, object] = field(default_factory=lambda: {})


@dataclass(frozen=True)
class MemorySearchHit:
    memory_id: str
    memory_type: str
    score: float
    summary: str
    content: dict[str, object] = field(default_factory=lambda: {})
    source: str = ""
    tags: tuple[str, ...] = ()
    timestamp: float = 0.0
    raw_payload: dict[str, object] = field(default_factory=lambda: {})


class VectorMemoryProvider(Protocol):
    def is_available(self) -> bool:
        ...

    def search(self, query: MemorySearchQuery, limit: int) -> list[MemorySearchHit]:
        ...


class NullVectorMemoryProvider:
    """Default vector provider that keeps vector strategy inert but valid."""

    def is_available(self) -> bool:
        return False

    def search(self, query: MemorySearchQuery, limit: int) -> list[MemorySearchHit]:
        return []


def normalize_history_texts(history_texts: Iterable[str] | None) -> tuple[str, ...]:
    if not history_texts:
        return ()
    return tuple(str(text) for text in history_texts if str(text).strip())


__all__ = [
    "MemoryScope",
    "MemorySearchHit",
    "MemorySearchQuery",
    "MemoryStrategy",
    "NullVectorMemoryProvider",
    "DirectedMemoryBundle",
    "PublicMemoryTier",
    "PublicMemoryTierName",
    "PublicMemoryTierSnapshot",
    "RetrievalQueryPlan",
    "RetrievalSECResult",
    "RetrievalSelectionTrace",
    "VectorMemoryProvider",
    "normalize_history_texts",
]