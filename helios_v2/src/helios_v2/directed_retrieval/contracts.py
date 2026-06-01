"""Owner: directed retrieval into thought window.

Owns:
- retrieval request and query-plan contracts
- tiered selection trace and bounded thought-window bundle contracts
- directed-retrieval API and publication ops

Does not own:
- memory persistence
- thought generation
- planner or executor routing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from helios_v2.thought_gating import ContinuationPressureState, SelectedStimulusSummary, ThoughtGateResult


class DirectedRetrievalError(RuntimeError):
    """Hard-stop error raised when directed-retrieval owner invariants fail."""


def _validate_unit_interval(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise DirectedRetrievalError(f"{name} must be within [0.0, 1.0]")


ThoughtWindowTier = Literal["short_term", "mid_term", "long_term", "autobiographical"]
RetrievalQuerySource = Literal["compact_stimuli", "recall_intent", "selected_memory_refs", "mixed"]
RetrievalStrategy = Literal["deterministic_first_version"]
DirectedRetrievalLearnedParameterCategory = Literal[
    "retrieval_planning_policy",
    "tier_selection_policy",
    "thought_window_shaping_policy",
]

_THOUGHT_WINDOW_TIERS = {"short_term", "mid_term", "long_term", "autobiographical"}
_RETRIEVAL_QUERY_SOURCES = {"compact_stimuli", "recall_intent", "selected_memory_refs", "mixed"}


@dataclass(frozen=True)
class DirectedRetrievalConfig:
    """Expose the confirmed initialization and learned-policy surface for directed retrieval."""

    max_hits_per_tier: int
    max_short_term_context: int
    retrieval_bootstrap_id: str
    mandatory_learned_parameters: tuple[DirectedRetrievalLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        expected = {
            "retrieval_planning_policy",
            "tier_selection_policy",
            "thought_window_shaping_policy",
        }
        if set(self.mandatory_learned_parameters) != expected:
            raise DirectedRetrievalError(
                "Directed-retrieval config must declare the confirmed mandatory learned-parameter categories"
            )
        if self.max_hits_per_tier <= 0:
            raise DirectedRetrievalError("DirectedRetrievalConfig.max_hits_per_tier must be > 0")
        if self.max_short_term_context <= 0:
            raise DirectedRetrievalError("DirectedRetrievalConfig.max_short_term_context must be > 0")
        if self.max_short_term_context > self.max_hits_per_tier:
            raise DirectedRetrievalError(
                "DirectedRetrievalConfig.max_short_term_context must not exceed max_hits_per_tier"
            )
        if not self.retrieval_bootstrap_id:
            raise DirectedRetrievalError("DirectedRetrievalConfig must declare a non-empty retrieval_bootstrap_id")


@dataclass(frozen=True)
class RetrievalRequest:
    """Explicit normalized retrieval-demand contract for one fired gate cycle."""

    request_id: str
    source_gate_result_id: str
    source_continuation_active: bool
    compact_stimuli: tuple[SelectedStimulusSummary, ...]
    recall_intent: str | None
    selected_memory_refs: tuple[str, ...]
    target_tiers: tuple[ThoughtWindowTier, ...]
    limit: int
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise DirectedRetrievalError("RetrievalRequest must declare a non-empty request_id")
        if not self.source_gate_result_id:
            raise DirectedRetrievalError("RetrievalRequest must declare a non-empty source_gate_result_id")
        if any(not ref for ref in self.selected_memory_refs):
            raise DirectedRetrievalError("RetrievalRequest selected_memory_refs must not contain empty values")
        if not self.target_tiers:
            raise DirectedRetrievalError("RetrievalRequest must declare at least one target tier")
        if any(tier not in _THOUGHT_WINDOW_TIERS for tier in self.target_tiers):
            raise DirectedRetrievalError("RetrievalRequest target_tiers must use the fixed thought-window tier taxonomy")
        if len(set(self.target_tiers)) != len(self.target_tiers):
            raise DirectedRetrievalError("RetrievalRequest target_tiers must not contain duplicates")
        if self.limit <= 0:
            raise DirectedRetrievalError("RetrievalRequest.limit must be > 0")
        if not self.compact_stimuli and not self.recall_intent and not self.selected_memory_refs:
            raise DirectedRetrievalError(
                "RetrievalRequest must include compact stimuli, recall_intent, or selected_memory_refs"
            )


@dataclass(frozen=True)
class RetrievalQueryPlan:
    """Owner-built query plan for one directed retrieval cycle."""

    plan_id: str
    source_request_id: str
    query_text: str
    query_source: RetrievalQuerySource
    target_tiers: tuple[ThoughtWindowTier, ...]
    limit: int
    retrieval_strategy: RetrievalStrategy
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.plan_id:
            raise DirectedRetrievalError("RetrievalQueryPlan must declare a non-empty plan_id")
        if not self.source_request_id:
            raise DirectedRetrievalError("RetrievalQueryPlan must declare a non-empty source_request_id")
        if not self.query_text:
            raise DirectedRetrievalError("RetrievalQueryPlan must declare non-empty query_text")
        if self.query_source not in _RETRIEVAL_QUERY_SOURCES:
            raise DirectedRetrievalError("RetrievalQueryPlan query_source must use the fixed taxonomy")
        if not self.target_tiers:
            raise DirectedRetrievalError("RetrievalQueryPlan must declare at least one target tier")
        if any(tier not in _THOUGHT_WINDOW_TIERS for tier in self.target_tiers):
            raise DirectedRetrievalError("RetrievalQueryPlan target_tiers must use the fixed taxonomy")
        if self.limit <= 0:
            raise DirectedRetrievalError("RetrievalQueryPlan.limit must be > 0")


@dataclass(frozen=True)
class MemoryRetrievalCandidate:
    """Bounded public memory-candidate projection supplied to the retrieval owner."""

    candidate_id: str
    tier: ThoughtWindowTier
    memory_id: str
    memory_type: str
    summary: str
    score: float
    source: str
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise DirectedRetrievalError("MemoryRetrievalCandidate must declare a non-empty candidate_id")
        if self.tier not in _THOUGHT_WINDOW_TIERS:
            raise DirectedRetrievalError("MemoryRetrievalCandidate tier must use the fixed taxonomy")
        if not self.memory_id:
            raise DirectedRetrievalError("MemoryRetrievalCandidate must declare a non-empty memory_id")
        if not self.memory_type:
            raise DirectedRetrievalError("MemoryRetrievalCandidate must declare a non-empty memory_type")
        if not self.summary:
            raise DirectedRetrievalError("MemoryRetrievalCandidate must declare a non-empty summary")
        _validate_unit_interval("MemoryRetrievalCandidate.score", self.score)
        if not self.source:
            raise DirectedRetrievalError("MemoryRetrievalCandidate must declare a non-empty source")
        if any(not tag for tag in self.tags):
            raise DirectedRetrievalError("MemoryRetrievalCandidate tags must not contain empty values")


@dataclass(frozen=True)
class ThoughtWindowHit:
    """Bounded selected memory projection for the thought window."""

    memory_id: str
    memory_type: str
    summary: str
    score: float
    source: str
    tags: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.memory_id:
            raise DirectedRetrievalError("ThoughtWindowHit must declare a non-empty memory_id")
        if not self.memory_type:
            raise DirectedRetrievalError("ThoughtWindowHit must declare a non-empty memory_type")
        if not self.summary:
            raise DirectedRetrievalError("ThoughtWindowHit must declare a non-empty summary")
        _validate_unit_interval("ThoughtWindowHit.score", self.score)
        if not self.source:
            raise DirectedRetrievalError("ThoughtWindowHit must declare a non-empty source")
        if any(not tag for tag in self.tags):
            raise DirectedRetrievalError("ThoughtWindowHit tags must not contain empty values")


@dataclass(frozen=True)
class RetrievalSelectionTrace:
    """Tier-level selection summary for one retrieval plan."""

    tier_name: ThoughtWindowTier
    candidate_count: int
    selected_count: int
    query_source: RetrievalQuerySource

    def __post_init__(self) -> None:
        if self.tier_name not in _THOUGHT_WINDOW_TIERS:
            raise DirectedRetrievalError("RetrievalSelectionTrace tier_name must use the fixed taxonomy")
        if self.candidate_count < 0:
            raise DirectedRetrievalError("RetrievalSelectionTrace.candidate_count must be >= 0")
        if self.selected_count < 0:
            raise DirectedRetrievalError("RetrievalSelectionTrace.selected_count must be >= 0")
        if self.selected_count > self.candidate_count:
            raise DirectedRetrievalError("RetrievalSelectionTrace.selected_count must not exceed candidate_count")
        if self.query_source not in _RETRIEVAL_QUERY_SOURCES:
            raise DirectedRetrievalError("RetrievalSelectionTrace query_source must use the fixed taxonomy")


@dataclass(frozen=True)
class RetrievalSECTraceItem:
    """Candidate-level first-version selection evidence for diagnostics."""

    candidate_id: str
    candidate_type: str
    score: float
    reason: str
    selected: bool

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise DirectedRetrievalError("RetrievalSECTraceItem must declare a non-empty candidate_id")
        if not self.candidate_type:
            raise DirectedRetrievalError("RetrievalSECTraceItem must declare a non-empty candidate_type")
        _validate_unit_interval("RetrievalSECTraceItem.score", self.score)
        if not self.reason:
            raise DirectedRetrievalError("RetrievalSECTraceItem must declare a non-empty reason")


@dataclass(frozen=True)
class ThoughtWindowBundle:
    """Immutable bounded memory bundle for a later internal thought window."""

    bundle_id: str
    source_plan_id: str
    short_term_context: tuple[ThoughtWindowHit, ...]
    mid_term_hits: tuple[ThoughtWindowHit, ...]
    long_term_hits: tuple[ThoughtWindowHit, ...]
    autobiographical_hits: tuple[ThoughtWindowHit, ...]
    selection_trace: tuple[RetrievalSelectionTrace, ...]
    retrieval_sec_trace: tuple[RetrievalSECTraceItem, ...]
    tick_id: int | None

    def __post_init__(self) -> None:
        if not self.bundle_id:
            raise DirectedRetrievalError("ThoughtWindowBundle must declare a non-empty bundle_id")
        if not self.source_plan_id:
            raise DirectedRetrievalError("ThoughtWindowBundle must declare a non-empty source_plan_id")
        trace_tiers = {trace.tier_name for trace in self.selection_trace}
        expected_tiers = {"short_term", "mid_term", "long_term", "autobiographical"}
        if trace_tiers != expected_tiers:
            raise DirectedRetrievalError("ThoughtWindowBundle selection_trace must cover every thought-window tier")
        if len(self.short_term_context) > 2:
            raise DirectedRetrievalError("ThoughtWindowBundle short_term_context must remain tiny and bounded")


@dataclass(frozen=True)
class PlanDirectedRetrievalOp:
    """Runtime-visible request op for one directed-retrieval planning cycle."""

    op_name: str
    owner: str
    request_id: str
    gate_result_id: str
    target_tier_count: int


@dataclass(frozen=True)
class PublishThoughtWindowBundleOp:
    """Runtime-visible publication op for one bounded thought-window bundle."""

    op_name: str
    owner: str
    bundle_id: str
    short_term_count: int
    mid_term_count: int
    long_term_count: int
    autobiographical_count: int


@runtime_checkable
class DirectedMemoryCandidateProvider(Protocol):
    """Public candidate source consumed by the directed-retrieval owner."""

    def collect_candidates(
        self,
        plan: RetrievalQueryPlan,
    ) -> tuple[MemoryRetrievalCandidate, ...]:
        """Return bounded public memory-candidate projections for one query plan."""


@runtime_checkable
class DirectedRetrievalAPI(Protocol):
    """Owner: directed retrieval into thought window API."""

    def retrieve_for_thought_window(
        self,
        gate_result: ThoughtGateResult,
        continuation_state: ContinuationPressureState,
        request: RetrievalRequest,
    ) -> tuple[RetrievalQueryPlan, ThoughtWindowBundle]:
        """Return one explicit retrieval query plan and one bounded thought-window bundle."""

    def build_plan_op(
        self,
        gate_result: ThoughtGateResult,
        request: RetrievalRequest,
    ) -> PlanDirectedRetrievalOp:
        """Return one request op describing directed-retrieval planning."""

    def build_publish_bundle_op(
        self,
        bundle: ThoughtWindowBundle,
    ) -> PublishThoughtWindowBundleOp:
        """Return one publication op describing thought-window bundle publication."""
