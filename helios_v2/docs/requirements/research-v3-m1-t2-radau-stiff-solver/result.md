# M1-T2: 8 维 CDS + Radau stiff solver(ship 总结)

> **完成时间**:2026-06-28
> **作者**:helios 调研分支

## ship 状态

- [x] 6 个文件全部 ship 到工作区
- [x] 单元测试 **24 passed / 0 failed**
- [x] 1000-tick production probe:**0 solver failures, 0 NaN, Kuramoto R mean=0.9811**
- [ ] git commit(待执行)
- [ ] git push(待执行)

## 执行结果

### 单元测试(M1-T2 24 个)

- `helios_v2/tests/research_v3_m1/test_cds.py`:24 tests passed
- 测试覆盖:
  - TestCDSODEParams:alpha 500x 范围、beta/gamma 8 维、rtol/atol 默认 (4 tests)
  - TestCDSColdStart:默认 state=0、C=0.1*I、Kuramoto R=1 (3 tests)
  - TestCDSTickConvergence:single tick success、100 tick 稳定、**1000 tick 不发散** (4 tests)
  - TestKuramotoR:R ∈ [0,1]、R=1 (proportional)、R<1 (orthogonal)、Rochat discrete levels (4 tests)
  - TestRewardHebbian:归一化 |C|max ≤ 1、zero reward 不变、directional 学习 (3 tests)
  - TestSelfExperience:keys 完整、agency_strength = PTS 2 (2 tests)
  - TestSeedPriorState:restore state、validate shape、restore C (3 tests)
  - TestPTSDimensionNames:8 dim 名字 (1 test)

### 1000-tick production probe

- `python -m helios_v2.scripts.r_v3_m1_t2_probe --ticks 1000`
- 结果:
  - **Solver failures: 0 (0.00%)**
  - **NaN count: 0**
  - **State max abs: 1.5369**(始终 bounded)
  - **Kuramoto R: min=0.9736, max=0.9986, mean=0.9811**(超过 M6 目标 0.4)
  - **C matrix: max_abs=0.1000**(reward 小,C 变化小,但归一化有效)
- trace 落盘:`helios_v2/logs/r_v3_m1/cds_traces/cds_1000t_*.jsonl`

### 关键发现

1. **Radau stiff solver 在 8 维 stiff ODE 上完全稳定**
   - 5 维快(alpha=5.0~0.3) + 3 维慢(alpha=0.1~0.01)
   - 1000 tick 内 0 失败
   - state 始终 bounded (max=1.54,远小于 10 clip 上限)

2. **Kuramoto R 计算正确**
   - 全同步状态(state ∝ scale)→ R ≈ 1.0
   - 反相关状态 → R < 1.0
   - 实测 1000 tick mean R = 0.98(说明动态输入 + C 矩阵耦合下系统自发高相干)

3. **Reward-Hebbian 归一化有效**
   - 高 reward (10.0) + 大 lr (0.5) 测试下,100 次 update 后 |C|max ≤ 1.0

4. **Rochat 5 levels 分段合理**
   - discrete level ∈ {0, 1, 2, 3, 4, 5}
   - mean R = 0.98 → Level 4 Permanence(接近 Level 5)

## 验证门

- [x] v2 baseline 100% passed
- [x] M1-T2 ≥ 24 单元测试 100% passed
- [x] Radau 收敛(1000 tick,0 failures)
- [x] Kuramoto R ∈ [0, 1]
- [x] Rochat 5 levels 合理
- [x] |C|max ≤ 1.0 归一化
- [x] 1000-tick production trace 落盘

## 4 个拍板问题状态

1. ✅ 对齐 v3 plan §3.2
2. ⚠️ alpha 序列 + scale 序列均引用 v3 plan,无新设计决策
3. ⚠️ Kuramoto R 实现细节(scale 异构、Rochat 5 段分段)需主人审阅
4. ✅ 不需要凭证/算力

## 后续

**M1-T3**(待主人拍板启动):
- EmergenceDetector(sync clusters + phase transitions + resonance)
- 同步集群:基于 Kuramoto R + state 距离的 hierarchical clustering
- 相变检测:KL 散度 + change point detection
- 共振检测:FFT-based frequency analysis
- 8 维 ODE 跟 LLM 异步鲁棒性(M1-T7)

## 6 个 ship 文件

```
helios_v2/src/helios_v2/research_v3_m1/cds.py
helios_v2/src/helios_v2/research_v3_m1/__init__.py (updated)
helios_v2/tests/research_v3_m1/test_cds.py
helios_v2/src/helios_v2/scripts/r_v3_m1_t2_probe.py
helios_v2/docs/requirements/research-v3-m1-t2-radau-stiff-solver/{requirement,design,task,result}.md
helios_v2/logs/r_v3_m1/cds_traces/cds_1000t_*.jsonl (production trace)
```
