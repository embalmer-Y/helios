# Requirement 18 - Subjective autonomy and proactive evolution

## 1. Task Breakdown

## 1.1 Boundary Baseline

1. R18 的 owner、允许依赖、禁止 shortcut 和迁移态解释以 [ARCHITECTURE_BOUNDARIES.zh-CN.md](../../ARCHITECTURE_BOUNDARIES.zh-CN.md) 与 [MODULE_REVIEW_MATRIX.zh-CN.md](../../MODULE_REVIEW_MATRIX.zh-CN.md) 为共同基线。
2. R18 task 只负责任何 proactive slice 如何落到既有 owner 边界上，不单独改写边界归属。

## 1.2 Progress Snapshot

1. 已完成：第一实现切片已落地 `proactive` state/export 与未外化原因链，当前 runtime 已能导出 regulation active path 的 evaluation、accept/reject 与 suppression 原因。
2. 当前约束：R19 已明确 `helios_main.py` 仍带被动响应迁移态，因此 R18 不能从 channel 或 prompt 层绕过主路径伪造主动性。
3. 已完成：personality projection、temporal gate 和 neurochem gate 的现有 bias 已正式汇总到 `proactive drive`/`dominant disposition`，且 runtime 已区分 `reactive` / `proactive` / `mixed` thought session。
4. 下一切片：把主动候选的 deferred trace 继续接入真正会改变后续判断的治理决策面，而不是只停留在 identity 慢变量摘要层。

### Task 1 - 建立 proactive drive 数据出口

1. 在 regulation 层聚合 drives、情绪张力、未完成意图和节律信号。
2. 将 proactive drive 以正式 snapshot 暴露给主循环。
3. 在 state/log 中提供最小可观测字段。
4. 首个验证：运行相关 regulation 单测或新增窄范围测试。
5. 当前状态：基础切片已完成，当前已具备 `proactive` state/export、accept/reject 和未外化原因链。
6. 下一切片要求：把 drive sources、dominant disposition 和四类压力分量纳入同一 export，而不直接放大主动外发频率。

### Task 2 - 接入主动 thought session

1. 修改主循环 idle-path，使其消费 proactive drive。
2. 在 thinking integration 中支持 proactive thought session。
3. 保持与现有 reactive path 并存，但 provenance 明确分离。
4. 为 continuity carry 或等价延续状态提供最小 owner 出口，避免主动 thought 只出现一次性脉冲。
5. 首个验证：运行触发 proactive thought 的窄范围测试。
6. 当前状态：最小 proactive thought session 已落地，`thought_gate` / `thought_cycle` / `internal_thought` / `proactive.counters` 已能区分 `reactive` / `proactive` / `mixed`。

### Task 3 - 打通 proactive planner/policy/outbound

1. 为 planning 和 policy 增加 proactive provenance 语义。
2. 使 channel gateway 执行路径可携带 proactive 标记。
3. 实现 policy 拒绝时的内部降级沉淀。
4. 记录主动外化未发生的原因，并把 deferred intent 或内部 trace 作为正式降级结果。
5. 首个验证：运行涉及 tick、planning、channel 的集成测试。
6. 已完成：`thought_action_bridge` proposal 已携带 `session_kind` / `dominant_disposition` / `trigger_sources`，planner `policy_trace`、proposal snapshot、outbound metadata 和 feedback trace 已能保留这组 proactive provenance。
7. 已完成：`thought_action_bridge` 的 policy 拒绝现在会把同一套 provenance 写回 `internal_thought` / `thought_cycle` 的 deferred trace，不再只停留在 feedback journal。
8. 已完成：`regulation` active proposal owner 现在也会产出统一的 `session_kind` / `dominant_disposition` / `trigger_sources`，并且 regulation path 的 policy rejection feedback 已保留同口径 proactive provenance。
9. 已完成：evaluation 现在会直接消费 `thought_cycle` / `internal_thought` / `proactive` 中的 proactive/deferred 语义，能导出 `proactive_thought_samples`、`deferred_trace_samples`、`deferred_regulation_samples`，并汇总 dominant disposition、trigger sources 和 deferred reasons。
10. 已完成：`thought_action_bridge` 与 `regulation` 的 deferred proactive rejection 现在会写入正式 `autobiographical` trace，并通过 `memory_write` journal 持久化同口径 provenance；`MemorySystem` 也已接上 live `autobiographical_store`，使这些 trace 能被后续 autobio retrieval 消费。
11. 已完成：deferred proactive trace 现在也会写入 `identity_store.identity_metadata` 的正式慢变量摘要与有界 history，并通过 `get_state()["identity"]` 暴露 `proactive_deferred_trace_count` 与 `latest_proactive_deferred_trace`，同时持久化到 `identity_store.json`。
12. 已完成：`identity_governance` 现在会基于 `proactive_deferred_trace_summary/history` 派生正式 `proactive_governance_signal`，并在高压场景下对低置信 `self_definition_revision` / `personality_adjustment` 施加治理 backpressure；`get_state()["identity"]` 与 `identity_store.json` 也会同步暴露该信号，确保 deferred proactive trace 不再只是被记录，而会改变后续治理判断。

### Task 4 - 写入自我演化轨迹并接入评估

1. 将主动 thought / action outcome 写入 memory 或治理 trace。
2. 为 evaluation 提供主动性指标出口。
3. 增加回归测试，防止主动链路再次被静默压制。
4. 首个验证：运行主动性相关测试与短时 live smoke。
5. 当前状态：evaluation 读取切片已完成，report 可直接汇总 proactive/deferred trace，不再只依赖 log 中的 rejection 字符串猜测主动性链路。
6. 当前状态：跨 tick memory 消费切片已完成，deferred proactive trace 已写入 `autobiographical` store，并可被后续 autobio retrieval 读取。
7. 当前状态：identity/governance 慢变量摘要切片已完成，deferred proactive trace 已进入 `identity_metadata` 的正式 summary/history，并能跨重启保留。
8. 当前状态：治理决策消费切片已完成，重复 deferred proactive trace 会派生 `proactive_governance_signal` 并对后续低置信 identity revision 形成正式 backpressure。
9. 当前状态：已完成两轮 R18 定向 evaluation/live smoke 校准；`proactive_governance_signal` 现改为基于 bounded recent history 与 recent density，而非 lifetime cumulative total，阈值实测曲线更新为 `1-2=none / 3-4=monitor / 5+ 且近期密集摩擦 => stabilize`，evaluation report 也会显式汇总 governance pressure level / review hint。现有仓库 `run_live_smoke.ps1` 仍有一项与 R18 无关的旧失败：`tests/test_response_pipeline.py::TestGenerateReply::test_personality_description_defaults_when_no_traits`。
10. 当前状态：在 2026-05-30 之后，旧 runtime/live log 已不再作为 R18 校准证据池，因为框架 owner/boundary 与链路语义已发生多轮重大改动；后续阈值细调只接受当前框架版本下的新 artifact，并要求真实命中连续 `proactive_deferred_trace` 或 thought-action/regulation rejection，且 governance signal 至少进入 `monitor`。

## 2. Dependencies

1. 依赖 R07、R08、R09、R11、R15 的基础 thought / action / retrieval 语义。
2. 依赖 R16 已提供的 channel gateway op 边界。
3. 依赖 R19 提供的 owner/boundary 文档基线，避免 R18 在实现前重新发明局部边界语义。
4. 建议与 R17 并行推进，以便主动性缺口可以被真实评估暴露。

## 3. Files and Modules

1. `helios_main.py`
2. `core/helios_state.py`
3. `regulation/regulation.py`
4. `regulation/conation.py`
5. `personality_projection.py`
6. `neurochem_gate.py`
7. `temporal_gate.py`
8. `cognition/thinking_integration.py`
9. `cognition/thinking.py`
10. `helios_io/planning.py`
11. `helios_io/interaction_policy.py`
12. `helios_io/limb.py`
13. `helios_io/channel_gateway.py`
14. `memory/memory_system.py`
15. `tests/test_tick_response_wiring.py`

## 4. Implementation Order

1. 先做 proactive drive 与 state observability。
2. 再做 personality / temporal / neurochem -> disposition 汇总。
3. 然后接 proactive thought session。
4. 再打通 planner/policy/outbound。
5. 最后接自我演化 trace 与 evaluation 指标。

## 5. Validation Plan

1. `pytest tests/test_tick_response_wiring.py -q`
2. 对受影响的 regulation / planning / channel 测试做窄范围回归。
3. 若新增主动性状态导出，再运行对应状态快照测试。
4. 以短时 live smoke 验证无输入窗口下的 proactive signal。
5. 对 continuity carry 或 deferred intent 做至少一组跨 tick 验证。
6. 若目标是继续细调 R18 governance 阈值，live artifact 必须先满足准入条件：`deferred_trace_samples > 0` 或存在真实 thought-action/regulation rejection，且 `governance_signal_monitor_samples > 0`；否则该 artifact 只用于其他链路诊断，不进入阈值校准结论。

## 5.1 Next Slice

1. 为 R18 增加定向 live/evaluation 场景或 harness 变体，优先稳定触发 thought-origin / regulation-origin deferred trace 与治理 `monitor` 命中，而不是继续依赖通用长对话 artifact 间接猜测阈值是否合理。
2. 保持“先补 provenance，再决定是否放大主动外化”的节奏，避免直接通过 channel 频率制造主动性假象。
3. 为 deferred trace 到治理决策消费增加更明确的回归测试锚点，并让 evaluation report 显式标记当前 artifact 是否具备 R18 阈值校准资格。

## 6. Completion Criteria

1. 系统能在无外部输入窗口触发可观测 proactive thought。
2. proactive 候选可进入正式 planner/policy/channel 路径并带 provenance。
3. policy 拒绝不会吞掉主动性结果，而会落为内部 trace 或延迟计划。
4. 自动化测试覆盖主动 thought、主动外化成功和拒绝降级场景。
5. 连续性验证能证明主动趋向不会在下一 tick 无痕消失。
