# Helios 项目整体架构

> Status: Active
> Audience: 开发者、维护者、后续架构演进工作
> Source of truth: 以当前代码实现为准；本文件描述其稳定边界和主流程

## 1. 项目定位

Helios 不是面向单次任务的脚本集合，而是一个持续运行的情感-认知代理。系统以 `helios_main.py` 为主循环入口，围绕情感底盘、记忆系统、认知层、调节层和 I/O 边界进行组织。

清理与迁移完成后，项目的核心目标是保持三件事清晰分离：

- 仓库根目录只保留运行入口和基础情感/生理底盘
- `helios_io/` 统一承接所有外部接口与传输适配
- `core/` 只保留与传输无关的内部运行基础设施

## 2. 运行总览

单独查看图：`diagrams/runtime_loop_overview.zh-CN.md`

这个视角强调的是“持续闭环”，而不是一次调用链。系统不会在发出一次回复后结束，而是把外部输入、内部状态变化、行为结果和后续接触重新送回下一轮 tick。

为了避免文档漂移，这里刻意保持抽象：图中只表达当前代码已经稳定存在的闭环方向，不提前承诺尚未成为默认主路径的多模态输出策略。当前实现里，QQ 仍然是主出站路径，TTS 属于已接入但非默认的能力面。

主循环每个 tick 的典型职责包括：

1. 采集来自通道和事件源的输入
2. 更新情感系统、异稳态、心境、人格及可选神经化学/意识指标
3. 运行记忆写入、整合和压缩
4. 运行认知评估、驱动推断和内生思维
5. 通过调节层选择行为倾向
6. 经由 `helios_io` 将输出落实为消息、语音或其他外部动作

## 3. 模块分层

### 3.1 仓库根目录

根目录现在只保留两类内容：

- 运行入口与部署资产：`helios_main.py`、`dashboard.py`、`dashboard.html`、service/shell/logrotate 文件
- 情感与生理底盘：`daisy_emotion.py`、`allostasis.py`、`mood_tracker.py`、`personality.py`、`neurochem.py`、`habituation.py`

这里不再承载协议客户端、语音生成器、通道抽象或兼容包装层。

### 3.2 `helios_io/`

`helios_io/` 是所有外部接口的唯一归属层，负责“与世界发生连接”的代码。

关键职责：

- 协议接入：`protocols/qq.py`
- 通道抽象：`channel.py`
- 通道到事件流的桥接：`channel_gateway.py`
- 具体多模态适配：`channels/`
- LLM 相关外部输出：`llm/speech.py`
- 对话历史、被动回复和 SEC 评估：`conversation_history.py`、`response_pipeline.py`、`llm_sec_evaluator.py`
- 行为执行边界：`limb.py`、`limb_decision_bridge.py`

判断规则很简单：如果模块负责接收、发送、适配、路由、编码、协议交互或把内部意图落实为外部动作，它应放在 `helios_io/`。

### 3.3 `core/`

`core/` 现在是轻量的内部运行基础设施层，不再拥有 I/O 实现。

当前边界包括：

- `event_source.py`: 统一事件源抽象
- `helios_state.py`: 运行态容器
- `tick_guard.py`: tick 节奏与保护
- `trigger_merge.py`: 触发合并逻辑
- `separation_source.py`: 分离焦虑事件源
- `drive_source.py`: 内驱事件源

`core/__init__.py` 仍对外重导出部分通道类型，这是兼容性表面，不代表实现所有权。

### 3.4 `memory/`

`memory/` 负责长期与短期记忆系统，包括：

- autobiographical store
- episodic / semantic / working memory surfaces
- seed memory import
- memory compression and consolidation

该层与主循环的关系是：接收经历、保存叙事、提供检索上下文，并参与长期压缩与组织。

### 3.5 `cognition/`

`cognition/` 负责解释、评估和内生思维：

- appraisal
- drives
- phi / consciousness metric
- thinking manager and thinking integration
- cognitive impact profile

它不直接与外部协议打交道，而是处理“系统如何理解当下，以及下一步内部在想什么”。

### 3.6 `regulation/`

`regulation/` 负责将内部状态转化为意图与行为倾向，包括：

- comfort deviation / baseline activation based regulation
- conation and intent formation
- behavior outcome feedback

它处于认知与执行边界之间，是“是否行动、为何行动、行动后如何回馈”的组织层。

## 4. 关键运行接口

### 4.1 入口

- `helios_main.py`: 真实运行主入口
- `dashboard.py`: 面板与可视化运行面

### 4.2 重要对象关系

- `HeliosConfig` 统一承载环境配置
- `Helios` 持有情感底盘、记忆、认知、调节和 I/O 相关组件
- `ChannelGateway` 将多种通道输入整理为内部可处理事件
- `BehaviorExecutor` / `LimbDecisionBridge` 将调节层输出落实为外部执行动作

## 5. 当前架构约束

当前代码库应继续遵守以下约束：

1. 不在根目录新增协议客户端或传输实现。
2. 不在 `core/` 中新增 transport-specific 类型或 gateway owner。
3. 新增协议统一放入 `helios_io/protocols/`。
4. 新增模型驱动的外部生成组件统一放入 `helios_io/llm/`。
5. `memory/`、`cognition/`、`regulation/` 应面向内部能力，不直接承担协议细节。

## 6. 演进建议

后续若继续收口，可优先考虑：

- 将根目录剩余底盘模块进一步收编为明确子包，例如 affect 或 substrate
- 为 `helios_io/` 增加更清晰的 provider/plugin 装配方式
- 保持 `current_structure.md` 作为快速边界索引，而将本文件作为完整结构说明

## 7. 理论到分层映射

当前实现并不是把研究材料散落在注释里独立存在，而是已经形成较稳定的“理论簇 → 代码层”的对应关系：

| 分层 | 代表模块 | 主要理论基础 |
| --- | --- | --- |
| 情感底盘 | `daisy_emotion.py`, `allostasis.py`, `mood_tracker.py`, `personality.py`, `neurochem.py`, `habituation.py` | Panksepp 原始情感系统、Allostasis、ALMA、人格 trait 调制、神经调质背景 |
| 认知层 | `cognition/phi.py`, `cognition/drives.py`, `cognition/appraisal.py`, `cognition/thinking_integration.py` | IIT、GNW、Predictive Processing、FEP、SEC appraisal、DMN |
| 记忆层 | `memory/memory_system.py`, `memory/autobiographical.py`, `memory/memory_compressor.py` | 多存储记忆模型、自传连续性、巩固与压缩 |
| 调节层 | `regulation/regulation.py`, `helios_io/limb.py`, `helios_io/limb_decision_bridge.py` | 情感调节、行为选择、结果反馈学习 |
| I/O 边界 | `helios_io/response_pipeline.py`, `helios_io/llm_sec_evaluator.py`, `helios_io/channel_gateway.py` | 基于 SEC 的交互评估、上下文调制表达、通道路由 |
| 主循环编排 | `helios_main.py` | 将上述理论实现编排成统一 tick 闭环 |

若需要继续追查到模块、类和关键函数级，请转到 `IMPLEMENTATION_REFERENCE.zh-CN.md`；若需要看原始资料和待补清单，请转到 `SOURCE_CATALOG.zh-CN.md`。

## 8. 文档关系

- 本文件说明“现在系统怎么组织”
- `DESIGN_PHILOSOPHY.zh-CN.md` 说明“系统如何运行、为何这样组织，以及关键设计约束”
- `IMPLEMENTATION_REFERENCE.zh-CN.md` 说明“哪些模块实现或参考了哪些理论、论文和测试行为”
- `SOURCE_CATALOG.zh-CN.md` 说明“仓库中有哪些资料、引用条目和待收集项”
- `architecture_overview.html` 提供 HTML 版整体架构图、tick 流程图和关键对象流
- `current_structure.md` 是更短的边界速查表
- `dmn_thinking_model.md` 等文件是理论基础，不是实现边界说明