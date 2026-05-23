"""Focused tests for registry-backed runtime behavior loading."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from behavior_registry import RuntimeBehaviorCatalog
from helios_io.action_models import BehaviorSpec
from regulation import RegulationEngine


def test_runtime_catalog_bootstraps_registry_and_filters_policy_domain(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    catalog = RuntimeBehaviorCatalog.from_db_path(db_path)

    imported = catalog.ensure_bootstrap_behaviors()
    passive = catalog.snapshot_by_name(policy_domain="interaction_passive")
    active = {profile.action_type for profile in catalog.list_regulation_behaviors()}
    sources = catalog.registry.list_behavior_sources(source_kind="bootstrap")

    assert imported >= 1
    assert "reply_message" in passive
    assert "reply_message" not in active
    assert "speak_share" in active
    assert "browse" in active
    assert any(source.behavior_id == "bootstrap.reply_message" for source in sources)


def test_regulation_engine_candidates_follow_registry_status(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    catalog = RuntimeBehaviorCatalog.from_db_path(db_path)
    catalog.ensure_bootstrap_behaviors()

    browse = catalog.get_behavior("browse")
    assert browse is not None
    browse.status = "draft"
    catalog.registry.upsert_behavior(browse)
    catalog.refresh()

    engine = RegulationEngine(data_dir=str(tmp_path), behavior_catalog=catalog)
    candidates = engine._query_candidates("SEEKING", deviation=0.7, hour_of_day=14)

    candidate_names = {candidate.action_type for candidate in candidates}
    assert "browse" not in candidate_names
    assert "search" in candidate_names


def test_runtime_catalog_hides_proposed_behavior_until_approved(tmp_path):
    db_path = tmp_path / "behavior_registry.sqlite3"
    catalog = RuntimeBehaviorCatalog.from_db_path(db_path)
    catalog.ensure_bootstrap_behaviors()

    proposed = catalog.propose_behavior(
        BehaviorSpec(
            behavior_id="proposal.compose_poem",
            name="compose_poem",
            display_name="Compose Poem",
            description="Compose a short poem for the user.",
            category="social",
            execution_mode="channel",
            allowed_channel_ids=["qq"],
            required_capabilities=["send"],
            supported_modalities=["text"],
        ),
        source_summary="LLM proposed a poem behavior",
    )

    assert proposed.review_state == "pending"
    assert "compose_poem" not in catalog.snapshot_by_name()

    approved = catalog.approve_behavior("compose_poem", approved_by="tester", review_note="safe")

    assert approved is not None
    assert approved.review_state == "approved"
    assert approved.status == "active"
    assert "compose_poem" in catalog.snapshot_by_name()