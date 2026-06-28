"""M4-T2..T6 Active Inference Owner (Layer 1)。

v3 design §2.2 / task §2.2:
  - HierarchicalGenerativeModel (5 层)
  - proxy_free_energy (诚实的 proxy, NOT real VFE)
  - predict / compute_proxy_free_energy / minimize / active_sampling

**重要 DISCLAIMER**:
  - proxy_free_energy 是 prediction error² 的简化近似
  - **不是** Friston 2010 严格意义的 variational free energy
  - 真正的 VFE: F = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]
  - 真 VFE 实现见 `variational_free_energy_TRUE()` (placeholder for M8)
  - M8 阶段用 PyMC/NumPyro variational inference 替换
  - Reference: Friston 2010 (DOI: 10.1038/nrn2787)

为什么用 proxy:
  - M4 阶段需要可验证可证伪的 proxy
  - 真 VFE 实现复杂(PyMC + Bayesian inference)
  - proxy 已足够验证 v3 设计中"minimize F"的基本逻辑
  - M8 升级时,ActiveInferenceOwner 接口不变,只换实现
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable
import numpy as np

from .hierarchical_generative_model import HierarchicalGenerativeModel


# === Module-level proxy_free_energy 函数 ===

def proxy_free_energy(predicted: np.ndarray, actual: np.ndarray) -> float:
    """proxy_free_energy = sum of squared prediction error.

    **NOT** real variational free energy!

    Args:
        predicted: 预测 sensory(来自 HGM.generate)
        actual: 实际 sensory 观察

    Returns:
        scalar proxy F (sum of squared errors)

    Note:
        真 VFE = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]
        这里是简化版,只算 prediction error²,缺少 KL 项。
        见 `variational_free_energy_TRUE` for M8 placeholder.
    """
    error = predicted - actual
    return float(np.sum(error ** 2))


def compute_proxy_free_energy(hgm: HierarchicalGenerativeModel,
                              latent: np.ndarray,
                              actual: np.ndarray) -> float:
    """计算 HGM 在 latent 下生成 sensory 跟 actual 之间的 proxy F。"""
    predicted = hgm.generate(latent)
    return proxy_free_energy(predicted, actual)


# === ActionPolicy dataclass ===

@dataclass(frozen=True)
class ActionPolicy:
    """active sampling 输出的 action policy。"""
    action_id: str
    action_vector: np.ndarray  # 8-dim I(下一个 CDS tick 的输入)
    expected_proxy_free_energy: float
    confidence: float
    description: str = ""


@dataclass
class ActiveInferenceStats:
    """Active Inference 统计。"""
    n_ticks: int = 0
    n_predicts: int = 0
    n_minimizations: int = 0
    n_active_samplings: int = 0
    last_proxy_free_energy: float = 0.0
    proxy_free_energy_history: list = field(default_factory=list)
    latent_history: list = field(default_factory=list)
    policy_history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_ticks": self.n_ticks,
            "n_predicts": self.n_predicts,
            "n_minimizations": self.n_minimizations,
            "n_active_samplings": self.n_active_samplings,
            "last_proxy_free_energy": self.last_proxy_free_energy,
            "proxy_free_energy_history_size": len(self.proxy_free_energy_history),
            "latent_history_size": len(self.latent_history),
            "policy_history_size": len(self.policy_history),
        }


class ActiveInferenceOwner:
    """Layer 1 Active Inference Owner (M4 简化版)。

    关键设计:
      1. **接口跟 v3.1 真 VFE 兼容**:有 `variational_free_energy_TRUE` placeholder
      2. **诚实标注**:每个返回 proxy F 的方法都明确标注 "proxy, NOT real VFE"
      3. **5 层 HGM**:从 sensory 推断 latent,生成预测
      4. **policy gradient active sampling**:基于 expected proxy F 选 action

    协作模式:
      ```python
      ai = ActiveInferenceOwner()
      for tick in range(n):
          # 1. predict
          predicted = ai.predict(sensory_input)
          # 2. minimize(可选,在没有 reflective owner 时跳过)
          latent = ai.minimize_proxy_free_energy(sensory_input, n_steps=3)
          # 3. active sampling - 选下一个 I
          policy = ai.active_sampling(sensory_input, n_candidates=5)
          # 4. 输出 policy.action_vector 给 SelfModelOwner.tick(I=...)
      ```
    """

    def __init__(self, hgm: Optional[HierarchicalGenerativeModel] = None,
                 lr: float = 0.01,
                 n_minimization_steps: int = 3,
                 seed: int = 42):
        self.hgm = hgm if hgm is not None else HierarchicalGenerativeModel(lr=lr)
        self.lr = lr
        self.n_minimization_steps = n_minimization_steps
        self._rng = np.random.default_rng(seed)
        self.stats = ActiveInferenceStats()
        self._current_latent: Optional[np.ndarray] = None

    # === 4 大方法 ===

    def predict(self, sensory_input: np.ndarray) -> np.ndarray:
        """预测:用当前 latent 生成 sensory 重建。

        Args:
            sensory_input: (8,) 感官输入(用于 context)

        Returns:
            (8,) HGM 的 sensory 重建(预测)
        """
        # 用 recognize 从 sensory 推断 latent,然后 generate
        latent = self.hgm.recognize(sensory_input)
        self._current_latent = latent
        predicted = self.hgm.generate(latent)
        self.stats.n_predicts += 1
        self.stats.latent_history.append(latent.tolist())
        return predicted

    def compute_proxy_free_energy(self, sensory_input: np.ndarray) -> float:
        """计算 proxy F(基于 sensory input 跟 HGM 预测的差异)。

        **这是 proxy, NOT real variational free energy!**

        Args:
            sensory_input: (8,) 感官输入

        Returns:
            scalar proxy F
        """
        if self._current_latent is None:
            latent = self.hgm.recognize(sensory_input)
        else:
            latent = self._current_latent
        predicted = self.hgm.generate(latent)
        f_proxy = proxy_free_energy(predicted, sensory_input)
        self.stats.last_proxy_free_energy = f_proxy
        self.stats.proxy_free_energy_history.append(f_proxy)
        return f_proxy

    def minimize_proxy_free_energy(self, sensory_input: np.ndarray,
                                    n_steps: Optional[int] = None) -> np.ndarray:
        """最小化 proxy F:通过 gradient descent 调整 latent。

        **注意**:这是 proxy F minimization, NOT real VFE minimization。
        M8 升级时此接口不变,只换实现。

        Args:
            sensory_input: (8,) 感官输入
            n_steps: 优化步数(None = 用 self.n_minimization_steps)

        Returns:
            (2,) 优化后的 latent
        """
        steps = n_steps if n_steps is not None else self.n_minimization_steps
        # 用 HGM.train_step 做 latent optimization
        # train_step 内部已经做 numerical gradient descent
        final_error = self.hgm.train_step(
            sensory=sensory_input,
            latent=None,  # 用 recognize 推断初始
            n_optim_steps=steps,
        )
        self.stats.n_minimizations += 1
        self.stats.last_proxy_free_energy = final_error
        self.stats.proxy_free_energy_history.append(final_error)
        # 重新 generate 用最新的 latent
        # 注意: train_step 已经更新过 latent 但没缓存到 _current_latent
        # 简化:再次 recognize + generate
        new_latent = self.hgm.recognize(sensory_input)
        self._current_latent = new_latent
        self.stats.latent_history.append(new_latent.tolist())
        return new_latent

    def active_sampling(self, sensory_input: np.ndarray, n_candidates: int = 5,
                         exploration_noise: float = 0.1) -> ActionPolicy:
        """Active sampling: 选下一个 I 输入(基于 expected proxy F)。

        **策略**:采样 n_candidates 个候选 action,选 expected proxy F 最低的。

        Args:
            sensory_input: (8,) 当前 sensory
            n_candidates: 候选 action 数量
            exploration_noise: 探索噪声(std)

        Returns:
            ActionPolicy(选中的 action + 期望 F)
        """
        candidates = []
        expected_Fs = []

        # 当前 latent 作为 reference
        current_latent = self._current_latent
        if current_latent is None:
            current_latent = self.hgm.recognize(sensory_input)

        for _ in range(n_candidates):
            # 候选 action = 随机扰动
            candidate_action = self._rng.standard_normal(8) * exploration_noise
            candidate_action = np.clip(candidate_action, -1.0, 1.0)

            # 模拟"如果应用此 action,预期 sensory 是什么"
            # 简化:用 candidate_action 作为微小 I 输入到当前 latent
            # 这里只粗略估计:expected_F = current_F + penalty(action magnitude)
            base_F = self.stats.last_proxy_free_energy if self.stats.last_proxy_free_energy > 0 else 1.0
            penalty = float(np.sum(candidate_action ** 2)) * 0.1
            expected_F = base_F + penalty + self._rng.standard_normal() * 0.05

            candidates.append(candidate_action)
            expected_Fs.append(expected_F)

        # 选 expected_F 最小的
        best_idx = int(np.argmin(expected_Fs))
        best_action = candidates[best_idx]

        policy = ActionPolicy(
            action_id=str(uuid.uuid4()),
            action_vector=best_action,
            expected_proxy_free_energy=float(expected_Fs[best_idx]),
            confidence=float(1.0 / (1.0 + expected_Fs[best_idx])),
            description=f"argmin over {n_candidates} candidates, F={expected_Fs[best_idx]:.4f}",
        )
        self.stats.n_active_samplings += 1
        self.stats.policy_history.append(policy.action_id)
        return policy

    # === M8 placeholder ===

    def variational_free_energy_TRUE(self) -> float:
        """真 VFE placeholder(M8 升级用)。

        M8 阶段用 PyMC/NumPyro variational inference 实现:
          F = D_KL[q(s|o) || p(s)] - E_q[ln p(o|s)]

        当前 raises NotImplementedError。

        Raises:
            NotImplementedError: M8 升级时实现
        """
        raise NotImplementedError(
            "variational_free_energy_TRUE() is a M8 placeholder. "
            "M4 stage uses proxy_free_energy() which is a simplified "
            "approximation (prediction error²), NOT real VFE. "
            "Reference: Friston 2010 (DOI: 10.1038/nrn2787)"
        )

    # === 工具 ===

    def tick(self, sensory_input: np.ndarray, do_minimize: bool = True,
             do_active_sampling: bool = True) -> dict:
        """1 个 AI tick: predict + (optional) minimize + (optional) active sampling。

        Returns:
            dict 含 predicted / proxy_free_energy / latent / policy(可能 None)
        """
        result = {
            "tick": self.stats.n_ticks,
            "predicted": None,
            "proxy_free_energy": None,
            "latent": None,
            "policy": None,
        }

        # 1. predict
        predicted = self.predict(sensory_input)
        result["predicted"] = predicted

        # 2. compute proxy F(based on prediction)
        f_proxy = self.compute_proxy_free_energy(sensory_input)
        result["proxy_free_energy"] = f_proxy

        # 3. minimize(可选)
        if do_minimize:
            latent = self.minimize_proxy_free_energy(sensory_input)
            result["latent"] = latent

        # 4. active sampling(可选)
        if do_active_sampling:
            policy = self.active_sampling(sensory_input)
            result["policy"] = policy

        self.stats.n_ticks += 1
        return result

    def get_stats(self) -> dict:
        return self.stats.to_dict()

    def get_proxy_free_energy_history(self) -> list:
        return list(self.stats.proxy_free_energy_history)

    def is_proxy_free_energy_monotonically_decreasing(self, last_n: int = 50,
                                                       tolerance: float = 0.0) -> bool:
        """检查最近 last_n 个 proxy F 值是否单调下降(tolerance 容许小波动)。

        Returns:
            True if all consecutive diffs <= tolerance
        """
        history = self.stats.proxy_free_energy_history[-last_n:]
        if len(history) < 2:
            return True  # 太短,无法判断
        diffs = np.diff(history)
        return bool(np.all(diffs <= tolerance))