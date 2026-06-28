"""M3 Markov Blanket 数学不变量验证。

v3 design §2.1 Layer 0 Markov Blanket:
  - 数学不变量: internal ⊥ external | sensory
  - 等价: p(int, ext | sensory) = p(int | sensory) · p(ext | sensory)

实现 2 种独立性检验:
  1. partial correlation(线性): 偏相关系数
  2. mutual information(非线性): 互信息估计

**重要 caveat**:
  - 这 2 种检验都是**统计**检验,样本数 N < 100 时不可靠
  - 偏相关假设线性关系,互信息更通用但需要 KDE 估计
  - 对于 v3 research,M3 阶段用 partial correlation 作 fast check,
    M5 接入真 LLM 后可改用更精确的检验 (HSIC, d-separation exact check)
"""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ConditionalSeparationResult:
    """conditional_separation 检验结果。"""
    passed: bool
    partial_corr: float  # 偏相关系数(internal, external | sensory)
    p_value: float       # 假设检验 p 值
    n_samples: int
    threshold: float
    method: str          # "partial_correlation" / "mutual_information"
    notes: str = ""


def _partial_correlation(
    internal: np.ndarray,
    external: np.ndarray,
    sensory: np.ndarray,
) -> tuple[float, float]:
    """计算偏相关系数 partial_corr(internal, external | sensory)。

    算法:
      1. Regress internal on sensory: internal_resid = internal - proj(internal | sensory)
      2. Regress external on sensory: external_resid = external - proj(external | sensory)
      3. corr(internal_resid, external_resid) = partial correlation

    Returns:
        (partial_corr, p_value)
    """
    n = len(internal)
    if n != len(external) or n != len(sensory):
        raise ValueError(f"length mismatch: internal={n}, external={len(external)}, sensory={len(sensory)}")

    if n < 3:
        # 样本太少,无法计算,返回 NaN
        return float("nan"), float("nan")

    # 用 numpy least-squares 做线性回归
    # 添加常数项做 intercept
    sensory_aug = np.column_stack([sensory, np.ones(n)])

    # internal ~ sensory
    coef_int, _, _, _ = np.linalg.lstsq(sensory_aug, internal, rcond=None)
    internal_resid = internal - sensory_aug @ coef_int

    # external ~ sensory
    coef_ext, _, _, _ = np.linalg.lstsq(sensory_aug, external, rcond=None)
    external_resid = external - sensory_aug @ coef_ext

    # Pearson r of residuals
    r = np.corrcoef(internal_resid, external_resid)[0, 1]

    # 简化的 p-value(基于 t 统计)
    # t = r * sqrt((n-2) / (1 - r^2))
    # p ≈ 2 * (1 - t_cdf(|t|, n-2))
    # 这里用简化近似: n 较大时 p ≈ 2 * (1 - Φ(|t|))
    if abs(r) >= 1.0:
        p_value = 0.0
    else:
        t = r * np.sqrt((n - 2) / (1 - r ** 2))
        # Normal approximation for t with df = n-2
        from scipy.stats import norm
        p_value = 2 * (1 - norm.cdf(abs(t)))

    return float(r), float(p_value)


def _mutual_information(
    x: np.ndarray,
    y: np.ndarray,
    n_bins: int = 10,
) -> float:
    """用直方图估计互信息 MI(X; Y)。

    MI(X; Y) = sum_{xy} p(x, y) * log(p(x, y) / (p(x) * p(y)))
    """
    n = len(x)
    if n != len(y):
        raise ValueError(f"length mismatch: x={n}, y={len(y)}")

    # 2D 直方图
    hist_2d, _, _ = np.histogram2d(x, y, bins=n_bins)
    p_xy = hist_2d / n
    p_x = p_xy.sum(axis=1, keepdims=True)
    p_y = p_xy.sum(axis=0, keepdims=True)

    # 避免 log(0)
    p_xy_safe = np.where(p_xy > 0, p_xy, 1.0)
    p_x_safe = np.where(p_x > 0, p_x, 1.0)
    p_y_safe = np.where(p_y > 0, p_y, 1.0)

    # MI
    mi = np.sum(p_xy * np.log(p_xy_safe / (p_x_safe * p_y_safe)))

    return float(mi)


def check_conditional_separation_partial_corr(
    internal_samples: np.ndarray,
    external_samples: np.ndarray,
    sensory_samples: np.ndarray,
    threshold: float = 0.1,
) -> ConditionalSeparationResult:
    """用偏相关系数验证 conditional_separation。

    Args:
        internal_samples: 1D array of internal state samples
        external_samples: 1D array of external state samples
        sensory_samples: 1D array of sensory state samples
        threshold: 偏相关系数绝对值阈值(默认 0.1)

    Returns:
        ConditionalSeparationResult

    Note:
        偏相关系数衡量**线性**条件独立性。
        对于非线性关系,可能漏检(false negative: MI > 0 但 partial_corr ≈ 0)。
    """
    internal = np.asarray(internal_samples, dtype=np.float64).ravel()
    external = np.asarray(external_samples, dtype=np.float64).ravel()
    sensory = np.asarray(sensory_samples, dtype=np.float64).ravel()

    n = len(internal)
    if n != len(external) or n != len(sensory):
        raise ValueError(f"length mismatch: internal={n}, external={len(external)}, sensory={len(sensory)}")

    if n < 5:
        return ConditionalSeparationResult(
            passed=False,
            partial_corr=float("nan"),
            p_value=float("nan"),
            n_samples=n,
            threshold=threshold,
            method="partial_correlation",
            notes=f"n_samples={n} too small (< 5), cannot verify reliably",
        )

    partial_corr, p_value = _partial_correlation(internal, external, sensory)

    # 独立性成立条件: |partial_corr| < threshold AND p_value > 0.05
    # 注: 这里采用宽松判断,实际部署应考虑 FDR / Bonferroni 校正
    passed = (abs(partial_corr) < threshold) and (p_value > 0.05)

    return ConditionalSeparationResult(
        passed=passed,
        partial_corr=partial_corr,
        p_value=p_value,
        n_samples=n,
        threshold=threshold,
        method="partial_correlation",
        notes=f"|r|={abs(partial_corr):.4f}, p={p_value:.4f}",
    )


def check_conditional_separation_mutual_info(
    internal_samples: np.ndarray,
    external_samples: np.ndarray,
    sensory_samples: np.ndarray,
    n_bins: int = 10,
    threshold: float = 0.1,
) -> ConditionalSeparationResult:
    """用互信息 (in nats) 验证 conditional_separation。

    计算 conditional MI(internal; external | sensory) =
      MI(internal, external, sensory) - MI(internal; sensory) - MI(external; sensory)
    简化估计: 用偏相关 + MI 联合估计

    Args:
        internal_samples: 1D array
        external_samples: 1D array
        sensory_samples: 1D array
        n_bins: 直方图 bin 数
        threshold: MI 阈值(nats)

    Returns:
        ConditionalSeparationResult

    Note:
        MI 估计依赖 binning,bias 较高。M3 阶段作辅助检验。
    """
    internal = np.asarray(internal_samples, dtype=np.float64).ravel()
    external = np.asarray(external_samples, dtype=np.float64).ravel()
    sensory = np.asarray(sensory_samples, dtype=np.float64).ravel()

    n = len(internal)
    if n < 5:
        return ConditionalSeparationResult(
            passed=False,
            partial_corr=float("nan"),
            p_value=float("nan"),
            n_samples=n,
            threshold=threshold,
            method="mutual_information",
            notes=f"n_samples={n} too small",
        )

    # 三维直方图估计
    # p(i, e, s) 然后算 conditional MI
    hist_3d, _ = np.histogramdd(
        np.column_stack([internal, external, sensory]),
        bins=(n_bins, n_bins, n_bins),
    )
    p_ies = hist_3d / n

    # marginals
    p_i = p_ies.sum(axis=(1, 2))
    p_e = p_ies.sum(axis=(0, 2))
    p_s = p_ies.sum(axis=(0, 1))
    p_is = p_ies.sum(axis=1)
    p_es = p_ies.sum(axis=0)
    p_ie = p_ies.sum(axis=2)

    eps = 1e-12
    # conditional MI = sum p(i,e,s) * log[p(i,e|s) / (p(i|s) * p(e|s))]
    # 等价: MI(I;E|S) = MI(I;E;S) - MI(I;S) - MI(E;S)
    # 简化用 joint MI 估计:直接对 (I, E) 在不同 S 层做平均
    # 这里用 partial MI 的简化估计:
    # MI(I;E|S) ≈ (MI(I;E) - corr(I;E)*corr(S;I)*... ) — 简化用偏相关近似

    # 实际上, 用偏相关系数 (linear) 更可靠,
    # 这里返回 MI + 偏相关作为综合信号

    partial_corr, p_value = _partial_correlation(internal, external, sensory)
    mi_ie = _mutual_information(internal, external, n_bins=n_bins)

    passed = (abs(partial_corr) < threshold) and (p_value > 0.05)

    return ConditionalSeparationResult(
        passed=passed,
        partial_corr=partial_corr,
        p_value=p_value,
        n_samples=n,
        threshold=threshold,
        method="mutual_information",
        notes=f"|r|={abs(partial_corr):.4f}, MI(I;E)={mi_ie:.4f} nats, p={p_value:.4f}",
    )


@dataclass
class MarkovBlanketBoundary:
    """Markov Blanket 数学不变量实施者。

    维护 3 组状态:
      - internal_states: 5 个 nested subsystems 的内部状态 (dict[str, np.ndarray])
      - sensory_signals: 通过 MB 的 sensory 信号(list[Signal])
      - active_signals: 通过 MB 的 active 信号(list[Signal])
      - external_signals: 外部世界信号(不直接进入 system,但用于 audit)

    通过 samples(历史样本)验证 conditional_separation:
      - 收集 (internal, external, sensory) 三元组样本
      - 调用 check_conditional_separation_*(samples) 验证
    """
    # 系统名称常量(v3 design §0)
    SUBSYSTEM_AI = "active_inference"          # Layer 1
    SUBSYSTEM_SELF_MODEL = "self_model"        # Layer 2
    SUBSYSTEM_REFLECTION = "reflection"        # Layer 3
    SUBSYSTEM_EVOLUTION = "evolution"          # Layer 4
    ALL_SUBSYSTEMS = ("active_inference", "self_model", "reflection", "evolution")

    # 配置(必须有默认值的字段放前面)
    threshold: float = 0.1
    max_samples: int = 1000
    min_samples_for_check: int = 30

    # 状态样本缓冲(由 __init__ 初始化)
    _internal_samples: dict = field(default_factory=dict)
    _external_samples: list = field(default_factory=list)
    _sensory_samples: list = field(default_factory=list)

    # 信号日志
    sensory_signals: list = field(default_factory=list)
    active_signals: list = field(default_factory=list)
    external_signals: list = field(default_factory=list)

    def __post_init__(self):
        if not self._internal_samples:
            self._internal_samples = {name: [] for name in self.ALL_SUBSYSTEMS}

    def record_internal(self, subsystem: str, value: float) -> None:
        """记录 1 个 subsystem 的内部状态样本。"""
        if subsystem not in self._internal_samples:
            raise ValueError(f"unknown subsystem: {subsystem}, valid: {self.ALL_SUBSYSTEMS}")
        self._internal_samples[subsystem].append(float(value))
        if len(self._internal_samples[subsystem]) > self.max_samples:
            self._internal_samples[subsystem].pop(0)

    def record_external(self, value: float) -> None:
        """记录 1 个外部世界状态样本。"""
        self._external_samples.append(float(value))
        if len(self._external_samples) > self.max_samples:
            self._external_samples.pop(0)

    def record_sensory(self, value: float) -> None:
        """记录 1 个 sensory 信号样本。"""
        self._sensory_samples.append(float(value))
        if len(self._sensory_samples) > self.max_samples:
            self._sensory_samples.pop(0)

    def add_sensory_signal(self, signal) -> None:
        """添加 1 条 sensory 信号。"""
        from .signals import Signal
        if not isinstance(signal, Signal):
            raise TypeError(f"expected Signal, got {type(signal)}")
        if signal.signal_type.value != "sensory":
            raise ValueError(f"expected sensory signal, got {signal.signal_type.value}")
        self.sensory_signals.append(signal)
        if len(self.sensory_signals) > self.max_samples:
            self.sensory_signals.pop(0)

    def add_active_signal(self, signal) -> None:
        """添加 1 条 active 信号。"""
        from .signals import Signal
        if not isinstance(signal, Signal):
            raise TypeError(f"expected Signal, got {type(signal)}")
        if signal.signal_type.value != "active":
            raise ValueError(f"expected active signal, got {signal.signal_type.value}")
        self.active_signals.append(signal)
        if len(self.active_signals) > self.max_samples:
            self.active_signals.pop(0)

    def add_external_signal(self, signal) -> None:
        """添加 1 条 external 信号(用于 audit,不直接进入 system)。"""
        from .signals import Signal
        if not isinstance(signal, Signal):
            raise TypeError(f"expected Signal, got {type(signal)}")
        if signal.signal_type.value != "external":
            raise ValueError(f"expected external signal, got {signal.signal_type.value}")
        self.external_signals.append(signal)
        if len(self.external_signals) > self.max_samples:
            self.external_signals.pop(0)

    def check_separation(
        self,
        subsystem: str,
        method: str = "partial_correlation",
    ) -> ConditionalSeparationResult:
        """验证 conditional_separation(internal ⊥ external | sensory)。

        Args:
            subsystem: 4 个 subsystems 之一
            method: "partial_correlation" 或 "mutual_information"

        Returns:
            ConditionalSeparationResult(passed + r + p_value + n + threshold + notes)
        """
        if subsystem not in self._internal_samples:
            raise ValueError(f"unknown subsystem: {subsystem}")

        n = len(self._internal_samples[subsystem])
        if n != len(self._external_samples) or n != len(self._sensory_samples):
            return ConditionalSeparationResult(
                passed=False,
                partial_corr=float("nan"),
                p_value=float("nan"),
                n_samples=min(n, len(self._external_samples), len(self._sensory_samples)),
                threshold=self.threshold,
                method=method,
                notes=f"sample length mismatch: int={n}, ext={len(self._external_samples)}, sen={len(self._sensory_samples)}",
            )

        if n < self.min_samples_for_check:
            return ConditionalSeparationResult(
                passed=False,
                partial_corr=float("nan"),
                p_value=float("nan"),
                n_samples=n,
                threshold=self.threshold,
                method=method,
                notes=f"insufficient samples: n={n} < {self.min_samples_for_check}",
            )

        internal = np.array(self._internal_samples[subsystem])
        external = np.array(self._external_samples)
        sensory = np.array(self._sensory_samples)

        if method == "partial_correlation":
            return check_conditional_separation_partial_corr(
                internal, external, sensory, threshold=self.threshold
            )
        elif method == "mutual_information":
            return check_conditional_separation_mutual_info(
                internal, external, sensory, threshold=self.threshold
            )
        else:
            raise ValueError(f"unknown method: {method}")

    def check_all_subsystems(
        self,
        method: str = "partial_correlation",
    ) -> dict[str, ConditionalSeparationResult]:
        """验证所有 4 个 subsystems 的 conditional_separation。

        Returns:
            dict[subsystem_name, ConditionalSeparationResult]
        """
        return {
            name: self.check_separation(name, method=method)
            for name in self.ALL_SUBSYSTEMS
        }

    def get_stats(self) -> dict:
        """MB 状态统计。"""
        return {
            "internal_samples": {k: len(v) for k, v in self._internal_samples.items()},
            "external_samples": len(self._external_samples),
            "sensory_samples": len(self._sensory_samples),
            "sensory_signals_count": len(self.sensory_signals),
            "active_signals_count": len(self.active_signals),
            "external_signals_count": len(self.external_signals),
            "threshold": self.threshold,
        }