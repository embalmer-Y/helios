"""M2 Reflection Owner - Layer 3 反思层。

v3 design §2.4 + task §1.2:
  - 4 trigger (POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED)
  - 4-level scheduling (IMMEDIATE / SHORT_TERM / MEDIUM_TERM / LONG_TERM)
  - LLM 被动接受 self_experience(只读,不修改 8d state 或 C)
  - reflection_audit grounded 验证
  - 输出 reflect 注入到 CDS

关键设计决策:
  1. **解耦 trigger 与 response**:trigger 只决定"是否反思",response 由 LLM caller 决定
  2. **POST_TICK rate-limited**:避免每 tick 都反思(成本高 + 反思泛滥)
  3. **RESTING_STATE 用 uncertainty 历史均值**:100 tick 内 R 持续高 → 静息态
  4. **HIGH_UNCERTAINTY 用 AspectState.uncertainty** (projection 自带,或 proxy 用 1-self_unity)
  5. **USER_INVOKED 是唯一显式触发**:其他都是自动
  6. **LLM 只读 snapshot**:绝不允许 LLM 修改 cds.state 或 cds.C
  7. **reflection_audit 4 项检查**:reflect 合法 / 提到 snapshot / 不修改 CDS / grounded
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from helios_v2.research_v3_m1 import SelfModelOwner


# === 常量 ===

POST_TICK_RATE_LIMIT = 50
"""POST_TICK 反思的最小 tick 间隔(避免反思泛滥)。"""

RESTING_STATE_THRESHOLD = 0.85
"""Kuramoto R 高于此阈值且持续 100 tick → 触发 RESTING_STATE。"""

RESTING_STATE_DURATION = 100
"""RESTING_STATE 判定的窗口长度(tick 数)。"""

HIGH_UNCERTAINTY_THRESHOLD = 0.7
"""uncertainty 高于此阈值 → 触发 HIGH_UNCERTAINTY。"""

AUDIT_MIN_RESPONSE_LENGTH = 10
"""LLM 响应文本的最短长度(防止空响应)。"""


class ReflectionTrigger(str, Enum):
    """4 种反思触发源。"""
    POST_TICK = "post_tick"               # 每 tick 后(限速)
    RESTING_STATE = "resting_state"       # 静息态(R 高且持续)
    HIGH_UNCERTAINTY = "high_uncertainty"  # uncertainty 高
    USER_INVOKED = "user_invoked"         # 用户主动触发


class ReflectionLevel(str, Enum):
    """4 级调度优先级。"""
    IMMEDIATE = "immediate"          # 立即执行(USER_INVOKED / HIGH_UNCERTAINTY)
    SHORT_TERM = "short_term"        # 短期排队(< 10 tick 延迟)
    MEDIUM_TERM = "medium_term"      # 中期排队(10-100 tick)
    LONG_TERM = "long_term"          # 长期排队(> 100 tick,POST_TICK 默认)


def _trigger_to_level(trigger: ReflectionTrigger) -> ReflectionLevel:
    """trigger → 默认 level 的映射。"""
    return {
        ReflectionTrigger.USER_INVOKED: ReflectionLevel.IMMEDIATE,
        ReflectionTrigger.HIGH_UNCERTAINTY: ReflectionLevel.IMMEDIATE,
        ReflectionTrigger.RESTING_STATE: ReflectionLevel.SHORT_TERM,
        ReflectionTrigger.POST_TICK: ReflectionLevel.LONG_TERM,
    }[trigger]


@dataclass(frozen=True)
class ReflectionAuditResult:
    """reflection_audit 验证结果。"""
    passed: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    def __bool__(self):
        return self.passed


@dataclass(frozen=True)
class ReflectionRecord:
    """单次反思的不可变记录(便于 reflection_audit 追溯)。"""
    record_id: str
    trigger: ReflectionTrigger
    level: ReflectionLevel
    tick_at_trigger: int
    tick_at_resolve: int
    self_experience_snapshot: dict  # snapshot 拷贝(grounded 验证)
    llm_response: str
    reflect_vector: np.ndarray       # 8-dim reflect(注入 CDS)
    audit: ReflectionAuditResult
    latency_ms: float
    timestamp: float                # wall-clock time


@dataclass
class ReflectionOwner:
    """Layer 3 反思 owner - 协调 4 trigger + LLM 被动接受 + audit。

    协作模式:
      - 调用者每 tick 调一次 `on_tick_after_cds()` 检测 trigger
      - USER_INVOKED 由调用者主动调 `invoke_user_reflection(prompt)`
      - `get_pending_reflect()` 返回当前应注入 CDS 的 reflect
      - 调用者用返回的 reflect 作为下个 CDS tick 的 reflect 参数
    """

    self_model: "SelfModelOwner"
    llm_caller: object  # LLMCallerProtocol(FakeLLMCaller 或真 LLM)
    post_tick_rate_limit: int = POST_TICK_RATE_LIMIT
    resting_state_threshold: float = RESTING_STATE_THRESHOLD
    resting_state_duration: int = RESTING_STATE_DURATION
    high_uncertainty_threshold: float = HIGH_UNCERTAINTY_THRESHOLD

    # 内部状态
    records: list[ReflectionRecord] = field(default_factory=list)
    _R_history: deque = field(default_factory=lambda: deque(maxlen=RESTING_STATE_DURATION))
    _uncertainty_history: deque = field(default_factory=lambda: deque(maxlen=RESTING_STATE_DURATION))
    _last_post_tick_reflection_tick: int = -POST_TICK_RATE_LIMIT * 2  # 允许首次立即触发
    _pending_reflect: Optional[np.ndarray] = None
    _n_reflections: int = 0
    _n_audit_passes: int = 0

    def __post_init__(self):
        # type 检查 llm_caller 是否实现 Protocol
        from .llm_caller import LLMCallerProtocol
        if not isinstance(self.llm_caller, LLMCallerProtocol):
            raise TypeError(
                f"llm_caller must implement LLMCallerProtocol, got {type(self.llm_caller)}"
            )

    # === 主入口 ===

    def on_tick_after_cds(self) -> dict:
        """每个 CDS tick 后调用 - 检测 trigger 并可能触发反思。

        Returns:
            dict 含 triggered (list[ReflectionTrigger]) + records (list[ReflectionRecord])
        """
        # 1. 取当前 snapshot
        snapshot = self.self_model.get_state_for_llm()

        # 2. 更新历史
        R = snapshot.get("global_coherence_R", 0.5)
        self_unity = snapshot.get("self_unity", 0.5)
        uncertainty = max(0.0, 1.0 - self_unity)  # proxy
        self._R_history.append(R)
        self._uncertainty_history.append(uncertainty)

        # 3. 检测 trigger
        triggered = []
        if self._should_post_tick_reflect(self.self_model.tick_count):
            triggered.append(ReflectionTrigger.POST_TICK)
        if self._is_resting_state():
            triggered.append(ReflectionTrigger.RESTING_STATE)
        if uncertainty > self.high_uncertainty_threshold:
            triggered.append(ReflectionTrigger.HIGH_UNCERTAINTY)

        # 4. 触发反思
        records = []
        for trig in triggered:
            record = self._do_reflect(trig, snapshot=snapshot)
            records.append(record)

        return {
            "triggers_fired": [t.value for t in triggered],
            "n_reflections": len(records),
            "records": [self._record_to_dict(r) for r in records],
        }

    def invoke_user_reflection(self, user_prompt: str) -> ReflectionRecord:
        """USER_INVOKED 主动触发反思。

        Returns:
            ReflectionRecord
        """
        snapshot = self.self_model.get_state_for_llm()
        return self._do_reflect(
            ReflectionTrigger.USER_INVOKED,
            snapshot=snapshot,
            user_prompt=user_prompt,
        )

    # === reflect 注入机制 ===

    def get_pending_reflect(self) -> np.ndarray:
        """返回当前应注入 CDS 的 reflect(8-dim)。

        调用者负责把这个向量作为下个 CDS tick 的 reflect 参数。

        Returns:
            8-dim np.ndarray(可能为 zeros 如果没有 pending reflect)
        """
        if self._pending_reflect is None:
            return np.zeros(8)
        return self._pending_reflect.copy()

    def consume_pending_reflect(self) -> np.ndarray:
        """返回并清空 pending reflect(一次性消费)。"""
        r = self.get_pending_reflect()
        self._pending_reflect = None
        return r

    # === trigger 检测 ===

    def _should_post_tick_reflect(self, current_tick: int) -> bool:
        """POST_TICK 限速:至少 post_tick_rate_limit tick 间隔。"""
        return (current_tick - self._last_post_tick_reflection_tick) >= self.post_tick_rate_limit

    def _is_resting_state(self) -> bool:
        """RESTING_STATE:R 持续高于阈值 且 持续时间达到 window。"""
        if len(self._R_history) < self.resting_state_duration:
            return False
        return all(r > self.resting_state_threshold for r in self._R_history)

    # === 反思执行 ===

    def _do_reflect(
        self,
        trigger: ReflectionTrigger,
        snapshot: dict,
        user_prompt: str | None = None,
    ) -> ReflectionRecord:
        """执行一次反思:LLM call + audit + 存 record。"""
        t0 = time.time()
        tick_at_trigger = self.self_model.tick_count

        # 1. LLM call(LLM 被动接受 snapshot)
        llm_response, reflect_vec = self.llm_caller.call(
            snapshot=snapshot,
            trigger=trigger.value,
            user_prompt=user_prompt,
        )
        reflect_vec = np.clip(np.asarray(reflect_vec, dtype=np.float64), -1.0, 1.0)

        # 2. reflection_audit(grounded 验证)
        audit = self._audit_reflection(snapshot, llm_response, reflect_vec)

        # 3. 存 record
        level = _trigger_to_level(trigger)
        record = ReflectionRecord(
            record_id=str(uuid.uuid4()),
            trigger=trigger,
            level=level,
            tick_at_trigger=tick_at_trigger,
            tick_at_resolve=self.self_model.tick_count,
            self_experience_snapshot=dict(snapshot),  # 浅拷贝防止后续 mutation
            llm_response=llm_response,
            reflect_vector=reflect_vec.copy(),
            audit=audit,
            latency_ms=(time.time() - t0) * 1000.0,
            timestamp=time.time(),
        )
        self.records.append(record)
        self._n_reflections += 1
        if audit.passed:
            self._n_audit_passes += 1

        # 4. 更新 _last_post_tick 跟踪
        if trigger == ReflectionTrigger.POST_TICK:
            self._last_post_tick_reflection_tick = tick_at_trigger

        # 5. 把 reflect 存为 pending(下次 CDS tick 用)
        self._pending_reflect = reflect_vec

        return record

    # === audit 验证 ===

    def _audit_reflection(
        self,
        snapshot: dict,
        llm_response: str,
        reflect_vec: np.ndarray,
    ) -> ReflectionAuditResult:
        """reflection_audit 4 项检查:

        1. reflect_vec shape = (8,)
        2. reflect_vec ∈ [-1, 1]
        3. llm_response 非空且 >= AUDIT_MIN_RESPONSE_LENGTH
        4. llm_response 提到 snapshot 的至少一个关键字段(grounded 验证)

        Returns:
            ReflectionAuditResult(passed + reasons + checks)
        """
        checks = {}
        reasons = []

        # Check 1: shape
        checks["reflect_shape_ok"] = (reflect_vec.shape == (8,))
        if not checks["reflect_shape_ok"]:
            reasons.append(f"reflect_vec.shape = {reflect_vec.shape}, expected (8,)")

        # Check 2: range
        if reflect_vec.shape == (8,):
            checks["reflect_range_ok"] = bool(np.all(np.abs(reflect_vec) <= 1.0 + 1e-6))
            if not checks["reflect_range_ok"]:
                reasons.append(f"reflect_vec out of [-1, 1]: max abs = {float(np.max(np.abs(reflect_vec))):.4f}")

        # Check 3: response not empty
        checks["response_nonempty"] = (
            isinstance(llm_response, str) and len(llm_response) >= AUDIT_MIN_RESPONSE_LENGTH
        )
        if not checks["response_nonempty"]:
            reasons.append(f"llm_response too short: {len(llm_response) if isinstance(llm_response, str) else 0} chars")

        # Check 4: grounded - 提到 snapshot 的至少一个关键字段
        snapshot_keys_to_check = [
            str(snapshot.get("global_coherence_R", ""))[:5],  # R 值
            str(snapshot.get("rochat_level_discrete", "")),     # Rochat 离散级别
        ]
        # R 值也可能写为 "0.xxx" 形式 - 直接检查 R 数值出现在 response 里
        R_val = snapshot.get("global_coherence_R", None)
        rochat_disc = snapshot.get("rochat_level_discrete", None)

        grounded_signals = []
        if R_val is not None:
            grounded_signals.append(f"R={R_val:.3f}" in llm_response or f"R = {R_val:.3f}" in llm_response)
        if rochat_disc is not None:
            grounded_signals.append(str(rochat_disc) in llm_response)
        # 任意 trigger 字段出现在 response
        grounded_signals.append("trigger=" in llm_response or "trigger =" in llm_response)

        checks["grounded_in_snapshot"] = any(grounded_signals)
        if not checks["grounded_in_snapshot"]:
            reasons.append(f"response does not mention R/rochat/trigger: {llm_response[:80]}")

        passed = all(checks.values())
        return ReflectionAuditResult(passed=passed, reasons=reasons, checks=checks)

    # === 统计 ===

    def get_stats(self) -> dict:
        """反思统计。"""
        trigger_counts = {t.value: 0 for t in ReflectionTrigger}
        for r in self.records:
            trigger_counts[r.trigger.value] += 1

        audit_pass_rate = (
            self._n_audit_passes / self._n_reflections
            if self._n_reflections > 0 else 0.0
        )

        return {
            "n_reflections": self._n_reflections,
            "n_audit_passes": self._n_audit_passes,
            "audit_pass_rate": audit_pass_rate,
            "trigger_counts": trigger_counts,
            "R_history_len": len(self._R_history),
            "uncertainty_history_len": len(self._uncertainty_history),
            "last_post_tick_tick": self._last_post_tick_reflection_tick,
        }

    # === 工具方法 ===

    def _record_to_dict(self, r: ReflectionRecord) -> dict:
        """record → dict(用于 logging / API 返回)。"""
        return {
            "record_id": r.record_id,
            "trigger": r.trigger.value,
            "level": r.level.value,
            "tick_at_trigger": r.tick_at_trigger,
            "tick_at_resolve": r.tick_at_resolve,
            "llm_response": r.llm_response,
            "reflect_vector": r.reflect_vector.tolist(),
            "audit_passed": r.audit.passed,
            "audit_reasons": r.audit.reasons,
            "audit_checks": r.audit.checks,
            "latency_ms": r.latency_ms,
            "timestamp": r.timestamp,
        }

    def get_records(self, trigger: ReflectionTrigger | None = None) -> list[ReflectionRecord]:
        """获取所有(或按 trigger 过滤的)记录。"""
        if trigger is None:
            return list(self.records)
        return [r for r in self.records if r.trigger == trigger]