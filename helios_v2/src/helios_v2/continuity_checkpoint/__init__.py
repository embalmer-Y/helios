"""Owner: durable runtime-continuity checkpoint.

Public surface for the durable latest-state runtime-continuity checkpoint owner. It keeps one
latest-state snapshot of the genuinely cross-tick continuity state (`09` continuation pressure,
`18`/`24` long-horizon continuity) and restores it on restart, advancing `FG-5.1` subjective
restart continuity. It is infrastructure, like `21` observability and `33` persistence; it holds
no cognitive policy.
"""

from .contracts import (
    SNAPSHOT_VERSION,
    CheckpointError,
    CheckpointStoreBackend,
    RuntimeContinuitySnapshot,
)
from .engine import (
    ContinuityCheckpointStore,
    InMemoryCheckpointBackend,
    SqliteCheckpointBackend,
    decode_snapshot,
    encode_snapshot,
)

__all__ = [
    "SNAPSHOT_VERSION",
    "CheckpointError",
    "CheckpointStoreBackend",
    "RuntimeContinuitySnapshot",
    "ContinuityCheckpointStore",
    "InMemoryCheckpointBackend",
    "SqliteCheckpointBackend",
    "encode_snapshot",
    "decode_snapshot",
]
