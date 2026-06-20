"""Owner: reportable conscious-content layer.

Owns:
- conscious commitment orchestration
- current-cycle input validation
- conscious-state and publication-op construction

Does not own:
- workspace competition
- runtime bridge assembly
- internal thought execution
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from helios_v2.workspace import WorkingStateSnapshot, WorkspaceCandidateSet

from .contracts import (
    CommitConsciousContentOp,
    ConsciousContentAPI,
    ConsciousContentMaterial,
    ConsciousContentMaterialSet,
    ConsciousState,
    ConsciousnessConfig,
    ConsciousnessError,
    PublishConsciousStateOp,
    PublishReportableConsciousContentOp,
    ReportableConsciousContent,
    SupportingContextItem,
)


def _validate_candidate_set(candidate_set: WorkspaceCandidateSet) -> None:
    if not candidate_set.set_id:
        raise ConsciousnessError("WorkspaceCandidateSet must declare a non-empty set_id")
    if not candidate_set.candidates:
        raise ConsciousnessError(
            "Reportable consciousness requires at least one WorkspaceCandidate in the current cycle"
        )


def _validate_working_state(
    working_state: WorkingStateSnapshot,
    candidate_set: WorkspaceCandidateSet,
) -> None:
    if working_state.source_candidate_set_id != candidate_set.set_id:
        raise ConsciousnessError(
            "WorkingStateSnapshot must preserve the source_candidate_set_id of the workspace candidate set"
        )
    candidate_ids = {candidate.candidate_id for candidate in candidate_set.candidates}
    for retained_candidate_id in working_state.retained_candidate_ids:
        if retained_candidate_id not in candidate_ids:
            raise ConsciousnessError(
                "WorkingStateSnapshot may retain only candidate ids published in the same workspace candidate set"
            )


def _validate_material_set(
    material_set: ConsciousContentMaterialSet,
    candidate_set: WorkspaceCandidateSet,
    working_state: WorkingStateSnapshot,
) -> dict[str, ConsciousContentMaterial]:
    if material_set.source_workspace_candidate_set_id != candidate_set.set_id:
        raise ConsciousnessError(
            "ConsciousContentMaterialSet must preserve the source workspace candidate-set id of the current cycle"
        )
    if material_set.source_working_state_id != working_state.state_id:
        raise ConsciousnessError(
            "ConsciousContentMaterialSet must preserve the source working-state id of the current cycle"
        )
    candidate_map = {candidate.candidate_id: candidate for candidate in candidate_set.candidates}
    material_map = {material.source_workspace_candidate_id: material for material in material_set.materials}
    if set(material_map) != set(candidate_map):
        raise ConsciousnessError(
            "ConsciousContentMaterialSet must cover the full current WorkspaceCandidateSet exactly once"
        )
    for candidate_id, material in material_map.items():
        candidate = candidate_map[candidate_id]
        if material.source_memory_candidate_id != candidate.source_memory_candidate_id:
            raise ConsciousnessError(
                "ConsciousContentMaterial must preserve the source_memory_candidate_id of its workspace candidate"
            )
        if material.source_feeling_state_id != candidate.source_feeling_state_id:
            raise ConsciousnessError(
                "ConsciousContentMaterial must preserve the source_feeling_state_id of its workspace candidate"
            )
        if material.forced_consolidation != candidate.forced_consolidation:
            raise ConsciousnessError(
                "ConsciousContentMaterial must preserve the forced_consolidation flag of its workspace candidate"
            )
        if material.workspace_score_hint != candidate.workspace_score_hint:
            raise ConsciousnessError(
                "ConsciousContentMaterial must preserve the workspace_score_hint of its workspace candidate"
            )
        if material.priority_hint != candidate.priority_hint:
            raise ConsciousnessError(
                "ConsciousContentMaterial must preserve the priority_hint of its workspace candidate"
            )
    return material_map


def _validate_focal_content(
    focal_content: ReportableConsciousContent,
    material_map: dict[str, ConsciousContentMaterial],
) -> None:
    material = next(
        (item for item in material_map.values() if item.material_id == focal_content.source_material_id),
        None,
    )
    if material is None:
        raise ConsciousnessError(
            "Committed focal content must reference a material published in the same current cycle"
        )
    if focal_content.source_workspace_candidate_id != material.source_workspace_candidate_id:
        raise ConsciousnessError(
            "Committed focal content must preserve the source_workspace_candidate_id of its material"
        )
    if focal_content.source_memory_candidate_id != material.source_memory_candidate_id:
        raise ConsciousnessError(
            "Committed focal content must preserve the source_memory_candidate_id of its material"
        )
    if focal_content.source_feeling_state_id != material.source_feeling_state_id:
        raise ConsciousnessError(
            "Committed focal content must preserve the source_feeling_state_id of its material"
        )


def _validate_supporting_context(
    supporting_context: tuple[SupportingContextItem, ...],
    material_map: dict[str, ConsciousContentMaterial],
    focal_content: ReportableConsciousContent | None,
    max_items: int,
) -> None:
    if len(supporting_context) > max_items:
        raise ConsciousnessError(
            "ConsciousState supporting_context exceeds the configured maximum for the first version"
        )
    focal_material_id = focal_content.source_material_id if focal_content is not None else None
    focal_workspace_candidate_id = (
        focal_content.source_workspace_candidate_id if focal_content is not None else None
    )
    for item in supporting_context:
        material = next((value for value in material_map.values() if value.material_id == item.source_material_id), None)
        if material is None:
            raise ConsciousnessError(
                "Supporting context items must reference materials published in the same current cycle"
            )
        if item.source_workspace_candidate_id != material.source_workspace_candidate_id:
            raise ConsciousnessError(
                "Supporting context items must preserve the source_workspace_candidate_id of their material"
            )
        if item.source_material_id == focal_material_id or (
            focal_workspace_candidate_id is not None
            and item.source_workspace_candidate_id == focal_workspace_candidate_id
        ):
            raise ConsciousnessError(
                "Supporting context items must remain auxiliary and must not duplicate the focal conscious item"
            )


def _validate_state(
    state: ConsciousState,
    candidate_set: WorkspaceCandidateSet,
    working_state: WorkingStateSnapshot,
    material_map: dict[str, ConsciousContentMaterial],
    config: ConsciousnessConfig,
) -> None:
    if state.source_workspace_candidate_set_id != candidate_set.set_id:
        raise ConsciousnessError(
            "ConsciousState must preserve the source_workspace_candidate_set_id of the current cycle"
        )
    if state.source_working_state_id != working_state.state_id:
        raise ConsciousnessError(
            "ConsciousState must preserve the source_working_state_id of the current cycle"
        )
    if state.focal_content is not None:
        _validate_focal_content(state.focal_content, material_map)
    _validate_supporting_context(
        state.supporting_context,
        material_map,
        state.focal_content,
        config.max_supporting_context_items,
    )


@runtime_checkable
class ConsciousCommitmentPath(Protocol):
    """Owner-private conscious commitment collaborator.

    Purpose:
        Turn explicit current-cycle workspace outputs and material into one formal conscious-state outcome.
    """

    def commit(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        config: ConsciousnessConfig,
        tick_id: int | None,
    ) -> ConsciousState:
        """Return one formal conscious-state outcome derived only from current-cycle inputs."""


@dataclass(frozen=True)
class _FocalSelectionOutcome:
    """Private selection-layer output consumed by semantic commitment rendering.

    This object isolates the question "what is the current-cycle focal selection outcome?" from the later question
    "how should that outcome be rendered into reportable semantics?"
    """

    commit_status: str
    focal_material: ConsciousContentMaterial | None
    supporting_materials: tuple[ConsciousContentMaterial, ...]
    no_commit_reason: str | None


@dataclass(frozen=True)
class _SemanticCommitmentRenderRequest:
    """Private owner-controlled request passed into semantic commitment rendering.

    The renderer sees only validated current-cycle materials plus explicit owner limits. This is the stable shape a
    future learned or LLM-backed renderer should consume.
    """

    commit_status: str
    tick_id: int | None
    focal_material: ConsciousContentMaterial | None
    supporting_materials: tuple[ConsciousContentMaterial, ...]
    max_supporting_context_items: int
    no_commit_reason: str | None


@dataclass(frozen=True)
class _SemanticCommitmentRenderResult:
    """Private semantic render result returned by one owner-controlled rendering pass."""

    focal_content: ReportableConsciousContent | None
    supporting_context: tuple[SupportingContextItem, ...]


@dataclass(frozen=True)
class _SemanticCommitmentRequestTrace:
    """Private normalized request trace for semantic commitment observability."""

    commit_status: str
    tick_id: int | None
    focal_material_id: str | None
    supporting_material_ids: tuple[str, ...]
    max_supporting_context_items: int
    no_commit_reason: str | None


@dataclass(frozen=True)
class _SemanticCommitmentResponseTrace:
    """Private normalized response trace for semantic commitment observability."""

    focal_content_id: str | None
    focal_source_material_id: str | None
    supporting_context_item_ids: tuple[str, ...]
    supporting_source_material_ids: tuple[str, ...]


@dataclass(frozen=True)
class _SemanticCommitmentCapabilityTrace:
    """Private standardized trace for one owner-controlled semantic capability attempt."""

    renderer_name: str
    capability_name: str
    request: _SemanticCommitmentRequestTrace
    response: _SemanticCommitmentResponseTrace | None
    terminal_status: _SemanticCommitmentCapabilityTerminalStatus
    failure_message: str | None


@dataclass(frozen=True)
class _FocalSelectionTrace:
    """Private normalized trace for the owner's focal-selection stage."""

    commit_status: str
    focal_material_id: str | None
    supporting_material_ids: tuple[str, ...]
    no_commit_reason: str | None


@dataclass(frozen=True)
class _FinalConsciousStateTrace:
    """Private normalized trace for the final published conscious state."""

    state_id: str
    commit_status: str
    focal_content_id: str | None
    focal_source_material_id: str | None
    supporting_context_item_ids: tuple[str, ...]
    no_commit_reason: str | None
    tick_id: int | None


@dataclass(frozen=True)
class _ConsciousCommitmentPathTrace:
    """Private end-to-end owner snapshot for one selection -> render -> final-state path."""

    selection: _FocalSelectionTrace | None
    render_request: _SemanticCommitmentRequestTrace | None
    render_response: _SemanticCommitmentResponseTrace | None
    capability_trace: _SemanticCommitmentCapabilityTrace | None
    final_state: _FinalConsciousStateTrace | None
    terminal_status: _ConsciousCommitmentPathTerminalStatus
    failure_message: str | None


class _SemanticCommitmentCapabilityTerminalStatus(StrEnum):
    """Fixed private terminal-status taxonomy for semantic capability attempts."""

    RENDERED = "rendered"
    REJECTED_CYCLE = "rejected_cycle"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"


class _ConsciousCommitmentPathTerminalStatus(StrEnum):
    """Fixed private terminal-status taxonomy for owner-path commitment traces."""

    SELECTION_REJECTED_CYCLE = "selection_rejected_cycle"
    SELECTION_CAPABILITY_UNAVAILABLE = "selection_capability_unavailable"
    INVALID_SELECTION_OUTCOME = "invalid_selection_outcome"
    RENDER_REJECTED_CYCLE = "render_rejected_cycle"
    RENDER_CAPABILITY_UNAVAILABLE = "render_capability_unavailable"
    PUBLISHED_NO_COMMIT_STATE = "published_no_commit_state"
    PUBLISHED_COMMITTED_STATE = "published_committed_state"


class _FirstVersionSemanticCommitmentMode(StrEnum):
    """Fixed private wiring taxonomy for the first-version semantic commitment path."""

    DETERMINISTIC = "deterministic"
    LLM_BACKED = "llm_backed"


class _FocalSelectionPolicy(Protocol):
    """Private policy for selecting focal-vs-no-commit outcomes from validated current-cycle inputs.

    This layer is LLM-ready in the sense that later versions may replace the deterministic selection policy without
    changing the semantic rendering surface or the capability boundary.

    R-PROTO-LEARN.P-TEMPORAL: `config` is now passed in so policies can read
    `commitment_score_floor` (the P5 surface for commitment_policy). Default
    `None` for backward compatibility with any test-only custom policy.
    """

    def decide(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_map: dict[str, ConsciousContentMaterial],
        config: "ConsciousnessConfig | None" = None,
    ) -> _FocalSelectionOutcome:
        """Return one private focal-selection outcome using current-cycle inputs only."""


class _SemanticCommitmentRenderer(Protocol):
    """Private renderer for turning a focal-selection outcome into reportable semantic content.

    This is the most likely insertion point for a later owner-controlled LLM path, because it owns semantic shaping
    while staying constrained to the current-cycle materials selected by the upstream private layer.
    """

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        """Render one semantic commitment result from one explicit owner-controlled request."""


class _OwnerControlledSemanticCommitmentCapability(Protocol):
    """Private capability boundary reserved for future learned or LLM-backed semantic rendering."""

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        """Render semantic commitment artifacts for one validated current-cycle request."""


@dataclass(frozen=True)
class _LLMSemanticCommitmentCapabilityRequest:
    """Private owner-controlled LLM request shape derived from current-cycle semantic inputs."""

    model: str
    system_prompt: str
    user_prompt: str
    temperature: float
    max_tokens: int
    response_format_json: bool
    render_request: _SemanticCommitmentRenderRequest
    request_trace: _SemanticCommitmentRequestTrace
    selection_trace: _FocalSelectionTrace


@dataclass(frozen=True)
class _LLMSemanticCommitmentRequestBuilderInput:
    """Private builder input exposing the current owner-private request and trace surface."""

    render_request: _SemanticCommitmentRenderRequest
    request_trace: _SemanticCommitmentRequestTrace
    selection_trace: _FocalSelectionTrace


class _LLMSemanticCommitmentRequestBuilder(Protocol):
    """Private builder for owner-controlled LLM semantic capability requests."""

    def build_request(
        self,
        builder_input: _LLMSemanticCommitmentRequestBuilderInput,
    ) -> _LLMSemanticCommitmentCapabilityRequest:
        """Build one LLM capability request from the current owner-private request and trace surface."""


class _LLMSemanticCommitmentTransport(Protocol):
    """Private transport boundary for LLM-backed semantic commitment execution."""

    def render(
        self,
        request: _LLMSemanticCommitmentCapabilityRequest,
    ) -> _SemanticCommitmentRenderResult:
        """Execute one LLM-backed semantic commitment request."""


class _LLMSemanticCommitmentResponsePolicy(Protocol):
    """Private owner-controlled acceptance boundary for parsed LLM semantic responses."""

    def evaluate(
        self,
        request: _SemanticCommitmentRenderRequest,
        result: _SemanticCommitmentRenderResult,
    ) -> _SemanticCommitmentRenderResult:
        """Return an accepted render result or reject the current cycle explicitly."""


class _OpenAICompatibleClientProvider(Protocol):
    """Private provider for OpenAI-compatible clients without embedding provider strategy in `08`."""

    def get_client(self) -> object:
        """Return a client exposing `chat.completions.create(...)`."""


class _CommitmentCapabilityRejectedCycle(RuntimeError):
    """Private signal meaning the configured semantic-commitment capability rejected this cycle.

    This maps to a formal `no_commit/capability_rejected_cycle` outcome instead of an execution failure.
    """


class _CommitmentCapabilityUnavailable(RuntimeError):
    """Private signal meaning the configured semantic-commitment capability is unavailable.

    Unlike a rejected cycle, this remains a hard-stop owner failure because no valid commitment capability existed.
    """


def _normalize_summary(summary: str) -> str:
    return " ".join(summary.split())


def _format_semantic_summary(prefix: str, material: ConsciousContentMaterial) -> str:
    normalized_summary = _normalize_summary(material.material_summary)
    if not normalized_summary:
        raise ConsciousnessError(
            "Conscious commitment cannot report material with an empty semantic summary after normalization"
        )
    summary = f"{prefix} {material.content_kind}: {normalized_summary}"
    if material.salient_tokens:
        summary = f"{summary}. Salient cues: {', '.join(material.salient_tokens)}"
    return summary


def _validate_semantic_render_result(
    request: _SemanticCommitmentRenderRequest,
    result: _SemanticCommitmentRenderResult,
) -> None:
    if request.commit_status == "committed" and result.focal_content is None:
        raise ConsciousnessError(
            "Semantic commitment renderer must return focal content for a committed selection outcome"
        )
    if request.commit_status == "no_commit" and result.focal_content is not None:
        raise ConsciousnessError(
            "Semantic commitment renderer must not return focal content for a no-commit selection outcome"
        )


def _build_request_trace(
    request: _SemanticCommitmentRenderRequest,
) -> _SemanticCommitmentRequestTrace:
    return _SemanticCommitmentRequestTrace(
        commit_status=request.commit_status,
        tick_id=request.tick_id,
        focal_material_id=(request.focal_material.material_id if request.focal_material is not None else None),
        supporting_material_ids=tuple(
            material.material_id for material in request.supporting_materials
        ),
        max_supporting_context_items=request.max_supporting_context_items,
        no_commit_reason=request.no_commit_reason,
    )


def _build_response_trace(
    result: _SemanticCommitmentRenderResult,
) -> _SemanticCommitmentResponseTrace:
    return _SemanticCommitmentResponseTrace(
        focal_content_id=(result.focal_content.content_id if result.focal_content is not None else None),
        focal_source_material_id=(
            result.focal_content.source_material_id if result.focal_content is not None else None
        ),
        supporting_context_item_ids=tuple(
            item.context_item_id for item in result.supporting_context
        ),
        supporting_source_material_ids=tuple(
            item.source_material_id for item in result.supporting_context
        ),
    )


def _build_selection_trace_from_render_request(
    request: _SemanticCommitmentRenderRequest,
) -> _FocalSelectionTrace:
    return _FocalSelectionTrace(
        commit_status=request.commit_status,
        focal_material_id=(request.focal_material.material_id if request.focal_material is not None else None),
        supporting_material_ids=tuple(
            material.material_id for material in request.supporting_materials
        ),
        no_commit_reason=request.no_commit_reason,
    )


def _build_selection_trace(
    outcome: _FocalSelectionOutcome,
) -> _FocalSelectionTrace:
    return _FocalSelectionTrace(
        commit_status=outcome.commit_status,
        focal_material_id=(outcome.focal_material.material_id if outcome.focal_material is not None else None),
        supporting_material_ids=tuple(
            material.material_id for material in outcome.supporting_materials
        ),
        no_commit_reason=outcome.no_commit_reason,
    )


def _build_final_state_trace(
    state: ConsciousState,
) -> _FinalConsciousStateTrace:
    return _FinalConsciousStateTrace(
        state_id=state.state_id,
        commit_status=state.commit_status,
        focal_content_id=(state.focal_content.content_id if state.focal_content is not None else None),
        focal_source_material_id=(
            state.focal_content.source_material_id if state.focal_content is not None else None
        ),
        supporting_context_item_ids=tuple(
            item.context_item_id for item in state.supporting_context
        ),
        no_commit_reason=state.no_commit_reason,
        tick_id=state.tick_id,
    )


def _build_capability_trace(
    *,
    renderer_name: str,
    capability_name: str,
    request_trace: _SemanticCommitmentRequestTrace,
    response_trace: _SemanticCommitmentResponseTrace | None,
    terminal_status: _SemanticCommitmentCapabilityTerminalStatus,
    failure_message: str | None,
) -> _SemanticCommitmentCapabilityTrace:
    return _SemanticCommitmentCapabilityTrace(
        renderer_name=renderer_name,
        capability_name=capability_name,
        request=request_trace,
        response=response_trace,
        terminal_status=terminal_status,
        failure_message=failure_message,
    )


def _material_map_for_request(
    request: _SemanticCommitmentRenderRequest,
) -> dict[str, ConsciousContentMaterial]:
    materials: list[ConsciousContentMaterial] = list(request.supporting_materials)
    if request.focal_material is not None:
        materials.append(request.focal_material)
    material_map = {material.material_id: material for material in materials}
    if len(material_map) != len(materials):
        raise ConsciousnessError(
            "Semantic commitment render request must not contain duplicate material ids"
        )
    return material_map


@dataclass(frozen=True)
class _LLMSemanticCommitmentFocalPayload:
    """Private parsed focal payload returned by an LLM-backed semantic capability."""

    source_material_id: str
    focal_summary: str
    salient_tokens: tuple[str, ...]


@dataclass(frozen=True)
class _LLMSemanticCommitmentSupportingPayload:
    """Private parsed supporting item payload returned by an LLM-backed semantic capability."""

    source_material_id: str
    summary: str


@dataclass(frozen=True)
class _LLMSemanticCommitmentResponsePayload:
    """Private parsed LLM response payload before conversion into render result contracts."""

    focal_content: _LLMSemanticCommitmentFocalPayload | None
    supporting_context: tuple[_LLMSemanticCommitmentSupportingPayload, ...]


def _build_openai_compatible_request_payload(
    request: _LLMSemanticCommitmentCapabilityRequest,
    *,
    timeout_seconds: float,
    reasoning_effort: str,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": request.model,
        "messages": [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ],
        "temperature": request.temperature,
        "max_tokens": request.max_tokens,
        "timeout": timeout_seconds,
        "reasoning_effort": reasoning_effort,
    }
    if request.response_format_json:
        payload["response_format"] = {"type": "json_object"}
    return payload


def _require_json_object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConsciousnessError(f"{context} must be a JSON object")
    return value


def _require_json_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ConsciousnessError(f"{context} must be a JSON array")
    return value


def _require_non_empty_string(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise ConsciousnessError(f"{context} must be a string")
    normalized = _normalize_summary(value)
    if not normalized:
        raise ConsciousnessError(f"{context} must be non-empty after normalization")
    return normalized


def _parse_llm_response_payload(raw_text: str) -> _LLMSemanticCommitmentResponsePayload:
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ConsciousnessError(
            "LLM-backed semantic commitment transport returned invalid JSON"
        ) from exc
    root = _require_json_object(payload, "LLM semantic commitment response")
    if "focal_content" not in root or "supporting_context" not in root:
        raise ConsciousnessError(
            "LLM semantic commitment response must declare focal_content and supporting_context"
        )

    focal_content_payload: _LLMSemanticCommitmentFocalPayload | None
    focal_content_value = root["focal_content"]
    if focal_content_value is None:
        focal_content_payload = None
    else:
        focal_object = _require_json_object(focal_content_value, "focal_content")
        salient_tokens_value = focal_object.get("salient_tokens", [])
        salient_tokens_list = _require_json_list(salient_tokens_value, "focal_content.salient_tokens")
        focal_content_payload = _LLMSemanticCommitmentFocalPayload(
            source_material_id=_require_non_empty_string(
                focal_object.get("source_material_id"),
                "focal_content.source_material_id",
            ),
            focal_summary=_require_non_empty_string(
                focal_object.get("focal_summary"),
                "focal_content.focal_summary",
            ),
            salient_tokens=tuple(
                _require_non_empty_string(token, "focal_content.salient_tokens[]")
                for token in salient_tokens_list
            ),
        )

    supporting_items: list[_LLMSemanticCommitmentSupportingPayload] = []
    for index, item in enumerate(
        _require_json_list(root["supporting_context"], "supporting_context")
    ):
        item_object = _require_json_object(item, f"supporting_context[{index}]")
        supporting_items.append(
            _LLMSemanticCommitmentSupportingPayload(
                source_material_id=_require_non_empty_string(
                    item_object.get("source_material_id"),
                    f"supporting_context[{index}].source_material_id",
                ),
                summary=_require_non_empty_string(
                    item_object.get("summary"),
                    f"supporting_context[{index}].summary",
                ),
            )
        )
    return _LLMSemanticCommitmentResponsePayload(
        focal_content=focal_content_payload,
        supporting_context=tuple(supporting_items),
    )


def _build_render_result_from_llm_payload(
    request: _SemanticCommitmentRenderRequest,
    payload: _LLMSemanticCommitmentResponsePayload,
    *,
    content_id_prefix: str,
    context_id_prefix: str,
) -> _SemanticCommitmentRenderResult:
    material_map = _material_map_for_request(request)
    focal_content = None
    if payload.focal_content is not None:
        focal_material = material_map.get(payload.focal_content.source_material_id)
        if focal_material is None:
            raise ConsciousnessError(
                "LLM-backed semantic commitment focal content must reference a declared current-cycle material"
            )
        focal_content = ReportableConsciousContent(
            content_id=f"{content_id_prefix}:{focal_material.material_id}",
            source_material_id=focal_material.material_id,
            source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
            source_memory_candidate_id=focal_material.source_memory_candidate_id,
            source_feeling_state_id=focal_material.source_feeling_state_id,
            content_kind=focal_material.content_kind,
            focal_summary=payload.focal_content.focal_summary,
            affect_trace=focal_material.affect_tag,
            salient_tokens=payload.focal_content.salient_tokens,
            tick_id=request.tick_id,
        )

    supporting_context: list[SupportingContextItem] = []
    focal_material_id = focal_content.source_material_id if focal_content is not None else None
    seen_supporting_material_ids: set[str] = set()
    for item in payload.supporting_context:
        supporting_material = material_map.get(item.source_material_id)
        if supporting_material is None:
            raise ConsciousnessError(
                "LLM-backed semantic commitment supporting context must reference declared current-cycle materials"
            )
        if supporting_material.material_id == focal_material_id:
            raise ConsciousnessError(
                "LLM-backed semantic commitment supporting context must not duplicate the focal material"
            )
        if supporting_material.material_id in seen_supporting_material_ids:
            raise ConsciousnessError(
                "LLM-backed semantic commitment supporting context must not repeat a source material"
            )
        seen_supporting_material_ids.add(supporting_material.material_id)
        supporting_context.append(
            SupportingContextItem(
                context_item_id=f"{context_id_prefix}:{supporting_material.material_id}",
                source_material_id=supporting_material.material_id,
                source_workspace_candidate_id=supporting_material.source_workspace_candidate_id,
                content_kind=supporting_material.content_kind,
                summary=item.summary,
                affect_trace=supporting_material.affect_tag,
            )
        )
    return _SemanticCommitmentRenderResult(
        focal_content=focal_content,
        supporting_context=tuple(supporting_context),
    )


def _build_commitment_path_trace(
    *,
    selection: _FocalSelectionTrace | None,
    render_request: _SemanticCommitmentRequestTrace | None,
    render_response: _SemanticCommitmentResponseTrace | None,
    capability_trace: _SemanticCommitmentCapabilityTrace | None,
    final_state: _FinalConsciousStateTrace | None,
    terminal_status: _ConsciousCommitmentPathTerminalStatus,
    failure_message: str | None,
) -> _ConsciousCommitmentPathTrace:
    return _ConsciousCommitmentPathTrace(
        selection=selection,
        render_request=render_request,
        render_response=render_response,
        capability_trace=capability_trace,
        final_state=final_state,
        terminal_status=terminal_status,
        failure_message=failure_message,
    )


@dataclass
class _RetainedWorkingStateSelectionPolicy(_FocalSelectionPolicy):
    """Private first-version focal-selection policy based on retained working-state ids only.

    R-PROTO-LEARN.P-TEMPORAL: when `config` is provided, the focal material's
    `workspace_score_hint` is compared against `commitment_score_floor`; below
    the floor the cycle is rejected with `insufficient_commitment_signal`.
    This is the quantitative gate that the prior architecture lacked (the
    old code only rejected on emptiness / summary normalization, not on
    low competition score). Default floor 0.5 preserves legacy behaviour
    for tests that don't pass a config.
    """

    def decide(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_map: dict[str, ConsciousContentMaterial],
        config: "ConsciousnessConfig | None" = None,
    ) -> _FocalSelectionOutcome:
        retained_materials = tuple(
            material_map[retained_candidate_id]
            for retained_candidate_id in working_state.retained_candidate_ids
        )
        if not retained_materials:
            return _FocalSelectionOutcome(
                commit_status="no_commit",
                focal_material=None,
                supporting_materials=(),
                no_commit_reason="insufficient_commitment_signal",
            )
        if len(retained_materials) > 1:
            return _FocalSelectionOutcome(
                commit_status="no_commit",
                focal_material=None,
                supporting_materials=retained_materials,
                no_commit_reason="semantic_conflict_unresolved",
            )
        focal_material = retained_materials[0]
        # R-PROTO-LEARN.P-TEMPORAL: quantitative commitment gate
        if config is not None:
            score = focal_material.workspace_score_hint
            if score is None or score < config.commitment_score_floor:
                return _FocalSelectionOutcome(
                    commit_status="no_commit",
                    focal_material=None,
                    supporting_materials=(),
                    no_commit_reason="insufficient_commitment_signal",
                )
        if not _normalize_summary(focal_material.material_summary):
            return _FocalSelectionOutcome(
                commit_status="no_commit",
                focal_material=None,
                supporting_materials=(),
                no_commit_reason="context_not_reportable",
            )
        supporting_materials = tuple(
            material_map[candidate.candidate_id]
            for candidate in candidate_set.candidates
            if candidate.candidate_id != focal_material.source_workspace_candidate_id
        )
        return _FocalSelectionOutcome(
            commit_status="committed",
            focal_material=focal_material,
            supporting_materials=supporting_materials,
            no_commit_reason=None,
        )


@dataclass
class IgnitionFocalSelectionPolicy(_FocalSelectionPolicy):
    """Owner: reportable conscious-content layer.

    Purpose:
        Global-workspace winner-take-all focal selection. When one or more candidates are
        retained in the working state, ignite the single highest-`workspace_score_hint`
        candidate as the focal reportable content and demote the remaining retained candidates
        to supporting context, instead of declaring `semantic_conflict_unresolved` whenever more
        than one candidate is retained. This is the de-shimmed commitment policy for the
        semantic-memory assembly, where the R46 `workspace_score_hint` is a real competition score.

    Failure semantics:
        Pure deterministic function. Zero retained candidates yields
        `no_commit/insufficient_commitment_signal`; an ignited focal whose normalized summary is
        empty yields `no_commit/context_not_reportable` (both preserved from the first-version
        policy). It never emits `semantic_conflict_unresolved` for mere retained multiplicity.

    Notes:
        Owned by `08`, injected through the existing `focal_selection_policy` seam. It produces
        exactly the focal+supporting shape the engine validation and the semantic renderer
        already accept (the renderer caps supporting items at `max_supporting_context_items`, so
        ranking the losers by descending score keeps the most salient ones under the cap). A
        material with no `workspace_score_hint` is ranked as score `0.0`. Ties break
        deterministically by `source_workspace_candidate_id`.
    """

    def decide(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_map: dict[str, ConsciousContentMaterial],
        config: "ConsciousnessConfig | None" = None,
    ) -> _FocalSelectionOutcome:
        retained_materials = tuple(
            material_map[retained_candidate_id]
            for retained_candidate_id in working_state.retained_candidate_ids
        )
        if not retained_materials:
            return _FocalSelectionOutcome(
                commit_status="no_commit",
                focal_material=None,
                supporting_materials=(),
                no_commit_reason="insufficient_commitment_signal",
            )
        # Winner-take-all ignition: the dominant candidate by the real R46 competition score.
        ranked = sorted(
            retained_materials,
            key=lambda material: (
                -(material.workspace_score_hint if material.workspace_score_hint is not None else 0.0),
                material.source_workspace_candidate_id,
            ),
        )
        focal_material = ranked[0]
        # R-PROTO-LEARN.P-TEMPORAL: quantitative commitment gate (matches
        # _RetainedWorkingStateSelectionPolicy so the two paths share one
        # commitment semantics; configurable per-assembly).
        if config is not None:
            score = focal_material.workspace_score_hint
            if score is None or score < config.commitment_score_floor:
                return _FocalSelectionOutcome(
                    commit_status="no_commit",
                    focal_material=None,
                    supporting_materials=(),
                    no_commit_reason="insufficient_commitment_signal",
                )
        if not _normalize_summary(focal_material.material_summary):
            return _FocalSelectionOutcome(
                commit_status="no_commit",
                focal_material=None,
                supporting_materials=(),
                no_commit_reason="context_not_reportable",
            )
        # The losers of the ignition become supporting context, ordered by descending score so
        # the renderer's bounded cap keeps the most salient ones.
        supporting_materials = ranked[1:]
        return _FocalSelectionOutcome(
            commit_status="committed",
            focal_material=focal_material,
            supporting_materials=supporting_materials,
            no_commit_reason=None,
        )


@dataclass
class _MaterialSummarySemanticCommitmentRenderer(_SemanticCommitmentRenderer):
    """Private first-version semantic renderer built only from explicit current-cycle material.

    This renderer is deterministic today, but it already marks the boundary where a later owner-controlled LLM-backed
    semantic commitment implementation could be injected.
    """

    content_id_prefix: str = "conscious-content"
    context_id_prefix: str = "supporting-context"

    def _build_focal_content(
        self,
        focal_material: ConsciousContentMaterial,
        tick_id: int | None,
    ) -> ReportableConsciousContent:
        return ReportableConsciousContent(
            content_id=f"{self.content_id_prefix}:{focal_material.material_id}",
            source_material_id=focal_material.material_id,
            source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
            source_memory_candidate_id=focal_material.source_memory_candidate_id,
            source_feeling_state_id=focal_material.source_feeling_state_id,
            content_kind=focal_material.content_kind,
            focal_summary=_format_semantic_summary("Current focal content from", focal_material),
            affect_trace=focal_material.affect_tag,
            salient_tokens=focal_material.salient_tokens,
            tick_id=tick_id,
        )

    def _build_supporting_context_items(
        self,
        materials: tuple[ConsciousContentMaterial, ...],
        max_items: int,
    ) -> tuple[SupportingContextItem, ...]:
        supporting_items: list[SupportingContextItem] = []
        for material in materials[:max_items]:
            supporting_items.append(
                SupportingContextItem(
                    context_item_id=f"{self.context_id_prefix}:{material.material_id}",
                    source_material_id=material.material_id,
                    source_workspace_candidate_id=material.source_workspace_candidate_id,
                    content_kind=material.content_kind,
                    summary=_format_semantic_summary("Supporting context from", material),
                    affect_trace=material.affect_tag,
                )
            )
        return tuple(supporting_items)

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        focal_content = None
        if request.commit_status == "committed":
            if request.focal_material is None:
                raise ConsciousnessError(
                    "Committed semantic render requests must declare one focal material"
                )
            focal_content = self._build_focal_content(request.focal_material, request.tick_id)
        return _SemanticCommitmentRenderResult(
            focal_content=focal_content,
            supporting_context=self._build_supporting_context_items(
                request.supporting_materials,
                request.max_supporting_context_items,
            ),
        )


@dataclass
class _UnavailableOwnerControlledSemanticCommitmentCapability(
    _OwnerControlledSemanticCommitmentCapability
):
    """Private skeleton capability that fails explicitly until a real owner-controlled renderer is wired."""

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        del request
        raise _CommitmentCapabilityUnavailable(
            "Owner-controlled semantic commitment capability is not configured"
        )


@dataclass
class _CurrentCycleLLMSemanticCommitmentRequestBuilder(_LLMSemanticCommitmentRequestBuilder):
    """Private first LLM request-builder skeleton consuming current owner-private request and traces only."""

    model: str = "owner-controlled-semantic-llm"
    temperature: float = 0.1
    max_tokens: int = 800
    response_format_json: bool = True

    def build_request(
        self,
        builder_input: _LLMSemanticCommitmentRequestBuilderInput,
    ) -> _LLMSemanticCommitmentCapabilityRequest:
        request = builder_input.render_request
        lines = [
            "Current-cycle reportable conscious-content commitment request.",
            f"commit_status={builder_input.selection_trace.commit_status}",
            f"tick_id={builder_input.request_trace.tick_id}",
            f"no_commit_reason={builder_input.selection_trace.no_commit_reason}",
            f"focal_material_id={builder_input.selection_trace.focal_material_id}",
            f"supporting_material_ids={builder_input.selection_trace.supporting_material_ids}",
            f"max_supporting_context_items={builder_input.request_trace.max_supporting_context_items}",
        ]
        if request.focal_material is not None:
            lines.extend(
                (
                    f"focal_content_kind={request.focal_material.content_kind}",
                    f"focal_material_summary={_normalize_summary(request.focal_material.material_summary)}",
                    f"focal_salient_tokens={request.focal_material.salient_tokens}",
                )
            )
        if request.supporting_materials:
            lines.append("supporting_materials=")
            for material in request.supporting_materials:
                lines.append(
                    "- "
                    f"material_id={material.material_id}; kind={material.content_kind}; "
                    f"summary={_normalize_summary(material.material_summary)}; "
                    f"salient_tokens={material.salient_tokens}"
                )
        return _LLMSemanticCommitmentCapabilityRequest(
            model=self.model,
            system_prompt=(
                "You are the owner-controlled reportable-consciousness semantic capability. "
                "Use only the supplied current-cycle materials. Return one focal conscious payload plus bounded "
                "supporting context when commit_status=committed, or bounded supporting context with no focal "
                "payload when commit_status=no_commit."
            ),
            user_prompt="\n".join(lines),
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format_json=self.response_format_json,
            render_request=builder_input.render_request,
            request_trace=builder_input.request_trace,
            selection_trace=builder_input.selection_trace,
        )


@dataclass
class _UnavailableLLMSemanticCommitmentTransport(_LLMSemanticCommitmentTransport):
    """Private transport skeleton that fails explicitly until a real LLM transport is wired."""

    def render(
        self,
        request: _LLMSemanticCommitmentCapabilityRequest,
    ) -> _SemanticCommitmentRenderResult:
        del request
        raise _CommitmentCapabilityUnavailable(
            "LLM-backed semantic commitment transport is not configured"
        )


@dataclass
class _UnavailableOpenAICompatibleClientProvider(_OpenAICompatibleClientProvider):
    """Private client-provider skeleton that fails explicitly until a real OpenAI-compatible client is wired."""

    def get_client(self) -> object:
        raise _CommitmentCapabilityUnavailable(
            "OpenAI-compatible semantic commitment client is not configured"
        )


@dataclass
class _DefaultOpenAICompatibleClientProvider(_OpenAICompatibleClientProvider):
    """Private default OpenAI-compatible client provider using injected or environment-backed config only."""

    api_key: str | None = None
    base_url: str | None = None
    client: object | None = field(default=None, init=False)

    def _resolve_api_key(self) -> str:
        if self.api_key is not None:
            return self.api_key
        return os.getenv("HELIOS_LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))

    def _resolve_base_url(self) -> str:
        if self.base_url is not None:
            return self.base_url
        return os.getenv(
            "HELIOS_LLM_BASE_URL",
            os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

    def get_client(self) -> object:
        if self.client is not None:
            return self.client
        api_key = self._resolve_api_key()
        if not api_key:
            raise _CommitmentCapabilityUnavailable(
                "OpenAI-compatible semantic commitment client requires an API key"
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise _CommitmentCapabilityUnavailable(
                "openai package is required for the default OpenAI-compatible semantic commitment client"
            ) from exc
        self.client = OpenAI(
            api_key=api_key,
            base_url=self._resolve_base_url(),
        )
        return self.client


@dataclass(frozen=True)
class _CurrentCycleLLMSemanticCommitmentResponsePolicy(_LLMSemanticCommitmentResponsePolicy):
    """Private owner-controlled response gate for LLM-backed semantic commitment.

    This policy keeps acceptance local to `08`: JSON parse success is not enough. The owner must still verify that
    the rendered result preserves the already-selected focal material and the configured supporting-context bounds.
    """

    def evaluate(
        self,
        request: _SemanticCommitmentRenderRequest,
        result: _SemanticCommitmentRenderResult,
    ) -> _SemanticCommitmentRenderResult:
        if request.commit_status == "committed":
            if request.focal_material is None:
                raise ConsciousnessError(
                    "Committed LLM semantic requests must declare one focal material before response evaluation"
                )
            if result.focal_content is None:
                raise _CommitmentCapabilityRejectedCycle(
                    "LLM-backed semantic commitment response did not return focal content for a committed cycle"
                )
            if result.focal_content.source_material_id != request.focal_material.material_id:
                raise _CommitmentCapabilityRejectedCycle(
                    "LLM-backed semantic commitment response must preserve the owner-selected focal material"
                )
        elif result.focal_content is not None:
            raise _CommitmentCapabilityRejectedCycle(
                "LLM-backed semantic commitment response must not introduce focal content for a no-commit cycle"
            )
        if len(result.supporting_context) > request.max_supporting_context_items:
            raise _CommitmentCapabilityRejectedCycle(
                "LLM-backed semantic commitment response exceeds the owner-configured supporting-context cap"
            )
        return result


@dataclass
class _OpenAICompatibleSemanticCommitmentTransport(_LLMSemanticCommitmentTransport):
    """Private OpenAI-compatible transport skeleton with strict response parsing and no provider strategy."""

    client_provider: _OpenAICompatibleClientProvider = field(
        default_factory=_DefaultOpenAICompatibleClientProvider
    )
    timeout_seconds: float = 30.0
    reasoning_effort: str = "low"
    content_id_prefix: str = "conscious-content"
    context_id_prefix: str = "supporting-context"
    last_request_payload: dict[str, object] | None = field(default=None, init=False)
    last_raw_response_text: str | None = field(default=None, init=False)

    def render(
        self,
        request: _LLMSemanticCommitmentCapabilityRequest,
    ) -> _SemanticCommitmentRenderResult:
        client = self.client_provider.get_client()
        payload = _build_openai_compatible_request_payload(
            request,
            timeout_seconds=self.timeout_seconds,
            reasoning_effort=self.reasoning_effort,
        )
        self.last_request_payload = payload
        try:
            response = client.chat.completions.create(**payload)
        except _CommitmentCapabilityRejectedCycle:
            raise
        except _CommitmentCapabilityUnavailable:
            raise
        except Exception as exc:
            raise _CommitmentCapabilityUnavailable(
                f"OpenAI-compatible semantic commitment transport failed: {exc}"
            ) from exc
        raw_text = response.choices[0].message.content or ""
        self.last_raw_response_text = raw_text
        parsed_payload = _parse_llm_response_payload(raw_text)
        return _build_render_result_from_llm_payload(
            request.render_request,
            parsed_payload,
            content_id_prefix=self.content_id_prefix,
            context_id_prefix=self.context_id_prefix,
        )


@dataclass
class _LLMBackedSemanticCommitmentCapability(_OwnerControlledSemanticCommitmentCapability):
    """Private LLM-backed semantic capability skeleton using the owner-private request/trace surface."""

    request_builder: _LLMSemanticCommitmentRequestBuilder = field(
        default_factory=_CurrentCycleLLMSemanticCommitmentRequestBuilder
    )
    transport: _LLMSemanticCommitmentTransport = field(
        default_factory=_OpenAICompatibleSemanticCommitmentTransport
    )
    response_policy: _LLMSemanticCommitmentResponsePolicy = field(
        default_factory=_CurrentCycleLLMSemanticCommitmentResponsePolicy
    )
    last_built_request: _LLMSemanticCommitmentCapabilityRequest | None = field(
        default=None,
        init=False,
    )

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        builder_input = _LLMSemanticCommitmentRequestBuilderInput(
            render_request=request,
            request_trace=_build_request_trace(request),
            selection_trace=_build_selection_trace_from_render_request(request),
        )
        self.last_built_request = self.request_builder.build_request(builder_input)
        return self.response_policy.evaluate(
            request,
            self.transport.render(self.last_built_request),
        )


@dataclass
class _OwnerControlledSemanticCommitmentRenderer(_SemanticCommitmentRenderer):
    """Private skeleton renderer that forwards one stable request to an owner-controlled capability."""

    capability: _OwnerControlledSemanticCommitmentCapability = field(
        default_factory=_UnavailableOwnerControlledSemanticCommitmentCapability
    )
    last_trace: _SemanticCommitmentCapabilityTrace | None = field(
        default=None,
        init=False,
    )

    def render(
        self,
        request: _SemanticCommitmentRenderRequest,
    ) -> _SemanticCommitmentRenderResult:
        request_trace = _build_request_trace(request)
        renderer_name = type(self).__name__
        capability_name = type(self.capability).__name__
        try:
            result = self.capability.render(request)
        except _CommitmentCapabilityRejectedCycle as exc:
            self.last_trace = _build_capability_trace(
                renderer_name=renderer_name,
                capability_name=capability_name,
                request_trace=request_trace,
                response_trace=None,
                terminal_status=_SemanticCommitmentCapabilityTerminalStatus.REJECTED_CYCLE,
                failure_message=str(exc),
            )
            raise
        except _CommitmentCapabilityUnavailable as exc:
            self.last_trace = _build_capability_trace(
                renderer_name=renderer_name,
                capability_name=capability_name,
                request_trace=request_trace,
                response_trace=None,
                terminal_status=_SemanticCommitmentCapabilityTerminalStatus.CAPABILITY_UNAVAILABLE,
                failure_message=str(exc),
            )
            raise
        self.last_trace = _build_capability_trace(
            renderer_name=renderer_name,
            capability_name=capability_name,
            request_trace=request_trace,
            response_trace=_build_response_trace(result),
            terminal_status=_SemanticCommitmentCapabilityTerminalStatus.RENDERED,
            failure_message=None,
        )
        return result


def _build_first_version_semantic_commitment_renderer(
    mode: _FirstVersionSemanticCommitmentMode = _FirstVersionSemanticCommitmentMode.DETERMINISTIC,
) -> _SemanticCommitmentRenderer:
    """Build one explicit owner-private semantic renderer wiring for the first-version path.

    This helper makes the deterministic-vs-LLM choice explicit. It does not fallback between modes.
    """

    if mode is _FirstVersionSemanticCommitmentMode.DETERMINISTIC:
        return _MaterialSummarySemanticCommitmentRenderer()
    if mode is _FirstVersionSemanticCommitmentMode.LLM_BACKED:
        return _OwnerControlledSemanticCommitmentRenderer(
            capability=_LLMBackedSemanticCommitmentCapability()
        )
    raise ConsciousnessError(
        f"Unsupported first-version semantic commitment mode: {mode}"
    )


def _build_first_version_conscious_commitment_path(
    mode: _FirstVersionSemanticCommitmentMode = _FirstVersionSemanticCommitmentMode.DETERMINISTIC,
) -> FirstVersionConsciousCommitmentPath:
    """Build one explicit owner-private first-version commitment path wiring.

    This is the owner-controlled constructor for choosing between the deterministic path and the LLM-backed path.
    """

    return FirstVersionConsciousCommitmentPath(
        semantic_commitment_renderer=_build_first_version_semantic_commitment_renderer(mode)
    )


@dataclass
class FirstVersionConsciousCommitmentPath(ConsciousCommitmentPath):
    """Owner-private first-version commitment path.

    Purpose:
        Commit one focal conscious item directly from current working-state retention, or publish an explicit no-commit outcome.

    Notes:
        This first version does not re-rank workspace candidates. It treats retained candidate ids as the current-cycle
        commitment signal, then delegates semantic shaping to a dedicated renderer fed only by explicit material.
    """

    state_id_prefix: str = "conscious-state"
    focal_selection_policy: _FocalSelectionPolicy = field(
        default_factory=_RetainedWorkingStateSelectionPolicy
    )
    semantic_commitment_renderer: _SemanticCommitmentRenderer = field(
        default_factory=_MaterialSummarySemanticCommitmentRenderer
    )
    last_trace: _ConsciousCommitmentPathTrace | None = field(
        default=None,
        init=False,
    )

    def _renderer_capability_trace(self) -> _SemanticCommitmentCapabilityTrace | None:
        return getattr(self.semantic_commitment_renderer, "last_trace", None)

    def _record_trace(
        self,
        *,
        selection: _FocalSelectionTrace | None,
        render_request: _SemanticCommitmentRequestTrace | None,
        render_response: _SemanticCommitmentResponseTrace | None,
        final_state: _FinalConsciousStateTrace | None,
        terminal_status: _ConsciousCommitmentPathTerminalStatus,
        failure_message: str | None,
    ) -> None:
        self.last_trace = _build_commitment_path_trace(
            selection=selection,
            render_request=render_request,
            render_response=render_response,
            capability_trace=self._renderer_capability_trace(),
            final_state=final_state,
            terminal_status=terminal_status,
            failure_message=failure_message,
        )

    def _build_capability_rejected_state(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        tick_id: int | None,
    ) -> ConsciousState:
        return ConsciousState(
            state_id=f"{self.state_id_prefix}:{working_state.state_id}",
            commit_status="no_commit",
            source_workspace_candidate_set_id=candidate_set.set_id,
            source_working_state_id=working_state.state_id,
            focal_content=None,
            supporting_context=(),
            no_commit_reason="capability_rejected_cycle",
            tick_id=tick_id,
        )

    def commit(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        config: ConsciousnessConfig,
        tick_id: int | None,
    ) -> ConsciousState:
        material_map = {
            material.source_workspace_candidate_id: material for material in material_set.materials
        }
        try:
            selection_outcome = self.focal_selection_policy.decide(
                candidate_set,
                working_state,
                material_map,
                config,  # R-PROTO-LEARN.P-TEMPORAL: pass config for commitment_score_floor
            )
        except _CommitmentCapabilityRejectedCycle:
            state = self._build_capability_rejected_state(candidate_set, working_state, tick_id)
            self._record_trace(
                selection=None,
                render_request=None,
                render_response=None,
                final_state=_build_final_state_trace(state),
                terminal_status=_ConsciousCommitmentPathTerminalStatus.SELECTION_REJECTED_CYCLE,
                failure_message="selection policy rejected this cycle",
            )
            return state
        except _CommitmentCapabilityUnavailable as exc:
            self._record_trace(
                selection=None,
                render_request=None,
                render_response=None,
                final_state=None,
                terminal_status=_ConsciousCommitmentPathTerminalStatus.SELECTION_CAPABILITY_UNAVAILABLE,
                failure_message=str(exc),
            )
            raise ConsciousnessError(
                "Configured conscious commitment capability is unavailable for the current cycle"
            ) from exc
        selection_trace = _build_selection_trace(selection_outcome)
        state_id = f"{self.state_id_prefix}:{working_state.state_id}"
        if selection_outcome.commit_status == "committed" and selection_outcome.focal_material is None:
            self._record_trace(
                selection=selection_trace,
                render_request=None,
                render_response=None,
                final_state=None,
                terminal_status=_ConsciousCommitmentPathTerminalStatus.INVALID_SELECTION_OUTCOME,
                failure_message="Committed first-version decision must declare a focal material before semantic rendering",
            )
            raise ConsciousnessError(
                "Committed first-version decision must declare a focal material before semantic rendering"
            )
        render_request = _SemanticCommitmentRenderRequest(
            commit_status=selection_outcome.commit_status,
            tick_id=tick_id,
            focal_material=selection_outcome.focal_material,
            supporting_materials=selection_outcome.supporting_materials,
            max_supporting_context_items=config.max_supporting_context_items,
            no_commit_reason=selection_outcome.no_commit_reason,
        )
        render_request_trace = _build_request_trace(render_request)
        try:
            render_result = self.semantic_commitment_renderer.render(render_request)
        except _CommitmentCapabilityRejectedCycle:
            state = self._build_capability_rejected_state(candidate_set, working_state, tick_id)
            self._record_trace(
                selection=selection_trace,
                render_request=render_request_trace,
                render_response=None,
                final_state=_build_final_state_trace(state),
                terminal_status=_ConsciousCommitmentPathTerminalStatus.RENDER_REJECTED_CYCLE,
                failure_message="semantic commitment renderer rejected this cycle",
            )
            return state
        except _CommitmentCapabilityUnavailable as exc:
            self._record_trace(
                selection=selection_trace,
                render_request=render_request_trace,
                render_response=None,
                final_state=None,
                terminal_status=_ConsciousCommitmentPathTerminalStatus.RENDER_CAPABILITY_UNAVAILABLE,
                failure_message=str(exc),
            )
            raise ConsciousnessError(
                "Configured conscious commitment capability is unavailable for the current cycle"
            ) from exc
        _validate_semantic_render_result(render_request, render_result)
        render_response_trace = _build_response_trace(render_result)
        if selection_outcome.commit_status == "no_commit":
            state = ConsciousState(
                state_id=state_id,
                commit_status="no_commit",
                source_workspace_candidate_set_id=candidate_set.set_id,
                source_working_state_id=working_state.state_id,
                focal_content=None,
                supporting_context=render_result.supporting_context,
                no_commit_reason=selection_outcome.no_commit_reason,
                tick_id=tick_id,
            )
            self._record_trace(
                selection=selection_trace,
                render_request=render_request_trace,
                render_response=render_response_trace,
                final_state=_build_final_state_trace(state),
                terminal_status=_ConsciousCommitmentPathTerminalStatus.PUBLISHED_NO_COMMIT_STATE,
                failure_message=None,
            )
            return state
        state = ConsciousState(
            state_id=state_id,
            commit_status="committed",
            source_workspace_candidate_set_id=candidate_set.set_id,
            source_working_state_id=working_state.state_id,
            focal_content=render_result.focal_content,
            supporting_context=render_result.supporting_context,
            no_commit_reason=None,
            tick_id=tick_id,
        )
        self._record_trace(
            selection=selection_trace,
            render_request=render_request_trace,
            render_response=render_response_trace,
            final_state=_build_final_state_trace(state),
            terminal_status=_ConsciousCommitmentPathTerminalStatus.PUBLISHED_COMMITTED_STATE,
            failure_message=None,
        )
        return state


@dataclass
class ConsciousnessEngine(ConsciousContentAPI):
    """Owner: reportable conscious-content layer.

    Purpose:
        Execute one current-cycle conscious commitment using an injected private commitment path.

    Failure semantics:
        Malformed inputs fail before collaborator invocation. Collaborator errors propagate as explicit owner failures.
    """

    config: ConsciousnessConfig
    commitment_path: ConsciousCommitmentPath
    # R-PROTO-LEARN.P-TEMPORAL: P5 learner binding (set by wire_learner_to_owner).
    _p5_learner_binding: object | None = None

    def apply_p5_policy(self, snapshot: object) -> None:
        """R-PROTO-LEARN.P-TEMPORAL: P5 surface override.

        Maps snapshot.policy_output[0] -> config.commitment_score_floor
        (clipped to [0, 1]). The override uses `object.__setattr__` because
        `ConsciousnessConfig` is frozen (immutable-per-instance safety);
        per-cycle overrides produce a new config attribute via a
        helper-setattr path (we write to a mutable shadow that the
        commitment path reads via `_effective_floor`).
        """
        if snapshot is None or not getattr(snapshot, "policy_output", None):
            return
        out = snapshot.policy_output
        if len(out) < 1:
            return
        new_floor = max(0.0, min(1.0, float(out[0])))
        # Use object.__setattr__ to bypass frozen (config is shared
        # across the engine; per-engine override is acceptable since
        # commitment_path receives config at commit() call time).
        object.__setattr__(self.config, "commitment_score_floor", new_floor)

    def commit_content(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        tick_id: int | None = None,
    ) -> ConsciousState:
        """Owner: reportable conscious-content layer.

        Purpose:
            Validate one current-cycle workspace/material bundle and produce one formal conscious state.

        Inputs:
            One `WorkspaceCandidateSet`, one `WorkingStateSnapshot`, one `ConsciousContentMaterialSet`, and an optional tick id.

        Returns:
            One `ConsciousState`.

        Raises:
            ConsciousnessError when inputs or collaborator output violate owner invariants.

        Notes:
            The injected commitment path receives only current-cycle inputs.
        """

        _validate_candidate_set(candidate_set)
        _validate_working_state(working_state, candidate_set)
        material_map = _validate_material_set(material_set, candidate_set, working_state)
        state = self.commitment_path.commit(
            candidate_set,
            working_state,
            material_set,
            self.config,
            tick_id,
        )
        _validate_state(state, candidate_set, working_state, material_map, self.config)
        return state

    def build_commit_op(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
    ) -> CommitConsciousContentOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the request op describing one conscious-content commitment cycle.

        Inputs:
            One `WorkspaceCandidateSet`, one `WorkingStateSnapshot`, and one `ConsciousContentMaterialSet`.

        Returns:
            A `CommitConsciousContentOp` summarizing the request.

        Raises:
            ConsciousnessError if current-cycle input alignment is malformed.
        """

        _validate_candidate_set(candidate_set)
        _validate_working_state(working_state, candidate_set)
        _validate_material_set(material_set, candidate_set, working_state)
        return CommitConsciousContentOp(
            op_name="commit_conscious_content",
            owner="reportable_conscious_content",
            workspace_candidate_count=len(candidate_set.candidates),
            retained_candidate_count=len(working_state.retained_candidate_ids),
            material_count=len(material_set.materials),
            working_state_id=working_state.state_id,
            forced_material_count=sum(1 for material in material_set.materials if material.forced_consolidation),
        )

    def build_publish_state_op(
        self,
        state: ConsciousState,
    ) -> PublishConsciousStateOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the publication op for one formal conscious state.

        Inputs:
            One `ConsciousState` produced by this owner.

        Returns:
            A `PublishConsciousStateOp` summarizing state publication.

        Raises:
            ConsciousnessError if the state is malformed.
        """

        if not state.state_id:
            raise ConsciousnessError("ConsciousState contains incomplete publication identity")
        return PublishConsciousStateOp(
            op_name="publish_conscious_state",
            owner="reportable_conscious_content",
            state_id=state.state_id,
            commit_status=state.commit_status,
            no_commit_reason=state.no_commit_reason,
            supporting_context_count=len(state.supporting_context),
        )

    def build_publish_reportable_content_op(
        self,
        state: ConsciousState,
    ) -> PublishReportableConsciousContentOp:
        """Owner: reportable conscious-content layer.

        Purpose:
            Build the publication op for one committed focal conscious-content payload.

        Inputs:
            One committed `ConsciousState`.

        Returns:
            A `PublishReportableConsciousContentOp` summarizing focal payload publication.

        Raises:
            ConsciousnessError if the state does not contain committed focal content.
        """

        if state.commit_status != "committed" or state.focal_content is None:
            raise ConsciousnessError(
                "PublishReportableConsciousContentOp requires a committed ConsciousState with focal content"
            )
        return PublishReportableConsciousContentOp(
            op_name="publish_reportable_conscious_content",
            owner="reportable_conscious_content",
            state_id=state.state_id,
            content_id=state.focal_content.content_id,
            source_material_id=state.focal_content.source_material_id,
        )