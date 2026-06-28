# M1-T2: 8 维 CDS + Radau stiff solver(TASK + 验收)

> **任务**:M1-T2 ship 任务清单
> **完成时间**:2026-06-28

## 1. ship 任务清单

| Task ID | 任务 | 状态 |
|---|---|---|
| T2-1 | CDSODEParams dataclass (alpha/beta/gamma/rtol/atol) | ✅ |
| T2-2 | CoupledDynamicalSystem class + Radau 数值积分 | ✅ |
| T2-3 | kuramoto_R + Rochat 5 levels 分段 | ✅ |
| T2-4 | Reward-Hebbian update_C + 归一化 | ✅ |
| T2-5 | self_experience 涌现态(LLM 被动接受接口) | ✅ |
| T2-6 | seed_prior_state 跨 tick carry | ✅ |
| T2-7 | test_cds.py 24+ 单元测试 | ✅ |
| T2-8 | 1000-tick production trace probe | ✅ |

## 2. 验收门

1. ✅ v2 baseline 100% passed
2. ✅ M1-T2 ≥ 24 单元测试 100% passed
3. ✅ Radau 收敛:1000 tick 0 solver failures
4. ✅ Kuramoto R ∈ [0, 1],Rochat 5 levels 合理
5. ✅ |C|max ≤ 1.0 归一化有效
6. ✅ 1000-tick production trace 落盘

## 3. 执行步骤(已 ship)

```bash
cd d:\Software\project\helios
pytest helios_v2/tests/research_v3_m1/test_cds.py -v   # 24 passed
python -m helios_v2.scripts.r_v3_m1_t2_probe --ticks 1000   # 0 failures
```

## 4. ship 后待主人拍板 4 个问题

1. ✅ 对齐 v3 plan §3.2
2. ⚠️ alpha 序列 + scale 序列均引用 v3 plan,无新设计决策
3. ⚠️ Kuramoto R 实现细节(scale 异构、Rochat 5 段分段)需主人审阅
4. ✅ 不需要凭证/算力

**待主人拍板后启动 M1-T3**(EmergenceDetector 实证)。
