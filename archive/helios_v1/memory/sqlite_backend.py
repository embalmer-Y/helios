"""SQLite-backed long-term memory backend implementations."""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterable, Iterator, Optional

from .backend import AutobiographicalBackend, MemoryBackend


SCHEMA_VERSION = 1


class SQLiteMemoryBackend(MemoryBackend, AutobiographicalBackend):
    """Persist semantic, episodic, and autobiographical memory state in SQLite."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(self._schema_sql())
            connection.execute(
                """
                INSERT INTO schema_migrations(version, applied_at)
                VALUES(?, ?)
                ON CONFLICT(version) DO NOTHING
                """,
                (SCHEMA_VERSION, time.time()),
            )
            connection.commit()

    def save_semantic_payload(self, payload: dict[str, Any]) -> None:
        self.initialize()
        facts = payload.get("facts", []) if isinstance(payload, dict) else []
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_semantic")
            for fact in facts:
                key = str(fact.get("key", ""))
                if not key:
                    continue
                tags = list(fact.get("tags", [])) if isinstance(fact.get("tags", []), list) else []
                connection.execute(
                    """
                    INSERT INTO memory_semantic(
                        memory_id,
                        memory_key,
                        payload_json,
                        confidence,
                        tags_json,
                        updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"semantic::{key}",
                        key,
                        json.dumps(fact, ensure_ascii=False, sort_keys=True),
                        float(fact.get("confidence", 0.0) or 0.0),
                        json.dumps(tags, ensure_ascii=False, sort_keys=True),
                        time.time(),
                    ),
                )
            connection.commit()

    def load_semantic_payload(self) -> Optional[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM memory_semantic ORDER BY memory_key"
            ).fetchall()
        if not rows:
            return None
        return {
            "version": 1,
            "timestamp": time.time(),
            "facts": [json.loads(row["payload_json"]) for row in rows],
        }

    def save_episodic_payload(self, payload: dict[str, Any]) -> None:
        self.initialize()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_episodic")
            for item in items:
                memory_id = str(item.get("id", ""))
                if not memory_id:
                    continue
                content = item.get("content", {}) if isinstance(item.get("content", {}), dict) else {}
                tags = list(content.get("tags", [])) if isinstance(content.get("tags", []), list) else []
                connection.execute(
                    """
                    INSERT INTO memory_episodic(
                        memory_id,
                        summary,
                        timestamp,
                        importance,
                        emotional_tag,
                        tags_json,
                        payload_json,
                        updated_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        str(item.get("summary", "")),
                        float(item.get("timestamp", 0.0) or 0.0),
                        float(item.get("importance", 0.0) or 0.0),
                        str(item.get("emotional_tag", "neutral")),
                        json.dumps(tags, ensure_ascii=False, sort_keys=True),
                        json.dumps(item, ensure_ascii=False, sort_keys=True),
                        time.time(),
                    ),
                )
            connection.commit()

    def load_episodic_payload(self) -> Optional[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM memory_episodic ORDER BY timestamp, memory_id"
            ).fetchall()
        if not rows:
            return None
        return {
            "version": 1,
            "timestamp": time.time(),
            "items": [json.loads(row["payload_json"]) for row in rows],
        }

    def append_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        self.initialize()
        with self._connect() as connection:
            for payload in payloads:
                self._upsert_autobio_moment(connection, payload)
            connection.commit()

    def load_moment_payloads(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM memory_autobio ORDER BY timestamp, moment_id"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def save_chapter_payloads(self, payloads: list[dict[str, Any]]) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_autobio_chapters")
            for payload in payloads:
                chapter_key = self._chapter_key(payload)
                connection.execute(
                    """
                    INSERT INTO memory_autobio_chapters(
                        chapter_key,
                        start_time,
                        end_time,
                        payload_json,
                        updated_at
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        chapter_key,
                        float(payload.get("start_time", 0.0) or 0.0),
                        float(payload.get("end_time", 0.0) or 0.0),
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        time.time(),
                    ),
                )
            connection.commit()

    def load_chapter_payloads(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM memory_autobio_chapters ORDER BY start_time, chapter_key"
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def count_moments(self) -> int:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM memory_autobio").fetchone()
        return int(row["count"] if row is not None else 0)

    def archive_active_log(self, archive_suffix: str) -> None:
        self.initialize()
        archived_at = time.time()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT moment_id, timestamp, payload_json FROM memory_autobio ORDER BY timestamp, moment_id"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    INSERT INTO memory_autobio_archive(
                        archive_batch,
                        moment_id,
                        timestamp,
                        payload_json,
                        archived_at
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        archive_suffix,
                        str(row["moment_id"]),
                        float(row["timestamp"]),
                        str(row["payload_json"]),
                        archived_at,
                    ),
                )
            connection.execute("DELETE FROM memory_autobio")
            connection.commit()

    def overwrite_active_moments(self, payloads: Iterable[dict[str, Any]]) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute("DELETE FROM memory_autobio")
            for payload in payloads:
                self._upsert_autobio_moment(connection, payload)
            connection.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _chapter_key(payload: dict[str, Any]) -> str:
        start_key = str(payload.get("start_moment_id", "") or payload.get("start_time", "0"))
        title_key = str(payload.get("title", "chapter"))
        return f"{start_key}::{title_key}"

    @staticmethod
    def _upsert_autobio_moment(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
        moment_id = str(payload.get("moment_id", ""))
        if not moment_id:
            return
        tags = payload.get("tags", []) if isinstance(payload.get("tags", []), list) else []
        source = payload.get("source", "")
        connection.execute(
            """
            INSERT INTO memory_autobio(
                moment_id,
                timestamp,
                significance,
                tags_json,
                source_json,
                payload_json,
                updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(moment_id) DO UPDATE SET
                timestamp=excluded.timestamp,
                significance=excluded.significance,
                tags_json=excluded.tags_json,
                source_json=excluded.source_json,
                payload_json=excluded.payload_json,
                updated_at=excluded.updated_at
            """,
            (
                moment_id,
                float(payload.get("timestamp", 0.0) or 0.0),
                float(payload.get("significance", 0.0) or 0.0),
                json.dumps(tags, ensure_ascii=False, sort_keys=True),
                json.dumps({"source": source}, ensure_ascii=False, sort_keys=True),
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                time.time(),
            ),
        )

    @staticmethod
    def _schema_sql() -> str:
        return """
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_semantic(
            memory_id TEXT PRIMARY KEY,
            memory_key TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            confidence REAL NOT NULL,
            tags_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_episodic(
            memory_id TEXT PRIMARY KEY,
            summary TEXT NOT NULL,
            timestamp REAL NOT NULL,
            importance REAL NOT NULL,
            emotional_tag TEXT NOT NULL,
            tags_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_autobio(
            moment_id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            significance REAL NOT NULL,
            tags_json TEXT NOT NULL,
            source_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_autobio_chapters(
            chapter_key TEXT PRIMARY KEY,
            start_time REAL NOT NULL,
            end_time REAL NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS memory_autobio_archive(
            archive_batch TEXT NOT NULL,
            moment_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            payload_json TEXT NOT NULL,
            archived_at REAL NOT NULL,
            PRIMARY KEY(archive_batch, moment_id)
        );

        CREATE INDEX IF NOT EXISTS idx_memory_semantic_key ON memory_semantic(memory_key);
        CREATE INDEX IF NOT EXISTS idx_memory_episodic_timestamp ON memory_episodic(timestamp);
        CREATE INDEX IF NOT EXISTS idx_memory_autobio_timestamp ON memory_autobio(timestamp);
        CREATE INDEX IF NOT EXISTS idx_memory_autobio_archive_batch ON memory_autobio_archive(archive_batch);
        """


def ensure_sqlite_memory_backend(db_path: str | Path) -> SQLiteMemoryBackend:
    backend = SQLiteMemoryBackend(db_path)
    backend.initialize()
    return backend


__all__ = ["SQLiteMemoryBackend", "ensure_sqlite_memory_backend"]