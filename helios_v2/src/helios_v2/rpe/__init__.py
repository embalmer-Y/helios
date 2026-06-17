"""helios_v2.rpe — Real-RPE signal layer for P5-A.

Owner: R-PROTO-LEARN.P5-A.

Per ROADMAP 13.3 P5-A sub-rule 2, learning signals must be anchored
on dopamine reward prediction error defined by *real* runtime
consequences (execution outcomes / continuity progress / goal conflict
resolution) — not LLM appraisal.
"""

from helios_v2.rpe.contracts import (
    ConflictResolution,
    ContinuityMetric,
    ExecutionOutcome,
    RealRPEConfig,
    RealRPEError,
    RPESignal,
)
from helios_v2.rpe.mock_environment import mock_environment_tick, phase_label
from helios_v2.rpe.rpe_computer import compute_rpe

__all__ = [
    "ConflictResolution",
    "ContinuityMetric",
    "ExecutionOutcome",
    "RealRPEConfig",
    "RealRPEError",
    "RPESignal",
    "compute_rpe",
    "mock_environment_tick",
    "phase_label",
]