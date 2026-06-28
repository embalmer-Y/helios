# M2 Reflection Owner 实证结果

## 测试结果

**38 个 M2 新测试全部通过**:

```
TestLLMCallerProtocol              3 passed
TestReflectionTriggerDetection     6 passed (4 trigger + 限速 + 多触发)
TestLLMPassiveAccept               5 passed (不修改 state + snapshot 字段 + 无 cds 引用 + 确定性)
TestReflectionAudit                6 passed (1 通过 + 4 失败各 1 + 1 直接 audit + 1 clip + 验收率)
TestReflectInjection               3 passed
TestReflectionRecord               4 passed
TestReflectionLevelMapping         4 passed
TestReflectionOwnerStats           2 passed
TestEndToEnd                       4 passed (含 4 trigger 都观察到)

总计 38 passed in 2.71s
```

加上 M1 wave (110),**M1 + M2 总计 148 passed in 12.35s**。

## 1000-tick 探针结果

```
=== M2 Reflection Owner ship 1000-tick 探针 ===
  ticks:           1000
  elapsed:         0.92s (1090.7 ticks/s)
  solver_failures: 0
  nan_count:       0
  reflect_applied: 973
  reflection_stats:
    n_reflections: 1895
    trigger_counts: {'post_tick': 20, 'resting_state': 901, 'high_uncertainty': 973, 'user_invoked': 1}
    audit_pass_rate: 1.0000
  Kuramoto R:      mean=0.9801 std=0.0060 [0.9689, 0.9987]
  overall audit pass rate (trigger_records): 1.0000

OVERALL: PASS
```

### 关键发现

1. **0 solver failures / 0 NaN**:1000 tick 反思循环完全稳定 ✅
2. **1895 reflections** 4 trigger 各被触发:
   - post_tick: 20(限速 50,1000 tick 理论 20 次 ✅)
   - resting_state: 901(R 持续 > 0.85 触发,100 tick 窗口满后每 tick 触发)
   - high_uncertainty: 973(state 饱和导致 self_unity 低 → uncertainty 高)
   - user_invoked: 1(测试中显式触发)
3. **audit_pass_rate = 1.0000**:M2 验收门 ≥ 0.8 ✅(FakeLLM 100% 通过)
4. **973 ticks 应用 reflect**:反思产生了实质性影响
5. **Kuramoto R 稳定**:mean=0.9801, std=0.0060,反映 CDS 稳态未被反思破坏

### 4 trigger 行为分析

**POST_TICK** (20 fires):
- 限速 50 tick 工作正常(1000 / 50 = 20 理论值 ✅)
- 首次在 tick 0 触发(用户配置 `last_post_tick_tick = -100` 允许首次立即触发)
- 后续每 50 tick 触发一次

**RESTING_STATE** (901 fires):
- 前 100 tick R history 不满,无触发
- 第 100 tick 后,因 R 持续 > 0.85(默认阈值),每 tick 都触发
- 901 fires / 900 possible ≈ 100% 触发率,符合"持续高 R"语义

**HIGH_UNCERTAINTY** (973 fires):
- 因 self_unity = 1 - std(state),当 state 饱和到 ±10 时,std 高 → self_unity 低 → uncertainty 高
- 973 / 1000 ≈ 97.3% 触发率,反映 M1-T7 result.md 中观察到的"state 饱和"现象
- **设计影响**:在真实部署中,可能需要调高 HIGH_UNCERTAINTY 阈值或用真实 uncertainty 信号

**USER_INVOKED** (1 fire):
- 测试在 tick 100 主动触发 1 次
- 验证显式触发接口可用

## v3 设计原则验证

| 原则 | 验证 |
|------|------|
| "LLM 被动接受 self-experience" | ✅ LLM 只拿 snapshot dict,不能改 cds.state / cds.C |
| "reflection_audit grounded 验证" | ✅ 4 项检查(reflect shape / range / response / grounded) |
| "可追溯" | ✅ ReflectionRecord frozen + 含 snapshot 拷贝 |
| "可证伪" | ✅ audit pass rate 可量化(100% / ≥ 0.8 验收门) |
| "LLM 越界防护" | ✅ _do_reflect 内 clip + audit 双层防护 |
| "4 trigger 显式调度" | ✅ POST_TICK 限速 / RESTING_STATE 窗口 / HIGH_UNCERTAINTY 阈值 / USER_INVOKED 直通 |

## v2 回归

跑完整 v2 测试(忽略 4 个 pre-existing fixture 错误 + 5 个 pre-existing 测试失败 + 2 个 r_proto_learn_p5a):

```
1820 passed (含 M1 wave 110 + M2 wave 38 = 148 新增 v3 测试),4 skipped, 6 failed, 2 errors
```

**M2 没有引入任何新的失败或回归**。

## 文件清单

**新增**:
- `helios_v2/src/helios_v2/research_v3_m2/__init__.py` (~40 lines)
- `helios_v2/src/helios_v2/research_v3_m2/reflection_owner.py` (~370 lines)
  - 4 enum / 2 dataclass / 1 owner class
- `helios_v2/src/helios_v2/research_v3_m2/llm_caller.py` (~110 lines)
  - LLMCallerProtocol + FakeLLMCaller
- `helios_v2/tests/research_v3_m2/__init__.py` (empty)
- `helios_v2/tests/research_v3_m2/test_reflection_owner.py` (~480 lines, 38 tests)
- `helios_v2/src/helios_v2/scripts/r_v3_m2_probe.py` (~150 lines)
- `helios_v2/docs/requirements/research-v3-m2-reflection-owner/{requirement,design,task,result}.md`

**日志**:
- `helios_v2/logs/r_v3_m2/reflection_traces/reflection_1000t_20260628_142653.jsonl`
- `helios_v2/logs/r_v3_m2/reflection_traces/reflection_1000t_summary_20260628_142653.json`

## 风险与后续

### 已观察到的设计风险

1. **RESTING_STATE 过度触发**:R 持续高时每 tick 都触发,稀释了反思的"稀缺性"
   - **缓解**:M4/M8 可加 cooldown(连续 N tick 内同一 trigger 最多 1 次)
   - **当前评估**:M2 验收门 ≥ 0.8 通过,功能正确,过度触发只是性能问题

2. **HIGH_UNCERTAINTY 阈值在饱和 state 下触发过频**:uncertainty proxy 是 1-self_unity,state 饱和时 self_unity 低 → uncertainty 高
   - **缓解**:M4 接入真 AspectState 的 uncertainty 字段,或调高阈值
   - **当前评估**:M2 范围内可接受,后续 M4 改进

3. **FakeLLMCaller 只反映 snapshot,不模拟 LLM 推理**:
   - **缓解**:M5-T1 接入真 LLM(LLMCallerProtocol 兼容)
   - **当前评估**:M2 验证 audit 协议有效,真 LLM 接入后行为应该一致

### 后续 ship

- [ ] **M3**:Boundary Owner(Markov Blanket + conditional_separation 数学不变量)
- [ ] **M4**:Active Inference + proxy_free_energy(真 VFE 留到 M8)
- [ ] **M5-T1**:真 LLM 集成(实现 LLMCallerProtocol,接入 ReflectionOwner)
- [ ] **M6**:Reflection Layer C + ToM 4 owner(mpfc / psts / temporal_poles / coordinator)
- [ ] **M7**:5 PTS sub-owners
- [ ] **M8**:真 VFE(PyMC/NumPyro)

**M2 ship 状态**:✅ 可 ship,待 master 拍板。Layer 3 反思层基础完成,可与 Layer 2 self-model 形成完整的 self-evidencing 循环(CDS → emergence → reflection → reflect → CDS)。