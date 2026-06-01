"""Property-based tests for seed autobiographical memory importing.

# Feature: helios-architecture-enhancement
# Property 38: Seed Memory Creation with Pre-dated Timestamps and Source Tags
# Property 39: Seed Memory Equivalence in Persistence and Retrieval

**Validates: Requirements 35.1, 35.2, 35.3, 35.5**
"""

from __future__ import annotations

import os
import re
import string
import sys
import time
import uuid
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import lists, text


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from memory import AutobiographicalStore, SeedMemoryImporter


SAFE_TEXT_ALPHABET = string.ascii_letters + string.digits + " _-"


def _create_unique_store_dir(tmp_path):
    store_dir = tmp_path / f"seed_{uuid.uuid4().hex}"
    store_dir.mkdir(parents=True, exist_ok=True)
    return store_dir


def _build_markdown(section_texts: list[str]) -> str:
    parts = []
    for index, section in enumerate(section_texts, start=1):
        parts.append(f"# Section {index}\n{section}")
    return "\n\n".join(parts)


class TestProperty38SeedMemoryCreation:
    """Property 38: seed creation keeps timestamps pre-dated and source-tagged."""

    @given(
        section_texts=lists(text(alphabet=SAFE_TEXT_ALPHABET, min_size=1, max_size=80), min_size=1, max_size=8),
        source_label=text(alphabet=SAFE_TEXT_ALPHABET, min_size=1, max_size=30),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    def test_import_document_creates_predated_source_tagged_moments(self, section_texts: list[str], source_label: str, tmp_path):
        store_dir = _create_unique_store_dir(tmp_path)
        path = str(store_dir / "autobio.jsonl")
        system_start = time.time()
        store = AutobiographicalStore(path, auto_flush=False)
        importer = SeedMemoryImporter(store, system_start_time=system_start)

        markdown = _build_markdown(section_texts)
        seeds = importer.import_document(markdown, source_label=source_label)

        assert len(seeds) == len(section_texts)
        assert len(store.moments) == len(section_texts)
        assert all(seed.timestamp < system_start for seed in seeds)
        assert all(seed.source == source_label for seed in seeds)
        timestamps = [seed.timestamp for seed in seeds]
        assert timestamps == sorted(timestamps)
        assert importer.verify_seed_integrity(source_label) is True


class TestProperty39SeedMemoryEquivalence:
    """Property 39: seed memories persist and retrieve like organic moments."""

    @given(
        topic=text(alphabet=SAFE_TEXT_ALPHABET, min_size=1, max_size=20),
        source_label=text(alphabet=SAFE_TEXT_ALPHABET, min_size=1, max_size=20),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=60000)
    def test_seed_persistence_and_retrieval_match_organic_lookup(self, topic: str, source_label: str, tmp_path):
        store_dir = _create_unique_store_dir(tmp_path)
        path = Path(store_dir / "autobio.jsonl")
        system_start = time.time()
        store = AutobiographicalStore(str(path), auto_flush=False)
        importer = SeedMemoryImporter(store, system_start_time=system_start)

        safe_topic = re.sub(r"\s+", " ", topic).strip()
        if not safe_topic:
            safe_topic = "topic"
        safe_source = re.sub(r"\s+", "_", source_label).strip("_") or "seed_source"
        importer.import_document(f"# Seed\nshared {safe_topic} memory", source_label=safe_source)
        store.record(
            panksepp={"CARE": 0.7},
            valence=0.5,
            arousal=0.4,
            dominant="CARE",
            phi=0.3,
            narrative=f"organic {safe_topic} memory",
        )
        store.flush()

        reloaded = AutobiographicalStore(str(path), auto_flush=False)
        related = reloaded.query_related(topic_text=safe_topic, limit=5)
        narratives = {moment.narrative for moment in related}

        assert f"shared {safe_topic} memory" in narratives
        assert f"organic {safe_topic} memory" in narratives
        assert any(moment.source == safe_source for moment in reloaded.moments)
