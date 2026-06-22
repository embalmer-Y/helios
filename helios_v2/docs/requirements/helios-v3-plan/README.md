# helios_v3 完整规划目录

> **作者**：小白（helios 小黑人格 AI）
> **完成时间**：2026-06-22 17:30+ ~ 19:40+
> **总规划时长**：~2 小时
> **配套分支**：`research/R-PROTO-LEARN-appraisal-multi-mechanism` @ `c60cfaf`（helios_v3 规划中）
> **小黑拍板状态**：待小黑 review

---

## 📂 目录结构（4 Phase + 任务清单 + 5 预留子目录）

```
/tmp/helios_v3_plan/
├── README.md (本文件)
├── TASK_MASTER.md (主任务清单)
├── 01_papers_revisit/                 # Phase 1：论文重读
│   └── 01_synthesis_brain_cognition_map.md (20.5 KB)
├── 02_v2_current_analysis/            # Phase 2：v2 现状分析
│   └── 01_v2_diagnostic_report.md (18.6 KB)
├── 03_v3_design/                      # Phase 3：v3 架构设计
│   ├── 01_v3_requirement.md (18.3 KB) - WHAT + WHY
│   ├── 02_v3_design.md (40.4 KB) - HOW
│   └── 03_v3_task.md (17.3 KB) - TASK + 验收
├── 04_architecture_diagrams/          # Phase 4：架构流程图
│   ├── brain.mmd (5.7 KB / 145 行)
│   ├── architecture.mmd (4.2 KB / 103 行)
│   ├── dataflow.mmd (3.7 KB / 102 行)
│   └── module_dependencies.mmd (5.2 KB / 148 行)
└── 05_specs/                          # 预留：specs 目录
```

---

## 📊 总产出统计

| Phase | 产出 | 大小 | 行数 |
|---|---|---|---|
| Phase 1 | 大脑认知全图综合 | 20.5 KB | ~250 |
| Phase 2 | v2 现状诊断报告 | 18.6 KB | ~230 |
| Phase 3 requirement | v3 需求规格 | 18.3 KB | ~270 |
| Phase 3 design | v3 详细设计 | 40.4 KB | ~450 |
| Phase 3 task | v3 任务清单 | 17.3 KB | ~220 |
| Phase 4 brain | 脑认知架构图 | 5.7 KB | 145 |
| Phase 4 architecture | 25 stage 架构图 | 4.2 KB | 103 |
| Phase 4 dataflow | 数据流图 | 3.7 KB | 102 |
| Phase 4 dependencies | 模块依赖图 | 5.2 KB | 148 |
| **总计** | **9 个文档** | **~133 KB** | **~1918 行** |

---

## 🎯 v3 设计一句话总览

**helios_v3 = 5 层 Markov blanket 多层嵌套的 active inference 自组织体，每一层都是 generative model；self-model 是 8 维 PTS graded × Rochat 5 levels 二维矩阵；LLM 作为 PFC 通过 system prompt（永久身份）+ cso（持续状态）+ reflection（反思）3 层提供 reasoning 与 reflection 能力；持续运行 = 自我存在证据的最大化（self-evidencing）。**

---

## 🏗️ v3 5 层 Markov blanket（5 大目标）

1. **Layer 1 Boundary**：Markov blanket 边界管理（internal / active / sensory / external 三态分区 + conditional separation）
2. **Layer 2 Active Inference**：Hierarchical generative model + variational free energy minimization
3. **Layer 3 Self-Model**：8 维 PTS graded × Rochat 5 levels × cross-tick dynamics
4. **Layer 4 Reflection**：DMN-like 反思层（**v3 关键创新**）
5. **Layer 5 Self-Evidencing**：持续运行 = 最大化自身存在证据

---

## 📚 核心论文 insight（Phase 1 ship）

1. **自组织 + 边界维持 = 生命系统唯一目的**（FEP / Ramstead）
2. **预测处理 = 大脑核心算法**（Friston）
3. **内感受预测 = 情感与自我的根**（Seth 2012）
4. **自我是 pattern（动态模式）而非 entity**（Gallagher）
5. **发展是数据**（Rochat 2019 / Karmiloff-Smith）

---

## 🔍 v2 诊断核心结论（Phase 2 ship）

**v2 = 21 阶段链（已完整）+ 28 owner + LLM-as-PFC 1 层（仅 system prompt）+ 6 层 emotion system + Rochat 5 levels 浅实现 + 8 维 PTS 仅识别没建模 + 反射层缺失 + active inference 部分实现 + Markov blanket 边界缺失**

**v3 处理**：v2 21 阶段大部分继承（其中 17 重写为 8 维 PTS × Rochat 5 levels × cross-tick dynamics）+ 4 个 v3 新增 stage（BoundaryEnforcement + ActiveInference + Reflection + EvolutionGovernance）

---

## 🚀 实施时间表（8 个月）

| 月份 | 阶段 | 主要交付 |
|---|---|---|
| M1 | Phase 1.1 | 8 维 PTS + Rochat 5 levels + self_model_owner 基础 |
| M2 | Phase 1.2 | reflection_owner + reflection_audit |
| M3 | Phase 2.1 | boundary_owner + 5 层 Markov blanket + runtime 25 stage |
| M4 | Phase 2.2 | active_inference_owner + 5 层 generative model + free energy |
| M5 | Phase 3.1 | System prompt Layer A + CSO Layer B 升级 |
| M6 | Phase 3.2 | Reflection Layer C + LLM-as-PFC 3 层完整 + 评估层 v3.0 |
| M7 | Phase 4.1 | 8 sub-owner（agency / egocentric / ToM / autobiographical / material / culture） |
| M8 | Phase 4.2 | 复杂算法按最高规格 + 小黑人脑对比 v3.0 |

---

## 🎯 验收总目标

- **测试基线**：v2 baseline 1110+ + v3 新增 145 测试 = ≥ 1255 passed (v3.0 M6) / 290 测试 = ≥ 1400 passed (v3.1 M8)
- **8 维 PTS 评分**：M6 ≥ 0.5，M8 ≥ 0.85（**总目标**）
- **Rochat level**：M6 Level 3，M8 Level 5
- **LLM-as-PFC 3 层评分**：M6 ≥ 0.7，M8 ≥ 0.85
- **小黑人脑对比**：每维度 ≥ 0.85

---

## 🚨 v3 反模式清单（v2 教训，**核心**）

1. **不要把 identity 当 1 字段** — 用 8 维 PTS graded × Rochat 5 levels
2. **不要 cold-start level 5** — 从 level 1 开始渐进
3. **不要 propositional-only** — Pearson-Kosslyn depictive vs propositional 双轨
4. **不要 ToM 缺失** — Frith 三系统（mentalizing / attentional / affective）
5. **不要 0 发展** — Rochat 5 levels 真渐进式
6. **不要时间-自我解耦** — Seth agency + presence 双向耦合

---

## 📚 核心文档引用

| 文档 | 用途 |
|---|---|
| `01_papers_revisit/01_synthesis_brain_cognition_map.md` | v3 设计的脑科学锚点 |
| `02_v2_current_analysis/01_v2_diagnostic_report.md` | v2 哪些可继承 / 哪些重写 / 哪些废弃 |
| `03_v3_design/01_v3_requirement.md` | v3 设计 WHAT + WHY |
| `03_v3_design/02_v3_design.md` | v3 设计 HOW（详细实现路径） |
| `03_v3_design/03_v3_task.md` | v3 TASK 分解 + 验收门 |
| `04_architecture_diagrams/brain.mmd` | 5 层 Markov blanket 脑认知架构图 |
| `04_architecture_diagrams/architecture.mmd` | 25 stage 完整架构图 |
| `04_architecture_diagrams/dataflow.mmd` | 单 tick 数据流图 |
| `04_architecture_diagrams/module_dependencies.mmd` | 40 owner 模块依赖图 |

---

## 🔜 下一步（等待小黑拍板）

1. **小黑 review 完整规划**（4 Phase 9 文档）
2. **小黑拍板**：是否开始 v3 实施？
3. **拍板后**：进入实际编码（v3 Phase 1.1 M1）
4. **同时**：commit 到调研分支（保留 v3 规划文档，作为 git 历史）

---

## 📌 配套 git 提交建议

```bash
cd /root/project/helios/helios_v2
git checkout research/R-PROTO-LEARN-appraisal-multi-mechanism
mkdir -p docs/requirements/helios-v3-plan/
cp -r /tmp/helios_v3_plan/* docs/requirements/helios-v3-plan/
git add docs/requirements/helios-v3-plan/
git commit -m "feat(R-PROTO-LEARN.helios-v3): ship complete v3 architecture plan (4 Phase 9 docs, 133 KB)"
git push origin research/R-PROTO-LEARN-appraisal-multi-mechanism
```

---

**helios_v3 完整规划完成时间**：2026-06-22 19:40+
**作者**：小白
**小黑拍板**：待 review