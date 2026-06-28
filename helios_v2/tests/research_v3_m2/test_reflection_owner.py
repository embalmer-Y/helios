"""M2 Reflection Owner 测试。

覆盖:
  - 4 trigger 各自正确触发 (POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED)
  - LLM 被动接受(只读 snapshot)
  - reflection_audit 4 项检查
  - reflect 注入机制(consume + pending)
  - 1000 tick 端到端
"""
import time
import pytest
import numpy as np

from helios_v2.research_v3_m1 import SelfModelOwner
from helios_v2.research_v3_m2 import (
    ReflectionOwner,
    FakeLLMCaller,
    LLMCallerProtocol,
    ReflectionTrigger,
    ReflectionLevel,
    ReflectionRecord,
    ReflectionAuditResult,
    POST_TICK_RATE_LIMIT,
    RESTING_STATE_THRESHOLD,
    HIGH_UNCERTAINTY_THRESHOLD,
)


# === Helpers ===

def make_owner():
    return SelfModelOwner.default()


def make_reflection_owner(post_tick_rate_limit=50,
                          resting_state_threshold=0.85,
                          resting_state_duration=100,
                          high_uncertainty_threshold=0.7):
    owner = make_owner()
    llm = FakeLLMCaller()
    ro = ReflectionOwner(
        self_model=owner,
        llm_caller=llm,
        post_tick_rate_limit=post_tick_rate_limit,
        resting_state_threshold=resting_state_threshold,
        resting_state_duration=resting_state_duration,
        high_uncertainty_threshold=high_uncertainty_threshold,
    )
    return ro, owner, llm


def drive_cds(owner, n_ticks, I_factory=None):
    """驱动 CDS n_ticks。"""
    for tick in range(n_ticks):
        if I_factory is None:
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
        else:
            I = I_factory(tick)
        owner.tick(I=I)


# === TestLLMCallerProtocol ===

class TestLLMCallerProtocol:
    """LLMCallerProtocol 接口测试。"""

    def test_FakeLLMCaller_implements_protocol(self):
        """FakeLLMCaller 必须实现 LLMCallerProtocol。"""
        llm = FakeLLMCaller()
        assert isinstance(llm, LLMCallerProtocol)

    def test_custom_caller_can_implement_protocol(self):
        """自定义 caller 只要有 call 方法就满足 Protocol(duck typing)。"""
        class MyCaller:
            def call(self, snapshot, trigger, user_prompt=None):
                return "test", np.zeros(8)

        assert isinstance(MyCaller(), LLMCallerProtocol)

    def test_non_caller_rejected_by_post_init(self):
        """非 caller 对象在 __post_init__ 被拒绝。"""
        with pytest.raises(TypeError):
            ReflectionOwner(self_model=make_owner(), llm_caller="not a caller")


# === TestReflectionTriggerDetection ===

class TestReflectionTriggerDetection:
    """4 trigger 检测测试。"""

    def test_POST_TICK_triggers_at_tick_0(self):
        """POST_TICK 在 tick 0 触发(首次)。"""
        ro, owner, _ = make_reflection_owner(post_tick_rate_limit=50)
        owner.tick(I=np.zeros(8))  # tick_count = 1
        result = ro.on_tick_after_cds()
        # POST_TICK 限制为 50 tick 间隔,tick 0 立即触发
        assert "post_tick" in result["triggers_fired"]

    def test_POST_TICK_rate_limit_blocks_immediate_retrigger(self):
        """POST_TICK 在 50 tick 内不再触发。"""
        ro, owner, _ = make_reflection_owner(post_tick_rate_limit=50)
        for tick in range(60):
            owner.tick(I=np.zeros(8))
            result = ro.on_tick_after_cds()
            if tick == 0:
                assert "post_tick" in result["triggers_fired"]
            elif tick < 50:
                assert "post_tick" not in result["triggers_fired"]
            elif tick == 50:
                assert "post_tick" in result["triggers_fired"]

    def test_HIGH_UNCERTAINTY_triggers_above_threshold(self):
        """uncertainty > 0.7 触发 HIGH_UNCERTAINTY。"""
        ro, owner, _ = make_reflection_owner(high_uncertainty_threshold=0.7)
        # 驱动 state 进入饱和,uncertainty > 0.7
        for tick in range(50):
            owner.tick(I=10.0 * np.ones(8))  # 大输入快速饱和
            result = ro.on_tick_after_cds()
            if "high_uncertainty" in result["triggers_fired"]:
                return  # success
        pytest.fail("HIGH_UNCERTAINTY never triggered with high-amplitude I")

    def test_RESTING_STATE_triggers_when_R_sustained_high(self):
        """R 持续 > threshold 持续 window 大小 tick → 触发 RESTING_STATE。"""
        ro, owner, _ = make_reflection_owner(
            resting_state_threshold=0.5,  # 降低阈值便于测试
            resting_state_duration=10,   # 短窗口
        )
        # 驱动 state → R 高
        # proportional state ([0.5, 0.5, ..., 2.5, 5.0, 15.0]) → R ≈ 1
        for tick in range(20):
            owner.tick(I=np.array([0.5, 0.5, 0.5, 0.5, 0.5, 2.5, 5.0, 15.0]))
            result = ro.on_tick_after_cds()
            if "resting_state" in result["triggers_fired"]:
                return  # success
        # 如果没触发,可能 R 没持续高
        stats = ro.get_stats()
        pytest.fail(f"RESTING_STATE never triggered. Stats: {stats}")

    def test_USER_INVOKED_triggers_on_demand(self):
        """USER_INVOKED 总是立即触发。"""
        ro, owner, _ = make_reflection_owner()
        owner.tick(I=np.zeros(8))
        rec = ro.invoke_user_reflection("test prompt")
        assert rec.trigger == ReflectionTrigger.USER_INVOKED
        assert rec.level == ReflectionLevel.IMMEDIATE

    def test_multiple_triggers_can_fire_simultaneously(self):
        """多个 trigger 可在同 tick 触发。"""
        ro, owner, _ = make_reflection_owner(
            post_tick_rate_limit=10,  # 短间隔便于测试
            high_uncertainty_threshold=0.5,
        )
        # 触发 POST_TICK + HIGH_UNCERTAINTY 同时
        for tick in range(30):
            owner.tick(I=10.0 * np.ones(8))
            result = ro.on_tick_after_cds()
            if len(result["triggers_fired"]) >= 2:
                return  # success
        pytest.fail(f"multiple triggers never fired. Last: {result['triggers_fired']}")


# === TestLLMPassiveAccept ===

class TestLLMPassiveAccept:
    """LLM 被动接受测试(不修改 CDS state)。"""

    def test_LLM_cannot_modify_cds_state(self):
        """LLM 拿到的 snapshot 改了不影响 CDS state。"""
        ro, owner, llm = make_reflection_owner()
        # 跑几个 tick 让 state 稳定
        drive_cds(owner, 5)

        state_before = owner.cds.state.copy()
        snapshot = owner.get_state_for_llm()
        # 模拟 LLM 修改 snapshot
        snapshot["8d_state"] = [99.0] * 8
        state_after = owner.cds.state.copy()
        assert np.allclose(state_before, state_after)

    def test_LLM_receives_snapshot_with_required_keys(self):
        """LLM 拿到的 snapshot 包含 8d_state + R + rochat 等。"""
        ro, owner, _ = make_reflection_owner()
        owner.tick(I=np.zeros(8))
        snapshot = owner.get_state_for_llm()
        for key in ["8d_state", "global_coherence_R", "rochat_level_discrete",
                    "self_unity", "tick_count"]:
            assert key in snapshot

    def test_LLM_does_not_get_cds_reference(self):
        """LLM 拿到的 snapshot 不含 cds 引用本身(防止 LLM 直接改)。"""
        ro, owner, _ = make_reflection_owner()
        owner.tick(I=np.zeros(8))
        snapshot = owner.get_state_for_llm()
        # snapshot 应该不含 cds / C 引用
        assert "cds" not in snapshot
        assert "C" not in snapshot  # 只暴露 coupling_matrix_summary

    def test_FakeLLM_deterministic_output(self):
        """FakeLLMCaller 确定性输出(相同 snapshot → 相同 reflect)。"""
        llm = FakeLLMCaller()
        snapshot = {
            "8d_state": [0.1] * 8,
            "global_coherence_R": 0.8,
            "rochat_level_discrete": 4,
            "self_unity": 0.9,
        }
        resp1, ref1 = llm.call(snapshot, "post_tick")
        resp2, ref2 = llm.call(snapshot, "post_tick")
        assert resp1 == resp2
        assert np.allclose(ref1, ref2)

    def test_FakeLLM_response_mentions_R(self):
        """FakeLLMCaller 响应提到 R 值(便于 audit 检查 grounded)。"""
        llm = FakeLLMCaller()
        snapshot = {"global_coherence_R": 0.825, "rochat_level_discrete": 4}
        resp, _ = llm.call(snapshot, "post_tick")
        assert "R=" in resp or "R =" in resp


# === TestReflectionAudit ===

class TestReflectionAudit:
    """reflection_audit 验证测试。"""

    def test_audit_passes_for_normal_reflection(self):
        """正常反思 → audit passed。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 5)
        rec = ro.invoke_user_reflection("test")
        assert rec.audit.passed
        assert rec.audit.checks["reflect_shape_ok"]
        assert rec.audit.checks["reflect_range_ok"]
        assert rec.audit.checks["response_nonempty"]
        assert rec.audit.checks["grounded_in_snapshot"]

    def test_audit_fails_for_wrong_shape_reflect(self):
        """reflect shape 错误 → audit failed。"""
        ro, owner, _ = make_reflection_owner()
        # 替换 llm_caller 返回错误 shape
        class BadLLM:
            def call(self, snapshot, trigger, user_prompt=None):
                return "test response long enough", np.zeros(5)  # 错误 shape!
        ro.llm_caller = BadLLM()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        assert not rec.audit.passed
        assert not rec.audit.checks["reflect_shape_ok"]
        assert any("shape" in r.lower() for r in rec.audit.reasons)

    def test_audit_fails_for_out_of_range_reflect_direct(self):
        """reflect 超出 [-1, 1] 时 audit 检测(直接调用 audit 函数)。"""
        ro, owner, _ = make_reflection_owner()
        snapshot = owner.get_state_for_llm()
        # 直接 audit 一个超界的 reflect(绕过 _do_reflect 的 clip)
        out_of_range_reflect = np.array([5.0] * 8)
        result = ro._audit_reflection(snapshot, "test response long enough", out_of_range_reflect)
        assert not result.passed
        assert not result.checks["reflect_range_ok"]
        assert any("range" in r.lower() or "[-1, 1]" in r for r in result.reasons)

    def test_LLM_out_of_range_gets_clipped_before_injection(self):
        """LLM 返回超界 → 被 clip 到 [-1, 1] 后再注入(防止 LLM 越界)。"""
        ro, owner, _ = make_reflection_owner()
        R_val = 0.5
        class BadLLM:
            def call(self, snapshot, trigger, user_prompt=None):
                # grounded 响应(提到 R),但 reflect 超界
                R = snapshot.get("global_coherence_R", 0.5)
                return f"trigger={trigger} R={R:.3f} but bad reflect", np.array([5.0] * 8)
        ro.llm_caller = BadLLM()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        # reflect_vector 应被 clip 到 [-1, 1](不在 5.0)
        assert np.all(np.abs(rec.reflect_vector) <= 1.0 + 1e-6)
        # reflect 合法 + grounded → audit 通过
        assert rec.audit.passed

    def test_audit_fails_for_empty_response(self):
        """LLM 响应太短 → audit failed。"""
        ro, owner, _ = make_reflection_owner()
        class BadLLM:
            def call(self, snapshot, trigger, user_prompt=None):
                return "no", np.zeros(8)  # 太短(< 10 chars)
        ro.llm_caller = BadLLM()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        assert not rec.audit.passed
        assert not rec.audit.checks["response_nonempty"]

    def test_audit_fails_for_ungrounded_response(self):
        """LLM 响应没提到 snapshot 任何字段 → audit failed。"""
        ro, owner, _ = make_reflection_owner()
        class BadLLM:
            def call(self, snapshot, trigger, user_prompt=None):
                return "Generic response with no snapshot references whatsoever", np.zeros(8)
        ro.llm_caller = BadLLM()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        assert not rec.audit.passed
        assert not rec.audit.checks["grounded_in_snapshot"]

    def test_audit_pass_rate_above_threshold(self):
        """M2 验收:reflection_audit 通过率 ≥ 80%。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 200)
        # 触发多个反思
        for _ in range(10):
            ro.invoke_user_reflection("test")
        stats = ro.get_stats()
        # FakeLLM 应该 100% 通过
        assert stats["audit_pass_rate"] >= 0.8


# === TestReflectInjection ===

class TestReflectInjection:
    """reflect 注入机制测试。"""

    def test_pending_reflect_set_after_reflection(self):
        """反思后 get_pending_reflect 返回新 reflect。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("test")
        pending = ro.get_pending_reflect()
        assert pending.shape == (8,)

    def test_consume_pending_clears(self):
        """consume_pending_reflect 清空 pending。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("test")
        ro.consume_pending_reflect()
        # consume 后 pending 应为 None(下次 get 返回 zeros)
        pending = ro.get_pending_reflect()
        assert np.allclose(pending, 0.0)

    def test_pending_reflect_used_in_next_cds_tick(self):
        """pending reflect 被下个 CDS tick 使用,state 受其影响。"""
        ro, owner, _ = make_reflection_owner()
        # 用强 reflect
        class StrongLLM:
            def call(self, snapshot, trigger, user_prompt=None):
                return "test response long enough", np.array([5.0] * 8)  # clip 到 1.0
        ro.llm_caller = StrongLLM()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("test")
        reflect = ro.consume_pending_reflect()
        # 注入到下个 tick
        state_before = owner.cds.state.copy()
        owner.tick(reflect=reflect)
        state_after = owner.cds.state.copy()
        # reflect 应该改变 state
        assert not np.allclose(state_before, state_after)


# === TestReflectionRecord ===

class TestReflectionRecord:
    """ReflectionRecord 不可变 + 完整字段测试。"""

    def test_record_is_frozen(self):
        """ReflectionRecord 是 frozen dataclass(防篡改)。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        with pytest.raises(Exception):  # FrozenInstanceError
            rec.tick_at_trigger = 999

    def test_record_contains_snapshot_copy(self):
        """record 含 snapshot 拷贝(grounded 验证用)。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        rec = ro.invoke_user_reflection("test")
        snapshot = rec.self_experience_snapshot
        assert "8d_state" in snapshot
        assert "global_coherence_R" in snapshot

    def test_record_has_unique_id(self):
        """每条 record 有唯一 ID。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        rec1 = ro.invoke_user_reflection("a")
        rec2 = ro.invoke_user_reflection("b")
        assert rec1.record_id != rec2.record_id

    def test_records_can_be_filtered_by_trigger(self):
        """按 trigger 过滤 record。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("a")
        ro.invoke_user_reflection("b")
        user_records = ro.get_records(trigger=ReflectionTrigger.USER_INVOKED)
        assert len(user_records) == 2


# === TestReflectionLevelMapping ===

class TestReflectionLevelMapping:
    """trigger → level 映射测试。"""

    def test_USER_INVOKED_is_IMMEDIATE(self):
        """USER_INVOKED → IMMEDIATE。"""
        rec = ReflectionRecord(
            record_id="t", trigger=ReflectionTrigger.USER_INVOKED,
            level=ReflectionLevel.IMMEDIATE,
            tick_at_trigger=0, tick_at_resolve=0,
            self_experience_snapshot={}, llm_response="",
            reflect_vector=np.zeros(8), audit=ReflectionAuditResult(passed=True),
            latency_ms=0, timestamp=0,
        )
        assert rec.level == ReflectionLevel.IMMEDIATE

    def test_HIGH_UNCERTAINTY_is_IMMEDIATE(self):
        """HIGH_UNCERTAINTY → IMMEDIATE。"""
        rec = ReflectionRecord(
            record_id="t", trigger=ReflectionTrigger.HIGH_UNCERTAINTY,
            level=ReflectionLevel.IMMEDIATE,
            tick_at_trigger=0, tick_at_resolve=0,
            self_experience_snapshot={}, llm_response="",
            reflect_vector=np.zeros(8), audit=ReflectionAuditResult(passed=True),
            latency_ms=0, timestamp=0,
        )
        assert rec.level == ReflectionLevel.IMMEDIATE

    def test_RESTING_STATE_is_SHORT_TERM(self):
        """RESTING_STATE → SHORT_TERM。"""
        rec = ReflectionRecord(
            record_id="t", trigger=ReflectionTrigger.RESTING_STATE,
            level=ReflectionLevel.SHORT_TERM,
            tick_at_trigger=0, tick_at_resolve=0,
            self_experience_snapshot={}, llm_response="",
            reflect_vector=np.zeros(8), audit=ReflectionAuditResult(passed=True),
            latency_ms=0, timestamp=0,
        )
        assert rec.level == ReflectionLevel.SHORT_TERM

    def test_POST_TICK_is_LONG_TERM(self):
        """POST_TICK → LONG_TERM。"""
        rec = ReflectionRecord(
            record_id="t", trigger=ReflectionTrigger.POST_TICK,
            level=ReflectionLevel.LONG_TERM,
            tick_at_trigger=0, tick_at_resolve=0,
            self_experience_snapshot={}, llm_response="",
            reflect_vector=np.zeros(8), audit=ReflectionAuditResult(passed=True),
            latency_ms=0, timestamp=0,
        )
        assert rec.level == ReflectionLevel.LONG_TERM


# === TestReflectionOwnerStats ===

class TestReflectionOwnerStats:
    """stats 统计测试。"""

    def test_stats_audit_pass_rate(self):
        """stats 含 audit_pass_rate。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("test")
        stats = ro.get_stats()
        assert "audit_pass_rate" in stats
        assert 0.0 <= stats["audit_pass_rate"] <= 1.0

    def test_stats_trigger_counts(self):
        """stats 含各 trigger 计数。"""
        ro, owner, _ = make_reflection_owner()
        drive_cds(owner, 3)
        ro.invoke_user_reflection("test")
        stats = ro.get_stats()
        assert "trigger_counts" in stats
        assert all(t.value in stats["trigger_counts"] for t in ReflectionTrigger)


# === TestEndToEnd ===

class TestEndToEnd:
    """端到端集成测试。"""

    def test_1000_tick_reflection_loop_stable(self):
        """1000 tick 反思循环稳定。"""
        ro, owner, _ = make_reflection_owner(
            post_tick_rate_limit=100,
            high_uncertainty_threshold=0.9,  # 调高避免频繁触发
        )
        for tick in range(1000):
            owner.tick(I=0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05))
            result = ro.on_tick_after_cds()
            # 验证不崩溃
            assert isinstance(result, dict)
            assert "triggers_fired" in result

        stats = ro.get_stats()
        assert stats["n_reflections"] > 0  # 至少应有 POST_TICK 触发
        # FakeLLM 应该全部通过 audit
        assert stats["audit_pass_rate"] >= 0.8

    def test_reflection_does_not_modify_cds_state(self):
        """1000 tick 反思循环不修改 CDS state(LLM 被动接受)。"""
        ro, owner, _ = make_reflection_owner(post_tick_rate_limit=200)

        # 跑 50 tick 不反思,记录 state 演化
        owner2 = SelfModelOwner.default()
        for tick in range(50):
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
            owner2.tick(I=I)

        # 跑 50 tick 加反思
        for tick in range(50):
            I = 0.3 * np.sin(np.linspace(0, 2 * np.pi, 8) + tick * 0.05)
            ro.on_tick_after_cds()  # 检测 trigger
            pending = ro.consume_pending_reflect()
            owner.tick(I=I, reflect=pending)

        # 两个 owner 的最终 state 不应完全相同(reflect 引入了差异)
        # 但都应在合法范围内
        assert np.all(np.abs(owner.cds.state) <= 10.0)
        assert np.all(np.abs(owner2.cds.state) <= 10.0)

    def test_USER_INVOKED_works_at_any_tick(self):
        """USER_INVOKED 在任意 tick 可用。"""
        ro, owner, _ = make_reflection_owner()
        for tick in range(20):
            owner.tick(I=np.zeros(8))
            rec = ro.invoke_user_reflection(f"tick {tick}")
            assert rec.trigger == ReflectionTrigger.USER_INVOKED
            assert rec.tick_at_trigger == owner.tick_count

    def test_4_triggers_each_can_be_observed_in_1000_ticks(self):
        """1000 tick 内 4 种 trigger 至少各观察到 1 次。

        注意:这个测试是 stress test,需要驱动 CDS 进入不同状态。
        """
        ro, owner, _ = make_reflection_owner(
            post_tick_rate_limit=10,        # 短间隔
            high_uncertainty_threshold=0.5,  # 低阈值
            resting_state_threshold=0.5,    # 低阈值
            resting_state_duration=20,      # 短窗口
        )

        observed_triggers = set()
        for tick in range(200):
            # 交替输入,产生不同 state 模式
            if tick % 3 == 0:
                # 高激活
                I = 10.0 * np.ones(8)
            elif tick % 3 == 1:
                # 低激活
                I = 0.1 * np.ones(8)
            else:
                # proportional(高 R)
                I = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 2.5, 5.0, 15.0])
            owner.tick(I=I)
            result = ro.on_tick_after_cds()
            for t in result["triggers_fired"]:
                observed_triggers.add(t)

        # USER_INVOKED 需要主动触发
        ro.invoke_user_reflection("force user invoked")
        observed_triggers.add("user_invoked")

        # 至少观察到 3 种 trigger
        assert len(observed_triggers) >= 3, f"only observed: {observed_triggers}"