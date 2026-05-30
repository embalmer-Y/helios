"""Focused tests for the structured RegulationPolicy boundary."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from behavior_registry import RuntimeBehaviorCatalog
from helios_io.action_models import ExecutionFeedback
from regulation import RegulationEngine, RegulationPolicy
from personality_projection import build_personality_projection


def test_regulation_policy_assess_returns_structured_selection(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    policy = RegulationPolicy(behavior_catalog=catalog)
    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)

    signals = policy.collect_signals(
        panksepp={"PANIC": 0.82, "CARE": 0.18, "SEEKING": 0.12},
        valence=-0.35,
        hour_of_day=14,
        drive_urgency=0.7,
        drive_dominant="social",
        recent_execution_outcomes=[{"action": "speak_missing", "success": True}],
    )
    assessment = policy.assess(
        signals,
        memories=engine.memories,
        last_executed=engine._last_executed,
    )

    assert assessment.wants_regulation
    assert assessment.selected_action
    assert assessment.selected_score >= 0.15
    assert assessment.candidates
    assert assessment.drive_dominant == "social"


def test_regulation_policy_propose_emits_action_proposal(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)

    assessment = engine.evaluate_regulation(
        panksepp={"SEEKING": 0.84, "PLAY": 0.22},
        valence=0.12,
        hour_of_day=15,
        drive_urgency=0.8,
        drive_dominant="curiosity",
    )
    proposals = engine.generate_action_proposals(
        panksepp={"SEEKING": 0.84, "PLAY": 0.22},
        valence=0.12,
        hour_of_day=15,
        tick=41,
        candidate_channels=["qq", "tts"],
        params={"tick": 41},
        drive_urgency=0.8,
        drive_dominant="curiosity",
    )

    assert assessment.wants_regulation
    assert proposals
    assert proposals[0].source_module == "regulation_policy"
    assert proposals[0].created_at_tick == 41
    assert proposals[0].behavior_name == assessment.selected_action
    assert proposals[0].provenance["session_kind"] == "proactive"
    assert proposals[0].provenance["dominant_disposition"] in {"externalize", "explore", "reflect", "defer"}
    assert any(item.startswith("drive:") for item in proposals[0].provenance["trigger_sources"])


def test_regulation_policy_provenance_includes_personality_influence_trace(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)
    projection = build_personality_projection(
        traits={
            "openness": 1.2,
            "extraversion": 1.2,
            "agreeableness": 1.0,
            "neuroticism": 0.9,
            "conscientiousness": 1.0,
        }
    )

    proposals = engine.generate_action_proposals(
        panksepp={"SEEKING": 0.84, "PLAY": 0.22},
        valence=0.12,
        hour_of_day=15,
        tick=41,
        candidate_channels=["qq", "tts"],
        params={"tick": 41},
        drive_urgency=0.8,
        drive_dominant="curiosity",
        personality_projection=projection,
    )

    assert proposals
    trace = proposals[0].provenance["personality_influence_trace"]
    assert trace["behavior_bias"] == proposals[0].score_bundle["personality_behavior_bias"]
    assert trace["novelty_bias"] >= 0.0
    assert "ranked_channels" in trace


def test_regulation_policy_recent_failure_penalizes_candidate(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)

    baseline = engine.evaluate_regulation(
        panksepp={"SEEKING": 0.88},
        valence=0.1,
        hour_of_day=16,
        drive_urgency=0.7,
        drive_dominant="curiosity",
    )
    penalized = engine.evaluate_regulation(
        panksepp={"SEEKING": 0.88},
        valence=0.1,
        hour_of_day=16,
        drive_urgency=0.7,
        drive_dominant="curiosity",
        recent_execution_outcomes=[{"action": baseline.selected_action, "success": False}],
    )

    assert baseline.wants_regulation
    assert penalized.wants_regulation
    baseline_score = next(candidate.final_score for candidate in baseline.candidates if candidate.action_type == baseline.selected_action)
    penalized_score = next(candidate.final_score for candidate in penalized.candidates if candidate.action_type == baseline.selected_action)
    assert penalized_score < baseline_score


def test_regulation_engine_uses_recorded_execution_feedback_by_default(tmp_path):
    catalog = RuntimeBehaviorCatalog.from_db_path(tmp_path / "behavior_registry.sqlite3")
    catalog.ensure_bootstrap_behaviors()
    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)

    engine.on_execution_feedback(
        ExecutionFeedback(
            proposal_id="proposal::1",
            decision_id="decision::1",
            behavior_name="browse",
            success=False,
            channel_id="",
            op_name="internal_execute",
            result_details={"tick": 8},
            observed_at_tick=8,
            observed_at_ts=100.0,
        )
    )

    assessment = engine.evaluate_regulation(
        panksepp={"SEEKING": 0.88},
        valence=0.1,
        hour_of_day=16,
        drive_urgency=0.7,
        drive_dominant="curiosity",
    )
    comparison_signals = engine.policy.collect_signals(
        panksepp={"SEEKING": 0.88},
        valence=0.1,
        hour_of_day=16,
        drive_urgency=0.7,
        drive_dominant="curiosity",
        recent_execution_outcomes=[],
    )
    baseline = engine.policy.assess(
        comparison_signals,
        memories=engine.memories,
        last_executed=engine._last_executed,
    )

    browse_candidate = next(candidate for candidate in assessment.candidates if candidate.action_type == "browse")
    baseline_browse = next(candidate for candidate in baseline.candidates if candidate.action_type == "browse")

    assert browse_candidate.final_score < baseline_browse.final_score