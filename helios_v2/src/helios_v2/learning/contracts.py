"""Owner: learning framework (R-PROTO-LEARN.Tier1).

Unified learning contract for 5 owners (06 memory / 09 thought_gating /
10 directed_retrieval / 11 internal_thought / 18 autonomy).

Each owner gets a LearnerABC subclass that:
  1. accepts the owner-specific state
  2. accepts the LLM appraisal (or owner-specific signal) as ground truth
  3. updates a private W matrix (state -> policy output) and bias
  4. uses numpy-only closure (no fallback, fail-fast)
  5. maintains 3 regimes (EXPLORATORY / MODEL_BASED / HABITUAL)
  6. is a sidecar / opt-in: never modifies the canonical owner state

Owns:
- LearnerConfig (frozen dataclass with 11 hyperparameters)
- Regime enum (3 states)
- Learner Protocol (duck-typed interface)
- _LearningSnapshot (frozen dataclass for introspection)
- _HormoneAdjustment (named result tuple)

Does not own:
- canonical owner state (R85 4 layer / R43 dual-timescale / R70)
- LLM appraisal paths (R-PROTO-LEARN.2 owner 03)
- composition/runtime_assembly (R85 composition root)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable


class Regime(Enum):
    """Three-state regime for P5 learning (Parisi 2019 inspired)."""
    EXPLORATORY = "exploratory"
    MODEL_BASED = "model_based"
    HABITUAL = "habitual"


@dataclass(frozen=True)
class LearnerConfig:
    """Unified learner config for all 5 P5 owners.

    All 11 hyperparameters are the same defaults across owners,
    matching the P5-feel R-PROTO-LEARN.8/9 calibration.
    """
    # 1. Learning rate
    learning_rate: float = 0.05
    # 2. Commit threshold (residual must be < this for N consecutive ticks)
    commit_threshold: float = 0.3
    # 3. Min stable ticks before commit
    min_stable_ticks: int = 8
    # 4. Frozen ticks after commit (no further update)
    frozen_ticks_post_commit: int = 5
    # 5. Regime hysteresis (consecutive ticks required to switch regime)
    regime_hysteresis_ticks: int = 2
    # 6. ACh flexibility threshold (above -> learn new mapping)
    flexibility_threshold: float = 0.3
    # 7. ACh flexibility floor
    flexibility_floor: float = 0.1
    # 8. ACh flexibility ceiling
    flexibility_ceiling: float = 1.0
    # 9. Dopamine precision gain
    dopamine_precision_gain: float = 0.3
    # 10. Frozen commit (block learning after first commit)
    frozen_commit: bool = True
    # 11. Habitual residual threshold
    habitual_residual_threshold: float = 0.5

    def __post_init__(self) -> None:
        # Defensive validation (fail-fast, no silent degradation)
        if not 0.0 < self.learning_rate <= 1.0:
            raise ValueError(
                f"learning_rate must be in (0, 1], got {self.learning_rate}"
            )
        if not 0.0 < self.commit_threshold <= 1.0:
            raise ValueError(
                f"commit_threshold must be in (0, 1], got {self.commit_threshold}"
            )
        if self.min_stable_ticks < 1:
            raise ValueError(
                f"min_stable_ticks must be >= 1, got {self.min_stable_ticks}"
            )
        if self.frozen_ticks_post_commit < 0:
            raise ValueError(
                f"frozen_ticks_post_commit must be >= 0, "
                f"got {self.frozen_ticks_post_commit}"
            )
        if not 0.0 <= self.flexibility_floor < self.flexibility_ceiling <= 1.0:
            raise ValueError(
                f"flexibility_floor < flexibility_ceiling <= 1.0 required, "
                f"got {self.flexibility_floor} < {self.flexibility_ceiling}"
            )


@runtime_checkable
class Learner(Protocol):
    """Duck-typed interface every P5 learner must satisfy.

    5 owners each implement this protocol via a LearnerABC subclass.
    """

    def update(
        self,
        state: object,
        llm_signal: tuple[float, ...] | None,
        novelty: float,
        tick_id: int | None,
    ) -> "_LearningSnapshot":
        """One tick of P5 learning.

        Args:
            state: Owner-specific state (canonical, read-only for learner).
            llm_signal: 7-dim LLM appraisal or owner-specific signal.
            novelty: [0, 1] novelty value (drives ACh flexibility).
            tick_id: Current tick id (or None).

        Returns:
            _LearningSnapshot with W/bias/regime/residual/commit.
        """
        ...

    def regime(self) -> Regime: ...
    def commit_count(self) -> int: ...
    def max_abs_weight(self) -> float: ...


@dataclass(frozen=True)
class _LearningSnapshot:
    """Frozen snapshot of a learner tick (for introspection / tests)."""
    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, ...]
    regime: Regime
    residual: tuple[float, ...]
    commit: bool
    tick_id: int | None


@dataclass(frozen=True)
class _HormoneAdjustment:
    """Result of a hormone adjustment computation (numpy-only)."""
    adjustment: tuple[float, ...]
    closed_loop_residual: tuple[float, ...]
    open_loop_residual: tuple[float, ...]


# Default mapping of canonical neuromodulator channels (9 channels).
# Mirrors helios_v2.feeling.learning_path.HORMONE_CHANNELS.
DEFAULT_HORMONE_CHANNELS: tuple[str, ...] = (
    "dopamine", "norepinephrine", "serotonin", "acetylcholine",
    "cortisol", "oxytocin", "opioid_tone", "excitation", "inhibition",
)


def _validate_7d_signal(name: str, signal: tuple[float, ...] | None) -> None:
    """Defensive validation for 7-dim LLM appraisal signals."""
    if signal is None:
        return
    if len(signal) != 7:
        raise ValueError(
            f"{name} must be 7-dim, got {len(signal)}"
        )
    for i, v in enumerate(signal):
        if not 0.0 <= v <= 1.0:
            raise ValueError(
                f"{name}[{i}] must be in [0, 1], got {v}"
            )
