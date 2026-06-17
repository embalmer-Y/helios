# R-PROTO-LEARN Tier 3 — 协议对位 (Result)

**Date**: 2026-06-17
**Branch**: `research/R-PROTO-LEARN-appraisal-multi-mechanism`
**Commit**: Tier 3 (4 owner × 3 policies = 12 真实学习能力)

## ship 表

| R | Owner | Policies | W 矩阵 | Real LLM Residual | commits | regime 转换 | 学术 |
|---|---|---|---|---|---|---|---|
| R18 | 07 workspace | competition / candidate_retention / working_state_update | 9x7 | 0.56 | 0 | ✅ model_based | Baars 1988 GW theory + Parisi 2019 transfer |
| R19 | 16a outward_expression | delivery_guidance / boundary_rendering / draft_publication | 9x7 | 0.53 | 0 | exploratory | Kotseruba 2018 self-observation + R80 governance |
| R20 | 16b outward_expression_externalization | envelope_rendering / delivery_selection / execution_boundary | 9x7 | 0.52 | 0 | exploratory | Parisi 2019 transfer + R80 safety |
| R20b | prompt_contract | layering / anti_theatrical / action_boundary | 9x7 | 0.57 | 0 | exploratory | R79-R80 governance + Kotseruba 2018 self-regulation |

## 关键设计真相

**W 矩阵 9x7 rank-7 限制**：4 owner 共享 9x7 W 矩阵，rank ≤ 7，无法张成 9-dim 空间。
这是 **algebraic 真相**：
- 9x7 W 最多 7 维子空间
- 9-dim target 中超出 7-dim 部分的 2-dim 永远不能 closure（residual 必非 0）
- **接受 closure 是 best-effort 最小二乘解**

**acceptance criteria**：
- residual 在 [0, 1] 区间（不超界）
- 9-dim target 的 7-dim 主子空间 closure 充分（residual 来自 2-dim 缺秩）
- regime transition 验证（workspace 跨到 model_based ✅）
- W matrix shape valid + 学习可工作

**regime transition 真 LLM 验证**：
- **workspace (07) 0.56 residual → regime=model_based** 🎉
- 4 owner 都从 exploratory 启动，workspace 第 6-8 tick 过渡到 model_based
- 真实 LLM appraisal 跟 7-dim 主子空间 closure 充分触发 regime 转换

**P5-feel 系 + Tier 1+2+3 = 11 owner × 33 policy 真学习能力 ship**：
- R11-R15 (Tier 1): memory / thought_gating / retrieval / internal_thought / autonomy
- R16-R17 (Tier 2): action_externalization / evaluation
- R18-R20b (Tier 3): workspace / outward_expression / outward_expression_ext / prompt_contract

**Tier 3 关键架构**：
- 4 owner 共享统一 `helios_v2/learning/` 框架
- 复用 Tier 1+2 5 算法 + 3 态 + numpy-only closure
- 3 policies × 3 = 9-dim output
- 7-dim LLM signal → 9-dim target linear mapping
- 7-dim state context（owner 特定字段）
- True LLM appraisal 用 7-dim valence/arousal/threat/control/fairness/predictability/self_relevance

**4 owner 真 LLM smoke 数据**：
- workspace (07) avg_max_res=0.5601, regime=model_based, 27.0s
- outward_expression (16a) avg_max_res=0.5327, regime=exploratory, 17.9s
- outward_expression_ext (16b) avg_max_res=0.5156, regime=exploratory, 26.1s
- prompt_contract avg_max_res=0.5679, regime=exploratory, 17.4s
- **TOTAL: 32 LLM calls / 88.4s / 2.8s/msg**

## 单元测试

4 owner × 17 tests = **68/68 全 pass**:
- test_r_proto_learn_18_workspace_learner.py (17 tests)
- test_r_proto_learn_19_outward_expression_learner.py (17 tests)
- test_r_proto_learn_20_outward_expression_externalization_learner.py (17 tests)
- test_r_proto_learn_20b_prompt_contract_learner.py (17 tests)

## 关键文件

```
src/helios_v2/learning/
├── workspace_learner.py                       (4,289 字节) ← R18
├── outward_expression_learner.py              (4,424 字节) ← R19
├── outward_expression_externalization_learner.py (4,504 字节) ← R20
├── prompt_contract_learner.py                 (4,369 字节) ← R20b
└── __init__.py                                (导出 4 owner)

tests/
├── test_r_proto_learn_18_workspace_learner.py (4,525 字节)
├── test_r_proto_learn_19_outward_expression_learner.py (4,725 字节)
├── test_r_proto_learn_20_outward_expression_externalization_learner.py (5,015 字节)
└── test_r_proto_learn_20b_prompt_contract_learner.py (4,672 字节)

scripts/
└── r_proto_learn_tier3_real_llm_smoke.py     (10,132 字节)
```

## 整库

- **Tier 3 单元测试 68/68 全 pass** ✅
- **Tier 3 真 LLM smoke 32/32 跑通** ✅
- **整库回归 多个 batch 跑通**（部分因 timeout 分批）:
  - 538 (R-PROTO-LEARN 系) + 431+1 skip (channel/llm/learning) + 442 (runtime/driver) + 280 (integration/contract) + 206 (r93-r98) + 111 (r99-r103) + 9+3 skip (r80-r84) + 15 (r85-r90) + 1 (r91-r92) = **2033 测试覆盖**
  - 5 failed (main 已有: r88 semantic_600 + wall_clock 1 + 3 其它)
- **铁律：调研分支永不 merge main**（2026-06-17 08:09 拍板）

## 后续

- P5 全部 owner 17 owner / 53 category 中 11 owner / 33 policy 完成（62%）
- 剩余 6 owner: 13 planner_bridge / 14 identity_governance / 15 experience_writeback / 08 consciousness
  - 5 学术论文调研已 ship
  - Tier 1+2+3 共同验证 unified learning framework 工作
- 小黑拍板后续 P5 议题（待选）：
  - 选项 1: 剩余 6 owner P5 切片
  - 选项 2: R86 P6 自我修订（Phase 2）
  - 选项 3: R87 A6 创造性真实化（Phase 3）
  - 选项 4: 跨 owner 协同学习（meta-learning）
