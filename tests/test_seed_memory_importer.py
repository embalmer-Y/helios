"""Tests for seed autobiographical memory importing."""

from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalStore, SeedMemoryImporter


class TestSeedMemoryImporter:
    def test_parse_sections_extracts_markdown_sections(self, tmp_path):
        store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
        importer = SeedMemoryImporter(store, system_start_time=time.time())

        sections = importer._parse_sections("# First\nhello\n\n## Second\nworld")

        assert len(sections) == 2
        assert sections[0]["heading"] == "First"
        assert sections[0]["text"] == "hello"
        assert sections[1]["heading"] == "Second"
        assert sections[1]["text"] == "world"

    def test_import_document_creates_predated_source_tagged_moments(self, tmp_path):
        store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
        system_start = time.time()
        importer = SeedMemoryImporter(store, system_start_time=system_start)

        seeds = importer.import_document(
            "# Memory A\nI felt warm and cared for.\n\n# Memory B\nI was afraid of losing contact.",
            source_label="seed_profile",
        )

        assert len(seeds) == 2
        assert all(seed.timestamp < system_start for seed in seeds)
        assert all(moment.source == "seed_profile" for moment in store.moments)
        assert importer.verify_seed_integrity("seed_profile") is True

    def test_seed_moments_survive_flush_and_reload(self, tmp_path):
        path = tmp_path / "autobio.jsonl"
        store = AutobiographicalStore(str(path), auto_flush=False)
        importer = SeedMemoryImporter(store, system_start_time=time.time())

        importer.import_document("# Origin\nA warm shared memory.", source_label="seed_origin")
        store.flush()

        reloaded = AutobiographicalStore(str(path), auto_flush=False)

        assert len(reloaded.moments) == 1
        assert reloaded.moments[0].source == "seed_origin"
        assert reloaded.moments[0].narrative == "A warm shared memory."

    def test_query_related_can_return_seed_memories(self, tmp_path):
        store = AutobiographicalStore(str(tmp_path / "autobio.jsonl"), auto_flush=False)
        importer = SeedMemoryImporter(store, system_start_time=time.time())

        importer.import_document("# Shared Story\nWe discovered something beautiful together.", source_label="seed_story")
        related = store.query_related(topic_text="beautiful", user_id="", history_texts=[], limit=3)

        assert len(related) == 1
        assert related[0].source == "seed_story"