from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from helios_v2.consciousness import (
    ConsciousContentMaterial,
    ConsciousContentMaterialSet,
    ConsciousState,
    ConsciousnessConfig,
    ConsciousnessEngine,
    ConsciousnessError,
    FirstVersionConsciousCommitmentPath,
    ReportableConsciousContent,
    SupportingContextItem,
)
from helios_v2.consciousness.engine import ConsciousCommitmentPath
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.workspace import WorkingStateSnapshot, WorkspaceCandidate, WorkspaceCandidateSet


def _build_feeling() -> InteroceptiveFeelingVector:
    return InteroceptiveFeelingVector(
        valence=0.4,
        arousal=0.7,
        tension=0.5,
        comfort=0.2,
        fatigue=0.3,
        pain_like=0.1,
        social_safety=0.4,
    )


def _build_config() -> ConsciousnessConfig:
    return ConsciousnessConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        conscious_state_bootstrap_id="consciousness-bootstrap:v1",
        max_supporting_context_items=2,
        mandatory_learned_parameters=(
            "commitment_policy",
            "quiet_state_policy",
            "semantic_shaping_policy",
        ),
    )


def _build_candidate_set() -> WorkspaceCandidateSet:
    return WorkspaceCandidateSet(
        set_id="workspace-set:001",
        source_feeling_state_id="feeling-state:001",
        candidates=(
            WorkspaceCandidate(
                candidate_id="workspace-candidate:001",
                source_memory_candidate_id="memory-candidate:001",
                source_feeling_state_id="feeling-state:001",
                priority_hint=0.8,
                forced_consolidation=True,
                workspace_score_hint=0.95,
            ),
            WorkspaceCandidate(
                candidate_id="workspace-candidate:002",
                source_memory_candidate_id="memory-candidate:002",
                source_feeling_state_id="feeling-state:001",
                priority_hint=0.5,
                forced_consolidation=False,
                workspace_score_hint=0.6,
            ),
        ),
        tick_id=7,
    )


def _build_working_state() -> WorkingStateSnapshot:
    return WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=("workspace-candidate:001",),
        tick_id=7,
    )


def _build_material(
    candidate_id: str,
    memory_candidate_id: str,
    memory_id: str,
    forced_consolidation: bool,
    workspace_score_hint: float,
    priority_hint: float,
) -> ConsciousContentMaterial:
    return ConsciousContentMaterial(
        material_id=f"material:{candidate_id}",
        source_workspace_candidate_id=candidate_id,
        source_memory_candidate_id=memory_candidate_id,
        source_memory_id=memory_id,
        source_feeling_state_id="feeling-state:001",
        content_kind="situational-summary",
        material_summary=f"situational-summary: {candidate_id}",
        summary_ref=f"summary:{candidate_id}",
        context_ref=f"context:{candidate_id}",
        salient_tokens=(candidate_id,),
        affect_tag=_build_feeling(),
        forced_consolidation=forced_consolidation,
        workspace_score_hint=workspace_score_hint,
        priority_hint=priority_hint,
    )


def _build_material_set() -> ConsciousContentMaterialSet:
    return ConsciousContentMaterialSet(
        set_id="material-set:001",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        materials=(
            _build_material(
                candidate_id="workspace-candidate:001",
                memory_candidate_id="memory-candidate:001",
                memory_id="memory:001",
                forced_consolidation=True,
                workspace_score_hint=0.95,
                priority_hint=0.8,
            ),
            _build_material(
                candidate_id="workspace-candidate:002",
                memory_candidate_id="memory-candidate:002",
                memory_id="memory:002",
                forced_consolidation=False,
                workspace_score_hint=0.6,
                priority_hint=0.5,
            ),
        ),
        tick_id=7,
    )


def _build_committed_state() -> ConsciousState:
    material_set = _build_material_set()
    focal_material = material_set.materials[0]
    supporting_material = material_set.materials[1]
    return ConsciousState(
        state_id="conscious-state:001",
        commit_status="committed",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        focal_content=ReportableConsciousContent(
            content_id="conscious-content:001",
            source_material_id=focal_material.material_id,
            source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
            source_memory_candidate_id=focal_material.source_memory_candidate_id,
            source_feeling_state_id=focal_material.source_feeling_state_id,
            content_kind=focal_material.content_kind,
            focal_summary="The current conscious focus is the dominant greeting signal.",
            affect_trace=focal_material.affect_tag,
            salient_tokens=focal_material.salient_tokens,
            tick_id=7,
        ),
        supporting_context=(
            SupportingContextItem(
                context_item_id="support:001",
                source_material_id=supporting_material.material_id,
                source_workspace_candidate_id=supporting_material.source_workspace_candidate_id,
                content_kind=supporting_material.content_kind,
                summary="Secondary context remains present but not focal.",
                affect_trace=supporting_material.affect_tag,
            ),
        ),
        no_commit_reason=None,
        tick_id=7,
    )


@dataclass
class RecordingCommitmentPath(ConsciousCommitmentPath):
    recorded_candidate_set: WorkspaceCandidateSet | None = None
    recorded_working_state: WorkingStateSnapshot | None = None
    recorded_material_set: ConsciousContentMaterialSet | None = None
    recorded_tick_id: int | None = None

    def commit(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        config: ConsciousnessConfig,
        tick_id: int | None,
    ) -> ConsciousState:
        assert config.max_supporting_context_items == 2
        self.recorded_candidate_set = candidate_set
        self.recorded_working_state = working_state
        self.recorded_material_set = material_set
        self.recorded_tick_id = tick_id
        return _build_committed_state()


@dataclass
class OverContextPath(ConsciousCommitmentPath):
    def commit(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_set: ConsciousContentMaterialSet,
        config: ConsciousnessConfig,
        tick_id: int | None,
    ) -> ConsciousState:
        del candidate_set, working_state, config, tick_id
        focal_material = material_set.materials[0]
        return ConsciousState(
            state_id="conscious-state:bad",
            commit_status="committed",
            source_workspace_candidate_set_id="workspace-set:001",
            source_working_state_id="working-state:001",
            focal_content=ReportableConsciousContent(
                content_id="conscious-content:bad",
                source_material_id=focal_material.material_id,
                source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
                source_memory_candidate_id=focal_material.source_memory_candidate_id,
                source_feeling_state_id=focal_material.source_feeling_state_id,
                content_kind=focal_material.content_kind,
                focal_summary="bad",
                affect_trace=focal_material.affect_tag,
                salient_tokens=focal_material.salient_tokens,
                tick_id=7,
            ),
            supporting_context=(
                SupportingContextItem(
                    context_item_id="support:1",
                    source_material_id=material_set.materials[1].material_id,
                    source_workspace_candidate_id=material_set.materials[1].source_workspace_candidate_id,
                    content_kind="situational-summary",
                    summary="one",
                    affect_trace=material_set.materials[1].affect_tag,
                ),
                SupportingContextItem(
                    context_item_id="support:2",
                    source_material_id=material_set.materials[1].material_id,
                    source_workspace_candidate_id=material_set.materials[1].source_workspace_candidate_id,
                    content_kind="situational-summary",
                    summary="two",
                    affect_trace=material_set.materials[1].affect_tag,
                ),
                SupportingContextItem(
                    context_item_id="support:3",
                    source_material_id=material_set.materials[1].material_id,
                    source_workspace_candidate_id=material_set.materials[1].source_workspace_candidate_id,
                    content_kind="situational-summary",
                    summary="three",
                    affect_trace=material_set.materials[1].affect_tag,
                ),
            ),
            no_commit_reason=None,
            tick_id=7,
        )


@dataclass
class RecordingDecisionPolicy:
    recorded_candidate_set: WorkspaceCandidateSet | None = None
    recorded_working_state: WorkingStateSnapshot | None = None
    recorded_material_keys: tuple[str, ...] = ()

    def decide(
        self,
        candidate_set: WorkspaceCandidateSet,
        working_state: WorkingStateSnapshot,
        material_map: dict[str, ConsciousContentMaterial],
    ):
        from helios_v2.consciousness.engine import _FocalSelectionOutcome

        self.recorded_candidate_set = candidate_set
        self.recorded_working_state = working_state
        self.recorded_material_keys = tuple(material_map)
        return _FocalSelectionOutcome(
            commit_status="committed",
            focal_material=material_map["workspace-candidate:001"],
            supporting_materials=(material_map["workspace-candidate:002"],),
            no_commit_reason=None,
        )


@dataclass
class RecordingRenderer:
    recorded_commit_status: str | None = None
    recorded_focal_material_id: str | None = None
    recorded_supporting_material_ids: tuple[str, ...] = ()
    recorded_tick_id: int | None = None
    recorded_no_commit_reason: str | None = None
    recorded_max_supporting_context_items: int | None = None

    def render(
        self,
        request,
    ):
        from helios_v2.consciousness.engine import _SemanticCommitmentRenderResult

        self.recorded_commit_status = request.commit_status
        self.recorded_focal_material_id = (
            request.focal_material.material_id if request.focal_material is not None else None
        )
        self.recorded_supporting_material_ids = tuple(
            material.material_id
            for material in request.supporting_materials[: request.max_supporting_context_items]
        )
        self.recorded_tick_id = request.tick_id
        self.recorded_no_commit_reason = request.no_commit_reason
        self.recorded_max_supporting_context_items = request.max_supporting_context_items
        focal_content = None
        if request.focal_material is not None:
            focal_material = request.focal_material
            focal_content = ReportableConsciousContent(
                content_id="conscious-content:custom",
                source_material_id=focal_material.material_id,
                source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
                source_memory_candidate_id=focal_material.source_memory_candidate_id,
                source_feeling_state_id=focal_material.source_feeling_state_id,
                content_kind=focal_material.content_kind,
                focal_summary="custom focal summary",
                affect_trace=focal_material.affect_tag,
                salient_tokens=focal_material.salient_tokens,
                tick_id=request.tick_id,
            )
        return _SemanticCommitmentRenderResult(
            focal_content=focal_content,
            supporting_context=tuple(
                SupportingContextItem(
                    context_item_id=f"support:{material.material_id}",
                    source_material_id=material.material_id,
                    source_workspace_candidate_id=material.source_workspace_candidate_id,
                    content_kind=material.content_kind,
                    summary=f"support from {material.material_id}",
                    affect_trace=material.affect_tag,
                )
                for material in request.supporting_materials[: request.max_supporting_context_items]
            )
        )


@dataclass
class RejectingRenderer:
    def render(self, request):
        del request
        from helios_v2.consciousness.engine import _CommitmentCapabilityRejectedCycle

        raise _CommitmentCapabilityRejectedCycle("renderer rejected this cycle")

@dataclass
class UnavailableRenderer:
    def render(self, request):
        del request
        from helios_v2.consciousness.engine import _CommitmentCapabilityUnavailable

        raise _CommitmentCapabilityUnavailable("renderer unavailable")



@dataclass
class RecordingOwnerControlledCapability:
    recorded_request: object | None = None

    def render(self, request):
        from helios_v2.consciousness.engine import _SemanticCommitmentRenderResult

        self.recorded_request = request
        focal_content = None
        if request.focal_material is not None:
            focal_material = request.focal_material
            focal_content = ReportableConsciousContent(
                content_id="conscious-content:owner-controlled",
                source_material_id=focal_material.material_id,
                source_workspace_candidate_id=focal_material.source_workspace_candidate_id,
                source_memory_candidate_id=focal_material.source_memory_candidate_id,
                source_feeling_state_id=focal_material.source_feeling_state_id,
                content_kind=focal_material.content_kind,
                focal_summary="owner controlled semantic summary",
                affect_trace=focal_material.affect_tag,
                salient_tokens=focal_material.salient_tokens,
                tick_id=request.tick_id,
            )
        return _SemanticCommitmentRenderResult(
            focal_content=focal_content,
            supporting_context=tuple(
                SupportingContextItem(
                    context_item_id=f"owner-support:{material.material_id}",
                    source_material_id=material.material_id,
                    source_workspace_candidate_id=material.source_workspace_candidate_id,
                    content_kind=material.content_kind,
                    summary=f"owner support from {material.material_id}",
                    affect_trace=material.affect_tag,
                )
                for material in request.supporting_materials[: request.max_supporting_context_items]
            ),
        )


@dataclass
class RejectingOwnerControlledCapability:
    def render(self, request):
        del request
        from helios_v2.consciousness.engine import _CommitmentCapabilityRejectedCycle

        raise _CommitmentCapabilityRejectedCycle("owner capability rejected this cycle")


@dataclass
class RecordingLLMRequestBuilder:
    recorded_input: object | None = None
    model: str = "test-llm-model"

    def build_request(self, builder_input):
        from helios_v2.consciousness.engine import _LLMSemanticCommitmentCapabilityRequest

        self.recorded_input = builder_input
        return _LLMSemanticCommitmentCapabilityRequest(
            model=self.model,
            system_prompt="test system prompt",
            user_prompt="test user prompt",
            temperature=0.2,
            max_tokens=321,
            response_format_json=True,
            render_request=builder_input.render_request,
            request_trace=builder_input.request_trace,
            selection_trace=builder_input.selection_trace,
        )


@dataclass
class RecordingLLMTransport:
    recorded_request: object | None = None

    def render(self, request):
        from helios_v2.consciousness.engine import _SemanticCommitmentRenderResult

        self.recorded_request = request
        return _SemanticCommitmentRenderResult(
            focal_content=ReportableConsciousContent(
                content_id="conscious-content:llm",
                source_material_id="material:workspace-candidate:001",
                source_workspace_candidate_id="workspace-candidate:001",
                source_memory_candidate_id="memory-candidate:001",
                source_feeling_state_id="feeling-state:001",
                content_kind="situational-summary",
                focal_summary="llm backed semantic summary",
                affect_trace=_build_feeling(),
                salient_tokens=("workspace-candidate:001",),
                tick_id=7,
            ),
            supporting_context=(
                SupportingContextItem(
                    context_item_id="support:llm:001",
                    source_material_id="material:workspace-candidate:002",
                    source_workspace_candidate_id="workspace-candidate:002",
                    content_kind="situational-summary",
                    summary="llm supporting summary",
                    affect_trace=_build_feeling(),
                ),
            ),
        )


@dataclass
class FakeOpenAIMessage:
    content: str


@dataclass
class FakeOpenAIChoice:
    message: FakeOpenAIMessage


@dataclass
class FakeOpenAIResponse:
    choices: tuple[FakeOpenAIChoice, ...]


@dataclass
class FakeOpenAIChatCompletions:
    response_text: str
    recorded_payload: dict[str, object] | None = None

    def create(self, **kwargs):
        self.recorded_payload = kwargs
        return FakeOpenAIResponse(
            choices=(FakeOpenAIChoice(message=FakeOpenAIMessage(content=self.response_text)),)
        )


@dataclass
class FakeOpenAIChat:
    completions: FakeOpenAIChatCompletions


@dataclass
class FakeOpenAIClient:
    chat: FakeOpenAIChat


@dataclass
class FakeOpenAIClientProvider:
    client: object

    def get_client(self):
        return self.client


@dataclass
class FakeOpenAIConstructor:
    recorded_api_key: str | None = None
    recorded_base_url: str | None = None

    def __call__(self, *, api_key, base_url):
        self.recorded_api_key = api_key
        self.recorded_base_url = base_url
        return FakeOpenAIClient(chat=FakeOpenAIChat(completions=FakeOpenAIChatCompletions(response_text="{}")))


def test_engine_commits_current_cycle_inputs_via_private_path() -> None:
    path = RecordingCommitmentPath()
    engine = ConsciousnessEngine(config=_build_config(), commitment_path=path)
    candidate_set = _build_candidate_set()
    working_state = _build_working_state()
    material_set = _build_material_set()

    state = engine.commit_content(candidate_set, working_state, material_set, tick_id=7)
    commit_op = engine.build_commit_op(candidate_set, working_state, material_set)
    publish_state_op = engine.build_publish_state_op(state)
    publish_content_op = engine.build_publish_reportable_content_op(state)

    assert path.recorded_candidate_set is candidate_set
    assert path.recorded_working_state is working_state
    assert path.recorded_material_set is material_set
    assert path.recorded_tick_id == 7
    assert state.commit_status == "committed"
    assert state.focal_content is not None
    assert state.focal_content.source_workspace_candidate_id == "workspace-candidate:001"
    assert commit_op.workspace_candidate_count == 2
    assert commit_op.retained_candidate_count == 1
    assert commit_op.forced_material_count == 1
    assert publish_state_op.commit_status == "committed"
    assert publish_content_op.source_material_id == "material:workspace-candidate:001"


def test_first_version_path_commits_single_retained_material_and_generates_supporting_context() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)
    publish_state_op = engine.build_publish_state_op(state)
    publish_content_op = engine.build_publish_reportable_content_op(state)

    assert state.commit_status == "committed"
    assert state.focal_content is not None
    assert state.focal_content.source_workspace_candidate_id == "workspace-candidate:001"
    assert state.focal_content.focal_summary == (
        "Current focal content from situational-summary: situational-summary: workspace-candidate:001. "
        "Salient cues: workspace-candidate:001"
    )
    assert len(state.supporting_context) == 1
    assert state.supporting_context[0].source_workspace_candidate_id == "workspace-candidate:002"
    assert state.supporting_context[0].summary == (
        "Supporting context from situational-summary: situational-summary: workspace-candidate:002. "
        "Salient cues: workspace-candidate:002"
    )
    assert publish_state_op.commit_status == "committed"
    assert publish_content_op.source_material_id == "material:workspace-candidate:001"


def test_first_version_path_publishes_explicit_no_commit_when_no_retained_signal_exists() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    working_state = WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=(),
        tick_id=7,
    )

    state = engine.commit_content(_build_candidate_set(), working_state, _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "insufficient_commitment_signal"
    assert state.supporting_context == ()

    with pytest.raises(ConsciousnessError, match="requires a committed ConsciousState"):
        engine.build_publish_reportable_content_op(state)


def test_first_version_path_publishes_conflict_no_commit_for_multiple_retained_ids() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    working_state = WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=("workspace-candidate:001", "workspace-candidate:002"),
        tick_id=7,
    )

    state = engine.commit_content(_build_candidate_set(), working_state, _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "semantic_conflict_unresolved"
    assert len(state.supporting_context) == 2
    assert tuple(item.source_workspace_candidate_id for item in state.supporting_context) == (
        "workspace-candidate:001",
        "workspace-candidate:002",
    )


def test_first_version_path_rejects_non_reportable_whitespace_only_material() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    material_set = ConsciousContentMaterialSet(
        set_id="material-set:001",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        materials=(
            ConsciousContentMaterial(
                material_id="material:workspace-candidate:001",
                source_workspace_candidate_id="workspace-candidate:001",
                source_memory_candidate_id="memory-candidate:001",
                source_memory_id="memory:001",
                source_feeling_state_id="feeling-state:001",
                content_kind="situational-summary",
                material_summary="   ",
                summary_ref="summary:001",
                context_ref="context:001",
                salient_tokens=(),
                affect_tag=_build_feeling(),
                forced_consolidation=True,
                workspace_score_hint=0.95,
                priority_hint=0.8,
            ),
            _build_material(
                candidate_id="workspace-candidate:002",
                memory_candidate_id="memory-candidate:002",
                memory_id="memory:002",
                forced_consolidation=False,
                workspace_score_hint=0.6,
                priority_hint=0.5,
            ),
        ),
        tick_id=7,
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), material_set, tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "context_not_reportable"


def test_first_version_path_can_compose_private_decision_and_renderer_collaborators() -> None:
    decision_policy = RecordingDecisionPolicy()
    renderer = RecordingRenderer()
    path = FirstVersionConsciousCommitmentPath(
        focal_selection_policy=decision_policy,
        semantic_commitment_renderer=renderer,
    )
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=path,
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert decision_policy.recorded_candidate_set is not None
    assert decision_policy.recorded_candidate_set.set_id == "workspace-set:001"
    assert decision_policy.recorded_working_state is not None
    assert decision_policy.recorded_working_state.state_id == "working-state:001"
    assert decision_policy.recorded_material_keys == (
        "workspace-candidate:001",
        "workspace-candidate:002",
    )
    assert renderer.recorded_focal_material_id == "material:workspace-candidate:001"
    assert renderer.recorded_supporting_material_ids == ("material:workspace-candidate:002",)
    assert renderer.recorded_tick_id == 7
    assert renderer.recorded_commit_status == "committed"
    assert renderer.recorded_no_commit_reason is None
    assert renderer.recorded_max_supporting_context_items == 2
    assert state.focal_content is not None
    assert state.focal_content.focal_summary == "custom focal summary"
    assert path.last_trace is not None
    assert path.last_trace.terminal_status.value == "published_committed_state"
    assert path.last_trace.failure_message is None
    assert path.last_trace.selection is not None
    assert path.last_trace.selection.commit_status == "committed"
    assert path.last_trace.selection.focal_material_id == "material:workspace-candidate:001"
    assert path.last_trace.render_request is not None
    assert path.last_trace.render_request.max_supporting_context_items == 2
    assert path.last_trace.render_response is not None
    assert path.last_trace.render_response.focal_content_id == "conscious-content:custom"
    assert path.last_trace.final_state is not None
    assert path.last_trace.final_state.state_id == state.state_id
    assert path.last_trace.final_state.focal_content_id == state.focal_content.content_id


def test_owner_controlled_renderer_skeleton_forwards_private_request_shape_without_llm_call() -> None:
    from helios_v2.consciousness.engine import _OwnerControlledSemanticCommitmentRenderer

    capability = RecordingOwnerControlledCapability()
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert capability.recorded_request is not None
    assert capability.recorded_request.commit_status == "committed"
    assert capability.recorded_request.tick_id == 7
    assert capability.recorded_request.focal_material is not None
    assert capability.recorded_request.focal_material.material_id == "material:workspace-candidate:001"
    assert tuple(
        material.material_id for material in capability.recorded_request.supporting_materials
    ) == ("material:workspace-candidate:002",)
    assert capability.recorded_request.max_supporting_context_items == 2
    assert capability.recorded_request.no_commit_reason is None
    assert renderer.last_trace is not None
    assert renderer.last_trace.renderer_name == "_OwnerControlledSemanticCommitmentRenderer"
    assert renderer.last_trace.capability_name == "RecordingOwnerControlledCapability"
    assert renderer.last_trace.terminal_status.value == "rendered"
    assert renderer.last_trace.failure_message is None
    assert renderer.last_trace.request.focal_material_id == "material:workspace-candidate:001"
    assert renderer.last_trace.request.supporting_material_ids == ("material:workspace-candidate:002",)
    assert renderer.last_trace.response is not None
    assert renderer.last_trace.response.focal_content_id == "conscious-content:owner-controlled"
    assert renderer.last_trace.response.focal_source_material_id == "material:workspace-candidate:001"
    assert renderer.last_trace.response.supporting_source_material_ids == (
        "material:workspace-candidate:002",
    )
    assert engine.commitment_path.last_trace is not None
    assert engine.commitment_path.last_trace.capability_trace == renderer.last_trace
    assert engine.commitment_path.last_trace.terminal_status.value == "published_committed_state"
    assert state.focal_content is not None
    assert state.focal_content.focal_summary == "owner controlled semantic summary"


def test_owner_controlled_renderer_skeleton_fails_explicitly_when_capability_is_not_configured() -> None:
    from helios_v2.consciousness.engine import _OwnerControlledSemanticCommitmentRenderer

    renderer = _OwnerControlledSemanticCommitmentRenderer()
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    with pytest.raises(ConsciousnessError, match="capability is unavailable"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert renderer.last_trace is not None
    assert renderer.last_trace.capability_name == "_UnavailableOwnerControlledSemanticCommitmentCapability"
    assert renderer.last_trace.terminal_status.value == "capability_unavailable"
    assert renderer.last_trace.response is None
    assert renderer.last_trace.request.focal_material_id == "material:workspace-candidate:001"
    assert renderer.last_trace.failure_message == "Owner-controlled semantic commitment capability is not configured"
    assert engine.commitment_path.last_trace is not None
    assert engine.commitment_path.last_trace.terminal_status.value == "render_capability_unavailable"
    assert engine.commitment_path.last_trace.render_request is not None
    assert engine.commitment_path.last_trace.render_request.focal_material_id == "material:workspace-candidate:001"
    assert engine.commitment_path.last_trace.render_response is None
    assert engine.commitment_path.last_trace.final_state is None
    assert engine.commitment_path.last_trace.capability_trace == renderer.last_trace


def test_owner_controlled_renderer_skeleton_records_rejected_cycle_trace() -> None:
    from helios_v2.consciousness.engine import _OwnerControlledSemanticCommitmentRenderer

    renderer = _OwnerControlledSemanticCommitmentRenderer(
        capability=RejectingOwnerControlledCapability()
    )
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "capability_rejected_cycle"
    assert renderer.last_trace is not None
    assert renderer.last_trace.capability_name == "RejectingOwnerControlledCapability"
    assert renderer.last_trace.terminal_status.value == "rejected_cycle"
    assert renderer.last_trace.response is None
    assert renderer.last_trace.request.supporting_material_ids == ("material:workspace-candidate:002",)
    assert renderer.last_trace.failure_message == "owner capability rejected this cycle"
    assert engine.commitment_path.last_trace is not None
    assert engine.commitment_path.last_trace.terminal_status.value == "render_rejected_cycle"
    assert engine.commitment_path.last_trace.selection is not None
    assert engine.commitment_path.last_trace.selection.commit_status == "committed"
    assert engine.commitment_path.last_trace.render_request is not None
    assert engine.commitment_path.last_trace.render_response is None
    assert engine.commitment_path.last_trace.final_state is not None
    assert engine.commitment_path.last_trace.final_state.commit_status == "no_commit"
    assert engine.commitment_path.last_trace.final_state.no_commit_reason == "capability_rejected_cycle"
    assert engine.commitment_path.last_trace.capability_trace == renderer.last_trace


def test_first_version_path_records_private_observability_snapshot_for_no_commit_publication() -> None:
    path = FirstVersionConsciousCommitmentPath()
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=path,
    )
    working_state = WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=("workspace-candidate:001", "workspace-candidate:002"),
        tick_id=7,
    )

    state = engine.commit_content(_build_candidate_set(), working_state, _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "semantic_conflict_unresolved"
    assert path.last_trace is not None
    assert path.last_trace.terminal_status.value == "published_no_commit_state"
    assert path.last_trace.failure_message is None
    assert path.last_trace.selection is not None
    assert path.last_trace.selection.commit_status == "no_commit"
    assert path.last_trace.selection.focal_material_id is None
    assert path.last_trace.selection.supporting_material_ids == (
        "material:workspace-candidate:001",
        "material:workspace-candidate:002",
    )
    assert path.last_trace.render_request is not None
    assert path.last_trace.render_request.no_commit_reason == "semantic_conflict_unresolved"
    assert path.last_trace.render_response is not None
    assert path.last_trace.render_response.focal_content_id is None
    assert path.last_trace.final_state is not None
    assert path.last_trace.final_state.state_id == state.state_id
    assert path.last_trace.final_state.no_commit_reason == "semantic_conflict_unresolved"
    assert path.last_trace.capability_trace is None


def test_llm_backed_semantic_capability_request_builder_consumes_owner_private_request_and_trace_surface() -> None:
    from helios_v2.consciousness.engine import (
        _LLMBackedSemanticCommitmentCapability,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    request_builder = RecordingLLMRequestBuilder()
    transport = RecordingLLMTransport()
    capability = _LLMBackedSemanticCommitmentCapability(
        request_builder=request_builder,
        transport=transport,
    )
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    path = FirstVersionConsciousCommitmentPath(semantic_commitment_renderer=renderer)
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=path,
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert request_builder.recorded_input is not None
    assert request_builder.recorded_input.request_trace.focal_material_id == "material:workspace-candidate:001"
    assert request_builder.recorded_input.request_trace.supporting_material_ids == (
        "material:workspace-candidate:002",
    )
    assert request_builder.recorded_input.selection_trace.commit_status == "committed"
    assert request_builder.recorded_input.selection_trace.focal_material_id == "material:workspace-candidate:001"
    assert capability.last_built_request is not None
    assert capability.last_built_request.model == "test-llm-model"
    assert capability.last_built_request.request_trace == request_builder.recorded_input.request_trace
    assert capability.last_built_request.selection_trace == request_builder.recorded_input.selection_trace
    assert transport.recorded_request is capability.last_built_request
    assert renderer.last_trace is not None
    assert renderer.last_trace.terminal_status.value == "rendered"
    assert path.last_trace is not None
    assert path.last_trace.capability_trace == renderer.last_trace
    assert path.last_trace.terminal_status.value == "published_committed_state"
    assert state.focal_content is not None
    assert state.focal_content.focal_summary == "llm backed semantic summary"


def test_llm_backed_semantic_capability_defaults_to_openai_compatible_private_wiring() -> None:
    from helios_v2.consciousness.engine import (
        _DefaultOpenAICompatibleClientProvider,
        _LLMBackedSemanticCommitmentCapability,
        _OpenAICompatibleSemanticCommitmentTransport,
    )

    capability = _LLMBackedSemanticCommitmentCapability()

    assert isinstance(capability.transport, _OpenAICompatibleSemanticCommitmentTransport)
    assert isinstance(capability.transport.client_provider, _DefaultOpenAICompatibleClientProvider)


def test_private_wiring_helper_builds_deterministic_first_version_path_without_llm_renderer() -> None:
    from helios_v2.consciousness.engine import (
        _FirstVersionSemanticCommitmentMode,
        _MaterialSummarySemanticCommitmentRenderer,
        _build_first_version_conscious_commitment_path,
    )

    path = _build_first_version_conscious_commitment_path(
        _FirstVersionSemanticCommitmentMode.DETERMINISTIC
    )

    assert isinstance(path.semantic_commitment_renderer, _MaterialSummarySemanticCommitmentRenderer)


def test_private_wiring_helper_builds_llm_backed_first_version_path_without_fallback() -> None:
    from helios_v2.consciousness.engine import (
        _FirstVersionSemanticCommitmentMode,
        _LLMBackedSemanticCommitmentCapability,
        _OwnerControlledSemanticCommitmentRenderer,
        _build_first_version_conscious_commitment_path,
    )

    path = _build_first_version_conscious_commitment_path(
        _FirstVersionSemanticCommitmentMode.LLM_BACKED
    )

    assert isinstance(path.semantic_commitment_renderer, _OwnerControlledSemanticCommitmentRenderer)
    assert isinstance(path.semantic_commitment_renderer.capability, _LLMBackedSemanticCommitmentCapability)


def test_private_wiring_helper_llm_backed_mode_still_fails_explicitly_without_runtime_capability(
    monkeypatch,
) -> None:
    from helios_v2.consciousness.engine import (
        _FirstVersionSemanticCommitmentMode,
        _build_first_version_conscious_commitment_path,
    )

    monkeypatch.delenv("HELIOS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = _build_first_version_conscious_commitment_path(
        _FirstVersionSemanticCommitmentMode.LLM_BACKED
    )
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=path,
    )

    with pytest.raises(ConsciousnessError, match="capability is unavailable"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert path.last_trace is not None
    assert path.last_trace.terminal_status.value == "render_capability_unavailable"


def test_llm_backed_semantic_capability_default_private_wiring_can_run_with_env_backed_provider(
    monkeypatch,
) -> None:
    from helios_v2.consciousness.engine import (
        _LLMBackedSemanticCommitmentCapability,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    response_text = json.dumps(
        {
            "focal_content": {
                "source_material_id": "material:workspace-candidate:001",
                "focal_summary": "default provider semantic summary",
                "salient_tokens": ["workspace-candidate:001", "default-provider"],
            },
            "supporting_context": [
                {
                    "source_material_id": "material:workspace-candidate:002",
                    "summary": "default provider supporting summary",
                }
            ],
        },
        ensure_ascii=False,
    )
    constructor = FakeOpenAIConstructor()
    constructor_client = FakeOpenAIClient(
        chat=FakeOpenAIChat(
            completions=FakeOpenAIChatCompletions(response_text=response_text)
        )
    )

    def _construct_client(*, api_key, base_url):
        constructor(api_key=api_key, base_url=base_url)
        return constructor_client

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_construct_client))
    monkeypatch.setenv("HELIOS_LLM_API_KEY", "default-helios-key")
    monkeypatch.setenv("HELIOS_LLM_BASE_URL", "https://default-helios.example/v1")
    monkeypatch.setenv("HELIOS_LLM_MODEL", "default-helios-model")

    capability = _LLMBackedSemanticCommitmentCapability()
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert constructor.recorded_api_key == "default-helios-key"
    assert constructor.recorded_base_url == "https://default-helios.example/v1"
    assert capability.last_built_request is not None
    assert capability.last_built_request.model == "owner-controlled-semantic-llm"
    assert state.focal_content is not None
    assert state.focal_content.focal_summary == "default provider semantic summary"
    assert state.focal_content.salient_tokens == ("workspace-candidate:001", "default-provider")
    assert renderer.last_trace is not None
    assert renderer.last_trace.terminal_status.value == "rendered"


def test_openai_compatible_transport_builds_request_payload_and_parses_response() -> None:
    from helios_v2.consciousness.engine import (
        _CurrentCycleLLMSemanticCommitmentRequestBuilder,
        _LLMBackedSemanticCommitmentCapability,
        _OpenAICompatibleSemanticCommitmentTransport,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    response_text = json.dumps(
        {
            "focal_content": {
                "source_material_id": "material:workspace-candidate:001",
                "focal_summary": "openai compatible semantic summary",
                "salient_tokens": ["workspace-candidate:001", "focus"],
            },
            "supporting_context": [
                {
                    "source_material_id": "material:workspace-candidate:002",
                    "summary": "openai compatible supporting summary",
                }
            ],
        },
        ensure_ascii=False,
    )
    completions = FakeOpenAIChatCompletions(response_text=response_text)
    provider = FakeOpenAIClientProvider(
        client=FakeOpenAIClient(chat=FakeOpenAIChat(completions=completions))
    )
    transport = _OpenAICompatibleSemanticCommitmentTransport(client_provider=provider)
    capability = _LLMBackedSemanticCommitmentCapability(
        request_builder=_CurrentCycleLLMSemanticCommitmentRequestBuilder(model="gpt-test"),
        transport=transport,
    )
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert capability.last_built_request is not None
    assert completions.recorded_payload is not None
    assert completions.recorded_payload["model"] == "gpt-test"
    assert completions.recorded_payload["response_format"] == {"type": "json_object"}
    assert completions.recorded_payload["reasoning_effort"] == "low"
    assert transport.last_request_payload == completions.recorded_payload
    assert transport.last_raw_response_text == response_text
    assert state.focal_content is not None
    assert state.focal_content.focal_summary == "openai compatible semantic summary"
    assert state.focal_content.salient_tokens == ("workspace-candidate:001", "focus")
    assert len(state.supporting_context) == 1
    assert state.supporting_context[0].summary == "openai compatible supporting summary"


def test_openai_compatible_transport_fails_fast_on_unknown_material_reference() -> None:
    from helios_v2.consciousness.engine import (
        _CurrentCycleLLMSemanticCommitmentRequestBuilder,
        _LLMBackedSemanticCommitmentCapability,
        _OpenAICompatibleSemanticCommitmentTransport,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    response_text = json.dumps(
        {
            "focal_content": {
                "source_material_id": "material:unknown",
                "focal_summary": "bad semantic summary",
                "salient_tokens": ["unknown"],
            },
            "supporting_context": [],
        },
        ensure_ascii=False,
    )
    provider = FakeOpenAIClientProvider(
        client=FakeOpenAIClient(
            chat=FakeOpenAIChat(
                completions=FakeOpenAIChatCompletions(response_text=response_text)
            )
        )
    )
    transport = _OpenAICompatibleSemanticCommitmentTransport(client_provider=provider)
    capability = _LLMBackedSemanticCommitmentCapability(
        request_builder=_CurrentCycleLLMSemanticCommitmentRequestBuilder(model="gpt-test"),
        transport=transport,
    )
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=renderer
        ),
    )

    with pytest.raises(ConsciousnessError, match="must reference a declared current-cycle material"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)


def test_llm_backed_capability_rejects_response_that_changes_owner_selected_focal_material() -> None:
    from helios_v2.consciousness.engine import (
        _CurrentCycleLLMSemanticCommitmentRequestBuilder,
        _LLMBackedSemanticCommitmentCapability,
        _OpenAICompatibleSemanticCommitmentTransport,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    response_text = json.dumps(
        {
            "focal_content": {
                "source_material_id": "material:workspace-candidate:002",
                "focal_summary": "llm tried to switch the focal material",
                "salient_tokens": ["workspace-candidate:002", "switched"],
            },
            "supporting_context": [],
        },
        ensure_ascii=False,
    )
    provider = FakeOpenAIClientProvider(
        client=FakeOpenAIClient(
            chat=FakeOpenAIChat(
                completions=FakeOpenAIChatCompletions(response_text=response_text)
            )
        )
    )
    transport = _OpenAICompatibleSemanticCommitmentTransport(client_provider=provider)
    capability = _LLMBackedSemanticCommitmentCapability(
        request_builder=_CurrentCycleLLMSemanticCommitmentRequestBuilder(model="gpt-test"),
        transport=transport,
    )
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    path = FirstVersionConsciousCommitmentPath(semantic_commitment_renderer=renderer)
    engine = ConsciousnessEngine(config=_build_config(), commitment_path=path)

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "capability_rejected_cycle"
    assert state.focal_content is None
    assert renderer.last_trace is not None
    assert renderer.last_trace.terminal_status.value == "rejected_cycle"
    assert "preserve the owner-selected focal material" in (renderer.last_trace.failure_message or "")
    assert path.last_trace is not None
    assert path.last_trace.terminal_status.value == "render_rejected_cycle"


def test_llm_backed_capability_rejects_response_that_exceeds_supporting_context_cap() -> None:
    from helios_v2.consciousness.engine import (
        _CurrentCycleLLMSemanticCommitmentRequestBuilder,
        _LLMBackedSemanticCommitmentCapability,
        _OpenAICompatibleSemanticCommitmentTransport,
        _OwnerControlledSemanticCommitmentRenderer,
    )

    response_text = json.dumps(
        {
            "focal_content": {
                "source_material_id": "material:workspace-candidate:001",
                "focal_summary": "valid focal summary",
                "salient_tokens": ["workspace-candidate:001", "focus"],
            },
            "supporting_context": [
                {
                    "source_material_id": "material:workspace-candidate:002",
                    "summary": "first supporting summary",
                },
            ],
        },
        ensure_ascii=False,
    )
    provider = FakeOpenAIClientProvider(
        client=FakeOpenAIClient(
            chat=FakeOpenAIChat(
                completions=FakeOpenAIChatCompletions(response_text=response_text)
            )
        )
    )
    transport = _OpenAICompatibleSemanticCommitmentTransport(client_provider=provider)
    capability = _LLMBackedSemanticCommitmentCapability(
        request_builder=_CurrentCycleLLMSemanticCommitmentRequestBuilder(model="gpt-test"),
        transport=transport,
    )
    renderer = _OwnerControlledSemanticCommitmentRenderer(capability=capability)
    path = FirstVersionConsciousCommitmentPath(semantic_commitment_renderer=renderer)
    config = ConsciousnessConfig(
        legal_min_score=0.0,
        legal_max_score=1.0,
        conscious_state_bootstrap_id="consciousness-bootstrap:v1",
        max_supporting_context_items=0,
        mandatory_learned_parameters=(
            "commitment_policy",
            "quiet_state_policy",
            "semantic_shaping_policy",
        ),
    )
    engine = ConsciousnessEngine(config=config, commitment_path=path)

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "capability_rejected_cycle"
    assert state.supporting_context == ()
    assert renderer.last_trace is not None
    assert renderer.last_trace.terminal_status.value == "rejected_cycle"
    assert "supporting-context cap" in (renderer.last_trace.failure_message or "")
    assert path.last_trace is not None
    assert path.last_trace.terminal_status.value == "render_rejected_cycle"


def test_default_openai_client_provider_reads_injected_and_environment_backed_config(monkeypatch) -> None:
    from helios_v2.consciousness.engine import _DefaultOpenAICompatibleClientProvider

    constructor = FakeOpenAIConstructor()
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=constructor))
    monkeypatch.setenv("HELIOS_LLM_API_KEY", "helios-key")
    monkeypatch.setenv("HELIOS_LLM_BASE_URL", "https://helios.example/v1")
    provider = _DefaultOpenAICompatibleClientProvider()

    client = provider.get_client()

    assert client is provider.client
    assert constructor.recorded_api_key == "helios-key"
    assert constructor.recorded_base_url == "https://helios.example/v1"


def test_default_openai_client_provider_fails_explicitly_without_api_key(monkeypatch) -> None:
    from helios_v2.consciousness.engine import (
        _CommitmentCapabilityUnavailable,
        _DefaultOpenAICompatibleClientProvider,
    )

    monkeypatch.delenv("HELIOS_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = _DefaultOpenAICompatibleClientProvider()

    with pytest.raises(_CommitmentCapabilityUnavailable, match="requires an API key"):
        provider.get_client()


def test_first_version_path_can_publish_capability_rejected_cycle_without_fallback() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=RejectingRenderer()
        ),
    )

    state = engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)

    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "capability_rejected_cycle"
    assert state.focal_content is None
    assert state.supporting_context == ()


def test_first_version_path_fails_explicitly_when_capability_is_unavailable() -> None:
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            semantic_commitment_renderer=UnavailableRenderer()
        ),
    )

    with pytest.raises(ConsciousnessError, match="capability is unavailable"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)


def test_engine_rejects_material_sets_that_do_not_cover_full_candidate_set() -> None:
    engine = ConsciousnessEngine(config=_build_config(), commitment_path=RecordingCommitmentPath())
    material_set = ConsciousContentMaterialSet(
        set_id="material-set:bad",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        materials=(
            _build_material(
                candidate_id="workspace-candidate:001",
                memory_candidate_id="memory-candidate:001",
                memory_id="memory:001",
                forced_consolidation=True,
                workspace_score_hint=0.95,
                priority_hint=0.8,
            ),
        ),
        tick_id=7,
    )

    with pytest.raises(ConsciousnessError, match="cover the full current WorkspaceCandidateSet exactly once"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), material_set, tick_id=7)


def test_engine_rejects_path_outputs_that_exceed_supporting_context_cap() -> None:
    engine = ConsciousnessEngine(config=_build_config(), commitment_path=OverContextPath())

    with pytest.raises(ConsciousnessError, match="must not exceed two items"):
        engine.commit_content(_build_candidate_set(), _build_working_state(), _build_material_set(), tick_id=7)


# --- R47: ignition focal selection (global-workspace winner-take-all) ---

from helios_v2.consciousness import IgnitionFocalSelectionPolicy  # noqa: E402


def _two_retained_working_state() -> WorkingStateSnapshot:
    return WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=("workspace-candidate:001", "workspace-candidate:002"),
        tick_id=7,
    )


def _ignition_engine() -> ConsciousnessEngine:
    return ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(
            focal_selection_policy=IgnitionFocalSelectionPolicy()
        ),
    )


def test_ignition_commits_highest_scoring_candidate_on_multi_retained_state() -> None:
    # The R46 bottleneck retains >1 candidate. Ignition must COMMIT the top-scored one, not
    # declare semantic_conflict_unresolved (the count-based shim behavior).
    engine = _ignition_engine()
    state = engine.commit_content(
        _build_candidate_set(),
        _two_retained_working_state(),
        _build_material_set(),
        tick_id=7,
    )

    assert state.commit_status == "committed"
    assert state.no_commit_reason is None
    assert state.focal_content is not None
    # candidate:001 has workspace_score_hint 0.95 > candidate:002's 0.6, so it ignites.
    assert state.focal_content.source_workspace_candidate_id == "workspace-candidate:001"
    # The loser becomes supporting context (bounded by max_supporting_context_items=2).
    assert len(state.supporting_context) == 1
    assert state.supporting_context[0].source_workspace_candidate_id == "workspace-candidate:002"


def test_ignition_tie_break_is_deterministic_by_candidate_id() -> None:
    policy = IgnitionFocalSelectionPolicy()
    candidate_set = _build_candidate_set()
    working_state = _two_retained_working_state()
    # Equal scores on both materials: smaller source_workspace_candidate_id ignites.
    material_map = {
        "workspace-candidate:001": _build_material(
            "workspace-candidate:001", "memory-candidate:001", "memory:001", True, 0.7, 0.8
        ),
        "workspace-candidate:002": _build_material(
            "workspace-candidate:002", "memory-candidate:002", "memory:002", False, 0.7, 0.5
        ),
    }
    outcome = policy.decide(candidate_set, working_state, material_map)
    assert outcome.commit_status == "committed"
    assert outcome.focal_material.source_workspace_candidate_id == "workspace-candidate:001"


def test_ignition_zero_retained_is_insufficient_commitment_signal() -> None:
    policy = IgnitionFocalSelectionPolicy()
    working_state = WorkingStateSnapshot(
        state_id="working-state:001",
        source_candidate_set_id="workspace-set:001",
        retained_candidate_ids=(),
        tick_id=7,
    )
    outcome = policy.decide(_build_candidate_set(), working_state, {})
    assert outcome.commit_status == "no_commit"
    assert outcome.no_commit_reason == "insufficient_commitment_signal"


def test_ignition_empty_focal_summary_is_context_not_reportable() -> None:
    policy = IgnitionFocalSelectionPolicy()
    working_state = _build_working_state()  # retains only candidate:001
    blank_material = ConsciousContentMaterial(
        material_id="material:workspace-candidate:001",
        source_workspace_candidate_id="workspace-candidate:001",
        source_memory_candidate_id="memory-candidate:001",
        source_memory_id="memory:001",
        source_feeling_state_id="feeling-state:001",
        content_kind="situational-summary",
        material_summary="   ",  # empty after normalization
        summary_ref="summary:x",
        context_ref="context:x",
        salient_tokens=("x",),
        affect_tag=_build_feeling(),
        forced_consolidation=True,
        workspace_score_hint=0.95,
        priority_hint=0.8,
    )
    outcome = policy.decide(
        _build_candidate_set(), working_state, {"workspace-candidate:001": blank_material}
    )
    assert outcome.commit_status == "no_commit"
    assert outcome.no_commit_reason == "context_not_reportable"


def test_ignition_is_deterministic() -> None:
    engine_a = _ignition_engine()
    engine_b = _ignition_engine()
    args = (_build_candidate_set(), _two_retained_working_state(), _build_material_set())
    state_a = engine_a.commit_content(*args, tick_id=7)
    state_b = engine_b.commit_content(*args, tick_id=7)
    assert state_a.commit_status == state_b.commit_status
    assert state_a.focal_content.source_workspace_candidate_id == (
        state_b.focal_content.source_workspace_candidate_id
    )


def test_count_based_default_still_no_commits_on_multi_retained_state() -> None:
    # Regression guard: the default (non-ignition) path keeps the count-based conflict behavior.
    engine = ConsciousnessEngine(
        config=_build_config(),
        commitment_path=FirstVersionConsciousCommitmentPath(),
    )
    state = engine.commit_content(
        _build_candidate_set(),
        _two_retained_working_state(),
        _build_material_set(),
        tick_id=7,
    )
    assert state.commit_status == "no_commit"
    assert state.no_commit_reason == "semantic_conflict_unresolved"
