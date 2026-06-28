# M1-T2: 8 维 CDS + Radau stiff solver 收敛性实证(WHAT + WHY)

> **任务**:helios_v3 M1-T2 —— 8 维耦合动力系统(CDS)+ Radau stiff solver 数值积分实证
> **完成时间**:2026-06-28 ship
> **作者**:helios 调研分支(综合 v3 plan §03_v3_design + 03_v3_task M1-T1/T2)
> **配套**:design.md + task.md + result.md

## 0. 一句话总览

**用 scipy.solve_ivp(method='Radau') 数值积分 v3 plan §3.2 定义的 8 维 stiff ODE(5 维快 + 3 维慢,α 差 500 倍),实证 1000 tick 演化数值稳定 + Kuramoto R order parameter 计算正确 + Reward-Hebbian C 矩阵学习不溢出 + Rochat 5 levels 分段合理,为 M1-T5/T6/T7/T8 提供数据底座。**

## 1. 研究问题

v3 plan §3.2 核心数据结构和 ODE 演化:
```
ds/dt = -alpha * s + C · tanh(s) + beta * I + gamma * reflect
R(t) = (1/8) |sum exp(i * theta_i)|,  theta_i = arctan(s_i / scale_i)
```

8 维 PTS 维度 alpha 衰减率:[5.0, 2.0, 1.0, 0.5, 0.3, 0.1, 0.05, 0.01](max/min = 500 倍,典型 stiff ODE)。

本 ship 实证 5 件事:
1. **Radau 数值稳定**:solve_ivp(method='Radau') 在 rtol=1e-4 atol=1e-6 下,1000 tick 内 state 始终 bounded,无 NaN/Inf。
2. **Kuramoto R 计算正确**:R ∈ [0, 1],同步状态 → R ≈ 1.0,反相关 → R < 1.0,Rochat level 离散化 ∈ {0, 1, 2, 3, 4, 5}。
3. **Reward-Hebbian 学习不溢出**:高 reward 推动 C 矩阵变化,但归一化保证 |C|max ≤ 1.0。
4. **C 矩阵方向性学习**:正 reward 增强 state × state 外积的方向。
5. **跨 tick carry**:seed_prior_state 正确恢复 state 和 C。

## 2. 成功标准(可证伪)

1. **Radau 收敛**:1000 tick 内 solver.success = True,无 NaN/Inf
2. **State bounded**:state ∈ [-10, 10] (clip 保护)
3. **Kuramoto R ∈ [0, 1]**:order parameter 数学正确
4. **Rochat 5 levels**:rochat_level_discrete ∈ {0, 1, 2, 3, 4, 5}
5. **|C|max ≤ 1.0**:归一化防发散
6. **24+ 单元测试 100% passed**

## 3. ship 7 件套

- [x] requirement.md(本文件)
- [x] design.md(HOW)
- [x] task.md(TASK + 验收)
- [x] result.md(ship 总结)
- [x] helios_v2/src/helios_v2/research_v3_m1/cds.py(实现)
- [x] helios_v2/tests/research_v3_m1/test_cds.py(24+ 单元测试)
- [x] helios_v2/src/helios_v2/scripts/r_v3_m1_t2_probe.py(1000-tick production trace probe)
- [x] helios_v2/logs/r_v3_m1/cds_traces/cds_1000t_*.jsonl(trace 落盘)

## 4. 依赖

- scipy 1.16.3(已装,v2 间接依赖)
- numpy 2.3.5(已装)
- M1-T1 AspectState 数据结构(M1-T2 ship 时已 ship)

## 5. 4 个拍板问题(主人 2026-06-21 红线)

1. ✅ 下一步研究问题对齐 v3 plan §3.2
2. ⚠️ alpha 衰减率序列(5.0 → 0.01)直接引用 v3 plan,无新设计决策
3. ⚠️ Kuramoto scale 异构 [1, 1, 1, 1, 1, 5, 10, 30] 直接引用 v3 plan §2
4. ✅ 不需要凭证/算力(纯本地数值积分)
