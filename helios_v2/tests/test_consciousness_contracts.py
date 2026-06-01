from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from helios_v2.consciousness import (
    ConsciousContentMaterial,
    ConsciousContentMaterialSet,
    ConsciousState,
    ConsciousnessConfig,
    ConsciousnessError,
    ReportableConsciousContent,
    SupportingContextItem,
)
from helios_v2.feeling import InteroceptiveFeelingVector


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


def _build_material(candidate_id: str = "workspace-candidate:001") -> ConsciousContentMaterial:
    return ConsciousContentMaterial(
        material_id=f"material:{candidate_id}",
        source_workspace_candidate_id=candidate_id,
        source_memory_candidate_id="memory-candidate:001",
        source_memory_id="memory:001",
        source_feeling_state_id="feeling-state:001",
        content_kind="situational-summary",
        material_summary="situational-summary: hello, novelty",
        summary_ref="summary:001",
        context_ref="context:001",
        salient_tokens=("hello", "novelty"),
        affect_tag=_build_feeling(),
        forced_consolidation=True,
        workspace_score_hint=0.9,
        priority_hint=0.8,
    )


def _build_focal_content() -> ReportableConsciousContent:
    material = _build_material()
    return ReportableConsciousContent(
        content_id="conscious-content:001",
        source_material_id=material.material_id,
        source_workspace_candidate_id=material.source_workspace_candidate_id,
        source_memory_candidate_id=material.source_memory_candidate_id,
        source_feeling_state_id=material.source_feeling_state_id,
        content_kind=material.content_kind,
        focal_summary="I am focused on the novel greeting in the current interaction.",
        affect_trace=material.affect_tag,
        salient_tokens=material.salient_tokens,
        tick_id=5,
    )


def test_conscious_material_is_immutable_and_range_checked() -> None:
    material = _build_material()

    with pytest.raises(FrozenInstanceError):
        material.material_summary = "changed"

    with pytest.raises(ConsciousnessError, match="workspace_score_hint"):
        ConsciousContentMaterial(
            material_id="material:bad",
            source_workspace_candidate_id="workspace-candidate:002",
            source_memory_candidate_id="memory-candidate:001",
            source_memory_id="memory:001",
            source_feeling_state_id="feeling-state:001",
            content_kind="situational-summary",
            material_summary="bad",
            summary_ref=None,
            context_ref=None,
            salient_tokens=("hello",),
            affect_tag=_build_feeling(),
            forced_consolidation=False,
            workspace_score_hint=1.2,
            priority_hint=0.2,
        )


def test_material_set_requires_unique_full_material_entries() -> None:
    material = _build_material()
    duplicate_candidate_material = ConsciousContentMaterial(
        material_id="material:workspace-candidate:001:duplicate",
        source_workspace_candidate_id="workspace-candidate:001",
        source_memory_candidate_id="memory-candidate:002",
        source_memory_id="memory:002",
        source_feeling_state_id="feeling-state:001",
        content_kind="situational-summary",
        material_summary="situational-summary: duplicate candidate",
        summary_ref="summary:002",
        context_ref="context:002",
        salient_tokens=("duplicate",),
        affect_tag=_build_feeling(),
        forced_consolidation=False,
        workspace_score_hint=0.4,
        priority_hint=0.3,
    )
    material_set = ConsciousContentMaterialSet(
        set_id="material-set:001",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        materials=(material,),
        tick_id=5,
    )

    assert material_set.materials[0].source_workspace_candidate_id == "workspace-candidate:001"

    with pytest.raises(ConsciousnessError, match="duplicate source_workspace_candidate_id"):
        ConsciousContentMaterialSet(
            set_id="material-set:002",
            source_workspace_candidate_set_id="workspace-set:001",
            source_working_state_id="working-state:001",
            materials=(material, duplicate_candidate_material),
            tick_id=5,
        )


def test_conscious_state_enforces_committed_payload_and_support_cap() -> None:
    content = _build_focal_content()
    state = ConsciousState(
        state_id="conscious-state:001",
        commit_status="committed",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        focal_content=content,
        supporting_context=(
            SupportingContextItem(
                context_item_id="context:001",
                source_material_id="material:workspace-candidate:002",
                source_workspace_candidate_id="workspace-candidate:002",
                content_kind="episodic",
                summary="Related prior context remains active.",
                affect_trace=_build_feeling(),
            ),
        ),
        no_commit_reason=None,
        tick_id=5,
    )

    assert state.focal_content is not None

    with pytest.raises(ConsciousnessError, match="must not exceed two items"):
        ConsciousState(
            state_id="conscious-state:002",
            commit_status="committed",
            source_workspace_candidate_set_id="workspace-set:001",
            source_working_state_id="working-state:001",
            focal_content=content,
            supporting_context=(
                SupportingContextItem(
                    context_item_id="context:001",
                    source_material_id="material:1",
                    source_workspace_candidate_id="workspace-candidate:101",
                    content_kind="episodic",
                    summary="one",
                    affect_trace=_build_feeling(),
                ),
                SupportingContextItem(
                    context_item_id="context:002",
                    source_material_id="material:2",
                    source_workspace_candidate_id="workspace-candidate:102",
                    content_kind="episodic",
                    summary="two",
                    affect_trace=_build_feeling(),
                ),
                SupportingContextItem(
                    context_item_id="context:003",
                    source_material_id="material:3",
                    source_workspace_candidate_id="workspace-candidate:103",
                    content_kind="episodic",
                    summary="three",
                    affect_trace=_build_feeling(),
                ),
            ),
            no_commit_reason=None,
            tick_id=5,
        )


def test_no_commit_state_requires_fixed_reason_taxonomy() -> None:
    state = ConsciousState(
        state_id="conscious-state:003",
        commit_status="no_commit",
        source_workspace_candidate_set_id="workspace-set:001",
        source_working_state_id="working-state:001",
        focal_content=None,
        supporting_context=(),
        no_commit_reason="semantic_conflict_unresolved",
        tick_id=5,
    )

    assert state.no_commit_reason == "semantic_conflict_unresolved"

    with pytest.raises(ConsciousnessError, match="fixed no_commit taxonomy"):
        ConsciousState(
            state_id="conscious-state:004",
            commit_status="no_commit",
            source_workspace_candidate_set_id="workspace-set:001",
            source_working_state_id="working-state:001",
            focal_content=None,
            supporting_context=(),
            no_commit_reason="free_text_reason",  # type: ignore[arg-type]
            tick_id=5,
        )


def test_config_accepts_only_confirmed_learned_parameter_categories() -> None:
    config = _build_config()

    assert config.max_supporting_context_items == 2

    with pytest.raises(ConsciousnessError, match="mandatory learned-parameter categories"):
        ConsciousnessConfig(
            legal_min_score=0.0,
            legal_max_score=1.0,
            conscious_state_bootstrap_id="consciousness-bootstrap:v1",
            max_supporting_context_items=2,
            mandatory_learned_parameters=(
                "commitment_policy",
                "quiet_state_policy",
            ),
        )