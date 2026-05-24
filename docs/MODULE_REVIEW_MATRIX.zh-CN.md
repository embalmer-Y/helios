# Helios 模块审查矩阵

> Status: Draft for confirmation
> Role: 在代码实施前，逐层确认哪些模块保留现有实现、哪些只保留实现但重定哲学、哪些需要接口调整、哪些应重构
> Interpretation: 本矩阵优先服务于新的类脑意识优先架构，不以旧文档边界为准

## 1. 审查分类说明

- `保留`：当前实现与新设计哲学基本一致，可继续沿用。
- `保留实现，重定哲学`：实现可暂留，但文档定位、调用方式或所有权解释必须改变。
- `调整接口`：核心能力可保留，但输入输出契约、数据流或边界需要重构。
- `重构/重建`：当前实现与新设计哲学冲突较大，应作为重点改造对象。

## 2. Root Runtime / Substrate

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `helios_main.py` | 主循环编排、状态聚合、被动回复与主动行为分叉、思考与执行桥接 | 重构/重建 | 当前仍以“被动回复链路 + 内部思考链路”双轨运行，不符合“LLM 属于内部意识循环”的总原则。应改为单一 thought-centered orchestration。 |
| `allostasis.py` | 异稳态、负载、疲劳与恢复 | 保留 | 作为类脑底盘的一部分，与新哲学一致。仅需在 HLD 中重新挂接到连续思考压力和恢复机制。 |
| `daisy_emotion.py` | Panksepp 情感系统驱动 | 保留 | 可继续作为底层情感底盘使用。 |
| `mood_tracker.py` | 心境状态聚合 | 保留 | 与新哲学不冲突。 |
| `habituation.py` | 刺激重复下的习惯化与新异性衰减 | 保留实现，重定哲学 | 可直接纳入“刺激权重与思考门控”框架，但不应只作为情感前处理，而应影响思考触发。 |
| `neurochem.py` | 神经化学状态与推进 | 调整接口 | 应从“辅助状态”升级为思考延续压力与行动强度协同层。 |
| `neurochem_gate.py` | 神经化学门控摘要 | 调整接口 | 需要接入 thought continuation pressure 与 outward intensity。 |
| `temporal_gate.py` | 时间动力学门控摘要 | 调整接口 | 需要服务“连续思考是否继续”和“何时外化行动”。 |
| `personality.py` | trait 状态、适配和持久化 | 调整接口 | 需保留 trait 演化能力，但增加首启注入、用户锁定、内部自我修订治理。 |
| `personality_projection.py` | 人格偏置投影 | 调整接口 | 仍可作为慢变量投影层，但要从“表达风格偏置”扩展为思考偏向和行动偏向先验。 |
| `personality_contract.py` | prompt/persona 统一描述 | 调整接口 | 需要被更严格地约束，不得向模型暴露“被设计程序”的叙述。 |
| `dashboard.py` / `dashboard.html` | 状态展示面板 | 保留实现，重定哲学 | 可以保留，但展示指标应围绕意识流、思考压力、记忆层和自我修订日志重新组织。 |
| `README.md` | 项目入口说明 | 重写 | 是否最终保留待定；若保留，必须严格从新哲学出发。 |

## 3. Core Infrastructure

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `core/helios_state.py` | tick 状态快照 | 调整接口 | 需要正式承载 stimulus provenance、stimulus intensity、thought pressure、continuation pressure、memory recall intent、outbound intensity。 |
| `core/event_source.py` | 事件源抽象 | 保留 | 抽象仍成立。 |
| `core/separation_source.py` | 分离焦虑事件源 | 保留实现，重定哲学 | 保留为内部刺激源，但不应天然直通外部表达，应先进入 thought loop。 |
| `core/drive_source.py` | 内驱映射为触发信号 | 保留实现，重定哲学 | 需要纳入统一刺激权重与思考门控。 |
| `core/temporal_dynamics.py` | 时间慢变量与节律 | 调整接口 | 要成为 thought continuation 和 memory consolidation 的共同时间底盘。 |
| `core/tick_guard.py` | tick 保护与安全模式 | 保留 | 无冲突。 |
| `core/trigger_merge.py` | 触发合并 | 调整接口 | 合并逻辑应能处理来源、强度、类别，而不仅是简单 trigger vector。 |

## 4. Cognition / Consciousness Loop

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `cognition/thinking_integration.py` | 内生思考触发与 LLM thought 生成 | 重构/重建 | 这是新的第一核心 owner 之一，需要从“内部 thought 支路”升级为主意识流 owner。 |
| `cognition/thinking.py` | 思考管理与 fallback | 调整接口 | 保留 thought type / mode 概念，但要围绕多 tick 连续思考和 recall intent 重构。 |
| `cognition/preconscious.py` | thought -> internal proposal | 重构/重建 | 当前 `internal_only` 约束与新需求直接冲突，应改为 thought-to-action 的受控 op bridge。 |
| `cognition/phi.py` | consciousness / ICRI 聚合 | 调整接口 | 保留为意识强度度量，但要更紧密地参与 thought trigger、continuation 和记忆定向检索。 |
| `cognition/appraisal.py` | appraisal 逻辑 | 保留实现，重定哲学 | 应更多地作为思考前的意义评估，而不是外部回复 gating 的配角。 |
| `cognition/drives.py` | 驱动估计 | 保留 | 驱动仍是 thought pressure 的重要输入。 |
| `cognition/cognitive_impact.py` | 输入认知影响模型 | 调整接口 | 应并入正式 stimulus contract。 |
| `cognition/__init__.py` | 导出边界 | 调整接口 | 配合模块所有权更新。 |

## 5. Memory / Retrieval

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `memory/memory_system.py` | working/episodic/semantic/autobio 管理与检索 | 重构/重建 | 新哲学要求正式对外定义为短期/中期/长期/自传，并引入思考前 directed retrieval。 |
| `memory/retrieval.py` | 统一检索契约 | 调整接口 | 应新增 stimulus-driven recall 与 prior-thought recall intent 两路入口，并允许 retrieval SEC。 |
| `memory/autobiographical.py` | 自传叙事存储 | 保留 | 可作为自传层 owner。 |
| `memory/emotional_memory.py` | 情绪相关记忆表示 | 调整接口 | 视后续 requirement 决定是合并、保留还是弱化。 |
| `memory/memory_compressor.py` | 压缩与汇总 | 保留实现，重定哲学 | 压缩规则要服从新的记忆层次和意识流价值判断。 |
| `memory/seed_memory_importer.py` | 种子记忆导入 | 调整接口 | 应扩展为首启身份/自我定义 bootstrap 的一部分，而不是仅导入叙事片段。 |
| `memory/backend.py` / `memory/sqlite_backend.py` | 后端抽象与 SQLite 存储 | 保留 | 可以作为新记忆分层的实现承载层。 |

## 6. Identity / Governance

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `personality.py` | trait 持久化与演化 | 调整接口 | 需进入正式身份治理体系。 |
| `personality_contract.py` | 统一人格提示描述 | 调整接口 | 需同时承载“自我烙印”与语言边界约束。 |
| `data/personality.json` 等现有持久化表面 | 当前状态落盘 | 重构/重建 | 需要从普通配置持久化升级为 bootstrap-only identity store + revision history。 |

## 7. Helios I/O / Channels / Ops

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `helios_io/action_models.py` | proposal / decision schema | 调整接口 | 应扩展 stimulus intensity、outbound intensity、source provenance、selected op payload。 |
| `helios_io/planning.py` | proposal 校验、决策与 planner | 调整接口 | 保留 planner/policy owner 地位，但要支持 LLM 提议 op+params 后的安全校验和通道绑定。 |
| `helios_io/limb.py` | 执行器 | 调整接口 | 应支持统一 op 执行语义和强度控制。 |
| `helios_io/limb_decision_bridge.py` | decision -> executor bridge | 保留实现，重定哲学 | 可保留为桥接层，但输入语义会变化。 |
| `helios_io/channel.py` | channel/message/op 抽象 | 重构/重建 | 需要正式定义输入来源、触发条件、输入刺激强度、输出表达强度、op schema。 |
| `helios_io/channel_gateway.py` | 通道路由与桥接 | 调整接口 | 应传播来源和强度，而不只是 message/text。 |
| `helios_io/protocols/` | 协议接入 | 保留 | 协议层仍保留。 |
| `helios_io/channels/qq_channel.py` | QQ 输入输出适配 | 调整接口 | 需提供更丰富的输入来源语义和输出 op 控制信息。 |
| `helios_io/channels/stt_channel.py` | 语音输入适配 | 调整接口 | 需明确刺激来源与触发条件。 |
| `helios_io/channels/tts_channel.py` | 语音输出适配 | 调整接口 | 需支持输出强度和控制参数。 |
| `helios_io/channels/vision_channel.py` | 视觉输入适配 | 调整接口 | 需进入统一 stimulus contract。 |
| `helios_io/interaction_policy.py` | 交互策略 | 重构/重建 | 不再以“是否回复”为中心，而应改成“外部刺激是否值得进入思考 / 行动外化候选”。 |
| `helios_io/response_pipeline.py` | 被动回复生成 | 重构/重建 | 当前 reply-first 角色与新哲学直接冲突，预计会被吸收、降级或删除。 |
| `helios_io/reply_prompt_builder.py` | 回复 prompt 构建 | 重构/重建 | 需要改写为 thought/action planning prompt contract 的一部分。 |
| `helios_io/llm_sec_evaluator.py` | LLM SEC | 调整接口 | 应从“是否回复”服务转向 stimulus appraisal 与 directed retrieval SEC。 |
| `helios_io/llm/speech.py` | LLM speech generation | 重构/重建 | 若保留，也应成为 thought externalization 的结果层，而不是主路径 owner。 |
| `helios_io/conversation_history.py` | 对话历史 | 调整接口 | 需并入短期记忆或输入回显层，而不是单独主导回复上下文。 |
| `helios_io/icri_temperature.py` | ICRI -> temperature/style | 保留实现，重定哲学 | 可继续使用，但作用目标应从“reply style”改为“thought / action externalization style”。 |
| `helios_io/routing_policy.py` | 通道偏好排序 | 保留实现，重定哲学 | 仍可保留，但需要纳入输出强度、行动类型和 op 约束。 |
| `helios_io/feedback_recorder.py` | 反馈与审计记录 | 保留 | 是后续 identity revision audit 和 action audit 的关键基础设施。 |

## 8. Regulation / Behavior Registry

| 模块 | 当前职责 | 建议 | 说明 |
| --- | --- | --- | --- |
| `regulation/regulation.py` | 主动调节与行为候选 | 调整接口 | 仍可保留为 internal pressure / action tendency owner，但要从与 reply path 并列改为服务 thought-centered loop。 |
| `regulation/policy.py` | regulation policy | 保留实现，重定哲学 | 仍有价值，但得让位于统一 thought/action architecture。 |
| `regulation/conation.py` | 意动与行为趋向 | 保留 | 符合新哲学。 |
| `regulation/constants.py` | 常量 | 调整接口 | 需要随新指标体系更新。 |
| `behavior_registry/runtime_catalog.py` | 运行时行为目录 | 保留 | 可以扩展为 LLM 可提议 op 的合法能力目录。 |
| `behavior_registry/sqlite_registry.py` | 行为注册表 SQLite | 保留 | 是受控动作能力治理的关键基础设施。 |
| `behavior_registry/records.py` | 记录模型 | 保留 | 可继续服务治理与审计。 |

## 9. Tests / Scripts / Data

| 区域 | 建议 | 说明 |
| --- | --- | --- |
| `tests/` | 调整接口 | 需要重写大量行为预期，但测试层必须保留并迁移到新哲学。 |
| `scripts/` | 调整接口 | 初始化脚本需扩展到 identity bootstrap 和新 memory/model governance。 |
| `data/` | 调整接口 | 需要区分运行数据、bootstrap 身份数据、审计历史和记忆后端。 |
| `.env.example` | 重写 | 配置项应反映新架构，尤其是首启身份注入与 LLM thought loop 配置。 |

## 10. 第一轮建议确认顺序

建议按以下分组与你逐轮确认：

1. Root Runtime / Substrate
2. Cognition / Consciousness Loop
3. Memory / Retrieval
4. Identity / Governance
5. Helios I/O / Channels / Ops
6. Regulation / Behavior Registry
7. Tests / Scripts / Data

每一轮确认输出三类结果：

- 保留原哲学
- 保留实现但调整哲学/接口
- 明确进入重构

## 11. 已确认结果

### 11.1 Root Runtime / Substrate

该分组已于 2026-05-24 完成第一轮确认，确认结论如下：

1. `helios_main.py`: 重构/重建
2. `allostasis.py`: 保留
3. `daisy_emotion.py`: 保留
4. `mood_tracker.py`: 保留
5. `habituation.py`: 保留实现，重定哲学
6. `neurochem.py`: 调整接口
7. `neurochem_gate.py`: 调整接口
8. `temporal_gate.py`: 调整接口
9. `personality.py`: 调整接口
10. `personality_projection.py`: 调整接口
11. `personality_contract.py`: 调整接口
12. `dashboard.py` / `dashboard.html`: 保留实现，重定哲学
13. `README.md`: 重写或最终删除待定

### 11.2 全局兼容性决策

该重构批次已明确不要求保留旧接口、旧 wrapper 或旧路径兼容层。

执行约束如下：

1. 与新哲学冲突的旧接口可以直接删除。
2. compatibility 不是默认 requirement。
3. 任何暂时保留的旧边界都只允许作为短期迁移措施，不得继续扩展。

### 11.3 Cognition / Consciousness Loop

该分组已于 2026-05-24 完成第一轮确认，确认结论如下：

1. `cognition/thinking_integration.py`: 重构/重建
2. `cognition/thinking.py`: 调整接口
3. `cognition/preconscious.py`: 重构/重建
4. `cognition/phi.py`: 调整接口
5. `cognition/appraisal.py`: 保留实现，重定哲学
6. `cognition/drives.py`: 保留
7. `cognition/cognitive_impact.py`: 调整接口
8. `cognition/__init__.py`: 调整接口
