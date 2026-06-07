# Requirement 64 - P3 Exit Evaluation (P3 退出评估)

## 1. Background and Problem

P3（去 shim 化感知-情感链）从 R35 到 R63 交付了 29 个需求，覆盖了认知主链 `02→10` 中所有 P3 目标 owner 的去 shim 化：

- `03` appraisal：五维 + 聚合全真实（R35/R39/R40/R41）
- `04` neuromodulator：appraisal 推导 + 双时间尺度跨 tick 演化（R36/R43/R56）
- `05` feeling：调质推导 + 双时间尺度 + 内感受信号消费（R38/R44/R51）
- `06` memory：形成/内容/惊讶/多候选全真实（R45/R52/R60/R61）
- `07` workspace：真实竞争 + 有界注意力瓶颈（R46）
- `08` consciousness：真实点火承诺（R47）
- `09` gate：六个输入全真实，无常量 shim（R37/R48/R53/R55/R62/R63）
- `10` retrieval：真实 recall intent（R49）

P3 的退出信号（`ARCHITECTURE_PHILOSOPHY` §13.1）为：

> "情感状态真实演化并可追溯地改变下游决策"

该退出信号服务于两条被锁定的终局验收标准：
- **FG-1**：`02→17` 认知主链的每一阶段都消费真实信号，而非 composition 注入的确定性常量 shim。
- **FG-2**：`04`/`05`/`06` 的情感状态在多 tick 上真实演化；至少存在一条可被评估层只读重建的因果链证明情感变化改变了下游决策；系统能在没有外部输入的纯内部 tick 上因情感/内感受状态而产生不同的内部行为。

目前没有形式化的评估机制来验证 P3 退出信号是否成立。需要一组自动化评估测试 + 文档审计，以可证伪的方式记录 P3 的退出判定。

## 2. Goal

以自动化评估测试 + 文档审计的形式，正式验证并记录 P3 退出信号（"情感状态真实演化并可追溯地改变下游决策"）的成立性，产出结构化的 pass/fail 退出判定报告，并诚实标注不在 P3 范围内的剩余 shim。

## 3. Functional Requirements

### 3.1 De-shim 覆盖率验证

1. 评估测试 must 在语义装配下验证 P3 范围内每个目标 owner（`03`/`04`/`05`/`06`/`07`/`08`/`09`/`10`）的 stage result 存在且非 None。
2. 评估测试 must 验证 `09` 门控的所有六个输入项（`arousal`/`global_activation_level`/`workload_pressure`/`temporal_signal`/`drive_urgency_signal`/`selected_stimuli`）在 `contributing_signals` 中出现。
3. 评估测试 must 验证 `03` appraisal 的五维（`novelty`/`uncertainty`/`social`/`threat`/`reward`）+ 聚合（`aggregate`）在语义装配下产出真实值。

### 3.2 FG-2.1 情感状态跨 tick 演化验证

1. 评估测试 must 使用变化的外部刺激（`SequenceExternalSignalSource`，R59）驱动至少 3 个 tick。
2. 评估测试 must 采集每 tick 的 `04` `NeuromodulatorStageResult.levels`、`05` `InteroceptiveFeelingStageResult.state.feeling`、`06` 形成的记忆 `affect_tag`。
3. 评估测试 must 断言至少两个 tick 的 `04` levels / `05` feeling / `06` affect_tag 不同（情感状态真实演化）。

### 3.3 FG-2.2 因果链验证

1. 评估测试 must 验证至少一条 FG-2 外部因果链：变化外部刺激 → `03` appraisal 变化 → `04` levels 变化 → `05` feeling 变化 → `09` gate 输入变化。
2. 评估测试 must 验证至少一条 FG-2 内部因果链：不同内感受压力 → `05` feeling 变化 → `07` workspace 竞争分变化。
3. 因果链验证 must 通过比较不同输入条件下的中间状态和下游决策来实现（而非仅断言存在性）。

### 3.4 结构化退出判定

1. 评估测试 must 产出一个结构化的 `P3ExitVerdict` 报告，包含每个检查项的 pass/fail + 证据。
2. 退出报告 must 包含 FG-1 覆盖率（P3 范围内）和 FG-2 因果链证据。
3. 退出报告 must 明确标注不在 P3 范围内的剩余 shim（诚实记录，不宣称超出范围的达成）。

### 3.5 不在 P3 范围的诚实记录

1. 评估 must 列出以下不在 P3 范围的已知留白：
   - 零-percept gate 前收口（R60 挂起项，独立后续需求）
   - `13` planner bridge channel state shim（P4 工具生态相关）
   - `14` identity governance 输入 shim（P6 自我修订相关）
   - 部分 P3 owner 的认知策略仍在 composition 中（owner-boundary 回收后续）
   - `FirstVersionSensorySource` 默认占位符（R59 已标注 NON-REAL，真实源属 wave_C）

## 4. Non-Functional Requirements

1. 评估测试 must 在离线（network-free）环境下运行，复用既有的确定性 fake provider 和 in-memory backend。
2. 评估测试 must 在 5 秒内完成（与既有测试套件一致的离线性能标准）。
3. 评估测试 must 不修改任何 owner 代码或引擎行为（纯 read-only 验证层）。

## 5. Code Behavior Constraints

1. 评估测试不得引入新的 owner 行为、bridge 或 stage。
2. 评估测试不得修改 `assemble_runtime` 或任何 owner 的引擎/契约。
3. 评估测试必须复用既有的 `SequenceExternalSignalSource`（R59）、`InMemoryExperienceStoreBackend`（R33）、`EmbeddingGateway` fake（R34）和 `_ConfigurableInteroceptiveSampler`（R50/R51）作为注入能力。

## 6. Impacted Modules

1. `helios_v2/tests/test_p3_exit_evaluation.py`（新增）— 评估测试文件。
2. `helios_v2/docs/requirements/64-p3-exit-evaluation/`（新增）— 需求包目录。
3. `helios_v2/docs/requirements/index.md`（修改）— 添加 R64 行。
4. `helios_v2/docs/PROGRESS_FLOW.en.md` / `.zh-CN.md`（修改）— 更新最近同步行。
5. `helios_v2/docs/OWNER_GUIDE.md` / `.zh-CN.md`（修改）— 更新 P3 相关 owner 的下一步。

## 7. Acceptance Criteria

1. `test_p3_exit_evaluation.py` 中的所有测试在语义装配下全绿。
2. 退出判定报告以代码可执行的形式（test 函数或 dataclass）产出 P3 pass 的结论。
3. FG-2.1 情感跨 tick 演化测试通过：至少两个 tick 的 `04`/`05` 状态不同。
4. FG-2.2 至少两条因果链测试通过：外部因果链（刺激→03→04→05→09）和内部因果链（压力→05→07）。
5. 不在 P3 范围的剩余 shim 被显式列出，不宣称超出 P3 范围的达成。
6. `index.md`、`PROGRESS_FLOW.*`、`OWNER_GUIDE.*` 同步更新。
7. 全测试套件（`pytest helios_v2/tests -q`）保持全绿。
