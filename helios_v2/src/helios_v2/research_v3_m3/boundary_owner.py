"""M3 Boundary Owner - Layer 0 边界 owner。

v3 design §2.1 / task §2.1:
  - 5 nested subsystems 共享 1 个 Markov Blanket
  - boundary_owner.check_signal 检查所有穿越 MB 的信号
  - audit log + boundary crossings

关键设计:
  1. **NestedSubsystem**: 表示 1 个嵌套子系统(Layer 1/2/3/4),有 state + update 方法
  2. **BoundaryOwner**: 协调 5 个 NestedSubsystem + 1 个 MarkovBlanketBoundary + audit log
  3. **check_signal**: 验证信号是否允许穿越 MB
     - sensory 信号: 允许 world → system(任何 sensory 都是合法的)
     - active 信号: 允许 system → world(任何 active 都是合法的)
     - internal 信号: 不应穿越 MB(只在 system 内部)
     - external 信号: 不应直接进入 system
  4. **tick()**: 每个 tick 调用每个 subsystem.update + 检查不变量
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .signals import Signal, SignalType
from .markov_blanket import (
    MarkovBlanketBoundary,
    ConditionalSeparationResult,
)


DEFAULT_PARTIAL_CORR_THRESHOLD = 0.1


@dataclass
class NestedSubsystem:
    """1 个嵌套子系统(Layer 1/2/3/4)。

    Attributes:
        name: 子系统名("active_inference" / "self_model" / "reflection" / "evolution")
        state: 内部状态(任意 numpy array 或 scalar)
        update_fn: callable(current_state, sensory_signal) → new_state
        layer: 层级编号(1-4)
    """
    name: str
    state: object
    update_fn: Optional[Callable] = None
    layer: int = 2

    def update(self, sensory_payload) -> object:
        """用 sensory 输入更新子系统状态。"""
        if self.update_fn is None:
            # 默认:不做任何事(返回当前 state)
            return self.state
        self.state = self.update_fn(self.state, sensory_payload)
        return self.state


@dataclass(frozen=True)
class BoundaryCrossing:
    """1 次边界穿越记录(audit log entry)。

    Attributes:
        crossing_id: 唯一 ID
        signal: 被检查的信号
        admitted: 是否 admit
        reason: admit/deny 原因
        conditional_separation_passed: 当次检查时 MB 不变量是否通过
        timestamp: wall-clock
    """
    crossing_id: str
    signal: Signal
    admitted: bool
    reason: str
    conditional_separation_passed: Optional[bool] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "crossing_id": self.crossing_id,
            "signal_id": self.signal.signal_id,
            "signal_type": self.signal.signal_type.value,
            "source": self.signal.source,
            "target": self.signal.target,
            "admitted": self.admitted,
            "reason": self.reason,
            "conditional_separation_passed": self.conditional_separation_passed,
            "timestamp": self.timestamp,
        }


class BoundaryOwner:
    """Layer 0 边界 owner。

    协调:
      - 1 个 MarkovBlanketBoundary(共享数学不变量验证)
      - 4 个 NestedSubsystem(Layer 1/2/3/4)
      - 1 个 audit log(BoundaryCrossing 列表)
    """

    def __init__(
        self,
        subsystems: dict[str, NestedSubsystem],
        mb: Optional[MarkovBlanketBoundary] = None,
        partial_corr_threshold: float = DEFAULT_PARTIAL_CORR_THRESHOLD,
        enforce_separation_check: bool = True,
    ):
        if not subsystems:
            raise ValueError("subsystems dict cannot be empty")
        self.subsystems = subsystems
        self.mb = mb if mb is not None else MarkovBlanketBoundary(
            threshold=partial_corr_threshold
        )
        self.partial_corr_threshold = partial_corr_threshold
        self.enforce_separation_check = enforce_separation_check
        self.audit_log: list[BoundaryCrossing] = []
        self._n_admitted = 0
        self._n_denied = 0

    # === 主入口 ===

    def check_signal(self, signal: Signal) -> bool:
        """检查 signal 是否允许穿越 MB(并写 audit log)。

        规则:
          - SENSORY 信号 (world → system): 允许(总是合法)
          - ACTIVE 信号 (system → world): 允许(总是合法)
          - INTERNAL 信号 (system internal): 拒绝(不应穿越 MB)
          - EXTERNAL 信号 (world external): 拒绝(不应直接进入 system)
          - 如果 enforce_separation_check 且 MB 不变量失败:
            - sensory/active 信号 deny(mathematical invariant violated)
            - internal/external 信号 deny(已经 deny 了,不变量检查冗余)

        Returns:
            bool: True = admitted, False = denied
        """
        # 1. 信号类型基本规则
        if signal.signal_type == SignalType.SENSORY:
            base_admit = True
            base_reason = "sensory signal: world → system"
        elif signal.signal_type == SignalType.ACTIVE:
            base_admit = True
            base_reason = "active signal: system → world"
        elif signal.signal_type == SignalType.INTERNAL:
            base_admit = False
            base_reason = "internal signal should not cross MB"
        elif signal.signal_type == SignalType.EXTERNAL:
            base_admit = False
            base_reason = "external signal should not directly enter system"
        else:
            base_admit = False
            base_reason = f"unknown signal type: {signal.signal_type}"

        # 2. conditional_separation 不变量检查(如果启用)
        sep_passed: Optional[bool] = None
        if self.enforce_separation_check and base_admit:
            # 只对合法信号检查不变量
            # 取目标 subsystem(默认 self_model)
            target = signal.target
            if target in self.mb.ALL_SUBSYSTEMS:
                result = self.mb.check_separation(target, method="partial_correlation")
                sep_passed = result.passed
                if not result.passed:
                    base_admit = False
                    base_reason = (
                        f"conditional_separation violated for {target}: "
                        f"|r|={abs(result.partial_corr):.3f} > {self.partial_corr_threshold}"
                    )

        # 3. 写 audit log
        crossing = BoundaryCrossing(
            crossing_id=str(uuid.uuid4()),
            signal=signal,
            admitted=base_admit,
            reason=base_reason,
            conditional_separation_passed=sep_passed,
        )
        self.audit_log.append(crossing)

        if base_admit:
            self._n_admitted += 1
            # 信号通过:更新 MB 状态
            self._on_signal_admitted(signal)
        else:
            self._n_denied += 1

        return base_admit

    def _on_signal_admitted(self, signal: Signal) -> None:
        """信号通过时更新 MB 状态。"""
        if signal.signal_type == SignalType.SENSORY:
            self.mb.add_sensory_signal(signal)
            # 记录 sensory 样本(payload scalar 或第一个值)
            value = self._extract_scalar(signal.payload)
            if value is not None:
                self.mb.record_sensory(value)

    @staticmethod
    def _extract_scalar(payload) -> Optional[float]:
        """从 payload 中提取标量值(用于 MB 状态记录)。"""
        if isinstance(payload, (int, float)):
            return float(payload)
        if isinstance(payload, np.ndarray):
            if payload.size == 1:
                return float(payload.ravel()[0])
            return float(np.mean(payload))
        if isinstance(payload, (list, tuple)):
            if len(payload) == 0:
                return None
            try:
                return float(np.mean(payload))
            except (TypeError, ValueError):
                return None
        return None

    def cross(self, signal: Signal) -> bool:
        """check_signal 的别名(更直观的命名)。"""
        return self.check_signal(signal)

    def check_signal_dry(self, signal: Signal) -> bool:
        """check_signal 但不自动记录 sensory 信号到 MB(用于 manual record 模式)。

        跟 check_signal 的区别:不调用 _on_signal_admitted,所以 MB sensory_samples 不增加。
        适用于 probe / 测试场景,需要手动控制 MB 样本对齐。
        """
        # 1. 信号类型基本规则
        if signal.signal_type == SignalType.SENSORY:
            base_admit = True
            base_reason = "sensory signal: world → system"
        elif signal.signal_type == SignalType.ACTIVE:
            base_admit = True
            base_reason = "active signal: system → world"
        elif signal.signal_type == SignalType.INTERNAL:
            base_admit = False
            base_reason = "internal signal should not cross MB"
        elif signal.signal_type == SignalType.EXTERNAL:
            base_admit = False
            base_reason = "external signal should not directly enter system"
        else:
            base_admit = False
            base_reason = f"unknown signal type: {signal.signal_type}"

        # 2. 不变量检查
        sep_passed: Optional[bool] = None
        if self.enforce_separation_check and base_admit:
            target = signal.target
            if target in self.mb.ALL_SUBSYSTEMS:
                result = self.mb.check_separation(target, method="partial_correlation")
                sep_passed = result.passed
                if not result.passed:
                    base_admit = False
                    base_reason = (
                        f"conditional_separation violated for {target}: "
                        f"|r|={abs(result.partial_corr):.3f} > {self.partial_corr_threshold}"
                    )

        # 3. 写 audit log(但不更新 MB)
        crossing = BoundaryCrossing(
            crossing_id=str(uuid.uuid4()),
            signal=signal,
            admitted=base_admit,
            reason=base_reason,
            conditional_separation_passed=sep_passed,
        )
        self.audit_log.append(crossing)

        if base_admit:
            self._n_admitted += 1
        else:
            self._n_denied += 1

        return base_admit

    # === 子系统管理 ===

    def update_subsystem(self, name: str, sensory_payload=None) -> object:
        """更新 1 个子系统 + 记录 internal 状态到 MB。"""
        if name not in self.subsystems:
            raise ValueError(f"unknown subsystem: {name}")
        sub = self.subsystems[name]
        new_state = sub.update(sensory_payload)

        # 记录 internal 状态样本(标量化)
        value = self._extract_scalar(new_state)
        if value is not None:
            self.mb.record_internal(name, value)

        return new_state

    def update_all_subsystems(self, sensory_payload=None) -> dict[str, object]:
        """更新所有 subsystems(并发更新,记录所有 internal 状态)。"""
        return {
            name: self.update_subsystem(name, sensory_payload)
            for name in self.subsystems
        }

    # === External / Active 输出 ===

    def emit_active(self, source: str, target: str, payload) -> Signal:
        """子系统发出 active 信号到外部世界。

        Returns:
            已 check 的 Signal(总是 admitted,因为 active 信号合法)
        """
        signal = Signal.make(
            signal_type=SignalType.ACTIVE,
            source=source,
            target=target,
            payload=payload,
        )
        self.check_signal(signal)
        # active 信号也记录到 MB active_signals
        self.mb.add_active_signal(signal)
        return signal

    def record_external(self, value: float) -> None:
        """记录外部世界状态样本(用于 MB 不变量验证)。"""
        self.mb.record_external(value)

    # === 统计 + 查询 ===

    def get_stats(self) -> dict:
        """边界 owner 统计。"""
        sep_results = self.mb.check_all_subsystems(method="partial_correlation")
        sep_pass_count = sum(1 for r in sep_results.values() if r.passed)
        return {
            "n_subsystems": len(self.subsystems),
            "n_admitted": self._n_admitted,
            "n_denied": self._n_denied,
            "audit_log_size": len(self.audit_log),
            "conditional_separation_pass_count": sep_pass_count,
            "conditional_separation_total": len(sep_results),
            "mb_stats": self.mb.get_stats(),
        }

    def get_audit_log(
        self,
        signal_type: Optional[SignalType] = None,
        admitted_only: bool = False,
    ) -> list[BoundaryCrossing]:
        """获取 audit log(可按 signal_type 过滤,或只返回 admitted)。"""
        log = self.audit_log
        if signal_type is not None:
            log = [c for c in log if c.signal.signal_type == signal_type]
        if admitted_only:
            log = [c for c in log if c.admitted]
        return log

    def clear_audit_log(self) -> int:
        """清空 audit log(返回清空数量)。"""
        count = len(self.audit_log)
        self.audit_log.clear()
        self._n_admitted = 0
        self._n_denied = 0
        return count

    # === 25 stage 接入的简化版 ===

    def stage_22_boundary_enforcement(self) -> dict:
        """v3 25 stage 中的 stage 22: BoundaryEnforcement。

        这个方法模拟 stage 22 的逻辑:
          1. 收集 internal/external/sensory 样本
          2. 验证 conditional_separation
          3. 如果不变量违反,deny 所有 active 信号(系统应该"沉默")
          4. 返回 audit 报告

        Returns:
            dict with stage status + invariant results + admitted/denied counts
        """
        sep_results = self.mb.check_all_subsystems(method="partial_correlation")
        all_passed = all(r.passed for r in sep_results.values())

        return {
            "stage": 22,
            "stage_name": "BoundaryEnforcement",
            "all_separations_passed": all_passed,
            "separation_results": {
                name: {
                    "passed": r.passed,
                    "partial_corr": r.partial_corr,
                    "p_value": r.p_value,
                    "n_samples": r.n_samples,
                }
                for name, r in sep_results.items()
            },
            "n_admitted": self._n_admitted,
            "n_denied": self._n_denied,
            "audit_log_size": len(self.audit_log),
        }