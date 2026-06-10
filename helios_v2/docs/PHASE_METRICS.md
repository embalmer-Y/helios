# Helios v2 Phase Metrics — P0–P7 退出指标与硬性条件

> 状态：活文档（阶段验收指标）。最近同步：R77。测试基线：834 passed。
> 角色：为 P0–P7 每个阶段定义**可量化的测试/性能指标**与**硬性退出条件**，使阶段达成可证伪、可只读重建。
> 配套文档：
> - `ARCHITECTURE_PHILOSOPHY.zh-CN.md` §11–13 — 终局目标、锁定验收标准、阶段路线图。
> - `PROGRESS_FLOW.zh-CN.md` — 模块进度图与状态小结。
> - `requirements/index.md` — 权威成熟度列。
> - `OWNER_GUIDE.zh-CN.md` — 逐 owner 参考。

---

## 1. 通用指标约定

下列指标适用于所有阶段，每个阶段退出时必须满足：

| 指标 ID | 指标名称 | 定义 | 采集方式 |
| --- | --- | --- | --- |
| G-1 | 测试套件全绿 | `pytest helios_v2/tests/ -x` 零失败、零错误 | CI / 本地 `pytest` |
| G-2 | 网络离线 | 测试与运行时不依赖外部网络（`psutil` 等懒加载除外） | 断网跑全测试 |
| G-3 | Owner 边界无越界 | `test_composition_owner_boundary_guard.py` 全绿 | 测试套件 |
| G-4 | 无 ad-hoc 日志 | `test_no_adhoc_logging_guard.py` 全绿 | 测试套件 |
| G-5 | 文档同步 | `requirements/index.md`、`PROGRESS_FLOW.*`、`OWNER_GUIDE.*`、`ARCHITECTURE_BOUNDARIES.md` 在同一次变更内同步更新 | 人工 review |
| G-6 | 评估层只读 | `17`/`23` 评估 owner 不变更任何运行时状态 | 代码 review + 契约测试 |

---

## 2. P0 — 初步可稳定运行基线

**状态：已达成（R31，393 tests passed）**

### 2.1 测试指标

| 指标 ID | 指标 | 目标值 | 实际值 |
| --- | --- | --- | --- |
| P0-T1 | 测试套件全绿 | ≥ 350 tests passed | 393 ✅ |
| P0-T2 | 认知主链端到端 | `02`→`17` 19 阶段全部执行且不抛异常 | ✅ |
| P0-T3 | 真实 LLM 思考 | `11` internal thought 经 `25` LLM 网关产出真实 completion | ✅ |
| P0-T4 | CLI 往返 | `31` CLI driver 端到端（输入 → 感知 → 认知 → 外化 → 输出）| ✅ |

### 2.2 硬性退出条件

| 条件 ID | 条件 | 状态 |
| --- | --- | --- |
| P0-H1 | 主链 fail-fast 成立：缺失关键依赖时启动阻断 | ✅ |
| P0-H2 | 契约化：每个 owner 有 contract + engine + stage + 测试 | ✅ |
| P0-H3 | 可观测：`21` 输出 per-tick 时间线 | ✅ |
| P0-H4 | 可评估：`17` 产出 consequence-binding 诊断 | ✅ |

---

## 3. P1 — 内部闭环里程碑（= v2.0.0）

**状态：推进中**

### 3.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P1-T1 | 测试套件全绿 | ≥ 500 tests passed | G-1 |
| P1-T2 | wave_A 行为真相 | `17` corroboration 产出 `corroborated`/`discrepant`/`unverifiable` 判定 | `test_evaluation_corroboration.py` |
| P1-T3 | wave_B 长程连续性 | `18`/`24` continuity thread 跨 ≥ 5 tick 存续 | `test_autonomy_continuity_threads.py` |
| P1-T4 | wave_C 本地往返 | CLI channel 端到端 ≥ 3 tick 不中断 | `test_channel_cli_roundtrip.py` |
| P1-T5 | 内部-only tick 闭合 | fired + no-proposal tick 完成全链 | `test_internal_only_tick.py` |
| P1-T6 | no-fire tick 闭合 | gate no-fire tick 完成全链（R54）| `test_gate_no_fire_closure.py` |

### 3.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P1-P1 | 单 tick 延迟（离线，无 LLM） | < 50ms |
| P1-P2 | 单 tick 延迟（含 LLM 思考） | < 5s（受模型延迟约束） |
| P1-P3 | 内存占用（空载运行 100 tick） | < 500MB |

### 3.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P1-H1 | `17`/`23` 能只读重建至少一条内部因果链 | FG-6 |
| P1-H2 | 连续 ≥ 10 tick 运行无异常中断 | FG-1（骨架） |
| P1-H3 | 所有 wave_A/B/C 收口测试全绿 | FG-1/FG-3 |
| P1-H4 | `ARCHITECTURE_PHILOSOPHY` §10 v2.0.0 判定语句满足 | — |

---

## 4. P2 — 持久化记忆与知识基座

**状态：已开篇（R33），核心交付 R33/R34/R42**

### 4.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P2-T1 | 测试套件全绿 | ≥ 600 tests passed | G-1 |
| P2-T2 | 持久化 append | `33` store 在 100 tick 后 `count ≥ 100` | `test_persistence_store.py` |
| P2-T3 | 跨重启连续性 | 进程重启后 `10` 检索到上一 session 的经验 | `test_restart_continuity.py` |
| P2-T4 | 语义召回 | embedding 写入后 `search_similar` 按余弦排序返回 | `test_semantic_retrieval.py` |
| P2-T5 | 检查点/恢复 | `42` checkpoint 保存 → 重启 → `09`/`18` 恢复上次状态 | `test_continuity_checkpoint.py` |
| P2-T6 | 双时标演化 | `04`/`05` 跨 tick carry 状态 ≠ 冷启动基线 | `test_dual_timescale_dynamics.py` |

### 4.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P2-P1 | SQLite append 吞吐 | ≥ 100 records/s |
| P2-P2 | 语义召回延迟（1000 条记录） | < 100ms |
| P2-P3 | 检查点 save/load | < 10ms per tick |
| P2-P4 | embedding 写入吞吐 | ≥ 50 embeds/s（离线 hash provider） |

### 4.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P2-H1 | 进程重启后主观连续性成立（`33` + `42` 端到端） | FG-5.1 |
| P2-H2 | 检索由真实表征驱动（`34` 语义召回，非 recency-only） | FG-1（记忆侧） |
| P2-H3 | 嵌入失败 = hard stop，无静默降级 | FG-6 |
| P2-H4 | `06`/`04`/`05`/`14` 持久化路径明确（已落地或显式延后） | FG-5.1 |

---

## 5. P3 — 去 shim 化感知-情感链

**状态：已退出（R64 PASS，R69 语义装配默认化）**

### 5.1 测试指标

| 指标 ID | 指标 | 目标值 | 实际值 |
| --- | --- | --- | --- |
| P3-T1 | 测试套件全绿 | ≥ 700 tests passed | 775 ✅ |
| P3-T2 | P3 exit evaluation | `test_p3_exit_evaluation.py` 全绿 | ✅ |
| P3-T3 | 03 五维全真实 | 语义装配下 03 每个维度 ≠ 首版常量 | ✅ |
| P3-T4 | 04 双时标演化 | 跨 tick `NeuromodulatorState` ≠ tonic baseline | ✅ |
| P3-T5 | 05 体感演化 | 跨 tick `InteroceptiveFeelingState` ≠ baseline | ✅ |
| P3-T6 | 09 门控无 shim | 所有 gate input 接真实信号（R63 收口）| ✅ |
| P3-T7 | 多候选竞争 | `07` workspace ≥ 2 candidates 竞争 | ✅（R52） |
| P3-T8 | 零感知收口 | `02` 空批次 → `06`/`07`/`08` inactive | ✅（R65） |

### 5.2 性能指标

| 指标 ID | 指标 | 目标值 | 实际值 |
| --- | --- | --- | --- |
| P3-P1 | FG-2 因果链可追踪 | ≥ 2 条端到端可只读重建因果链 | ✅（外部 + 内感受） |
| P3-P2 | 跨 tick 情感差异 | 变化刺激下 03/04/05 状态可测量差异 | ✅ |
| P3-P3 | 默认装配门控可 fire | 默认装配 gate score > 0.55 | ✅（R63） |

### 5.3 硬性退出条件（已满足）

| 条件 ID | 条件 | 对应终局标准 | 状态 |
| --- | --- | --- | --- |
| P3-H1 | FG-1 de-shim 覆盖率：03-10 全消费真实信号 | FG-1 | ✅ R64 PASS |
| P3-H2 | FG-2.1 情感跨 tick 演化成立 | FG-2.1 | ✅ R64 PASS |
| P3-H3 | FG-2.2 因果链端到端可追溯 | FG-2.2 | ✅ R64 PASS |
| P3-H4 | 语义装配为默认（R69），无需 opt-in | — | ✅ |

### 5.4 P3 遗留项（诚实记录，不阻塞退出）

| 遗留项 | 归属阶段 | 说明 |
| --- | --- | --- |
| `06` 去重/合并 | P5 | 挂 `consolidation_policy`，有界、owner-owned |
| `03`/`04`/`05`/`09` 系数学习 | P5 | 有界参数 RL 微调 |
| `13` planner bridge channel 状态 | P4 | 需要工具/效应器生态 |
| 真实外部网络传输 | wave_C | QQ/语音/视觉 driver |

---

## 6. P4 — 工具 / 效应器生态

**状态：未开始**

### 6.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P4-T1 | 测试套件全绿 | ≥ P3 基线 + 新增 tool 测试 | G-1 |
| P4-T2 | 工具注册/发现 | `30` 框架扩展支持 ≥ 1 tool driver 注册 | `test_tool_driver_registration.py` |
| P4-T3 | planner 工具选择 | `13` 能从 ≥ 2 候选 tool 中选择一个并发起调用 | `test_planner_tool_selection.py` |
| P4-T4 | 工具结果回流 | 工具执行结果作为 `RawSignal` 经 `02` 回流 | `test_tool_result_sensory_feedback.py` |
| P4-T5 | 工具失败收口 | 工具不可用/失败/拒绝 → 正式结果写回，非静默 | `test_tool_failure_handling.py` |
| P4-T6 | 端到端工具链 | 思考 → planner → tool → 结果回流 → 再思考 | `test_tool_end_to_end.py` |

### 6.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P4-P1 | 工具调用延迟开销 | < 500ms（不含工具本身执行时间） |
| P4-P2 | tool driver 注册/注销 | < 10ms |
| P4-P3 | 工具结果回流 sensory | 同一 tick 内完成 |

### 6.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P4-H1 | ≥ 1 条端到端工具链可只读重建 | FG-4.3 |
| P4-H2 | tool 是受治理的 driver（`30` 框架谱系），非 owner 旁路 | FG-4.1 |
| P4-H3 | 工具失败/拒绝/不可用全以正式结果写回 | FG-4.4 |
| P4-H4 | planner 能选择、绑定并发起 ≥ 1 种工具调用 | FG-4.2 |
| P4-H5 | `13` channel 状态去 shim（来自真实 tool driver 状态） | FG-4 |

---

## 7. P5 — 学习循环（自训练第一步）

**状态：未开始**

### 7.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P5-T1 | 测试套件全绿 | ≥ P4 基线 + 新增学习测试 | G-1 |
| P5-T2 | 奖励预测误差信号 | `04` 多巴胺通道产出 RPE 信号（真实后果 - 预期） | `test_reward_prediction_error.py` |
| P5-T3 | 参数更新 | ≥ 1 个有界参数（`04`/`05`/`09` coupling/gain）被真实经验更新 | `test_parameter_learning.py` |
| P5-T4 | 行为改变 | 参数更新后，同输入产出可测量不同结果 | `test_learning_behavior_change.py` |
| P5-T5 | 离线巩固 | replay 驱动离线巩固改变记忆表征 | `test_offline_consolidation.py` |
| P5-T6 | 去重/合并 | `06` 相同记忆条目去重、相似记忆合并 | `test_memory_dedup_merge.py` |

### 7.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P5-P1 | 参数更新延迟 | < 1ms per update |
| P5-P2 | 离线巩固吞吐 | ≥ 10 records/s（replay + 再 embed） |
| P5-P3 | 学习后行为差异 | 同输入、不同经验后 gate score 差异 > 0.01 |
| P5-P4 | 参数边界安全 | 所有更新后参数仍在 `[legal_min, legal_max]` 内 |

### 7.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P5-H1 | ≥ 1 种真实学习成立：经验改变参数 → 可观测行为改变 | FG-5.2 |
| P5-H2 | 学习过程不违反 owner 边界（参数归 owner 所有） | G-3 |
| P5-H3 | 参数更新有界、单调性约束可验证、不发散 | FG-6 |
| P5-H4 | 离线巩固不替换在线认知（replay 是 additive） | FG-5.2 |
| P5-H5 | 奖励信号锚定真实后果（非人工硬编码分数） | §14.6 |

---

## 8. P6 — 受治理的自我修订

**状态：未开始**

### 8.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P6-T1 | 测试套件全绿 | ≥ P5 基线 + 新增治理测试 | G-1 |
| P6-T2 | 修订提案生成 | `14` 能产出 ≥ 1 个自我修订提案 | `test_revision_proposal.py` |
| P6-T3 | 治理审核通过 | 提案经 `14` 治理校验后产出 `accepted`/`rejected` | `test_governance_review.py` |
| P6-T4 | 修订生效 | `accepted` 提案作为正式状态生效 | `test_revision_application.py` |
| P6-T5 | 可审计 | 修订全过程经 `21` 可观测留痕 | `test_revision_audit_trail.py` |
| P6-T6 | 可回滚 | 生效的修订可被回滚到上一状态 | `test_revision_rollback.py` |
| P6-T7 | 评估不退化 | 修订后 `17`/`23` 不暴露因果链退化 | `test_post_revision_evaluation.py` |

### 8.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P6-P1 | 修订提案延迟 | < 1s（含 LLM 生成） |
| P6-P2 | 治理审核延迟 | < 100ms |
| P6-P3 | 回滚延迟 | < 10ms |
| P6-P4 | 审计日志完整性 | 100% 修订事件留痕 |

### 8.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P6-H1 | 自我修订作为正式状态生效，非 prompt 表演 | FG-5.3 |
| P6-H2 | 全部修订经治理（`14`）+ 可审计 + 可回滚 | FG-5.3 |
| P6-H3 | 修订不绕过 owner 边界或契约纪律 | G-3 |
| P6-H4 | 修订后评估层不暴露因果链退化 | FG-6 |
| P6-H5 | 治理拒绝的修订不生效，不静默应用 | FG-5.3 |

---

## 9. P7 — 受治理的代码自修改（终极自我开发）

**状态：未开始**

### 9.1 测试指标

| 指标 ID | 指标 | 目标值 | 验证方式 |
| --- | --- | --- | --- |
| P7-T1 | 测试套件全绿 | ≥ P6 基线 + 新增代码修改测试 | G-1 |
| P7-T2 | 代码变更提案 | 系统能对自身 owner 代码产出 diff 提案 | `test_code_proposal.py` |
| P7-T3 | 测试验证 | 提案触发全测试套件运行，全绿才允许继续 | `test_code_proposal_test_gate.py` |
| P7-T4 | 评估验证 | `17`/`23` 对提案后代码不暴露因果链退化 | `test_code_proposal_evaluation_gate.py` |
| P7-T5 | 治理通过 | 提案经 `14` 治理审核通过 | `test_code_proposal_governance.py` |
| P7-T6 | 合并受控 | 仅在适应度门全绿 + 治理通过时合并 | `test_code_proposal_merge_gate.py` |
| P7-T7 | 全过程留痕 | `21` 记录提案 → 测试 → 评估 → 治理 → 合并全链 | `test_code_proposal_audit.py` |
| P7-T8 | 可回滚 | 合并的代码修改可回滚到上一版本 | `test_code_proposal_rollback.py` |

### 9.2 性能指标

| 指标 ID | 指标 | 目标值 |
| --- | --- | --- |
| P7-P1 | 提案生成延迟 | < 5s（含 LLM 生成 diff） |
| P7-P2 | 测试验证延迟 | < 60s（全套件） |
| P7-P3 | 合并延迟 | < 1s |
| P7-P4 | 回滚延迟 | < 5s |

### 9.3 硬性退出条件

| 条件 ID | 条件 | 对应终局标准 |
| --- | --- | --- |
| P7-H1 | 代码修改仅在适应度门（测试 + 评估 + 治理）全绿时合并 | FG-5.4 |
| P7-H2 | 代码修改不绕过 owner 边界、契约或 fail-fast | FG-5.4, FG-6 |
| P7-H3 | 全过程经 `21` 可观测留痕 | FG-6 |
| P7-H4 | 合并的修改可回滚 | FG-5.4 |
| P7-H5 | 系统不能修改自身的治理门或安全门 | §12.7 |
| P7-H6 | 终局验收标准 `FG-1` 到 `FG-6` 全部可证伪成立 | §12.7 |

---

## 10. 阶段间依赖矩阵

```
P0 (已达成) → P1 (推进中) → P2 (已开篇) → P3 (已退出) → P4 → P5 → P6 → P7
```

| 阶段 | 前置阶段 | 关键依赖 |
| --- | --- | --- |
| P0 | — | — |
| P1 | P0 | wave_A/B/C 收口 |
| P2 | P1 | 持久化基座 |
| P3 | P2 | 语义记忆 + embedding |
| P4 | P3 | 去 shim 后的认知链 |
| P5 | P2 + P3 | 持久化 + 真实信号 |
| P6 | P1 + P2 + P5 | 可证伪评估 + 持久化 + 学习基础 |
| P7 | P6 | 治理闭环成立 |

---

## 11. 当前状态快照（R77）

| 阶段 | 状态 | 测试基线 | 关键里程碑 |
| --- | --- | --- | --- |
| P0 | ✅ 已达成 | 393 → 834 | R31 |
| P1 | 🔄 推进中 | 775 → 834 | R71 性能基准、R72 P1 退出评估、R74 审计、R75 反馈路径 |
| P2 | 🔄 核心交付 | 775 → 834 | R73 P2 退出评估、R76 记忆稳定性、R77 长期稳定前置 |
| P3 | ✅ 已退出 | 746 → 834 | R64 PASS, R69 默认化 |
| P4 | ⬜ 未开始 | — | — |
| P5 | ⬜ 未开始 | — | — |
| P6 | ⬜ 未开始 | — | — |
| P7 | ⬜ 未开始 | — | — |

### 11.1 终局验收标准进度

| 标准 | 状态 | 最近推进 |
| --- | --- | --- |
| FG-1 类脑闭环真实信号 | ✅ P3 退出成立 | R64/R69 |
| FG-2 情感可追溯 | ✅ FG-2.1 + FG-2.2 成立 | R64 |
| FG-3 自我意识可重建 | 🔄 部分（`18` 连续性 + `14` carry） | R67/R68 |
| FG-4 工具闭环 | ⬜ 未开始 | — |
| FG-5 自训练/自进化 | 🔄 FG-5.1 成立（持久化）；FG-5.2–5.4 未开始 | R33/R34/R42 |
| FG-6 全局可证伪 | 🔄 P3 范围内的可证伪成立；P4–P7 待推进 | R64 |

---

## 12. 更新约束

本文件必须在以下情况发生时、于**同一次变更**内同步更新：

1. 某阶段的退出信号状态发生变化；
2. 新增或修改了某阶段的测试/性能指标；
3. 终局验收标准（FG-1 到 FG-6）的达成状态发生变化。

顶部"最近同步"行必须写明最后改动本文件的 requirement。
