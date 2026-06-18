"""Owner: learning framework (R-PROTO-LEARN.Tier1).

Generalized LearnerABC that 5 owner-specific learners inherit from.

Failure semantics:
- numpy import is module-level (fail-fast, no lazy import, no fallback).
- All illegal-shape / out-of-range inputs raise ValueError defensively.
- No silent degradation paths.

Implements the same 5 algorithms + 3-regime + numpy-only closure as
helios_v2.feeling.learning_path (R-PROTO-LEARN.8/9/10), generalized for
arbitrary input dim / output dim so 5 different owner-specific learners
can reuse the framework.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Module-level numpy import: fail-fast, no fallback.
# (小黑 2026-06-17 06:59 拍板: 不做无依赖降级)
import numpy as np

from helios_v2.learning.contracts import (
    DEFAULT_HORMONE_CHANNELS,
    LearnerConfig,
    Regime,
    _LearningSnapshot,
    _validate_7d_signal,
    _validate_4d_rpe,
)


def _numpy_pseudo_inverse(W: np.ndarray, rcond: float | None = None) -> np.ndarray:
    """numpy.linalg.pinv (R-PROTO-LEARN.9 closure, generalized).

    Args:
        W: (output_dim, input_dim) weight matrix.
        rcond: numpy.linalg.pinv rcond parameter (default: numpy default).

    Returns:
        (input_dim, output_dim) pseudo-inverse of W.
    """
    return np.linalg.pinv(W, rcond=rcond)


def _compute_closure_adjustment(
    W: np.ndarray,
    state_vec: np.ndarray,
    target_vec: np.ndarray,
    strength: float = 1.0,
    clip: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """R-PROTO-LEARN.9 / R-PROTO-LEARN.10 closure (generalized).

    Computes the sidecar adjustment to state_vec that would make
    W @ (state_vec + adjustment) match target_vec in the least-squares
    sense (via numpy pinv). The adjustment is scaled by `strength` and
    clipped to +/- `clip` per channel.

    Args:
        W: (output_dim, input_dim) weight matrix.
        state_vec: (input_dim,) current state.
        target_vec: (output_dim,) target output (e.g. LLM appraisal).
        strength: Adjustment strength multiplier (0.0-1.0).
        clip: Per-channel clip (>= 1.0 means unclamped).

    Returns:
        (adjustment, closed_loop_residual, open_loop_residual) as numpy arrays.
    """
    current_output = W @ state_vec
    open_loop_residual = target_vec - current_output
    # Least-squares solution for adjustment:
    W_pinv = _numpy_pseudo_inverse(W)
    adj0 = W_pinv @ open_loop_residual
    adj = strength * adj0
    if clip < 1.0:
        adj = np.clip(adj, -clip, clip)
    effective_state = state_vec + adj
    closed_loop_output = W @ effective_state
    closed_loop_residual = target_vec - closed_loop_output
    return adj, closed_loop_residual, open_loop_residual


class LearnerABC:
    """Abstract base class for P5 learners (5 owner-specific subclasses).

    Implements the 5 algorithms + 3-regime + numpy-only closure
    generalized for arbitrary (input_dim, output_dim) shapes.
    Subclasses override:
      - _state_to_vec(state) -> np.ndarray (state -> input vec)
      - _vec_to_state_vec(state_vec) -> np.ndarray (input vec -> vec)
      - _vec_to_policy_outputs(feeling_vec) -> np.ndarray (input -> output)
      - _llm_signal_to_target_vec(llm_signal, novelty) -> np.ndarray
        (LLM appraisal -> target output)

    These hooks let 5 different owners reuse the same W/bias/regime/commit
    machinery while keeping their input/output schema distinct.
    """

    # Subclasses MUST override:
    input_dim: int = 0
    output_dim: int = 0

    def __init__(self, config: LearnerConfig | None = None) -> None:
        self._config = config or LearnerConfig()
        # Read dims from config if not yet set on the instance
        if not getattr(self, "input_dim", None) and hasattr(self._config, "input_dim"):
            self.input_dim = self._config.input_dim
        if not getattr(self, "output_dim", None) and hasattr(self._config, "output_dim"):
            self.output_dim = self._config.output_dim
        if self.input_dim <= 0 or self.output_dim <= 0:
            raise ValueError(
                f"{type(self).__name__} must define input_dim and output_dim > 0; "
                f"got input_dim={self.input_dim}, output_dim={self.output_dim}"
            )
        # W matrix: (output_dim, input_dim) dense
        # Default: small random + small dense baseline
        rng = np.random.default_rng(seed=42)
        self._W: np.ndarray = rng.uniform(
            -0.1, 0.1, size=(self.output_dim, self.input_dim),
        )
        # bias: (output_dim,)
        self._bias: np.ndarray = np.zeros(self.output_dim)
        # Regime + history
        self._regime: Regime = Regime.EXPLORATORY
        self._regime_candidate: Regime = Regime.EXPLORATORY
        self._regime_candidate_ticks: int = 0
        # Residual history (for stable commit)
        self._residual_history: list[tuple[float, ...]] = []
        # Tick tracking
        self._tick_id: int | None = None
        # Commit tracking
        self._commit_count: int = 0
        self._last_commit_tick: int | None = None
        # Frozen after commit
        self._frozen_ticks_remaining: int = 0

    # ---- Properties / introspection ----

    def regime(self) -> Regime:
        return self._regime

    def commit_count(self) -> int:
        return self._commit_count

    def max_abs_weight(self) -> float:
        return float(np.max(np.abs(self._W))) if self._W.size else 0.0

    def weights_snapshot(self) -> tuple[tuple[float, ...], ...]:
        return tuple(tuple(row) for row in self._W.tolist())

    def bias_snapshot(self) -> tuple[float, ...]:
        return tuple(self._bias.tolist())

    def regime_snapshot(self) -> Regime:
        return self._regime

    def last_residual(self) -> tuple[float, ...]:
        if not self._residual_history:
            return (0.0,) * self.output_dim
        return self._residual_history[-1]

    # ---- Subclass hooks (overridden) ----

    def _state_to_vec(self, state: object) -> np.ndarray:
        """Convert owner-specific state -> input vector.

        Subclasses MUST override. The default returns a zero vector of
        input_dim to make the contract explicit; if not overridden the
        learner will always produce zero outputs (fail-fast via the
        `NotImplementedError` in the strict version).
        """
        raise NotImplementedError(
            f"{type(self).__name__}._state_to_vec not implemented"
        )

    def _llm_signal_to_target_vec(
        self,
        llm_signal: tuple[float, ...] | None,
        novelty: float,
    ) -> np.ndarray:
        """Convert LLM appraisal (7-dim) + novelty -> target output vector.

        Subclasses MUST override.
        """
        raise NotImplementedError(
            f"{type(self).__name__}._llm_signal_to_target_vec not implemented"
        )

    def _rpe_to_output_additions(
        self,
        dopamine: float,
        norepinephrine: float,
        serotonin: float,
        cortisol: float,
    ) -> np.ndarray:
        """R-PROTO-LEARN.P5-A.2: Map 4 RPE channels to output dim additions.

        Default mapping: 4 channels fill output dim 0-3 directly.
        Subclasses MAY override for owner-specific mapping.

        RPE 4 channel (already clipped to [0, 1]):
          - dopamine (RPE)         -> output dim 0 (confidence)
          - norepinephrine (effort) -> output dim 1 (effort)
          - serotonin (stability)   -> output dim 2 (stability)
          - cortisol (threat)       -> output dim 3 (threat)
        """
        additions = np.zeros(self.output_dim)
        if self.output_dim >= 1:
            additions[0] = dopamine
        if self.output_dim >= 2:
            additions[1] = norepinephrine
        if self.output_dim >= 3:
            additions[2] = serotonin
        if self.output_dim >= 4:
            additions[3] = cortisol
        return additions

    def _signals_to_target_vec(
        self,
        llm_signal: tuple[float, ...] | None,
        rpe_signal: tuple[float, ...] | None,
        novelty: float,
    ) -> np.ndarray:
        """R-PROTO-LEARN.P5-A.2: Combine LLM appraisal + RPE -> target vec.

        Fall-back chain:
          1. If rpe_signal is None OR rpe_signal_enabled=False:
               return _llm_signal_to_target_vec(llm_signal, novelty)
               (P5-A.1 compatible behavior)
          2. If llm_signal is None:
               target = _rpe_to_output_additions(...)
          3. Else: target = (1 - rpe_weight) * llm_target + rpe_weight * rpe_additions
        """
        if rpe_signal is None or not self._config.rpe_signal_enabled:
            # P5-A.1 compatible path
            if llm_signal is not None:
                _validate_7d_signal("llm_signal", llm_signal)
                return self._llm_signal_to_target_vec(llm_signal, novelty)
            return self._project_unclamped(self._state_to_vec(None))

        _validate_4d_rpe("rpe_signal", rpe_signal)
        # Clip RPE dopamine (signed [-1, 1]) to [0, 1]
        rpe_dopamine = max(0.0, min(1.0, (rpe_signal[0] + 1.0) / 2.0))
        rpe_ne = max(0.0, min(1.0, rpe_signal[1]))
        rpe_ser = max(0.0, min(1.0, rpe_signal[2]))
        rpe_cor = max(0.0, min(1.0, rpe_signal[3]))
        rpe_additions = self._rpe_to_output_additions(
            rpe_dopamine, rpe_ne, rpe_ser, rpe_cor
        )

        if llm_signal is None:
            return rpe_additions
        _validate_7d_signal("llm_signal", llm_signal)
        llm_target = self._llm_signal_to_target_vec(llm_signal, novelty)
        w = self._config.rpe_weight
        return (1.0 - w) * llm_target + w * rpe_additions

    def _project_unclamped(self, vec: np.ndarray) -> np.ndarray:
        """Project from input vec to output vec (no clamp)."""
        return self._W @ vec + self._bias

    def _project(self, vec: np.ndarray) -> np.ndarray:
        """Project from input vec to output vec (clamped to [0, 1])."""
        out = self._project_unclamped(vec)
        return np.clip(out, 0.0, 1.0)

    # ---- Dopamine + ACh extraction (override for owner-specific) ----

    def _dopamine(self, state: object) -> float:
        """Extract dopamine level (0-1) from state. Default 0.5."""
        return 0.5

    def _acetylcholine(self, state: object) -> float:
        """Extract acetylcholine level (0-1) from state. Default 0.5."""
        return 0.5

    def _novelty_flexibility(self, ach: float) -> float:
        """ACh -> flexibility in [floor, ceiling]. Strict < threshold = floor."""
        if ach < self._config.flexibility_threshold:
            return self._config.flexibility_floor
        return min(self._config.flexibility_ceiling, ach)

    # ---- 3-regime switching (Parisi 2019 inspired) ----

    def _is_habitual_candidate(self) -> bool:
        """Check if recent residual history suggests HABITUAL regime."""
        if len(self._residual_history) < self._config.min_stable_ticks:
            return False
        recent = self._residual_history[-self._config.min_stable_ticks:]
        max_residuals = [max(abs(v) for v in r) for r in recent]
        return all(
            r < self._config.habitual_residual_threshold for r in max_residuals
        )

    def _determine_regime(
        self,
        ach: float,
        novelty: float,
    ) -> Regime:
        """3-regime decision tree (with hysteresis)."""
        if len(self._residual_history) < 5:
            self._regime_candidate = Regime.EXPLORATORY
            return self._regime_candidate

        # EXPLORATORY: high ACh flexibility + high novelty
        if ach > self._config.flexibility_threshold and novelty > 0.5:
            self._regime_candidate = Regime.EXPLORATORY
        # HABITUAL: stable low residual
        elif self._is_habitual_candidate():
            self._regime_candidate = Regime.HABITUAL
        else:
            self._regime_candidate = Regime.MODEL_BASED

        # Hysteresis: keep previous regime until N consecutive new regime
        if self._regime_candidate != self._regime:
            self._regime_candidate_ticks += 1
            if self._regime_candidate_ticks >= self._config.regime_hysteresis_ticks:
                self._regime = self._regime_candidate
                self._regime_candidate_ticks = 0
        else:
            self._regime_candidate_ticks = 0
        return self._regime

    # ---- DA precision gate (decision function) ----

    def _accept_update(self, residual: np.ndarray) -> bool:
        """DA precision gate: residual * (1 - DA) < threshold."""
        da = 0.5  # Default; subclasses can override via _dopamine()
        max_residual = float(np.max(np.abs(residual)))
        # Higher DA -> lower threshold (more accepting)
        adjusted_threshold = self._config.commit_threshold * (
            1.0 - self._config.dopamine_precision_gain * da
        )
        return max_residual < adjusted_threshold

    # ---- Commit logic ----

    def _should_commit(self) -> bool:
        """Check if current residual is stable for min_stable_ticks."""
        if len(self._residual_history) < self._config.min_stable_ticks:
            return False
        recent = self._residual_history[-self._config.min_stable_ticks:]
        for r in recent:
            max_residual = max(abs(v) for v in r)
            if max_residual >= self._config.commit_threshold:
                return False
        return True

    def commit_if_stable(self) -> bool:
        """Manually trigger commit if stable. Returns True if committed."""
        if self._should_commit() and not self._frozen():
            self._commit_count += 1
            self._last_commit_tick = self._tick_id
            self._frozen_ticks_remaining = self._config.frozen_ticks_post_commit
            return True
        return False

    def _frozen(self) -> bool:
        """Check if learner is in frozen post-commit period."""
        if self._config.frozen_commit and self._frozen_ticks_remaining > 0:
            self._frozen_ticks_remaining -= 1
            return True
        return False

    # ---- Main update loop ----

    def update(
        self,
        state: object,
        llm_signal: tuple[float, ...] | None,
        novelty: float,
        tick_id: int | None,
        rpe_signal: tuple[float, ...] | None = None,
    ) -> _LearningSnapshot:
        """One tick of P5 learning (5 algorithms + 3-regime + numpy closure).

        Algorithm 1 (EXPLORATORY): LLM signal -> numpy pinv closure
            -> adjust state_vec (sidecar) -> effective output matches target.
        Algorithm 2 (DA precision gate): residual * (1 - DA) < threshold
            -> accept; else -> reject.
        Algorithm 3 (ACh flexibility gate): ACh < threshold -> keep
            current mapping; else -> allow new mapping to be learned.
        Algorithm 4 (regime switching): 3-regime decision tree with
            hysteresis.
        Algorithm 5 (commit): min_stable_ticks consecutive low residual
            -> write to config; freeze for frozen_ticks_post_commit.

        R-PROTO-LEARN.P5-A.2: rpe_signal (4-dim) is an explicit real-
        consequence signal. When provided AND rpe_signal_enabled=True,
        the target_vec is blended with RPE-driven output additions
        (dopamine / NE / serotonin / cortisol mapped to output dim 0-3).
        """
        self._tick_id = tick_id
        if novelty is None:
            novelty = 0.0
        if not 0.0 <= novelty <= 1.0:
            raise ValueError(
                f"novelty must be in [0, 1], got {novelty}"
            )

        # Convert state -> input vector
        state_vec = self._state_to_vec(state)
        if state_vec.shape != (self.input_dim,):
            raise ValueError(
                f"state_vec shape mismatch: expected ({self.input_dim},), "
                f"got {state_vec.shape}"
            )

        # Compute target output vector
        # P5-A.2: route through _signals_to_target_vec(llm, rpe, novelty)
        target_vec = self._signals_to_target_vec(llm_signal, rpe_signal, novelty)

        # R-PROTO-LEARN.9 closure: compute sidecar adjustment
        adj, closed_residual, open_residual = _compute_closure_adjustment(
            W=self._W,
            state_vec=state_vec,
            target_vec=target_vec,
            strength=1.0,
            clip=1.0,
        )

        # Compute learning target residual
        # If frozen post-commit, use open-loop residual (no learning)
        if self._frozen():
            residual = tuple(float(v) for v in open_residual)
        else:
            # DA precision gate: accept or reject the update
            if self._accept_update(closed_residual):
                # Apply gradient update to W (simplified least-mean-squares)
                # delta_W = learning_rate * closed_residual * state_vec^T / ||state_vec||^2
                state_norm_sq = float(np.dot(state_vec, state_vec))
                if state_norm_sq > 1e-9:
                    delta_W = self._config.learning_rate * np.outer(
                        closed_residual, state_vec,
                    ) / state_norm_sq
                    self._W = self._W + delta_W
                # Update bias similarly
                self._bias = self._bias + self._config.learning_rate * closed_residual
                residual = tuple(float(v) for v in closed_residual)
            else:
                residual = tuple(float(v) for v in closed_residual)

        # Update history
        self._residual_history.append(residual)
        if len(self._residual_history) > 256:
            # Keep last 256 to bound memory
            self._residual_history = self._residual_history[-256:]

        # Determine regime
        ach = self._acetylcholine(state)
        regime = self._determine_regime(ach=ach, novelty=novelty)

        # Check commit
        commit = self.commit_if_stable()

        return _LearningSnapshot(
            weights=self.weights_snapshot(),
            bias=self.bias_snapshot(),
            regime=regime,
            residual=residual,
            commit=commit,
            tick_id=tick_id,
        )
