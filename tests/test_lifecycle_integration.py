"""Focused integration tests for phase-26 lifecycle wiring."""

from __future__ import annotations

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