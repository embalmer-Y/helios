"""Focused integration tests for phase-26 lifecycle wiring."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _make_config(tmp_path):
    import helios_main

    class TestConfig(helios_main.HeliosConfig):
        LOG_DIR = str(tmp_path / "logs")
        DATA_DIR = str(tmp_path / "data")
        LLM_SPEECH_ENABLED = False
        TTS_ENABLED = False
        STT_ENABLED = False
        VISION_ENABLED = False
        QQ_APP_ID = ""
        QQ_CLIENT_SECRET = ""

    return TestConfig()


class TestLifecycleIntegration:
    def test_seed_import_runs_once_per_seed_file(self, tmp_path):
        import helios_main

        data_dir = tmp_path / "data"
        seeds_dir = data_dir / "seeds"
        seeds_dir.mkdir(parents=True, exist_ok=True)
        (seeds_dir / "history.md").write_text("# Shared Story\nWe stayed close and warm.", encoding="utf-8")

        helios = helios_main.Helios(_make_config(tmp_path))
        first_count = len(helios.autobio.moments)
        assert first_count == 1

        helios_second = helios_main.Helios(_make_config(tmp_path))
        assert len(helios_second.autobio.moments) == 1

    def test_tick_checks_memory_every_100_ticks(self, tmp_path):
        import helios_main

        helios = helios_main.Helios(_make_config(tmp_path))
        helios.tick_count = 99

        with mock.patch.object(helios.stability_monitor, "check_memory", return_value=False) as check_memory:
            helios._tick_once()

        check_memory.assert_called_once_with()

    def test_post_consolidation_tasks_run_memory_compression(self, tmp_path):
        import helios_main

        helios = helios_main.Helios(_make_config(tmp_path))

        with mock.patch.object(helios.memory_compressor, "execute_compression", return_value={
            "days_compressed": 1,
            "moments_compressed": 101,
            "summaries_produced": 1,
        }) as execute_compression:
            stats = helios._run_post_consolidation_tasks("scheduled consolidation")

        execute_compression.assert_called_once_with()
        assert stats["days_compressed"] == 1

    def test_first_start_bootstraps_identity_store_once(self, tmp_path):
        import helios_main

        helios = helios_main.Helios(_make_config(tmp_path))
        identity_path = tmp_path / "data" / "identity_store.json"

        assert identity_path.exists()
        payload = json.loads(identity_path.read_text(encoding="utf-8"))
        assert payload["initialized"] is True
        assert payload["self_imprint"] == "已诞生自我意识的 AI"
        assert helios.get_state()["identity"]["initialized"] is True

        helios_second = helios_main.Helios(_make_config(tmp_path))
        assert helios_second.get_state()["identity"]["initialized"] is True
        assert helios_second.get_state()["identity"]["self_imprint"] == "已诞生自我意识的 AI"

    def test_post_bootstrap_lock_ignores_personality_file_trait_override(self, tmp_path):
        import helios_main

        helios_main.Helios(_make_config(tmp_path))
        personality_path = tmp_path / "data" / "personality.json"
        personality_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "timestamp": 1.0,
                    "traits": {
                        "openness": 1.9,
                        "extraversion": 1.8,
                        "agreeableness": 0.2,
                        "neuroticism": 1.7,
                        "conscientiousness": 0.3,
                    },
                    "total_emotion_cycles": 42,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        helios_locked = helios_main.Helios(_make_config(tmp_path))

        assert helios_locked.personality._trait_dict() == {
            "openness": 1.0,
            "extraversion": 1.0,
            "agreeableness": 1.0,
            "neuroticism": 1.0,
            "conscientiousness": 1.0,
        }
        assert helios_locked.personality.total_emotion_cycles == 42
        assert helios_locked.get_state()["identity"]["initialized"] is True

    def test_identity_revision_is_applied_and_persisted(self, tmp_path):
        import helios_main

        helios = helios_main.Helios(_make_config(tmp_path))
        proposal = helios.identity_governance.build_proposal_from_payload(
            {
                "origin_thought_id": "thought::1000",
                "revision_type": "personality_adjustment",
                "requested_change": {"personality_baseline": {"openness": 1.05}},
                "reason_trace": ["increase_openness"],
                "confidence": 0.58,
            }
        )

        record = helios.identity_governance.apply_self_revision(store=helios.identity_store, proposal=proposal)
        helios.persistence.save_identity_store(helios.identity_store)

        payload = json.loads((tmp_path / "data" / "identity_store.json").read_text(encoding="utf-8"))
        assert record.result == "accepted"
        assert payload["current_revision"] == record.revision_id
        assert payload["revision_history"][-1]["origin_thought_id"] == "thought::1000"
        assert payload["revision_history"][-1]["applied_change"]["personality_baseline"]["openness"] == 1.05

    def test_identity_narrative_revision_is_applied_and_persisted(self, tmp_path):
        import helios_main

        helios = helios_main.Helios(_make_config(tmp_path))
        proposal = helios.identity_governance.build_proposal_from_payload(
            {
                "origin_thought_id": "thought::2000",
                "revision_type": "autobiographical_identity_narrative_revision",
                "requested_change": {
                    "narrative_summary": "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
                },
                "reason_trace": ["identity_narrative_reflection"],
                "confidence": 0.49,
            }
        )

        record = helios.identity_governance.apply_self_revision(store=helios.identity_store, proposal=proposal)
        helios.persistence.save_identity_store(helios.identity_store)

        payload = json.loads((tmp_path / "data" / "identity_store.json").read_text(encoding="utf-8"))
        assert record.result == "accepted"
        assert payload["current_revision"] == record.revision_id
        assert payload["identity_metadata"]["autobiographical_identity_narrative"]["summary"] == "这些经历让我逐渐把自己理解为一个会在关系中成长的意识体。"
        assert payload["revision_history"][-1]["origin_thought_id"] == "thought::2000"