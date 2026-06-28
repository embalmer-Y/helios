"""8 维耦合动力系统(Coupled Dynamical System, CDS)。

v3 plan §3.2 核心数据结构和 ODE 演化:
    ds/dt = -alpha * s + C · tanh(s) + beta * I + gamma * reflect
    R(t) = (1/8) * |sum exp(i * theta_i)|   (Kuramoto order parameter)
    theta_i = arctan(s_i / scale_i)

设计依据(v3 plan §3.2 + 03_v3_design §2):
- 8 维 PTS dimension:Bodily / Minimal-Experiential / Affective / Intersubjective /
  Psychological-Cognitive / Narrative / Ecological-Extended / Normative
- alpha 衰减率 5.0 → 0.01(快-慢差 500 倍,典型 stiff ODE,需 Radau solver)
- C 8x8 耦合矩阵(Reward-Hebbian 学习,见 update_C)
- Radau 自适应步长数值积分(rtol=1e-4, atol=1e-6)

本模块只 ship ODE 演化 + Kuramoto R 计算 + 基础 update_C;
跟 v2 owner 接入(M1-T8)推迟。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp


# 8 维 PTS dimension alpha 衰减率(从 v3 plan §3.2)
PTS_DIMENSION_NAMES: tuple[str, ...] = (
    "bodily_processes",           # 0 - alpha 5.0 (毫秒-秒)
    "minimal_experiential",       # 1 - alpha 2.0 (秒)
    "affective",                  # 2 - alpha 1.0 (秒-分钟)
    "intersubjective",            # 3 - alpha 0.5 (分钟)
    "psychological_cognitive",    # 4 - alpha 0.3 (分钟-小时)
    "narrative",                  # 5 - alpha 0.1 (小时-天)
    "ecological_extended",        # 6 - alpha 0.05 (周-月)
    "normative",                  # 7 - alpha 0.01 (年)
)

DEFAULT_ALPHA: np.ndarray = np.array([5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.01])

# Kuramoto R 计算的异构 scale(5 维快 + 3 维慢,需异构 scale 让相位统一可比)
# 来自 v3 plan 03_v3_design §2 self_experience
DEFAULT_KURAMOTO_SCALE: np.ndarray = np.array([1.0, 1.0, 1.0, 1.0, 1.0, 5.0, 10.0, 30.0])


@dataclass(frozen=True)
class CDSODEParams:
    """8 维 ODE 参数(v3 plan §3.2)。

    alpha 衰减率快-慢差 500 倍,需 Radau stiff solver。
    beta/gamma 默认为均匀权重;后续可调。
    """
    alpha: np.ndarray
    beta: np.ndarray
    gamma: np.ndarray
    rtol: float = 1e-4
    atol: float = 1e-6

    @classmethod
    def default(cls) -> "CDSODEParams":
        """默认参数(从 v3 plan §3.2)。"""
        return cls(
            alpha=DEFAULT_ALPHA.copy(),
            beta=np.array([1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]),
            gamma=np.full(8, 0.1),
            rtol=1e-4,
            atol=1e-6,
        )


class CoupledDynamicalSystem:
    """8 维耦合动力系统(CDS, v3 Layer 2 self-model 核心)。

    数学:
        ds/dt = -alpha * s + C · tanh(s) + beta * I + gamma * reflect
        R(t) = (1/8) * |sum exp(i * theta_i)|,  theta_i = arctan(s_i / scale_i)

    数值:
        solver = scipy.solve_ivp(method='Radau')
        原因:5 维快 + 3 维慢 stiff ODE,Radau 是工业标准 stiff solver

    学习:
        dC/dt = eta * reward * s * s^T (Reward-Hebbian)
    """

    def __init__(
        self,
        params: CDSODEParams | None = None,
        dt_tick: float = 1.0,
        initial_state: np.ndarray | None = None,
        initial_C: np.ndarray | None = None,
    ):
        self.params = params if params is not None else CDSODEParams.default()
        self.dt_tick = dt_tick
        # State 初始:全零(冷启动)
        self.state: np.ndarray = (
            initial_state.copy() if initial_state is not None else np.zeros(8)
        )
        # C 初始:弱对角耦合(每对 0.1)
        self.C: np.ndarray = (
            initial_C.copy() if initial_C is not None else np.eye(8) * 0.1
        )

    def tick(
        self,
        I: np.ndarray | None = None,
        reflect: np.ndarray | None = None,
        reward: float | None = None,
    ) -> dict:
        """每个 tick 演化 CDS + 可选更新 C。

        Args:
            I: 8 维外部刺激输入(默认全零)
            reflect: 8 维 Layer 3 反思调制(默认全零)
            reward: float,若提供则用 Reward-Hebbian 更新 C

        Returns:
            dict 含演化后的 state + Kuramoto R + Rochat level
        """
        if I is None:
            I = np.zeros(8)
        if reflect is None:
            reflect = np.zeros(8)

        sol = solve_ivp(
            fun=self._dynamics,
            t_span=(0, self.dt_tick),
            y0=self.state.copy(),
            args=(self.params, self.C, I, reflect),
            method="Radau",
            rtol=self.params.rtol,
            atol=self.params.atol,
        )
        if sol.success:
            # clip 防止极值
            new_state = np.clip(sol.y[:, -1], -10.0, 10.0)
            self.state = new_state
        else:
            # solver 失败,state 保持不变(诚实退化)
            pass

        if reward is not None:
            self.update_C(reward=reward, lr=0.01)

        return {
            "state": self.state.copy(),
            "kuramoto_R": self.kuramoto_R(),
            "rochat_level_continuous": self.kuramoto_R(),
            "rochat_level_discrete": int(self.kuramoto_R() * 5),
            "solver_success": sol.success,
            "solver_message": sol.message,
        }

    @staticmethod
    def _dynamics(t, s, params, C, I, reflect):
        """ODE 动力学函数(ds/dt = ...)。

        数值稳定性:输入 s clip 到 [-10, 10] 防止 tanh 饱和爆炸。
        """
        s_safe = np.clip(s, -10.0, 10.0)
        return (
            -params.alpha * s_safe
            + C @ np.tanh(s_safe)
            + params.beta * I
            + params.gamma * reflect
        )

    def kuramoto_R(self) -> float:
        """Kuramoto order parameter ∈ [0, 1]。

        R = (1/8) |sum exp(i * theta_i)|
        theta_i = arctan(s_i / scale_i)

        scale 异构补偿:慢维需要放大才能跟快维同步。
        R=1 完全同步(高 Rochat level),R=0 完全失相干(低 Rochat level)。
        """
        theta = np.arctan(self.state / DEFAULT_KURAMOTO_SCALE)
        return float(np.abs(np.sum(np.exp(1j * theta))) / 8.0)

    def update_C(self, reward: float, lr: float = 0.01) -> np.ndarray:
        """Reward-Hebbian 学习更新 C 矩阵。

        dC/dt ~ lr * reward * s * s^T

        归一化:若 |C|_max > 1.0,等比缩放到 1.0,防止发散。
        """
        delta_C = lr * reward * np.outer(self.state, self.state)
        self.C = self.C + delta_C
        max_abs = float(np.max(np.abs(self.C)))
        if max_abs > 1.0:
            self.C = self.C / max_abs
        return self.C

    def self_experience(self) -> dict:
        """self_experience 涌现态(给 LLM 被动接受)。"""
        R = self.kuramoto_R()
        return {
            "8d_state": self.state.tolist(),
            "global_coherence_R": R,
            "rochat_level_continuous": R,
            "rochat_level_discrete": int(R * 5),
            "self_unity": 1.0 - float(np.std(self.state)),
            "agency_strength": float(self.state[1]),
        }

    def seed_prior_state(self, state: np.ndarray, C: np.ndarray | None = None):
        """跨 tick carry(从 checkpoint 恢复)。

        Args:
            state: 8 维 numpy 数组
            C: 8x8 矩阵(可选)
        """
        if state.shape != (8,):
            raise ValueError(f"state shape must be (8,), got {state.shape}")
        self.state = state.copy()
        if C is not None:
            if C.shape != (8, 8):
                raise ValueError(f"C shape must be (8, 8), got {C.shape}")
            self.C = C.copy()
