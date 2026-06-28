# M2 Reflection Owner 设计

## 架构

```
              SelfModelOwner (Layer 2)
              tick() returns 8d state + R + self_experience
                       |
                       | get_state_for_llm() READ-ONLY snapshot
                       v
              ReflectionOwner (Layer 3)
              +---------------------------------+
              |  on_tick_after_cds()            |
              |  - 检测 4 trigger               |
              |  - 调用 LLM (passive accept)    |
              |  - reflection_audit             |
              |  - 存 ReflectionRecord          |
              |  - 存 pending reflect           |
              +---------------------------------+
                       |
                       | get_pending_reflect()
                       v
              下个 CDS tick(I, reflect=...)
```

## 4 trigger 实现

| Trigger | 检测逻辑 | Level |
|---------|---------|-------|
| **POST_TICK** | `current_tick - last_post_tick_tick >= post_tick_rate_limit`(默认 50) | LONG_TERM |
| **RESTING_STATE** | `len(R_history) >= 100 AND all(R > 0.85)` | SHORT_TERM |
| **HIGH_UNCERTAINTY** | `uncertainty > 0.7`(proxy: `max(0, 1 - self_unity)`) | IMMEDIATE |
| **USER_INVOKED** | 调用者主动调 `invoke_user_reflection(prompt)` | IMMEDIATE |

**关键**:
- POST_TICK 限速避免反思泛滥(50 tick = 大约每分钟反思一次)
- RESTING_STATE 用窗口均值,避免单 tick R 抖动误触发
- HIGH_UNCERTAINTY 用 1-self_unity 作 proxy(避免引入 AspectState 依赖)
- USER_INVOKED 是唯一显式触发,绕过所有自动 trigger 检测

## LLM 被动接受契约

```python
@runtime_checkable
class LLMCallerProtocol(Protocol):
    def call(self, snapshot: dict, trigger: str, user_prompt: str | None = None) -> tuple[str, np.ndarray]:
        ...
```

**关键约束**:
1. LLM 拿到 `snapshot`(dict),**不能**反序列化出 cds 引用本身
2. LLM 返回 `(text_response, reflect_vector)`
3. `reflect_vector` 在 `_do_reflect` 内 clip 到 [-1, 1](防 LLM 越界)
4. LLM 永远不会收到 `cds.state` 引用,只能通过 snapshot dict 修改其值(改 snapshot 不影响 cds)

**安全机制**:
- `__post_init__` 验证 `llm_caller` 实现了 `LLMCallerProtocol`
- `snapshot` 不含 `cds` / `C` 字段(只有 `coupling_matrix_summary`)
- 测试 `test_LLM_does_not_get_cds_reference` 验证此约束

## reflection_audit 4 项检查

```python
def _audit_reflection(snapshot, llm_response, reflect_vec) -> ReflectionAuditResult:
    checks = {
        "reflect_shape_ok": reflect_vec.shape == (8,),       # shape 必须是 (8,)
        "reflect_range_ok": np.all(np.abs(reflect_vec) <= 1.0),  # ∈ [-1, 1]
        "response_nonempty": len(llm_response) >= 10,       # response ≥ 10 chars
        "grounded_in_snapshot": any([
            f"R={R:.3f}" in llm_response or f"R = {R:.3f}" in llm_response,
            str(rochat_discrete) in llm_response,
            "trigger=" in llm_response,
        ]),
    }
    passed = all(checks.values())
    return ReflectionAuditResult(passed, reasons, checks)
```

**关键设计**:
- 4 项检查**全部**必须通过才算 grounded
- grounded 检查不强求 R 数值精确匹配(LLM 可能四舍五入),但要求 R / rochat / trigger 至少出现一个
- audit 失败不阻止反思记录,但计入 `n_audit_failures`,M2 验收要求 pass rate ≥ 80%

## reflect 注入机制

```python
def get_pending_reflect(self) -> np.ndarray:
    """返回当前应注入 CDS 的 reflect(8-dim)。"""
    if self._pending_reflect is None:
        return np.zeros(8)
    return self._pending_reflect.copy()

def consume_pending_reflect(self) -> np.ndarray:
    """返回并清空 pending reflect(一次性消费)。"""
    r = self.get_pending_reflect()
    self._pending_reflect = None
    return r
```

**调用模式**:
```python
for tick in range(n_ticks):
    # 1. 消费上次的 reflect
    reflect = ro.consume_pending_reflect()
    # 2. CDS tick 用 reflect
    owner.tick(I=..., reflect=reflect)
    # 3. 检测 trigger 并可能产生新 reflect
    ro.on_tick_after_cds()
```

## ReflectionRecord 不可变

```python
@dataclass(frozen=True)
class ReflectionRecord:
    record_id: str  # uuid
    trigger: ReflectionTrigger
    level: ReflectionLevel
    tick_at_trigger: int
    tick_at_resolve: int
    self_experience_snapshot: dict  # 浅拷贝(防后续 mutation)
    llm_response: str
    reflect_vector: np.ndarray      # clip 后
    audit: ReflectionAuditResult
    latency_ms: float
    timestamp: float                # wall-clock
```

**为什么 frozen**:
- 反思记录是不可变审计证据(类似 v2 的 reflection_audit)
- 防止 reflection_owner 后续逻辑意外篡改历史
- 允许安全地跨进程/线程共享

## FakeLLMCaller heuristic

```python
def call(self, snapshot, trigger, user_prompt=None):
    R = snapshot["global_coherence_R"]
    state = np.array(snapshot["8d_state"])
    reflect = np.zeros(8)

    if R > 0.7:
        # 全同步:弱调制(确认系统稳定)
        reflect = 0.05 * np.sin(np.linspace(0, 2π, 8))
    elif R < 0.3:
        # 低同步:强调制(尝试激发)
        reflect = 0.4 * np.cos(np.linspace(0, π, 8))
    else:
        # 中等:按维度启发
        for i in range(8):
            if abs(state[i]) > 5.0:
                reflect[i] = -0.3 * np.sign(state[i])
            else:
                reflect[i] = 0.1 * state[i] / 5.0

    reflect = np.clip(reflect, -1, 1)
    response = f"[fake-llm] trigger={trigger} R={R:.3f} rochat={...} state_max={...}"
    return response, reflect
```

**关键**:
- deterministic:相同 snapshot → 相同 reflect
- 响应**总是提到 R**(便于 audit 检查 grounded)
- 设计简单,只反映 snapshot 状态(不模拟 LLM 推理)

## 测试覆盖(38 个)

| 测试类 | 数量 | 覆盖点 |
|--------|------|--------|
| `TestLLMCallerProtocol` | 3 | Protocol 接口 / 自定义 caller / TypeError 拒绝 |
| `TestReflectionTriggerDetection` | 6 | 4 trigger 各自 + 限速 + 多触发并发 |
| `TestLLMPassiveAccept` | 5 | 不可修改 state / snapshot 字段 / 无 cds 引用 / 确定性 |
| `TestReflectionAudit` | 6 | 通过 + 4 项失败各 1 + 验收通过率 |
| `TestReflectInjection` | 3 | pending 设置 / consume 清空 / 注入生效 |
| `TestReflectionRecord` | 4 | frozen / 含 snapshot / 唯一 ID / filter |
| `TestReflectionLevelMapping` | 4 | 4 trigger → 4 level 映射 |
| `TestReflectionOwnerStats` | 2 | audit_pass_rate + trigger_counts |
| `TestEndToEnd` | 4 | 1000 tick 稳定 / 不改 state / USER_INVOKED / 4 trigger 都观察到 |

## 关键设计决策

### 决策 1:LLM clip 在 audit 之前

**选择**:LLM 返回的 reflect 先 clip 到 [-1, 1],然后 audit。

**理由**:
- 防止 LLM 越界导致 CDS 状态爆炸
- audit 检查的是"将注入 CDS 的 reflect"是否合法,clip 后总合法
- LLM 越界行为被静默纠正(下次可观察 audit_pass_rate 是否下降)

**风险**:LLM 故意越界无法被 audit 检测。**缓解**:M5 接入真 LLM 后,可以增加 "raw_reflect_range_ok" audit 检查。

### 决策 2:POST_TICK 用 LLM 响应验证 grounded

**选择**:POST_TICK 的 audit 不放宽要求(跟其他 trigger 一样严格)。

**理由**:
- 防止"POST_TICK 反思泛滥但都是空话"
- M2 验收要求 audit pass rate ≥ 80%,所有 trigger 同标准

### 决策 3:USER_INVOKED 不限速

**选择**:USER_INVOKED 不受 post_tick_rate_limit 限制。

**理由**:
- USER_INVOKED 是显式触发,调用者知道自己在做什么
- 限速会让用户感觉"为什么按了没反应"
- 信任调用者(测试中验证多次调用都成功)

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 反思泛滥 | POST_TICK 限速 50 tick |
| RESTING_STATE 误触发 | 窗口 100 tick 持续高 R |
| LLM 越界 | _do_reflect 内强制 clip |
| audit 漏检 grounded | 3 重检查(R / rochat / trigger) |
| ReflectionRecord 被改 | frozen=True |
| pending_reflect 累积 | consume_pending_reflect 一次性清空 |