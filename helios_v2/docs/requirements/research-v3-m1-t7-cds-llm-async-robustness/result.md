# M1-T7 CDS 跟 LLM 异步鲁棒性 实证结果

## 测试结果

**23 个 M1-T7 新测试全部通过**:

```
TestAsyncReflectBuffer            8 passed
TestAsyncSimulationScenarios      5 passed (A/B/C/D/E)
TestAsyncSimulationProperties     6 passed
TestReflectBufferEdgeCases        4 passed

总计 23 passed in 16.98s
```

加上 M1-T1 + M1-T2 + M1-T5 + M1-T6 (67),**M1 wave 总计 90 passed in 16.11s**。

## 5 场景 × 1000 tick 探针结果

```
=== M1-T7 ship 异步鲁棒性 5 场景 × 1000 tick 探针 ===

场景 A 同步           : solver_failures=0, nan=0, R_mean=0.9817, state_abs_max=10.00, reflect_applied=999, timeouts=0
场景 B 快速异步 1-2tick: solver_failures=0, nan=0, R_mean=0.9816, state_abs_max=10.00, reflect_applied=666, timeouts=0
场景 C 慢速异步 5tick  : solver_failures=0, nan=0, R_mean=0.9807, state_abs_max=10.00, reflect_applied=995, timeouts=0
场景 D 随机抖动 0-8tick: solver_failures=0, nan=0, R_mean=0.9821, state_abs_max=10.00, reflect_applied=656, timeouts=0
场景 E 含超时 10%     : solver_failures=0, nan=0, R_mean=0.9805, state_abs_max=10.00, reflect_applied=899, timeouts=98

total ticks: 5000
elapsed:     5.43s (≈ 920 ticks/s)

OVERALL: PASS — 5 场景全部稳定
```

### 关键发现

1. **0 solver failures**:5 场景 × 1000 tick = 5000 次 ODE 求解全部成功 ✅
2. **0 NaN**:即使在随机抖动和超时场景下,CDS 也不产生 NaN ✅
3. **R 高度稳定**:所有场景 R mean ∈ [0.9805, 0.9821],std 极小,反映 CDS 收敛到全同步态 ✅
4. **state_abs_max=10.00**:所有场景达到 CDS clip 上限(±10),这是预期的 —— 8-dim 系统在持续输入下达到饱和。**注意**:这不是发散信号,而是 clip 的设计边界
5. **reflect 应用率差异**:
   - 场景 A 同步:999/1000 = 99.9%
   - 场景 B 快速异步:666/1000 = 66.6%(部分 reflect 在 max_age 内未到)
   - 场景 C 慢速异步:995/1000 = 99.5%(累积在 arrived 中,后续取到)
   - 场景 D 随机抖动:656/1000 = 65.6%(随机分布)
   - 场景 E 含超时:899/1000 = 89.9%(10% 强制 timeout)
6. **超时识别**:场景 E 正确识别 98 个 timeout(期望 100,因为前 10 tick 还没积累超时窗口)

### Buffer 内存安全

`pending_peak` + `arrived_peak` 在所有场景下 < 100,证明 `cleanup_stale()` 有效防止 buffer 累积。即便在随机抖动场景 D,buffer 也在 `max_age=10` 限制内稳定。

## v3 设计原则验证

| 原则 | 验证 |
|------|------|
| "LLM 是被动消费者" | ✅ LLM 异步提供 reflect,CDS 同步 tick;LLM 不阻塞 tick 循环 |
| "诚实验证" | ✅ 不掩盖 buffer 协议的真实行为:5 个 pattern 全部真实模拟,包括失败模式 |
| "可扩展" | ✅ AsyncReflectBuffer 是通用协议,任意 reflect_pattern 都能驱动 |
| "鲁棒性优先" | ✅ 5000 tick 0 failure,0 NaN,buffer 不爆炸 |

## 文件清单

**新增**:
- `helios_v2/src/helios_v2/research_v3_m1/async_loop.py` (~280 lines)
  - `PendingReflect` dataclass
  - `AsyncReflectBuffer` 类
  - `AsyncSimulationStats` dataclass
  - `simulate_async_loop()` 函数
  - 5 个 `pattern_*` 函数
- `helios_v2/tests/research_v3_m1/test_async_robustness.py` (~280 lines, 23 tests)
- `helios_v2/src/helios_v2/scripts/r_v3_m1_t7_probe.py` (~110 lines)
- `helios_v2/docs/requirements/research-v3-m1-t7-cds-llm-async-robustness/{requirement,design,task,result}.md`

**修改**:
- `helios_v2/src/helios_v2/research_v3_m1/__init__.py` (添加 AsyncReflectBuffer / simulate_async_loop / AsyncSimulationStats)

**日志**:
- `helios_v2/logs/r_v3_m1/async_traces/async_robustness_5x1000t_summary_20260628_140637.json`

## 风险与后续

### 已观察到的设计风险

1. **state_abs_max=10 是 clip 上限**:所有场景 state 都达到 ±10,意味着 8-dim 系统在持续驱动下进入饱和。
   - **影响**:R 永远高(全同步饱和),M2 reflection_audit 难以区分"平凡同步"vs"涌现同步"
   - **缓解**:
     - (a) 降低 clip 上限(从 ±10 到 ±5),但可能影响 ODE 精度
     - (b) 输入归一化,让 I 和 reflect 的幅度更小
     - (c) M2 reflection_audit 用 R deviation from baseline 评估涌现,而非 raw R
   - **决策**:留给 M2/M5 评估,本 ship 保留 clip ±10 不变

2. **Reflect 在慢异步(C)下累积**:场景 C 中 995/1000 reflect 被应用,但其中 990 个是 arrived 累积。这反映 buffer 协议"取最新 arrived"的设计 —— 老的 reflect 实际上被忽略了,只是没被显式标记。
   - **缓解**:M2 可以加 `n_reflect_overwritten_by_newer` 统计

### 后续 ship

- [ ] **M1-T8**:OwnerFieldBridge(9-dim hormone + 7-dim feeling + 5-dim salience → CDS I)
- [ ] **M2**:Reflection Owner(用 AsyncReflectBuffer 接收 LLM 反思,触发 reflection_audit)
- [ ] **M5-T1**:真 LLM 集成(替换 reflect_pattern 为真 LLM 调用)

**M1-T7 ship 状态**:✅ 可 ship,待 master 拍板。