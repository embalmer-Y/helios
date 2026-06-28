"""helios_v3 调研 M3 ship package。

M3 Boundary Owner (Layer 0 Markov Blanket) - v3 design §2.1 / task §2.1。

核心组件:
  - SignalType: 4 类信号 (sensory / active / internal / external)
  - Signal: 单条信号(signal_id, type, source, target, payload)
  - BoundaryCrossing: 一次边界穿越记录(audit log)
  - MarkovBlanketBoundary: 数学不变量验证(conditional_separation)
  - BoundaryOwner: 5 nested subsystems 共享 1 MB + check_signal + audit log
"""
from .signals import Signal, SignalType
from .markov_blanket import (
    MarkovBlanketBoundary,
    ConditionalSeparationResult,
    check_conditional_separation_partial_corr,
    check_conditional_separation_mutual_info,
)
from .boundary_owner import (
    BoundaryOwner,
    BoundaryCrossing,
    NestedSubsystem,
    DEFAULT_PARTIAL_CORR_THRESHOLD,
)

__all__ = [
    # Signals
    "Signal",
    "SignalType",
    # Markov Blanket
    "MarkovBlanketBoundary",
    "ConditionalSeparationResult",
    "check_conditional_separation_partial_corr",
    "check_conditional_separation_mutual_info",
    # Boundary Owner
    "BoundaryOwner",
    "BoundaryCrossing",
    "NestedSubsystem",
    "DEFAULT_PARTIAL_CORR_THRESHOLD",
]