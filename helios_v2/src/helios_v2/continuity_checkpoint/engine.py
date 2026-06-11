"""Owner: durable runtime-continuity checkpoint.

Provides the `ContinuityCheckpointStore` facade, the first-version single-row SQLite file
backend, and a deterministic in-memory backend double.

The store is infrastructure: it durably keeps ONE latest-state snapshot of the genuinely
cross-tick continuity state and returns it verbatim on load. The facade owns the JSON
encode/decode of the `RuntimeContinuitySnapshot` (a field-by-field projection of the reused
`09`/`18`/`24` owner contracts); the backend stays a dumb durable text sink. The owner holds
no cognitive policy, ranks nothing, and makes no runtime decision.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from helios_v2.autonomy import ContinuityThread, DeferredContinuityRecord
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.neuromodulation import NeuromodulatorLevels
from helios_v2.thought_gating import ContinuationPressureState

from .contracts import (
    CheckpointError,
    CheckpointStoreBackend,
    InternalMonologueCarryState,
    RuntimeContinuitySnapshot,
    SNAPSHOT_VERSION,
)

_NEUROMODULATOR_CHANNELS: tuple[str, ...] = (
    "dopamine",
    "norepinephrine",
    "serotonin",
    "acetylcholine",
    "cortisol",
    "oxytocin",
    "opioid_tone",
    "excitation",
    "inhibition",
)

_FEELING_DIMENSIONS: tuple[str, ...] = (
    "valence",
    "arousal",
    "tension",
    "comfort",
    "fatigue",
    "pain_like",
    "social_safety",
)


def _encode_neuromodulator_levels(levels: NeuromodulatorLevels) -> dict[str, float]:
    """Owner: durable runtime-continuity checkpoint. Project `04` levels to a plain dict."""

    return {channel: getattr(levels, channel) for channel in _NEUROMODULATOR_CHANNELS}


def _decode_neuromodulator_levels(payload: dict[str, object]) -> NeuromodulatorLevels:
    """Owner: durable runtime-continuity checkpoint. Reconstruct the `04` levels contract.

    Runs the `04` owner's own level-range validation, so a corrupt stored level hard-stops.
    """

    return NeuromodulatorLevels(
        **{channel: float(payload[channel]) for channel in _NEUROMODULATOR_CHANNELS}
    )


def _encode_feeling(feeling: InteroceptiveFeelingVector) -> dict[str, float]:
    """Owner: durable runtime-continuity checkpoint. Project `05` feeling to a plain dict."""

    return {dimension: getattr(feeling, dimension) for dimension in _FEELING_DIMENSIONS}


def _decode_feeling(payload: dict[str, object]) -> InteroceptiveFeelingVector:
    """Owner: durable runtime-continuity checkpoint. Reconstruct the `05` feeling contract.

    Runs the `05` owner's own range validation, so a corrupt stored feeling hard-stops.
    """

    return InteroceptiveFeelingVector(
        **{dimension: float(payload[dimension]) for dimension in _FEELING_DIMENSIONS}
    )


def _encode_continuation_state(state: ContinuationPressureState) -> dict[str, object]:
    """Owner: durable runtime-continuity checkpoint. Project `09` state to a plain dict."""

    return {
        "active": state.active,
        "level": state.level,
        "origin_thought_id": state.origin_thought_id,
        "reason": state.reason,
        "expires_at_tick": state.expires_at_tick,
        "carry_count": state.carry_count,
    }


def _decode_continuation_state(payload: dict[str, object]) -> ContinuationPressureState:
    """Owner: durable runtime-continuity checkpoint. Reconstruct the `09` owner contract.

    Calls the owner's own constructor so its invariants run on the restored values.
    """

    return ContinuationPressureState(
        active=bool(payload["active"]),
        level=float(payload["level"]),
        origin_thought_id=str(payload.get("origin_thought_id", "")),
        reason=str(payload.get("reason", "")),
        expires_at_tick=int(payload.get("expires_at_tick", 0)),
        carry_count=int(payload.get("carry_count", 0)),
    )


def _encode_deferred_record(record: DeferredContinuityRecord) -> dict[str, object]:
    """Owner: durable runtime-continuity checkpoint. Project an `18` deferred record to a dict."""

    return {
        "record_id": record.record_id,
        "continuity_key": record.continuity_key,
        "origin_ref": record.origin_ref,
        "carry_reason": record.carry_reason,
        "carry_count": record.carry_count,
        "decayed_pressure": record.decayed_pressure,
        "expires_after_ticks": record.expires_after_ticks,
    }


def _decode_deferred_record(payload: dict[str, object]) -> DeferredContinuityRecord:
    """Owner: durable runtime-continuity checkpoint. Reconstruct the `18` owner contract."""

    expires = payload.get("expires_after_ticks")
    return DeferredContinuityRecord(
        record_id=str(payload["record_id"]),
        continuity_key=str(payload["continuity_key"]),
        origin_ref=str(payload["origin_ref"]),
        carry_reason=str(payload["carry_reason"]),
        carry_count=int(payload["carry_count"]),
        decayed_pressure=float(payload["decayed_pressure"]),
        expires_after_ticks=None if expires is None else int(expires),
    )


def _encode_thread(thread: ContinuityThread) -> dict[str, object]:
    """Owner: durable runtime-continuity checkpoint. Project a `24` thread to a dict."""

    return {
        "thread_id": thread.thread_id,
        "continuity_key": thread.continuity_key,
        "origin_ref": thread.origin_ref,
        "age_ticks": thread.age_ticks,
        "reinforcement_count": thread.reinforcement_count,
        "thread_strength": thread.thread_strength,
        "thread_state": thread.thread_state,
        "last_carry_reason": thread.last_carry_reason,
    }


def _decode_thread(payload: dict[str, object]) -> ContinuityThread:
    """Owner: durable runtime-continuity checkpoint. Reconstruct the `24` owner contract."""

    return ContinuityThread(
        thread_id=str(payload["thread_id"]),
        continuity_key=str(payload["continuity_key"]),
        origin_ref=str(payload["origin_ref"]),
        age_ticks=int(payload["age_ticks"]),
        reinforcement_count=int(payload["reinforcement_count"]),
        thread_strength=float(payload["thread_strength"]),
        thread_state=str(payload["thread_state"]),  # type: ignore[arg-type]
        last_carry_reason=str(payload["last_carry_reason"]),
    )


def _encode_internal_monologue(im: "InternalMonologueCarryState | None") -> "dict | None":
    """Project an InternalMonologueCarryState into a JSON-safe dict.

    None -> None (no carry state captured this tick).
    """
    if im is None:
        return None
    return {
        "last_envelope": dict(im.last_envelope),
        "last_tick_id": im.last_tick_id,
        "i_want_to_think_more": im.i_want_to_think_more,
        "think_more_about": im.think_more_about,
    }


def _decode_internal_monologue(payload):
    """Reconstruct an InternalMonologueCarryState from its JSON projection.

    Missing or None payload -> None. The InternalMonologueCarryState constructor
    runs its own validation (Mapping check, tick_id >= 0 check, bool/str coercion).
    """
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise CheckpointError(
            "Stored snapshot internal_monologue must be a JSON object"
        )
    return InternalMonologueCarryState(
        last_envelope=payload.get("last_envelope"),
        last_tick_id=payload.get("last_tick_id"),
    )


def encode_snapshot(snapshot: RuntimeContinuitySnapshot) -> str:
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        Encode a `RuntimeContinuitySnapshot` into deterministic JSON text for durable storage.

    Inputs:
        `snapshot` - the latest-state snapshot to encode.

    Returns:
        A JSON string carrying the snapshot's version, tick id, and the projected `09`/`18`/`24`
        states.

    Raises:
        CheckpointError on an unexpected encoding failure.

    Notes:
        Field-by-field projection of the reused owner contracts. The facade owns this so the
        backend stays a dumb text sink.
    """

    try:
        return json.dumps(
            {
                "snapshot_version": snapshot.snapshot_version,
                "tick_id": snapshot.tick_id,
                "continuation_state": _encode_continuation_state(snapshot.continuation_state),
                "deferred_records": [
                    _encode_deferred_record(record) for record in snapshot.deferred_records
                ],
                "continuity_threads": [
                    _encode_thread(thread) for thread in snapshot.continuity_threads
                ],
                "neuromodulator_levels": (
                    _encode_neuromodulator_levels(snapshot.neuromodulator_levels)
                    if snapshot.neuromodulator_levels is not None
                    else None
                ),
                "feeling": (
                    _encode_feeling(snapshot.feeling)
                    if snapshot.feeling is not None
                    else None
                ),
                "internal_monologue": _encode_internal_monologue(
                    snapshot.internal_monologue
                ),
            },
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise CheckpointError(f"Could not encode runtime-continuity snapshot: {error}") from error


def decode_snapshot(payload: str) -> RuntimeContinuitySnapshot:
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        Decode durable JSON text back into a `RuntimeContinuitySnapshot`, reconstructing the
        reused owner contracts so their validation runs.

    Inputs:
        `payload` - the JSON text produced by `encode_snapshot`.

    Returns:
        The reconstructed `RuntimeContinuitySnapshot`.

    Raises:
        CheckpointError on non-JSON, a non-object payload, a snapshot version that does not match
        the current `SNAPSHOT_VERSION`, or a missing/malformed field. An invariant-violating
        reconstructed owner state raises that owner's own error, which is wrapped here into a
        `CheckpointError` so a corrupt snapshot is always a hard stop on load.

    Notes:
        Version handling: a v3 payload is decoded and reconstructed with
        `internal_monologue=None` (no v3 field); a v4 payload is decoded as-is. v>4
        payloads are rejected (forward-incompatible); v<3 payloads are rejected (cannot
        retro-migrate past R43/R44). This mirrors the runtime migrate path: a stored v3
        snapshot is transparently upgraded to v4 on first read; older payloads are not.
    """

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise CheckpointError("Stored runtime-continuity snapshot is not valid JSON") from error
    if not isinstance(data, dict):
        raise CheckpointError("Stored runtime-continuity snapshot must be a JSON object")
    try:
        snapshot_version = int(data.get("snapshot_version", -1))
        if snapshot_version > SNAPSHOT_VERSION:
            raise CheckpointError(
                f"Stored runtime-continuity snapshot version {snapshot_version} is forward of "
                f"the current version {SNAPSHOT_VERSION}; it is rejected rather than migrated"
            )
        if snapshot_version < 3:
            raise CheckpointError(
                f"Stored runtime-continuity snapshot version {snapshot_version} is pre-R43; "
                f"only v3 (migrated to v4) and v4 (current) are supported"
            )
        continuation_payload = data["continuation_state"]
        if not isinstance(continuation_payload, dict):
            raise CheckpointError("Stored snapshot continuation_state must be an object")
        continuation_state = _decode_continuation_state(continuation_payload)
        deferred_records = tuple(
            _decode_deferred_record(item) for item in data.get("deferred_records", [])
        )
        continuity_threads = tuple(
            _decode_thread(item) for item in data.get("continuity_threads", [])
        )
        levels_payload = data.get("neuromodulator_levels")
        neuromodulator_levels = (
            _decode_neuromodulator_levels(levels_payload)
            if isinstance(levels_payload, dict)
            else None
        )
        feeling_payload = data.get("feeling")
        feeling = (
            _decode_feeling(feeling_payload)
            if isinstance(feeling_payload, dict)
            else None
        )
        tick_id_value = data.get("tick_id")
        tick_id = None if tick_id_value is None else int(tick_id_value)
        internal_monologue_payload = data.get("internal_monologue")
        internal_monologue = (
            _decode_internal_monologue(internal_monologue_payload)
            if snapshot_version == SNAPSHOT_VERSION
            else None  # v3: no internal_monologue field, default to None.
        )
    except CheckpointError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise CheckpointError(f"Stored runtime-continuity snapshot is malformed: {error}") from error
    except RuntimeError as error:
        # An invariant-violating owner contract (e.g. ContinuationPressureState, NeuromodulatorLevels)
        # raises its own *Error (a RuntimeError subclass). Wrap it so a corrupt snapshot is a hard
        # stop on load.
        raise CheckpointError(f"Stored runtime-continuity snapshot violates an owner invariant: {error}") from error
    return RuntimeContinuitySnapshot(
        tick_id=tick_id,
        continuation_state=continuation_state,
        deferred_records=deferred_records,
        continuity_threads=continuity_threads,
        neuromodulator_levels=neuromodulator_levels,
        feeling=feeling,
        internal_monologue=internal_monologue,
        snapshot_version=snapshot_version,
    )


@dataclass
class InMemoryCheckpointBackend(CheckpointStoreBackend):
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        A deterministic single-slot backend double for tests and offline runs. Same
        latest-state replace semantics as the SQLite backend, but with no file.

    Failure semantics:
        Save and load are total. Not durable across processes; for restart-continuity use the
        SQLite backend.
    """

    _payload: str | None = None

    def initialize(self) -> None:
        """Owner: durable runtime-continuity checkpoint. Idempotent no-op for the in-memory backend."""

        return None

    def save_latest(self, payload: str) -> None:
        """Owner: durable runtime-continuity checkpoint. Replace the single latest payload."""

        self._payload = payload

    def load_latest(self) -> str | None:
        """Owner: durable runtime-continuity checkpoint. Return the latest payload or `None`."""

        return self._payload


@dataclass
class SqliteCheckpointBackend(CheckpointStoreBackend):
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        The first-version durable backend: a local SQLite file (standard library, no new
        dependency) holding ONE latest-state row keyed by a fixed id. The latest snapshot
        survives process exit and re-open of the same file.

    Failure semantics:
        Wraps any `sqlite3.Error` (including an unwritable path) in `CheckpointError`. Never
        fabricates or partially writes a payload.

    Notes:
        `INSERT OR REPLACE` on a fixed primary key gives atomic latest-state replace. Each call
        opens and closes its own connection so the backend holds no long-lived handle.
    """

    db_path: str
    _initialized: bool = False

    _TABLE = "runtime_continuity_checkpoint"
    _ROW_ID = 1

    def _connect(self) -> sqlite3.Connection:
        try:
            path = Path(self.db_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            return sqlite3.connect(self.db_path)
        except (sqlite3.Error, OSError, ValueError) as error:
            raise CheckpointError(
                f"SqliteCheckpointBackend could not open '{self.db_path}': {error}"
            ) from error

    def initialize(self) -> None:
        """Owner: durable runtime-continuity checkpoint. Create the single-row table (idempotent)."""

        try:
            with self._connect() as connection:
                connection.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._TABLE} (
                        row_id INTEGER PRIMARY KEY,
                        payload TEXT NOT NULL
                    )
                    """
                )
                connection.commit()
            self._initialized = True
        except sqlite3.Error as error:
            raise CheckpointError(
                f"SqliteCheckpointBackend could not initialize '{self.db_path}': {error}"
            ) from error

    def save_latest(self, payload: str) -> None:
        """Owner: durable runtime-continuity checkpoint. Replace the single latest row."""

        if not self._initialized:
            self.initialize()
        try:
            with self._connect() as connection:
                connection.execute(
                    f"INSERT OR REPLACE INTO {self._TABLE} (row_id, payload) VALUES (?, ?)",
                    (self._ROW_ID, payload),
                )
                connection.commit()
        except sqlite3.Error as error:
            raise CheckpointError(
                f"SqliteCheckpointBackend save failed for '{self.db_path}': {error}"
            ) from error

    def load_latest(self) -> str | None:
        """Owner: durable runtime-continuity checkpoint. Read the single latest row or `None`."""

        if not self._initialized:
            self.initialize()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    f"SELECT payload FROM {self._TABLE} WHERE row_id = ?",
                    (self._ROW_ID,),
                ).fetchone()
        except sqlite3.Error as error:
            raise CheckpointError(
                f"SqliteCheckpointBackend read failed for '{self.db_path}': {error}"
            ) from error
        if row is None:
            return None
        return str(row[0])


@dataclass
class ContinuityCheckpointStore:
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        The public facade over an injected durable backend. It saves the latest
        runtime-continuity snapshot (replacing any prior one) and loads the latest snapshot (or
        reports explicit absence). It owns the snapshot JSON encode/decode; the backend stores
        opaque text.

    Failure semantics:
        Delegates durability to the backend, which raises `CheckpointError` on failure. A
        corrupt stored payload raises `CheckpointError` on load (decode failure or an
        invariant-violating owner reconstruction).

    Notes:
        The facade performs no continuity judgment. It is latest-state only; it keeps no history.
    """

    backend: CheckpointStoreBackend

    def initialize(self) -> None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Idempotently prepare the durable backend before any save or load.

        Raises:
            CheckpointError if the backend cannot be initialized.
        """

        self.backend.initialize()

    def save_latest(self, snapshot: RuntimeContinuitySnapshot) -> None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Encode and durably save `snapshot` as the single latest snapshot, replacing any prior.

        Inputs:
            `snapshot` - the latest-state continuity snapshot.

        Returns:
            None.

        Raises:
            CheckpointError on an encoding or durability failure.
        """

        self.backend.save_latest(encode_snapshot(snapshot))

    def load_latest(self) -> RuntimeContinuitySnapshot | None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Load and decode the latest persisted snapshot, or return `None` when the store is cold.

        Inputs:
            None.

        Returns:
            The latest `RuntimeContinuitySnapshot`, or `None` when no snapshot has been saved.

        Raises:
            CheckpointError on a read failure or a corrupt/invariant-violating stored payload.
        """

        payload = self.backend.load_latest()
        if payload is None:
            return None
        return decode_snapshot(payload)
