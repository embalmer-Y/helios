# helios_v3 完整规划目录

> **作者**：小白（helios 小黑人格 AI）
> **完成时间**：2026-06-22 17:30+ ~ 19:48+ / 2026-06-23 04:00+（按 4 项决策 + 3 个子选项 + 8 维耦合动力系统重写）
> **总规划时长**：~2.3h（4 Phase ship）+ ~0.5h（5 项小黑 review + 修复 ship）
> **配套分支**：`research/R-PROTO-LEARN-appraisal-multi-mechanism`
> **小黑拍板状态**：**已 review + 拍板 4 项决策 + 3 个子选项 + 已修复 ship**

---

## 📂 目录结构（4 Phase + 5 预留子目录 + 13 文件）

```
/tmp/helios_v3_plan/
├── README.md (本文件)
├── TASK_MASTER.md
├── 01_papers_revisit/01_synthesis_brain_cognition_map.md
├── 02_v2_current_analysis/01_v2_diagnostic_report.md
├── 03_v3_design/
│   ├── 01_v3_requirement.md (重写)
│   ├── 02_v3_design.md (重写)
│   └── 03_v3_task.md (重写)
├── 04_architecture_diagrams/ (4 个 mermaid 全部重画)
│   ├── brain.mmd
│   ├── architecture.mmd
│   ├── dataflow.mmd
│   └── module_dependencies.mmd
├── 05_self_model_design.md (4 项决策详细设计)
├── references.md (11 篇论文 DOI)
└── 05_specs/ (预留)
```

---

## 📊 总产出统计

| 文件 | 大小 | 行数 |
|---|---|---|
| `01_synthesis_brain_cognition_map.md` | 27.1 KB | 507 |
| `01_v2_diagnostic_report.md` | 22.1 KB | 495 |
| `01_v3_requirement.md`（重写） | 10.0 KB | ~250 |
| `02_v3_design.md`（重写） | 14.0 KB | ~350 |
| `03_v3_task.md`（重写） | 6.9 KB | ~200 |
| `05_self_model_design.md` | 23.4 KB | 636 |
| `references.md` | 11.8 KB | 216 |
| `04_architecture_diagrams/*.mmd`（重画） | 15.5 KB | 498 |
| `README.md` + `TASK_MASTER.md` | 9.0 KB | 209 |
| **总计** | **~140 KB** | **~3361 行** |

---

## 🎯 v3 设计一句话总览

**helios_v3 = 5 个嵌套自组织系统（仅最外层 Layer 0 为严格 Markov blanket）+ 8 维耦合动力系统（Coupled Dynamical System）作为 self-model + LLM-as-PFC 3 层（system prompt + cso + reflection，被动接受）+ 8 维 ODE 数值积分（Radau）+ Reward-Hebbian 耦合矩阵学习 + Kuramoto order parameter 作为 Rochat level + variational free energy minimization 的 active inference + 持续运行 = 自我存在证据的最大化（self-evidencing）。**

---

## 🏗️ 5 个嵌套子系统（**不是** 5 层 Markov blanket）

| Layer | 名称 | 性质 |
|---|---|---|
| **Layer 0** | **Markov Blanket** | **严格** MB（internal ⊥ external \| sensory） |
| **Layer 1** | **Active Inference Subsystem** | 8 维 generative model + proxy_free_energy (v3.0) / VFE (v3.1) |
| **Layer 2** | **Self-Model Subsystem** | 8 维耦合动力系统（CDS） + Kuramoto R |
| **Layer 3** | **Reflection Subsystem** | DMN-like 4 trigger + LLM 被动接受 |
| **Layer 4** | **Self-Evidencing Subsystem** | 4 个 fitness gate + audit |

**重要修正**：v3 文档早期版本用"5 层 Markov blanket"——这在数学上不严谨。**严格意义的 MB 只有 Layer 0**。

---

## 🔬 8 维耦合动力系统（self-model 核心）

### 数学
$$ds/dt = -αs + C·tanh(s) + βI + γ·reflect$$
$$R(t) = (1/8) |Σ e^{iθ_i(t)}| ∈ [0, 1]$$
$$dC/dt = η · r(t) · s · s^T$$

### 8 维 PTS dimension
1. Bodily Processes (BP) - α=5.0
2. Minimal Experiential (ME) - α=2.0
3. Affective (AF) - α=1.0
4. Intersubjective (IS) - α=0.5
5. Psychological/Cognitive (PC) - α=0.3
6. Narrative (NA) - α=0.1
7. Ecological/Extended (EE) - α=0.05
8. Normative (NO) - α=0.01

### 3 个子选项决策
- 6.1 ODE 方案：**(a) 8 维单 ODE + Radau**
- 6.2 C 学习：**(ii) Reward-Hebbian**
- 6.3 self-experience 涌现：**(Y) LLM 被动接受**

---

## 🚨 v2 验收标准继承（**不是** 测试基线继承）

v3 继承 v2 的**验收维度**：
- D1-D10 评分维度
- 28 owner 测试套件
- 6 governance 红线
- observability + audit

v3 新增验收：
- 8 维 ODE 收敛性
- C 矩阵稳定性
- Kuramoto R 演化
- self-experience 涌现合理性
- proxy_free_energy 单调下降（v3.0）
- VFE 单调下降（v3.1）

---

## 📚 11 篇核心论文

全部有 DOI（详见 `references.md`）：
- 8 篇已有本地 PDF
- 3 篇仅有 DOI（Barrett 2017 / Rao & Ballard 1999 / Friston 2010，M1 阶段补下载）

---

## 🚀 实施时间表（8 个月）

| 月份 | 阶段 | 主要交付 |
|---|---|---|
| M1 | Phase 1.1 | 8 维耦合动力系统 + Kuramoto R + Reward-Hebbian |
| M2 | Phase 1.2 | Reflection Owner + LLM 被动接受 |
| M3 | Phase 2.1 | Boundary Owner + 严格 MB + runtime 25 stage |
| M4 | Phase 2.2 | Active Inference + proxy_free_energy（诚实降级） |
| M5 | Phase 3.1 | System Prompt + CSO 升级 |
| M6 | Phase 3.2 | Reflection Layer C + ToM 4 owner + 评估层 v3.0 |
| M7 | Phase 4.1 | 5 PTS sub-owner（agency/egocentric/autobio/material/culture） |
| M8 | Phase 4.2 | 真 VFE（PyMC/NumPyro）+ 复杂算法 + 小黑人脑对比 |

---

## 🎯 验收总目标

- **测试基线**：v2 baseline 1110+ + v3 新增 145（M6）= 1255+ / 290（M8）= 1400+
- **Kuramoto R 评分**：M6 R ≥ 0.4，M8 R ≥ 0.85
- **8 维 ODE 收敛性**：每 tick R 单调不减
- **C 矩阵稳定性**：|C| ≤ 1.0
- **LLM-as-PFC 3 层**：完整接通
- **proxy_free_energy**：M4-M6 单调下降
- **VFE**：M8 单调下降
- **Self-evidencing**：fitness gate 严格性 ≥ 99%
- **小黑人脑对比**：8 维 PTS 评分 ≥ 0.85

---

## 🚨 4 项小黑拍板决策汇总

| # | 决策 | 实质 |
|---|---|---|
| 1 | A：5 个嵌套自组织系统 | 仅最外层是严格 MB |
| 2 | 验收标准继承 | v2 验收维度继承（不是"测试基线"） |
| 3 | A+D 组合 | v3.0 `proxy_free_energy`（诚实）+ v3.1 真 VFE |
| 4 | 3 sub-owners + 1 coordinator | mpfc / psts / temporal_poles + tom_coordinator |
| 5 | 8 维耦合动力系统 | CDS + Kuramoto R + Reward-Hebbian + 涌现 |

---

## 📌 配套 git 提交

调研分支 `research/R-PROTO-LEARN-appraisal-multi-mechanism` 已 ship 3 个 commit：
- `7ce4ed9` v3 完整规划（11 文件）
- `3d12037` references.md 修复（11 文件 + 1 references）
- `967d5ba` self-model redesign 详细设计（12 文件 + 1 self_model_design）
- **（待 ship）** 批量更新 11 个 v3 文档（按 4 项决策 + 3 个子选项 + 8 维 CDS 重写）

---

**helios_v3 完整规划最终 ship 时间**：2026-06-23 04:00+ UTC
**作者**：小白
**小黑拍板**：已完成，**等批量更新 ship**