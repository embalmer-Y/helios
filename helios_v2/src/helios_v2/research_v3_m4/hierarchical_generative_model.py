"""M4-T1 HierarchicalGenerativeModel(5 层 generative model)。

v3 design §2.2: 8 维 generative model(hierarchical)。

**简化版** (M4 阶段):
  - 5 层: sensory(8) → low(16) → mid(8) → high(4) → latent(2)
  - 每层是 linear projection + tanh
  - Top-down generate: 从 latent 重建 sensory
  - Bottom-up recognize: 从 sensory 推断 latent
  - 权重用 numpy 数组(stochastic gradient descent 训练)

**重要 caveat** (跟 v3 design §2.2 一致):
  - 这是简化版 generative model,用于 M4 阶段验证 proxy_free_energy
  - 真 VFE 用 PyMC/NumPyro variational inference(M8 阶段)
  - 当前实现的 "5 层" 是层级结构,不是 Friston 2010 严格分层
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple
import numpy as np


# === 5 层配置 ===

HGM_LAYER_DIMS: Tuple[int, ...] = (8, 16, 8, 4, 2)
"""5 层维度: sensory(8) → low(16) → mid(8) → high(4) → latent(2)。"""

HGM_LAYER_NAMES: Tuple[str, ...] = (
    "sensory", "low_level", "mid_level", "high_level", "latent"
)
"""5 层名称(从 bottom 到 top)。"""

DEFAULT_HGM_LR: float = 0.01
"""梯度下降学习率。"""


@dataclass
class HierarchicalGenerativeModel:
    """5 层 Hierarchical Generative Model (简化版)。

    Attributes:
        weights: 4 个 linear projection 权重矩阵(从 top 到 bottom)
            weights[0]: latent(2) → high(4)
            weights[1]: high(4) → mid(8)
            weights[2]: mid(8) → low(16)
            weights[3]: low(16) → sensory(8)
        biases: 4 个 bias 向量(对应每层除 sensory 外)
        forward_cache: 前向传播时缓存的中间激活(MSE 计算用)
        lr: 学习率
    """
    weights: list = field(default_factory=list)
    biases: list = field(default_factory=list)
    lr: float = DEFAULT_HGM_LR
    forward_cache: list = field(default_factory=list)
    last_recognition_error: float = 0.0

    def __post_init__(self):
        if not self.weights:
            self._init_weights()
        if not self.biases:
            self._init_biases()

    def _init_weights(self):
        """用小随机数初始化 4 个权重矩阵(从 latent 到 sensory)。

        HGM_LAYER_DIMS = (8, 16, 8, 4, 2) = (sensory, low, mid, high, latent)
        weights[0]: latent(2) → high(4)         shape (4, 2)
        weights[1]: high(4) → mid(8)            shape (8, 4)
        weights[2]: mid(8) → low(16)            shape (16, 8)
        weights[3]: low(16) → sensory(8)        shape (8, 16)
        """
        rng = np.random.default_rng(42)
        self.weights = []
        n_layers = len(HGM_LAYER_DIMS)
        for i in range(n_layers - 1):
            # weights[i] maps from layer (n_layers - 1 - i) to layer (n_layers - 2 - i)
            in_dim = HGM_LAYER_DIMS[n_layers - 1 - i]      # top-down source
            out_dim = HGM_LAYER_DIMS[n_layers - 2 - i]     # top-down target
            # Glorot initialization(scale ~ sqrt(2/(in+out)))
            scale = np.sqrt(2.0 / (in_dim + out_dim))
            W = rng.standard_normal((out_dim, in_dim)) * scale
            self.weights.append(W)

    def _init_biases(self):
        """bias 初始化为 0(对应每层除 latent 外的输出)。"""
        # biases[i] shape = HGM_LAYER_DIMS[n_layers - 2 - i]
        n_layers = len(HGM_LAYER_DIMS)
        self.biases = [
            np.zeros(HGM_LAYER_DIMS[n_layers - 2 - i])
            for i in range(n_layers - 1)
        ]

    def reset_cache(self):
        """清空前向缓存。"""
        self.forward_cache = []

    def generate(self, latent: np.ndarray) -> np.ndarray:
        """Top-down 生成: 从 latent 重建 sensory。

        Args:
            latent: (2,) 顶层 latent 状态

        Returns:
            (8,) sensory 重建
        """
        self.reset_cache()
        h = latent.copy()
        self.forward_cache.append(h)
        for W, b in zip(self.weights, self.biases):
            h = np.tanh(W @ h + b)
            self.forward_cache.append(h)
        return h  # 最后一层 = sensory 重建

    def recognize(self, sensory: np.ndarray) -> np.ndarray:
        """Bottom-up 识别: 从 sensory 推断 latent。

        Args:
            sensory: (8,) 感官输入

        Returns:
            (2,) latent 推断
        """
        # 用同一套权重但转置(简化,实际应 separate W_rec)
        # 反向传播:W[i] 形状 (out, in),W[i].T 形状 (in, out)
        # 反向顺序:从 sensory(8) → low(16) → mid(8) → high(4) → latent(2)
        h = sensory.copy()
        for W in reversed(self.weights):
            # W 形状 (out, in), W.T 形状 (in, out)
            # 当前 h 维度 = out,需要转换到 in
            h = np.tanh(W.T @ h)
        return h

    def compute_reconstruction(self, latent: np.ndarray, target: np.ndarray) -> np.ndarray:
        """计算 latent 给定时 sensory 的重建 + reconstruction error。

        Args:
            latent: (2,) 顶层 latent
            target: (8,) 目标 sensory(实际观察)

        Returns:
            reconstruction: (8,) 重建 sensory
            error: scalar reconstruction error (sum of squared diff)
        """
        reconstruction = self.generate(latent)
        error = float(np.sum((reconstruction - target) ** 2))
        return reconstruction, error

    def train_step(self, sensory: np.ndarray, latent: np.ndarray | None = None,
                   n_optim_steps: int = 1) -> float:
        """1 个 training step: 优化 latent 最小化 reconstruction error。

        用数值梯度(有限差分)避免手动实现 backprop。
        这是 M4 阶段简化实现,M8 真 VFE 用 PyMC 自动微分。

        Args:
            sensory: (8,) 目标 sensory
            latent: 初始 latent(None = 用 recognize 推断)
            n_optim_steps: latent optimization 步数

        Returns:
            final_reconstruction_error
        """
        if latent is None:
            latent = self.recognize(sensory)
        latent = latent.copy().astype(np.float64)

        for _ in range(n_optim_steps):
            grad = self._numerical_gradient(latent, sensory, eps=1e-4)
            latent = latent - self.lr * grad

        # Final reconstruction
        reconstruction, final_error = self.compute_reconstruction(latent, sensory)
        self.last_recognition_error = final_error
        return final_error

    def _numerical_gradient(self, latent: np.ndarray, target: np.ndarray,
                            eps: float = 1e-4) -> np.ndarray:
        """计算 reconstruction_error 对 latent 的数值梯度(中心差分)。"""
        grad = np.zeros_like(latent)
        for i in range(len(latent)):
            latent_plus = latent.copy()
            latent_plus[i] += eps
            _, err_plus = self.compute_reconstruction(latent_plus, target)

            latent_minus = latent.copy()
            latent_minus[i] -= eps
            _, err_minus = self.compute_reconstruction(latent_minus, target)

            grad[i] = (err_plus - err_minus) / (2 * eps)
        return grad

    def get_weights_summary(self) -> dict:
        """返回权重统计(用于 audit)。"""
        return {
            "weight_shapes": [W.shape for W in self.weights],
            "weight_norms": [float(np.linalg.norm(W)) for W in self.weights],
            "weight_max_abs": [float(np.max(np.abs(W))) for W in self.weights],
            "last_recognition_error": self.last_recognition_error,
            "lr": self.lr,
        }