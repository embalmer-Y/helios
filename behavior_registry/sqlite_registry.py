"""SQLite-backed behavior registry for bootstrap and future learned behaviors."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import time
from typing import Any
from typing import Iterable, Iterator, Optional

from helios_io.action_models import BehaviorSpec
from .records import BehaviorExecutionRecord, BehaviorSourceRecord, FeedbackEventRecord


SCHEMA_VERSION = 1


class SQLiteBehaviorRegistry:
    """Persist and query behavior definitions through a local SQLite database."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._initialized = False

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        if self._initialized:
            return
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
            self._initialized = True

    def upsert_behavior(self, spec: BehaviorSpec) -> None:
        self.initialize()
        payload = self._spec_to_row(spec)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO behaviors(
                    behavior_id,
                    name,
                    display_name,
                    description,
                    category,
                    status,
                    version,
                    execution_mode,
                    parameter_schema_json,
                    applicable_context_json,
                    cooldown_policy_json,
                    cost_policy_json,
                    allowed_channel_ids_json,
                    required_capabilities_json,
                    supported_modalities_json,
                    source_kind,
                    source_detail_json,
                    review_state,
                    created_at,
                    updated_at
                ) VALUES(
                    :behavior_id,
                    :name,
                    :display_name,
                    :description,
                    :category,
                    :status,
                    :version,
                    :execution_mode,
                    :parameter_schema_json,
                    :applicable_context_json,
                    :cooldown_policy_json,
                    :cost_policy_json,
                    :allowed_channel_ids_json,
                    :required_capabilities_json,
                    :supported_modalities_json,
                    :source_kind,
                    :source_detail_json,
                    :review_state,
                    :created_at,
                    :updated_at
                )
                ON CONFLICT(behavior_id) DO UPDATE SET
                    name=excluded.name,
                    display_name=excluded.display_name,
                    description=excluded.description,
                    category=excluded.category,
                    status=excluded.status,
                    version=excluded.version,
                    execution_mode=excluded.execution_mode,
                    parameter_schema_json=excluded.parameter_schema_json,
                    applicable_context_json=excluded.applicable_context_json,
                    cooldown_policy_json=excluded.cooldown_policy_json,
                    cost_policy_json=excluded.cost_policy_json,
                    allowed_channel_ids_json=excluded.allowed_channel_ids_json,
                    required_capabilities_json=excluded.required_capabilities_json,
                    supported_modalities_json=excluded.supported_modalities_json,
                    source_kind=excluded.source_kind,
                    source_detail_json=excluded.source_detail_json,
                    review_state=excluded.review_state,
                    updated_at=excluded.updated_at
                """,
                payload,
            )
            connection.commit()

    def get_behavior(self, behavior_name_or_id: str) -> Optional[BehaviorSpec]:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM behaviors
                WHERE behavior_id = ? OR name = ? OR display_name = ?
                LIMIT 1
                """,
                (behavior_name_or_id, behavior_name_or_id, behavior_name_or_id),
            ).fetchone()
        return None if row is None else self._row_to_spec(row)

    def list_behaviors(
        self,
        *,
        category: str = "",
        status: str = "",
        review_state: str = "",
    ) -> list[BehaviorSpec]:
        self.initialize()
        clauses: list[str] = []
        params: list[str] = []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if review_state:
            clauses.append("review_state = ?")
            params.append(review_state)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM behaviors {where} ORDER BY category, name",
                params,
            ).fetchall()
        return [self._row_to_spec(row) for row in rows]

    def import_behaviors(self, specs: Iterable[BehaviorSpec]) -> int:
        self.initialize()
        count = 0
        with self._connect() as connection:
            for spec in specs:
                payload = self._spec_to_row(spec)
                connection.execute(
                    """
                    INSERT INTO behaviors(
                        behavior_id,
                        name,
                        display_name,
                        description,
                        category,
                        status,
                        version,
                        execution_mode,
                        parameter_schema_json,
                        applicable_context_json,
                        cooldown_policy_json,
                        cost_policy_json,
                        allowed_channel_ids_json,
                        required_capabilities_json,
                        supported_modalities_json,
                        source_kind,
                        source_detail_json,
                        review_state,
                        created_at,
                        updated_at
                    ) VALUES(
                        :behavior_id,
                        :name,
                        :display_name,
                        :description,
                        :category,
                        :status,
                        :version,
                        :execution_mode,
                        :parameter_schema_json,
                        :applicable_context_json,
                        :cooldown_policy_json,
                        :cost_policy_json,
                        :allowed_channel_ids_json,
                        :required_capabilities_json,
                        :supported_modalities_json,
                        :source_kind,
                        :source_detail_json,
                        :review_state,
                        :created_at,
                        :updated_at
                    )
                    ON CONFLICT(behavior_id) DO UPDATE SET
                        name=excluded.name,
                        display_name=excluded.display_name,
                        description=excluded.description,
                        category=excluded.category,
                        status=excluded.status,
                        version=excluded.version,
                        execution_mode=excluded.execution_mode,
                        parameter_schema_json=excluded.parameter_schema_json,
                        applicable_context_json=excluded.applicable_context_json,
                        cooldown_policy_json=excluded.cooldown_policy_json,
                        cost_policy_json=excluded.cost_policy_json,
                        allowed_channel_ids_json=excluded.allowed_channel_ids_json,
                        required_capabilities_json=excluded.required_capabilities_json,
                        supported_modalities_json=excluded.supported_modalities_json,
                        source_kind=excluded.source_kind,
                        source_detail_json=excluded.source_detail_json,
                        review_state=excluded.review_state,
                        updated_at=excluded.updated_at
                    """,
                    payload,
                )
                count += 1
            connection.commit()
        return count

    def propose_behavior(
        self,
        spec: BehaviorSpec,
        *,
        source_summary: str = "",
        source_uri: str = "",
        source_kind: str = "llm_proposal",
    ) -> BehaviorSpec:
        normalized = self._clone_spec(
            spec,
            status="draft",
            review_state="pending",
            source_kind=source_kind or spec.source_kind or "llm_proposal",
            source_detail=self._merge_source_detail(
                spec.source_detail,
                {
                    "proposal_created_at": time.time(),
                    "proposal_source_kind": source_kind or spec.source_kind or "llm_proposal",
                },
            ),
        )
        self.upsert_behavior(normalized)
        self.record_behavior_source(
            BehaviorSourceRecord(
                source_id=f"source::proposal::{normalized.behavior_id}",
                behavior_id=normalized.behavior_id,
                source_kind=normalized.source_kind,
                source_uri=source_uri,
                source_summary=source_summary or f"Proposed behavior {normalized.name}",
                captured_at=float(normalized.source_detail.get("proposal_created_at", time.time())),
            )
        )
        return normalized

    def approve_behavior(
        self,
        behavior_name_or_id: str,
        *,
        approved_by: str = "",
        review_note: str = "",
        status: str = "active",
    ) -> Optional[BehaviorSpec]:
        existing = self.get_behavior(behavior_name_or_id)
        if existing is None:
            return None
        approved = self._clone_spec(
            existing,
            status=status,
            review_state="approved",
            source_detail=self._merge_source_detail(
                existing.source_detail,
                {
                    "approved_at": time.time(),
                    "approved_by": approved_by,
                    "review_note": review_note,
                },
            ),
        )
        self.upsert_behavior(approved)
        return approved

    def record_behavior_source(self, record: BehaviorSourceRecord) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO behavior_sources(
                    source_id,
                    behavior_id,
                    source_kind,
                    source_uri,
                    source_summary,
                    captured_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    behavior_id=excluded.behavior_id,
                    source_kind=excluded.source_kind,
                    source_uri=excluded.source_uri,
                    source_summary=excluded.source_summary,
                    captured_at=excluded.captured_at
                """,
                (
                    record.source_id,
                    record.behavior_id,
                    record.source_kind,
                    record.source_uri or None,
                    record.source_summary,
                    record.captured_at,
                ),
            )
            connection.commit()

    def record_behavior_sources(self, records: Iterable[BehaviorSourceRecord]) -> int:
        self.initialize()
        row_count = 0
        with self._connect() as connection:
            for record in records:
                connection.execute(
                    """
                    INSERT INTO behavior_sources(
                        source_id,
                        behavior_id,
                        source_kind,
                        source_uri,
                        source_summary,
                        captured_at
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        behavior_id=excluded.behavior_id,
                        source_kind=excluded.source_kind,
                        source_uri=excluded.source_uri,
                        source_summary=excluded.source_summary,
                        captured_at=excluded.captured_at
                    """,
                    (
                        record.source_id,
                        record.behavior_id,
                        record.source_kind,
                        record.source_uri or None,
                        record.source_summary,
                        record.captured_at,
                    ),
                )
                row_count += 1
            connection.commit()
        return row_count

    def list_behavior_sources(
        self,
        *,
        behavior_id: str = "",
        source_kind: str = "",
    ) -> list[BehaviorSourceRecord]:
        self.initialize()
        clauses: list[str] = []
        params: list[str] = []
        if behavior_id:
            clauses.append("behavior_id = ?")
            params.append(behavior_id)
        if source_kind:
            clauses.append("source_kind = ?")
            params.append(source_kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM behavior_sources {where} ORDER BY captured_at, source_id",
                params,
            ).fetchall()
        return [self._row_to_source_record(row) for row in rows]

    def record_execution_feedback(self, record: BehaviorExecutionRecord) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO behavior_execution_log(
                    execution_id,
                    behavior_id,
                    proposal_id,
                    decision_id,
                    channel_id,
                    op_name,
                    success,
                    result_json,
                    feedback_json,
                    created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    behavior_id=excluded.behavior_id,
                    proposal_id=excluded.proposal_id,
                    decision_id=excluded.decision_id,
                    channel_id=excluded.channel_id,
                    op_name=excluded.op_name,
                    success=excluded.success,
                    result_json=excluded.result_json,
                    feedback_json=excluded.feedback_json,
                    created_at=excluded.created_at
                """,
                (
                    record.execution_id,
                    record.behavior_id,
                    record.proposal_id,
                    record.decision_id,
                    record.channel_id or None,
                    record.op_name or None,
                    1 if record.success else 0,
                    json.dumps(record.result_details, ensure_ascii=False, sort_keys=True),
                    json.dumps(record.feedback_details, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()

    def list_execution_feedback(
        self,
        *,
        behavior_id: str = "",
        proposal_id: str = "",
        decision_id: str = "",
    ) -> list[BehaviorExecutionRecord]:
        self.initialize()
        clauses: list[str] = []
        params: list[str] = []
        if behavior_id:
            clauses.append("behavior_id = ?")
            params.append(behavior_id)
        if proposal_id:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if decision_id:
            clauses.append("decision_id = ?")
            params.append(decision_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM behavior_execution_log {where} ORDER BY created_at, execution_id",
                params,
            ).fetchall()
        return [self._row_to_execution_record(row) for row in rows]

    def record_feedback_event(self, record: FeedbackEventRecord) -> None:
        self.initialize()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO feedback_events(
                    event_id,
                    event_kind,
                    source_path,
                    proposal_id,
                    decision_id,
                    behavior_id,
                    channel_id,
                    memory_id,
                    payload_json,
                    created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    event_kind=excluded.event_kind,
                    source_path=excluded.source_path,
                    proposal_id=excluded.proposal_id,
                    decision_id=excluded.decision_id,
                    behavior_id=excluded.behavior_id,
                    channel_id=excluded.channel_id,
                    memory_id=excluded.memory_id,
                    payload_json=excluded.payload_json,
                    created_at=excluded.created_at
                """,
                (
                    record.event_id,
                    record.event_kind,
                    record.source_path,
                    record.proposal_id or None,
                    record.decision_id or None,
                    record.behavior_id or None,
                    record.channel_id or None,
                    record.memory_id or None,
                    json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
                    record.created_at,
                ),
            )
            connection.commit()

    def list_feedback_events(
        self,
        *,
        event_kind: str = "",
        source_path: str = "",
        proposal_id: str = "",
        decision_id: str = "",
        behavior_id: str = "",
        channel_id: str = "",
        memory_id: str = "",
    ) -> list[FeedbackEventRecord]:
        self.initialize()
        clauses: list[str] = []
        params: list[str] = []
        if event_kind:
            clauses.append("event_kind = ?")
            params.append(event_kind)
        if source_path:
            clauses.append("source_path = ?")
            params.append(source_path)
        if proposal_id:
            clauses.append("proposal_id = ?")
            params.append(proposal_id)
        if decision_id:
            clauses.append("decision_id = ?")
            params.append(decision_id)
        if behavior_id:
            clauses.append("behavior_id = ?")
            params.append(behavior_id)
        if channel_id:
            clauses.append("channel_id = ?")
            params.append(channel_id)
        if memory_id:
            clauses.append("memory_id = ?")
            params.append(memory_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM feedback_events {where} ORDER BY created_at, event_id",
                params,
            ).fetchall()
        return [self._row_to_feedback_event(row) for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @staticmethod
    def _schema_sql() -> str:
        return """
        CREATE TABLE IF NOT EXISTS schema_migrations(
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS behaviors(
            behavior_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            version TEXT NOT NULL,
            execution_mode TEXT NOT NULL,
            parameter_schema_json TEXT NOT NULL,
            applicable_context_json TEXT NOT NULL,
            cooldown_policy_json TEXT NOT NULL,
            cost_policy_json TEXT NOT NULL,
            allowed_channel_ids_json TEXT NOT NULL,
            required_capabilities_json TEXT NOT NULL,
            supported_modalities_json TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_detail_json TEXT NOT NULL,
            review_state TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS behavior_sources(
            source_id TEXT PRIMARY KEY,
            behavior_id TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_uri TEXT,
            source_summary TEXT NOT NULL,
            captured_at REAL NOT NULL,
            FOREIGN KEY(behavior_id) REFERENCES behaviors(behavior_id)
        );

        CREATE TABLE IF NOT EXISTS behavior_execution_log(
            execution_id TEXT PRIMARY KEY,
            behavior_id TEXT NOT NULL,
            proposal_id TEXT NOT NULL,
            decision_id TEXT NOT NULL,
            channel_id TEXT,
            op_name TEXT,
            success INTEGER NOT NULL,
            result_json TEXT NOT NULL,
            feedback_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY(behavior_id) REFERENCES behaviors(behavior_id)
        );

        CREATE TABLE IF NOT EXISTS feedback_events(
            event_id TEXT PRIMARY KEY,
            event_kind TEXT NOT NULL,
            source_path TEXT NOT NULL,
            proposal_id TEXT,
            decision_id TEXT,
            behavior_id TEXT,
            channel_id TEXT,
            memory_id TEXT,
            payload_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_behaviors_name ON behaviors(name);
        CREATE INDEX IF NOT EXISTS idx_behaviors_category ON behaviors(category);
        CREATE INDEX IF NOT EXISTS idx_behavior_sources_behavior_id ON behavior_sources(behavior_id);
        CREATE INDEX IF NOT EXISTS idx_behavior_execution_log_behavior_id ON behavior_execution_log(behavior_id);
        CREATE INDEX IF NOT EXISTS idx_feedback_events_kind ON feedback_events(event_kind);
        CREATE INDEX IF NOT EXISTS idx_feedback_events_source_path ON feedback_events(source_path);
        CREATE INDEX IF NOT EXISTS idx_feedback_events_behavior_id ON feedback_events(behavior_id);
        """

    @staticmethod
    def _spec_to_row(spec: BehaviorSpec) -> dict[str, object]:
        now = time.time()
        created_at = now
        source_detail = dict(spec.source_detail)
        if "created_at" in source_detail:
            try:
                created_at = float(source_detail["created_at"])
            except (TypeError, ValueError):
                created_at = now
        return {
            "behavior_id": spec.behavior_id,
            "name": spec.name,
            "display_name": spec.display_name,
            "description": spec.description,
            "category": spec.category,
            "status": spec.status,
            "version": spec.version,
            "execution_mode": spec.execution_mode,
            "parameter_schema_json": json.dumps(spec.parameter_schema, ensure_ascii=False, sort_keys=True),
            "applicable_context_json": json.dumps(spec.applicable_context, ensure_ascii=False, sort_keys=True),
            "cooldown_policy_json": json.dumps(spec.cooldown_policy, ensure_ascii=False, sort_keys=True),
            "cost_policy_json": json.dumps(spec.cost_policy, ensure_ascii=False, sort_keys=True),
            "allowed_channel_ids_json": json.dumps(list(spec.allowed_channel_ids), ensure_ascii=False),
            "required_capabilities_json": json.dumps(list(spec.required_capabilities), ensure_ascii=False),
            "supported_modalities_json": json.dumps(list(spec.supported_modalities), ensure_ascii=False),
            "source_kind": spec.source_kind,
            "source_detail_json": json.dumps(spec.source_detail, ensure_ascii=False, sort_keys=True),
            "review_state": spec.review_state,
            "created_at": created_at,
            "updated_at": now,
        }

    @staticmethod
    def _row_to_spec(row: sqlite3.Row) -> BehaviorSpec:
        return BehaviorSpec(
            behavior_id=str(row["behavior_id"]),
            name=str(row["name"]),
            display_name=str(row["display_name"]),
            description=str(row["description"]),
            category=str(row["category"]),
            status=str(row["status"]),
            version=str(row["version"]),
            execution_mode=str(row["execution_mode"]),
            parameter_schema=json.loads(row["parameter_schema_json"]),
            applicable_context=json.loads(row["applicable_context_json"]),
            cooldown_policy=json.loads(row["cooldown_policy_json"]),
            cost_policy=json.loads(row["cost_policy_json"]),
            allowed_channel_ids=list(json.loads(row["allowed_channel_ids_json"])),
            required_capabilities=list(json.loads(row["required_capabilities_json"])),
            supported_modalities=list(json.loads(row["supported_modalities_json"])),
            source_kind=str(row["source_kind"]),
            source_detail=json.loads(row["source_detail_json"]),
            review_state=str(row["review_state"]),
        )

    @staticmethod
    def _row_to_source_record(row: sqlite3.Row) -> BehaviorSourceRecord:
        return BehaviorSourceRecord(
            source_id=str(row["source_id"]),
            behavior_id=str(row["behavior_id"]),
            source_kind=str(row["source_kind"]),
            source_uri=str(row["source_uri"] or ""),
            source_summary=str(row["source_summary"]),
            captured_at=float(row["captured_at"]),
        )

    @staticmethod
    def _row_to_execution_record(row: sqlite3.Row) -> BehaviorExecutionRecord:
        return BehaviorExecutionRecord(
            execution_id=str(row["execution_id"]),
            behavior_id=str(row["behavior_id"]),
            proposal_id=str(row["proposal_id"]),
            decision_id=str(row["decision_id"]),
            channel_id=str(row["channel_id"] or ""),
            op_name=str(row["op_name"] or ""),
            success=bool(row["success"]),
            result_details=json.loads(row["result_json"]),
            feedback_details=json.loads(row["feedback_json"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _row_to_feedback_event(row: sqlite3.Row) -> FeedbackEventRecord:
        return FeedbackEventRecord(
            event_id=str(row["event_id"]),
            event_kind=str(row["event_kind"]),
            source_path=str(row["source_path"]),
            proposal_id=str(row["proposal_id"] or ""),
            decision_id=str(row["decision_id"] or ""),
            behavior_id=str(row["behavior_id"] or ""),
            channel_id=str(row["channel_id"] or ""),
            memory_id=str(row["memory_id"] or ""),
            payload=json.loads(row["payload_json"]),
            created_at=float(row["created_at"]),
        )

    @staticmethod
    def _clone_spec(spec: BehaviorSpec, **overrides: Any) -> BehaviorSpec:
        payload = asdict(spec)
        payload.update(overrides)
        return BehaviorSpec(**payload)

    @staticmethod
    def _merge_source_detail(source_detail: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        merged = dict(source_detail)
        merged.update(updates)
        return merged


def ensure_behavior_registry(db_path: str | Path) -> SQLiteBehaviorRegistry:
    registry = SQLiteBehaviorRegistry(db_path)
    registry.initialize()
    return registry