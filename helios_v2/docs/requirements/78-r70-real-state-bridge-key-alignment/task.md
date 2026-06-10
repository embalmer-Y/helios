# Requirement 78 - R70 Real-State Bridge Stage-Key Alignment — Task

## 1. Task Breakdown

### T1 — 创建 R78 需求包

文件已创建在 `docs/requirements/78-r70-real-state-bridge-key-alignment/`，含
`requirement.md`（8035 bytes）、`design.md`（7665 bytes）、`task.md`（本文件）。

### T2 — 修复 `composition/bridges.py` 三个 stage-result key

1. **L1980** `_affective_summary_text`（在 `SemanticEmbodiedPromptRequestBridge` 里）:
   - 旧：`feeling_result = stage_results.get("interoceptive_feeling")`
   - 新：`feeling_result = stage_results.get("interoceptive_feeling_layer")`

2. **L2085** `_internal_state_text`（neuromodulator 部分，在
   `SemanticInternalThoughtRequestBridge` 里）:
   - 旧：`nm_result = stage_results.get("neuromodulation")`
   - 新：`nm_result = stage_results.get("neuromodulator_system")`

3. **L2097** `_internal_state_text`（feeling 部分，在
   `SemanticInternalThoughtRequestBridge` 里）:
   - 旧：`feeling_result = stage_results.get("interoceptive_feeling")`
   - 新：`feeling_result = stage_results.get("interoceptive_feeling_layer")`

### T3 — 编写验证测试

新文件 `tests/test_r70_real_state_bridge_key_alignment.py`。

测试内容：

1. 用 mock LlmGatewayAPI + Fake CLI source 跑一个 tick（参考
   `scratch_llm_prompt_reconstruction.py` 的端到端捕获结构）。
2. 断言 LLM user message 包含 `"DA "` 前缀（真实 neuromodulator 投影）。
3. 断言 LLM user message 包含 `"arousal "` 前缀（真实 feeling 投影）。
4. 断言 LLM user message **不包含** 字面子串 `"neuromodulators at tonic baseline"`。
5. 断言 LLM user message **不包含** 字面子串 `"feeling at baseline"`。

测试不引入新的 mock 框架，复用 `helios_v2.composition.assemble_runtime` 和 mock gateway
pattern（在 `scratch_llm_prompt_reconstruction.py` 中已经验证过）。

### T4 — 跑测试，确认基线 834 → 835+

1. `pytest helios_v2/tests/test_r70_real_state_bridge_key_alignment.py -x -v` — 新测试绿。
2. `pytest helios_v2/tests/ -x` — 整库绿，基线从 834 passed 提升到 835+ passed。

### T5 — 重新跑端到端捕获验证

运行 `python scratch_llm_prompt_reconstruction.py`，3 个 tick 连续跑，输出原文
`scratch_llm_capture_output_r78_fixed.txt`。期望：

- 三个 tick 的 user message 都包含 `DA <value> NE <value> ...` 真实投影。
- 三个 tick 的 user message 都包含 `arousal <value>, valence <value>, tension <value>`
  真实投影。
- 三个 tick 的 user message 都 **不包含** 字面 fallback `"neuromodulators at tonic
  baseline"` 或 `"feeling at baseline"`。

### T6 — 文档同步

1. `helios_v2/docs/requirements/index.md` 在 R77 之后追加 R78 行，maturity
   `baseline_implementation`，状态 `implemented`。
2. `helios_v2/docs/PROGRESS_FLOW.en.md` 和 `PROGRESS_FLOW.zh-CN.md` 同步行命名 R78。
3. `helios_v2/docs/PHASE_METRICS.md` 确认 P1 metrics 不变。

### T7 — Git 提交

1. 分支 `fix/R78-r70-real-state-bridge-key-alignment`。
2. 单个 commit：`fix(R78): align R70 semantic bridges with stages.py stage names — 04/05
   projections now reach the LLM`。
3. 提交内容：
   - `composition/bridges.py`（3 个 key 改）
   - `tests/test_r70_real_state_bridge_key_alignment.py`（新测试）
   - `docs/requirements/index.md`（R78 行）
   - `docs/PROGRESS_FLOW.en.md`（同步行）
   - `docs/PROGRESS_FLOW.zh-CN.md`（同步行）
   - `docs/requirements/78-r70-real-state-bridge-key-alignment/{requirement,design,task}.md`
4. Push 到 origin。

## 2. Dependencies

1. T1 → T2 → T3 → T4 → T5 → T6 → T7（严格顺序）。
2. T2 不需要任何前置 owner 改动。
3. T3 不需要 T1 之外的任何外部包。
4. T5 复用 `scratch_llm_prompt_reconstruction.py` 的端到端结构，不引入新工具。

## 3. Files and Modules

### 修改

- `helios_v2/src/helios_v2/composition/bridges.py` — 3 个 key 改（约 1 行 × 3）。
- `helios_v2/docs/requirements/index.md` — +1 行。
- `helios_v2/docs/PROGRESS_FLOW.en.md` — 同步行。
- `helios_v2/docs/PROGRESS_FLOW.zh-CN.md` — 同步行。
- `helios_v2/docs/PHASE_METRICS.md` — 确认（无改动）。

### 新增

- `helios_v2/tests/test_r70_real_state_bridge_key_alignment.py` — ~80 行。

## 4. Implementation Order

1. **T1**（已完成）：写 R78 需求包（requirement.md / design.md / task.md）。
2. **T2**（下一步）：打 patch 到 bridges.py。
3. **T3**：写新测试。
4. **T4**：跑测试。
5. **T5**：跑端到端捕获。
6. **T6**：同步文档。
7. **T7**：commit + push。

## 5. Validation Plan

1. **新测试**：`pytest helios_v2/tests/test_r70_real_state_bridge_key_alignment.py -x`。
2. **整库回归**：`pytest helios_v2/tests/ -x`（期望 835+ passed）。
3. **端到端捕获**：`python scratch_llm_prompt_reconstruction.py` 跑 3 tick，原文确认。
4. **Owner-boundary guard**：`pytest helios_v2/tests/test_composition_owner_boundary_guard.py
   -x`（必须仍然绿，证明 bridges 仍然 owner-neutral）。

## 6. Completion Criteria

- [ ] `composition/bridges.py` L1980 / L2085 / L2097 三个 key 已修正。
- [ ] 新测试 `test_r70_real_state_bridge_key_alignment.py` 绿。
- [ ] 整库 835+ passed（基线 834 + 1 新增）。
- [ ] 端到端捕获显示 04 / 05 真实数值（不再 fallback）。
- [ ] R78 需求包三件套齐全且符合 authoring standard。
- [ ] Owner-boundary guard 仍绿。
- [ ] 文档同步完成（index.md / PROGRESS_FLOW.en / PROGRESS_FLOW.zh-CN / PHASE_METRICS）。
- [ ] commit 推送到 `fix/R78-r70-real-state-bridge-key-alignment` 分支。
