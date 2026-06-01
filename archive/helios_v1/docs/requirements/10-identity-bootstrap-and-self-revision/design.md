# Requirement 10 - Identity Bootstrap and Self-Revision

## 1. Design Overview

本设计引入正式的 identity governance owner，将“我是誰”“我具有什么人格基线”“我如何修订自己”从分散配置与 prompt 文本中抽离出来，变成可治理、可审计的系统级结构。

## 2. Current State and Gap

当前 gap：

1. `personality.py` 只拥有 trait 状态，不拥有完整 identity boundary。
2. `personality_contract.py` 只负责描述，不负责治理。
3. seed memory importer 只导入叙事，不负责首启 identity bootstrap。
4. 当前没有 revision record 或 identity version history。
5. 当前 bootstrap 内容仍主要来自代码常量与分散 JSON/seed 数据，缺少正式的 bootstrap definition owner 与 schema。

## 3. Target Architecture

目标结构：

1. 新增 `IdentityStore` 概念，独立于普通配置。
2. 首启时加载 bootstrap definition 并写入 `IdentityStore`。
3. 后续启动只读取 `IdentityStore`，不再读取 bootstrap config 进行覆盖。
4. thought result 如提出 self-revision，则进入 `IdentityGovernance`。
5. `IdentityGovernance` 验证后写入新 version，并生成 revision record。
6. bootstrap definition 由正式 owner 提供，拥有 schema 校验、版本号和 seed-memory mapping。

## 4. Data Structures

### 4.1 IdentityStore

```text
initialized
bootstrap_version
self_imprint
self_definition
personality_baseline
identity_metadata
current_revision
```

### 4.2 BootstrapDefinition

```text
bootstrap_version
self_imprint
self_definition
identity_narrative
personality_baseline
identity_seed_memories
metadata
```

### 4.3 SelfRevisionProposal

```text
origin_thought_id
revision_type
requested_change
reason_trace
confidence
scope
```

### 4.4 IdentityRevisionRecord

```text
revision_id
origin_thought_id
requested_change
applied_change
reason_trace
created_at_ts
applied_by
result
```

## 5. Module Changes

1. `personality.py`
   - 保留 trait state，但与 identity store 对接。
2. `personality_contract.py`
   - 改为从 identity store + trait state 构建 prompt identity contract。
3. `memory/seed_memory_importer.py`
   - 扩展为 bootstrap identity seed owner 或配合新 owner。
   - 支持结构化 `identity_seed_memories` 条目，并在导入时保留 source / original_section 等 trace 字段。
4. `helios_main.py`
   - 启动时只在未初始化情况下执行 bootstrap。
   - 将 bootstrap seed import trace 写入 `identity_store.identity_metadata`，避免 trace 只留在一次性启动流程。
5. `cognition/thinking_integration.py`
   - 允许产出 self-revision proposal。
6. 新增 identity governance owner 模块（建议）。
7. 新增 bootstrap definition loader / validator（建议）。

## 6. Migration Plan

1. 先定义 identity store 和 revision record。
2. 再从现有 personality seed/contract 中提取 bootstrap 信息。
3. 再实现 post-bootstrap lock。
4. 最后接通 self-revision proposal。
5. 最后移除或冻结旧的分散默认常量来源，避免双写。

## 7. Failure Modes and Constraints

1. 若 identity store 初始化失败，系统不得静默重新跑 bootstrap 覆盖现有状态。
2. 若 self-revision proposal 非法，必须拒绝并记录。
3. 若 revision 触及最低层自我烙印，默认拒绝，除非后续 requirement 放开。
4. 若 bootstrap definition 缺失字段或 schema 非法，系统必须拒绝初始化并输出明确错误。

## 8. Observability and Logging

必须记录：

1. identity bootstrap started / completed / skipped
2. identity store initialized status
3. self-revision proposal created / accepted / rejected
4. revision history write result
5. bootstrap definition version / source / validation result
6. bootstrap seed import fingerprint / entry_count / imported_count / entries summary

## 9. Validation Strategy

1. 单元测试验证 bootstrap 幂等性。
2. 单元测试验证 post-bootstrap lock。
3. 单元测试验证 self-revision proposal 的治理与审计。
4. 集成测试验证重启后不再读取 bootstrap config 覆盖 identity。
5. 单元测试验证 bootstrap definition schema 校验与 seed-memory 映射。
6. 集成测试验证 bootstrap seed import trace 持久化到 identity store。
