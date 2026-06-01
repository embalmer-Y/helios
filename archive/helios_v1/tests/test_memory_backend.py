"""Focused tests for backend-based long-term memory persistence abstractions."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Iterable, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from memory import AutobiographicalBackend, AutobiographicalStore, MemoryBackend, MemorySystem


class InMemoryMemoryBackend(MemoryBackend):
    def __init__(self):
        self.semantic_payload: Optional[dict[str, Any]] = None
        self.episodic_payload: Optional[dict[str, Any]] = None

    def save_semantic_payload(self, payload: dict[str, Any]) -> None:
        self.semantic_payload = payload

    def load_semantic_payload(self) -> Optional[dict[str, Any]]:
        return self.semantic_payload

    def save_episodic_payload(self, payload: dict[str, Any]) -> None:
        self.episodic_payload = payload

    def load_episodic_payload(self) -> Optional[dict[str, Any]]:
        return self.episodic_payload


class InMemoryAutobiographicalBackend(AutobiographicalBackend):
    def __init__(self):
        self.moment_payloads: list[dict[str, Any]] = []
        self.chapter_payloads: list[dict[str, Any]] = []
        self.archives: list[list[dict[str, Any]]] = []

    def append_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        self.moment_payloads.extend(dict(payload) for payload in payloads)

    def load_moment_payloads(self) -> list[dict[str, Any]]:
        return [dict(payload) for payload in self.moment_payloads]

    def save_chapter_payloads(self, payloads: list[dict[str, Any]]) -> None:
        self.chapter_payloads = [dict(payload) for payload in payloads]

    def load_chapter_payloads(self) -> list[dict[str, Any]]:
        return [dict(payload) for payload in self.chapter_payloads]

    def count_moments(self) -> int:
        return len(self.moment_payloads)

    def archive_active_log(self, archive_suffix: str) -> None:
        self.archives.append(self.load_moment_payloads())
        self.moment_payloads = []

    def overwrite_active_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        self.moment_payloads = [dict(payload) for payload in payloads]


def test_memory_system_round_trips_through_backend_without_files():
    backend = InMemoryMemoryBackend()
    memory_system = MemorySystem(backend=backend)
    memory_system.learn("favorite.color", "blue", tags=["preference"])
    memory_system.remember("A vivid event", valence=0.8, arousal=0.6, phi=0.5)

    memory_system.save_to_backend(backend)

    restored = MemorySystem(backend=backend)
    restored.load_from_backend(backend)

    assert backend.semantic_payload is not None
    assert backend.episodic_payload is not None
    assert restored.know("favorite.color") == "blue"
    assert len(restored.episodic.items) == 1
    assert restored.episodic.items[0].summary == "A vivid event"


def test_autobiographical_store_round_trips_through_backend_without_files(tmp_path):
    backend = InMemoryAutobiographicalBackend()
    filepath = tmp_path / "autobio.jsonl"
    store = AutobiographicalStore(str(filepath), auto_flush=False, backend=backend)

    store.record(
        panksepp={"SEEKING": 0.8},
        valence=0.4,
        arousal=0.5,
        dominant="SEEKING",
        phi=0.3,
        narrative="Found something interesting",
        cycle=7,
    )
    store.flush()

    reloaded = AutobiographicalStore(str(filepath), auto_flush=False, backend=backend)

    assert backend.count_moments() == 1
    assert len(reloaded.moments) == 1
    assert reloaded.moments[0].narrative == "Found something interesting"
    assert reloaded.moments[0].cycle == 7
