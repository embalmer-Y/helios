from __future__ import annotations

import pytest

from helios_v2.experience_writeback import (
    ExperienceWritebackConfig,
    ExperienceWritebackEngine,
    ExperienceWritebackError,
    ExperienceWritebackRequest,
    FirstVersionExperienceWritebackPath,
)


def _build_config() -> ExperienceWritebackConfig:
    return ExperienceWritebackConfig(
        legal_min_priority=0.0,
        legal_max_priority=1.0,
        writeback_bootstrap_id="experience-writeback-bootstrap:v1",
        mandatory_learned_parameters=(
            "continuity_classification_policy",
            "consolidation_priority_policy",
            "autobiographical_salience_policy",
        ),
    )


def _request(
    *,
    source_outcome_kind: str,
    source_outcome_status: str,
    outcome_class: str,
) -> ExperienceWritebackRequest:
    provenance = {
        "source_request_id": f"{source_outcome_kind}-request:001",
        "proposal_id": "proposal:001",
    }
    if source_outcome_kind == "planner_bridge":
        provenance["decision_id"] = "decision:001"
    else:
        provenance["revision_id"] = "revision:001"
        provenance["origin_thought_id"] = "thought:001"
    return ExperienceWritebackRequest(
        request_id=f"experience-writeback-request:{source_outcome_kind}:{outcome_class}",
        source_outcome_kind=source_outcome_kind,
        source_outcome_id=f"{source_outcome_kind}-result:001",
        source_outcome_status=source_outcome_status,
        outcome_class=outcome_class,
        source_provenance=provenance,
        requested_effect_summary="continuity-relevant effect was requested",
        applied_effect_summary="continuity-relevant effect summary was published",
        reason_trace=("continuity owner preserved the upstream reason",),
        tick_id=1,
    )


def test_engine_publishes_written_external_action_with_candidates() -> None:
    engine = ExperienceWritebackEngine(
        config=_build_config(),
        writeback_path=FirstVersionExperienceWritebackPath(),
    )
    request = _request(
        source_outcome_kind="planner_bridge",
        source_outcome_status="executed",
        outcome_class="world_changed",
    )

    result = engine.write_experience(request)
    publish_op = engine.build_publish_experience_writeback_op(result)
    candidate_ops = tuple(
        engine.build_publish_consolidation_candidate_op(result, candidate)
        for candidate in result.consolidation_candidates
    )

    assert result.status == "written"
    assert result.continuity_packet.continuity_kind == "external_action"
    assert len(result.consolidation_candidates) == 3
    assert publish_op.continuity_kind == "external_action"
    assert {op.target_memory_family for op in candidate_ops} == {
        "episodic",
        "autobiographical",
        "semantic",
    }


@pytest.mark.parametrize(
    ("outcome_class", "source_outcome_status", "expected_status", "expected_kind"),
    (
        ("world_blocked", "policy_rejected", "written_blocked_outcome", "blocked_action"),
        ("world_failed", "execution_failed", "written_unresolved_outcome", "failed_action"),
        (
            "self_blocked",
            "rejected",
            "written_unresolved_outcome",
            "blocked_identity_change",
        ),
    ),
)
def test_engine_preserves_blocked_or_failed_continuity_paths(
    outcome_class: str,
    source_outcome_status: str,
    expected_status: str,
    expected_kind: str,
) -> None:
    engine = ExperienceWritebackEngine(
        config=_build_config(),
        writeback_path=FirstVersionExperienceWritebackPath(),
    )
    request = _request(
        source_outcome_kind="planner_bridge" if outcome_class.startswith("world") else "identity_governance",
        source_outcome_status=source_outcome_status,
        outcome_class=outcome_class,
    )

    result = engine.write_experience(request)

    assert result.status == expected_status
    assert result.continuity_packet.continuity_kind == expected_kind


def test_engine_publishes_identity_change_distinct_from_world_outcomes() -> None:
    engine = ExperienceWritebackEngine(
        config=_build_config(),
        writeback_path=FirstVersionExperienceWritebackPath(),
    )
    request = _request(
        source_outcome_kind="identity_governance",
        source_outcome_status="accepted",
        outcome_class="self_changed",
    )

    result = engine.write_experience(request)

    assert result.status == "written_identity_change"
    assert result.continuity_packet.continuity_kind == "identity_change"
    assert result.consolidation_candidates[1].target_memory_family == "autobiographical"
    assert result.consolidation_candidates[1].priority_hint == 0.92


def test_engine_requires_explicit_writeback_capability() -> None:
    engine = ExperienceWritebackEngine(
        config=_build_config(),
        writeback_path=None,
    )

    with pytest.raises(
        ExperienceWritebackError,
        match="explicit writeback capability",
    ):
        engine.write_experience(
            _request(
                source_outcome_kind="planner_bridge",
                source_outcome_status="executed",
                outcome_class="world_changed",
            )
        )