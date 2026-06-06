"""Owner: durable runtime-continuity checkpoint.

Owns:
- the durable latest-state runtime-continuity snapshot contract
- the durable checkpoint backend protocol boundary

Does not own:
- continuity classification or continuation-pressure policy (owned by `09` thought gating)
- long-horizon continuity policy (owned by `18` autonomy / `24` threads)
- any cognitive runtime decision or salience judgment
- the runtime stage chain or composition wiring

This owner is infrastructure, like observability (`21`) and the durable experience store
(`33`). Where `33` durably appends the episodic experience stream, this owner durably keeps
ONE latest-state snapshot of the genuinely cross-tick continuity state and restores it on
restart. It stores and returns owner-published values verbatim; it never interprets their
meaning and never makes a cognitive decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from helios_v2.autonomy import ContinuityThread, DeferredContinuityRecord
from helios_v2.thought_gating import ContinuationPressureState

# Current snapshot schema version. Bumped only when the snapshot's persisted shape changes
# in a way the facade's decode must branch on. The version is persisted so an older file can
# be loaded by a newer runtime: fields absent in an older version reconstruct to the existing
# inert owner defaults rather than failing.
SNAPSHOT_VERSION = 1


class CheckpointError(RuntimeError):
    """Hard-stop error raised when runtime-continuity checkpoint invariants or backends fail."""


@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        One immutable latest-state snapshot of the runtime's genuinely cross-tick continuity
        state at a given tick: the `09` continuation-pressure state and the `18`/`24`
        long-horizon continuity (deferred-continuity records plus continuity threads).

    Failure semantics:
        Construction raises `CheckpointError` on a negative `snapshot_version`. The reused
        owner-contract fields (`continuation_state`, `deferred_records`, `continuity_threads`)
        are validated by their own owners' constructors, so an invalid value cannot reach this
        snapshot without that owner having raised first.

    Notes:
        This snapshot reuses the owners' own frozen contracts directly as its fields rather
        than inventing parallel shapes, so the owners remain the sole definition of their state
        shape and reconstruction runs their validation. It carries no authority and is never an
        inter-owner decision transport; it exists only so a restarted runtime can resume its
        prior cross-tick continuity. `04`/`05`/`14`/`06` state is intentionally out of scope:
        it is not cross-tick in-process state in the current runtime. The `snapshot_version`
        field allows those to be added additively later without breaking older files.
    """

    tick_id: int | None
    continuation_state: ContinuationPressureState
    deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    continuity_threads: tuple[ContinuityThread, ...] = ()
    snapshot_version: int = SNAPSHOT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_version, int) or self.snapshot_version < 1:
            raise CheckpointError("RuntimeContinuitySnapshot snapshot_version must be a positive integer")
        for record in self.deferred_records:
            if not isinstance(record, DeferredContinuityRecord):
                raise CheckpointError(
                    "RuntimeContinuitySnapshot deferred_records must contain DeferredContinuityRecord values"
                )
        for thread in self.continuity_threads:
            if not isinstance(thread, ContinuityThread):
                raise CheckpointError(
                    "RuntimeContinuitySnapshot continuity_threads must contain ContinuityThread values"
                )


@runtime_checkable
class CheckpointStoreBackend(Protocol):
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        The durable backend boundary behind which a concrete checkpoint store (SQLite file,
        in-memory double) is injected. The `ContinuityCheckpointStore` facade depends only on
        this protocol and owns the snapshot encode/decode; the backend is a dumb durable text
        sink keyed to a single latest-state slot.

    Notes:
        Implementations persist exactly one latest payload. `save_latest` must fully replace
        any prior payload (latest-state, not an append log). They must raise `CheckpointError`
        on an unrecoverable durability failure and must never fabricate or partially write a
        payload.
    """

    def initialize(self) -> None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Idempotently prepare the backend (create the table/file if absent).

        Inputs:
            None.

        Returns:
            None.

        Raises:
            CheckpointError if the backend cannot be initialized (for example an unwritable
            path).

        Notes:
            Must be safe to call more than once.
        """

    def save_latest(self, payload: str) -> None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Durably persist `payload` as the single latest snapshot, replacing any prior one.

        Inputs:
            `payload` - the facade-encoded snapshot text.

        Returns:
            None.

        Raises:
            CheckpointError on a durability failure.

        Notes:
            Latest-state only. A prior payload is overwritten, never appended to.
        """

    def load_latest(self) -> str | None:
        """Owner: durable runtime-continuity checkpoint.

        Purpose:
            Return the single latest persisted payload, or `None` when the store is cold.

        Inputs:
            None.

        Returns:
            The latest payload text, or `None` when no snapshot has been saved.

        Raises:
            CheckpointError on a read failure.

        Notes:
            Absence is reported as `None`, never as a fabricated empty snapshot.
        """
