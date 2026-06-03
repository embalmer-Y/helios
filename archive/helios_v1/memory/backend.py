"""Persistence backends for long-term memory stores."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable, Optional


class MemoryBackend(ABC):
    """Abstract persistence backend for semantic and episodic memory state."""

    @abstractmethod
    def save_semantic_payload(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_semantic_payload(self) -> Optional[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_episodic_payload(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_episodic_payload(self) -> Optional[dict[str, Any]]:
        raise NotImplementedError


class DirectoryMemoryBackend(MemoryBackend):
    """JSON file backend compatible with the legacy MemorySystem persistence layout."""

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    @property
    def semantic_path(self) -> Path:
        return self.data_dir / "semantic_memory.json"

    @property
    def episodic_path(self) -> Path:
        return self.data_dir / "episodic_memory.json"

    def save_semantic_payload(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.semantic_path, payload, ".helios_semantic_")

    def load_semantic_payload(self) -> Optional[dict[str, Any]]:
        return self._read_json(self.semantic_path)

    def save_episodic_payload(self, payload: dict[str, Any]) -> None:
        self._atomic_write_json(self.episodic_path, payload, ".helios_episodic_")

    def load_episodic_payload(self) -> Optional[dict[str, Any]]:
        return self._read_json(self.episodic_path)

    def _atomic_write_json(self, path: Path, payload: dict[str, Any], prefix: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=prefix,
            dir=str(path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_json(path: Path) -> Optional[dict[str, Any]]:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)


class AutobiographicalBackend(ABC):
    """Abstract persistence backend for append-only autobiographical history."""

    @abstractmethod
    def append_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_moment_payloads(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_chapter_payloads(self, payloads: list[dict[str, Any]]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_chapter_payloads(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def count_moments(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def archive_active_log(self, archive_suffix: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def overwrite_active_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        raise NotImplementedError


class JsonlAutobiographicalBackend(AutobiographicalBackend):
    """JSONL file backend compatible with the legacy AutobiographicalStore format."""

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    @property
    def chapters_path(self) -> Path:
        return Path(str(self.filepath).replace(".jsonl", "_chapters.json"))

    def append_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        with open(self.filepath, "a", encoding="utf-8") as handle:
            for payload in payloads:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def load_moment_payloads(self) -> list[dict[str, Any]]:
        if not self.filepath.exists():
            return []
        payloads: list[dict[str, Any]] = []
        with open(self.filepath, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payloads.append(json.loads(line))
        return payloads

    def save_chapter_payloads(self, payloads: list[dict[str, Any]]) -> None:
        with open(self.chapters_path, "w", encoding="utf-8") as handle:
            json.dump(payloads, handle, ensure_ascii=False, indent=2)

    def load_chapter_payloads(self) -> list[dict[str, Any]]:
        if not self.chapters_path.exists():
            return []
        with open(self.chapters_path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []

    def count_moments(self) -> int:
        if not self.filepath.exists():
            return 0
        with open(self.filepath, "r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)

    def archive_active_log(self, archive_suffix: str) -> None:
        archive_name = self.filepath.stem + f"_{archive_suffix}" + self.filepath.suffix
        archive_path = self.filepath.parent / archive_name
        os.rename(self.filepath, archive_path)

    def overwrite_active_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        with open(self.filepath, "w", encoding="utf-8") as handle:
            for payload in payloads:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


__all__ = [
    "AutobiographicalBackend",
    "DirectoryMemoryBackend",
    "JsonlAutobiographicalBackend",
    "MemoryBackend",
]