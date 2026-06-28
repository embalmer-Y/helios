# M2 Reflection Owner 需求

## 背景

v3 设计原则 §5.3:"LLM 被动接受 self-experience(不做主动协调)"。Layer 3 Reflection Subsystem 是 v3 self-evidencing 循环的关键环节,但目前 M1 wave 完成了 Layer 2(SelfModelOwner + EmergenceDetector)后,**没有** Layer 3 的实现:

- 4 trigger 缺失(POST_TICK / RESTING_STATE / HIGH_UNCERTAINTY / USER_INVOKED)
- LLM passive accept 接口缺失(reflect 注入机制未实现)
- reflection_audit grounded 验证缺失
- 4-level scheduling 未规划

没有 Layer 3,v3 self-model 只能"被 CDS 演化驱动",无法"反思自己的演化"。

## 目标

实现 `ReflectionOwner`(Layer 3 反思 owner),提供:

1. **4 trigger 机制**:每 CDS tick 后检测 trigger 并可能触发反思
   - `POST_TICK`: 每 tick 后(限速 50 tick 间隔)
   - `RESTING_STATE`: Kuramoto R 持续 > 0.85 持续 100 tick
   - `HIGH_UNCERTAINTY`: uncertainty(代理 1-self_unity)> 0.7
   - `USER_INVOKED`: 调用者主动触发

2. **4-level scheduling**:`IMMEDIATE / SHORT_TERM / MEDIUM_TERM / LONG_TERM`
   - USER_INVOKED / HIGH_UNCERTAINTY → IMMEDIATE
   - RESTING_STATE → SHORT_TERM
   - POST_TICK → LONG_TERM

3. **LLM passive accept**:LLM 只读 self_experience snapshot,**绝不能**修改 8d state 或 C

4. **reflection_audit grounded 验证**:4 项检查
   - reflect shape = (8,)
   - reflect ∈ [-1, 1]
   - response 非空且 ≥ 10 chars
   - response 提到 snapshot 的至少一个关键字段(R / rochat / trigger)

5. **reflect 注入机制**:reflection 产生的 8-dim reflect 注入下个 CDS tick

6. **`FakeLLMCaller`**:deterministic LLM stub,基于 snapshot heuristic 产生 reflect(M5 替换为真 LLM)

## 验收标准(v3 task §1.2)

1. ✅ 4 trigger 各自正确触发
2. ✅ LLM 只能调 I 和 reflect,**不能修改** C 或 8d state
3. ✅ reflection_audit 通过率 ≥ 80%
4. ✅ 1000 tick 不崩溃,solver 0 failure,0 NaN
5. ✅ 38 个 M2 测试全过(M1 wave 110 + M2 wave 38 = 148 passed)

## 范围

✅ 包含:
- `ReflectionTrigger` enum(4 种)
- `ReflectionLevel` enum(4 级)
- `ReflectionRecord` frozen dataclass
- `ReflectionAuditResult` frozen dataclass
- `ReflectionOwner` 类(含 4 trigger 检测 + LLM 调用 + audit + reflect 注入)
- `FakeLLMCaller` deterministic stub
- `LLMCallerProtocol` interface(M5 替换)
- 38 个测试
- 1000-tick 探针

❌ 不包含:
- 真 LLM 集成(M5-T1,届时实现 LLMCallerProtocol 即可)
- reflection persistence(checkpoint 留到 M4)
- governance 红线检查(M4 governance owner)
- 跨 session 的反思历史检索(M8)

## 不在范围

- ToM 4 owner(M6)
- PTS sub-owners(M7)
- 真 VFE(M8)