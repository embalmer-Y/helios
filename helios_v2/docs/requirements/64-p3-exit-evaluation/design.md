# Requirement 64 - P3 Exit Evaluation: Design

## 1. Title

R64 Design - P3 退出评估

## 2. Design Overview

R64 是一个纯评估需求：不引入新的 owner 行为、bridge 或 stage，而是以一组聚焦的自动化测试 + 文档审计来验证 P3 退出信号。

设计核心：在语义装配（store + embedding + external_signal_source + interoceptive_sampler）下运行多个 tick，采集 P3 范围内每个 owner 的 stage result，比较跨 tick 的状态变化，验证因果链端到端可追溯。

产出一个 `P3ExitVerdict` dataclass，汇总每个检查项的 pass/fail 与证据，供 `test_p3_exit_verdict` 函数断言。

## 3. Current State and Gap

### 3.1 P3 已交付状态

R35-R63 共 29 个需求已交付并验证（741 tests passed）。P3 范围内的 02-10 链所有 owner 的输入均已真实化。

### 3.2 评估缺口

- 没有单独的评估测试文件验证 P3 退出信号整体成立。
- 既有的 R35-R63 测试各自验证单个需求的行为，但没有一个测试汇总 P3 全范围的 FG-1/FG-2 达成证据。
- P3 退出判定目前只在文档中隐含（PROGRESS_FLOW 的 R63 更新），没有形式化的 pass/fail 报告。

## 4. Target Architecture

```
test_p3_exit_evaluation.py
├── _semantic_handle()         # 构建语义装配运行时（复用既有 helpers）
├── _external_batch()          # 构建外部刺激批次
├── _ConfigurableSampler       # 复用 R50/R51 的内感受采样器
│
├── test_p3_de_shim_coverage()          # FG-1: 03-10 stage results 存在 + 09 输入全真实
├── test_p3_fg2_emotion_evolves()       # FG-2.1: 情感状态跨 tick 演化
├── test_p3_fg2_causal_chain_external() # FG-2.2: 外部因果链
├── test_p3_fg2_causal_chain_internal() # FG-2.2: 内部因果链
└── test_p3_exit_verdict()              # 综合退出判定报告
```

### 4.1 装配配置

评估测试使用语义装配（最完整的 de-shim 路径）：

```python
handle = assemble_runtime(
    gateway=fake_gateway,
    experience_store=InMemoryExperienceStoreBackend(),
    embedding_gateway=fake_embedding_gateway,
    external_signal_source=SequenceExternalSignalSource(batches=(...)),
    interoceptive_sampler=ConfigurableSampler(cpu=..., memory=...),
)
```

### 4.2 数据流

```
变化外部刺激 (R59)
    ↓
02 sensory_ingress → StimulusBatch
    ↓
03 rapid_salience_appraisal → 五维真实 + aggregate (R35-R41)
    ↓
04 neuromodulator_system → levels (R36, dual-timescale R43)
    ↓
05 interoceptive_feeling_layer → feeling vector (R38, R44, R51)
    ↓
06 memory_affect_and_replay → affect-tagged memory (R45, R60, R61)
    ↓
07 workspace_competition → score + bounded attention (R46)
    ↓
08 reportable_conscious_content → ignition commitment (R47)
    ↓
09 thought_gating → fire/no_fire decision (R37, R48, R53, R55, R62, R63)
    ↓
10 directed_retrieval → recall intent from 11 handoff (R49)
```

## 5. Data Structures

### 5.1 P3ExitVerdict（评估退出判定）

```python
@dataclass
class P3ExitCheck:
    """单个检查项的 pass/fail + 证据。"""
    name: str
    passed: bool
    evidence: str

@dataclass
class P3ExitVerdict:
    """P3 退出评估的综合判定。"""
    checks: list[P3ExitCheck]
    out_of_scope_items: list[str]  # 不在 P3 范围的诚实记录

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> str:
        ...
```

### 5.2 复用的既有契约（不新增）

- `ThoughtGateSignalSnapshot` / `ThoughtGateResult`（`09`）
- `RapidSalienceVector`（`03`）
- `NeuromodulatorLevels`（`04`）
- `InteroceptiveFeelingVector` / `InteroceptiveFeelingState`（`05`）
- `MemoryReplayCandidate`（`06`/`07`）
- `WorkspaceCandidateSet` / `WorkingStateSnapshot`（`07`）

## 6. Module Changes

| 文件 | 操作 | 说明 |
|------|------|------|
| `tests/test_p3_exit_evaluation.py` | 新增 | P3 退出评估测试（~150 行） |
| `docs/requirements/64-*/requirement.md` | 新增 | 本需求 |
| `docs/requirements/64-*/design.md` | 新增 | 本设计 |
| `docs/requirements/64-*/task.md` | 新增 | 任务分解 |
| `docs/requirements/index.md` | 修改 | 添加 R64 行 |
| `docs/PROGRESS_FLOW.en.md` / `.zh-CN.md` | 修改 | 更新最近同步行 |
| `docs/OWNER_GUIDE.md` / `.zh-CN.md` | 修改 | P3 owner 下一步标注 |

无 owner 代码变更。无新 bridge、stage 或契约。

## 7. Migration Plan

无运行时行为变更，无需迁移。评估测试是 additive 的纯测试文件。

## 8. Failure Modes and Constraints

1. **语义装配不可用**：评估测试依赖 store + embedding 同时存在。若缺失则语义装配不启用，测试会 fail-fast（与既有 R35-R63 测试一致的 `CompositionError`）。
2. **外部刺激耗尽**：`SequenceExternalSignalSource` 耗尽后吐空批次。评估测试设计为在耗尽前采集足够 tick 数据（3-4 个 batch）。
3. **门控 no-fire**：高内感受压力可能导致 `09` no-fire。内部因果链测试使用低压力值保持在 fire 窗口内（与 R51/R53 一致）。
4. **默认装配不变**：评估测试不触碰默认装配路径。default/recency/channel-bound 装配字节级不变。

## 9. Observability and Logging

无新日志机制。评估测试通过 pytest 断言和 `P3ExitVerdict.summary()` 输出结果。

## 10. Validation Strategy

### 10.1 测试用例

| 测试函数 | 验证目标 | 验证方法 |
|----------|---------|---------|
| `test_p3_de_shim_coverage` | FG-1: 03-10 stage results 存在 | 语义装配 tick → 检查每个 stage result 非 None + 09 contributing_signals 含六项 |
| `test_p3_fg2_emotion_evolves` | FG-2.1: 情感跨 tick 演化 | 3 个不同刺激 tick → 04 levels / 05 feeling 至少两 tick 不同 |
| `test_p3_fg2_causal_chain_external` | FG-2.2: 外部因果链 | 两个不同刺激 → 03 salience 不同 → 04 levels 不同 → 05 feeling 不同 → 09 signals 不同 |
| `test_p3_fg2_causal_chain_internal` | FG-2.2: 内部因果链 | 低/高内感受压力 → 05 feeling 不同 → 07 workspace score 不同 |
| `test_p3_exit_verdict` | 综合退出判定 | 运行全部检查 → P3ExitVerdict.passed == True + out_of_scope 已列出 |

### 10.2 验证命令

```
pytest helios_v2/tests/test_p3_exit_evaluation.py -v
pytest helios_v2/tests -q  # 全套件
```
