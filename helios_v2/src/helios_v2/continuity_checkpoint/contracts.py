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
from typing import Mapping, Protocol, runtime_checkable
from dataclasses import replace

from helios_v2.autonomy import ContinuityThread, DeferredContinuityRecord
from helios_v2.feeling import InteroceptiveFeelingVector
from helios_v2.neuromodulation import NeuromodulatorLevels
from helios_v2.thought_gating import ContinuationPressureState

# Current snapshot schema version. Bumped only when the snapshot's persisted shape changes
# in a way the facade's decode must branch on. The version is persisted so a loaded payload
# whose version does not match is rejected rather than silently migrated (R43: bumped to 2 to
# add the `04` neuromodulator levels; R44: bumped to 3 to add the `05` feeling; no migration,
# since no production data exists yet).
SNAPSHOT_VERSION = 4  # R43: bumped to 2 to add the 04 neuromodulator levels;
                   # R44: bumped to 3 to add the 05 feeling;
                   # R81: bumped to 4 to add the internal_monologue carry state.


class CheckpointError(RuntimeError):
    """Hard-stop error raised when runtime-continuity checkpoint invariants or backends fail."""




@dataclass(frozen=True)
class InternalMonologueCarryState:
    """One immutable snapshot of the LLM envelope carried across ticks.

    Owner: 42 continuity_checkpoint (lives in the snapshot module, not in
    22 composition, because the envelope persists in the checkpoint file).

    Construction:
        - last_envelope is the verbatim subset of the LLM JSON envelope
          produced by the v3 prompt path. May be None (v1 baseline) or a
          Mapping (v3 baseline).
        - last_tick_id is the tick_id when last_envelope was captured. None
          if no envelope has been captured yet.
        - i_want_to_think_more is a convenience projection of
          last_envelope["i_want_to_think_more"] (default False).
        - think_more_about is a convenience projection of
          last_envelope["think_more_about"] (default "").

    Failure semantics:
        - last_envelope must be a Mapping[str, object] or None. Any other
          type (str, int, list, etc.) raises CheckpointError.
        - i_want_to_think_more and think_more_about are coerced from
          last_envelope: missing key or wrong type -> False / "".
          These coercions do NOT raise.
        - last_tick_id must be None or a non-negative int.
    """

    last_envelope: "Mapping[str, object] | None"
    last_tick_id: "int | None"
    i_want_to_think_more: bool = False
    think_more_about: str = ""

    def __post_init__(self) -> None:
        if self.last_envelope is not None and not isinstance(self.last_envelope, Mapping):
            raise CheckpointError(
                "InternalMonologueCarryState.last_envelope must be a Mapping or None; "
                f"got {type(self.last_envelope).__name__}"
            )
        if self.last_tick_id is not None and self.last_tick_id < 0:
            raise CheckpointError(
                "InternalMonologueCarryState.last_tick_id must be >= 0 or None"
            )
        # Coerce convenience projections (no raise)
        if self.last_envelope is not None:
            v_iwttm = self.last_envelope.get("i_want_to_think_more", False)
            if not isinstance(v_iwttm, bool):
                v_iwttm = False
            object.__setattr__(self, "i_want_to_think_more", v_iwttm)
            v_tma = self.last_envelope.get("think_more_about", "")
            if not isinstance(v_tma, str):
                v_tma = ""
            object.__setattr__(self, "think_more_about", v_tma)


@dataclass(frozen=True)
class RuntimeContinuitySnapshot:
    """Owner: durable runtime-continuity checkpoint.

    Purpose:
        One immutable latest-state snapshot of the runtime's genuinely cross-tick continuity
        state at a given tick: the `09` continuation-pressure state, the `18`/`24` long-horizon
        continuity (deferred-continuity records plus continuity threads), (R43) the `04`
        neuromodulator levels, and (R44) the `05` interoceptive feeling.

    Failure semantics:
        Construction raises `CheckpointError` on a non-positive `snapshot_version`. The reused
        owner-contract fields (`continuation_state`, `deferred_records`, `continuity_threads`,
        `neuromodulator_levels`, `feeling`) are validated by their own owners' constructors, so an
        invalid value cannot reach this snapshot without that owner having raised first.

    Notes:
        This snapshot reuses the owners' own frozen contracts directly as its fields rather
        than inventing parallel shapes, so the owners remain the sole definition of their state
        shape and reconstruction runs their validation. It carries no authority and is never an
        inter-owner decision transport; it exists only so a restarted runtime can resume its
        prior cross-tick continuity. With R43/R44 the `04` neuromodulator levels and `05` feeling
        are included (now that both carry cross-tick state through their dual-timescale dynamics).
        `14`/`06` state remains out of scope: it is not cross-tick in-process state in the current
        runtime. The `snapshot_version` field is bumped when the shape changes; a loaded payload
        whose version does not match the current one is rejected rather than migrated.
    """

    tick_id: int | None
    continuation_state: ContinuationPressureState
    deferred_records: tuple[DeferredContinuityRecord, ...] = ()
    continuity_threads: tuple[ContinuityThread, ...] = ()
    neuromodulator_levels: NeuromodulatorLevels | None = None
    feeling: InteroceptiveFeelingVector | None = None
    internal_monologue: "InternalMonologueCarryState | None" = None
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


def _migrate_v3_to_v4(
    snapshot: "RuntimeContinuitySnapshot",
) -> "RuntimeContinuitySnapshot":
    """Migrate a v3 snapshot to v4 by setting internal_monologue=None.

    Behavior:
        - v4 input -> returns input unchanged (no-op)
        - v3 input -> returns replace(snapshot, internal_monologue=None, snapshot_version=4)
        - v<3 input -> raises CheckpointError (cannot retro-migrate past R43/R44)
        - v>4 input -> raises CheckpointError (forward-incompatible)
    """
    if snapshot.snapshot_version == 4:
        return snapshot
    if snapshot.snapshot_version == 3:
        return replace(
            snapshot,
            internal_monologue=None,
            snapshot_version=4,
        )
    raise CheckpointError(
        f"Cannot migrate v{snapshot.snapshot_version} snapshot to v4; "
        "supported: v3 (migrated) or v4 (no-op)"
    )
