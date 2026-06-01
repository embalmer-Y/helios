"""Owner: directed retrieval into thought window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from helios_v2.thought_gating import ContinuationPressureState, ThoughtGateResult

from .contracts import (
    DirectedMemoryCandidateProvider,
    DirectedRetrievalAPI,
    DirectedRetrievalConfig,
    DirectedRetrievalError,
    MemoryRetrievalCandidate,
    PlanDirectedRetrievalOp,
    PublishThoughtWindowBundleOp,
    RetrievalQueryPlan,
    RetrievalRequest,
    RetrievalSECTraceItem,
    RetrievalSelectionTrace,
    ThoughtWindowBundle,
    ThoughtWindowHit,
    ThoughtWindowTier,
)


def _validate_gate_result(gate_result: ThoughtGateResult) -> None:
    if not gate_result.result_id:
        raise DirectedRetrievalError("ThoughtGateResult must declare a non-empty result_id")
    if gate_result.decision != "fire":
        raise DirectedRetrievalError("Directed retrieval requires a fired ThoughtGateResult")


def _validate_continuation_alignment(
    continuation_state: ContinuationPressureState,
    request: RetrievalRequest,
) -> None:
    if continuation_state.active != request.source_continuation_active:
        raise DirectedRetrievalError("RetrievalRequest must preserve the current continuation active flag")


def _validate_request(gate_result: ThoughtGateResult, request: RetrievalRequest) -> None:
    if request.source_gate_result_id != gate_result.result_id:
        raise DirectedRetrievalError("RetrievalRequest must preserve the source gate-result id")


def _validate_bundle(plan: RetrievalQueryPlan, bundle: ThoughtWindowBundle, config: DirectedRetrievalConfig) -> None:
    if bundle.source_plan_id != plan.plan_id:
        raise DirectedRetrievalError("ThoughtWindowBundle must preserve the source query-plan id")
    if len(bundle.short_term_context) > config.max_short_term_context:
        raise DirectedRetrievalError("ThoughtWindowBundle short-term context exceeds configured bound")
    for tier_hits in (
        bundle.short_term_context,
        bundle.mid_term_hits,
        bundle.long_term_hits,
        bundle.autobiographical_hits,
    ):
        if len(tier_hits) > config.max_hits_per_tier:
            raise DirectedRetrievalError("ThoughtWindowBundle tier output exceeds configured bound")


@runtime_checkable
class DirectedRetrievalPath(Protocol):
    def plan_and_select(
        self,
        request: RetrievalRequest,
        candidate_provider: DirectedMemoryCandidateProvider,
        config: DirectedRetrievalConfig,
    ) -> tuple[RetrievalQueryPlan, ThoughtWindowBundle]:
        """Return one query plan and one bounded bundle from validated retrieval demand."""


@dataclass
class FirstVersionDirectedRetrievalPath(DirectedRetrievalPath):
    """Owner-private deterministic first-version directed-retrieval path."""

    strategy_name: str = "deterministic_first_version"

    def plan_and_select(
        self,
        request: RetrievalRequest,
        candidate_provider: DirectedMemoryCandidateProvider,
        config: DirectedRetrievalConfig,
    ) -> tuple[RetrievalQueryPlan, ThoughtWindowBundle]:
        query_text, query_source = self._build_query_text(request)
        plan = RetrievalQueryPlan(
            plan_id=f"retrieval-plan:{request.request_id}",
            source_request_id=request.request_id,
            query_text=query_text,
            query_source=query_source,
            target_tiers=request.target_tiers,
            limit=min(request.limit, config.max_hits_per_tier),
            retrieval_strategy="deterministic_first_version",
            tick_id=request.tick_id,
        )
        candidates = candidate_provider.collect_candidates(plan)
        return plan, self._build_bundle(plan, candidates, config)

    def _build_query_text(self, request: RetrievalRequest) -> tuple[str, str]:
        fragments: list[str] = []
        query_source = "compact_stimuli"
        if request.recall_intent:
            fragments.append(request.recall_intent.strip())
            query_source = "recall_intent"
        for summary in request.compact_stimuli:
            fragments.append(f"{summary.source_kind}:{summary.stimulus_id}")
        if request.selected_memory_refs:
            fragments.extend(request.selected_memory_refs)
            query_source = "selected_memory_refs" if not request.recall_intent and not request.compact_stimuli else "mixed"
        elif request.recall_intent and request.compact_stimuli:
            query_source = "mixed"
        return " | ".join(fragments), query_source

    def _build_bundle(
        self,
        plan: RetrievalQueryPlan,
        candidates: tuple[MemoryRetrievalCandidate, ...],
        config: DirectedRetrievalConfig,
    ) -> ThoughtWindowBundle:
        selected_by_tier: dict[str, tuple[ThoughtWindowHit, ...]] = {}
        traces: list[RetrievalSelectionTrace] = []
        sec_trace: list[RetrievalSECTraceItem] = []
        for tier in ("short_term", "mid_term", "long_term", "autobiographical"):
            tier_candidates = tuple(candidate for candidate in candidates if candidate.tier == tier)
            limit = config.max_short_term_context if tier == "short_term" else config.max_hits_per_tier
            selected_candidates = tuple(
                sorted(tier_candidates, key=lambda candidate: (-candidate.score, candidate.candidate_id))[:limit]
            )
            selected_ids = {candidate.candidate_id for candidate in selected_candidates}
            selected_by_tier[tier] = tuple(
                ThoughtWindowHit(
                    memory_id=candidate.memory_id,
                    memory_type=candidate.memory_type,
                    summary=candidate.summary,
                    score=candidate.score,
                    source=candidate.source,
                    tags=candidate.tags,
                )
                for candidate in selected_candidates
            )
            traces.append(
                RetrievalSelectionTrace(
                    tier_name=tier,  # type: ignore[arg-type]
                    candidate_count=len(tier_candidates),
                    selected_count=len(selected_candidates),
                    query_source=plan.query_source,
                )
            )
            for candidate in tier_candidates:
                sec_trace.append(
                    RetrievalSECTraceItem(
                        candidate_id=candidate.candidate_id,
                        candidate_type=candidate.memory_type,
                        score=candidate.score,
                        reason="selected_by_first_version_score_order"
                        if candidate.candidate_id in selected_ids
                        else "not_selected_by_first_version_score_order",
                        selected=candidate.candidate_id in selected_ids,
                    )
                )
        return ThoughtWindowBundle(
            bundle_id=f"thought-window-bundle:{plan.plan_id}",
            source_plan_id=plan.plan_id,
            short_term_context=selected_by_tier["short_term"],
            mid_term_hits=selected_by_tier["mid_term"],
            long_term_hits=selected_by_tier["long_term"],
            autobiographical_hits=selected_by_tier["autobiographical"],
            selection_trace=tuple(traces),
            retrieval_sec_trace=tuple(sec_trace),
            tick_id=plan.tick_id,
        )


@dataclass
class DirectedRetrievalEngine(DirectedRetrievalAPI):
    """Execute one directed-retrieval cycle using an injected private retrieval path."""

    config: DirectedRetrievalConfig
    retrieval_path: DirectedRetrievalPath
    candidate_provider: DirectedMemoryCandidateProvider | None

    def retrieve_for_thought_window(
        self,
        gate_result: ThoughtGateResult,
        continuation_state: ContinuationPressureState,
        request: RetrievalRequest,
    ) -> tuple[RetrievalQueryPlan, ThoughtWindowBundle]:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        _validate_continuation_alignment(continuation_state, request)
        if self.candidate_provider is None:
            raise DirectedRetrievalError("Directed retrieval requires an explicit public memory candidate provider")
        plan, bundle = self.retrieval_path.plan_and_select(request, self.candidate_provider, self.config)
        if plan.source_request_id != request.request_id:
            raise DirectedRetrievalError("RetrievalQueryPlan must preserve the source request id")
        _validate_bundle(plan, bundle, self.config)
        return plan, bundle

    def build_plan_op(
        self,
        gate_result: ThoughtGateResult,
        request: RetrievalRequest,
    ) -> PlanDirectedRetrievalOp:
        _validate_gate_result(gate_result)
        _validate_request(gate_result, request)
        return PlanDirectedRetrievalOp(
            op_name="plan_directed_retrieval",
            owner="directed_retrieval_into_thought_window",
            request_id=request.request_id,
            gate_result_id=gate_result.result_id,
            target_tier_count=len(request.target_tiers),
        )

    def build_publish_bundle_op(
        self,
        bundle: ThoughtWindowBundle,
    ) -> PublishThoughtWindowBundleOp:
        if not bundle.bundle_id:
            raise DirectedRetrievalError("ThoughtWindowBundle contains incomplete publication identity")
        return PublishThoughtWindowBundleOp(
            op_name="publish_thought_window_bundle",
            owner="directed_retrieval_into_thought_window",
            bundle_id=bundle.bundle_id,
            short_term_count=len(bundle.short_term_context),
            mid_term_count=len(bundle.mid_term_hits),
            long_term_count=len(bundle.long_term_hits),
            autobiographical_count=len(bundle.autobiographical_hits),
        )
