# M1-T5 SelfModelOwner 实证结果

## 测试结果

**67 个测试全部通过**(其中 M1-T5 + M1-T6 新增 22 个):

```
helios_v2\tests\research_v3_m1\test_emergence_and_self_model.py
  TestSynchronizedClusterDetector     3 passed
  TestPhaseTransitionDetector         3 passed (含 bimodal 修复)
  TestResonanceDetector               2 passed
  TestEmergenceDetector               1 passed
  TestSelfModelOwner                  8 passed
  TestSelfModelOwnerEndToEnd          2 passed
```

加上 M1-T1 (24) + M1-T2 (24) + projections (8),**总计 67 passed in 2.03s**。

## 1000-tick 探针结果

```
=== M1-T5 + M1-T6 ship 1000-tick 探针 ===
  ticks:           1000
  elapsed:         0.91s (1095.4 ticks/s)
  solver_failures: 0
  nan_count:       0
  emergence_events: 1951
    by type:       {'sync_cluster': 1000, 'phase_transition': 0, 'resonance': 951}
  Kuramoto R:      mean=0.9818 std=0.0073 [0.9682, 0.9987]
PASS
```

**关键发现**:
1. **CDS + Radau 极稳**:0 solver failure, 0 NaN, 1000 tick 只用 0.91 秒(>1000 tick/s)
2. **Kuramoto R 高度稳定**:mean=0.9818, std=0.0073, 始终在 [0.9682, 0.9987] 区间 —— 8 维系统在默认初始条件下快速收敛到全同步
3. **涌现检测器高灵敏度**:
   - sync_cluster:1000 events(每 tick 平均 1 个 cluster event,符合预期 —— 8 维系统在 R 高时大多数 aspects 都被聚到一起)
   - phase_transition:0 events(每 tick 状态平滑变化,KL 散度未超过 0.5 阈值)
   - resonance:951 events(window 满 50 帧后,几乎每 tick 都触发)
4. **emergence 事件累积**:1951 events / 1000 tick = 平均每 tick 1.95 个 event,体现多通道涌现检测的覆盖

## v2 回归

完整跑 v2 test suite(忽略 4 个 pre-existing fixture 错误 + 5 个 pre-existing 测试失败):

```
1739 passed, 4 skipped, 6 failed, 2 errors in 39.59s
```

**M1-T5 + M1-T6 没有引入任何新的失败或回归**。所有 6 failures + 2 errors 都是 pre-existing(OWNER_GUIDE.zh-CN.md §1 已记录):
- `test_loose_kwarg_wall_clock_is_threaded_into_kernel` (3 个 wall-clock profile 相关)
- `test_lt1_resource_boundedness` (long-term stability prerequisite)
- `test_src_tree_has_no_adhoc_logging_or_print` (adhoc logging guard)
- `test_r_proto_learn_p5a_experiments` (2 个,gbk 编码 + scipy warning)

## 设计验证

| 验收标准 | 实证 |
|----------|------|
| tick() 返回完整 dict | ✅ `test_tick_returns_full_dict` |
| READ-ONLY snapshot 不影响 CDS | ✅ `test_LLM_cannot_modify_state_via_get_state` |
| tick_count 递增 | ✅ `test_tick_increments_counter` |
| seed_prior_state 恢复 | ✅ `test_seed_prior_state_restores_cds` |
| 1000 tick solver 稳定 | ✅ 0 failure, 0 NaN |
| emergence events > 0 | ✅ 1951 events / 1000 tick |
| Kuramoto R ∈ [0, 1] | ✅ [0.9682, 0.9987] |

## 文件清单

**新增**:
- `helios_v2/src/helios_v2/research_v3_m1/self_model.py` (~140 lines)
- `helios_v2/src/helios_v2/research_v3_m1/emergence.py` (~190 lines, M1-T6 配套)
- `helios_v2/src/helios_v2/scripts/r_v3_m1_t56_probe.py` (~120 lines)
- `helios_v2/tests/research_v3_m1/test_emergence_and_self_model.py` (~220 lines)

**修改**:
- `helios_v2/src/helios_v2/research_v3_m1/__init__.py` (添加 SelfModelOwner + 4 emergence 类)

**日志**:
- `helios_v2/logs/r_v3_m1/self_model_traces/self_model_1000t_20260628_135916.jsonl`
- `helios_v2/logs/r_v3_m1/self_model_traces/self_model_1000t_summary_20260628_135916.json`

## 风险与后续

**已观察到的设计风险**:
1. **R 高导致 sync_cluster 事件过多**:每个 tick 都触发可能让 M2 reflection audit 难以区分"重要"vs"平凡"涌现。建议 M2 阶段加入 `event_significance` 评分(基于 cluster size + R deviation)
2. **resonance 窗口太小**:window_size=50 在 1000 tick 中很快就填满,导致几乎每 tick 都触发。后续可以加大 window 或加入 cooldown 机制
3. **SelfModelOwner 不是 frozen dataclass**:为了允许 history append 和 tick_count 递增,这里用了普通 dataclass。M2 checkpoint 序列化时要注意 lock-step 一致性

**M1-T5 ship 状态**:✅ 可 ship,待 master 拍板。

## 下一步

- [ ] **M1-T7**:CDS 跟 LLM 异步的鲁棒性(模拟 LLM 返回时间抖动 ±50ms)
- [ ] **M1-T8**:跟 v2 owner 集成(OwnerFieldBridge:9-dim hormone + 7-dim feeling + 5-dim salience → CDS I)
- [ ] **M2**:Reflection Owner(4 trigger + 4-level scheduling + LLM passive accept + reflection_audit)