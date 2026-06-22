# helios_v3 架构规划 — 主任务清单

## 决策记录（2026-06-22 17:30+）

### 小黑拍板
- **v3 跟 v2 关系**：A（v3 完全重写，v2 作为 reference 停止开发）
- **v3 范围**：6 大改造全包含 + LLM-as-PFC 3 层
- **5-layer 划分**：先综合研判后自行决定
- **执行顺序**：按计划推进
- **设计规格**：**最高规格**（真实大脑工作细节 + LLM 局限性权衡 + 复杂算法/神经网络部分按最高规格）

### 4 个 Phase

#### Phase 1：重读所有论文（预估 1-2h）
- 11 份已有调研（/tmp/helios_brain_gap/, /tmp/human_self_cognition_survey.md, BRAIN_ARCHITECTURE_COMPARISON.md）
- 6 篇精读报告（/tmp/helios_brain_gap/02_papers_summary_v2.md）
- 输出：综合大脑认知全图 + 关键论文必读清单 + v3 设计原则

#### Phase 2：v2 现状详细分析（预估 1-2h）
- 28 owner 全部 engine.py 详细读
- runtime/stages.py 流程图梳理
- P5 framework 当前状态
- 哪些复用 / 哪些重写 / 哪些废弃
- 输出：v2 现状诊断报告（哪些资产可继承）

#### Phase 3：v3 架构设计（预估 4-6h）—— **核心**
- 综合 6 大改造 + LLM-as-PFC + 论文全图
- 模块划分（5-layer Markov blanket，**自行研判**）
- 30+ 模块设计 spec
- 复杂算法部分（Neural / Bayesian / Optimization）按最高规格
- LLM 局限性权衡（system prompt 永久身份 / cso 持续状态 / reflection 反思）
- 输出：v3 完整设计文档（requirement + design + task + result）

#### Phase 4：架构流程图（预估 1-2h）
- 新流程图（基于 Markov blanket + 8 维 PTS + Rochat 5 levels）
- 模块交互图
- LLM-as-PFC 流程图
- 输出：多张架构图（mermaid + ASCII）

#### Phase 5：ship + commit（0.5h）
- 写到 docs/requirements/research-helios-v3-architecture/
- 提交 commit + push 远端
- 写日报

## 总时间预估
6.5-9.5 小时一次性完成