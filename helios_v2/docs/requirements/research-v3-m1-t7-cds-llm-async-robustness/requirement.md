# M1-T7 CDS 跟 LLM 异步鲁棒性需求

## 背景

v3 设计原则 §5:"LLM 是被动消费者" —— LLM 在 v3 中不参与 tick 控制流,但会异步提供 `reflect` 输入(SelfModelOwner.tick() 的第二参数,8-dim 反思调制)。

M1-T5 SelfModelOwner 已经提供了 `tick(I, reflect, reward)` 接口,但**未验证**:
1. 当 reflect 延迟到达时,CDS tick 循环是否仍然稳定?
2. 当 reflect 延迟抖动时,是否会累积导致 buffer 爆炸?
3. 当 LLM 超时时,CDS 是否能优雅退化?

如果不验证这点,M2-M8 接入真 LLM 后可能出现:
- tick 循环被 LLM 响应阻塞(同步等待)
- buffer 累积导致内存泄漏
- reflect 输入缺失导致 state 发散

## 目标

设计并验证:
1. **AsyncReflectBuffer**:一个时间索引的 reflect 请求 buffer,支持:
   - submit(reflect, current_tick, delay_ticks)
   - advance_to_tick(current_tick) — 时间推进,触发 arrived
   - get_latest_arrived(current_tick) — 取最新 arrived(超过 max_age 视为 stale)
   - cleanup_stale(current_tick) — 清理超时的 pending
2. **simulate_async_loop()**:驱动 CDS tick 循环 + 模拟 LLM 异步 reflect,产出 AsyncSimulationStats
3. **5 个 reflect_pattern**:覆盖 同步 / 快速异步 / 慢速异步 / 随机抖动 / 超时
4. **23 个测试**:单元测试(buffer) + 场景测试(5 pattern) + 性质测试(鲁棒性不变量)

## 验收标准

1. ✅ 90 个 M1 测试全过(67 旧 + 23 新 M1-T7)
2. ✅ 5 场景 × 1000 tick 探针:0 solver failure, 0 NaN, R ∈ [0, 1], state |·| < 30
3. ✅ Buffer 在 max_age=10 下,peak size < 100(防止内存泄漏)
4. ✅ Timeout 场景下,10% 请求被识别为 timeout(>= 50/1000)

## 范围

✅ 包含:AsyncReflectBuffer + simulate_async_loop + 5 reflect_pattern + 23 测试 + 5×1000 探针
❌ 不包含:
- 真 LLM 集成(留到 M5-T1,届时会替换 reflect_pattern 为真 LLM 调用)
- async/await 异步 I/O(M1-T7 只验证同步仿真,真异步集成在 M5-T1)
- reflect 的语义解释(M2 Reflection Owner 会处理)

## 不在范围

- 多线程并行 LLM 调用(本期单线程仿真足够,真并发留到 M5)
- Buffer 持久化(checkpoint 留到 M2 reflection_audit)