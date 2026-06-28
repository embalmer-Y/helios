"""M3 信号类型定义。

v3 design §2.1 Layer 0 Markov Blanket:
  - 4 类状态: internal / sensory / active / external
  - internal ⊥ external | sensory(数学不变量)
  - 信号必须经 MB 检查才能穿越

类比 Pearl 1995:
  - U: 外部未观测(对应 external)
  - X: 边界观测(对应 sensory)
  - 内生变量: 对应 internal
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    """4 类信号类型。"""
    SENSORY = "sensory"      # 输入信号 (world → system 经 MB)
    ACTIVE = "active"        # 输出信号 (system → world 经 MB)
    INTERNAL = "internal"    # 系统内部状态变化(不穿越 MB)
    EXTERNAL = "external"    # 外部世界状态(不直接进入 system)


@dataclass(frozen=True)
class Signal:
    """单条信号 - 不可变(便于 audit log)。

    Attributes:
        signal_id: 唯一 ID
        signal_type: 4 类之一
        source: 发送者 ID(如 "world", "user", "self_model")
        target: 接收者 ID(如 "boundary", "active_inference", "external_world")
        payload: 信号内容(任意 JSON-serializable)
        timestamp: wall-clock 时间
    """
    signal_id: str
    signal_type: SignalType
    source: str
    target: str
    payload: Any
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def make(
        cls,
        signal_type: SignalType,
        source: str,
        target: str,
        payload: Any,
    ) -> "Signal":
        """工厂方法:自动生成 signal_id。"""
        return cls(
            signal_id=str(uuid.uuid4()),
            signal_type=signal_type,
            source=source,
            target=target,
            payload=payload,
        )

    def __repr__(self) -> str:
        return f"Signal({self.signal_type.value}: {self.source} → {self.target})"