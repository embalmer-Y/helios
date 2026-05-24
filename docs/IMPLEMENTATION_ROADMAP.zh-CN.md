# Helios 总任务路标

> Status: Canonical Draft
> Role: 基于新架构哲学与 HLD 的总实施路标
> Constraint: 本文档只定义实施流，不替代 requirement package

## 1. 总体策略

实施必须遵循“先方向、再 requirement、再代码”的顺序。

严格禁止：

1. 在旧 reply-first 架构上继续堆局部修补。
2. 在未明确 owner 的情况下直接加入新状态或 prompt 字段。
3. 在未完成模块命运确认前，对相关大模块做无边界重构。

默认允许：

1. 删除与新哲学冲突的旧接口、旧 wrapper 和旧路径。
2. 在 requirement 明确后直接替换无用旧模块边界，而不是保留兼容层。
3. 将 compatibility 视为例外，而不是本轮重构默认目标。

## 2. 执行阶段

### Phase 0. 模块命运确认

目标：完成 [MODULE_REVIEW_MATRIX.zh-CN.md](MODULE_REVIEW_MATRIX.zh-CN.md) 的逐组确认。

建议确认顺序：

1. Root Runtime / Substrate
2. Cognition / Consciousness Loop
3. Memory / Retrieval
4. Identity / Governance
5. Helios I/O / Channels / Ops
6. Regulation / Behavior Registry
7. Tests / Scripts / Data

每组确认输出：

- 保留原哲学
- 保留实现但改文档/接口
- 重构

### Phase 1. 最小文档集落地

目标：完成新的方向文档体系。

交付物：

1. 架构哲学文档
2. High Level Design
3. requirements index
4. requirement packages
5. 总任务路标

完成条件：新文档已足以约束开发方向，旧文档尚未删除但已失去权威地位。

### Phase 2. requirement packages 编写

建议初始 requirement 集：

1. consciousness-first-llm-loop
2. stimulus-weighting-and-thought-gating
3. thought-to-action-op-bridge
4. identity-bootstrap-and-self-revision
5. memory-tiering-and-directed-retrieval
6. prompt-metric-and-channel-context-contract

如模块矩阵确认后出现额外核心 concern，可新增 package，但不得混装多个独立关切。

### Phase 3. 旧文档清理

目标：在新文档确认后，删除旧架构文档、旧需求文档和历史资料，仅保留最小必要集。

要求：

1. 删除必须在新文档批准后进行。
2. 删除前先修正所有 surviving links。
3. `requirement-authoring-standard.md` 必须保留。

### Phase 4. 代码实施总线

代码实施应按以下工作流推进：

1. Thought loop owner 重构
2. Stimulus / provenance / intensity contract
3. Thought-to-action op bridge
4. Identity bootstrap / self-revision governance
5. Memory tiering / directed retrieval
6. Prompt contract unification
7. Dashboard / scripts / tests / data migration

### Phase 5. 回归与清理

目标：完成测试迁移、数据迁移、无用接口清理和文档收口。

## 3. 每个工作流的实施纪律

### 3.1 Thought loop owner 重构

必须先明确：

- 哪个模块拥有思考门控
- 哪个模块拥有 continuation pressure
- 哪个模块生成 recall intent
- 哪个模块有权产出 action proposal

### 3.2 Stimulus / provenance / intensity contract

必须先明确：

- 输入统一对象是什么
- 输出统一对象是什么
- 各字段上下限和语义是什么
- 哪些模块负责传递和落盘

### 3.3 Thought-to-action op bridge

必须先明确：

- LLM 可以提议到什么粒度
- planner 如何校验
- executor 如何标准化执行
- rejection/fallback 如何记录

### 3.4 Identity governance

必须先明确：

- 首启身份如何注入
- 运行期用户为何不能改
- 内部修订如何申请、审计和应用
- 哪些字段允许演化，哪些字段是底层自我烙印

### 3.5 Memory tiering

必须先明确：

- 四层记忆的功能边界
- directed retrieval 的入口
- retrieval SEC 的职责
- 旧 working/episodic/semantic/autobio 如何迁移

### 3.6 Prompt contract

必须先明确：

- 哪些指标要解释
- 上下限如何表达
- channel 上下文如何描述
- 允许哪些 ops 和参数
- 禁止哪些身份表述

## 4. 批准门槛

进入大规模代码实施前，至少需要满足：

1. 模块审查矩阵完成一轮确认。
2. 架构哲学文档确认。
3. HLD 确认。
4. requirements index 与首批 requirement packages 确认。
5. 旧文档删除范围确认。

## 5. 输出要求

每个阶段结束都应输出：

1. 已确认边界
2. 暂未确认风险
3. 下一阶段输入条件
4. 哪些旧实现暂时允许保留，哪些不允许继续扩展
