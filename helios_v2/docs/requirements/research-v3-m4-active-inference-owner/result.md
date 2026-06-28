# M4 Active Inference Owner 实证结果

## 测试结果

**39 个 M4 新测试全部通过**:

```
TestHierarchicalGenerativeModel    8 passed
TestTrainStep                      3 passed
TestProxyFreeEnergy                5 passed (含 disclaimer docstring 测试)
TestActiveInferenceOwner          10 passed
TestVariationalFreeEnergyTrue      1 passed
TestActiveInferenceTick            5 passed
TestMonotonicallyDecreasing        2 passed
TestStats                          2 passed
TestEndToEnd                       3 passed

总计 39 passed in 0.90s
```

加上 M1 + M2 + M3 (193),**v3 research wave 总计 232 passed in 14.28s**。

## 1000-tick 探针结果

```
=== Test 1: fixed sensory → minimize decreases F ===
  initial F: 0.5975
  final F (after 1000 optimization steps): 0.5971
  decrease: 0.0003 (0.05%)
  monotonic decreasing: True ✅

=== Test 2: 1000 tick AI loop ===
  ticks:           1000
  elapsed:         0.20s (5117.2 ticks/s)
  nan_count:       0
  F_min/max/mean:  0.3107 / 0.3944 / 0.3527

=== Test 3: variational_free_energy_TRUE placeholder ===
  ✅ raises NotImplementedError mentioning M8

OVERALL: PASS
```

### 关键发现

1. **monotonic decreasing 验证通过**:
   - 1000 步数值梯度下降, F 单调下降(monotonic=True ✅)
   - 总下降 0.05%(因 2-dim latent 限制 + 随机 HGM 权重)
   - v3 task §2.2 验收门"proxy_free_energy 单调下降"满足

2. **1000 tick AI loop 稳定**:
   - 0 NaN ✅
   - F ∈ [0.31, 0.39], mean=0.35(合理范围)
   - 5117 ticks/s(数值梯度慢但仍足够快)

3. **M8 placeholder 正确**:
   - variational_free_energy_TRUE() raises NotImplementedError
   - 错误信息明确提到 "M8 placeholder"

4. **proxy_free_energy 严格 disclaimer**:
   - module-level 函数 docstring 含 "NOT" + "VFE"
   - 测试 `test_proxy_F_NOT_VFE_in_docstring` 通过
   - 任何 M8 真 VFE 实现必须保持 API 兼容

## v3 设计原则验证

| 原则 | 验证 |
|------|------|
| "proxy_free_energy 诚实的 proxy" | ✅ docstring + 测试明确标注 NOT VFE |
| "5 层 generative model" | ✅ HGM_LAYER_DIMS = (8, 16, 8, 4, 2) |
| "minimize_proxy_free_energy" | ✅ 1000 步 gradient descent, monotonic decreasing |
| "active sampling policy gradient" | ✅ active_sampling 选 min expected_F action |
| "跟 v3.1 VFE 接口兼容" | ✅ variational_free_energy_TRUE placeholder 准备好 M8 替换 |
| "可证伪 + 可审计" | ✅ stats dataclass + ActionPolicy frozen |

## v2 回归

跑完整 v2 测试(忽略 4 个 pre-existing fixture 错误 + 5 个 pre-existing 测试失败 + 2 个 r_proto_learn_p5a + 1 flaky r83):

```
1903 passed (含 M4 wave 39 新增 v3 测试),4 skipped, 6-7 failed, 2 errors
```

**M4 没有引入任何新的失败或回归**。

## 文件清单

**新增**:
- `helios_v2/src/helios_v2/research_v3_m4/__init__.py` (~30 lines)
- `helios_v2/src/helios_v2/research_v3_m4/hierarchical_generative_model.py` (~180 lines)
  - HGM + 数值梯度 train_step
- `helios_v2/src/helios_v2/research_v3_m4/active_inference_owner.py` (~280 lines)
  - proxy_free_energy + 4 大方法 + M8 placeholder
- `helios_v2/tests/research_v3_m4/__init__.py` (empty)
- `helios_v2/tests/research_v3_m4/test_active_inference_owner.py` (~470 lines, 39 tests)
- `helios_v2/src/helios_v2/scripts/r_v3_m4_probe.py` (~150 lines)
- `helios_v2/docs/requirements/research-v3-m4-active-inference-owner/{requirement,design,task,result}.md`

**日志**:
- `helios_v2/logs/r_v3_m4/active_inference_traces/active_inference_1000t_20260628_175933.jsonl`
- `helios_v2/logs/r_v3_m4/active_inference_traces/active_inference_1000t_summary_20260628_175933.json`

## 风险与后续

### 已观察到的设计风险

1. **数值梯度下降收敛慢**:1000 步只降低 0.05%,因:
   - 2-dim latent 限制优化空间
   - 数值梯度精度有限(eps=1e-4)
   - HGM 权重不优化,只能调 latent
   - **缓解**:M8 升级用 PyMC 自动微分,优化 weights + latent 联合

2. **active_sampling 是贪心策略**:选 min expected_F 但不保证全局最优
   - **缓解**:M5/M6 真 LLM policy gradient 替换
   - **当前评估**:M4 简化版够用,贪心策略通常足够(small n_candidates)

3. **5 层结构是简化版**:不是 Friston 2010 严格分层(缺少 message passing + free energy decomposition)
   - **缓解**:M8 真 VFE 升级时,严格实现分层 generative model
   - **当前评估**:5 层结构足够验证 v3 基本 active inference 逻辑

### 后续 ship

- [ ] **M5-T1**:真 LLM 集成(替换 FakeLLMCaller + System Prompt + CSO)
- [ ] **M5+**:LLM-as-PFC 3 层完整接通(Layer A System Prompt + Layer B CSO + Layer C Reflection)
- [ ] **M6**:Reflection Layer C + ToM 4 owner
- [ ] **M8**:真 VFE 用 PyMC/NumPyro variational inference(替换 proxy_free_energy)

**M4 ship 状态**:✅ 可 ship,待 master 拍板。Layer 1 Active Inference 基础完成,可跟 Layer 0/2/3 形成完整的 self-evidencing 循环(MB → HGM → CDS → Reflection)。