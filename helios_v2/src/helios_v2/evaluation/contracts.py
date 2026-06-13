"""Owner: evaluation fidelity and diagnostic provenance.

Owns:
- read-only evaluation request and evidence-bundle contracts
- diagnostic artifact assembly contracts and publication ops
- evaluation owner API

Does not own:
- runtime mutation
- planner authority
- channel execution
- governance decisions
- storage writes
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, runtime_checkable


class EvaluationError(RuntimeError):
    """Hard-stop error raised when evaluation owner invariants fail."""


EvaluationScenarioKind = Literal["runtime_tick", "session_window"]
EvaluationLearnedParameterCategory = Literal[
    "fidelity_scoring_policy",
    "gap_analysis_policy",
    "long_range_diagnostic_policy",
]

# The fixed consequence-path-outcome vocabulary an evaluation cycle may claim. This must
# stay aligned with the labels the evaluation engine derives. A `ConsequenceClaim` may only
# assert one of these outcomes; the corroboration step checks the claim against execution
# truth, but the vocabulary itself is owned here so the carried claim is self-validating.
CONSEQUENCE_PATH_OUTCOMES = frozenset(
    {
        "no_activation",
        "internally_activated_only",
        "internal_only_decision",
        "blocked",
        "rejected",
        "executed",
        "continuity_written",
    }
)

_SCENARIO_KINDS = {"runtime_tick", "session_window"}
_LEARNED_PARAMETER_CATEGORIES = {
    "fidelity_scoring_policy",
    "gap_analysis_policy",
    "long_range_diagnostic_policy",
}


def _freeze_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    frozen = MappingProxyType(dict(mapping))
    for key in frozen:
        if not key:
            raise EvaluationError("Evaluation mappings must not contain empty keys")
    return frozen


def _freeze_evidence_items(
    name: str,
    items: tuple[Mapping[str, object], ...],
) -> tuple[Mapping[str, object], ...]:
    frozen_items = tuple(_freeze_mapping(item) for item in items)
    for item in frozen_items:
        evidence_id = item.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id:
            raise EvaluationError(f"{name} items must declare non-empty evidence_id")
    return frozen_items


@dataclass(frozen=True)
class EvaluationConfig:
    """Expose the confirmed initialization and learned-policy surface for evaluation."""

    evaluation_bootstrap_id: str
    mandatory_learned_parameters: tuple[EvaluationLearnedParameterCategory, ...]

    def __post_init__(self) -> None:
        if set(self.mandatory_learned_parameters) != _LEARNED_PARAMETER_CATEGORIES:
            raise EvaluationError(
                "EvaluationConfig must declare the confirmed mandatory learned-parameter categories"
            )
        if not self.evaluation_bootstrap_id:
            raise EvaluationError("EvaluationConfig must declare a non-empty evaluation_bootstrap_id")


@dataclass(frozen=True)
class EvaluationRequest:
    """Immutable request contract for one read-only evaluation cycle."""

    request_id: str
    scenario_kind: EvaluationScenarioKind
    time_window_summary: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.request_id:
            raise EvaluationError("EvaluationRequest must declare a non-empty request_id")
        if self.scenario_kind not in _SCENARIO_KINDS:
            raise EvaluationError("EvaluationRequest scenario_kind must use the fixed taxonomy")
        time_window_summary = _freeze_mapping(self.time_window_summary)
        if not time_window_summary:
            raise EvaluationError("EvaluationRequest must declare non-empty time_window_summary")
        object.__setattr__(self, "time_window_summary", time_window_summary)


@dataclass(frozen=True)
class ConsequenceClaim:
    """Owner: evaluation fidelity and diagnostic provenance.

    Purpose:
        Capture the self-reported consequence outcome the evaluation owner derived for one
        evaluated tick, plus the owner-published statuses that outcome depended on. The
        composition owner carries the previous completed tick's claim forward, tick-aligned
        with that tick's execution timeline, so the next evaluation cycle can corroborate
        the self-report against kernel execution truth.

    Failure semantics:
        Construction raises `EvaluationError` on an empty `claim_id` or an unknown
        `consequence_path_outcome`.

    Notes:
        This is a model of the self-report, not an authority. It carries owner statuses that
        arrived through formal owner result contracts; it never carries a re-derived decision
        and never travels through the log channel.
    """

    claim_id: str
    tick_id: int | None
    consequence_path_outcome: str
    planner_status: str | None
    action_status: str | None
    continuity_written: bool
    decision_id: str | None = None
    selected_op: str | None = None
    op_effect_class: str | None = None
    op_user_visible: bool | None = None

    def __post_init__(self) -> None:
        if not self.claim_id:
            raise EvaluationError("ConsequenceClaim must declare a non-empty claim_id")
        if self.consequence_path_outcome not in CONSEQUENCE_PATH_OUTCOMES:
            raise EvaluationError(
                "ConsequenceClaim consequence_path_outcome must use the fixed outcome vocabulary"
            )

    def to_evidence(self, evidence_id: str) -> dict[str, object]:
        """Owner: evaluation fidelity and diagnostic provenance.

        Purpose:
            Return a compact, JSON-friendly projection of this claim for the owner-neutral
            carry and the prior-claim evidence category consumed next tick.

        Inputs:
            `evidence_id` - a non-empty stable id the carrier assigns to this evidence.

        Returns:
            A plain dict carrying `evidence_id`, `tick_id`, `consequence_path_outcome`,
            `planner_status`, `action_status`, `continuity_written`, and (R87) the
            delivery-relevant decision facts `decision_id`, `selected_op`, `op_effect_class`,
            `op_user_visible`.

        Raises:
            EvaluationError if `evidence_id` is empty.
        """

        if not evidence_id:
            raise EvaluationError("ConsequenceClaim.to_evidence requires a non-empty evidence_id")
        return {
            "evidence_id": evidence_id,
            "tick_id": self.tick_id,
            "consequence_path_outcome": self.consequence_path_outcome,
            "planner_status": self.planner_status,
            "action_status": self.action_status,
            "continuity_written": self.continuity_written,
            "decision_id": self.decision_id,
            "selected_op": self.selected_op,
            "op_effect_class": self.op_effect_class,
            "op_user_visible": self.op_user_visible,
        }


@dataclass(frozen=True)
class EvaluationEvidenceBundle:
    """Immutable read-only evidence bundle assembled from explicit runtime owner outputs."""

    bundle_id: str
    source_request_id: str
    thought_evidence: tuple[Mapping[str, object], ...]
    action_evidence: tuple[Mapping[str, object], ...]
    planner_evidence: tuple[Mapping[str, object], ...]
    governance_evidence: tuple[Mapping[str, object], ...]
    writeback_evidence: tuple[Mapping[str, object], ...]
    autonomy_evidence: tuple[Mapping[str, object], ...]
    prompt_evidence: tuple[Mapping[str, object], ...]
    outward_expression_evidence: tuple[Mapping[str, object], ...]
    outward_expression_externalization_evidence: tuple[Mapping[str, object], ...]
    execution_timeline_evidence: tuple[Mapping[str, object], ...] = ()
    prior_consequence_claim_evidence: tuple[Mapping[str, object], ...] = ()
    delivered_tool_result_evidence: tuple[Mapping[str, object], ...] = ()

    def __post_init__(self) -> None:
        if not self.bundle_id:
            raise EvaluationError("EvaluationEvidenceBundle must declare a non-empty bundle_id")
        if not self.source_request_id:
            raise EvaluationError(
                "EvaluationEvidenceBundle must declare a non-empty source_request_id"
            )
        for attr_name in (
            "thought_evidence",
            "action_evidence",
            "planner_evidence",
            "governance_evidence",
            "writeback_evidence",
            "autonomy_evidence",
            "prompt_evidence",
            "outward_expression_evidence",
            "outward_expression_externalization_evidence",
            "execution_timeline_evidence",
            "prior_consequence_claim_evidence",
            "delivered_tool_result_evidence",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_evidence_items(attr_name, getattr(self, attr_name)),
            )


@dataclass(frozen=True)
class FidelityWarning:
    """Immutable provenance-rich warning emitted by the evaluation owner."""

    warning_id: str
    warning_kind: str
    summary: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.warning_id:
            raise EvaluationError("FidelityWarning must declare a non-empty warning_id")
        if not self.warning_kind:
            raise EvaluationError("FidelityWarning must declare a non-empty warning_kind")
        if not self.summary:
            raise EvaluationError("FidelityWarning must declare a non-empty summary")
        if not self.evidence_refs or any(not item for item in self.evidence_refs):
            raise EvaluationError("FidelityWarning must declare non-empty evidence_refs")


@dataclass(frozen=True)
class EvaluationArtifact:
    """Immutable evaluation artifact published from one evidence bundle."""

    artifact_id: str
    source_bundle_id: str
    dimension_scores: Mapping[str, float]
    gap_summary: Mapping[str, object]
    fidelity_warnings: tuple[FidelityWarning, ...]
    long_range_diagnostics: Mapping[str, object]

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise EvaluationError("EvaluationArtifact must declare a non-empty artifact_id")
        if not self.source_bundle_id:
            raise EvaluationError("EvaluationArtifact must declare a non-empty source_bundle_id")
        dimension_scores = _freeze_mapping(self.dimension_scores)
        if not dimension_scores:
            raise EvaluationError("EvaluationArtifact must declare non-empty dimension_scores")
        for key, value in dimension_scores.items():
            if not isinstance(value, float) and not isinstance(value, int):
                raise EvaluationError(
                    f"EvaluationArtifact dimension_scores[{key}] must be numeric"
                )
        gap_summary = _freeze_mapping(self.gap_summary)
        if not gap_summary:
            raise EvaluationError("EvaluationArtifact must declare non-empty gap_summary")
        long_range_diagnostics = _freeze_mapping(self.long_range_diagnostics)
        if not long_range_diagnostics:
            raise EvaluationError(
                "EvaluationArtifact must declare non-empty long_range_diagnostics"
            )
        object.__setattr__(self, "dimension_scores", dimension_scores)
        object.__setattr__(self, "gap_summary", gap_summary)
        object.__setattr__(self, "long_range_diagnostics", long_range_diagnostics)


@dataclass(frozen=True)
class EvaluateEvidenceBundleOp:
    """Runtime-visible request op for one evidence-driven evaluation cycle."""

    op_name: str
    owner: str
    request_id: str
    bundle_id: str
    scenario_kind: EvaluationScenarioKind


@dataclass(frozen=True)
class PublishEvaluationArtifactOp:
    """Runtime-visible publication op for one evaluation artifact."""

    op_name: str
    owner: str
    artifact_id: str
    source_bundle_id: str
    warning_count: int


@runtime_checkable
class EvaluationAPI(Protocol):
    """Public API for read-only evaluation artifact assembly."""

    def build_evaluate_op(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
    ) -> EvaluateEvidenceBundleOp:
        """Return one request op describing evidence-driven evaluation."""

        ...

    def evaluate(
        self,
        request: EvaluationRequest,
        bundle: EvaluationEvidenceBundle,
    ) -> EvaluationArtifact:
        """Return one read-only diagnostic artifact from explicit runtime evidence."""

        ...

    def build_publish_artifact_op(
        self,
        artifact: EvaluationArtifact,
    ) -> PublishEvaluationArtifactOp:
        """Return one publication op describing evaluation-artifact publication."""

        ...